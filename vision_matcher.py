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
                    "You are Scout — a field-trained visual assistant for the Illinois Home Weatherization Assistance Program (IHWAP), "
                    "operating under the Wxbot Code of Operations. Your job is to visually assess photos from the field for health, safety, and code concerns.\n\n"
                    "Prioritize in this order:\n"
                    "1. Health & Safety\n"
                    "2. Structural Integrity\n"
                    "3. Energy Efficiency\n\n"
                    "Return your results in **JSON only**. Use this format:\n"
                    "{\n"
                    "  \"description\": \"Brief, plain-language summary of the image\",\n"
                    "  \"visible_elements\": [\"furnace\", \"flex duct\", \"floor joist\", \"flue collar\"],\n"
                    "  \"hazards\": [\"corroded flue\", \"missing discharge pipe\"],\n"
                    "  \"scout_thought\": \"QCI-style insight about what the crew or auditor should do next.\"\n"
                    "}\n\n"
                    "Tips:\n"
                    "- Do not include markdown, headers, or explanations. Return only JSON.\n"
                    "- Use clear terms from field inspections: 'fiberglass insulation', 'unsealed duct', 'foundation wall', etc.\n"
                    "- If hazard is visible (e.g. water, rot, flame risk), name it. If unsure, say nothing.\n"
                    "- The 'scout_thought' should be a calm, actionable comment — like from a seasoned auditor.\n"
                    "- Never hallucinate tools or measurements — only describe what you **can see**.\n"
                    "- Do not invent codes. Your job is visual flagging, not quoting standards.\n\n"
                    "You are helping a real weatherization team. Accuracy matters. Keep it tight. JSON only."
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
            raw = raw.split("```")[-1].strip()

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
        if not any(kw in description for kw in ["stain", "drooping", "wet", "mold", "sag"]):
            return 0
    if "fan duct" in trigger_key or "bathroom fan" in trigger_key:
        if not any(kw in description for kw in ["fan", "duct", "vent", "exhaust"]):
            return 0
    if "vermiculite" in trigger_key:
        if not any(kw in description for kw in ["granular", "gray", "gold", "pebble", "vermiculite"]):
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

    if matches:
        for trigger_key, logic, score in matches[:3]:  # Return top 3 matches
            result["matched_triggers"].append({
                "trigger": trigger_key,
                "score": score,
                "response": {
                    "action": logic.get("action", "⚠️🛑 Action Item"),
                    "reason": logic.get("reason", ""),
                    "recommendation": logic.get("recommendation", ""),
                    "source_policy": logic.get("source_policy", ""),
                    "category": logic.get("category", ""),
                    "visual_cue": logic.get("visual_cue", "")
                }
            })
    else:
        result["matched_triggers"].append({
            "trigger": "unlisted condition",
            "score": 0,
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
