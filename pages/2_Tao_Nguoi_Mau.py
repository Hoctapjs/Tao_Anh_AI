import io
import os
import zipfile
from datetime import datetime

import streamlit as st
from utils import (
    MAX_GENERATIONS, MODEL_TEXT2IMG, MODEL_TEXT2IMG_ULTRA,
    color_name_from_filename, extract_dominant_color,
    label_from_filename, run_text2img_model, build_text2img_prompt,
    render_quota_bar, render_sidebar, save_used, run_with_retry,
)

token, _, _ = render_sidebar()
used, remaining = render_quota_bar()

st.title("🧑 Tạo người mẫu mới từ màu tóc")
st.caption("Chỉ cần upload ảnh swatch màu tóc — AI sẽ tự sinh người mẫu hoàn toàn mới "
           "với màu tóc đó. Không cần ảnh người mẫu đầu vào.")

st.divider()

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1️⃣ Ảnh mẫu tóc")
    swatch_files = st.file_uploader(
        "Swatch màu tóc (đặt tên kiểu 2-dark-brown.png)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True, key="swatches2")
    if swatch_files:
        st.image([f.getvalue() for f in swatch_files], width=110)

with col2:
    st.subheader("2️⃣ Tùy chọn người mẫu")
    ethnicity   = st.selectbox("Chủng tộc",  ["Da trắng", "Châu Á", "Da đen"])
    gender      = st.selectbox("Giới tính",  ["Nữ", "Nam"])
    hair_length = st.selectbox("Độ dài tóc", ["Dài", "Trung bình", "Ngắn"])

    quality = st.radio(
        "Chất lượng ảnh",
        options=["Tiêu chuẩn", "Chất lượng cao"],
        horizontal=True,
        help="Chất lượng cao cho ảnh sắc nét, chi tiết hơn — tốn 2 lượt/ảnh.",
    )
    selected_model = MODEL_TEXT2IMG_ULTRA if quality == "Chất lượng cao" else MODEL_TEXT2IMG

    # Action presets phổ biến cho chụp ảnh demo tóc giả
    ACTION_PRESETS = {
        "— Không chọn —": "",
        "Nhìn thẳng, biểu cảm tự nhiên": "looking straight at camera with a natural, relaxed expression",
        "Cười tươi nhìn thẳng": "smiling warmly at the camera, bright and confident",
        "Biểu cảm nghiêm, editorial": "serious editorial expression, intense gaze at camera",
        "Nhìn nghiêng, tóc xõa": "turning slightly to the side, hair flowing naturally to showcase texture",
        "Nhìn qua vai": "looking over the shoulder towards the camera, hair draped behind",
        "Tóc bay, tung tóc": "hair mid-toss in the air, dynamic movement, hair strands visible",
        "Tay vuốt tóc": "gently running fingers through hair, showcasing hair texture and shine",
        "Cúi đầu nhìn xuống": "looking down gracefully, head slightly tilted, hair falling forward",
        "Nghiêng đầu nhẹ": "head tilted slightly to one side, soft and approachable expression",
        "Quay lưng, nhìn lại": "back to camera, turning head to look back over shoulder, showing hair from behind",
    }

    preset = st.selectbox(
        "Action mẫu (chọn nhanh)",
        options=list(ACTION_PRESETS.keys()),
        help="Chọn tư thế phổ biến cho ảnh demo tóc giả.")

    custom_action = st.text_input(
        "Hoặc nhập thêm mô tả tự do (tiếng Anh)",
        placeholder="VD: sitting on a stool, wind blowing hair gently...",
        help="Bổ sung thêm chi tiết tư thế ngoài preset ở trên.")

    # Ghép preset + custom
    parts  = [p for p in [ACTION_PRESETS[preset], custom_action.strip()] if p]
    action = ", ".join(parts)

    if action:
        st.caption(f"📝 Prompt action: _{action}_")
    st.caption("AI sẽ tự sinh khuôn mặt — mỗi ảnh là một người khác nhau.")

if swatch_files:
    total = len(swatch_files)
    st.info(f"Sẽ tạo **{total} ảnh** (1 ảnh mỗi màu tóc) — tốn **{total} lượt**.")

run = st.button("🚀 Tạo người mẫu", type="primary",
                use_container_width=True, disabled=(remaining == 0))

if run:
    if not token:
        st.error("Chưa nhập Replicate API Token ở sidebar.")
        st.stop()
    if not swatch_files:
        st.error("Cần ít nhất 1 ảnh mẫu tóc.")
        st.stop()
    if remaining == 0:
        st.error("🚫 Đã hết lượt tạo.")
        st.stop()

    os.environ["REPLICATE_API_TOKEN"] = token
    total   = len(swatch_files)

    if total > remaining:
        st.info(f"ℹ️ Batch cần {total} lượt nhưng chỉ còn {remaining}. "
                f"App sẽ tự dừng khi hết lượt.")

    progress = st.progress(0.0, text=f"0/{total}")
    results  = []
    stopped  = False

    for i, s_file in enumerate(swatch_files, start=1):
        if remaining <= 0:
            stopped = True
            break

        s_bytes    = s_file.getvalue()
        color_name = color_name_from_filename(s_file.name)
        hex_color, tone, level = extract_dominant_color(s_bytes)
        safe_color = color_name.replace(" ", "-")
        out_name   = f"generated_{safe_color}.png"
        prompt     = build_text2img_prompt(
            color_name, hex_color, tone, level,
            ethnicity, gender, hair_length, action)

        with st.status(f"[{i}/{total}] Tạo người mẫu tóc {color_name} ({hex_color})",
                       expanded=False) as status:
            try:
                data = run_with_retry(lambda: run_text2img_model(prompt, selected_model))
                used      += 1
                remaining  = MAX_GENERATIONS - used
                save_used(used)
                results.append((out_name, data))
                status.update(label=f"✅ {out_name} (còn {remaining} lượt)",
                              state="complete")
            except Exception as e:
                status.update(label=f"❌ {out_name}: {e}", state="error")

        progress.progress(i / total, text=f"{i}/{total}")

    progress.empty()
    if stopped:
        st.warning(f"⏹️ Dừng vì hết lượt. Đã tạo được {len(results)} ảnh.")
    else:
        st.success(f"Hoàn thành! Tạo được {len(results)} ảnh. Còn {remaining} lượt.")

    # Hiển thị kết quả
    if results:
        st.divider()
        cols = st.columns(3)
        for idx, (name, data) in enumerate(results):
            with cols[idx % 3]:
                st.image(data, caption=name, use_container_width=True)
                st.download_button("⬇️ Tải", data, file_name=name,
                                   mime="image/png", key=f"gen_{idx}")

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            for name, data in results:
                zf.writestr(name, data)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button("⬇️ Tải tất cả (ZIP)", zip_buf.getvalue(),
                           file_name=f"generated_models_{ts}.zip",
                           mime="application/zip", type="primary",
                           use_container_width=True)
