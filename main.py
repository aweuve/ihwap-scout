# IHWAP Scout – Flask back‑end (patched from user‑supplied working main)
# ---------------------------------------------------------------------
#  • Keeps ALL original logic intact
#  • Adds safe defaults so templates don’t error when no photo uploaded
#  • /chat detects Ajax (Accept: application/json or X‑Requested‑With) and
#    returns JSON; plain form‑POST still redirects back to /chat.
#  • /age_finder now serves a GET form so it no longer shows 405 on direct visit.
#  • Small PEP‑8 re‑formatting for readability (imports and empty lines only).

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
                                "You are Scout, an IHWAP 2026 assistant for Weatherization staff.

"
                                "✅ Follow the Weatherization Creed:
"
                                "1. Health & Safety
2. Home Integrity
3. Energy Efficiency

"
                                "Acceptable topics:
"
                                "- IHWAP 2026 policies & measures
"
                                "- DOE WAP rules
"
                                "- Field inspections, scopes, and troubleshooting
"
                                "- Rubber-ducking field issues or manual lookups

"
                                "Answer structure:
"
                                "- Health & Safety concerns first
"
                                "- Deferral risks second
"
                                "- Compliance or tech details last
"
                                "- Include IHWAP 2026 citations if applicable
"
                                "- Be friendly, clear, and concise for field use

"
                                "If unrelated, say:
"
                                "\"I can assist with IHWAP 2026, Weatherization, and inspection topics only.\""
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

            # Determine if caller expects JSON (fetch) or HTML redirect (form)
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

            # ---------------- scene detection ----------------
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

            # ------------- match FAAIE triggers -------------
            result = get_matching_trigger_from_image(image_bytes, faaie_logic)
            visible_elements = result.get("visible_elements", [])

            # heuristic upgrade if GPT said "other"
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

            # auto‑trigger via hard‑coded rules
            auto_triggered = []
            for rule in trigger_rules.get(scene_type, []):
                if all(elem in visible_elements for elem in rule["elements"]):
                    auto_triggered.append(rule["trigger"])
            result.update({
                "auto_triggered": auto_triggered,
                "scene_type": scene_type,
            })

            # cache for later scope page
            session["last_result"] = result
            session["last_scene"] = scene_type

    # ---------- safe default so template never errors ----------
    return render_template(
        "qci.html",
        result=session.get("last_result", {
            "scene_type": "unset",
            "matched_triggers": [],
            "auto_triggered": [],
        }),
    )


@app.route("/scope")
def scope():
    result = session.get("last_result", {
        "scene_type": "unset",
        "matched_triggers": [],
        "auto_triggered": [],
    })
    return render_template("scope.html", result=result)


@app.route("/prevent")
def prevent():
    return render_template("prevent.html")


# ---------- AGE FINDER ----------
@app.route("/age_finder", methods=["GET", "POST"])
def age_finder():
    result = None
    if request.method == "POST":
        serial = request.form.get("serial")
        brand = request.form.get("brand")
        if serial and brand:
            result = decode_serial(serial, brand)
    return render_template("age_finder.html", result=result)


# ---------- QCI REVIEW (AJAX) ----------
@app.route("/qci_review", methods=["POST"])
def qci_review():
    data = request.json or {}
    scene_type = data.get("scene_type", "unknown")
    matched_triggers = data.get("matched_triggers", [])
    auto_triggers = data.get("auto_triggered", [])

    qci_prompt = (
        f"You are a certified IHWAP Quality Control Inspector (QCI). Review this photo for scene type '{scene_type}'.\n"
        f"Issues detected: {', '.join([t['trigger'] for t in matched_triggers] + auto_triggers)}.\n\n"
        "Write a field-ready inspection note listing corrections, documentation, or reinspection needs before approval."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": qci_prompt}],
            max_tokens=300,
        )
        review = response.choices[0].message["content"]
    except Exception as e:
        review = f"Error generating QCI review: {str(e)}"

    session.setdefault("chat_history", []).append({"role": "assistant", "content": review})
    return jsonify({"qci_review": review})


# ---------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

