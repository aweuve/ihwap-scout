# IHWAP Scout – Flask back‑end (rev 5 – adds /prevent + /index placeholders)
# -------------------------------------------------------------
# • Landing page (/) – hub of tool buttons
# • Threaded chat (/chat) – AJAX + fallback
# • Age‑finder helper (/age_finder) – demo utility
# • QCI Photo Review placeholder (/qci)
# • Scope‑of‑Work Summary placeholder (/scope)
# • Preventive Measures placeholder (/prevent)
# • Index placeholder (/index) – optional template link
#
# NOTE: Replace FAKE_FAIIE_REPLY stub with real FAAIE inference call when ready.

from datetime import datetime
import os
from typing import List, Dict

from flask import Flask, render_template, request, jsonify, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecret")

# ---------------------------------------------------------------------------
# Landing page – lists tool buttons
# ---------------------------------------------------------------------------
@app.route("/")
def landing():
    return render_template("landing.html")

# ---------------------------------------------------------------------------
# Chat – AJAX + full‑page fallback
# ---------------------------------------------------------------------------
@app.route("/chat", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            return redirect(url_for("chat"))

        # Persist thread in session for demo purposes
        messages: List[Dict] = session.setdefault("messages", [])
        ts = datetime.now().strftime("%H:%M:%S")
        messages.append({"role": "user", "text": prompt, "ts": ts})

        # ✂️ stub FAAIE call – replace with real logic
        reply = "FAKE_FAIIE_REPLY"
        messages.append({"role": "assistant", "text": reply, "ts": ts})
        session["messages"] = messages

        # AJAX response
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
# QCI Photo Review placeholder – prevents url_for BuildError
# ---------------------------------------------------------------------------
@app.route("/qci")
def qci():
    return render_template("qci.html")  # ensure template exists

# ---------------------------------------------------------------------------
# Scope‑of‑Work Summary placeholder – prevents url_for BuildError
# ---------------------------------------------------------------------------
@app.route("/scope")
def scope():
    return render_template("scope.html")

# ---------------------------------------------------------------------------
# Preventive Measures placeholder – prevents url_for BuildError
# ---------------------------------------------------------------------------
@app.route("/prevent")
def prevent():
    return render_template("prevent.html")

# ---------------------------------------------------------------------------
# Optional index page if linked – safe no‑op
# ---------------------------------------------------------------------------
@app.route("/index")
def index_page():
    return render_template("index.html")

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
