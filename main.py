from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import openai
import json
import base64
import uuid
import markdown
import re
from datetime import datetime
import glob
from vision_matcher import get_matching_trigger_from_image
from decoders import decode_serial

# ------------------------------
# Load ALL Section JSONs at startup (if you still use them elsewhere)
# ------------------------------
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

# ------------------------------
# Load ALL v1–v9 logic JSONs at startup
# ------------------------------
def load_all_health_safety_logic():
    logic = []
    for fname in sorted(glob.glob("logic_health_safety_v*.json")):
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

# ------------------------------
# Modern Search Policy
# ------------------------------
def search_policy(keyword):
    keyword_lower = keyword.lower()
    results = []

    for item in ALL_HEALTH_SAFETY_LOGIC:
        trigger = item.get("trigger", "").lower()
        action_item = item.get("action_item", "").lower()
        policy_text = item.get("policy_text", "").lower()
        tags = [t.lower() for t in item.get("tags", [])]
        doc = item.get("documentation", "")
        policy = item.get("reference_policy", "")

        # Match in trigger, tags, action_item, or policy_text
        match_score = 0
        if keyword_lower in trigger:
            match_score += 3
        if any(keyword_lower in tag for tag in tags):
            match_score += 2
        if keyword_lower in action_item or keyword_lower in policy_text:
            match_score += 1

        if match_score > 0:
            answer_lines = []
            answer_lines.append(f"<b>Trigger:</b> {item.get('trigger','')}")
            answer_lines.append(f"<b>Action Item:</b> {item.get('action_item','')}")
            if "policy_text" in item:
                answer_lines.append(f"<b>Policy Summary:</b> {item['policy_text']}")
            if doc:
                answer_lines.append(f"<b>Required Documentation:</b> {doc}")
            if tags:
                answer_lines.append(f"<b>Tags:</b> {', '.join(item.get('tags', []))}")
            answer_lines.append(f"<b>Citation:</b> {policy}")
            answer = "<br>".join(answer_lines)
            results.append({"answer": answer, "policy": policy, "score": match_score})

    # Sort results by match_score (desc), then by trigger alphabetically
    results = sorted(results, key=lambda r: (-r['score'], r['answer']))
    # Remove the 'score' field before returning
    for r in results:
        r.pop('score', None)
    return results

# ------------------------------
# Flask App Setup
# ------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "super_secret_key")
openai.api_key = os.getenv("OPENAI_API_KEY")

# ------------------------------
# Register Chat Blueprint (modular)
# ------------------------------
from chat_routes import init_chat_routes
init_chat_routes(app, search_policy)

# ------------------------------
# ROUTES
# ------------------------------
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
            unique_filename = f"upload_{uuid.uuid4().hex[:8]}.jpg"
            image_path = os.path.join(upload_dir, unique_filename)
            image.save(image_path)
            session["last_image_filename"] = unique_filename

            with open(image_path, "rb") as f:
                image_bytes = f.read()
            # Use ALL_HEALTH_SAFETY_LOGIC for image logic
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

@app.route("/logic_test")
def logic_test():
    lines = []
    for i, item in enumerate(ALL_HEALTH_SAFETY_LOGIC, 1):
        trigger = item.get("trigger", "NO_TRIGGER")
        tags = ", ".join(item.get("tags", []))
        policy = item.get("reference_policy", "")
        lines.append(f"<b>{i}.</b> <b>{trigger}</b> <br>Tags: <i>{tags}</i> <br>Policy: {policy}<br><hr>")
    total = len(ALL_HEALTH_SAFETY_LOGIC)
    return f"<h2>{total} H&S Triggers Loaded</h2>" + "".join(lines)

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

# MAIN GUARD
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)

