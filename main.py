from flask import Flask, render_template, request, send_file, jsonify
import os
import openai
import datetime
import io
from vision_matcher import get_matching_trigger_from_image
from evaluate_faaie import evaluate_trigger  # Optional if still used

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/", methods=["GET", "POST"])
def home():
    trigger = None
    result = None
    image_path = None
    chat_response = None

    if request.method == "POST":
        # Chat input
        if "chat_input" in request.form and request.form["chat_input"].strip() != "":
            user_question = request.form["chat_input"]
            completion = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are Scout, a compliance assistant for IHWAP. Respond with brief, factual policy guidance."},
                    {"role": "user", "content": user_question}
                ],
                max_tokens=250
            )
            chat_response = completion.choices[0].message["content"]
            return render_template("index.html", chat_response=chat_response)

        # Image logic
        trigger = request.form.get("trigger", None)
        image = request.files.get("image")

        if image:
            upload_dir = os.path.join("static", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            image_path = os.path.join(upload_dir, "upload.jpg")
            image.save(image_path)

            with open(image_path, "rb") as f:
                image_bytes = f.read()

            result = get_matching_trigger_from_image(image_bytes)

    return render_template("index.html", trigger=trigger, result=result, image_path=image_path, chat_response=chat_response)

@app.route("/evaluate_image", methods=["POST"])
def evaluate_image():
    image_file = request.files.get("image")
    if not image_file:
        return jsonify({"error": "No image file provided"}), 400

    image_bytes = image_file.read()
    result = get_matching_trigger_from_image(image_bytes)

    # Build Debug Log
    debug_log = f"📤 Image upload received\n🧠 Description:\n{result['description'][:500]}\n\n"
    if result["matched_triggers"]:
        for match in result["matched_triggers"]:
            debug_log += f"✅ Matched Trigger: {match['trigger']}\n🔧 Score Details: {match['response'].get('reason', '')}\n\n"
    else:
        debug_log += "❌ No matches found in logic.\n"

    result["debug_log"] = debug_log
    return jsonify(result)

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
