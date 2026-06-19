import io
import os
import zipfile
from datetime import datetime

import streamlit as st
from utils import (
    run_upscale_model, render_quota_bar, render_sidebar, run_with_retry,
)

token, _, _ = render_sidebar()
used, remaining = render_quota_bar()

st.title("🔍 Upscale ảnh siêu nét")
st.caption(
    "Upload nhiều ảnh cùng lúc — AI sẽ phóng to và làm sắc nét từng ảnh (Real-ESRGAN). "
    "Mỗi ảnh tốn **1 lượt**."
)

st.divider()

col1, col2 = st.columns([2, 1])

with col1:
    uploaded_files = st.file_uploader(
        "Chọn ảnh cần upscale (có thể chọn nhiều file)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="upscale_files",
    )

with col2:
    scale = st.select_slider(
        "Hệ số phóng to",
        options=[2, 4, 6, 8, 10],
        value=4,
        help="4x là tốt nhất cho hầu hết ảnh. Hệ số lớn = file nặng hơn.",
    )
    face_enhance = st.toggle(
        "Tăng cường khuôn mặt",
        value=False,
        help="Dùng GFPGAN để làm sắc nét mặt người — bật nếu ảnh có mặt người.",
    )

if uploaded_files:
    n = len(uploaded_files)
    st.info(f"Đã chọn **{n} ảnh** — sẽ tốn **{n} lượt** (còn {remaining} lượt).")

    if n > remaining:
        st.warning(f"⚠️ Chỉ còn {remaining} lượt, app sẽ dừng sau {remaining} ảnh.")

    # Preview thumbnail
    preview_cols = st.columns(min(n, 5))
    for i, f in enumerate(uploaded_files[:5]):
        with preview_cols[i]:
            st.image(f.getvalue(), caption=f.name, use_container_width=True)
    if n > 5:
        st.caption(f"... và {n - 5} ảnh khác")

st.divider()

run = st.button(
    "🚀 Upscale tất cả",
    type="primary",
    use_container_width=True,
    disabled=(remaining == 0 or not uploaded_files),
)

if run:
    if not token:
        st.error("Chưa nhập Replicate API Token ở sidebar.")
        st.stop()
    if not uploaded_files:
        st.error("Chưa chọn ảnh nào.")
        st.stop()
    if remaining == 0:
        st.error("🚫 Đã hết lượt tạo.")
        st.stop()

    os.environ["REPLICATE_API_TOKEN"] = token

    results = []
    total = min(len(uploaded_files), remaining)
    progress = st.progress(0.0, text=f"0/{total}")

    for i, f in enumerate(uploaded_files[:total], start=1):
        name_stem = os.path.splitext(f.name)[0]
        out_name = f"{name_stem}_upscale_{scale}x.png"

        with st.status(f"[{i}/{total}] {f.name}...", expanded=False) as status:
            try:
                data = run_with_retry(
                    lambda img=f.getvalue(): run_upscale_model(img, scale, face_enhance)
                )
                from utils import save_used, load_used, MAX_GENERATIONS
                used_now = load_used() + 1
                save_used(used_now)
                remaining = MAX_GENERATIONS - used_now
                results.append((out_name, data))
                status.update(
                    label=f"✅ {f.name} → {out_name} (còn {remaining} lượt)",
                    state="complete",
                )
            except Exception as e:
                status.update(label=f"❌ {f.name}: {e}", state="error")

        progress.progress(i / total, text=f"{i}/{total}")

    progress.empty()

    if results:
        st.success(f"Hoàn thành! Upscale được {len(results)}/{total} ảnh. Còn {remaining} lượt.")
        st.divider()

        cols = st.columns(min(len(results), 3))
        for idx, (name, data) in enumerate(results):
            with cols[idx % 3]:
                st.image(data, caption=name, use_container_width=True)
                st.download_button(
                    "⬇️ Tải",
                    data,
                    file_name=name,
                    mime="image/png",
                    key=f"up_dl_{idx}",
                )

        if len(results) > 1:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                for name, data in results:
                    zf.writestr(name, data)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                "⬇️ Tải tất cả (ZIP)",
                zip_buf.getvalue(),
                file_name=f"upscale_{ts}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )
