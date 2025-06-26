from flask import Flask, render_template, request, send_file
import os
import openai
from vision_analyzer import get_vision_trigger
from evaluate_faaie import evaluate_trigger
import datetime
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/", methods=["GET", "POST"])
def home():
    trigger = None
    result = None
    image_path = None
    chat_response = None

    if request.method == "POST":
        if "chat_input" in request.form and request.form["chat_input"].strip() != "":
            user_question = request.form["chat_input"]
            completion = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are Scout, a compliance assistant for IHWAP. Respond with brief, factual policy guidance."},
                    {"role": "user", "content": user_question}
                ],
                max_tokens=250
            )
            chat_response = completion.choices[0].message.content
            return render_template("index.html", chat_response=chat_response)

        trigger = request.form.get("trigger", None)
        image = request.files.get("image")

        if image:
            upload_dir = os.path.join("static", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            image_path = os.path.join(upload_dir, "upload.jpg")
            image.save(image_path)
            trigger = get_vision_trigger(image_path)

        if trigger:
            result = evaluate_trigger(trigger)

    return render_template("index.html", trigger=trigger, result=result, image_path=image_path, chat_response=chat_response)

@app.route("/download_report")
def download_report():
    trigger = request.args.get("trigger", "N/A")
    result = request.args.get("result", "N/A")
    image_path = request.args.get("image_path", None)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Helvetica", 12)

    pdf.drawString(50, 750, "🧠 IHWAP Scout Report")
    pdf.drawString(50, 730, f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pdf.drawString(50, 710, f"Trigger: {trigger}")
    pdf.drawString(50, 690, f"Result: {result}")

    if image_path and os.path.exists(image_path):
        try:
            pdf.drawImage(image_path, 50, 500, width=200, height=150)
        except Exception as e:
            pdf.drawString(50, 670, f"Image error: {str(e)}")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="scout_report.pdf", mimetype="application/pdf")

# ✅ Port binding for Render
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)

