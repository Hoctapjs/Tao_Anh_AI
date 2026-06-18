import io
import os
import re
import json
import zipfile
import time
from datetime import datetime

import replicate
import streamlit as st
from PIL import Image

# ====== CẤU HÌNH MODEL ======
MODEL_MULTI = "flux-kontext-apps/multi-image-kontext-pro"   # nhìn cả swatch
MODEL_SINGLE = "black-forest-labs/flux-kontext-pro"         # chỉ ảnh người mẫu

# ====== QUOTA (giới hạn số lần tạo) ======
MAX_GENERATIONS = 50      # tổng số lần tạo tối đa
INITIAL_USED = 16         # số lần đã dùng ban đầu
USAGE_FILE = "usage.json"


def load_used():
    if os.path.exists(USAGE_FILE):
        try:
            with open(USAGE_FILE, "r", encoding="utf-8") as f:
                return int(json.load(f).get("used", INITIAL_USED))
        except Exception:
            return INITIAL_USED
    save_used(INITIAL_USED)
    return INITIAL_USED


def save_used(value):
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump({"used": int(value)}, f)

# ---------- Hàm xử lý ----------
def extract_dominant_color(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((100, 100))
    quantized = img.quantize(colors=5)
    palette = quantized.getpalette()
    idx = max(quantized.getcolors(), key=lambda x: x[0])[1]
    r, g, b = palette[idx * 3: idx * 3 + 3]
    hex_color = f"#{r:02x}{g:02x}{b:02x}"
    brightness = round(0.299 * r + 0.587 * g + 0.114 * b)
    if r - b > 25:
        tone = "warm"
    elif b - r > 10:
        tone = "cool"
    else:
        tone = "neutral"
    if brightness < 60:
        level = "very dark"
    elif brightness < 110:
        level = "dark"
    elif brightness < 160:
        level = "medium"
    else:
        level = "light"
    return hex_color, tone, level


def color_name_from_filename(filename):
    name = filename.rsplit(".", 1)[0]
    name = re.sub(r"^\d+[-_]?", "", name)
    return name.replace("-", " ").replace("_", " ").strip() or "hair"


def label_from_filename(filename):
    return filename.rsplit(".", 1)[0]


def output_to_bytes(output):
    if hasattr(output, "read"):
        return output.read()
    if isinstance(output, (list, tuple)):
        first = output[0]
        if hasattr(first, "read"):
            return first.read()
        import requests
        return requests.get(str(first), timeout=120).content
    import requests
    return requests.get(str(output), timeout=120).content


def build_prompt(color_name, hex_color, tone, level, multi):
    ref = "image 2" if multi else "the target color"
    head = (
        f"Using image 1 as the person and image 2 as the hair color reference: "
        if multi else "")
    return (
        f"{head}"
        f"completely replace the hair color of the woman in image 1 with the "
        f"EXACT color from {ref}. The target color is {color_name}, "
        f"a {level} {tone} tone, exactly matching hex {hex_color}. "
        f"Match the precise lightness and tone exactly: "
        f"do NOT make the hair lighter or brighter than the target, "
        f"do NOT add warm, red, auburn or orange tones unless the target is warm. "
        f"Every single strand must be exactly this shade. "
        f"Do NOT blend with her original hair color; discard it entirely. "
        f"Keep her face, skin tone, facial features, pose, expression "
        f"and background completely unchanged. "
        f"Photorealistic, natural looking hair, high detail. "
        f"CRITICAL COMPOSITION RULES: The output must show EXACTLY ONE single woman, "
        f"the exact same person as in image 1, alone in the frame, "
        f"with the exact same framing, crop and zoom level as image 1. "
        f"There must be only ONE face and ONE person in the entire image. "
        f"Do NOT add, duplicate, clone, mirror or reflect any second person or face. "
        f"Do NOT show two women, twins, or copies of her. "
        f"Do NOT create a side-by-side, split-screen, diptych, collage, grid, "
        f"panel layout, two-person or before/after comparison image. "
        f"Do NOT include the color swatch, reference image, borders or extra panels "
        f"in the output. Just one clean single portrait of one woman."
    )


def run_model(model, model_bytes, swatch_bytes, prompt, multi):
    if multi:
        inp = {
            "prompt": prompt,
            "input_image_1": io.BytesIO(model_bytes),
            "input_image_2": io.BytesIO(swatch_bytes),
            "output_format": "png",
        }
    else:
        inp = {
            "prompt": prompt,
            "input_image": io.BytesIO(model_bytes),
            "output_format": "png",
        }
    return output_to_bytes(replicate.run(model, input=inp))


# ---------- Giao diện ----------
st.set_page_config(page_title="Đổi màu tóc AI", page_icon="💇", layout="wide")
st.title("💇 Đổi màu tóc theo mẫu — FLUX Kontext")

used = load_used()
remaining = max(0, MAX_GENERATIONS - used)

# Thanh quota nổi bật ở đầu trang
q1, q2, q3 = st.columns(3)
q1.metric("Đã dùng", f"{used}/{MAX_GENERATIONS}")
q2.metric("Còn lại", remaining, delta=None,
          delta_color="inverse" if remaining <= 5 else "normal")
q3.metric("Tối đa", MAX_GENERATIONS)
st.progress(used / MAX_GENERATIONS,
            text=f"Đã dùng {used}/{MAX_GENERATIONS} lần • Còn lại {remaining} lần")
if remaining == 0:
    st.error("🚫 Đã hết lượt tạo (50/50). Không thể tạo thêm.")
elif remaining <= 5:
    st.warning(f"⚠️ Sắp hết lượt — chỉ còn {remaining} lần tạo.")

with st.sidebar:
    st.header("⚙️ Cấu hình")
    try:
        default_token = st.secrets.get("REPLICATE_API_TOKEN", "")
    except Exception:
        default_token = ""
    token = st.text_input("Replicate API Token", value=default_token,
                          type="password", help="Lấy tại replicate.com/account/api-tokens")
    use_multi = st.toggle("Dùng multi-image (nhìn ảnh swatch)", value=True,
                          help="Bật: chính xác màu hơn. Tắt: dùng mô tả màu.")
    st.divider()
    st.metric("⚡ Lượt tạo còn lại", f"{remaining}/{MAX_GENERATIONS}")
    st.caption("⚠️ Mỗi lần gọi API (kể cả thử lại) tính là 1 lượt, ~$0.04.")

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

run = st.button("🚀 Bắt đầu tạo ảnh", type="primary",
                use_container_width=True, disabled=(remaining == 0))

if run:
    if not token:
        st.error("Chưa nhập Replicate API Token.")
        st.stop()
    if not model_files or not swatch_files:
        st.error("Cần ít nhất 1 ảnh người mẫu và 1 ảnh mẫu tóc.")
        st.stop()
    if remaining == 0:
        st.error("🚫 Đã hết lượt tạo.")
        st.stop()

    os.environ["REPLICATE_API_TOKEN"] = token
    model = MODEL_MULTI if use_multi else MODEL_SINGLE

    tasks = [(m, s) for m in model_files for s in swatch_files]
    total = len(tasks)

    # Mỗi ảnh gọi API đúng 1 lần = 1 lượt
    if total > remaining:
        st.info(f"ℹ️ Batch cần {total} lượt nhưng chỉ còn {remaining}. "
                f"App sẽ tự dừng khi hết lượt.")

    progress = st.progress(0.0, text=f"0/{total}")
    results = []          # (filename, bytes)
    stopped = False

    for i, (m_file, s_file) in enumerate(tasks, start=1):
        if remaining <= 0:
            stopped = True
            break

        m_bytes = m_file.getvalue()
        s_bytes = s_file.getvalue()
        color_name = color_name_from_filename(s_file.name)
        hex_color, tone, level = extract_dominant_color(s_bytes)
        label = label_from_filename(m_file.name)
        safe_color = color_name.replace(" ", "-")
        out_name = f"{label}_{safe_color}.png"
        prompt = build_prompt(color_name, hex_color, tone, level, use_multi)

        with st.status(f"[{i}/{total}] {label} + {color_name} ({hex_color})",
                       expanded=False) as status:
            try:
                data = run_model(model, m_bytes, s_bytes, prompt, use_multi)
                # Gọi API thành công = 1 lượt
                used += 1
                remaining = MAX_GENERATIONS - used
                save_used(used)
                results.append((out_name, data))
                status.update(label=f"✅ {out_name} (còn {remaining} lượt)",
                              state="complete")
            except Exception as e:
                status.update(label=f"❌ {out_name}: {e}", state="error")

        progress.progress(i / total, text=f"{i}/{total}")

    progress.empty()
    if stopped:
        st.warning(f"⏹️ Dừng vì hết lượt tạo. Đã tạo được {len(results)} ảnh.")
    else:
        st.success(f"Hoàn thành! Tạo được {len(results)} ảnh. Còn {remaining} lượt.")

    # Hiển thị kết quả
    cols = st.columns(3)
    for idx, (name, data) in enumerate(results):
        with cols[idx % 3]:
            st.image(data, caption=name, use_container_width=True)
            st.download_button("⬇️ Tải", data, file_name=name,
                               mime="image/png", key=f"dl_{idx}")

    # Tải tất cả dạng zip
    if results:
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            for name, data in results:
                zf.writestr(name, data)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button("⬇️ Tải tất cả (ZIP)", zip_buf.getvalue(),
                           file_name=f"hair_results_{ts}.zip",
                           mime="application/zip", type="primary")
