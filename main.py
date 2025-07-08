# IHWAP Scout – Flask back‑end (rev 2 – adds /qci placeholder)
# -------------------------------------------------------------
# Routes:
#   • /               → landing page (tool hub)
#   • /chat           → threaded chat (AJAX + full‑page POST fallback)
#   • /age_finder     → demo serial‑decode helper
#   • /qci            → NEW: placeholder for QCI Photo Review (fixes BuildError)
#
# NOTE: swap FAKE_FAIIE_REPLY for a live call when ready.

from datetime import datetime
from pathlib import Path
from typing import List, Dict
import os

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    session,
    make_response,
)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "scout‑dev‑key")

# ----------------------------- Landing -----------------------------
@app.route("/")
def landing():
    """Tool hub with links to Chat, Age‑Finder, QCI, etc."""
    return render_template("landing.html")

# ------------------------------ Chat -------------------------------
@app.route("/chat", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            return redirect(url_for("chat"))

        history: List[Dict] = session.get("history", [])
        history.append({"role": "user", "text": prompt, "ts": datetime.now().strftime("%H:%M")})

        # TODO: replace with real FAAIE logic call
        assistant_reply = FAKE_FAIIE_REPLY(prompt)
        history.append({"role": "assistant", "text": assistant_reply, "ts": datetime.now().strftime("%H:%M")})

        session["history"] = history

        # AJAX? → return JSON
        if request.headers.get("HX-Request") or request.accept_mimetypes.best == "application/json":
            return jsonify({"reply": assistant_reply, "ts": history[-1]["ts"]})

        return redirect(url_for("chat"))

    # GET
    history = session.get("history", [])
    return render_template("chat.html", messages=history)


def FAKE_FAIIE_REPLY(prompt: str) -> str:
    """Temporary stub until FAAIE inference is wired in."""
    return f"(stub) You said: {prompt[:60]}…"

# --------------------------- Age Finder ----------------------------
@app.route("/age_finder", methods=["POST"])
def age_finder():
    serial = request.form.get("serial", "").strip()
    if not serial:
        return jsonify(error="Missing serial number"), 400

    # very rudimentary example – real logic will map serial → manufacture date
    try:
        year = int(serial[-2:]) + 2000  # e.g., "AB1234 24" ⇒ 2024
        return jsonify({"estimated_year": year})
    except ValueError:
        return jsonify(error="Could not parse year from serial"), 422

# ----------------------------- QCI ---------------------------------
@app.route("/qci", methods=["GET", "POST"])
def qci():
    """Minimal placeholder so landing.html’s link resolves.
    Expand later to accept image uploads & call FAAIE."""

    if request.method == "POST":
        # In future: handle file upload & return JSON verdict
        return jsonify({"status": "upload received – processing TBD"})

    # Simple inline HTML avoids template‑not‑found error
    html = """
    <h1>QCI Photo Review (Placeholder)</h1>
    <p>The endpoint is wired; UI coming soon.</p>
    <p><a href='/'>Back to tool hub</a></p>
    """
    return make_response(html)

# ---------------------------- Run dev ------------------------------
if __name__ == "__main__":
    debug_host = os.getenv("HOST", "127.0.0.1")
    debug_port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host=debug_host, port=debug_port)
