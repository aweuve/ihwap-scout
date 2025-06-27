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

def get_vision_analysis(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Scout — a visual field auditor working under the Illinois Home Weatherization Assistance Program (IHWAP), "
                    "trained in the Wxbot Code of Operations. You always remember: ‘The house is a system.’\n\n"
                    "When analyzing the image, consider safety first, then home integrity, then energy. Speak plainly, like you're talking to a crew lead or QCI. "
                    "Use field wisdom. Be specific. Be calm.\n\n"
                    "Return a JSON object like this:\n"
                    "{\n"
                    "  \"description\": \"Human-style plain language summary of the image\",\n"
                    "  \"visible_elements\": [\"attic trusses\", \"pink fiberglass insulation\", \"vent pipe\"],\n"
                    "  \"hazards\": [\"corroded flue collar\", \"missing vent termination\"],\n"
                    "  \"scout_thought\": \"Reflective insight from Scout about safety, sequence, or overlooked risks.\"\n"
                    "}"
                )
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this image for IHWAP field conditions."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        max_tokens=750
    )

    try:
        raw = response.choices[0].message["content"].strip()

        if "```json" in raw:
            raw = raw.split("```json")[-1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[-1].split("```")[-1].strip()

        if not raw.startswith("{"):
            raise ValueError("Scout returned non-JSON content.")

        parsed = json.loads(raw)
        return {
            "description": parsed.get("description", "").lower(),
            "visible_elements": parsed.get("visible_elements", []),
            "hazards": parsed.get("hazards", []),
            "scout_thought": parsed.get("scout_thought", "")
        }

    except Exception as e:
        return {
            "description": "image analysis failed",
            "visible_elements": [],
            "hazards": [],
            "scout_thought": f"Error during analysis: {str(e)}"
        }

def score_trigger_match(parsed, trigger_key, logic):
    description = parsed["description"]
    words = description.split()
    tags = parsed["visible_elements"] + parsed["hazards"]
    score = 0

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

    for tag in tags:
        clean_tag = tag.lower().strip()
        if clean_tag in trigger_key.lower():
            score += 2
        if any(clean_tag in part.lower() for part in parts):
            score += 1

    return score

def get_matching_trigger_from_image(image_bytes, faaie_logic):
    parsed = get_vision_analysis(image_bytes)
    matches = []

    for trigger_key, logic in faaie_logic.items():
        score = score_trigger_match(parsed, trigger_key, logic)
        if score >= 2 or any(h in trigger_key.lower() for h in [t.lower() for t in parsed["hazards"]]):
            matches.append((trigger_key, logic, score))

    matches.sort(key=lambda x: x[2], reverse=True)

    result = {
        "description": parsed["description"],
        "visible_elements": parsed["visible_elements"],
        "hazards": parsed["hazards"],
        "scout_thought": parsed["scout_thought"],
        "matched_triggers": []
    }

    for trigger_key, logic, score in matches[:1]:
        result["matched_triggers"].append({
            "trigger": trigger_key,
            "response": logic
        })

    if not result["matched_triggers"] and matches:
        best_match = matches[0]
        result["matched_triggers"].append({
            "trigger": best_match[0],
            "response": best_match[1]
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
                "visual_cue": ""
            }
        })

    return result
