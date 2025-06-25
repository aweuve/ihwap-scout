import json

def evaluate_trigger(trigger):
    try:
        with open("faaie_logic.json", "r") as f:
            logic = json.load(f)
        return logic.get(trigger, "⚠️🛑 Action Item: Unknown trigger or unlisted condition.")
    except Exception as e:
        return f"Error reading logic: {str(e)}"
