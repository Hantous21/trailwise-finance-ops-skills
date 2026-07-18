---
name: revenue-ghost-hunter
description: Recover silent revenue from dead quotes, unanswered proposals, stalled jobs, and unfinished contracts. Use when the pipeline looks empty but quotes were sent, proposals went quiet, follow-ups died, deposits were never collected, or the owner says work "should have closed."
---

# Revenue Ghost Hunter

Small businesses often do not lack leads — they **lose finished pursuit work that never got a last chase**. This skill builds a **ghost ledger**, ranks recovery attractiveness with **honest probability**, and drafts **owner-safe scripts**. Distinct from `ar-collections-automation` (invoices already billed) — this is pre-invoice revenue recovery.

**Leading words:** ghost ledger · last-touch gaps · honest probability · owner-safe scripts

## Workflow

1. **Export** ghosts as CSV (see `fixtures/input/ghosts.csv`):
   `who,offer,amount,first_sent,last_touch,channel,status_guess,blocker,reply_warmth,product_fit,effort_to_restart`
2. **Run** the engine:
   ```bash
   python3 scripts/revenue_ghost_hunter.py fixtures/input/ghosts.csv \
       --as-of 2026-07-01 --json out.json
   ```
3. **Inventory economic ghosts** — status_guess only from evidence:
   `no-response | price-stall | competitor | timing | internal-hard-no | unclear`.
   Never invent deals. Engine hard-stops `internal-hard-no` as `do-not-chase`.
4. **Review scored queues** — Hot ≥70, Warm 40–69, Cold <40. Score weights:
   size 30 (vs chaseable max), recency 25, warmth 20, fit 15, effort 10.
5. **Draft owner-safe scripts** per queue (SMS + email + call opener). No fake urgency, no invented discounts. Include **permission to close**.
6. **Publish a 7-day rescue plan** — who, channel, script id, effort minutes, success metric (`reply | meeting | deposit | closed-lost`).

## Controls

- **Honest probability** beats optimism — label residual uncertainty after the score.
- Never auto-send; drafts only unless the user explicitly approves sends.
- Respect opt-out / do-not-contact language.
- If data is thin, ask for 5 sample deals instead of hallucinating a pipeline.
- Size scale ignores `do-not-chase` rows so a huge killed deal cannot distort ranks.

## Deliverables

1. Engine report (`out.json`) + ghost ledger table
2. Ranked queues + $ at risk (chaseable only)
3. Warm/hot/cold scripts
4. 7-day rescue plan
5. Process fix: every open item must have a next action + date

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — recovery systems and AI follow-up for SMBs.
