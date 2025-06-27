import os
import openai
import json
import base64
from io import BytesIO
from PIL import Image

openai.api_key = os.getenv("OPENAI_API_KEY")

# Load logic from faaie_logic.json
with open("faaie_logic.json", "r") as f:
    faaie_logic = json.load(f)

def get_vision_description(image_bytes):
    """
    Sends image to OpenAI vision model and returns structured audit analysis.
    """
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are Scout, an IHWAP visual field auditor. Return JSON like this:\n\n{\n  \"description\": \"plain-language summary\",\n  \"visible_elements\": [\"attic insulation\", \"vent pipe\"],\n  \"hazards\": [\"rust\", \"missing vent cap\"]\n}"},
            {"role": "user", "content": [
                {"type": "text", "text": "Analyze this image for IHWAP field audit."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]}
        ],
        max_tokens=700
    )

    try:
        parsed = json.loads(response.choices[0].message["content"])
        return {
            "description": parsed.get("description", "").lower(),
            "visible_elements": parsed.get("visible_elements", []),
            "hazards": parsed.get("hazards", [])
        }
    except Exception:
        return {
            "description": "image analysis failed",
            "visible_elements": [],
            "hazards": []
        }

def score_trigger_match(parsed, trigger_key, logic):
    """
    Scores based on matches with description, visible elements, and hazards.
    Excludes mismatches using context rules.
    """
    description = parsed["description"]
    words = description.split()
    tags = parsed["visible_elements"] + parsed["hazards"]
    score = 0

    # Exclusion logic
    if "attic" in description:
        if "water heater" in trigger_key or "confined closet" in trigger_key:
            return 0
    if "exposed fiberglass" in trigger_key:
        if not any(kw in description for kw in ["living space", "occupied", "room", "habitable"]):
            return 0
    if "knob and tube" in trigger_key:
        if not any(kw in description for kw in ["knob", "tube", "cloth-wrapped", "old wiring"]):
            return 0
    if "moisture" in trigger_key or "sag" in trigger_key:
        if not any(kw in description for kw in ["stain", "stains", "drooping", "wet", "mold", "sag"]):
            return 0
    if "fan duct" in trigger_key or "bathroom fan" in trigger_key or "vent fan" in trigger_key:
        if not any(kw in description for kw in ["fan", "duct", "vent pipe", "exhaust"]):
            return 0
    if "vermiculite" in trigger_key:
        if not any(kw in description for kw in ["granular", "gray", "gold", "pebble", "cat litter", "vermiculite"]):
            return 0

    # Positive scoring from description + logic
    parts = [
        trigger_key,
        logic.get("reason", ""),
        logic.get("visual_cue", ""),
        " ".join(logic.get("tags", []))
    ]
    for part in parts:
        for word in part.lower().split():
            if word in words:
                score += 1

    # Bonus points for visible/hazard tag match
    for tag in tags:
        tag_words = tag.lower().split()
        for tw in tag_words:
            if any(tw in part.lower() for part in parts):
                score += 1

    return score

def get_matching_trigger_from_image(image_bytes, faaie_logic):
    parsed = get_vision_description(image_bytes)
    matches = []

    for trigger_key, logic in faaie_logic.items():
        score = score_trigger_match(parsed, trigger_key, logic)
        if score >= 2:
            matches.append((trigger_key, logic, score))

    matches.sort(key=lambda x: x[2], reverse=True)

    result = {
        "description": parsed["description"],
        "visible_elements": parsed["visible_elements"],
        "hazards": parsed["hazards"],
        "matched_triggers": []
    }

    for trigger_key, logic, score in matches[:3]:
        result["matched_triggers"].append({
            "trigger": trigger_key,
            "response": logic
        })

    if not result["matched_triggers"]:
        result["matched_triggers"].append({
            "trigger": "unlisted condition",
            "response": {
                "action": "⚠️🛑 Action Item",
                "reason": "Unknown trigger or unlisted condition.",
                "recommendation": "No direct match found. Review photo manually.",
                "source_policy": "N/A",
                "category": "unsorted",
                "visual_cue": "",
                "tags": []
            }
        })

    return result

