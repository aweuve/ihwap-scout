import os
import openai
import json
import base64

openai.api_key = os.getenv("OPENAI_API_KEY")

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

    # Simple logic for reducing false positives based on condition/context
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
        logic.get("policy_text", ""),
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

def get_matching_trigger_from_image(image_bytes, logic_list):
    parsed = get_vision_analysis(image_bytes)
    best_match = None
    best_score = 0

    for logic in logic_list:
        trigger_key = logic.get("trigger", "")
        score = score_trigger_match(parsed, trigger_key, logic)
        if score > best_score:
            best_score = score
            best_match = logic

    if not best_match or best_score == 0:
        best_match = {
            "trigger": "Unlisted or ambiguous condition",
            "action_item": "⚠️🛑 Action Item",
            "policy_text": "Unknown trigger or unlisted condition. Please review photo manually.",
            "reference_policy": "N/A",
            "documentation": "",
            "tags": ["unsorted"]
        }

    result = {
        "trigger": best_match.get("trigger", "Unknown trigger"),
        "action_item": best_match.get("action_item", ""),
        "policy_text": best_match.get("policy_text", ""),
        "reference_policy": best_match.get("reference_policy", ""),
        "documentation": best_match.get("documentation", ""),
        "tags": best_match.get("tags", []),
        "scout_thought": parsed.get("scout_thought", ""),
        "visible_elements": parsed.get("visible_elements", []),
        "hazards": parsed.get("hazards", []),
        "description": parsed.get("description", "")
    }

    return result

