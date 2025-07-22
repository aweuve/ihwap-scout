from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
import openai
import markdown

def init_chat_routes(app, search_policy):
    chat_bp = Blueprint('chat', __name__)

    @chat_bp.route("/chat", methods=["GET", "POST"])
    def chat():
        session.setdefault("chat_history", [])

        if request.method == "POST":
            user_msg = (
                request.form.get("chat_input")
                or request.form.get("prompt")
                or (request.json.get("prompt") if request.is_json else None)
            )

            if user_msg:
                session["chat_history"].append({"role": "user", "content": user_msg})
                # --- Get the most relevant rule/action from your logic search ---
                search_results = search_policy(user_msg)
                context_snippet = ""
                found_citation = None
                if search_results:
                    # Use only the most relevant result (first)
                    best = search_results[0]
                    # Build a bullet-style summary using fields from your JSON logic
                    field_answer = ""
                    if "answer" in best and best["answer"]:
                        field_answer += best["answer"].strip() + "\n"
                    # Add Action Item as a field bullet (if present)
                    if "action_item" in best and best["action_item"]:
                        field_answer += f"- {best['action_item'].strip()}\n"
                    # Add tags if helpful for field users (optional)
                    # if "tags" in best and best["tags"]:
                    #     field_answer += f"Tags: {', '.join(best['tags'])}\n"
                    context_snippet = field_answer.strip()
                    # Get the citation, if present
                    if best.get("policy") or best.get("reference_policy"):
                        citation_val = best.get("policy") or best.get("reference_policy")
                        found_citation = f"[Citation: {citation_val}]"
                        context_snippet += f"\n\n{found_citation}"
                else:
                    # No result found; fallback context
                    context_snippet = (
                        "No specific IHWAP rule found. Please consult your agency supervisor or the IHWAP Operations Manual."
                    )

                try:
                    # --- System prompt: always short, field-ready, must cite if present ---
                    system_prompt = (
                        "You are Scout, the IHWAP 2026 compliance assistant for Weatherization staff.\n"
                        "Your job is to provide direct, field-ready answers based on the provided rule context, with exact code or policy citations when available.\n"
                        "Always prioritize this order: Health & Safety > Structure > Energy Efficiency.\n"
                        "When you answer, use this format:\n"
                        "- Brief summary of the IHWAP requirement or rule\n"
                        "- List exact field actions required, using clear bullet points\n"
                        "- End with [Citation: ...] if present — always, and only from the reference context\n"
                        "Keep answers short and to the point — avoid fluff, never speculate.\n"
                        "If you don’t know, say so and suggest asking a supervisor or consulting the IHWAP manual.\n"
                        f"\nReference context:\n{context_snippet}\n"
                    )

                    completion = openai.ChatCompletion.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": system_prompt},
                        ]
                        + session["chat_history"],
                        max_tokens=500,
                    )
                    assistant_reply_raw = completion.choices[0].message["content"]
                    # Guarantee citation is appended if found (extra-safe)
                    if found_citation and found_citation not in assistant_reply_raw:
                        assistant_reply_raw = assistant_reply_raw.rstrip() + "\n\n" + found_citation
                    assistant_reply = markdown.markdown(
                        assistant_reply_raw,
                        extensions=['extra'],
                        output_format='html5'
                    )
                except Exception as e:
                    assistant_reply = f"<pre>Error: {e}</pre>"

                session["chat_history"].append({"role": "assistant", "content": assistant_reply})
                session.modified = True

                wants_json = (
                    request.is_json
                    or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                    or request.headers.get("Accept", "").startswith("application/json")
                )
                if wants_json:
                    return jsonify({"reply": assistant_reply})
                return redirect(url_for("chat.chat"))

        return render_template("chat.html", chat_history=session.get("chat_history", []))

    @chat_bp.route("/reset_chat")
    def reset_chat():
        session["chat_history"] = []
        return redirect(url_for("chat.chat"))

    app.register_blueprint(chat_bp)



