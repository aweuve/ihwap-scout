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
    """
    Sends image to OpenAI vision model and returns structured field-aware analysis with Scout's voice and the Wxbot creed.
    Includes fallback for formatting errors (e.g. Markdown or code blocks).
    """
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

        # 🧼 Clean markdown/codeblock wrappers
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
