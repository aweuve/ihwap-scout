from flask import Flask, request, render_template
from werkzeug.utils import secure_filename
import os
from evaluate_faaie import evaluate_trigger
from vision_analyzer import get_vision_trigger

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ✅ Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def home():
    trigger = ""
    result = ""
    image_path = ""

    if request.method == "POST":
        trigger = request.form.get("trigger", "").lower()
        image = request.files.get("image")

        if image and image.filename:
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)

            if not trigger:
                print("🛰️ Running Vision Trigger")
                trigger = get_vision_trigger(image_path)

        if trigger:
            result = evaluate_trigger(trigger)

    return render_template("index.html", trigger=trigger, result=result, image_path=image_path)

# ✅ Required for Render to expose public port
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
