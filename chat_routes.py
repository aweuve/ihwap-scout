# chat_routes.py
"""
IHWAP Scout — Chat routes (WX-only + FAAIE-first + safe LLM helper)

- Smalltalk/out-of-scope → suggestions (no decision).
- FAAIE match → deterministic Decision/Sequence/Verify/Docs/Citation card.
- LLM is helper only: explains matched rule or suggests topics on a miss.
- Keeps your existing 'search_policy' pattern if provided; otherwise uses a
  simple internal mapping via logic_index.json.

Env:
  OPENAI_API_KEY   (required for LLM helper)
  LLM_MODEL        (default: gpt-4o-mini)
  LLM_MAXTOK       (default: 320)
"""

from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template, current_app
import openai
import markdown
import bleach
import json
import os
from typing import Callable, List, Dict, Any, Optional

# ---------- Config ----------

openai.api_key = os.getenv("OPENAI_API_KEY")
_LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
_LLM_MAXTOK = int(os.getenv("LLM_MAXTOK", "320"))

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

def _tokens(s: str) -> List[str]:
    return [t for t in _normalize(s).split() if len(t) >= 3]

def _is_smalltalk(q: str) -> bool:
    q = (q or "").strip().lower()
    if not q:
        return True
    if q in {"hi","hello","hey","ok","okay","thanks","thank you","yo","lol","moo","?","??","???"}:
        return True
    toks = _tokens(q)
    return (len(toks) < 2) and (q not in {"t&p","co","gfci","afci","wx+"})

def _in_scope(q: str) -> bool:
    return bool(set(_tokens(q)) & _IN_SCOPE)

def _render_suggestions_html(message: str, items: List[str]) -> str:
    lis = "".join(f"<li>{bleach.clean(i)}</li>" for i in items)
    return f"<p>{bleach.clean(message)}</p><ul>{lis}</ul>"

# ---------- FAAIE card renderer ----------

def _render_decision_card(rule: Dict[str, Any]) -> str:
    """
    Deterministic FAAIE card (no model text). Supports v1/v2 fields.
    """
    decision = rule.get("display_decision") or rule.get("decision_code") or rule.get("answer") or "Decision"
    sequence = rule.get("sequence") or rule.get("actions") or ([] if not rule.get("action_item") else [rule.get("action_item")])
    verify = rule.get("verify") or []
    docs = rule.get("documentation") or []
    cite = rule.get("reference_policy") or rule.get("policy") or ""
    funding = rule.get("funding_source") or "H&S"

    def bullets(items):
        if not items: return "<ul></ul>"
        return "<ul>" + "".join(f"<li>{bleach.clean(str(i))}</li>" for i in items) + "</ul>"

    parts = []
    parts.append(
        f"<p><strong>Decision:</strong> {bleach.clean(decision)} "
        f"<span style='border:1px solid #ddd;border-radius:8px;padding:1px 6px;margin-left:6px;font-size:12px;opacity:.8'>{bleach.clean(funding)}</span></p>"
    )
    if sequence: parts.append("<p><strong>Sequence:</strong></p>" + bullets(sequence))
    if verify:   parts.append("<p><strong>Verify:</strong></p>" + bullets(verify))
    if docs:     parts.append("<p><strong>Documentation:</strong></p>" + bullets(docs))
    if cite:     parts.append(f"<p><em>[Citation: {bleach.clean(cite)}]</em></p>")
    return "\n".join(parts)

# ---------- Safe LLM helpers (explain/suggest only) ----------

_SYSTEM_WX_ONLY = (
    "You are Scout for IHWAP weatherization. Scope: combustion safety, HVAC/water heaters, electrical (GFCI/AFCI), "
    "shell/air sealing, attics/crawls/basements, ventilation, dryer ducts, admin (landlord auth, DOE Readiness, WX+). "
    "Priorities: (1) Health & Safety, (2) Protect home, (3) Energy. "
    "When a FAAIE rule is provided, you may EXPLAIN briefly but MUST NOT change the decision/steps or invent citations. "
    "If no rule is provided, DO NOT output any Decision/Sequence/Verify/Docs—only suggestions or a brief guiding note. "
    "Be concise, professional, and actionable. No chit-chat or jokes."
)

def _llm_explain_rule(user_q: str, rule_for_llm: Dict[str, Any]) -> Optional[str]:
    """
    Return short HTML explanation; never a decision.
    """
    if not openai.api_key:
        return None
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

def _llm_suggest(user_q: str) -> Dict[str, Any]:
    """
    Return {'message': str, 'suggestions': [...]}; never a decision.
    """
    if not openai.api_key:
        return {"message":"No direct FAAIE match. Try one of the suggestions below.", "suggestions": _SUGGESTIONS}
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

# ---------- Optional internal search_policy fallback ----------

def _fallback_search_policy_factory() -> Callable[[str], List[Dict[str, Any]]]:
    """
    If the app doesn't inject a search_policy, use a simple key map that
    reads a path from logic_index.json and returns triggers from that file.
    """
    logic_index = None
    try:
        with open("logic_index.json", "r", encoding="utf-8") as f:
            logic_index = json.load(f)
    except Exception:
        pass

    key_map = {
        "tankless": ["faaie", "HVAC", "water_heater", "tankless"],
        "power vent": ["faaie", "HVAC", "water_heater", "power_vent"],
        "electric water heater": ["faaie", "HVAC", "water_heater", "electric"],
        "water heater": ["faaie", "HVAC", "water_heater", "health_and_safety"],
        "co": ["faaie", "HVAC", "water_heater", "combustion_safety"],
        "boiler": ["faaie", "HVAC", "boiler", "health_and_safety"],
        "crawlspace": ["faaie", "foundations", "crawlspace"],
        "ptac": ["faaie","HVAC","air_conditioning","IHWAP_context"],
        "mini split": ["faaie","HVAC","air_conditioning","IHWAP_context"],
        "mixing valve": ["faaie","HVAC","water_heater","health_and_safety"],
        "t&p": ["faaie","HVAC","water_heater","health_and_safety"],
        "gfci": ["faaie","health_and_safety","electrical"],
        "knob and tube": ["faaie","health_and_safety","electrical"],
        "sump": ["faaie","foundations","basement","scopes"],
    }

    def _search(user_input: str) -> List[Dict[str, Any]]:
        if not logic_index:
            return []
        query = (user_input or "").lower()
        for keyword, keys in key_map.items():
            if keyword in query:
                try:
                    node = logic_index
                    for k in keys:
                        node = node[k]
                    with open(node, "r", encoding="utf-8") as f:
                        logic = json.load(f)
                    return logic.get("triggers", [])
                except Exception as e:
                    current_app.logger.warning({"event":"search_policy_error","kw":keyword,"err":str(e)})
                    return []
        return []

    return _search

# ---------- Blueprint init ----------

def init_chat_routes(app, search_policy: Optional[Callable[[str], List[Dict[str, Any]]]] = None):
    chat_bp = Blueprint('chat', __name__)

    # use injected search_policy if provided; otherwise fallback
    sp = search_policy or _fallback_search_policy_factory()

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
                # store sanitized user text for UI
                session["chat_history"].append({"role": "user", "content": bleach.clean(user_msg)})
                session.modified = True

                # --- Guardrails (no model) ---
                if _is_smalltalk(user_msg):
                    assistant_reply = _render_suggestions_html("Scout is weatherization-only. Try one of these:", _SUGGESTIONS)
                    session["chat_history"].append({"role": "assistant", "content": assistant_reply})
                    session.modif
