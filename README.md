<h1 align="center">Trailwise Finance Ops Skills</h1>

<p align="center">
  <strong>AI Agent Skills for Finance Operations Automation</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Skills-50+-blue?style=flat-square" alt="Skills">
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

A collection of **AI agent skills** for automating finance operations in small and mid-size businesses. Built by a 7-year finance ops veteran, not a software company.

### What is a "Skill"?

A skill is a `SKILL.md` file — structured instructions that an AI coding assistant (Claude Code, Cursor, Copilot) can read and execute. Each skill solves a real finance ops problem: what to automate, what code to generate, what edge cases to handle. You open a skill folder in your AI assistant, and it helps you implement the solution.

**Finance operations, handled.**

---

## What Can You Automate?

| Your problem | What the skill does | Skill to run | Folder |
|--------------|---------------------|--------------|--------|
| Subcontractor COIs expiring with no warning | Track COIs/licenses, auto-remind before expiry | `subcontractor-compliance-tracker` | `1_Trailwise_Toolkit/` |
| Invoice reconciliation takes days | Match invoices to POs, flag discrepancies | `invoice-reconciliation` | `1_Trailwise_Toolkit/` |
| Budget overruns discovered too late | Real-time budget vs actual, alert on threshold breach | `budget-variance-tracker` | `1_Trailwise_Toolkit/` |
| Payment applications take hours | Generate AIA-style pay apps from project data | `payment-app-generator` | `1_Trailwise_Toolkit/` |
| Don't know which vendors are overdue | AR aging report with auto-categorization | `ar-aging-report` | `1_Trailwise_Toolkit/` |
| Cash flow is a guessing game | S-curve projections from schedule + cost data | `cash-flow-forecaster` | `1_Trailwise_Toolkit/` |
| Financial data scattered everywhere | Audit all data sources, map flows, find silos | `data-source-audit` | `2_Trailwise_Methodology/` |
| Invoices stuck in email approval | Auto-route invoices for approval via n8n | `n8n-invoice-approval` | `3_Trailwise_Automation/` |
| No idea when vendors need paying | Payment reminder automation | `n8n-payment-reminders` | `3_Trailwise_Automation/` |
| Reports take hours to compile | Auto-generate recurring financial reports | `n8n-recurring-reports` | `3_Trailwise_Automation/` |
| No visibility into financial KPIs | Interactive dashboard from your data | `financial-kpi-dashboard` | `1_Trailwise_Toolkit/` |
| Can't predict which projects will overrun | ML-based cost overrun prediction | `cost-overrun-prediction` | `5_Trailwise_Advanced/` |
| Unusual invoices slip through | Detect invoice anomalies and fraud patterns | `invoice-anomaly-detector` | `5_Trailwise_Advanced/` |

---

## Collection Structure

| Category | What's inside | Skills | Start here if... |
|----------|---------------|--------|------------------|
| **1_Trailwise_Toolkit** | Production-ready tools: reconciliation, budget tracking, pay apps, aging reports | 15 | You need a working tool now |
| **2_Trailwise_Methodology** | Skills mapped to finance ops principles: accrual vs cash, % complete, data quality | 7 | You want to understand the methodology |
| **3_Trailwise_Automation** | n8n/Zapier workflows: invoice approval, payment reminders, recurring reports | 6 | You need workflow automation |
| **4_Trailwise_Documents** | Generate pay apps, lien waivers, financial reports, KPI dashboards | 8 | You need formatted output |
| **5_Trailwise_Advanced** | ML/AI: cost overrun prediction, anomaly detection, vendor risk scoring | 5 | You're ready for predictive analytics |

---

## How to Use a Skill

```bash
# 1. Clone this repository
git clone https://github.com/trailwise/finance-ops-skills.git

# 2. Open a skill folder in your AI assistant
cd finance-ops-skills/1_Trailwise_Toolkit/invoice-reconciliation/

# 3. The assistant reads SKILL.md and generates the code for you

# 4. Review, adapt to your data, and run
```

---

## Implementation Path

| Stage | What you do | Which skills help |
|-------|-------------|-------------------|
| **1. Audit** | List all financial data sources (Excel, QuickBooks, ERP, bank, email) | `data-source-audit`, `data-silo-detection` |
| **2. Organize** | Classify your data, validate quality, map workflows | `data-quality-check`, `workflow-mapping` |
| **3. Automate** | Build reconciliation, budget tracking, payment automation | `invoice-reconciliation`, `budget-variance-tracker`, `n8n-invoice-approval` |
| **4. Report** | Generate recurring reports, dashboards, payment apps | `n8n-recurring-reports`, `financial-kpi-dashboard`, `payment-app-generator` |
| **5. Predict** | Apply ML to forecast overruns, detect anomalies, score vendor risk | `cost-overrun-prediction`, `invoice-anomaly-detector` |

---

## Why This Exists

Most small businesses run finance ops on spreadsheets and email. The gap between "free tools" (Excel, Gmail) and "enterprise software" (NetSuite, Procore, SAP) is enormous. No one targets small construction firms, restaurants, or service businesses with practical finance automation.

**Trailwise fills that gap.** These skills encode 7 years of real-world finance ops experience into reusable AI agent instructions. No SaaS subscription required — just an AI coding assistant and your data.

### The Trailwise Philosophy

1. **Own your data** — No vendor lock-in, no per-seat tax, no cloud-only prison
2. **Understand before automating** — Methodology first, tools second
3. **AI as multiplier** — Your expertise + AI agents = 10x output, not replacement
4. **Industry-agnostic** — Finance ops is finance ops. Construction, restaurants, services — same principles apply

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

**Trailwise** is a finance operations agency. We help small and mid-size businesses streamline their financial workflows, from invoicing to reporting to forecasting. Agency-first, SaaS emerges from client patterns.

- **Website:** [https://trailwise.com](https://trailwise.com)
- **Tagline:** Finance operations, handled.
- **Consulting:** Book a session — we install and configure these skills for your business

---

## License

MIT License — free to use, modify, and distribute. No attribution required (but appreciated).

---

## Contributing

Contributions welcome:
- **Report issues** — bugs, unclear documentation, broken links
- **Suggest skills** — describe the finance automation you need
- **Submit PRs** — new skills, improvements, translations

Each skill should include a `SKILL.md` with clear instructions, working code examples, and at least one test case.
