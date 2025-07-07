from flask import Flask, render_template, request, send_file, jsonify, session
import os
import openai
import json
import datetime
import io
import base64
from vision_matcher import get_matching_trigger_from_image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ✅ Load FAAIE logic
with open("faaie_logic.json", "r") as f:
    faaie_logic = json.load(f)

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Needed for session handling
openai.api_key = os.getenv("OPENAI_API_KEY")

SYSTEM_PROMPT = (
    "You are Scout — a QCI and compliance assistant trained in the Illinois Home Weatherization Assistance Program (IHWAP), "
    "SWS Field Guide, and DOE WAP protocols.\n\n"
    "Respond in a clear, field-savvy tone with:\n"
    "• Bullet point examples when helpful\n"
    "• Bold policy citations (e.g., **IHWAP 5.4.4**, **SWS 3.1201.2**)\n"
    "• Human fallback flag if unsure\n\n"
    "Always prioritize:\n"
    "1. Health & Safety\n"
    "2. Home Integrity\n"
    "3. Energy Efficiency"
)

scene_categories = {
    "attic": ["attic", "ventilation", "hazardous materials", "structural"],
    "crawlspace": ["crawlspace", "mechanical", "moisture", "structural"],
    "basement": ["mechanical", "structural", "moisture", "electrical"],
    "mechanical room or appliance": ["mechanical", "combustion safety", "electrical"],
    "exterior": ["shell", "ventilation", "hazardous materials"],
    "living space": ["health and safety", "electrical", "shell", "windows"],
    "other": []
}

# ✅ Auto-trigger rules: Scene + Visible Elements combo
trigger_rules = {
    "mechanical room or appliance": [
        {"elements": ["water heater", "rust"], "trigger": "Water Heater Corrosion"},
        {"elements": ["flue pipe"], "trigger": "Flue Pipe Rust or Disconnection"}
    ],
    "attic": [
        {"elements": ["insulation", "rafters"], "trigger": "Uninsulated Attic Hatch Door"},
        {"elements": ["insulation", "vents"], "trigger": "Insulation Blocking Attic Ventilation"},
        {"elements": ["fiberglass insulation", "rafters"], "trigger": "Attic Insulation Review Suggested"}
    ],
    "crawlspace": [
        {"elements": ["vapor barrier", "duct"], "trigger": "Unsealed Vapor Barrier in Crawlspace"},
        {"elements": ["floor joist", "insulation"], "trigger": "Floor Above Crawlspace Uninsulated"}
    ]
}

@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    image_path = None
    chat_response = None
    scene_type = None
    scope_of_work = []

    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        if "clear_chat" in request.form:
            session["chat_history"] = []

        elif "chat_input" in request.form and request.form["chat_input"].strip() != "":
            user_question = request.form["chat_input"]
            session["chat_history"].append({"role": "user", "content": user_question})
            try:
                completion = openai.ChatCompletion.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + session["chat_history"],
                    max_tokens=400
                )
                reply = completion.choices[0].message["content"]
                session["chat_history"].append({"role": "assistant", "content": reply})
            except Exception as e:
                chat_response = f"Error retrieving response: {str(e)}"

        image = request.files.get("image")
        if image:
            upload_dir = os.path.join("static", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            image_path = os.path.join(upload_dir, "upload.jpg")
            image.save(image_path)
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            # Scene classification using OpenAI Vision
            try:
                base64_image = base64.b64encode(image_bytes).decode("utf-8")
                vision_response = openai.ChatCompletion.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a home inspection assistant. Identify the primary location or part of the home shown in this photo.\n"
                                "Choose ONLY from: attic, crawlspace, basement, mechanical room or appliance, exterior, living space, other.\n\n"
                                "Definitions:\n"
                                "- Mechanical room or appliance includes HVAC systems, furnaces, water heaters, boilers, electrical panels, or appliance close-ups.\n\n"
                                "If the image shows a water heater, it falls under mechanical room or appliance.\n\n"
                                "Also, carefully inspect the image for signs of these issues:\n"
                                "- Moisture damage, staining, mold, corrosion, rust, insulation damage, air leakage, duct damage, electrical risks, combustion venting problems, or structural failure.\n\n"
                                "Respond ONLY with the category name."
                            )
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=10
                )
                scene_type = vision_response.choices[0].message["content"].strip().lower()
                if scene_type not in scene_categories:
                    scene_type = "other"
                if "water heater" in vision_response.choices[0].message["content"].lower():
                    scene_type = "mechanical room or appliance"
            except Exception as e:
                scene_type = "other"

            result = get_matching_trigger_from_image(image_bytes, faaie_logic)

            # Fallback scene detection based on visible elements
            visible_elements = result.get("visible_elements", [])
            if scene_type == "other":
                if any(kw in visible_elements for kw in {"rafters", "fiberglass insulation", "attic floor"}):
                    scene_type = "attic"
                elif any(kw in visible_elements for kw in {"vapor barrier", "floor joist", "duct"}):
                    scene_type = "crawlspace"
                elif any(kw in visible_elements for kw in {"water heater", "furnace", "flue pipe", "tank"}):
                    scene_type = "mechanical room or appliance"

            # Filter triggers based on scene
            allowed = scene_categories.get(scene_type, [])
            result["matched_triggers"] = [
                trig for trig in result.get("matched_triggers", [])
                if trig.get("response", {}).get("category") in allowed
            ]

            # Auto-trigger logic based on scene + visible elements
            auto_triggered = []
            for rule in trigger_rules.get(scene_type, []):
                if all(elem in visible_elements for elem in rule["elements"]):
                    auto_triggered.append(rule["trigger"])
            result["auto_triggered"] = auto_triggered
            result["scene_type"] = scene_type

            # Generate IHWAP Scope of Work
            scope_of_work = []
            for idx, trig in enumerate(result.get("matched_triggers", []), 1):
                scope_of_work.append({
                    "number": idx,
                    "work_item": trig.get("trigger"),
                    "fix": trig.get("response", {}).get("recommendation"),
                    "policy": trig.get("response", {}).get("source_policy")
                })

    return render_template("index.html", result=result, image_path=image_path, chat_response=chat_response, chat_history=session.get("chat_history", []), scope_of_work=scope_of_work)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
