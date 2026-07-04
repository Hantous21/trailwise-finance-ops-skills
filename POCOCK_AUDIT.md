# Trailwise Skills — Pocock Checklist Audit

Matt Pocock's "The Missing Manual" framework: **Trigger → Structure → Steering → Pruning**.

## TL;DR

Two quality tiers in the repo:
- **Good (6 skills)**: `Contractor_Operations/` (5) + `data-quality-check` — 47–52 lines, external scripts, strong leading words, minimal SKILL.md. Already Pocock-compliant.
- **Bad (9 skills)**: `Trailwise_Toolkit/` + `Methodology` + `Automation` + `Advanced` — 177–450 lines, all inline Python/JSON, minimal steering, code-dump anti-pattern.

Plus 3 skills in between (`change-order-tracker`, `data-source-audit`, `n8n-invoice-approval`).

## Top 5 Skills Needing the Most Work

| Rank | Skill | Lines | Core Problem |
|------|-------|-------|--------------|
| 1 | `ar-collections-automation` | 450 | Largest file; 350 lines inline Python across 5 classes; zero external scripts; no steering |
| 2 | `month-end-close` | 434 | 300 lines inline Python; 35-line reference table embedded in code; no steps/reference split |
| 3 | `payment-app-generator` | 407 | 340 lines inline Python; has good steering words ("Retainage is legal money") but wastes them in 16 KB |
| 4 | `subcontractor-compliance-tracker` | 370 | Identity crisis — labeled `implemented_in: FieldOS` but ships as a skill with 250 lines of inline code |
| 5 | `bank-reconciliation` | 334 | 240 lines inline Python; 3-pass matching logic buried in loops; very high trigger frequency = worst context-cost/value ratio |

## Cross-Cutting Patterns

1. **13 of 18 skills inline full Python/JSON code in SKILL.md.** Only the 5 `Contractor_Operations` + `data-quality-check` skills use external `scripts/` dirs. The 9 "big" skills inline everything — Pocock's exact anti-pattern ("giant code dumps").

2. **The "One-Shot vs Ongoing" upsell block is copy-pasted in all 18 files** (~14 lines each = ~250 lines of pure marketing sediment). Deleting all would change zero agent behavior.

3. **12 of 18 skills have zero explicit leading words.** Only `Contractor_Operations` (5) + `payment-app-generator` + `change-order-tracker` + `data-quality-check` have memorable steering phrases.

4. **None has a formal STEPS (numbered procedure) + REFERENCE (templates/supporting info) split.** `data-source-audit` comes closest with 4 named steps but inlines code after each.

5. **No skill has `templates/` or `references/` directories.** Branch-specific reference (CSV formats, n8n JSON, output examples) is all inline.

6. **`change-order-tracker` has a dangling import** (`from scripts.main import ChangeOrderManager`) with no `scripts/` dir in its folder.

7. **`invoice-reconciliation` has a latent bug** at line 155: `receipt_item` referenced but never defined — `NameError` when a receipt exists.

8. **`n8n-invoice-approval` hardcodes** `claude-sonnet-4-20250514` and is missing `depends_on: invoice-reconciliation`.

## Trigger Recommendation

**Default to model-invoked, but move the 9 big inline-code skills to user-invoked now.**

- The 6 good skills (≤52 lines, external scripts, precise descriptions) are good model-invoked citizens — low context cost, narrow triggers.
- The 9 big skills (7–18 KB each) are too expensive for model-invoked. If all 18 descriptions sit in context, that's ~85 KB of context pointers. If the agent auto-loads `ar-collections-automation` on every "invoice" query, it pays 17 KB for a code dump it probably doesn't need.
- **Action**: Add `disable model invocation: true` to the 9 big skills. Once externalized and trimmed to ~60–80 lines, they can re-qualify for model-invoked.

---

## Per-Skill Findings (all 18)

### ar-collections-automation (450 lines, ~17 KB)
- **Trigger**: Model-invoked. 17 KB inline = catastrophic context cost if auto-loaded on AR queries.
- **Structure**: No steps/reference split. ~350 of 450 lines are inline Python (5 classes). No `scripts/` dir. Dunning-email logic is branch-specific (only "send dunning" path).
- **Steering**: No leading words. Dunning-tier thresholds (1–15 friendly, 16–45 firm, 46–90 final) buried in code.
- **Pruning**: Upsell block duplicated. Integration section = marketing sediment. Edge Cases (7 items) only useful reference.
- **Top fix**: Move all Python to `scripts/ar_collections.py`; cut SKILL.md to ~60 lines (overview + 3-step workflow + dunning schedule table + pointer).

### month-end-close (434 lines, ~18 KB)
- **Trigger**: Model-invoked. "Close checklist" is high-frequency — would auto-fire constantly.
- **Structure**: No split. ~300 lines inline Python (4 managers). `DEFAULT_TASKS` list (35 lines) is reference data belonging in `templates/close_checklist.yaml`.
- **Steering**: None. No leading words for materiality thresholds or sign-off sequencing.
- **Pruning**: Upsell block. Integration section is a 5-line ad.
- **Top fix**: Extract `DEFAULT_TASKS` to `references/close_checklist_template.yaml`; move classes to `scripts/`; cut SKILL.md to ~70 lines.

### payment-app-generator (407 lines, ~16 KB)
- **Trigger**: Model-invoked. Description narrowly scoped to AIA G702/G703 (good precision) but 16 KB inline.
- **Structure**: No split. ~340 lines inline Python (4 classes). CSV input-format + G702 output examples only needed on "format/export" branch.
- **Steering**: **"Retainage is legal money"** — excellent leading word (line 33). Also "Never auto-submit to client." These work. Rest is vague prose.
- **Pruning**: Upsell block. Integration mentions reportlab but code never imports it. Output example (25 lines) valuable but could be external.
- **Top fix**: Externalize Python to `scripts/payment_app.py`; keep Safety & Controls + steering words + 4-step workflow.

### subcontractor-compliance-tracker (370 lines, ~15 KB)
- **Trigger**: Model-invoked. Has `implemented_in: "FieldOS"` — unclear if it should be model-invoked at all.
- **Structure**: No split. ~250 lines inline Python (4 classes). "Real-World Migration Path" (8 lines) is the closest thing to STEPS.
- **Steering**: None. The 30/15/5 reminder cadence should be a leading rule ("30-15-5 cadence") but isn't.
- **Pruning**: Upsell block. Reddit quote (4 lines) = marketing sediment. CSV format duplicated between code and prose.
- **Top fix**: If this is a FieldOS spec, label it and make user-invoked. Otherwise, externalize code and cut to ~60 lines.

### bank-reconciliation (334 lines, ~15 KB)
- **Trigger**: Model-invoked. "bank reconciliation" is extremely high-frequency — worst context-cost/value ratio.
- **Structure**: No split. ~240 lines inline Python (3-pass matching engine). `_description_similarity` method is implementation detail the agent never needs.
- **Steering**: None. 3-pass matching logic (exact → high-confidence → low-confidence) should be a stated rule, not buried in loops.
- **Pruning**: Upsell block. Input CSV examples (15 lines) are branch-specific.
- **Top fix**: Externalize reconciler to `scripts/bank_reconciliation.py`; state 3-pass matching rule as a leading word.

### invoice-reconciliation (304 lines, ~12 KB)
- **Trigger**: Model-invoked. Same context-cost issue. **Latent bug**: line 155 references `receipt_item` (never defined) — `NameError` when receipt exists.
- **Structure**: No split. ~200 lines inline Python. Tolerance thresholds (2% price, 5% qty, $500 auto-approve) embedded in constructor defaults — good data, wrong location.
- **Steering**: None. Three-way-match concept should be a leading word ("three-way match: invoice ↔ PO ↔ receipt").
- **Pruning**: Upsell block. The bug is both a code defect and a steering failure.
- **Top fix**: Fix `receipt_item` bug, externalize code, add "three-way match" as leading phrase.

### cash-flow-forecaster (287 lines, ~11 KB)
- **Trigger**: Model-invoked. "cash flow" is high-frequency.
- **Structure**: No split. ~200 lines inline Python. `scenario_early_payment` method is a distinct branch (extraction candidate).
- **Steering**: None. "S-curve" appears but isn't defined as a steering concept. Shortfall recommendation logic buried in private method.
- **Pruning**: Upsell block. No edge-cases section at all (unusual for this repo).
- **Top fix**: Externalize code; add edge cases; state shortfall-detection rule as a leading word.

### cost-overrun-prediction (280 lines, ~11 KB)
- **Trigger**: Model-invoked. Narrowly scoped to ML prediction — reasonable trigger, but 11 KB is heavy for a skill requiring 20+ completed projects.
- **Structure**: No split. ~190 lines inline Python (sklearn). Feature-importance table and training-data requirements are excellent reference but only needed on "train" branch, not "predict" branch.
- **Steering**: Partial. "20%+ complete for prediction" is a threshold buried in prose. Feature-importance table is good implicit steering.
- **Pruning**: Upsell block. `prepare_features` method duplicates logic from `train` — DRY violation within the file.
- **Top fix**: Split into two branches (train vs predict) or two skills; externalize ML code to `scripts/`.

### n8n-payment-reminders (253 lines, ~10 KB)
- **Trigger**: Model-invoked. `depends_on: "ar-collections-automation"` — only skill with explicit dependency. Good.
- **Structure**: No split. ~140 lines inline JSON (n8n workflow definition). Not executable Python — it's a deployment artifact. Should be `workflows/payment_reminders.json`.
- **Steering**: Partial. "Test with internal email addresses first" and auto-send/approval matrix are good controls.
- **Pruning**: Upsell block. JSON has escaped newlines making it hard to read.
- **Top fix**: Move n8n JSON to `workflows/payment_reminders.json`; keep SKILL.md as architecture + safety rules + config table.

### budget-variance-tracker (252 lines, ~9 KB)
- **Trigger**: Model-invoked. "budget vs actual" is extremely common — would fire on nearly every project finance query.
- **Structure**: No split. ~170 lines inline Python. Alert thresholds (50/75/90/95%) embedded in code. Alert-routing table is branch-specific.
- **Steering**: None. Burn-rate forecasting formula (`spent / %complete = projected total`) should be a leading word ("burn-rate projection").
- **Pruning**: Upsell block. No edge-cases handling for the 5 listed scenarios.
- **Top fix**: Externalize code; state "burn-rate projection" as core steering concept; move alert routing to reference table.

### change-order-tracker (235 lines, ~8 KB)
- **Trigger**: Model-invoked. Quick Start imports `from scripts.main import ChangeOrderManager` — **but no `scripts/` dir exists**. Dangling import.
- **Structure**: Hybrid — only "big" skill that attempts external scripts. But then inlines 75 lines of data-model Python anyway. Classification rules and severity scoring are clean tables.
- **Steering**: **Strong**. "Never auto-approve," "Never auto-modify the budget," "Dispute packets are drafts" — 5 explicit safety controls. Best steering in the repo.
- **Pruning**: Upsell block (variant wording). Dangling import is a bug or points to non-existent module.
- **Top fix**: Resolve `scripts.main` import; remove inlined data model (should live in the script).

### data-source-audit (177 lines, ~7 KB)
- **Trigger**: Model-invoked. Scoped to "audit all financial data sources" — reasonably precise.
- **Structure**: Partial split. Has 4 named steps (Inventory, Map Flows, Identify Silos, Score) — closest to Pocock's STEPS format among big skills. But each step followed by inline Python. `AuditReport` class only needed on "score" branch.
- **Steering**: None. "Each arrow is a manual touch point" is the closest thing — good but isolated.
- **Pruning**: Upsell block. Real-world example (8 lines) = marketing-flavored sediment.
- **Top fix**: Convert 4 steps into numbered STEPS block; externalize Python; keep example as reference.

### n8n-invoice-approval (192 lines, ~6 KB)
- **Trigger**: Model-invoked. No `depends_on` despite being deployment layer for invoice-reconciliation.
- **Structure**: No split. ~110 lines inline JSON. Approval routing table is clean reference. JSON hardcodes `claude-sonnet-4-20250514` — stale/unversioned.
- **Steering**: Partial. "Auto-escalate to backup approver after deadline" is a control but stated only in edge cases.
- **Pruning**: Upsell block. Hardcoded model name will go stale. Missing `depends_on`.
- **Top fix**: Externalize JSON to `workflows/`; add `depends_on: invoice-reconciliation`; parameterize LLM model.

### data-quality-check (47 lines, ~2 KB) ✅
- **Trigger**: Model-invoked. Description is excellent — specifies use case ("preparing reconciliation, forecasting, migration, reporting"). Benchmark skill for the repo.
- **Structure**: **Excellent**. Uses `scripts/data_quality_check.py` (external, 3.5 KB). 5-step workflow + controls + CLI example. Minimal and correct.
- **Steering**: **"Treat unexpected or missing columns as schema drift"**, **"Review whether blanks mean unknown, zero, not applicable, or a true error"** — two strong leading words.
- **Pruning**: Upsell block is the only sediment.
- **Top fix**: Remove upsell block. Already near-ideal.

### daily-field-report (52 lines, ~2 KB) ✅
- **Trigger**: Model-invoked. Well-scoped. External `scripts/daily_field_report.py` (4.9 KB).
- **Structure**: Good. 5-step workflow + controls + code example. Has `agents/openai.yaml` — only skill with agent configs.
- **Steering**: **"Do not manufacture weather, progress, responsibility, or safety facts"**, **"Label responsibility as unknown until confirmed"** — excellent.
- **Pruning**: Upsell block only.
- **Top fix**: Remove upsell block. Already strong.

### submittal-tracker (48 lines, ~2 KB) ✅
- **Trigger**: Model-invoked. Good description. External script.
- **Structure**: Good. 5-step workflow + controls + code example. Clean.
- **Steering**: **"Do not interpret timing risk as contractual responsibility"**, **"Require a human decision before procurement"** — clear.
- **Pruning**: Upsell block only.
- **Top fix**: Remove upsell block. Already strong.

### schedule-delay-analyzer (52 lines, ~2 KB) ✅
- **Trigger**: Model-invoked. Well-scoped. External `scripts/schedule_delay_analyzer.py` (4.9 KB).
- **Structure**: Good. 5-step workflow + model boundaries + code example.
- **Steering**: **"Treat the result as screening analysis, not a forensic delay opinion"**, **"Never write scenario dates back to a live schedule"** — strong.
- **Pruning**: Upsell block only.
- **Top fix**: Remove upsell block. Already strong.

### rfi-management (48 lines, ~2 KB) ✅
- **Trigger**: Model-invoked. Good description. External `scripts/rfi_management.py` (3.9 KB).
- **Structure**: Good. 5-step workflow + controls + code example.
- **Steering**: **"Never treat an unanswered impact field as zero"** — the single best leading word in the entire repo. Also **"Do not infer responsibility, entitlement, or compensability from lateness."**
- **Pruning**: Upsell block only.
- **Top fix**: Remove upsell block. Already strong.
