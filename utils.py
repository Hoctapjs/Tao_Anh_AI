import io
import os
import re
import json
import requests

import replicate
import streamlit as st
from PIL import Image

# ====== CONSTANTS ======
MODEL_MULTI    = "flux-kontext-apps/multi-image-kontext-pro"
MODEL_SINGLE   = "black-forest-labs/flux-kontext-pro"
MODEL_TEXT2IMG       = "black-forest-labs/flux-1.1-pro"
MODEL_TEXT2IMG_ULTRA = "black-forest-labs/flux-1.1-pro-ultra"

MAX_GENERATIONS = 50
INITIAL_USED    = 16
USAGE_FILE      = "usage.json"


# ====== QUOTA ======
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


# ====== IMAGE UTILS ======
def extract_dominant_color(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((100, 100))
    quantized = img.quantize(colors=5)
    palette = quantized.getpalette()
    idx = max(quantized.getcolors(), key=lambda x: x[0])[1]
    r, g, b = palette[idx * 3: idx * 3 + 3]
    hex_color  = f"#{r:02x}{g:02x}{b:02x}"
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
        return requests.get(str(first), timeout=120).content
    return requests.get(str(output), timeout=120).content


# ====== PROMPTS ======
def build_prompt(color_name, hex_color, tone, level, multi):
    ref  = "image 2" if multi else "the target color"
    head = ("Using image 1 as the person and image 2 as the hair color reference: "
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


def build_text2img_prompt(color_name, hex_color, tone, level,
                          ethnicity, gender, hair_length, action=""):
    ethnicity_map   = {"Châu Á": "East Asian", "Da trắng": "Caucasian", "Da đen": "Black"}
    gender_map      = {"Nữ": "woman", "Nam": "man"}
    hair_length_map = {"Dài": "long", "Ngắn": "short", "Trung bình": "medium-length"}

    e = ethnicity_map.get(ethnicity, ethnicity)
    g = gender_map.get(gender, gender)
    h = hair_length_map.get(hair_length, hair_length)
    action_part = f" The model is {action.strip()}." if action and action.strip() else ""

    return (
        f"A photorealistic commercial product portrait of a {g} {e} hair model "
        f"wearing a wig, with {h} hair.{action_part} "
        f"HAIR COLOR RULES — this is a wig product advertisement, hair color accuracy is critical: "
        f"The entire hair — from roots to tips, every single strand — must be EXACTLY {color_name}, "
        f"hex {hex_color}, a {level} {tone} tone. "
        f"The hairline where the wig meets the scalp must also be EXACTLY the same color {hex_color} — "
        f"no dark shadow at the hairline, no skin-colored roots, no parting line showing a different color. "
        f"The roots at the scalp line must be identical in color to the mid-lengths and ends. "
        f"No darker roots, no natural root shadow, no ombre, no gradient, no highlights, no lowlights. "
        f"100% uniform color from the scalp hairline all the way to the ends of every strand. "
        f"Do NOT add any warm, red, auburn or cool tones unless they exist in the target color. "
        f"Do NOT make the hair lighter or darker than hex {hex_color}. "
        f"Hair texture: smooth, shiny, well-styled, realistic wig appearance. "
        f"Professional commercial studio lighting that shows the true hair color accurately. "
        f"Sharp focus on hair, neutral grey background, "
        f"high-end fashion and beauty photography style, 8k, ultra detailed. "
        f"EXACTLY ONE person in the frame, clean single portrait."
    )


# ====== API CALLS ======
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


def run_with_retry(fn, max_retries=3, wait_seconds=12):
    """Tự retry khi bị lỗi 429 rate limit, tối đa max_retries lần."""
    import time
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if "429" in str(e) or "throttled" in str(e).lower():
                if attempt < max_retries:
                    time.sleep(wait_seconds)
                    continue
            raise  # lỗi khác thì raise ngay
    raise last_err


def run_text2img_model(prompt, model=None):
    if model is None:
        model = MODEL_TEXT2IMG
    negative_prompt = (
        "dark roots, darker roots, shadow at roots, root shadow, visible roots, "
        "two-tone hair, ombre hair, ombre roots, natural roots, regrowth, "
        "root regrowth, darker hairline, shadowed hairline, black roots, "
        "brown roots, uneven hair color, hair color gradient, balayage, "
        "highlights, lowlights, streaks, uncolored roots, grow-out roots"
    )
    inp = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "aspect_ratio": "2:3",
        "output_format": "png",
    }
    return output_to_bytes(replicate.run(model, input=inp))


# ====== SHARED UI COMPONENTS ======
def render_quota_bar():
    used      = load_used()
    remaining = max(0, MAX_GENERATIONS - used)

    q1, q2, q3 = st.columns(3)
    q1.metric("Đã dùng", f"{used}/{MAX_GENERATIONS}")
    q2.metric("Còn lại", remaining)
    q3.metric("Tối đa", MAX_GENERATIONS)
    st.progress(used / MAX_GENERATIONS,
                text=f"Đã dùng {used}/{MAX_GENERATIONS} lần • Còn lại {remaining} lần")
    if remaining == 0:
        st.error("🚫 Đã hết lượt tạo (50/50). Không thể tạo thêm.")
    elif remaining <= 5:
        st.warning(f"⚠️ Sắp hết lượt — chỉ còn {remaining} lần tạo.")

    return used, remaining


def render_sidebar():
    with st.sidebar:
        st.header("⚙️ Cấu hình")

        # Token persist giữa các page qua session_state
        try:
            secret_token = st.secrets.get("REPLICATE_API_TOKEN", "")
        except Exception:
            secret_token = ""
        default_token = st.session_state.get("token", secret_token)
        token = st.text_input("Replicate API Token", value=default_token,
                              type="password",
                              help="Lấy tại replicate.com/account/api-tokens")
        st.session_state["token"] = token

        use_multi = st.toggle(
            "Dùng multi-image (nhìn ảnh swatch)", value=True,
            help="Bật: chính xác màu hơn. Tắt: dùng mô tả màu.",
            key="use_multi_toggle",
        )

        st.divider()
        used      = load_used()
        remaining = max(0, MAX_GENERATIONS - used)
        st.metric("⚡ Lượt tạo còn lại", f"{remaining}/{MAX_GENERATIONS}")
        st.caption("Mỗi lần gọi API tính là 1 lượt.")

    return token, use_multi, remaining
