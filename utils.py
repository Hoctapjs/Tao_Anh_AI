import io
import os
import re
import json
import requests

import replicate
import streamlit as st
from PIL import Image

# ====== CONSTANTS ======
MODEL_MULTI        = "flux-kontext-apps/multi-image-kontext-pro"
MODEL_SINGLE       = "black-forest-labs/flux-kontext-pro"
MODEL_SINGLE_MAX   = "black-forest-labs/flux-kontext-max"
MODEL_NANO         = "google/nano-banana"
MODEL_NANO2        = "google/nano-banana-2"
MODEL_TEXT2IMG       = "black-forest-labs/flux-1.1-pro"
MODEL_TEXT2IMG_ULTRA = "black-forest-labs/flux-1.1-pro-ultra"
MODEL_SIGNBOARD      = "ideogram-ai/ideogram-v3-quality"
MODEL_UPSCALE        = "nightmareai/real-esrgan"

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


def build_nano_prompt(color_name, hex_color):
    return (
        f"Change ONLY the hair color of the person in the first image to exactly match "
        f"the hair color shown in the second image (the color swatch). "
        f"The new hair color is {color_name}, hex {hex_color}. "
        f"Every strand, from the roots at the scalp to the tips, must be this exact uniform color — "
        f"no dark roots, no shadow at the hairline, no ombre or highlights. "
        f"Keep her face, skin, facial features, expression, pose, framing and background "
        f"completely identical to the first image. Do not change anything except the hair color. "
        f"Output a single photorealistic portrait of this one person."
    )


def build_nano_highlight_prompt(color_name, hex_color, density="thin"):
    if density == "thin":
        density_rule = (
            f"IMPORTANT — keep the colored strands MINIMAL and THIN: render them as a few slim, sparse "
            f"accent strands. Do NOT widen, thicken, expand, multiply or duplicate the colored strands, "
            f"and do NOT let the color bleed into the surrounding natural hair. "
            f"Reduce the colored coverage, especially near the crown, the part line and the top of the "
            f"head — most of the hair there must stay its natural color, with only a few thin colored "
            f"strands showing. The overall amount of colored hair should look lighter and more delicate "
            f"than a thick block of color. "
        )
    else:
        density_rule = (
            f"Keep the colored strands roughly the same amount and thickness as the existing colored "
            f"strands in the first image — do NOT widen or expand them, and do NOT let the color bleed "
            f"into the surrounding natural hair. "
        )

    return (
        f"In the first image, the person already has brightly colored clip-in hair extension strands "
        f"(unnatural dyed color, e.g. blue/green/pink) woven into their natural hair. "
        f"Identify the existing colored extension strands and recolor them so they EXACTLY match the "
        f"color shown in the second image (the color swatch): {color_name}, hex {hex_color}. "
        f"CRITICAL: replace the old extension color 100% completely — there must be NO trace, patch, "
        f"streak or pixel of the original color (such as blue) left anywhere in the final image. "
        f"Every part of every remaining colored strand, from where it starts down to the very tip, "
        f"must become the exact uniform color {hex_color}. "
        f"Match the exact hue, saturation and brightness of {hex_color} — do NOT make the strands "
        f"lighter, brighter, more neon or more saturated than the swatch color. "
        f"{density_rule}"
        f"Keep the person's OWN natural hair color exactly as in the first image (for example keep blonde "
        f"hair blonde, brown hair brown — do NOT darken or change it), and keep the face, skin, facial "
        f"features, expression, pose, framing and background completely unchanged. "
        f"Do NOT recolor the natural hair, only the existing colored extension strands. "
        f"Photorealistic, high detail. "
        f"CRITICAL COMPOSITION RULES: The output must be ONLY the single edited portrait of this one "
        f"person, with the EXACT same framing, crop and zoom as the first image. "
        f"Do NOT include the second image (the color swatch), and do NOT paste, append or show the swatch, "
        f"any reference image, borders, or extra panels anywhere in the output. "
        f"Do NOT create a side-by-side, split-screen, diptych, collage, grid or two-panel image. "
        f"There must be exactly ONE person and ONE photo in the result — just the clean edited portrait."
    )


def run_nano_banana(model_bytes, swatch_bytes, prompt, hi_res=False):
    """Nano Banana: nhận list ảnh qua image_input. Ảnh 1 = người mẫu, ảnh 2 = swatch.
    hi_res=True dùng nano-banana-2 và xuất ảnh 4K."""
    inp = {
        "prompt": prompt,
        "image_input": [io.BytesIO(model_bytes), io.BytesIO(swatch_bytes)],
        "output_format": "png",
    }
    if hi_res:
        inp["resolution"] = "4K"
        model = MODEL_NANO2
    else:
        model = MODEL_NANO
    return output_to_bytes(replicate.run(model, input=inp))


def build_nano_text2img_prompt(color_name, hex_color, ethnicity, gender,
                               hair_length, action=""):
    ethnicity_map   = {"Châu Á": "East Asian", "Da trắng": "Caucasian", "Da đen": "Black"}
    gender_map      = {"Nữ": "woman", "Nam": "man"}
    hair_length_map = {"Dài": "long", "Ngắn": "short", "Trung bình": "medium-length"}

    e = ethnicity_map.get(ethnicity, ethnicity)
    g = gender_map.get(gender, gender)
    h = hair_length_map.get(hair_length, hair_length)
    action_part = f" The model is {action.strip()}." if action and action.strip() else ""

    return (
        f"Generate a brand-new photorealistic commercial product portrait of a {g} {e} hair model "
        f"wearing a wig, with {h} hair.{action_part} "
        f"Use the attached image as the EXACT hair color reference — the wig hair color must match "
        f"that color swatch precisely ({color_name}, hex {hex_color}). "
        f"This is a wig advertisement, so hair color accuracy is critical: every strand from the roots "
        f"at the scalp and hairline all the way to the tips must be this exact uniform color. "
        f"No dark roots, no shadow at the hairline, no skin-colored roots, no parting line in a different "
        f"color, no ombre, no gradient, no highlights or lowlights. "
        f"The model's face is a completely new invented person (do NOT copy any face from the reference image; "
        f"it is only a color sample, not a person). "
        f"Professional studio lighting that shows the true hair color, neutral grey background, "
        f"high-end beauty photography, ultra detailed. EXACTLY ONE person in the frame, clean single portrait."
    )


def run_nano_text2img(swatch_bytes, prompt, hi_res=False):
    """Sinh người mẫu mới bằng Nano Banana, dùng swatch làm tham chiếu màu.
    hi_res=True dùng nano-banana-2 và xuất ảnh 4K."""
    inp = {
        "prompt": prompt,
        "image_input": [io.BytesIO(swatch_bytes)],
        "aspect_ratio": "2:3",
        "output_format": "png",
    }
    if hi_res:
        inp["resolution"] = "4K"
        model = MODEL_NANO2
    else:
        model = MODEL_NANO
    return output_to_bytes(replicate.run(model, input=inp))


# ====== BỘ 3 ẢNH HIGHLIGHT CLIP-IN (Before / After / Lifestyle) ======
def run_nano_multi(images_bytes, prompt, aspect_ratio="1:1", hi_res=False):
    """Nano Banana đa năng: nhận list bytes ảnh + aspect_ratio tùy chỉnh.
    images_bytes có thể rỗng (text-to-image) hoặc nhiều ảnh tham chiếu."""
    inp = {
        "prompt": prompt,
        "image_input": [io.BytesIO(b) for b in images_bytes],
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
    }
    if hi_res:
        inp["resolution"] = "4K"
        model = MODEL_NANO2
    else:
        model = MODEL_NANO
    return output_to_bytes(replicate.run(model, input=inp))


_ETH_MAP = {"Châu Á": "East Asian", "Da trắng": "Caucasian", "Da đen": "Black"}
_GEN_MAP = {"Nữ": "woman", "Nam": "man"}

_EXPR = {
    "confident": "a happy, bright, warm and confident smile, a lively and self-assured expression",
    "gentle":    "a soft, gentle, calm and serene expression with a subtle natural smile",
    "neutral":   "a relaxed natural expression",
}

# Màu áo: nhãn tiếng Việt -> mô tả tiếng Anh
CLOTHING_COLORS = {
    "Giữ nguyên":   "",
    "Trắng":        "white",
    "Đen":          "black",
    "Kem / Be":     "beige cream",
    "Xám":          "grey",
    "Xanh navy":    "navy blue",
    "Xanh dương":   "blue",
    "Xanh lá":      "green",
    "Hồng":         "pink",
    "Đỏ":           "red",
    "Vàng":         "yellow",
    "Nâu":          "brown",
    "Tím":          "purple",
}


_ETH_DETAIL = {
    "East Asian": (
        "distinctly East Asian facial features: monolid or double-eyelid almond-shaped eyes, "
        "high cheekbones, soft straight brows, small refined nose, porcelain smooth East Asian skin tone"
    ),
    "Caucasian": (
        "distinctly Caucasian European facial features: defined bone structure, deep-set eyes, "
        "sculpted nose bridge, fair European skin tone — NOT American, NOT generic Western"
    ),
    "Black": (
        "distinctly Black African facial features: full lips, broad nose, rich deep skin tone, "
        "strong cheekbones"
    ),
}


def _clothing_rule(clothing_en):
    if clothing_en:
        return (
            f"Replace her outfit with a LUXURIOUS, high-fashion {clothing_en} garment — "
            f"think premium editorial fashion: elegant drape, fine fabric texture (silk, satin, cashmere, "
            f"or structured tailoring), polished and sophisticated. The garment must be {clothing_en} in color "
            f"and look expensive and on-trend. Do NOT keep the original clothing style if it looks casual. "
        )
    return ""


def build_clipin_faceswap(ethnicity, gender, clothing_en="", expression="confident"):
    """Đổi gương mặt KHÁC HẲN trên template + biểu cảm + màu áo; giữ tóc/lọn/dáng/nền."""
    e = _ETH_MAP.get(ethnicity, "Caucasian")
    g = _GEN_MAP.get(gender, "woman")
    expr = _EXPR.get(expression, _EXPR["neutral"])
    eth_detail = _ETH_DETAIL.get(e, "")
    return (
        f"The image is a TEMPLATE providing only the pose, hair, clothing and background. "
        f"COMPLETELY discard the original face and replace it with a brand-new invented {g} who is "
        f"CLEARLY and UNMISTAKABLY {e}. Treat the template face as irrelevant — invent a fully new person. "
        f"The new face MUST have {eth_detail}. "
        f"Make it IMPOSSIBLE to recognize the original person — every single facial feature must change: "
        f"face shape, forehead, eye shape and spacing, nose bridge and tip, lip shape, jawline, chin, "
        f"cheekbones and brow arch. The result must look like a COMPLETELY DIFFERENT human being. "
        f"Give her {expr}. "
        f"{_clothing_rule(clothing_en)}"
        f"Keep EVERYTHING else identical to the original image: the exact same hairstyle, the SAME natural "
        f"hair color (keep blonde blonde, do NOT darken), hair length, hair texture, the EXACT same colored "
        f"clip-in highlight strands (same color, position, thickness, amount — do NOT change/thicken/move "
        f"any strand), the same pose, the same framing and the same background. "
        f"Photorealistic, natural, sharp. Square 1:1 framing. EXACTLY ONE person, clean single portrait. "
        f"Do NOT add borders, panels or a side-by-side/collage in the output."
    )


def build_clipin_before(clothing_en="", match_identity=True):
    """Ảnh Before từ before-template (tóc tự nhiên). match_identity=True: lấy gương mặt
    từ ảnh thứ 2 (ảnh After) để cùng 1 người; biểu cảm nhẹ nhàng + đổi màu áo."""
    if match_identity:
        identity = (
            "The first image provides the POSE, BODY FRAMING, HAIR and BACKGROUND to use. "
            "The second image is the FACE DONOR — you must COMPLETELY REPLACE the face in the first image "
            "with the face from the second image. Transplant the exact face, facial features, skin tone and "
            "identity from the second image onto the body/pose of the first image. "
            "The result must look unmistakably like the SAME person as in the second image — "
            "do NOT blend or average the two faces, do NOT keep any feature of the first image's face. "
            "The body, hair, pose and background come from image 1; the face comes entirely from image 2. "
        )
    else:
        identity = "Keep the person's own face and identity unchanged. "
    return (
        f"This is the BEFORE photo. {identity}"
        f"Give her {_EXPR['gentle']}. "
        f"Her hair must be completely NATURAL with NO colored highlight strands at all. Keep her OWN natural "
        f"hair color exactly as in the first image (for example keep blonde hair blonde — do NOT darken or "
        f"change the hair color). "
        f"{_clothing_rule(clothing_en)}"
        f"Keep the first image's pose, hairstyle, hair color, hair length, hair texture, framing and "
        f"background. "
        f"Photorealistic, high-end editorial fashion photo, natural, sharp. "
        f"Square 1:1 framing. EXACTLY ONE person, clean single portrait. "
        f"Do NOT add borders, panels or a side-by-side/collage in the output."
    )


def build_clipin_lifestyle_from_after(color_name, hex_color):
    """Ảnh Lifestyle: từ ảnh After -> đổi dáng tạo kiểu, giữ nguyên mặt + lọn màu."""
    return (
        f"A lifestyle fashion photo of the SAME person from the first image, keeping her face, identity, "
        f"skin tone, natural hair color, hair length and the same STRAIGHT smooth hair texture identical "
        f"(do NOT make the hair wavy or curly). "
        f"Keep the EXACT same thin colored clip-in highlight strands that are already in the first image "
        f"(color {color_name}, hex {hex_color}) — same position, same amount, same subtle thin look. "
        f"Do NOT add more colored strands, do NOT make them thicker, do NOT change the hair. "
        f"Change ONLY her pose: she now poses naturally and elegantly, turning slightly, with one hand "
        f"gently holding a section of her hair to show off the colored highlight strands, with a happy "
        f"bright confident expression. "
        f"Premium editorial lifestyle style inspired by Luxy Hair: clean, bright, high-end and fashionable, "
        f"soft natural lighting, simple elegant background. Photorealistic, sharp, realistic. "
        f"Square 1:1 framing. EXACTLY ONE person, the same person as the first image. "
        f"Do NOT include any swatch, borders, panels or a side-by-side/collage in the output."
    )


# ====== BẢNG HIỆU QUẢNG CÁO ======
# Kích thước (cm) phổ biến ở VN -> aspect_ratio gần nhất nano-banana-2 hỗ trợ
SIGNBOARD_SIZES = {
    "80 x 100 cm (dọc 4:5)":       "4:5",
    "100 x 80 cm (ngang 5:4)":     "5:4",
    "80 x 120 cm (dọc 2:3)":       "2:3",
    "60 x 80 cm (dọc 3:4)":        "3:4",
    "Bảng ngang cửa hàng (3:1)":   "3:1",
    "Bảng ngang mặt tiền (2:1)":   "2:1",
    "Bảng ngang tiêu chuẩn (16:9)":"16:9",
    "Bảng vuông (1:1)":            "1:1",
    "Bảng dọc đứng (3:4)":         "3:4",
    "Bảng dọc treo (9:16)":        "9:16",
}

# Phong cách phổ thông cho bảng hiệu cửa hàng VN
SIGNBOARD_STYLES = {
    "Hiện đại tối giản":   "modern minimalist look, clean sans-serif typography, bold solid color background",
    "Truyền thống VN":     "traditional Vietnamese shop sign style, warm red and yellow colors, classic bold typography",
    "Sang trọng cao cấp":  "elegant premium look, gold and dark colors, refined serif typography, luxury feel",
    "Tươi sáng bắt mắt":   "bright eye-catching colors, vibrant and friendly, high contrast, clean",
    "Ẩm thực / quán ăn":   "appetizing food-business style, warm inviting colors, friendly rounded typography",
    "Cà phê / trà sữa":    "trendy cafe and milk-tea style, cozy modern colors, stylish lettering",
}

# Loại hình ảnh nền/họa tiết
SIGNBOARD_LOOKS = {
    "Minh họa (vector)": (
        "flat 2D vector illustration style, hand-drawn cartoon graphic elements, "
        "clean illustrated icons and decorations, like a Canva poster"
    ),
    "Hình ảnh tự nhiên": (
        "realistic photographic background and elements, real product photography, "
        "natural photo-realistic look with real photos of the products/food/drinks, "
        "NOT a cartoon, NOT a flat vector illustration"
    ),
}


def build_signboard_prompt(shop_name, business, contact, slogan,
                           style_label, look_label="Minh họa (vector)", extra=""):
    style = SIGNBOARD_STYLES.get(style_label, style_label)
    look  = SIGNBOARD_LOOKS.get(look_label, look_label)

    lines = [f'  - SHOP NAME (largest, focal point): "{shop_name}"']
    if business:
        lines.append(f'  - business line (smaller): "{business}"')
    if slogan:
        lines.append(f'  - slogan: "{slogan}"')
    if contact:
        lines.append(f'  - contact info (small, at the bottom): "{contact}"')
    text_block = "\n".join(lines)

    extra_part = f" Additional details: {extra.strip()}." if extra and extra.strip() else ""

    return (
        f"An advertising poster / banner design for a Vietnamese shop, print-ready, "
        f"the design fills the entire frame edge to edge. "
        f"Visual look: {look}. "
        f"Color & mood style: {style}. "
        f"The poster must display EXACTLY the following Vietnamese text, each on its own line:\n"
        f"{text_block}\n"
        f"VIETNAMESE TEXT RULES (very important): The text is in the Vietnamese language and uses "
        f"Latin letters with diacritics. Reproduce every word LETTER-FOR-LETTER exactly as given above, "
        f"including all Vietnamese special characters such as ă â đ ê ô ơ ư and the tone marks "
        f"(à á ả ã ạ, è é ẻ ẽ ẹ, etc.). "
        f"Do NOT drop, add, swap or change any accent or tone mark. Do NOT replace Vietnamese letters "
        f"with plain English letters (e.g. keep 'ơ' not 'o', keep 'đ' not 'd'). "
        f"Do NOT translate, do NOT invent extra words, and do NOT add any text that is not listed above. "
        f"Spell-check the result so every Vietnamese word matches the given text perfectly. "
        f"Use a clean, well-known font that fully supports Vietnamese diacritics. "
        f"DESIGN PRINCIPLES: strong clear visual hierarchy with the shop name most prominent and easy "
        f"to read from far away; high contrast between text and background; limited harmonious color "
        f"palette (2-3 main colors); generous margins and balanced spacing; legible typography; "
        f"a small simple icon or logo mark relevant to the business if suitable.{extra_part} "
        f"The text must be sharp, perfectly legible and correctly spelled with all Vietnamese accents. "
        f"IMPORTANT: Output ONLY the poster design itself, filling the entire frame edge to edge, "
        f"as a clean exported design file. Do NOT show the poster hanging on a wall, on a building, on a "
        f"storefront, on a stand, on a mockup, or held by a person. Do NOT add an outer border, frame, "
        f"margin or background around the poster. No surrounding environment, no street scene, "
        f"no perspective tilt — just the flat front-facing poster filling the whole image. "
        f"High resolution, professional design, commercial quality."
    )


def run_signboard_model(prompt, aspect_ratio="4:5"):
    inp = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": "2K",
        "output_format": "png",
    }
    return output_to_bytes(replicate.run(MODEL_NANO2, input=inp))


def run_upscale_model(image_bytes, scale=4, face_enhance=False):
    """Upscale ảnh bằng Real-ESRGAN. scale: 1-10 (default 4x). face_enhance: GFPGAN."""
    inp = {
        "image": io.BytesIO(image_bytes),
        "scale": scale,
        "face_enhance": face_enhance,
    }
    result = replicate.run(MODEL_UPSCALE, input=inp)
    if hasattr(result, "read"):
        return result.read()
    if isinstance(result, str):
        return requests.get(result, timeout=60).content
    return result


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
