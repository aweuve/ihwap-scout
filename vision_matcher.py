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
    Sends image to OpenAI vision model and returns the raw description.
    """
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are Scout, a visual field auditor for IHWAP. Describe any visible home safety or structural issues."},
            {"role": "user", "content": [
                {"type": "text", "text": "Describe this image for an audit report."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]}
        ],
        max_tokens=500
    )
    return response.choices[0].message["content"].lower()

def score_trigger_match(description, trigger_key, logic):
    """
    Scores based on overlap between description and trigger metadata.
    Requires minimum 2 total hits.
    Applies exclusions based on context and sanity checks.
    """
    words = description.split()
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

    # ❌ Sanity check: skip known safe phrases
    if "attic moisture" in trigger_key and "no visible" in description and "water damage" in description:
        return 0
    if "sag" in trigger_key and "no apparent signs of structural damage" in description:
        return 0
    if "vermiculite" in trigger_key and "pink insulation" in description:
        return 0

    # Positive scoring
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

    return score

def get_matching_trigger_from_image(image_bytes, faaie_logic):
    description = get_vision_description(image_bytes)
    matches = []

    for trigger_key, logic in faaie_logic.items():
        score = score_trigger_match(description, trigger_key, logic)
        if score >= 2:
            matches.append((trigger_key, logic, score))

    matches.sort(key=lambda x: x[2], reverse=True)

    result = {
        "description": description,
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
