from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "super_secret_key"

# ✅ Landing Page Route
@app.route("/")
def landing():
    return render_template("landing.html")

# ✅ Chat Route (Chat with Scout)
@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "chat_history" not in session:
        session["chat_history"] = []
    if request.method == "POST":
        question = request.form.get("chat_input")
        if question:
            session["chat_history"].append({"role": "user", "content": question})
            # Placeholder reply — replace with your real Scout chat logic later
            reply = f"🧠 Scout says: I'm answering your question about '{question}'."
            session["chat_history"].append({"role": "assistant", "content": reply})
    return render_template("chat.html", chat_history=session.get("chat_history", []))

# ✅ QCI Photo Review Route
@app.route("/qci", methods=["GET", "POST"])
def qci():
    # Placeholder — replace with your real QCI photo logic later
    return render_template("qci.html")

# ✅ Scope of Work Route
@app.route("/scope")
def scope():
    # Placeholder — replace with your scope display logic later
    return render_template("scope.html")

# ✅ Deferral Preventer Route (Preview)
@app.route("/prevent", methods=["GET", "POST"])
def prevent():
    return render_template("prevent.html")

# ✅ HVAC / Appliance Age Finder Route (Preview)
@app.route("/age", methods=["GET", "POST"])
def age():
    return render_template("age.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

