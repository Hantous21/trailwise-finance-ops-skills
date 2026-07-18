# Audit: Original Flagship Skills (post-merge 5ed46c8)

**Scope:** 11 skills added via PR #6  
**Bar:** Trailwise toolkit standard (SKILL.md + scripts/ + fixtures/ + pytest + controls + leading words) + Pocock 4-point (trigger/structure/steering/pruning)

## Executive summary

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Frontmatter / validator | A | name+description only, `Use when`, folder match, agents/openai.yaml |
| Steering (leading words) | A | Every skill has explicit leading words |
| Controls / safety | A- | Strong; a few placeholders (`$X`/`$Y`) |
| Numbered workflow | A | 5 steps each |
| Deterministic engine | **F** | **0/11 have scripts/** |
| Fixtures | **F** | **0/11 have fixtures/** |
| Tests | **F** | **0/11 have pytest coverage** |
| Input schemas | D | Narrative only; no CSV column contracts |
| Edge-case section | C | Buried in controls, not explicit |
| Effectiveness fully agent-runnable | D+ | Good facilitation playbooks; not push-button analysis |

**Verdict:** Safe as human+agent coaching skills. **Not production-complete** vs retainage / prime-cost / compliance. Highest risk is **hallucinated scores** where formulas are claimed without engines (ghost score, capacity strain, killlist sort, weather band).

## What is good (no bugs of substance)

- Distinct from toolkit twins (documented overlap policy holds).
- Clear when-not-to-use (especially safety, surety honesty, no auto-send).
- Deliverables lists give agents a complete end-state.
- Line count 37–40 → low context cost; no sediment tables.
- Single-line CTA only (Pocock pruning OK).

## Bugs / defects

| ID | Severity | Skill | Issue |
|----|----------|-------|-------|
| B1 | High | All scoring skills | Formula text without `scripts/` → agent improvises numbers |
| B2 | Med | `drawer-truth-close` | Thresholds literally `$X` / `$Y` — not executable defaults |
| B3 | Med | `cash-weather-report` | Weather bands defined; no calc of fixed-cost buffer weeks |
| B4 | Med | `revenue-ghost-hunter` | Weights sum to 100 but answer warmth / product-fit scales undefined |
| B5 | Low | `bid-bond-gate` | Strain 1–5 qualitative only; "fail gate" rule not booleanized |
| B6 | Low | `labor-percent-guard` | No target labor % default or hours formula |
| B7 | Low | Process skills | No sample input artifact → first run needs heavy clarifying |

## Completeness vs mature skill

Mature pattern (`retainage-tracker`):

```
SKILL.md
agents/openai.yaml
scripts/<name>.py
fixtures/input/...
fixtures/expected/...
tests/test_<name>.py
```

Original flagships today:

```
SKILL.md
agents/openai.yaml
```

## Skill-by-skill effectiveness

| Skill | Type | Effective today? | Gap to close |
|-------|------|------------------|--------------|
| revenue-ghost-hunter | Score + scripts | Partial | scoring engine + CSV |
| founder-time-reclaim | Facilitation | Yes (coaching) | template CSV time diary |
| cash-weather-report | Calc + narrative | Partial | buffer/weather engine |
| staff-brain-backup | Facilitation | Yes | interview template file |
| repeat-question-killlist | Rank + write | Partial | ranking engine + sample intents |
| bid-bond-gate | Decision tree | Partial | gate engine |
| food-cost-bleed-map | Attribution | Partial | theoretical vs actual script |
| labor-percent-guard | Schedule economics | Partial | labor% daypart script |
| eighty-six-chain-breaker | Protocol design | Yes (process) | example chain-map CSV |
| guest-recovery-playbook | Protocol design | Yes (process) | severity example bank file |
| drawer-truth-close | Protocol + variance | Partial | spine template + $ defaults |

## Recommended remediation priority

1. **P0** — Engines + fixtures + tests for: `revenue-ghost-hunter`, `cash-weather-report`, `bid-bond-gate`, `food-cost-bleed-map`  
2. **P1** — Defaults + templates: `drawer-truth-close`, `labor-percent-guard`, `repeat-question-killlist`  
3. **P2** — Sample artifacts only: founder-time, staff-brain, 86, guest-recovery  

## Non-claims

- Did not re-audit pre-existing 29 toolkit skills.
- Did not claim human facilitation skills *require* Python to be valuable — only that scoring claims need engines.

## Follow-up

Remediation on branch after this audit (scripts/fixtures/tests + SKILL.md quick-start lines).
