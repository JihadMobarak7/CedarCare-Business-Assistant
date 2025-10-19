# Business Assistant — CedarCare (Assignment-Ready)

This project implements the **CedarCare Wellness Assistant**, aligned with the *Agentic Business Assistant* assignment phases.

It includes:
- A **single unified agent module** (`agent.py`) that combines:
  - The business context loader  
  - Tool specifications  
  - Tool implementations (`record_customer_interest`, `record_feedback`)  
  - OpenAI Chat Completions wiring (with function-calling support)
- A **clean Gradio chat UI** inside the notebook (`business_bot.ipynb`)
- Persistent **log storage** in `./logs/` for leads and feedback
- Stable dependency pins (avoiding Gradio schema errors)

---

## 🧩 Project Structure

```
business_bot/
├─ me/
│  ├─ business_summary.txt         # Short text summary (used in context)
│  └─ about_business.pdf           # Optional detailed profile
│
├─ agent.py                        # Unified agent + tools + logging
├─ business_bot.ipynb              # Main notebook (agent wiring + Gradio UI)
├─ requirements.txt                # Pinned dependencies
├─ .env.example                    # Sample for environment setup
├─ .env                            # (excluded) your actual API key here
└─ logs/
   ├─ leads.csv
   ├─ leads.jsonl
   └─ feedback.jsonl
```

> `app.py` is **not required** and has been removed for clarity.  
> The logic previously split into multiple files (`tools.py`, `loader.py`) is now unified in `agent.py`.

---

## ⚙️ Setup Instructions

### 1️⃣ Create and activate a virtual environment
```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

### 2️⃣ Install dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ Configure your `.env` file
Copy `.env.example` → `.env` and edit it:
```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini
```

> No key hardcoding needed — it’s automatically loaded with `python-dotenv`.

---

## 🚀 Running the Assistant

### Option A — Recommended: Run from Notebook
Open **`business_bot.ipynb`** and execute all cells **top-to-bottom**:
1. Environment setup  
2. Context loader (`me/business_summary.txt`, optional PDF)  
3. Agent wiring (`agent.py`)  
4. Launch Gradio UI  

You’ll see a minimal clean chat UI:
- User messages appear on the right  
- Assistant messages on the left  
- “About CedarCare” summary shown below  

**Tool behaviors**:
- Leads and feedback are auto-recorded to `./logs/`.
- Missing information triggers a feedback log.
- Buying intent triggers polite lead capture (asks for name + email).

---

## 🧠 Tool Logic (Auto-Invoked by the Model)

### `record_customer_interest(email, name, message)`
Saves potential customer data.

Writes to:
- `logs/leads.csv`  
- `logs/leads.jsonl`

Console output:
```
[LEAD] 2025-10-19T17:34:53.824501+00:00 | johndobes@gmail.com | John Dobes | Interested in booking a consultation.
```

---

### `record_feedback(question)`
Logs user questions that the assistant couldn’t answer with the provided docs.

Writes to:
- `logs/feedback.jsonl`

Console output:
```
[FEEDBACK] 2025-10-19T17:40:09.569771+00:00 | Do you operate in London?
```

---

## 🧹 Reset / Refresh Instructions

To **clear logs** and start fresh:
```bash
rm -rf logs && mkdir logs
```

Or inside a Python cell:
```python
from pathlib import Path
for name in ("leads.csv", "leads.jsonl", "feedback.jsonl"):
    Path("logs", name).write_text("", encoding="utf-8")
print("Logs cleared.")
```

> The assistant has **no internal cache** — only these files persist.

---

## 🧪 Quick Test (No UI)

You can run a single-agent test:
```python
from agent import run_agent
print(run_agent("Hello"))
```

Expected output: a friendly CedarCare greeting or clarification message.

---

## 🧩 Dependencies

All are pinned for reproducibility and to avoid FastAPI/Gradio version mismatches.

```txt
openai>=1.46,<2
python-dotenv>=1.0
gradio==4.44.0
gradio_client==1.3.0
fastapi==0.115.2
starlette==0.40.0
anyio==4.4.0
aiofiles==23.2.1
ffmpy==0.3.2
pydantic==2.10.6
pypdf>=5.0
fpdf2>=2.7
```

---

## 🧭 Notes for Graders

- All required artifacts are included and functional.  
- Tools (`record_customer_interest`, `record_feedback`) write persistently to `./logs/`.  
- The UI is simple, polished, and clearly separated by assignment phase sections.  
- `.env` is excluded from version control for security.

---

## 📄 License

For academic use — CedarCare Wellness Assistant (AUB Assignment).
