<h1 align="center">Trailwise Finance Ops Skills</h1>

<p align="center">
  <strong>AI Agent Skills for Construction & Trades Finance Operations</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Skills-16-blue?style=flat-square" alt="Skills">
  <img src="https://img.shields.io/badge/Categories-5-green?style=flat-square" alt="Categories">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="License">
</p>

<p align="center">
  <a href="https://claude.ai/download"><img src="https://img.shields.io/badge/Claude_Code-191919?style=for-the-badge&logo=anthropic&logoColor=white" alt="Claude Code"></a>
  <a href="https://cursor.sh"><img src="https://img.shields.io/badge/Cursor-333333?style=for-the-badge&logo=cursor&logoColor=white" alt="Cursor"></a>
  <a href="https://github.com/features/copilot"><img src="https://img.shields.io/badge/Copilot-24292e?style=for-the-badge&logo=github&logoColor=white" alt="Copilot"></a>
  <a href="https://opencode.ai"><img src="https://img.shields.io/badge/OpenCode-FF6B35?style=for-the-badge&logoColor=white" alt="OpenCode"></a>
</p>

---

## What is this?

A collection of **AI agent skills** for automating finance operations. Built by a 7-year finance ops veteran — starting with construction and trades, expanding to other verticals as patterns emerge.

Each skill is a `SKILL.md` file — structured instructions that an AI coding assistant (Claude Code, Cursor, Copilot) can read and execute. You open a skill folder in your AI assistant, and it helps you implement the solution.

**These skills run one-time analyses.** For ongoing automation — scheduled runs, live dashboards, Slack alerts, multi-project views — use [**FieldOS**](https://trailwiseai.com).

**Finance operations, handled.**

---

## Skills

| Skill | What it does | Folder |
|-------|-------------|--------|
| `subcontractor-compliance-tracker` | Track COIs/licenses, auto-remind before expiry | `1_Trailwise_Toolkit/` |
| `month-end-close` | Close checklist, accruals, variance, roll-forwards | `1_Trailwise_Toolkit/` |
| `bank-reconciliation` | Auto-match bank to ledger, flag unmatched items | `1_Trailwise_Toolkit/` |
| `ar-collections-automation` | AR aging, tiered dunning emails, payment prediction | `1_Trailwise_Toolkit/` |
| `invoice-reconciliation` | Match invoices to POs, flag discrepancies | `1_Trailwise_Toolkit/` |
| `budget-variance-tracker` | Real-time budget vs actual, alert on threshold breach | `1_Trailwise_Toolkit/` |
| `cash-flow-forecaster` | S-curve projections from schedule + cost data | `1_Trailwise_Toolkit/` |
| `data-source-audit` | Audit all data sources, map flows, find silos | `2_Trailwise_Methodology/` |
| `n8n-invoice-approval` | Auto-route invoices for approval via n8n | `3_Trailwise_Automation/` |
| `n8n-payment-reminders` | Payment reminder automation | `3_Trailwise_Automation/` |
| `cost-overrun-prediction` | ML-based cost overrun prediction | `5_Trailwise_Advanced/` |
| `daily-field-report` | Compile daily field reports with labor hours, delays, safety flags | `6_Contractor_Operations/` |
| `rfi-management` | Track RFIs, triage by priority, flag overdue items | `6_Contractor_Operations/` |
| `schedule-delay-analyzer` | CPM critical path analysis, delay simulation, float calculation | `6_Contractor_Operations/` |
| `submittal-tracker` | Track submittals, calculate required dates, flag late items | `6_Contractor_Operations/` |
| `data-quality-check` | Validate CSV data against schema, flag duplicates/blanks/invalid types | `2_Trailwise_Methodology/` |

---

## Free Skill vs FieldOS

These skills are free (MIT). They run **one-time analyses** — you execute them when you need a snapshot.

[**FieldOS**](https://trailwiseai.com) takes the same workflows and runs them **ongoing** — scheduled automatically, with live dashboards, alerts, and multi-project consolidation.

| This skill does (free) | FieldOS does ($49/mo) |
|------------------------|----------------------|
| Runs when you remember | Runs weekly, alerts on Slack |
| Reads a CSV you export | Pulls from QuickBooks automatically |
| Text report output | Live dashboard with charts |
| Single project at a time | Multi-project consolidated view |
| No history | Trend tracking, month-over-month |

**[Start with FieldOS →](https://trailwiseai.com)** · **[Book a consultation →](https://trailwiseai.com/#contact)**

---

## How to Use a Skill

```bash
# 1. Clone this repository
git clone https://github.com/Hantous21/trailwise-finance-ops-skills.git

# 2. Open a skill folder in your AI assistant
cd trailwise-finance-ops-skills/1_Trailwise_Toolkit/invoice-reconciliation/

# 3. The assistant reads SKILL.md and generates the code for you

# 4. Review, adapt to your data, and run
```

---

## Flagship Skills (Contractor Cash & Controls Pack)

These five skills are the core product. They solve the most common finance ops pains for construction and trades firms:

| Skill | Outcome | FieldOS Feature |
|-------|---------|-----------------|
| `invoice-reconciliation` | Stop overpaying vendors — match every invoice to a PO | Invoice reconciliation (automated 3-way match) |
| `budget-variance-tracker` | Catch overruns before they happen — real-time alerts | Budget variance tracker (threshold alerts + trends) |
| `cash-flow-forecaster` | Know your cash position 8+ weeks out — no surprises | Cash flow forecaster (weekly auto-run + multi-project) |
| `subcontractor-compliance-tracker` | Never let a COI expire again — automated reminders | Subcontractor compliance tracker (dashboard + expiry alerts) |
| `ar-collections-automation` | Get paid faster — tiered dunning + late payment prediction | AR collections automation (dunning sequences + aging dashboard) |

---

## Why This Exists

Most small businesses run finance ops on spreadsheets and email. The gap between "free tools" (Excel, Gmail) and "enterprise software" (NetSuite, Procore, SAP) is enormous. No one targets small construction firms, restaurants, or service businesses with practical finance automation.

**Trailwise fills that gap.** These skills encode 7 years of real-world finance ops experience into reusable AI agent instructions.

### The Trailwise Philosophy

1. **Own your data** — No vendor lock-in, no per-seat tax, no cloud-only prison
2. **Understand before automating** — Methodology first, tools second
3. **AI as multiplier** — Your expertise + AI agents = 10x output, not replacement
4. **Construction-first, not construction-only** — Finance ops principles are universal, but domain specificity (AIA pay apps, retainage, lien waivers, WIP, change orders) is the moat. Start vertical, expand later

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python 3.9+** | Most skills use Python scripts |
| **AI Coding Assistant** | Claude Code, Cursor, Copilot, or similar |
| **Basic Python knowledge** | Ability to run scripts and install packages |
| **Your data** | Excel files, CSVs, bank exports, or ERP exports |

Optional for advanced skills:
- Docker (for n8n workflows)
- PostgreSQL or SQLite (for database skills)
- OpenAI/Anthropic API key (for LLM-based skills)

---

## About Trailwise

**Trailwise** is a finance operations agency. We help construction firms and trades businesses streamline their financial workflows — from invoicing to reporting to forecasting. Agency-first, SaaS emerges from client patterns.

**Starting vertical:** Construction & trades (GCs, subcontractors, specialty contractors)
**Expanding to:** Other verticals with similar finance ops pain points

- **Website:** [https://trailwiseai.com](https://trailwiseai.com)
- **Tagline:** Finance operations, handled.
- **Consulting:** Book a session — we install and configure these skills for your business

---

## License

MIT License — free to use, modify, and distribute. No attribution required (but appreciated).
