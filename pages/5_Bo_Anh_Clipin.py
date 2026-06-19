import io
import os
import zipfile
from datetime import datetime

import streamlit as st
from utils import (
    CLOTHING_COLORS, MODEL_SINGLE_MAX,
    color_name_from_filename, extract_dominant_color,
    run_nano_multi, run_nano_banana, run_model,
    build_clipin_faceswap, build_nano_highlight_prompt,
    build_clipin_before, build_clipin_lifestyle_from_after,
    render_sidebar, run_with_retry,
)

token, _, _ = render_sidebar()

st.title("📸 Bộ ảnh Highlight Clip-In")
st.caption("Upload template Before (tóc tự nhiên) + template After (đã gắn clip) + swatch. "
           "App đổi sang 1 gương mặt mới (khác hẳn) dùng chung cho cả bộ, recolor lọn theo swatch, "
           "đổi màu áo, biểu cảm Before nhẹ nhàng / After tự tin. Ảnh 1:1.")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ Template Before (tóc tự nhiên)")
    before_tmpl_file = st.file_uploader(
        "Ảnh model tóc tự nhiên, chưa gắn clip — lấy dáng/bố cục cho ảnh Before",
        type=["png", "jpg", "jpeg", "webp"], key="ci_before_tmpl")
    if before_tmpl_file:
        st.image(before_tmpl_file.getvalue(), width=140)

    st.subheader("2️⃣ Template After (đã gắn clip)")
    after_tmpl_file = st.file_uploader(
        "Ảnh model đã gắn clip highlight thật — lấy dáng/lọn cho ảnh After",
        type=["png", "jpg", "jpeg", "webp"], key="ci_after_tmpl")
    if after_tmpl_file:
        st.image(after_tmpl_file.getvalue(), width=140)

    st.subheader("3️⃣ Swatch màu highlight")
    swatch_file = st.file_uploader(
        "Swatch màu (đặt tên kiểu 2-pink.png)",
        type=["png", "jpg", "jpeg", "webp"], key="ci_swatch")
    if swatch_file:
        st.image(swatch_file.getvalue(), width=140)

with col2:
    st.subheader("4️⃣ Gương mặt & trang phục")
    change_face = st.toggle("Đổi sang gương mặt mới (khác hẳn)", value=True,
                            help="Tắt: giữ mặt template. Bật: tạo 1 model mới dùng chung Before+After.")
    cc1, cc2 = st.columns(2)
    with cc1:
        ethnicity = st.selectbox("Chủng tộc", ["Da trắng", "Châu Á", "Da đen"],
                                 disabled=not change_face)
    with cc2:
        gender = st.selectbox("Giới tính", ["Nữ", "Nam"], disabled=not change_face)

    clothing_label = st.selectbox("Màu áo model", list(CLOTHING_COLORS.keys()))
    clothing_en    = CLOTHING_COLORS[clothing_label]

    review_face = st.toggle("Duyệt gương mặt trước khi chạy tiếp", value=False,
                            disabled=not change_face,
                            help="Tạo gương mặt xong sẽ dừng để bạn xem; ưng thì bấm chạy tiếp.")

    st.subheader("5️⃣ Chọn ảnh cần tạo")
    want_after     = st.checkbox("Ảnh After (có lọn màu, tự tin)", value=True)
    want_before    = st.checkbox("Ảnh Before (tóc tự nhiên, nhẹ nhàng)", value=True)
    want_lifestyle = st.checkbox("Ảnh Lifestyle (tạo dáng)", value=True)

    hi_res = st.toggle("Xuất 4K siêu nét", value=False,
                       help="Ảnh độ phân giải cao (lâu hơn một chút).")

    after_engine = st.radio(
        "Engine recolor lọn (ảnh After)",
        ["nano-banana", "FLUX Kontext Max (giữ texture)"],
        horizontal=True,
        help="• nano-banana: bám màu tốt theo swatch, hỗ trợ 4K.\n"
             "• FLUX Kontext Max: giữ texture/sáng-tối lọn tự nhiên hơn, ít bị tô phẳng "
             "(màu theo mã hex, không 4K).")

# Số ảnh cần tạo
need_after_gen = want_after or want_lifestyle
any_selected   = want_after or want_before or want_lifestyle
need_swap      = change_face and any_selected
use_flux_after = after_engine.startswith("FLUX")


# ===== Helpers =====
def gen_step(label, fn):
    with st.status(f"{label}...", expanded=False) as status:
        try:
            data = run_with_retry(fn)
            status.update(label=f"✅ {label}", state="complete")
            return data
        except Exception as e:
            status.update(label=f"❌ {label}: {e}", state="error")
            return None


def make_faceswap(after_tmpl_bytes):
    return gen_step("Đổi gương mặt (giữ lọn gốc)",
                    lambda: run_nano_multi([after_tmpl_bytes],
                                           build_clipin_faceswap(ethnicity, gender,
                                                                 clothing_en, "confident"),
                                           "1:1", hi_res))


def run_rest(after_base, before_tmpl, identity_ref, s_bytes,
             color_name, hex_color, safe_color, swap_bytes=None):
    results = {}
    if swap_bytes is not None:
        results["swap"] = (f"doimat_goc_{safe_color}.png", swap_bytes)

    after_data = None
    if after_base is not None and need_after_gen:
        if use_flux_after:
            # FLUX Kontext Max single-image: không có ảnh swatch nên không bị dán collage
            recolor_prompt = build_nano_highlight_prompt(color_name, hex_color, "thin",
                                                         with_swatch=False)
            run_after = lambda: run_model(MODEL_SINGLE_MAX, after_base, None, recolor_prompt, False)
        else:
            recolor_prompt = build_nano_highlight_prompt(color_name, hex_color, "thin")
            run_after = lambda: run_nano_banana(after_base, s_bytes, recolor_prompt, hi_res)
        after_data = gen_step("Ảnh After (recolor lọn)", run_after)
        if want_after and after_data is not None:
            results["after"] = (f"after_{safe_color}.png", after_data)

    if before_tmpl is not None and want_before:
        match = change_face and identity_ref is not None
        # ảnh 1 = after (face+outfit đã confirm), ảnh 2 = before_tmpl (pose ref)
        # fallback về identity_ref nếu after chưa được tạo
        face_src = after_data if after_data is not None else identity_ref
        imgs = [face_src, before_tmpl] if match else [before_tmpl]
        b = gen_step("Ảnh Before (tóc tự nhiên)",
                     lambda: run_nano_multi(imgs,
                                            build_clipin_before(clothing_en, match),
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
        if st.button("🚀 Bước 1: Tạo gương mặt", type="primary",
                     use_container_width=True):
            if not token:
                st.error("Chưa nhập Replicate API Token ở sidebar.")
                st.stop()
            if not after_tmpl_file:
                st.error("Cần ảnh Template After (đã gắn clip) để tạo gương mặt.")
                st.stop()
            os.environ["REPLICATE_API_TOKEN"] = token
            swapped = make_faceswap(after_tmpl_file.getvalue())
            if swapped is not None:
                st.session_state["ci_swap_bytes"] = swapped
                st.rerun()
    else:
        st.markdown("### 👤 Gương mặt vừa tạo")
        st.image(pending, width=300)
        st.download_button("⬇️ Tải ảnh gương mặt", pending,
                           file_name="doimat_goc.png", mime="image/png")

        b1, b2, b3 = st.columns(3)
        with b1:
            confirm = st.button("✅ Xác nhận & chạy tiếp", type="primary",
                                use_container_width=True)
        with b2:
            regen = st.button("🔄 Tạo lại gương mặt", use_container_width=True,
                              )
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
            swapped = make_faceswap(after_tmpl_file.getvalue())
            if swapped is not None:
                st.session_state["ci_swap_bytes"] = swapped
                st.rerun()

        if confirm:
            if not swatch_file:
                st.error("Cần ảnh swatch màu highlight để chạy tiếp.")
                st.stop()
            if want_before and not before_tmpl_file:
                st.error("Cần ảnh Template Before để tạo ảnh Before.")
                st.stop()
            if not any_selected:
                st.error("Chọn ít nhất 1 ảnh cần tạo.")
                st.stop()
            os.environ["REPLICATE_API_TOKEN"] = token
            s_bytes, color_name, hex_color, safe_color = swatch_info()
            before_tmpl = before_tmpl_file.getvalue() if before_tmpl_file else None
            results = run_rest(pending, before_tmpl, pending, s_bytes,
                               color_name, hex_color, safe_color, swap_bytes=pending)
            del st.session_state["ci_swap_bytes"]
            st.success(f"Hoàn thành! Tạo được {len(results)} ảnh.")
            show_results(results)

# ================= CHẾ ĐỘ CHẠY HẾT QUY TRÌNH =================
else:
    if st.button("🚀 Tạo ảnh", type="primary",
                 use_container_width=True):
        if not token:
            st.error("Chưa nhập Replicate API Token ở sidebar.")
            st.stop()
        if not after_tmpl_file:
            st.error("Cần ảnh Template After (đã gắn clip).")
            st.stop()
        if not swatch_file:
            st.error("Cần ảnh swatch màu highlight.")
            st.stop()
        if want_before and not before_tmpl_file:
            st.error("Cần ảnh Template Before để tạo ảnh Before.")
            st.stop()
        if not any_selected:
            st.error("Chọn ít nhất 1 ảnh cần tạo.")
            st.stop()

        os.environ["REPLICATE_API_TOKEN"] = token
        s_bytes, color_name, hex_color, safe_color = swatch_info()
        before_tmpl = before_tmpl_file.getvalue() if before_tmpl_file else None

        after_base   = after_tmpl_file.getvalue()
        swap_bytes   = None
        identity_ref = None
        if change_face:
            swap_bytes = make_faceswap(after_tmpl_file.getvalue())
            after_base   = swap_bytes      # None nếu lỗi
            identity_ref = swap_bytes

        results = run_rest(after_base, before_tmpl, identity_ref, s_bytes,
                           color_name, hex_color, safe_color, swap_bytes=swap_bytes)
        st.success(f"Hoàn thành! Tạo được {len(results)} ảnh.")
        show_results(results)
