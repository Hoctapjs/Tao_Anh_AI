import io
import os
import zipfile
from datetime import datetime

import streamlit as st
from utils import (
    run_nano2_edit, render_sidebar, run_with_retry,
)

token, _, _ = render_sidebar()

st.title("🎨 Chỉnh sửa ảnh (nano-banana-2)")
st.caption("Upload ảnh + nhập yêu cầu chỉnh sửa bằng lời (tiếng Việt hoặc tiếng Anh). "
           "AI sẽ chỉnh sửa theo mô tả của bạn. Có thể upload nhiều ảnh để kết hợp.")

st.divider()

col1, col2 = st.columns([3, 2])

with col1:
    uploaded_files = st.file_uploader(
        "Ảnh cần chỉnh sửa (có thể chọn nhiều ảnh để kết hợp)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="edit_imgs",
    )
    if uploaded_files:
        st.image([f.getvalue() for f in uploaded_files], width=120)

    prompt = st.text_area(
        "Yêu cầu chỉnh sửa",
        placeholder="VD: đổi nền thành bãi biển hoàng hôn; xóa người phía sau; "
                    "đổi áo sang màu đỏ; thêm ánh sáng studio chuyên nghiệp...",
        height=130,
    )

with col2:
    st.subheader("⚙️ Tùy chọn")
    resolution = st.radio("Độ phân giải", ["1K", "2K", "4K"], index=1, horizontal=True,
                          help="4K nét nhất nhưng lâu hơn.")
    keep_ratio = st.toggle("Giữ tỷ lệ ảnh gốc", value=True,
                           help="Tắt để chọn tỷ lệ khác.")
    aspect = None
    if not keep_ratio:
        aspect = st.selectbox("Tỷ lệ khung", ["1:1", "2:3", "3:2", "16:9", "9:16", "4:3", "3:4"])

    n_variants = st.slider("Số phương án tạo ra", 1, 4, 1,
                           help="Mỗi phương án là 1 lần chỉnh sửa khác nhau.")

run = st.button("🚀 Chỉnh sửa ảnh", type="primary",
                use_container_width=True, disabled=(not uploaded_files))

if run:
    if not token:
        st.error("Chưa nhập Replicate API Token ở sidebar.")
        st.stop()
    if not uploaded_files:
        st.error("Chưa chọn ảnh nào.")
        st.stop()
    if not prompt.strip():
        st.error("Cần nhập yêu cầu chỉnh sửa.")
        st.stop()

    os.environ["REPLICATE_API_TOKEN"] = token
    images_bytes = [f.getvalue() for f in uploaded_files]

    progress = st.progress(0.0, text=f"0/{n_variants}")
    results = []

    for i in range(1, n_variants + 1):
        with st.status(f"[{i}/{n_variants}] Đang chỉnh sửa...", expanded=False) as status:
            try:
                data = run_with_retry(
                    lambda: run_nano2_edit(images_bytes, prompt.strip(), resolution, aspect))
                results.append((f"chinhsua_{i}.png", data))
                status.update(label=f"✅ Phương án {i} xong", state="complete")
            except Exception as e:
                status.update(label=f"❌ Phương án {i}: {e}", state="error")
        progress.progress(i / n_variants, text=f"{i}/{n_variants}")

    progress.empty()

    if results:
        st.success(f"Hoàn thành! Tạo được {len(results)} ảnh.")
        st.divider()
        cols = st.columns(min(len(results), 2))
        for idx, (name, data) in enumerate(results):
            with cols[idx % 2]:
                st.image(data, caption=name, use_container_width=True)
                st.download_button("⬇️ Tải", data, file_name=name,
                                   mime="image/png", key=f"edit_dl_{idx}")

        if len(results) > 1:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                for name, data in results:
                    zf.writestr(name, data)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button("⬇️ Tải tất cả (ZIP)", zip_buf.getvalue(),
                               file_name=f"chinhsua_{ts}.zip",
                               mime="application/zip", type="primary",
                               use_container_width=True)
