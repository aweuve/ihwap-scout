# IHWAP Scout – Flask back‑end (clean rebuild)
# ------------------------------------------------
# This single file spins up:
# • Landing page
# • Threaded chat interface (AJAX‑enabled)
# • Age‑finder demo (fixed bug)
# NOTE: Replace the FAKE_FAIIE_REPLY stub with your real FAAIE inference call.

from datetime import datetime
from typing import List, Dict

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    session,
)

app = Flask(__name__)
app.secret_key = "CHANGE_ME_🚨"  # Needed for session storage

# ------------------------------------------------
# Helpers
# ------------------------------------------------

def _init_history() -> List[Dict]:
    """Seed chat history if not present in session."""
    if "messages" not in session:
        session["messages"] = [
            {
                "role": "assistant",
                "text": (
                    "Hello! How can I assist you today with the Illinois Home "
                    "Weatherization Assistance Program or related protocols?"
                ),
                "ts": datetime.now().strftime("%I:%M %p"),
            }
        ]
    return session["messages"]


def _faaie_stub(prompt: str) -> str:
    """Placeholder for FAAIE / OpenAI call – returns a canned reply."""
    # TODO: wire your real model here
    return (
        "[Stub] I received your message: '" + prompt + "'. "
        "Real FAAIE logic will respond once integrated."
    )


# ------------------------------------------------
# Routes
# ------------------------------------------------

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/chat", methods=["GET", "POST"])
def chat():
    history = _init_history()

    if request.method == "POST":
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            # Empty prompt – no processing
            return redirect(url_for("chat"))

        # 1️⃣  store user message
        history.append({
            "role": "user",
            "text": prompt,
            "ts": datetime.now().strftime("%I:%M %p"),
        })

        # 2️⃣  get assistant reply (stub → FAAIE later)
        reply = _faaie_stub(prompt)
        history.append({
            "role": "assistant",
            "text": reply,
            "ts": datetime.now().strftime("%I:%M %p"),
        })
        session.modified = True  # mark session dirty

        # JSON‑aware response (AJAX fetch)
        if request.accept_mimetypes["application/json"] >= request.accept_mimetypes["text/html"]:
            return jsonify({"reply": reply, "ts": history[-1]["ts"]})

        return redirect(url_for("chat"))

    return render_template("chat.html", messages=history)


@app.route("/age_finder", methods=["GET", "POST"])
def age_finder():
    """Simple demo form that calculates appliance age from manufacture year."""
    age = None
    if request.method == "POST":
        year_raw = request.form.get("year")
        try:
            year_int = int(year_raw)
            current_year = datetime.now().year
            age = current_year - year_int
        except (TypeError, ValueError):
            age = "Invalid year input."
    return render_template("age_finder.html", age=age)


# ------------------------------------------------
# Entry‑point for Render / gunicorn
# ------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)



