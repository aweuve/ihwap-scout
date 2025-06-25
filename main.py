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
                trigger = get_vision_trigger(image_path)

        if trigger:
            result = evaluate_trigger(trigger)

    return render_template("index.html", trigger=trigger, result=result, image_path=image_path)
