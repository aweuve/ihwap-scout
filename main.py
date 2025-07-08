# IHWAP Scout – Flask back‑end (rev 7 – clean full rebuild)
# ---------------------------------------------------------------------
#  💠  ROUTE MAP
#  ────────────────────────────────────────────────────────────────────
#  /                 → landing tool‑hub
#  /chat             → threaded chat (GET + AJAX POST)
#  /age_finder       → serial‑decode helper (GET form + POST json)
#  /qci              → QCI Photo Review placeholder (GET + POST)
#  /scope            → Scope‑of‑Work placeholder
#  /prevent          → Preventive Measures placeholder
#  /index            → optional simple index page
#
#  🔧  HOW TO EXTEND
#  • Swap FAKE_FAIIE_REPLY for a call to your FAAIE inference API
#  • Replace placeholder templates with real logic as features mature
# ---------------------------------------------------------------------

from datetime import datetime
import os
from typing import List, Dict

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecret")

# ---------------------------------------------------------------------------
# Landing page – hub with tool buttons
# ---------------------------------------------------------------------------
@app.route("/")
def landing():
    return render_template("landing.html")

# ---------------------------------------------------------------------------
# Threaded Chat (AJAX‑enhanced)
# ---------------------------------------------------------------------------
@app.route("/chat", methods=["GET", "POST"])
def chat():
    # ensure session history list exists
    messages: List[Dict] = session.setdefault("messages", [])

    if request.method == "POST":
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            return redirect(url_for("chat"))

        ts = datetime.now().strftime("%H:%M:%S")
        messages.append({"role": "user", "text": prompt, "ts": ts})

        # ▶️  TODO: call live FAAIE endpoint here
        reply = "FAKE_FAIIE_REPLY"
        messages.append({"role": "assistant", "text": reply, "ts": ts})
        session["messages"] = messages

        # AJAX post returns JSON instead of redirect
        if request.accept_mimetypes.accept_json:
            return jsonify({"reply": reply, "ts": ts})
        return redirect(url_for("chat"))

    return render_template("chat.html", messages=messages)

# ---------------------------------------------------------------------------
# Age Finder helper – GET form + POST JSON
# ---------------------------------------------------------------------------
@app.route("/age_finder", methods=["GET", "POST"])
def age_finder():
    if request.method == "GET":
        return render_template("age_finder.html")

    serial = request.form.get("serial", "").strip()
    if not serial or not serial[-4:].isdigit():
        return jsonify(error="Bad serial"), 400
    age = datetime.now().year - int(serial[-4:])
    return jsonify(age=age)

# ---------------------------------------------------------------------------
# QCI Photo Review – placeholder accepts GET & POST for future file upload
# ---------------------------------------------------------------------------
@app.route("/qci", methods=["GET", "POST"])
def qci():
    if request.method == "POST":
        # TODO: process uploaded image / run vision model
        analyzed = {
            "scene_type": "crawlspace",  # stub value
            "flags": ["⚠️ Moisture risk"],
            "recommendations": ["Install vapor barrier"]
        }
        return render_template("qci.html", result=analyzed)

    # GET → safe empty context so template doesn’t 500
    empty_ctx = {
        "scene_type": "unknown",
        "flags": [],
        "recommendations": []
    }
    return render_template("qci.html", result=empty_ctx)

# ---------------------------------------------------------------------------
# Scope‑of‑Work Summary placeholder
# ---------------------------------------------------------------------------
@app.route("/scope")
def scope():
    return render_template("scope.html")

# ---------------------------------------------------------------------------
# Preventive Measures placeholder
# ---------------------------------------------------------------------------
@app.route("/prevent")
def prevent():
    return render_template("prevent.html")

# ---------------------------------------------------------------------------
# Optional simple index page
# ---------------------------------------------------------------------------
@app.route("/index")
def index_page():
    return render_template("index.html")

# ---------------------------------------------------------------------------
# MAIN ENTRY
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Render looks for the PORT env; default 5000 for local dev
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
