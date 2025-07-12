# chat_routes.py
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
                search_results = search_policy(user_msg)
                context_snippet = ""
                found_citation = None
                if search_results:
                    for result in search_results[:1]:
                        context_snippet += result["answer"]
                        if result["policy"]:
                            found_citation = f"[Citation: {result['policy']}]"
                            context_snippet += f"\n\n{found_citation}"
                try:
                    system_prompt = (
                        "You are Scout, an IHWAP 2026 assistant for Weatherization staff.\n"
                        "If the reference context includes a '[Citation: ...]' line, you must always include it exactly as written at the end of your answer—no exceptions.\n"
                        "Use action items and field protocol found in the reference context when possible, and cite the real-world policy from [Citation: ...] only (never reference file or section numbers from JSON structure).\n"
                        "If you can't answer directly, say so and suggest next steps.\n\n"
                        f"Reference context:\n{context_snippet}\n\n"
                        "Answer in a friendly, clear, and concise field style. Always finish with [Citation: ...] if present."
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
                    # Guarantee the citation is appended if it was found, even if GPT forgets
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

    app.register_blueprint(chat_bp)

