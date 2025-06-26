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
