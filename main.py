# IHWAP Scout – Flask back‑end (syntax‑safe patch)
# ---------------------------------------------------------------------
#  • Fixes unterminated string literal in the system prompt block (line 93)
#  • No other logic changed – retains user‑supplied working code + patches
# ---------------------------------------------------------------------

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import openai
import json
import base64
from vision_matcher import get_matching_trigger_from_image
from decoders import decode_serial

# ---------------------------------------------------------------------
# Load FAAIE logic
# ---------------------------------------------------------------------
with open("faaie_logic.json", "r") as f:
    faaie_logic = json.load(f)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "super_secret_key")
openai.api_key = os.getenv("OPENAI_API_KEY")

# ---------------------------------------------------------------------
# Scene categories & hard‑coded trigger rules
# ---------------------------------------------------------------------
scene_categories = {
    "attic": ["attic", "ventilation", "hazardous materials", "structural"],
    "crawlspace": ["crawlspace", "mechanical", "moisture", "structural"],
    "basement": ["mechanical", "structural", "moisture", "electrical"],
    "mechanical room or appliance": ["mechanical", "combustion safety", "electrical"],
    "exterior": ["shell", "ventilation", "hazardous materials"],
    "living space": ["health and safety", "electrical", "shell", "windows"],
    "other": [],
}

trigger_rules = {
    "mechanical room or appliance": [
        {"elements": ["water heater", "rust"], "trigger": "Water Heater Corrosion"},
        {"elements": ["flue pipe"], "trigger": "Flue Pipe Rust or Disconnection"},
    ],
    "attic": [
        {"elements": ["insulation", "rafters"], "trigger": "Uninsulated Attic Hatch Door"},
        {"elements": ["insulation", "vents"], "trigger": "Insulation Blocking Attic Ventilation"},
        {"elements": ["fiberglass insulation", "rafters"], "trigger": "Attic Insulation Review Suggested"},
    ],
    "crawlspace": [
        {"elements": ["vapor barrier", "duct"], "trigger": "Unsealed Vapor Barrier in Crawlspace"},
        {"elements": ["floor joist", "insulation"], "trigger": "Floor Above Crawlspace Uninsulated"},
    ],
}

# ---------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------
@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/chat", methods=["GET", "POST"])
def chat():
    """Threaded chat route – supports:
    • Standard form POST with field name either 'chat_input' **or** 'prompt'.
    • JS fetch() JSON POST  → {"prompt": "..."}
    Returns JSON if the client asks for it (Accept header or X‑Requested‑With),
    otherwise redirects back to the chat page to avoid resubmit‑on‑refresh.
    """

    session.setdefault("chat_history", [])

    # ------ POST handler ------
    if request.method == "POST":
        user_msg = (
            request.form.get("chat_input")
            or request.form.get("prompt")
            or (request.json.get("prompt") if request.is_json else None)
        )

        if user_msg:
            session["chat_history"].append({"role": "user", "content": user_msg})
            try:
                completion = openai.ChatCompletion.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                """You are Scout, an IHWAP 2026 assistant for Weatherization staff.

✅ Follow the Weatherization Creed:
1. Health & Safety
2. Home Integrity
3. Energy Efficiency

Acceptable topics:
- IHWAP 2026 policies & measures
- DOE WAP rules
- Field inspections, scopes, and troubleshooting
- Rubber-ducking field issues or manual lookups

Answer structure:
- Health & Safety concerns first
- Deferral risks second
- Compliance or tech details last
- Include IHWAP 2026 citations if applicable
- Be friendly, clear, and concise for field use

If unrelated, say:
"I can assist with IHWAP 2026, Weatherization, and inspection topics only."""  # noqa: E501
                            ),
                        }
                    ]
                    + session["chat_history"],
                    max_tokens=500,
                )
                assistant_reply = completion.choices[0].message["content"]
            except Exception as e:
                assistant_reply = f"Error: {e}"

            session["chat_history"].append({"role": "assistant", "content": assistant_reply})

            wants_json = (
                request.is_json
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or request.headers.get("Accept", "").startswith("application/json")
            )
            if wants_json:
                return jsonify({"reply": assistant_reply})
            return redirect(url_for("chat"))

    # ------ GET handler ------
    return render_template("chat.html", chat_history=session.get("chat_history", []))


# ---------- QCI UPLOAD / ANALYSIS ----------
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
                vision_resp = openai.ChatCompletion.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a home inspection assistant. Identify the primary location or part of the home shown in this photo. "
                                "Choose ONLY from: attic, crawlspace, basement, mechanical room or appliance, exterior, living space, other."
                            ),
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                                }
                            ],
                        },
                    ],
                    max_tokens=10,
                )
                scene_type = vision_resp.choices[0].message["content"].strip().lower()
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
                trig
                for trig in result.get("matched_triggers", [])
                if trig.get("response", {}).get("category") in allowed
            ]

            auto_triggered = []
            for rule in trigger_rules.get(scene_type, []):
                if all(elem in visible_elements for elem in rule["elements"]):
                    auto_triggered.append(rule["trigger"])
            result.update({
                "auto_triggered": auto_triggered,
                "scene_type": scene_type,
            })

            session["last_result"] = result
            session["last_scene"] = scene_type

    return render_template(
        "qci.html",
        result=session.get(
            "last_result",
            {"scene_type": "unset", "matched_triggers": [], "auto_triggered": []},
        ),
    )


@app.route("/scope")
def scope():
    result = session.get("last_result", {"scene_type": "unset", "matched_triggers": [], "auto_trigger
