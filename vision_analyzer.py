import os
import openai
from base64 import b64encode

# Load OpenAI key from environment
openai.api_key = os.environ.get("OPENAI_API_KEY")

def get_vision_trigger(image_path):
    # Encode image for base64 upload
    with open(image_path, "rb") as image_file:
        encoded_image = b64encode(image_file.read()).decode("utf-8")

    # Ask GPT-4o to describe the issue
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are an expert in home weatherization field inspections. When given an image, return a simple label describing the most important issue present — like 'water heater corrosion' or 'vermiculite insulation'."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_image}"
                        }
                    }
                ]
            }
        ],
        max_tokens=50
    )

    label = response.choices[0].message.content.strip().lower()
    print("🔍 GPT-4 Vision label:", label)
    return label

