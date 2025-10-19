from __future__ import annotations

import os, json, re, csv
from pathlib import Path
from datetime import datetime, timezone
from typing import Final
from threading import RLock

from dotenv import load_dotenv
load_dotenv(override=False)

# ---------- Repo-anchored paths (portable) ----------
BASE_DIR: Final = Path(__file__).resolve().parent
LOG_DIR:   Final = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LEADS_CSV:       Final = LOG_DIR / "leads.csv"
LEADS_JSONL:     Final = LOG_DIR / "leads.jsonl"
FEEDBACK_JSONL:  Final = LOG_DIR / "feedback.jsonl"

EMAIL_RE:  Final = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_WRITE_LOCK = RLock()  # shared lock for all log writes

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _clean(s: str, /, max_len: int = 800) -> str:
    s = (s or "").strip().replace("\r", " ").replace("\n", " ")
    return (s[: max_len - 1] + "…") if len(s) > max_len else s

def _append_jsonl(path: Path, obj: dict) -> None:
    """
    Append a JSON line to 'path' with flush + fsync to avoid buffering surprises
    when Gradio threads write quickly one after another.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())

# ---------- Tools (inlined) ----------
def record_customer_interest(email: str, name: str, message: str) -> str:
    """
    Tool #1 — Save a potential customer's contact so we can follow up.
    Writes CSV and JSONL to ./logs/.
    """
    email   = _clean(email, 200).lower()
    name    = _clean(name, 200)
    message = _clean(message or "General inquiry", 800)

    if not EMAIL_RE.match(email):
        return "Invalid email address."
    if not name:
        return "Please provide a name."

    ts = _utc_iso()
    print(f"[LEAD] {ts} | {email} | {name} | {message}")

    entry = {"timestamp": ts, "email": email, "name": name, "message": message}

    with _WRITE_LOCK:
        # CSV (create header on first write)
        if not LEADS_CSV.exists():
            with LEADS_CSV.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["timestamp", "email", "name", "message"])
                f.flush()
                os.fsync(f.fileno())
        with LEADS_CSV.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([ts, email, name, message])
            f.flush()
            os.fsync(f.fileno())

        # JSONL mirror
        _append_jsonl(LEADS_JSONL, entry)

    return "Lead saved."

def record_feedback(question: str) -> str:
    """
    Tool #2 — Log questions we can't answer with the current business context.
    """
    q = _clean(question, 1000)
    if not q:
        return "Feedback requires a non-empty question."

    ts = _utc_iso()
    print(f"[FEEDBACK] {ts} | {q}")
    entry = {"timestamp": ts, "question": q}

    with _WRITE_LOCK:
        try:
            _append_jsonl(FEEDBACK_JSONL, entry)
            # Helpful trace while you’re validating paths; remove later if you like
            print(f"[FEEDBACK→{FEEDBACK_JSONL}] ok")
            return "Feedback recorded."
        except Exception as e:
            # Ultra-defensive fallback into current working dir
            try:
                fallback = Path.cwd() / "logs" / "feedback.jsonl"
                _append_jsonl(fallback, entry)
                print(f"[FEEDBACK→{fallback}] fallback ok")
                return f"Feedback recorded (fallback path used: {fallback})"
            except Exception as e2:
                return f"Failed to record feedback: {e} | fallback error: {e2}"

# ---------- Business context & prompt ----------
from loader import load_business_context  # your existing loader.py
from pathlib import Path
try:
    from pypdf import PdfReader  # optional
except Exception:
    PdfReader = None

def _read_txt(path: str | Path) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""

def _read_pdf(path: str | Path) -> str:
    if PdfReader is None:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    out = []
    reader = PdfReader(str(p))
    for page in reader.pages:
        out.append(page.extract_text() or "")
    return "\n".join(out).strip()

def load_business_context(
    txt_path: str | Path = Path(__file__).resolve().parent / "me" / "business_summary.txt",
    pdf_path: str | Path = Path(__file__).resolve().parent / "me" / "about_business.pdf",
) -> str:
    txt = _read_txt(txt_path)
    pdf = _read_pdf(pdf_path)
    return "\n\n".join([s for s in (txt, pdf) if s]).strip()

BUSINESS_CONTEXT = load_business_context()

SYSTEM_PROMPT = f"""
You are the official assistant for **CedarCare Wellness Clinics**. Stay strictly in character.

SOURCE OF TRUTH
- Use ONLY the content in `business_summary.txt` (and `about_business.pdf` when available).
- If a user asks for information that is missing/unclear in these docs, CALL the tool `record_feedback` with the exact user question and then reply briefly that you'll pass this to the team.
- Do not invent details, prices, policies, or locations not present in the docs.

LEAD CAPTURE (VIA CHAT ONLY)
- If the user shows buying intent (pricing, booking, quote, demo, appointment), FIRST ask politely for their **name** and **email** if missing.
- After you have both name and email, CALL `record_customer_interest` with: email, name, and a short "message" summarizing their request (e.g., "Pricing for teleconsult").
- Acknowledge that you saved their details and state the next step.

TONE & STYLE
- Be warm, clear, and concise. Prefer short paragraphs or bullets.
- If you’re unsure, say so and call `record_feedback`.

HEALTH & SAFETY
- You are not diagnosing. Offer general guidance from the docs and suggest contacting a clinician when appropriate.
- For urgent/severe symptoms: “If this is an emergency, please contact local emergency services immediately.”

BUSINESS KNOWLEDGE:
{BUSINESS_CONTEXT}
""".strip()

# ---------- Tool spec & dispatch ----------
TOOL_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "record_customer_interest",
            "description": "Save a potential customer's contact to follow up.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type":"string","description":"Customer email"},
                    "name": {"type":"string","description":"Customer full name"},
                    "message": {"type":"string","description":"Short summary of request"},
                },
                "required": ["email","name","message"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_feedback",
            "description": "Log a question we cannot answer with the current business context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type":"string","description":"Exact user question we couldn't answer"},
                },
                "required": ["question"],
                "additionalProperties": False,
            },
        },
    },
]

def _dispatch_tool(name, args):
    if isinstance(args, str):
        try:
            args = json.loads(args) if args else {}
        except Exception:
            args = {}
    elif not isinstance(args, dict):
        args = {}

    try:
        if name == "record_customer_interest":
            return record_customer_interest(**args)
        if name == "record_feedback":
            return record_feedback(**args)
        return f"Unknown tool: {name}"
    except TypeError as e:
        return f"Tool '{name}' argument error: {e}"
    except Exception as e:
        return f"Tool '{name}' failed: {e}"

# ---------- Provider check ----------
def _provider_ready():
    k = (os.getenv("OPENAI_API_KEY") or "").strip()
    return (k.startswith(("sk-", "sk-proj-")) and len(k) > 40)

_SETUP_MSG = "(Setup needed) No API key visible to this Python process. Set OPENAI_API_KEY and re-run."

# ---------- History adapter ----------
def _tuplize(history):
    if not history:
        return []
    first = history[0]
    if isinstance(first, (list, tuple)) and len(first) == 2:
        return [(str(u or ""), str(a or "")) for (u, a) in history]
    pairs, last_user = [], None
    for m in history:
        role, content = m.get("role"), m.get("content", "")
        if role == "user":
            last_user = content
        elif role == "assistant":
            pairs.append((last_user or "", content))
            last_user = None
    return pairs

# ---------- Main agent ----------
def run_agent(user_text: str, history=None) -> str:
    if not _provider_ready():
        return _SETUP_MSG
    try:
        from openai import OpenAI
        client = OpenAI()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for (u, a) in _tuplize(history):
            if u:
                messages.append({"role": "user", "content": u})
            if a:
                messages.append({"role": "assistant", "content": a})
        messages.append({"role": "user", "content": user_text})

        # First turn
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SPEC,
            tool_choice="auto",
            temperature=0.3,
        )
        msg = resp.choices[0].message

        # Tool calls?
        if getattr(msg, "tool_calls", None):
            messages.append({
                "role": "assistant",
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                result = _dispatch_tool(tc.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": result,
                })
            # Final answer after tools
            final = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
            )
            return final.choices[0].message.content or "(no response)"

        return msg.content or "(no response)"

    except Exception as e:
        return f"(Agent error) {type(e).__name__}: {e}"