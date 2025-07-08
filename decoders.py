# decoders.py
# Appliance Serial Number Decoders – IHWAP Scout

# Major & Legacy Brands Covered:
# - Rheem / Ruud
# - AO Smith / State
# - Bradford White
# - Goodman / Amana
# - Lennox
# - York / Luxaire / Coleman
# - Carrier / Bryant / Payne
# - American Standard / Trane
# - GE Water Heaters


def decode_rheem(serial):
    try:
        month = int(serial[0:2])
        year = int(serial[2:4])
        if not 1 <= month <= 12:
            return "Invalid month in serial number."
        full_year = 2000 + year if year < 50 else 1900 + year
        age = 2025 - full_year
        manufacture_date = f"{month:02d}/{full_year}"
        action_flag = ""
        if age >= 15:
            action_flag = "⚠️🛑 Action Item: Recommend replacement consideration per IHWAP 2026 §5.3.4"
        return {
            "brand": "Rheem / Ruud",
            "manufacture_date": manufacture_date,
            "age": age,
            "action_flag": action_flag
        }
    except Exception as e:
        return f"Error decoding serial number: {e}"


def decode_ao_smith(serial):
    try:
        year = int(serial[0:2])
        week = int(serial[2:4])
        full_year = 2000 + year if year < 50 else 1900 + year
        age = 2025 - full_year
        manufacture_date = f"Week {week}, {full_year}"
        action_flag = ""
        if age >= 15:
            action_flag = "⚠️🛑 Action Item: Recommend replacement consideration per IHWAP 2026 §5.3.4"
        return {
            "brand": "AO Smith / State",
            "manufacture_date": manufacture_date,
            "age": age,
            "action_flag": action_flag
        }
    except Exception as e:
        return f"Error decoding serial number: {e}"


def decode_bradford_white(serial):
    try:
        year_letters = {
            "A": 1984, "B": 1985, "C": 1986, "D": 1987, "E": 1988, "F": 1989,
            "G": 1990, "H": 1991, "J": 1992, "K": 1993, "L": 1994, "M": 1995,
            "N": 1996, "P": 1997, "S": 1998, "T": 1999, "W": 2000, "X": 2001,
            "Y": 2002, "A": 2004, "B": 2005, "C": 2006, "D": 2007, "E": 2008,
            "F": 2009, "G": 2010, "H": 2011, "J": 2012, "K": 2013, "L": 2014,
            "M": 2015, "N": 2016, "P": 2017, "S": 2018, "T": 2019, "W": 2020,
            "X": 2021, "Y": 2022
        }
        month_letters = {
            "A": "January", "B": "February", "C": "March", "D": "April",
            "E": "May", "F": "June", "G": "July", "H": "August",
            "J": "September", "K": "October", "L": "November", "M": "December"
        }
        year_code = serial[0].upper()
        month_code = serial[1].upper()
        full_year = year_letters.get(year_code, None)
        month = month_letters.get(month_code, None)
        if full_year is None or month is None:
            return "Invalid Bradford White serial number."
        age = 2025 - full_year
        manufacture_date = f"{month}, {full_year}"
        action_flag = ""
        if age >= 15:
            action_flag = "⚠️🛑 Action Item: Recommend replacement consideration per IHWAP 2026 §5.3.4"
        return {
            "brand": "Bradford White",
            "manufacture_date": manufacture_date,
            "age": age,
            "action_flag": action_flag
        }
    except Exception as e:
        return f"Error decoding serial number: {e}"


def decode_goodman(serial):
    try:
        year = int(serial[0:2])
        month = int(serial[2:4])
        if not 1 <= month <= 12:
            return "Invalid month in serial number."
        full_year = 2000 + year if year < 50 else 1900 + year
        age = 2025 - full_year
        manufacture_date = f"{month:02d}/{full_year}"
        action_flag = ""
        if age >= 15:
            action_flag = "⚠️🛑 Action Item: Recommend replacement consideration per IHWAP 2026 §5.3.4"
        return {
            "brand": "Goodman / Amana",
            "manufacture_date": manufacture_date,
            "age": age,
            "action_flag": action_flag
        }
    except Exception as e:
        return f"Error decoding serial number: {e}"


def decode_lennox(serial):
    try:
        year = int(serial[0:2])
        month = int(serial[2:4])
        if 1 <= month <= 12:
            full_year = 2000 + year if year < 50 else 1900 + year
            age = 2025 - full_year
            manufacture_date = f"{month:02d}/{full_year}"
        else:
            full_year = int(serial[0:4])
            age = 2025 - full_year
            manufacture_date = f"{full_year}"
        action_flag = ""
        if age >= 15:
            action_flag = "⚠️🛑 Action Item: Recommend replacement consideration per IHWAP 2026 §5.3.4"
        return {
            "brand": "Lennox",
            "manufacture_date": manufacture_date,
            "age": age,
            "action_flag": action_flag
        }
    except Exception as e:
        return f"Error decoding serial number: {e}"


def decode_york(serial):
    try:
        year = int(serial[2:4])
        week = int(serial[4:6])
        full_year = 2000 + year if year < 50 else 1900 + year
        age = 2025 - full_year
        manufacture_date = f"Week {week}, {full_year}"
        action_flag = ""
        if age >= 15:
            action_flag = "⚠️🛑 Action Item: Recommend replacement consideration per IHWAP 2026 §5.3.4"
        return {
            "brand": "York / Luxaire / Coleman",
            "manufacture_date": manufacture_date,
            "age": age,
            "action_flag": action_flag
        }
    except Exception as e:
        return f"Error decoding serial number: {e}"


def decode_carrier(serial):
    try:
        year = int(serial[0:2])
        week = int(serial[2:4])
        if week > 52:
            year = int(serial[2:4])
            week = int(serial[0:2])
        full_year = 2000 + year if year < 50 else 1900 + year
        age = 2025 - full_year
        manufacture_date = f"Week {week}, {full_year}"
        action_flag = ""
        if age >= 15:
            action_flag = "⚠️🛑 Action Item: Recommend replacement consideration per IHWAP 2026 §5.3.4"
        return {
            "brand": "Carrier / Bryant / Payne",
            "manufacture_date": manufacture_date,
            "age": age,
            "action_flag": action_flag
        }
    except Exception as e:
        return f"Error decoding serial number: {e}"


def decode_trane(serial):
    try:
        year = int(serial[0:2])
        week = int(serial[2:4])
        full_year = 2000 + year if year < 50 else 1900 + year
        age = 2025 - full_year
        manufacture_date = f"Week {week}, {full_year}"
        action_flag = ""
        if age >= 15:
            action_flag = "⚠️🛑 Action Item: Recommend replacement consideration per IHWAP 2026 §5.3.4"
        return {
            "brand": "American Standard / Trane",
            "manufacture_date": manufacture_date,
            "age": age,
            "action_flag": action_flag
        }
    except Exception as e:
        return f"Error decoding serial number: {e}"


def decode_ge(serial):
    try:
        month = int(serial[0:2])
        year = int(serial[2:4])
        if not 1 <= month <= 12:
            return "Invalid month in serial number."
        full_year = 2000 + year if year < 50 else 1900 + year
        age = 2025 - full_year
        manufacture_date = f"{month:02d}/{full_year}"
        action_flag = ""
        if age >= 15:
            action_flag = "⚠️🛑 Action Item: Recommend replacement consideration per IHWAP 2026 §5.3.4"
        return {
            "brand": "GE Water Heater",
            "manufacture_date": manufacture_date,
            "age": age,
            "action_flag": action_flag
        }
    except Exception as e:
        return f"Error decoding serial number: {e}"


def decode_serial(serial, brand):
    brand_map = {
        'Rheem / Ruud': decode_rheem,
        'AO Smith / State': decode_ao_smith,
        'Bradford White': decode_bradford_white,
        'Goodman / Amana': decode_goodman,
        'Lennox': decode_lennox,
        'York / Luxaire / Coleman': decode_york,
        'Carrier / Bryant / Payne': decode_carrier,
        'American Standard / Trane': decode_trane,
        'GE Water Heater': decode_ge
    }
    decoder = brand_map.get(brand)
    if decoder:
        return decoder(serial)
    else:
        return f"Brand '{brand}' not recognized. Please verify the brand selection."
