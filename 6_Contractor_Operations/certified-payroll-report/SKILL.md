---
name: certified-payroll-report
description: Build WH-347-style certified payroll from timecards and a Davis-Bacon wage determination; flag underpayment with restitution owed. Use when submitting weekly certified payroll on a prevailing-wage job, when reconciling actual paid rates to the wage determination, or when preparing the Statement of Compliance.
---

# Certified Payroll Report (WH-347)

## Overview

Weekly certified payroll per employee. Each row computes straight-time and
overtime hours, gross wages (overtime on the base rate only, fringe owed on
all hours at straight rate — Davis-Bacon / CWHSSA), and a compliance check
against the prevailing wage determination. Reports total gross and
exceptions (underpaid employees and employees with a classification not
listed in the determination).

## Workflow

1. **Export** timecards (`timecards.csv`) and the wage determination
   (`wage_determination.csv`) for the project.
2. **Run** the script:
   ```bash
   python3 scripts/certified_payroll_report.py \
       fixtures/input/timecards.csv \
       fixtures/input/wage_determination.csv \
       --json out.json
   ```
3. **Review** `out.json` — every underpaid row needs a restitution check
   before the Statement of Compliance is signed.

## Controls

- Overtime after 40 hours at 1.5× the base rate; the fringe rate does not get the multiplier but is owed on every hour.
- Total paid (base + fringe) must meet the wage determination's total for the classification — cash can cover fringe, but the sum rules.
- Never guess a classification. A missing determination line is a stop-and-ask, not a default.
- Compute restitution before submission; a signed Statement of Compliance with known underpayment is a False Claims Act problem, not a bookkeeping error.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
