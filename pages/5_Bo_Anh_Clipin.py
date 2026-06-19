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

    st.subheader("4️⃣ Chọn ảnh cần tạo")
    want_after     = st.checkbox("Ảnh After (có lọn màu)", value=True)
    want_before    = st.checkbox("Ảnh Before (tóc tự nhiên)", value=True)
    want_lifestyle = st.checkbox("Ảnh Lifestyle (tạo dáng)", value=True)

    hi_res = st.toggle("Xuất 4K siêu nét", value=False,
                       help="Ảnh độ phân giải cao (lâu hơn một chút).")

# Tính số lượt cần (theo dependency: Lifestyle cần After; faceswap dùng chung)
need_after_gen = want_after or want_lifestyle
any_selected   = want_after or want_before or want_lifestyle
cost = 0
if change_face and any_selected:
    cost += 1                      # faceswap
if need_after_gen:
    cost += 1                      # After (recolor)
if want_before:
    cost += 1                      # Before
if want_lifestyle:
    cost += 1                      # Lifestyle
with col2:
    st.caption(f"⚠️ Lựa chọn hiện tại tốn **{cost} lượt**.")

run = st.button("🚀 Tạo ảnh", type="primary",
                use_container_width=True, disabled=(remaining == 0))

if run:
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
        st.warning(f"⚠️ Chỉ còn {remaining} lượt — có thể không đủ cho cả bộ ({cost} lượt), "
                   f"app sẽ dừng khi hết.")

    os.environ["REPLICATE_API_TOKEN"] = token

    t_bytes    = template_file.getvalue()
    s_bytes    = swatch_file.getvalue()
    color_name = color_name_from_filename(swatch_file.name)
    hex_color, _, _ = extract_dominant_color(s_bytes)
    safe_color = color_name.replace(" ", "-")

    results  = {}   # key -> (name, data)
    total    = cost
    step_no  = [0]
    progress = st.progress(0.0, text=f"0/{total}")

    def do_step(key, label, fn, out_name=None):
        global used, remaining
        if remaining <= 0:
            return None
        step_no[0] += 1
        data = None
        with st.status(f"[{step_no[0]}/{total}] {label}...", expanded=False) as status:
            try:
                data = run_with_retry(fn)
                used      += 1
                remaining  = MAX_GENERATIONS - used
                save_used(used)
                if out_name:
                    results[key] = (out_name, data)
                status.update(label=f"✅ {label} xong (còn {remaining} lượt)", state="complete")
            except Exception as e:
                status.update(label=f"❌ {label}: {e}", state="error")
                data = None
        progress.progress(step_no[0] / total, text=f"{step_no[0]}/{total}")
        return data

    # --- Bước A (nếu đổi mặt): faceswap template, giữ nguyên lọn ---
    base_bytes = t_bytes
    if change_face:
        swapped = do_step(
            "swap", "Đổi gương mặt (giữ lọn gốc)",
            lambda: run_nano_multi([t_bytes],
                                   build_clipin_faceswap(ethnicity, gender), "1:1", hi_res),
            f"doimat_goc_{safe_color}.png")
        base_bytes = swapped  # None nếu lỗi

    # --- After: recolor lọn bằng đúng cách trang móc lai (chỉ khi cần) ---
    after_data = None
    if base_bytes is not None and need_after_gen:
        after_data = do_step(
            "after", "Ảnh After (recolor lọn)",
            lambda: run_nano_multi([base_bytes, s_bytes],
                                   build_nano_highlight_prompt(color_name, hex_color, "thin"),
                                   "1:1", hi_res),
            f"after_{safe_color}.png" if want_after else None)

    # --- Before = base -> bỏ hết lọn màu (không phụ thuộc After) ---
    if base_bytes is not None and want_before:
        do_step(
            "before", "Ảnh Before (bỏ lọn màu)",
            lambda: run_nano_multi([base_bytes], build_clipin_before_from_after(), "1:1", hi_res),
            f"before_{safe_color}.png")

    # --- Lifestyle = After -> đổi dáng (giữ mặt + lọn) ---
    if after_data is not None and want_lifestyle:
        do_step(
            "lifestyle", "Ảnh Lifestyle (tạo dáng)",
            lambda: run_nano_multi([after_data],
                                   build_clipin_lifestyle_from_after(color_name, hex_color),
                                   "1:1", hi_res),
            f"lifestyle_{safe_color}.png")

    progress.empty()
    st.success(f"Hoàn thành! Tạo được {len(results)} ảnh. Còn {remaining} lượt.")

    # Hiển thị theo thứ tự: Đổi mặt (gốc) -> Before -> After -> Lifestyle
    ordered = [results[k] for k in ("swap", "before", "after", "lifestyle") if k in results]
    if ordered:
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
                           file_name=f"clipin_{safe_color}_{ts}.zip",
                           mime="application/zip", type="primary",
                           use_container_width=True)
