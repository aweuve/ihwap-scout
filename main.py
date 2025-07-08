# IHWAP Scout – Flask back‑end (rev 6 – fixes UndefinedError in /qci)
# -------------------------------------------------------------
# • Adds safe‑context payload to /qci so qci.html can reference {{ result.* }}
# • No other logic changed.
#
# NOTE: Replace FAKE_FAIIE_REPLY with real FAAIE inference call when ready.

from datetime import datetime
import os
from typing import List, Dict

from flask import Flask, render_template, request, jsonify, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecret")

# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------
@app.route("/")
def landing():
    return render_template("landing.html")

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
@app.route("/chat", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            return redirect(url_for("chat"))

        messages: List[Dict] = session.setdefault("messages", [])
        ts = datetime.now().strftime("%H:%M:%S")
        messages.append({"role": "user", "text": prompt, "ts": ts})

        # ▶️  stub – replace with real FAAIE call
        reply = "FAKE_FAIIE_REPLY"
        messages.append({"role": "assistant", "text": reply, "ts": ts})
        session["messages"] = messages

        if request.accept_mimetypes.accept_json:
            return jsonify({"reply": reply, "ts": ts})
        return redirect(url_for("chat"))

    return render_template("chat.html", messages=session.get("messages", []))

# ---------------------------------------------------------------------------
# Age‑finder helper demo
# ---------------------------------------------------------------------------
@app.route("/age_finder", methods=["POST"])
def age_finder():
    serial = request.form.get("serial", "").strip()
    if not serial or not serial[-4:].isdigit():
        return jsonify(error="Bad serial"), 400
    age = datetime.now().year - int(serial[-4:])
    return jsonify(age=age)

# ---------------------------------------------------------------------------
# QCI Photo Review – now passes default context to template
# ---------------------------------------------------------------------------
@app.route("/qci")
def qci():
    placeholder_result = {
        "scene_type": "unknown",
        "flags": [],
        "recommendations": []
    }
    return render_template("qci.html", result=placeholder_result)

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
# Optional index page
# ---------------------------------------------------------------------------
@app.route("/index")
def index_page():
    return render_template("index.html")

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
