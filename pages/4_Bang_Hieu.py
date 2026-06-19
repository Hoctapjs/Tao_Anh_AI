import io
import os
import zipfile
from datetime import datetime

import streamlit as st
from utils import (
    MAX_GENERATIONS, SIGNBOARD_SIZES, SIGNBOARD_STYLES,
    build_signboard_prompt, run_signboard_model,
    render_quota_bar, render_sidebar, save_used, run_with_retry,
)

token, _, _ = render_sidebar()
used, remaining = render_quota_bar()

st.title("🪧 Tạo bảng hiệu quảng cáo")
st.caption("Nhập thông tin cửa hàng, chọn kích thước và phong cách — AI sẽ thiết kế "
           "bảng hiệu với chữ tiếng Việt, theo nguyên tắc thiết kế bảng hiệu cửa hàng.")

st.divider()

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("1️⃣ Thông tin bảng hiệu")
    shop_name = st.text_input("Tên cửa hàng *", placeholder="VD: Cà Phê Sớm Mai")
    business  = st.text_input("Ngành nghề / mô tả", placeholder="VD: Cà phê - Trà sữa - Ăn vặt")
    slogan    = st.text_input("Slogan (tùy chọn)", placeholder="VD: Ngon từ hạt, chất từ tâm")
    contact   = st.text_input("SĐT / Địa chỉ (tùy chọn)", placeholder="VD: 0901 234 567 - 12 Lê Lợi")
    extra     = st.text_area("Mô tả tự do thêm (tùy chọn)",
                             placeholder="VD: nền xanh lá, có hình ly cà phê, viền gỗ...",
                             height=80)

with col2:
    st.subheader("2️⃣ Kích thước & phong cách")
    size_label  = st.selectbox("Kích thước bảng hiệu", list(SIGNBOARD_SIZES.keys()))
    style_label = st.selectbox("Phong cách thiết kế", list(SIGNBOARD_STYLES.keys()))
    n_variants  = st.slider("Số mẫu tạo ra", 1, 4, 2,
                            help="Mỗi mẫu là 1 phương án thiết kế khác nhau, tốn 1 lượt/mẫu.")

aspect_ratio = SIGNBOARD_SIZES[size_label]

if shop_name:
    st.info(f"Sẽ tạo **{n_variants} mẫu** bảng hiệu cho **{shop_name}** "
            f"({size_label}) — tốn **{n_variants} lượt**.")

run = st.button("🚀 Thiết kế bảng hiệu", type="primary",
                use_container_width=True, disabled=(remaining == 0))

if run:
    if not token:
        st.error("Chưa nhập Replicate API Token ở sidebar.")
        st.stop()
    if not shop_name.strip():
        st.error("Cần nhập ít nhất Tên cửa hàng.")
        st.stop()
    if remaining == 0:
        st.error("🚫 Đã hết lượt tạo.")
        st.stop()

    os.environ["REPLICATE_API_TOKEN"] = token
    total = n_variants

    if total > remaining:
        st.info(f"ℹ️ Cần {total} lượt nhưng chỉ còn {remaining}. App sẽ tự dừng khi hết lượt.")

    prompt = build_signboard_prompt(
        shop_name.strip(), business.strip(), contact.strip(),
        slogan.strip(), style_label, extra.strip())

    safe_name = shop_name.strip().replace(" ", "-")
    progress  = st.progress(0.0, text=f"0/{total}")
    results   = []
    stopped   = False

    for i in range(1, total + 1):
        if remaining <= 0:
            stopped = True
            break

        out_name = f"banghieu_{safe_name}_{i}.png"
        with st.status(f"[{i}/{total}] Đang thiết kế mẫu {i}...", expanded=False) as status:
            try:
                data = run_with_retry(lambda: run_signboard_model(prompt, aspect_ratio))
                used      += 1
                remaining  = MAX_GENERATIONS - used
                save_used(used)
                results.append((out_name, data))
                status.update(label=f"✅ Mẫu {i} xong (còn {remaining} lượt)",
                              state="complete")
            except Exception as e:
                status.update(label=f"❌ Mẫu {i}: {e}", state="error")

        progress.progress(i / total, text=f"{i}/{total}")

    progress.empty()
    if stopped:
        st.warning(f"⏹️ Dừng vì hết lượt. Đã tạo được {len(results)} mẫu.")
    else:
        st.success(f"Hoàn thành! Tạo được {len(results)} mẫu. Còn {remaining} lượt.")

    if results:
        st.divider()
        cols = st.columns(2)
        for idx, (name, data) in enumerate(results):
            with cols[idx % 2]:
                st.image(data, caption=name, use_container_width=True)
                st.download_button("⬇️ Tải", data, file_name=name,
                                   mime="image/png", key=f"sb_dl_{idx}")

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            for name, data in results:
                zf.writestr(name, data)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button("⬇️ Tải tất cả (ZIP)", zip_buf.getvalue(),
                           file_name=f"banghieu_{ts}.zip",
                           mime="application/zip", type="primary",
                           use_container_width=True)
