import base64
import os
import openai

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def get_vision_trigger(image_path):
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    base64_image = encode_image_to_base64(image_path)

    response = openai.ChatCompletion.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    { "type": "text", "text": (
                        "This image was taken during a home weatherization inspection. "
                        "What specific field condition or hazard does this photo show? "
                        "Respond with a short label like: 'attic moisture', 'mold', 'flue too close to pipe', "
                        "'rim joist unsealed', 'rusted water heater', etc. Return only the condition."
                    ) },
                    { "type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }}
                ]
            }
        ],
        max_tokens=50
    )
    print("🔍 GPT-4 Vision label:", label)
    return label
    
    if "water heater" in label and "rust" in label:
        return "water heater corrosion"
    if "vermiculite" in label:
        return "vermiculite insulation"
    if "rim joist" in label or "box sill" in label:
        return "rim joist unsealed"
    if "pipe" in label and "flue" in label:
        return "pipe insulation near flue"
    if "moisture" in label or "mold" in label:
        return "attic moisture"
    if "open panel" in label or "electrical" in label:
        return "open electrical panel"

    return label
