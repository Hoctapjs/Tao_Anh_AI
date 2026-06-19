import io
import os
import zipfile
from datetime import datetime

import streamlit as st
from utils import (
    MAX_GENERATIONS,
    color_name_from_filename, extract_dominant_color,
    run_nano_multi, build_clipin_after_recolor,
    build_clipin_before_from_after, build_clipin_lifestyle_from_after,
    render_quota_bar, render_sidebar, save_used, run_with_retry,
)

token, _, _ = render_sidebar()
used, remaining = render_quota_bar()

st.title("📸 Bộ ảnh Highlight Clip-In")
st.caption("Upload 1 ảnh template (model đã gắn clip thật) + swatch màu. App sẽ recolor lọn "
           "sang màu swatch + đổi sang gương mặt mới, rồi tạo bộ 3 ảnh đồng nhất: "
           "Before → After → Lifestyle (1:1).")

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

    hi_res = st.toggle("Xuất 4K siêu nét", value=False,
                       help="Ảnh độ phân giải cao (lâu hơn một chút).")
    st.caption("⚠️ Mỗi bộ tạo 3 ảnh = tốn **3 lượt**.")

run = st.button("🚀 Tạo bộ 3 ảnh", type="primary",
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
    if remaining < 1:
        st.error("🚫 Đã hết lượt tạo.")
        st.stop()
    if remaining < 3:
        st.warning(f"⚠️ Chỉ còn {remaining} lượt — có thể không đủ cho cả 3 ảnh, app sẽ dừng khi hết.")

    os.environ["REPLICATE_API_TOKEN"] = token

    t_bytes    = template_file.getvalue()
    s_bytes    = swatch_file.getvalue()
    color_name = color_name_from_filename(swatch_file.name)
    hex_color, _, _ = extract_dominant_color(s_bytes)
    safe_color = color_name.replace(" ", "-")

    results  = {}   # key -> (name, data)
    progress = st.progress(0.0, text="0/3")

    def do_step(idx, key, label, fn, out_name):
        global used, remaining
        if remaining <= 0:
            return None
        with st.status(f"[{idx}/3] {label}...", expanded=False) as status:
            try:
                data = run_with_retry(fn)
                used      += 1
                remaining  = MAX_GENERATIONS - used
                save_used(used)
                results[key] = (out_name, data)
                status.update(label=f"✅ {label} xong (còn {remaining} lượt)", state="complete")
                return data
            except Exception as e:
                status.update(label=f"❌ {label}: {e}", state="error")
                return None

    # --- Bước 1: After = template + swatch -> recolor lọn + đổi mặt ---
    after_data = do_step(
        1, "after", "Ảnh After (recolor lọn + đổi mặt)",
        lambda: run_nano_multi(
            [t_bytes, s_bytes],
            build_clipin_after_recolor(color_name, hex_color, ethnicity, gender, change_face),
            "1:1", hi_res),
        f"after_{safe_color}.png")
    progress.progress(1/3, text="1/3")

    # --- Bước 2: Before = After -> bỏ hết lọn màu (giữ mặt/dáng) ---
    if after_data:
        do_step(
            2, "before", "Ảnh Before (bỏ lọn màu)",
            lambda: run_nano_multi([after_data], build_clipin_before_from_after(), "1:1", hi_res),
            f"before_{safe_color}.png")
        progress.progress(2/3, text="2/3")

        # --- Bước 3: Lifestyle = After -> đổi dáng (giữ mặt + lọn) ---
        do_step(
            3, "lifestyle", "Ảnh Lifestyle (tạo dáng)",
            lambda: run_nano_multi([after_data],
                                   build_clipin_lifestyle_from_after(color_name, hex_color),
                                   "1:1", hi_res),
            f"lifestyle_{safe_color}.png")
        progress.progress(1.0, text="3/3")

    progress.empty()
    st.success(f"Hoàn thành! Tạo được {len(results)}/3 ảnh. Còn {remaining} lượt.")

    # Hiển thị theo thứ tự logic: Before -> After -> Lifestyle
    ordered = [results[k] for k in ("before", "after", "lifestyle") if k in results]
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
