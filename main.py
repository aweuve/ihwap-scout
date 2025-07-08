# IHWAP Scout – Flask back‑end (rev 8 – fixes chat JSON response)
# ---------------------------------------------------------------------
# Changes from rev 7:
#   • /chat now reliably returns JSON when the request comes from fetch()
#     – checks for Accept header OR X‑Requested‑With header
#   • GET /chat still renders the template with message history
#   • POST via regular form‑submit continues to redirect back to /chat
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

# Helper to detect an AJAX/fetch call -------------------------------

def is_ajax(req):
    # fetch() without explicit headers usually sets this Accept value
    return (
        req.headers.get("Accept", "").startswith("application/json") or
        req.headers.get("X-Requested-With") == "XMLHttpRequest"
    )

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

        # Return JSON for fetch/AJAX callers, otherwise redirect
        if is_ajax(request):
            return jsonify({"reply": reply, "ts": ts})
        return redirect(url_for("chat"))

    # GET
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

    empty_ctx = {"scene_type": "unknown", "flags": [], "recommendations": []}
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
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
