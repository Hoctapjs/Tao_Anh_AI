import io
import os
import zipfile
from datetime import datetime

import streamlit as st
from utils import (
    MAX_GENERATIONS,
    color_name_from_filename, extract_dominant_color,
    run_nano_multi, build_clipin_before_prompt,
    build_clipin_after_prompt, build_clipin_lifestyle_prompt,
    render_quota_bar, render_sidebar, save_used, run_with_retry,
)

token, _, _ = render_sidebar()
used, remaining = render_quota_bar()

st.title("📸 Bộ ảnh Highlight Clip-In")
st.caption("Tạo bộ 3 ảnh đồng nhất gương mặt cho mỗi màu: Before (tóc tự nhiên) → "
           "After (thêm vài line highlight mảnh) → Lifestyle (model tạo dáng). Tỷ lệ 1:1.")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ Ảnh model (tùy chọn)")
    model_file = st.file_uploader(
        "Upload 1 ảnh model tóc tự nhiên — bỏ trống để AI tự sinh model mới",
        type=["png", "jpg", "jpeg", "webp"], key="ci_model")
    if model_file:
        st.image(model_file.getvalue(), width=160)
        st.caption("Sẽ giữ gương mặt & tóc của ảnh này xuyên suốt 3 ảnh.")
    else:
        st.caption("Chưa có ảnh — AI sẽ tự sinh model. Chọn đặc điểm bên dưới:")
        ethnicity   = st.selectbox("Chủng tộc",  ["Da trắng", "Châu Á", "Da đen"], key="ci_eth")
        gender      = st.selectbox("Giới tính",  ["Nữ", "Nam"], key="ci_gen")
        hair_length = st.selectbox("Độ dài tóc", ["Dài", "Trung bình", "Ngắn"], key="ci_len")

with col2:
    st.subheader("2️⃣ Ảnh mẫu màu highlight")
    swatch_file = st.file_uploader(
        "Swatch màu (đặt tên kiểu 2-pink.png)",
        type=["png", "jpg", "jpeg", "webp"], key="ci_swatch")
    if swatch_file:
        st.image(swatch_file.getvalue(), width=160)

    hi_res = st.toggle("Xuất 4K siêu nét", value=False,
                       help="Ảnh độ phân giải cao (lâu hơn một chút).")
    st.caption("⚠️ Mỗi bộ tạo 3 ảnh = tốn **3 lượt**.")

run = st.button("🚀 Tạo bộ 3 ảnh", type="primary",
                use_container_width=True, disabled=(remaining == 0))

if run:
    if not token:
        st.error("Chưa nhập Replicate API Token ở sidebar.")
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

    s_bytes    = swatch_file.getvalue()
    color_name = color_name_from_filename(swatch_file.name)
    hex_color, _, _ = extract_dominant_color(s_bytes)
    has_ref    = model_file is not None

    safe_color = color_name.replace(" ", "-")
    results    = []
    progress   = st.progress(0.0, text="0/3")

    def do_step(idx, label, fn, out_name):
        global used, remaining
        if remaining <= 0:
            return None
        with st.status(f"[{idx}/3] {label}...", expanded=False) as status:
            try:
                data = run_with_retry(fn)
                used      += 1
                remaining  = MAX_GENERATIONS - used
                save_used(used)
                results.append((out_name, data))
                status.update(label=f"✅ {label} xong (còn {remaining} lượt)", state="complete")
                return data
            except Exception as e:
                status.update(label=f"❌ {label}: {e}", state="error")
                return None

    # --- Bước 1: Before ---
    if has_ref:
        m_bytes = model_file.getvalue()
        before_prompt = build_clipin_before_prompt(True)
        before_imgs   = [m_bytes]
    else:
        before_prompt = build_clipin_before_prompt(False, ethnicity, gender, hair_length)
        before_imgs   = []
    before_data = do_step(
        1, "Ảnh Before (tóc tự nhiên)",
        lambda: run_nano_multi(before_imgs, before_prompt, "1:1", hi_res),
        f"before_{safe_color}.png")
    progress.progress(1/3, text="1/3")

    # --- Bước 2 & 3: dùng chính ảnh Before làm gốc để đồng nhất gương mặt ---
    if before_data:
        after_data = do_step(
            2, "Ảnh After (thêm highlight)",
            lambda: run_nano_multi([before_data, s_bytes],
                                   build_clipin_after_prompt(color_name, hex_color),
                                   "1:1", hi_res),
            f"after_{safe_color}.png")
        progress.progress(2/3, text="2/3")

        do_step(
            3, "Ảnh Lifestyle (tạo dáng)",
            lambda: run_nano_multi([before_data, s_bytes],
                                   build_clipin_lifestyle_prompt(color_name, hex_color),
                                   "1:1", hi_res),
            f"lifestyle_{safe_color}.png")
        progress.progress(1.0, text="3/3")

    progress.empty()
    st.success(f"Hoàn thành! Tạo được {len(results)}/3 ảnh. Còn {remaining} lượt.")

    if results:
        st.divider()
        cols = st.columns(3)
        for idx, (name, data) in enumerate(results):
            with cols[idx % 3]:
                st.image(data, caption=name, use_container_width=True)
                st.download_button("⬇️ Tải", data, file_name=name,
                                   mime="image/png", key=f"ci_dl_{idx}")

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            for name, data in results:
                zf.writestr(name, data)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button("⬇️ Tải cả bộ (ZIP)", zip_buf.getvalue(),
                           file_name=f"clipin_{safe_color}_{ts}.zip",
                           mime="application/zip", type="primary",
                           use_container_width=True)
