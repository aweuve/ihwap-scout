from flask import Flask, render_template, request, jsonify, session
import os
import openai
import json
import base64
from vision_matcher import get_matching_trigger_from_image

# Load FAAIE logic
with open("faaie_logic.json", "r") as f:
    faaie_logic = json.load(f)

app = Flask(__name__)
app.secret_key = "super_secret_key"
openai.api_key = os.getenv("OPENAI_API_KEY")

scene_categories = {
    "attic": ["attic", "ventilation", "hazardous materials", "structural"],
    "crawlspace": ["crawlspace", "mechanical", "moisture", "structural"],
    "basement": ["mechanical", "structural", "moisture", "electrical"],
    "mechanical room or appliance": ["mechanical", "combustion safety", "electrical"],
    "exterior": ["shell", "ventilation", "hazardous materials"],
    "living space": ["health and safety", "electrical", "shell", "windows"],
    "other": []
}

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

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        question = request.form.get("chat_input")
        if question:
            session["chat_history"].append({"role": "user", "content": question})
            try:
                completion = openai.ChatCompletion.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are Scout, an assistant trained in Illinois Home Weatherization Assistance Program (IHWAP) 2026 standards and weatherization field work.\n\n"
                                "✅ Always follow the Weatherization Creed:\n"
                                "1. Health & Safety\n2. Home Integrity\n3. Energy Efficiency\n\n"
                                "Acceptable questions include:\n"
                                "- IHWAP 2026 policies and field measures\n"
                                "- DOE WAP rules\n"
                                "- Inspection or scope guidance\n"
                                "- General weatherization strategies and troubleshooting\n"
                                "- Rubber-ducking field problems or asking for manual lookups\n\n"
                                "Answer Style:\n"
                                "- Health & Safety first.\n"
                                "- Deferral risks second.\n"
                                "- Technical details last.\n"
                                "- Include IHWAP 2026 citations where relevant.\n"
                                "- Be friendly, clear, and concise for field use.\n\n"
                                "If the question is unrelated to weatherization or energy programs, reply:\n"
                                '\"I can assist with Weatherization, IHWAP 2026, DOE WAP, inspections, and field questions. Please ask about those topics.\"'
                            )
                        }
                    ] + session["chat_history"],
                    max_tokens=500
                )
                reply = completion.choices[0].message["content"]
                session["chat_history"].append({"role": "assistant", "content": reply})
            except Exception as e:
                session["chat_history"].append({"role": "assistant", "content": f"Error: {e}"})

    return render_template("chat.html", chat_history=session.get("chat_history", []))

@app.route("/qci", methods=["GET", "POST"])
def qci():
    result = None
    image_path = None
    scene_type = None

    if request.method == "POST":
        image = request.files.get("image")
        if image:
            upload_dir = os.path.join("static", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            image_path = os.path.join(upload_dir, "upload.jpg")
            image.save(image_path)
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            try:
                base64_image = base64.b64encode(image_bytes).decode("utf-8")
                vision_response = openai.ChatCompletion.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {"role": "system", "content": (
                            "You are a home inspection assistant. Identify the primary location or part of the home shown in this photo. "
                            "Choose ONLY from: attic, crawlspace, basement, mechanical room or appliance, exterior, living space, other."
                        )},
                        {"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]}
                    ],
                    max_tokens=10
                )
                scene_type = vision_response.choices[0].message["content"].strip().lower()
                if scene_type not in scene_categories:
                    scene_type = "other"
            except Exception:
                scene_type = "other"

            result = get_matching_trigger_from_image(image_bytes, faaie_logic)

            visible_elements = result.get("visible_elements", [])
            if scene_type == "other":
                if any(kw in visible_elements for kw in {"rafters", "fiberglass insulation", "attic floor"}):
                    scene_type = "attic"
                elif any(kw in visible_elements for kw in {"vapor barrier", "floor joist", "duct"}):
                    scene_type = "crawlspace"
                elif any(kw in visible_elements for kw in {"water heater", "furnace", "flue pipe"}):
                    scene_type = "mechanical room or appliance"

            allowed = scene_categories.get(scene_type, [])
            result["matched_triggers"] = [
                trig for trig in result.get("matched_triggers", [])
                if trig.get("response", {}).get("category") in allowed
            ]

            auto_triggered = []
            for rule in trigger_rules.get(scene_type, []):
                if all(elem in visible_elements for elem in rule["elements"]):
                    auto_triggered.append(rule["trigger"])
            result["auto_triggered"] = auto_triggered
            result["scene_type"] = scene_type

            session["last_result"] = result
            session["last_scene"] = scene_type

    return render_template("qci.html")

@app.route("/scope")
def scope():
    result = session.get("last_result")
    return render_template("scope.html", result=result)

@app.route("/prevent")
def prevent():
    return render_template("prevent.html")

@app.route("/age")
def age():
    return render_template("age.html")

@app.route("/qci_review", methods=["POST"])
def qci_review():
    data = request.json
    scene_type = data.get("scene_type", "unknown")
    matched_triggers = data.get("matched_triggers", [])
    auto_triggers = data.get("auto_triggered", [])

    qci_prompt = (
        f"You are acting as a certified IHWAP Quality Control Inspector (QCI). Review this photo based on its scene type: {scene_type}.\n"
        f"The detected issues are: {', '.join([t['trigger'] for t in matched_triggers] + auto_triggers)}.\n\n"
        "Provide a professional field-style inspection note listing specific corrections, documentation needs, or verification steps required before approval.\n"
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": qci_prompt}],
            max_tokens=300
        )
        review = response.choices[0].message["content"]
    except Exception as e:
        review = f"Error generating QCI review: {str(e)}"

    session.setdefault("chat_history", []).append({"role": "assistant", "content": review})
    return jsonify({"qci_review": review})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


