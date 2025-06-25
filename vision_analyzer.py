import os
import openai
from base64 import b64encode

openai.api_key = os.environ.get("OPENAI_API_KEY")

def get_vision_trigger(image_path):
    # Encode image to base64
    with open(image_path, "rb") as image_file:
        encoded_image = b64encode(image_file.read()).decode("utf-8")

    # Call GPT-4o with vision input
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are an expert home weatherization inspector. Respond with a simple label for the most important issue in the image — like 'vermiculate insulation' or 'water heater corrosion'."
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

    label = response['choices'][0]['message']['content'].strip().lower()
    print("🔍 GPT-4 Vision label:", label)
    return label
