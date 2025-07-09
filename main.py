from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import openai
import json
import base64
import uuid
import markdown
from datetime import datetime
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
    session.setdefault("chat_history", [])

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
"I can assist with IHWAP 2026, Weatherization, and inspection topics only."""
                            ),
                        }
                    ]
                    + session["chat_history"],
                    max_tokens=500,
                )
                assistant_reply_raw = completion.choices[0].message["content"]
                assistant_reply = markdown.markdown(
                    assistant_reply_raw,
                    extensions=['extra'],
                    output_format='html5'
                )
            except Exception as e:
                assistant_reply = f"<pre>Error: {e}</pre>"

            session["chat_history"].append({"role": "assistant", "content": assistant_reply})
            session.modified = True

            wants_json = (
                request.is_json
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or request.headers.get("Accept", "").startswith("application/json")
            )
            if wants_json:
                return jsonify({"reply": assistant_reply})
            return redirect(url_for("chat"))

    return render_template("chat.html", chat_history=session.get("chat_history", []))


@app.route("/qci", methods=["GET", "POST"])
def qci():
    # --- Session reset for "New QCI Review" ---
    if request.method == "GET" and request.args.get("new"):
        session.pop("last_image_filename", None)
        session.pop("last_result", None)
        session.pop("last_scene", None)
        session.pop("last_analysis_date", None)
        return redirect(url_for("qci"))

    result = session.get("last_result")
    image_path = None
    scene_type = None

    if request.method == "POST":
        image = request.files.get("image")
        if image:
            upload_dir = os.path.join("static", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            unique_filename = f"upload_{uuid.uuid4().hex[:8]}.jpg"
            image_path = os.path.join(upload_dir, unique_filename)
            image.save(image_path)
            session["last_image_filename"] = unique_filename

            with open(image_path, "rb") as f:
                image_bytes = f.read()
            # Model/logic analysis
            result = get_matching_trigger_from_image(image_bytes, faaie_logic)
            visible_elements = result.get("visible_elements", [])

            if result.get("scene_type"):
                scene_type = result["scene_type"]
            else:
                scene_type = None

            session["last_result"] = result
            session["last_scene"] = scene_type
            session["last_analysis_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # On GET (or after POST), load info from session
    unique_filename = session.get("last_image_filename")
    if unique_filename:
        image_path = os.path.join("static", "uploads", unique_filename)

    return render_template(
        "qci.html",
        result=session.get("last_result"),
        analysis_date=session.get("last_analysis_date", ""),
        image_path=image_path
    )

@app.route("/age_finder", methods=["GET", "POST"])
def age_finder():
    result = None
    fail_msg = None
    use_manual = False

    if request.method == "POST":
        # Manual fallback
        if request.form.get("manual"):
            use_manual = True
            brand = request.form.get("brand", "")
            serial = request.form.get("serial", "").strip()
            if not serial or not brand:
                fail_msg = "Please provide both brand and serial number."
            else:
                res = decode_serial(serial, brand)
                if isinstance(res, dict):
                    result = res
                else:
                    fail_msg = res

        # Photo upload
        elif "photo" in request.files:
            photo = request.files.get("photo")
            if photo and photo.filename:
                img_bytes = photo.read()
                # Use GPT-4 Vision to extract serial/model from the image
                try:
                    base64_img = base64.b64encode(img_bytes).decode("utf-8")
                    vision_resp = openai.ChatCompletion.create(
                        model="gpt-4-vision-preview",
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are an expert at reading appliance nameplate/label images. "
                                    "Return the brand and serial number in this photo. "
                                    "Only respond in this JSON format: "
                                    '{"brand": "...", "serial": "..."} '
                                ),
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"},
                                    }
                                ],
                            },
                        ],
                        max_tokens=200,
                    )
                    import json as pyjson
                    txt = vision_resp.choices[0].message["content"]
                    try:
                        data = pyjson.loads(txt)
                        brand = data.get("brand", "").strip()
                        serial = data.get("serial", "").strip()
                        if not brand or not serial:
                            raise ValueError
                        res = decode_serial(serial, brand)
                        if isinstance(res, dict):
                            result = res
                        else:
                            fail_msg = res
                    except Exception:
                        fail_msg = (
                            "Could not automatically extract brand/serial from the image. "
                            "Please enter them manually below."
                        )
                        use_manual = True
                except Exception as e:
                    fail_msg = f"Vision model error: {e}"
                    use_manual = True
            else:
                fail_msg = "No image uploaded."
    return render_template(
        "age_finder.html",
        result=result,
        fail_msg=fail_msg,
        use_manual=use_manual,
    )

@app.route("/scope")
def scope():
    result = session.get("last_result", {"scene_type": "unset", "matched_triggers": [], "auto_triggered": []})
    return render_template("scope.html", result=result)

@app.route("/prevent")
def prevent():
    return render_template("prevent.html")

# MAIN GUARD – run locally or on Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
