import io
import os
import zipfile
from datetime import datetime

import streamlit as st
from utils import (
    MAX_GENERATIONS,
    color_name_from_filename, extract_dominant_color,
    run_nano_multi, build_clipin_faceswap, build_nano_highlight_prompt,
    build_clipin_before_from_after, build_clipin_lifestyle_from_after,
    render_quota_bar, render_sidebar, save_used, run_with_retry,
)

token, _, _ = render_sidebar()
used, remaining = render_quota_bar()

st.title("📸 Bộ ảnh Highlight Clip-In")
st.caption("Upload 1 ảnh template (model đã gắn clip thật) + swatch màu. App sẽ recolor lọn "
           "sang màu swatch + đổi sang gương mặt mới. Chọn ảnh cần tạo: "
           "After / Before / Lifestyle (1:1).")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ Ảnh template (model gắn clip)")
    template_file = st.file_uploader(
        "Ảnh model đã gắn clip highlight thật (dùng làm khuôn)",
        type=["png", "jpg", "jpeg", "webp"], key="ci_template")
    if template_file:
        st.image(template_file.getvalue(), width=160)
        st.caption("Sẽ giữ kiểu tóc, vị trí lọn & dáng của ảnh này; chỉ đổi màu lọn + gương mặt.")

with col2:
    st.subheader("2️⃣ Ảnh mẫu màu highlight")
    swatch_file = st.file_uploader(
        "Swatch màu (đặt tên kiểu 2-pink.png)",
        type=["png", "jpg", "jpeg", "webp"], key="ci_swatch")
    if swatch_file:
        st.image(swatch_file.getvalue(), width=160)

    st.subheader("3️⃣ Gương mặt model mới")
    change_face = st.toggle("Đổi sang gương mặt mới", value=True,
                            help="Tắt: giữ nguyên mặt template, chỉ đổi màu lọn.")
    cc1, cc2 = st.columns(2)
    with cc1:
        ethnicity = st.selectbox("Chủng tộc", ["Da trắng", "Châu Á", "Da đen"],
                                 disabled=not change_face)
    with cc2:
        gender = st.selectbox("Giới tính", ["Nữ", "Nam"], disabled=not change_face)

    review_face = st.toggle("Duyệt gương mặt trước khi chạy tiếp", value=False,
                            disabled=not change_face,
                            help="Tạo gương mặt xong sẽ dừng để bạn xem; ưng thì bấm chạy tiếp.")

    st.subheader("4️⃣ Chọn ảnh cần tạo")
    want_after     = st.checkbox("Ảnh After (có lọn màu)", value=True)
    want_before    = st.checkbox("Ảnh Before (tóc tự nhiên)", value=True)
    want_lifestyle = st.checkbox("Ảnh Lifestyle (tạo dáng)", value=True)

    hi_res = st.toggle("Xuất 4K siêu nét", value=False,
                       help="Ảnh độ phân giải cao (lâu hơn một chút).")

# Số lượt cần (Lifestyle cần After; faceswap dùng chung)
need_after_gen = want_after or want_lifestyle
any_selected   = want_after or want_before or want_lifestyle
cost = 0
if change_face and any_selected:
    cost += 1
if need_after_gen:
    cost += 1
if want_before:
    cost += 1
if want_lifestyle:
    cost += 1
with col2:
    st.caption(f"⚠️ Lựa chọn hiện tại tốn **{cost} lượt**.")


# ===== Helpers =====
def gen_step(label, fn):
    """Chạy 1 bước: trừ quota, trả bytes (None nếu lỗi/hết lượt)."""
    global used, remaining
    if remaining <= 0:
        st.error("🚫 Hết lượt tạo.")
        return None
    with st.status(f"{label}...", expanded=False) as status:
        try:
            data = run_with_retry(fn)
            used      += 1
            remaining  = MAX_GENERATIONS - used
            save_used(used)
            status.update(label=f"✅ {label} (còn {remaining} lượt)", state="complete")
            return data
        except Exception as e:
            status.update(label=f"❌ {label}: {e}", state="error")
            return None


def make_faceswap(t_bytes):
    return gen_step("Đổi gương mặt (giữ lọn gốc)",
                    lambda: run_nano_multi([t_bytes],
                                           build_clipin_faceswap(ethnicity, gender),
                                           "1:1", hi_res))


def run_rest(base_bytes, s_bytes, color_name, hex_color, safe_color, swap_bytes=None):
    """Tạo After/Before/Lifestyle từ base_bytes. swap_bytes (nếu có) để hiển thị kèm."""
    results = {}
    if swap_bytes is not None:
        results["swap"] = (f"doimat_goc_{safe_color}.png", swap_bytes)

    after_data = None
    if base_bytes is not None and need_after_gen:
        after_data = gen_step(
            "Ảnh After (recolor lọn)",
            lambda: run_nano_multi([base_bytes, s_bytes],
                                   build_nano_highlight_prompt(color_name, hex_color, "thin"),
                                   "1:1", hi_res))
        if want_after and after_data is not None:
            results["after"] = (f"after_{safe_color}.png", after_data)

    if base_bytes is not None and want_before:
        b = gen_step("Ảnh Before (bỏ lọn màu)",
                     lambda: run_nano_multi([base_bytes], build_clipin_before_from_after(),
                                            "1:1", hi_res))
        if b is not None:
            results["before"] = (f"before_{safe_color}.png", b)

    if after_data is not None and want_lifestyle:
        l = gen_step("Ảnh Lifestyle (tạo dáng)",
                     lambda: run_nano_multi([after_data],
                                            build_clipin_lifestyle_from_after(color_name, hex_color),
                                            "1:1", hi_res))
        if l is not None:
            results["lifestyle"] = (f"lifestyle_{safe_color}.png", l)
    return results


def show_results(results):
    ordered = [results[k] for k in ("swap", "before", "after", "lifestyle") if k in results]
    if not ordered:
        return
    st.divider()
    cols = st.columns(3)
    for idx, (name, data) in enumerate(ordered):
        with cols[idx % 3]:
            st.image(data, caption=name, use_container_width=True)
            st.download_button("⬇️ Tải", data, file_name=name,
                               mime="image/png", key=f"ci_dl_{idx}")
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        for name, data in ordered:
            zf.writestr(name, data)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button("⬇️ Tải cả bộ (ZIP)", zip_buf.getvalue(),
                       file_name=f"clipin_{ts}.zip",
                       mime="application/zip", type="primary",
                       use_container_width=True)


def swatch_info():
    s_bytes    = swatch_file.getvalue()
    color_name = color_name_from_filename(swatch_file.name)
    hex_color, _, _ = extract_dominant_color(s_bytes)
    safe_color = color_name.replace(" ", "-")
    return s_bytes, color_name, hex_color, safe_color


st.divider()
use_review = change_face and review_face

# ================= CHẾ ĐỘ DUYỆT GƯƠNG MẶT =================
if use_review:
    pending = st.session_state.get("ci_swap_bytes")

    if pending is None:
        # Bước 1: tạo gương mặt
        if st.button("🚀 Bước 1: Tạo gương mặt", type="primary",
                     use_container_width=True, disabled=(remaining == 0)):
            if not token:
                st.error("Chưa nhập Replicate API Token ở sidebar.")
                st.stop()
            if not template_file:
                st.error("Cần ảnh template (model đã gắn clip).")
                st.stop()
            if remaining < 1:
                st.error("🚫 Đã hết lượt tạo.")
                st.stop()
            os.environ["REPLICATE_API_TOKEN"] = token
            swapped = make_faceswap(template_file.getvalue())
            if swapped is not None:
                st.session_state["ci_swap_bytes"] = swapped
                st.rerun()
    else:
        # Bước 2: xem gương mặt, xác nhận hoặc tạo lại
        st.markdown("### 👤 Gương mặt vừa tạo")
        st.image(pending, width=300)
        st.download_button("⬇️ Tải ảnh gương mặt", pending,
                           file_name="doimat_goc.png", mime="image/png")

        b1, b2, b3 = st.columns(3)
        with b1:
            confirm = st.button("✅ Xác nhận & chạy tiếp", type="primary",
                                use_container_width=True, disabled=(remaining == 0))
        with b2:
            regen = st.button("🔄 Tạo lại gương mặt", use_container_width=True,
                              disabled=(remaining == 0))
        with b3:
            cancel = st.button("❌ Hủy", use_container_width=True)

        if cancel:
            del st.session_state["ci_swap_bytes"]
            st.rerun()

        if regen:
            if not token:
                st.error("Chưa nhập Replicate API Token ở sidebar.")
                st.stop()
            os.environ["REPLICATE_API_TOKEN"] = token
            swapped = make_faceswap(template_file.getvalue())
            if swapped is not None:
                st.session_state["ci_swap_bytes"] = swapped
                st.rerun()

        if confirm:
            if not swatch_file:
                st.error("Cần ảnh swatch màu highlight để chạy tiếp.")
                st.stop()
            if not any_selected:
                st.error("Chọn ít nhất 1 ảnh cần tạo (After / Before / Lifestyle).")
                st.stop()
            os.environ["REPLICATE_API_TOKEN"] = token
            s_bytes, color_name, hex_color, safe_color = swatch_info()
            results = run_rest(pending, s_bytes, color_name, hex_color, safe_color,
                               swap_bytes=pending)
            del st.session_state["ci_swap_bytes"]
            st.success(f"Hoàn thành! Tạo được {len(results)} ảnh. Còn {remaining} lượt.")
            show_results(results)

# ================= CHẾ ĐỘ CHẠY HẾT QUY TRÌNH =================
else:
    if st.button("🚀 Tạo ảnh", type="primary",
                 use_container_width=True, disabled=(remaining == 0)):
        if not token:
            st.error("Chưa nhập Replicate API Token ở sidebar.")
            st.stop()
        if not template_file:
            st.error("Cần ảnh template (model đã gắn clip).")
            st.stop()
        if not swatch_file:
            st.error("Cần ảnh swatch màu highlight.")
            st.stop()
        if not any_selected:
            st.error("Chọn ít nhất 1 ảnh cần tạo (After / Before / Lifestyle).")
            st.stop()
        if remaining < 1:
            st.error("🚫 Đã hết lượt tạo.")
            st.stop()
        if remaining < cost:
            st.warning(f"⚠️ Chỉ còn {remaining} lượt — có thể không đủ ({cost} lượt), "
                       f"app sẽ dừng khi hết.")

        os.environ["REPLICATE_API_TOKEN"] = token
        s_bytes, color_name, hex_color, safe_color = swatch_info()

        base_bytes = template_file.getvalue()
        swap_bytes = None
        if change_face:
            swap_bytes = make_faceswap(base_bytes)
            base_bytes = swap_bytes  # None nếu lỗi

        results = run_rest(base_bytes, s_bytes, color_name, hex_color, safe_color,
                           swap_bytes=swap_bytes)
        st.success(f"Hoàn thành! Tạo được {len(results)} ảnh. Còn {remaining} lượt.")
        show_results(results)
