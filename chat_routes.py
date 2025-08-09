# chat_routes.py
from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template, current_app
import openai
import markdown
import bleach
import json
import os

# ---------- WX-only guardrails & suggestions ----------

_SUGGESTIONS = [
    "T&P discharge uphill",
    "Worst-case depressurization spillage",
    "Landlord authorization missing",
    "Dryer uses plastic flex into crawlspace",
]

_IN_SCOPE = {
    "weatherization","ihwap","sws","health","safety","hazard","combustion","spillage","backdraft","co",
    "draft","caz","furnace","boiler","water","heater","t&p","discharge","vent","flue","liner",
    "electrical","gfci","afci","splice","panel","egress","smoke","alarm",
    "attic","insulation","air","sealing","seal","bypass","hatch",
    "crawlspace","basement","moisture","leak","mold","sump","drain","vapor","barrier",
    "dryer","duct","vent","bath","fan","range","hood",
    "landlord","authorization","owner","permission","wx+","readiness","doe","deferral","hold"
}

def _normalize(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() or ch in " &/-" else " " for ch in (s or "")).strip()

def _tokens(s: str):
    return [t for t in _normalize(s).split() if len(t) >= 3]

def _is_smalltalk(q: str) -> bool:
    q = (q or "").strip().lower()
    if not q:
        return True
    if q in {"hi","hello","hey","ok","okay","thanks","thank you","yo","lol","moo","?","??","???"}:
        return True
    toks = _tokens(q)
    if len(toks) < 2 and q not in {"t&p","co","gfci","afci","wx+"}:
        return True
    return False

def _in_scope(q: str) -> bool:
    return bool(set(_tokens(q)) & _IN_SCOPE)

def _render_suggestions_html(message: str, items: list) -> str:
    lis = "".join(f"<li>{bleach.clean(i)}</li>" for i in items)
    return f"<p>{bleach.clean(message)}</p><ul>{lis}</ul>"

def _render_decision_card(rule: dict) -> str:
    """Deterministic FAAIE card (no model text). Handles both legacy and v2 fields."""
    # v2 fields
    decision = rule.get("display_decision") or rule.get("decision_code") or rule.get("answer") or "Decision"
    seq = rule.get("sequence") or rule.get("actions") or ([] if not rule.get("action_item") else [rule.get("action_item")])
    ver = rule.get("verify") or []
    docs = rule.get("documentation") or []
    cite = rule.get("reference_policy") or rule.get("policy") or ""
    funding = rule.get("funding_source") or "H&S"

    def bullets(items):
        if not items: return "<ul></ul>"
        return "<ul>" + "".join(f"<li>{bleach.clean(str(i))}</li>" for i in items) + "</ul>"

    block = []
    block.append(
        f"<p><strong>Decision:</strong> {bleach.clean(decision)} "
        f"<span style='border:1px solid #ddd;border-radius:8px;padding:1px 6px;margin-left:6px;font-size:12px;opacity:.8'>{bleach.clean(funding)}</span></p>"
    )
    if seq:  block.append("<p><strong>Sequence:</strong></p>" + bullets(seq))
    if ver:  block.append("<p><strong>Verify:</strong></p>" + bullets(ver))
    if docs: block.append("<p><strong>Documentation:</strong></p>" + bullets(docs))
    if cite: block.append(f"<p><em>[Citation: {bleach.clean(cite)}]</em></p>")
    return "\n".join(block)

# ---------- Safe LLM helpers (explain/suggest only) ----------

openai.api_key = os.getenv("OPENAI_API_KEY")
_LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
_LLM_MAXTOK = int(os.getenv("LLM_MAXTOK", "320"))

_SYSTEM_WX_ONLY = (
    "You are Scout for IHWAP weatherization. Scope: combustion safety, HVAC/water heaters, electrical (GFCI/AFCI), "
    "shell/air sealing, attics/crawls/basements, ventilation, dryer ducts, admin (landlord auth, DOE Readiness, WX+). "
    "Priorities: (1) Health & Safety, (2) Protect home, (3) Energy. "
    "When a FAAIE rule is provided, you may EXPLAIN briefly but MUST NOT change the decision/steps or invent citations. "
    "If no rule is provided, DO NOT output any Decision/Sequence/Verify/Docs—only suggestions or a brief guiding note. "
    "Be concise, professional, and actionable. No chit-chat or jokes."
)

def _llm_explain_rule(user_q: str, rule_for_llm: dict) -> str or None:
    """Return short HTML explanation; never a decision."""
    try:
        prompt = (
            "User asked: " + user_q + "\n\n"
            "Explain in 2–4 sentences why the following rule applies and what to watch out for in the field. "
            "If helpful, end with ONE clarifying question on a new line.\n\n"
            "Rule (do NOT alter this):\n" + json.dumps(rule_for_llm, ensure_ascii=False)
        )
        r = openai.ChatCompletion.create(
            model=_LLM_MODEL,
            messages=[{"role":"system","content":_SYSTEM_WX_ONLY},
                      {"role":"user","content":prompt}],
            max_tokens=_LLM_MAXTOK,
            temperature=0.2,
        )
        text = (r.choices[0].message.get("content") or "").strip()
        if not text:
            return None
        html = markdown.markdown(text, extensions=['extra'], output_format='html5')
        return bleach.clean(
            html,
            tags=bleach.sanitizer.ALLOWED_TAGS + ["p","ul","ol","li","code","pre","strong","em","br"],
            strip=True,
        )
    except Exception as ex:
        current_app.logger.warning({"event":"llm_explain_error","err":str(ex)})
        return None

def _llm_suggest(user_q: str) -> dict:
    """Return {'message': str, 'suggestions': [...]}; never a decision."""
    try:
        prompt = (
            "User asked: " + user_q + "\n\n"
            "Task: Stay strictly within weatherization scope. If the request is unrelated, say 'Out of scope for weatherization.' "
            "Otherwise suggest up to 4 concise, specific weatherization topics the user may have meant "
            "(e.g., 'T&P discharge uphill', 'Worst-case depressurization spillage', 'Landlord authorization'). "
            "Return a short guiding sentence, then a short list."
        )
        r = openai.ChatCompletion.create(
            model=_LLM_MODEL,
            messages=[{"role":"system","content":_SYSTEM_WX_ONLY},
                      {"role":"user","content":prompt}],
            max_tokens=_LLM_MAXTOK,
            temperature=0.2,
        )
        text = (r.choices[0].message.get("content") or "").strip()
        lines = [l.strip("-• ").strip() for l in text.split("\n") if l.strip()]
        msg = lines[0] if lines else "No direct FAAIE match. Try one of the suggestions below."
        sugg = [s for s in lines[1:5] if s] or _SUGGESTIONS
        return {"message": msg, "suggestions": sugg}
    except Exception as ex:
        current_app.logger.warning({"event":"llm_suggest_error","err":str(ex)})
        return {"message":"No direct FAAIE match. Try one of the suggestions below.", "suggestions": _SUGGESTIONS}

# ---------- Routes ----------

def init_chat_routes(app, search_policy):
    chat_bp = Blueprint('chat', __name__)

    @chat_bp.route("/chat", methods=["GET", "POST"])
    def chat():
        session.setdefault("chat_history", [])

        if request.method == "POST":
            user_msg = (
                request.form.get("chat_input")
                or request.form.get("prompt")
                or ((request.json or {}).get("prompt") if request.is_json else None)
            )
            user_msg = (user_msg or "").strip()

            if user_msg:
                # store raw user text for UI (sanitized)
                session["chat_history"].append({"role": "user", "content": bleach.clean(user_msg)})
                session.modified = True

                # --- Guardrails ---
                if _is_smalltalk(user_msg):
                    assistant_reply = _render_suggestions_html(
                        "Scout is weatherization-only. Try one of these:",
                        _SUGGESTIONS
                    )
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

                if not _in_scope(user_msg):
                    assistant_reply = _render_suggestions_html(
                        "Out of scope for weatherization. Try one of these:",
                        _SUGGESTIONS
                    )
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

                # --- FAAIE-first (authoritative) ---
                search_results = search_policy(user_msg)

                if search_results:
                    best = search_results[0]
                    # Deterministic decision card
                    card_html = _render_decision_card(best)

                    # Optional: model explanation (cannot alter decision)
                    rule_for_llm = {
                        "trigger": best.get("trigger",""),
                        "decision": best.get("display_decision") or best.get("decision_code",""),
                        "sequence": best.get("sequence", []),
                        "verify": best.get("verify", []),
                        "documentation": best.get("documentation", []),
                        "funding_source": best.get("funding_source",""),
                        "reference_policy": best.get("reference_policy") or best.get("policy",""),
                    }
                    addendum_html = _llm_explain_rule(user_msg, rule_for_llm)
                    if addendum_html:
                        card_html += "<hr style='border:none;border-top:1px solid #eee;margin:10px 0' />" + addendum_html

                    assistant_reply = card_html

                else:
                    # No FAAIE rule → suggestions only (never a Decision)
                    s = _llm_suggest(user_msg)
                    assistant_reply = _render_suggestions_html(s["message"], s["suggestions"])

                # sanitize final HTML
                assistant_reply = bleach.clean(
                    assistant_reply,
                    tags=bleach.sanitizer.ALLOWED_TAGS + ["p","ul","ol","li","code","pre","strong","em","br","hr","span"],
                    attributes={"span": ["style"]},
                    strip=True,
                )

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
