import io
import os
import zipfile
from datetime import datetime

import streamlit as st
from utils import (
    MODEL_MULTI, MODEL_SINGLE, MODEL_SINGLE_MAX,
    color_name_from_filename, extract_dominant_color,
    label_from_filename, run_model, build_prompt,
    run_nano_banana, build_nano_prompt,
    render_sidebar, run_with_retry,
)

token, use_multi, _ = render_sidebar()

st.title("💇 Đổi màu tóc theo mẫu")
st.caption("Upload ảnh người mẫu + ảnh swatch màu tóc. App sẽ đổi màu tóc "
           "trong khi giữ nguyên khuôn mặt.")

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Ảnh người mẫu")
    model_files = st.file_uploader("Ảnh khuôn mặt (có thể chọn nhiều)",
                                   type=["png", "jpg", "jpeg", "webp"],
                                   accept_multiple_files=True, key="models")
    if model_files:
        st.image([f.getvalue() for f in model_files], width=110)

with col2:
    st.subheader("2️⃣ Ảnh mẫu tóc")
    swatch_files = st.file_uploader("Swatch màu tóc (đặt tên kiểu 2-dark-brown.png)",
                                    type=["png", "jpg", "jpeg", "webp"],
                                    accept_multiple_files=True, key="swatches")
    if swatch_files:
        st.image([f.getvalue() for f in swatch_files], width=110)

quality = st.radio(
    "Chất lượng ảnh",
    options=["Tiêu chuẩn", "Chất lượng cao", "Giữ mặt tốt nhất", "4K siêu nét"],
    horizontal=True,
    help="• Tiêu chuẩn / Chất lượng cao: đổi màu nhanh.\n"
         "• Giữ mặt tốt nhất: giữ khuôn mặt giống hệt, bám màu swatch sát nhất.\n"
         "• 4K siêu nét: như trên nhưng xuất ảnh độ phân giải 4K cho ảnh quảng bá "
         "(lâu hơn một chút).",
)

if model_files and swatch_files:
    total = len(model_files) * len(swatch_files)
    st.info(f"Sẽ tạo **{total} ảnh** ({len(model_files)} người mẫu × {len(swatch_files)} màu tóc).")

run = st.button("🚀 Bắt đầu tạo ảnh", type="primary",
                use_container_width=True)

if run:
    if not token:
        st.error("Chưa nhập Replicate API Token ở sidebar.")
        st.stop()
    if not model_files or not swatch_files:
        st.error("Cần ít nhất 1 ảnh người mẫu và 1 ảnh mẫu tóc.")
        st.stop()
    os.environ["REPLICATE_API_TOKEN"] = token
    use_nano = quality in ("Giữ mặt tốt nhất", "4K siêu nét")
    nano_hi_res = (quality == "4K siêu nét")
    if use_nano:
        model = None  # Nano Banana có hàm gọi riêng
    elif use_multi:
        model = MODEL_MULTI
    elif quality == "Chất lượng cao":
        model = MODEL_SINGLE_MAX
    else:
        model = MODEL_SINGLE
    tasks  = [(m, s) for m in model_files for s in swatch_files]
    total  = len(tasks)

    progress = st.progress(0.0, text=f"0/{total}")
    results  = []

    for i, (m_file, s_file) in enumerate(tasks, start=1):
        m_bytes    = m_file.getvalue()
        s_bytes    = s_file.getvalue()
        color_name = color_name_from_filename(s_file.name)
        hex_color, tone, level = extract_dominant_color(s_bytes)
        label      = label_from_filename(m_file.name)
        safe_color = color_name.replace(" ", "-")
        out_name   = f"{label}_{safe_color}.png"
        if use_nano:
            prompt = build_nano_prompt(color_name, hex_color)
            run_fn = lambda mb=m_bytes, sb=s_bytes, p=prompt: run_nano_banana(mb, sb, p, nano_hi_res)
        else:
            prompt = build_prompt(color_name, hex_color, tone, level, use_multi)
            run_fn = lambda mb=m_bytes, sb=s_bytes, p=prompt: run_model(model, mb, sb, p, use_multi)

        with st.status(f"[{i}/{total}] {label} + {color_name} ({hex_color})",
                       expanded=False) as status:
            try:
                data = run_with_retry(run_fn)
                results.append((out_name, data))
                status.update(label=f"✅ {out_name}", state="complete")
            except Exception as e:
                status.update(label=f"❌ {out_name}: {e}", state="error")

        progress.progress(i / total, text=f"{i}/{total}")

    progress.empty()
    st.success(f"Hoàn thành! Tạo được {len(results)} ảnh.")

    # Hiển thị kết quả
    if results:
        st.divider()
        cols = st.columns(3)
        for idx, (name, data) in enumerate(results):
            with cols[idx % 3]:
                st.image(data, caption=name, use_container_width=True)
                st.download_button("⬇️ Tải", data, file_name=name,
                                   mime="image/png", key=f"dl_{idx}")

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            for name, data in results:
                zf.writestr(name, data)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button("⬇️ Tải tất cả (ZIP)", zip_buf.getvalue(),
                           file_name=f"hair_results_{ts}.zip",
                           mime="application/zip", type="primary",
                           use_container_width=True)
