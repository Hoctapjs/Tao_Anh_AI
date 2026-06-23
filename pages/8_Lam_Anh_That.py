import io
import os
import zipfile
from datetime import datetime

import streamlit as st
from utils import (
    run_nano2_edit, render_sidebar, run_with_retry,
    build_realism_prompt, REALISM_CAMERA, REALISM_LIGHTING,
)

token, _, _ = render_sidebar()

st.title("✨ Làm ảnh chân thật")
st.caption(
    "Giữ nguyên 100% nội dung ảnh gốc (người, tóc, màu, dáng, nền) — chỉ làm cho ảnh "
    "trông như ảnh chụp thật trong mắt người xem, bớt cảm giác 'ảo / do AI tạo'. "
    "Phù hợp để xử lý các ảnh bị khách chê 'chưa thật'."
)

st.divider()

col1, col2 = st.columns([3, 2])

with col1:
    uploaded_files = st.file_uploader(
        "Ảnh cần làm chân thật (chọn nhiều ảnh để xử lý hàng loạt)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="realism_imgs",
    )
    if uploaded_files:
        n = len(uploaded_files)
        st.info(f"Đã chọn **{n} ảnh**.")
        preview_cols = st.columns(min(n, 5))
        for i, f in enumerate(uploaded_files[:5]):
            with preview_cols[i]:
                st.image(f.getvalue(), caption=f.name, use_container_width=True)
        if n > 5:
            st.caption(f"... và {n - 5} ảnh khác")

with col2:
    st.subheader("⚙️ Tùy chọn chân thực")

    intensity = st.select_slider(
        "Mức độ",
        options=["Nhẹ", "Vừa", "Mạnh"],
        value="Vừa",
        help="Nhẹ: giữ ảnh gần như nguyên bản, chỉ bớt 'ảo'. "
             "Mạnh: thêm rõ hạt phim/texture, trông như ảnh chụp film.",
    )

    st.markdown("**Độ không hoàn hảo** (chìa khóa của sự thật)")
    skin_texture = st.toggle("Texture da thật (lỗ chân lông)", value=True,
                             help="Xóa cảm giác da nhựa/bóng lì, thêm lỗ chân lông tự nhiên.")
    film_grain = st.toggle("Hạt phim / noise", value=True,
                           help="Thêm hạt nhiễu nhẹ cho cảm giác ảnh chụp thật.")
    lens_artifacts = st.toggle("Quang sai ống kính (viền tím nhẹ)", value=False,
                               help="Thêm chromatic aberration nhẹ ở mép tương phản cao.")

    camera = st.selectbox(
        "Máy ảnh / ống kính",
        list(REALISM_CAMERA.keys()),
        index=0,
        help="Mô phỏng chất màu & độ xóa phông của thiết bị thật.",
    )
    lighting = st.selectbox(
        "Ánh sáng",
        list(REALISM_LIGHTING.keys()),
        index=0,
        help="'Giữ nguyên ánh sáng' nếu không muốn đổi ánh sáng ảnh gốc.",
    )

    resolution = st.radio("Độ phân giải", ["1K", "2K", "4K"], index=1, horizontal=True,
                          help="4K nét nhất nhưng lâu hơn.")
    n_variants = st.slider("Số phương án mỗi ảnh", 1, 4, 1,
                           help="Tạo nhiều phương án để chọn tấm thật nhất.")

with st.expander("👀 Xem prompt sẽ dùng"):
    preview_prompt = build_realism_prompt(
        camera_en=REALISM_CAMERA.get(camera, ""),
        lighting_en=REALISM_LIGHTING.get(lighting, ""),
        skin_texture=skin_texture,
        film_grain=film_grain,
        lens_artifacts=lens_artifacts,
        intensity=intensity,
    )
    st.code(preview_prompt, language=None)

st.divider()

run = st.button(
    "🚀 Làm chân thật tất cả",
    type="primary",
    use_container_width=True,
    disabled=not uploaded_files,
)

if run:
    if not token:
        st.error("Chưa nhập Replicate API Token ở sidebar.")
        st.stop()
    if not uploaded_files:
        st.error("Chưa chọn ảnh nào.")
        st.stop()

    os.environ["REPLICATE_API_TOKEN"] = token

    prompt = build_realism_prompt(
        camera_en=REALISM_CAMERA.get(camera, ""),
        lighting_en=REALISM_LIGHTING.get(lighting, ""),
        skin_texture=skin_texture,
        film_grain=film_grain,
        lens_artifacts=lens_artifacts,
        intensity=intensity,
    )

    results = []
    total = len(uploaded_files) * n_variants
    progress = st.progress(0.0, text=f"0/{total}")
    done = 0

    for f in uploaded_files:
        name_stem = os.path.splitext(f.name)[0]
        img_bytes = f.getvalue()

        for v in range(1, n_variants + 1):
            done += 1
            suffix = f"_that" if n_variants == 1 else f"_that_{v}"
            out_name = f"{name_stem}{suffix}.png"

            with st.status(f"[{done}/{total}] {f.name} (phương án {v})...",
                           expanded=False) as status:
                try:
                    data = run_with_retry(
                        lambda b=img_bytes: run_nano2_edit([b], prompt, resolution)
                    )
                    results.append((out_name, data))
                    status.update(label=f"✅ {out_name}", state="complete")
                except Exception as e:
                    status.update(label=f"❌ {f.name} (p.án {v}): {e}", state="error")

            progress.progress(done / total, text=f"{done}/{total}")

    progress.empty()

    if results:
        st.success(f"Hoàn thành! Tạo được {len(results)}/{total} ảnh.")
        st.divider()
        cols = st.columns(min(len(results), 3))
        for idx, (name, data) in enumerate(results):
            with cols[idx % 3]:
                st.image(data, caption=name, use_container_width=True)
                st.download_button("⬇️ Tải", data, file_name=name,
                                   mime="image/png", key=f"real_dl_{idx}")

        if len(results) > 1:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                for name, data in results:
                    zf.writestr(name, data)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                "⬇️ Tải tất cả (ZIP)",
                zip_buf.getvalue(),
                file_name=f"lam_anh_that_{ts}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )
