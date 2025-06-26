# vision_matcher.py
import openai
import base64

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_matching_trigger_from_image(image_bytes, faaie_logic):
    # Step 1: Encode image for GPT-4o Vision
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    # Step 2: Ask GPT to describe the image
    vision_response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a weatherization field inspector trained in IHWAP standards. Describe what this photo shows in detail."},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                    {"type": "text", "text": "What are the visible housing conditions or issues?"}
                ]
            }
        ],
        temperature=0.2,
        max_tokens=300
    )

    # Step 3: Get GPT’s response
    description = vision_response.choices[0].message['content'].lower()

    # Step 4: Fuzzy match FAAIE logic
    best_match = None
    highest_score = 0

    for trigger, entry in faaie_logic.items():
        for tag in entry.get("tags", []):
            if tag.lower() in description:
                match_score = description.count(tag.lower())
                if match_score > highest_score:
                    best_match = trigger
                    highest_score = match_score

    if best_match:
        return {
            "matched_trigger": best_match,
            "response": faaie_logic[best_match],
            "description": description
        }
    else:
        return {
            "matched_trigger": None,
            "response": None,
            "description": description
        }
