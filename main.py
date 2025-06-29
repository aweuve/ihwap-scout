from flask import Flask, render_template, request, send_file, jsonify, session
import os
import openai
import json
import datetime
import io
from vision_matcher import get_matching_trigger_from_image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ✅ Load FAAIE logic
with open("faaie_logic.json", "r") as f:
    faaie_logic = json.load(f)

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Needed for session chat history
openai.api_key = os.getenv("OPENAI_API_KEY")

# ✅ Scout Chat personality
SYSTEM_PROMPT = (
    "You are Scout — a QCI and compliance assistant trained in the Illinois Home Weatherization Assistance Program (IHWAP), "
    "SWS Field Guide, and DOE WAP protocols.\n\n"
    "Respond in a clear, field-savvy tone with:\n"
    "• Bullet point examples when helpful\n"
    "• Bold policy citations (e.g., **IHWAP 5.4.4**, **SWS 3.1201.2**)\n"
    "• Human fallback flag if unsure\n\n"
    "Always prioritize:\n"
    "1. Health & Safety\n"
    "2. Home Integrity\n"
    "3. Energy Efficiency"
)

@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    image_path = None
    chat_response = None

    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        # Chat input
        user_question = request.form.get("chat_input", "").strip()
        if user_question:
            session["chat_history"].append({"role": "user", "content": user_question})
            try:
                completion = openai.ChatCompletion.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + session["chat_history"],
                    max_tokens=400
                )
                reply = completion.choices[0].message["content"]
                session["chat_history"].append({"role": "assistant", "content": reply})
                chat_response = reply
            except Exception as e:
                chat_response = f"Error retrieving response: {str(e)}"

        # Image analysis
        image = request.files.get("image")
        if image:
            upload_dir = os.path.join("static", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            image_path = os.path.join(upload_dir, "upload.jpg")
            image.save(image_path)

            with open(image_path, "rb") as f:
                image_bytes = f.read()
            result = get_matching_trigger_from_image(image_bytes, faaie_logic)

    return render_template(
        "index.html",
        result=result,
        image_path=image_path,
        chat_response=chat_response,
        chat_history=session["chat_history"]
    )

@app.route("/evaluate_image", methods=["POST"])
def evaluate_image():
    try:
        image_file = request.files.get("image")
        if not image_file:
            return jsonify({"error": "No image file provided"}), 400

        image_bytes = image_file.read()
        result = get_matching_trigger_from_image(image_bytes, faaie_logic)

        debug_log = f"📤 Image upload received\n🧠 Description:\n{result['description'][:500]}\n\n"
        if result["visible_elements"]:
            debug_log += f"🔎 Visible Elements: {', '.join(result['visible_elements'])}\n"
        if result["hazards"]:
            debug_log += f"⚠️ Hazards: {', '.join(result['hazards'])}\n"
        if result["scout_thought"]:
            debug_log += f"💭 Scout's Thought: {result['scout_thought']}\n"

        result["debug_log"] = debug_log
        return jsonify(result)

    except Exception as e:
        print("🚨 Server Error:", str(e))
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

@app.route("/download_report")
def download_report():
    trigger = request.args.get("trigger", "N/A")
    result_text = request.args.get("result", "N/A")
    image_path = request.args.get("image_path", None)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Helvetica", 12)

    pdf.drawString(50, 750, "🧠 IHWAP Scout Report")
    pdf.drawString(50, 730, f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pdf.drawString(50, 710, f"Trigger: {trigger}")
    pdf.drawString(50, 690, f"Result: {result_text}")

    if image_path and os.path.exists(image_path):
        try:
            pdf.drawImage(image_path, 50, 500, width=200, height=150)
        except Exception as e:
            pdf.drawString(50, 670, f"Image error: {str(e)}")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="scout_report.pdf", mimetype="application/pdf")

# ✅ Launch app
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)


