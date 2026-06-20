import io
import os
import re
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
MODEL_FLUX2          = "black-forest-labs/flux-2-pro"


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


def build_nano_highlight_prompt(color_name, hex_color, density="thin", with_swatch=True):
    if with_swatch:
        color_ref = (f"recolor them so they EXACTLY match the color shown in the second image "
                     f"(the color swatch): {color_name}, hex {hex_color}. ")
        no_collage = (
            "Do NOT include the second image (the color swatch), and do NOT paste, append or show the swatch, "
            "any reference image, borders, or extra panels anywhere in the output. ")
    else:
        color_ref = f"recolor them so they EXACTLY become {color_name}, hex {hex_color}. "
        no_collage = (
            "Do NOT paste, append or show any swatch, reference image, borders, or extra panels anywhere "
            "in the output. ")

    if density == "thin":
        density_rule = (
            f"IMPORTANT — keep the colored highlight VERY THIN and delicate: make the colored area "
            f"NOTICEABLY NARROWER than it currently is — roughly half the width — just a slim ribbon, "
            f"not a wide band. Do NOT widen, thicken, expand, multiply or duplicate the colored strands. "
            f"The vast majority of the hair must stay natural blonde; only a thin sliver shows color. "
            f"The overall amount of colored hair should look light, subtle and delicate, never a thick "
            f"block of color. "
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
        f"Identify the existing colored extension strands and {color_ref}"
        f"STRICT REGION LOCK: recolor ONLY the exact narrow area that is ALREADY colored in the original "
        f"image — keep the colored region the SAME width, SAME length and SAME position as the existing "
        f"strand. Do NOT extend, spread or bleed the color onto any blonde hair that was not already "
        f"colored; the vast majority of the hair must stay natural blonde, with only that one slim existing "
        f"strand changing color. "
        f"CRITICAL: replace the old extension color 100% completely — there must be NO trace, patch, "
        f"streak or pixel of the original color (such as blue) left anywhere in the final image. "
        f"Recolor it the way real HAIR DYE works: KEEP the existing strand's own brightness, shine, "
        f"highlights, shadows, flyaway hairs and individual fiber detail EXACTLY as they are, and ONLY "
        f"shift the HUE to {color_name} (hex {hex_color}). Do NOT flatten it to one uniform tone — "
        f"the strand must keep the same light-and-shadow gradient as the surrounding hair, just in the "
        f"new color (brighter and glossy where light hits, deeper and darker in shadow). "
        f"COLOR MATCH: the colored fibers must match the swatch color {color_name} (hex {hex_color}) "
        f"EXACTLY — same hue, same saturation AND the SAME brightness/lightness as the swatch. Do NOT make "
        f"them darker, deeper or duller than the swatch, and do NOT wash them out pale or pastel either. "
        f"Aim for the exact bright, vivid tone of the swatch — neither darker nor lighter. "
        f"The airy, light look must come ONLY from blonde hairs woven BETWEEN the colored ones, NOT from "
        f"darkening or fading the color. So: vivid swatch-accurate colored strands interlaced with blonde "
        f"strands — the green stays true to the swatch's exact tone, just broken up by blonde threads. "
        f"Keep natural shine and subtle light-and-shadow on the colored fibers, but overall the hue and "
        f"brightness stay matched to the swatch, not darker. "
        f"Where the colored strand meets the natural hair, the edges must FEATHER and interweave softly "
        f"with individual blonde hairs mixing into it — NO hard sharp edge, NO solid stripe, NO clean-cut boundary. "
        f"It must read as real dyed human hair with depth, NOT a flat painted stripe, NOT ink smeared on "
        f"top of the hair, NOT a sticker or a neon graphic overlay. "
        f"LIGHTING CONSISTENCY: the colored strand receives the EXACT same studio lighting as the rest of "
        f"the hair — the bright glossy highlight band and the shadowed darker areas must fall at the SAME "
        f"vertical position and follow the SAME direction as the highlights and shadows on the surrounding "
        f"blonde hair, so the colored strand is lit identically and clearly belongs to the same head of hair. "
        f"PHYSICAL LOGIC of a clip-in extension: each colored strand is ONE continuous piece of hair clipped "
        f"in near the top/upper section and flowing UNBROKEN all the way down to the tips, following the "
        f"natural fall and curve of the hair. Do NOT create a separate floating colored segment that appears "
        f"only in the lower half with nothing connecting it upward — every colored strand must trace back "
        f"continuously to its clip attachment point higher up. Keep the colored strands physically plausible "
        f"and consistent with how a clip-in highlight is really worn. "
        f"PLACEMENT: keep the colored highlight ONLY in the front, face-framing section of hair that falls "
        f"over the shoulder and is fully facing the camera. Remove any colored strands on the back of the "
        f"head or on hair sections turned away/behind — those areas stay fully natural blonde. "
        f"WOVEN 'highlight' STYLE: the colored strand must absolutely NOT be one solid uninterrupted band. "
        f"Heavily INTERLACE it with natural blonde hair — run MANY distinct blonde strands down through the "
        f"middle and across the whole colored section, so it breaks into several thin colored wisps "
        f"separated by plenty of visible blonde hair woven between them. There should be MORE blonde "
        f"threading through than before: blonde and colored fibers alternate constantly along the entire "
        f"length, top to bottom, so you clearly see blonde streaks running inside the colored area, not just "
        f"at the edges. The effect is a finely interlaced balayage-style highlight, airy and broken up, "
        f"NOT a filled block. Keep it interwoven and delicate yet the color still clearly visible. "
        f"{density_rule}"
        f"Keep the person's OWN natural hair color exactly as in the first image (for example keep blonde "
        f"hair blonde, brown hair brown — do NOT darken or change it), and keep the face, skin, facial "
        f"features, expression, pose, framing and background completely unchanged. "
        f"Do NOT recolor the natural hair, only the existing colored extension strands. "
        f"Photorealistic, high detail, natural hair texture throughout. "
        f"CRITICAL COMPOSITION RULES: The output must be ONLY the single edited portrait of this one "
        f"person, with the EXACT same framing, crop and zoom as the first image. "
        f"{no_collage}"
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


def run_flux2(images_bytes, prompt, aspect_ratio="match_input_image"):
    """FLUX 2 Pro: img2img, nhận list ảnh qua input_images (tối đa 8).
    aspect_ratio mặc định bám theo ảnh đầu vào."""
    inp = {
        "prompt": prompt,
        "input_images": [io.BytesIO(b) for b in images_bytes],
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
    }
    return output_to_bytes(replicate.run(MODEL_FLUX2, input=inp))


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
    "gentle":    "a soft, calm and serene expression — relaxed, natural, NOT smiling, lips gently closed",
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
    """Ảnh Before: ảnh 1 = doimat_goc (face source), ảnh 2 = before-template (pose ref).
    Giữ nguyên mặt từ ảnh 1, đổi sang dáng/pose của ảnh 2, xóa lọn màu."""
    if match_identity:
        identity = (
            "The FIRST image is the ONE AND ONLY source of the person: copy her EXACT face, facial features, "
            "identity, skin tone/skin color, natural hair color, hair length, hair texture AND her "
            "clothing/outfit (same garment style, neckline, sleeves, fabric, color) — everything about the "
            "person must come from the first image. "
            "The SECOND image is ONLY a body-pose reference — use it SOLELY to copy the body posture, the "
            "angle the body is turned and the arm position. IGNORE everything else about the second image: "
            "do NOT take its face, do NOT take its skin tone, do NOT take its hair color or hairstyle, do NOT "
            "take its clothing — the second person is NOT the subject, she is only a posing mannequin for the "
            "body angle. "
            "The final person MUST be unmistakably the SAME woman as in the FIRST image (same face, same skin "
            "color, same natural hair color, same outfit), just standing in the body pose of the second image. "
            "Match her SKIN TONE precisely to the first image — same exact skin color and warmth; if she has "
            "tan / medium-brown skin keep it exactly that tan, do NOT lighten or whiten her skin. "
            "If the first image shows tan/medium-dark skin and dark hair, the result MUST also have that same "
            "tan skin and dark hair — never turn her into a different, lighter or blonde person. "
        )
        clothing_override = ""
    else:
        identity = "Keep the person's own face and identity unchanged. "
        clothing_override = _clothing_rule(clothing_en)
    return (
        f"This is the BEFORE photo. {identity}"
        f"CHANGE her expression to: {_EXPR['gentle']} — do NOT keep the smiling or happy expression from the first image, replace it completely with this calm serene look. Her head and face are turned forward, aligned with her body — NOT turned sideways or in profile. "
        f"Her hair must be COMPLETELY ONE SINGLE natural color with ABSOLUTELY NO colored highlight strands "
        f"— remove every single blue/green/pink/colored extension strand 100%, leaving NO trace, streak or "
        f"tint of blue (or any unnatural color) anywhere in the hair. Every strand from roots to tips is the "
        f"ONE uniform natural base color. Keep that natural base color exactly as the first image's natural "
        f"hair (if dark brown/black keep dark brown/black, if blonde keep blonde — match the first image, do "
        f"NOT lighten, darken or change it). The before hair looks like she is NOT wearing any color "
        f"extensions at all — just her plain natural hair. "
        f"{clothing_override}"
        f"Keep the hairstyle, hair length, hair texture from the first image. "
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
        f"Keep her OUTFIT EXACTLY the same as in the first image — copy every detail of the clothing: the "
        f"exact same garment style, color, neckline, sleeves, fabric and cut. Do NOT add, remove, restyle "
        f"or change the clothing into beachwear; she wears the IDENTICAL outfit from the first image. "
        f"Keep the EXACT same thin colored clip-in highlight strands that are already in the first image "
        f"(color {color_name}, hex {hex_color}) — same position, same amount, same subtle thin look. "
        f"Do NOT add more colored strands, do NOT make them thicker, do NOT change the hair. "
        f"Change her POSE and SETTING: place her at a beautiful sunny BEACH, posing naturally and relaxed "
        f"as if on a vacation lifestyle shoot — standing or strolling by the sea, turning slightly, "
        f"with a happy bright confident expression. Natural candid beach posing, not stiff. Keep her hair "
        f"perfectly STRAIGHT and smooth as in the first image (do NOT make it windblown, wavy or messy). "
        f"Soft natural daylight, sandy beach and blue ocean softly blurred in the background. "
        f"Premium editorial lifestyle style inspired by Luxy Hair: clean, bright, high-end and fashionable, "
        f"airy and aspirational. Photorealistic, sharp, realistic. "
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

    return token, use_multi, None
