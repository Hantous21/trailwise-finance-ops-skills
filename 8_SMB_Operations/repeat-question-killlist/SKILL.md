---
name: repeat-question-killlist
description: Identify customer questions that waste the most staff time and produce a killlist pack (canonical answers, channel of truth, macros) that permanently reduces repeats. Use when inbox/chat is the same questions forever, onboarding confuses buyers, after-hours pings never stop, or support costs rise without sales growth.
---

# Repeat Question Killlist

SMBs bleed hours on **identical questions** across five channels. Build a **killlist**, write each answer **once**, place it on a **channel of truth**, and plan **deflection with dignity**.

**Leading words:** killlist · channel of truth · answer once · deflection with dignity

## Workflow

1. **Export intents** as CSV (see `fixtures/input/intents.csv`):
   `intent,example,volume,minutes_per_answer,wrong_answer_risk,current_home,gap,tag`
2. **Run** the engine:
   ```bash
   python3 scripts/repeat_question_killlist.py fixtures/input/intents.csv --top 10 --json out.json
   ```
3. **Rank** by `score = volume × minutes_per_answer × wrong_answer_risk` (risk clamped 1–5). Higher = kill first.
4. **Answer once** — short (SMS), medium (email), long (FAQ) for each killlist intent. Include escalate-when.
5. **Channel of truth + dignity** — one primary home per intent; no hostile-thread deflection; measure volume next 30 days.

## Controls

- No fake guarantees; keep policy-accurate dates, fees, returns.
- Hostile/angry threads are not deflection targets — route to a human.
- Prefer fixing product/UX confusion over a longer FAQ when the root is design.
- Policy changes hit the channel of truth first.

## Deliverables

1. Ranked killlist (`out.json`)
2. Canonical answers (short/medium/long)
3. Channel-of-truth map
4. Macro/chatbot snippets
5. Hours-in-top metric for live-answer cost

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — customer-ops automation for SMBs without turning them into a call center.
