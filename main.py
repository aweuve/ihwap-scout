import os
import openai
import json
import base64
import uuid
import markdown
import re
from datetime import datetime
import glob

from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from vision_matcher import get_matching_trigger_from_image  # Assumes you have this in your stack
from decoders import decode_serial
from chat_routes import init_chat_routes  # Assumes you have chat_routes.py in your stack

# ------------------------------
# LOAD ALL HEALTH & SAFETY LOGIC v1-v9
# ------------------------------
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

# ------------------------------
# FLEXIBLE SEARCH POLICY FUNCTION
# ------------------------------
def search_policy(keyword):
    keyword_lower = keyword.lower().strip()
    key_terms = re.split(r"[\s_\-]+", keyword_lower)
    results = []
    seen_policies = set()

    def _score_match(text):
        score = 0
        for term in key_terms:
            if term in text:
                score += 1
        return score

    for item in ALL_HEALTH_SAFETY_LOGIC:
        fields = [
            item.get("trigger", ""),
            item.get("action_item", ""),
            item.get("policy_text", ""),
            item.get("documentation", ""),
            " ".join(item.get("tags", [])),
        ]
        joined = " ".join(fields).lower()
        match_score = _score_match(joined)
        if match_score == len(key_terms):
            policy = item.get("reference_policy", "")
            answer = f"{item.get('action_item', '')}\n{item.get('policy_text', '')}"
            if policy not in seen_policies:
                results.append({
                    "answer": answer.strip(),
                    "policy": policy,
                    "score": match_score,
                })
                seen_policies.add(policy)

    # Fallback: partial matches if nothing perfect
    if not results:
        for item in ALL_HEALTH_SAFETY_LOGIC:
            fields = [
                item.get("trigger", ""),
                item.get("action_item", ""),
                item.get("policy_text", ""),
                item.get("documentation", ""),
                " ".join(item.get("tags", [])),
            ]
            joined = " ".join(fields).lower()
            match_score = sum(1 for term in key_terms if term in joined)
            if match_score > 0:
                policy = item.get("reference_policy", "")
                answer = f"{item.get('action_item', '')}\n{item.get('policy_text', '')}"
                if policy not in seen_policies:
                    results.append({
                        "answer": answer.strip(),
                        "policy": policy,
                        "score": match_score,
                    })
                    seen_policies.add(policy)

    results = sorted(results, key=lambda r: -r["score"])
    for r in results:
        r.pop("score", None)
    return results

# ------------------------------
# FLASK APP SETUP
# ------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "super_secret_key")
openai.api_key = os.getenv("OPENAI_API_KEY")

# ------------------------------
# REGISTER CHAT ROUTES (MODULAR)
# ------------------------------
init_chat_routes(app, search_policy)

# ------------------------------
# OTHER APP LOGIC (OPTIONAL)
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

@app.route("/scope")
def scope():
    result = session.get("last_result", {"scene_type": "unset", "matched_triggers": [], "auto_triggered": []})
    return render_template("scope.html", result=result)

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
    return f"<h2>{total} H&S Triggers Loaded</h2>" + "".join(lines)

# ------------------------------
# MAIN GUARD
# ------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
