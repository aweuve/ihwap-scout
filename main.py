@app.route("/age_finder", methods=["GET", "POST"])
def age_finder():
    result = None
    fail_msg = None
    use_manual = False
    ocr_text = None

    if request.method == "POST":
        # Manual fallback
        if request.form.get("manual"):
            use_manual = True
            brand = request.form.get("brand", "")
            serial = request.form.get("serial", "").strip()
            if not serial or not brand:
                fail_msg = "Please provide both brand and serial number."
            else:
                res = decode_serial(serial, brand)
                if isinstance(res, dict):
                    result = res
                else:
                    fail_msg = res

        # Photo upload
        elif "photo" in request.files:
            photo = request.files.get("photo")
            if photo and photo.filename:
                img_bytes = photo.read()
                # --- ENHANCED VISION PROMPT START ---
                try:
                    base64_img = base64.b64encode(img_bytes).decode("utf-8")
                    vision_prompt = (
                        "You are an HVAC and appliance label expert. "
                        "Extract ONLY the following from the nameplate or label in this photo: "
                        "brand (if shown), model number, and serial number. "
                        "Look for fields labeled 'Model', 'Model (Modèle)', 'Serial No', 'Serial (Série) No', 'S/N', or similar. "
                        "Ignore barcodes—use only the printed letters/numbers. "
                        "Respond ONLY with valid JSON like this: "
                        '{"brand": "...", "model": "...", "serial": "..."} '
                        "If any value is not found, return an empty string for that field. "
                        "EXAMPLE: "
                        '{"brand": "", "model": "GD080M16B-S", "serial": "GD0000658741"}'
                    )
                    vision_resp = openai.ChatCompletion.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": vision_prompt},
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"},
                                    }
                                ],
                            },
                        ],
                        max_tokens=200,
                    )
                    import json as pyjson
                    txt = vision_resp.choices[0].message["content"]
                    try:
                        data = pyjson.loads(txt)
                        brand = data.get("brand", "").strip()
                        serial = data.get("serial", "").strip()
                        if not brand or not serial:
                            raise ValueError
                        res = decode_serial(serial, brand)
                        if isinstance(res, dict):
                            result = res
                        else:
                            fail_msg = res
                    except Exception:
                        # --- FALLBACK: Try to extract all text for manual copy ---
                        ocr_prompt = (
                            "You are an OCR engine. Extract ALL readable text from the uploaded appliance label photo, including numbers and letters. "
                            "Respond ONLY with a plain text list. Do NOT try to interpret it. Do NOT reply in JSON."
                        )
                        ocr_resp = openai.ChatCompletion.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": ocr_prompt},
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "image_url",
                                            "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"},
                                        }
                                    ],
                                },
                            ],
                            max_tokens=600,
                        )
                        ocr_text = ocr_resp.choices[0].message["content"]
                        fail_msg = (
                            "Could not automatically extract brand/serial from the image. "
                            "See all detected label text below, or enter the info manually."
                        )
                        use_manual = True
                except Exception as e:
                    fail_msg = f"Vision model error: {e}"
                    use_manual = True
            else:
                fail_msg = "No image uploaded."
    return render_template(
        "age_finder.html",
        result=result,
        fail_msg=fail_msg,
        use_manual=use_manual,
        ocr_text=ocr_text,
    )
