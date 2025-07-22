import os
import openai
import json
import glob
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
from vision_matcher import get_matching_trigger_from_image
from decoders import decode_serial

# ----------------------------
# Load ALL logic_health_safety_v*.json at startup
# ----------------------------
def load_all_health_safety_logic():
    logic = []
    for fname in glob.glob("logic_health_safety_v*.json"):
        try:
            with open(fname, "r", encoding="utf-8") as f:
                items = json.load(f)
                if isinstance(items, list):
                    logic.extend(items)
                elif isinstance(items, dict):
                    logic.append(items)
        except Exception as e:
            print(f"Error loading {fname}: {e}")
    return logic

ALL_HEALTH_SAFETY_LOGIC = load_all_health_safety_logic()

# ----------------------------
# Load ALL Section JSONs (manual, sections, field guide)
# ----------------------------
def load_all_sections():
    sections = []
    for fname in glob.glob("Section*.json"):
        with open(fname, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "sections" in data:
                for sec in data["sections"].values():
                    sections.append(sec)
            elif "section" in data:
                sections.append(data)
    return sections

ALL_SECTIONS = load_all_sections()

# ----------------------------
# SEARCH POLICY - finds all matches across ALL logic triggers and all sections/manuals
# ----------------------------
def search_policy(keyword):
    keyword_lower = keyword.lower()
    results = []

    # --- 1. Search logic triggers (ALL_HEALTH_SAFETY_LOGIC) ---
    for item in ALL_HEALTH_SAFETY_LOGIC:
        search_fields = [
            item.get("trigger", ""),
            item.get("action_item", ""),
            item.get("policy_text", ""),
            item.get("documentation", ""),
            " ".join(item.get("tags", []))
        ]
        if any(keyword_lower in field.lower() for field in search_fields):
            answer = f"**Trigger:** {item.get('trigger','')}\n" \
                     f"**Action Item:** {item.get('action_item','')}\n" \
                     f"**Policy Text:** {item.get('policy_text','')}\n" \
                     f"**Documentation:** {item.get('documentation','')}\n"
            policy = item.get("reference_policy", "")
            results.append({"answer": answer, "policy": policy})

    # --- 2. Search manual/sections (ALL_SECTIONS) ---
    for section in ALL_SECTIONS:
        section_flat = json.dumps(section).lower()
        if keyword_lower in section_flat:
            policy = section.get("reference_policy", "") or section.get("reference", "")
            context = []
            for k, v in section.items():
                if k not in ["reference_policy", "reference", "section", "title", "last_updated"]:
                    if isinstance(v, str):
                        context.append(f"{k.capitalize()}: {v}")
                    elif isinstance(v, list):
                        context.extend([str(i) for i in v])
            answer = "\n".join(context)
            results.append({"answer": answer, "policy": policy})

    return results

# ----------------------------
# Flask App Setup
# ----------------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "super_secret_key")
openai.api_key = os.getenv("OPENAI_API_KEY")

# ----------------------------
# Register Chat Blueprint
# ----------------------------
from chat_routes import init_chat_routes
init_chat_routes(app, search_policy)

# ----------------------------
# QCI, Age Finder, and Other App Logic
# ----------------------------
@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/qci", methods=["GET", "POST"])
def qci():
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
            unique_filename = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            image_path = os.path.join(upload_dir, unique_filename)
            image.save(image_path)
            session["last_image_filename"] = unique_filename

            with open(image_path, "rb") as f:
                image_bytes = f.read()
            result = get_matching_trigger_from_image(image_bytes, ALL_HEALTH_SAFETY_LOGIC)
            visible_elements = result.get("visible_elements", [])
            scene_type = result.get("scene_type") if result.get("scene_type") else None

            session["last_result"] = result
            session["last_scene"] = scene_type
            session["last_analysis_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")

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
    # ... (your age finder logic unchanged)
    return render_template("age_finder.html")

@app.route("/scope")
def scope():
    result = session.get("last_result", {"scene_type": "unset", "matched_triggers": [], "auto_triggered": []})
    return render_template("scope.html", result=result)

@app.route("/prevent")
def prevent():
    return render_template("prevent.html")

@app.route("/knowledge", methods=["GET"])
def knowledge():
    q = request.args.get("q")
    if not q:
        return "Query ?q= missing", 400
    results = search_policy(q)
    if not results:
        return "No policy or logic found.", 404
    answers = []
    for res in results:
        answers.append(f"{res['answer']}<br><em>[{res['policy']}]</em>")
    return "<hr>".join(answers)

@app.route("/logic_test")
def logic_test():
    lines = []
    for i, item in enumerate(ALL_HEALTH_SAFETY_LOGIC, 1):
        trigger = item.get("trigger", "NO_TRIGGER")
        tags = ", ".join(item.get("tags", []))
        policy = item.get("reference_policy", "")
        lines.append(f"<b>{i}.</b> <b>{trigger}</b> <br>Tags: <i>{tags}</i> <br>Policy: {policy}<br><hr>")
    total = len(ALL_HEALTH_SAFETY_LOGIC)
    return f"<h2>{total} Triggers Loaded</h2>" + "".join(lines)

# ----------------------------
# MAIN GUARD
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)



