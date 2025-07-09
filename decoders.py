<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>HVAC/Appliance Age Finder</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f9f9f9; }
        .container { max-width: 500px; margin: 40px auto; background: #fff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 16px #eee; }
        h1 { text-align: center; font-size: 2em; }
        .form-section { margin-bottom: 30px; }
        .manual-toggle { margin: 12px 0 8px 0; text-align: center; }
        .btn { padding: 8px 20px; background: #007bff; color: #fff; border: none; border-radius: 4px; cursor: pointer; margin-top: 10px;}
        .btn:hover { background: #0056b3; }
        .result-card { background: #f6f9fb; border: 1.5px solid #bcd4e3; border-radius: 7px; padding: 18px 20px; margin-top: 18px; }
        .fail { color: #b11; margin: 10px 0 0 0; }
        .img-preview { max-width: 98%; border: 1.2px solid #ccc; border-radius: 4px; margin: 7px 0 18px 0; }
        .or-sep { text-align: center; color: #888; font-size: 1em; margin: 16px 0 2px 0; }
        label { font-weight: bold; }
        input[type="text"], select { width: 100%; padding: 8px; margin-top: 4px; border: 1.1px solid #ccc; border-radius: 4px; }
    </style>
    <script>
        function showManual() {
            document.getElementById('manual-form').style.display = 'block';
            document.getElementById('photo-form').style.display = 'none';
        }
        function showPhoto() {
            document.getElementById('manual-form').style.display = 'none';
            document.getElementById('photo-form').style.display = 'block';
        }
        // Show preview of uploaded image
        function previewImg(event) {
            const out = document.getElementById('img-prev');
            if(event.target.files && event.target.files[0]) {
                out.src = URL.createObjectURL(event.target.files[0]);
                out.style.display = "block";
            } else {
                out.style.display = "none";
            }
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>🔍 HVAC/Appliance Age Finder</h1>
        <div id="photo-form" class="form-section" style="display: {{ 'block' if not use_manual else 'none' }};">
            <form method="POST" enctype="multipart/form-data">
                <label>Upload Photo of Nameplate or Label:</label>
                <input type="file" name="photo" accept="image/*" onchange="previewImg(event)" required>
                <img id="img-prev" class="img-preview" style="display:none;">
                <button class="btn" type="submit">Analyze Photo</button>
            </form>
            <div class="manual-toggle">
                <span>or&nbsp;</span>
                <a href="#" onclick="showManual();return false;">Enter Serial/Brand Manually</a>
            </div>
        </div>
        <div id="manual-form" class="form-section" style="display: {{ 'block' if use_manual else 'none' }};">
            <form method="POST">
                <label for="brand">Brand:</label>
                <select name="brand" id="brand" required>
                    <option value="">-- Select Brand --</option>
                    <option>Rheem / Ruud</option>
                    <option>AO Smith / State</option>
                    <option>Bradford White</option>
                    <option>Goodman / Amana</option>
                    <option>Lennox</option>
                    <option>York / Luxaire / Coleman</option>
                    <option>Carrier / Bryant / Payne</option>
                    <option>American Standard / Trane</option>
                    <option>GE Water Heater</option>
                </select>
                <label for="serial">Serial Number:</label>
                <input type="text" name="serial" id="serial" required>
                <button class="btn" type="submit" name="manual" value="1">Decode Serial</button>
            </form>
            <div class="manual-toggle">
                <a href="#" onclick="showPhoto();return false;">⬅️ Back to Photo Upload</a>
            </div>
        </div>
        {% if result %}
            <div class="result-card">
                {% if result.brand %}<b>Brand:</b> {{ result.brand }}<br>{% endif %}
                {% if result.manufacture_date %}<b>Manufacture Date:</b> {{ result.manufacture_date }}<br>{% endif %}
                {% if result.age is not none %}<b>Age:</b> {{ result.age }} years<br>{% endif %}
                {% if result.action_flag %}<b>{{ result.action_flag }}</b>{% endif %}
                {% if result.note %}<div style="color:#d00">{{ result.note }}</div>{% endif %}
            </div>
        {% elif fail_msg %}
            <div class="fail">{{ fail_msg }}</div>
        {% endif %}
    </div>
</body>
</html>
