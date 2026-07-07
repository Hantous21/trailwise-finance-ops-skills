---
name: n8n-payment-reminders
description: Send tiered dunning reminders (friendly, then firm, then final) for outstanding invoices via n8n. Use when payment chasing is manual, or when deploying ar-collections-automation as an ongoing workflow.
---

# n8n Payment Reminders

## Overview

Daily n8n workflow that scans overdue invoices, determines the dunning stage (friendly → firm → final → escalated), sends reminders via email, routes firm/final notices through Slack for human approval, and logs every action. Deployment layer for the `ar-collections-automation` skill.

## Workflow Steps

1. **Trigger** — schedule fires at 9 AM weekdays (`0 9 * * *`).
2. **Fetch invoices** — GET open & overdue invoices from accounting API.
3. **Filter** — drop balances below the minimum threshold (default $100).
4. **Deduplicate** — check activity log; skip invoices already reminded today.
5. **Classify** — function node computes days-past-due and assigns dunning stage; skips disputed invoices.
6. **Route** — switch node sends friendly emails automatically; firm and final notices go to Slack for approval.
7. **Approve** — human reacts ✅/❌ in `#finance-approvals`; workflow waits 24 h for a response.
8. **Send** — approved firm/final emails go out (firm CCs the account manager).
9. **Log** — append invoice, client, amount, stage, and method to the Google Sheets log.

> Workflow JSON: see `workflows/payment_reminders.json`.

## Controls

- **Test with internal email first** — point `FINANCE_EMAIL` and `client_email` at yourself before going live; never auto-send to a client untested.
- **Approval matrix** — friendly sends automatically; firm and final require Slack ✅; escalated is manual only.
- **Exclude disputed invoices** — set `disputed = true` on the invoice record; the workflow skips it.
- **Minimum invoice amount** — adjust the filter threshold so small balances aren't chased.
- **Log every send** — the Google Sheets node records each action for audit and dedup.

## Dunning Schedule (Reference)

| Days Past Due | Stage | Auto-Send? | Channel | CC |
|---|---|---|---|---|
| 1–15 | Friendly | ✅ Yes | Email | — |
| 16–45 | Firm | ❌ Approval | Email | Account manager |
| 46–90 | Final | ❌ Approval | Email + letter | Owner/principal |
| 90+ | Escalated | ❌ Manual | Collections agency | Owner + attorney |

## Configuration Variables (Reference)

Set these in your n8n environment before activating.

| Variable | Description | Example |
|---|---|---|
| `FINANCE_EMAIL` | From address for reminders | `ar@yourcompany.com` |
| `SENDER_NAME` | Name in email signature | `Your Finance Team` |
| `ACCOUNT_MANAGER_EMAIL` | CC for firm reminders | `manager@yourcompany.com` |
| `ACCOUNTING_API_URL` | Accounting system API base URL | `https://api.quickbooks.com/v1` |
| `ACCOUNTING_API_KEY` | API key for accounting system | `***` |
| `LOG_SHEET_ID` | Google Sheet ID for activity log | `abc123...` |
| `SLACK_CHANNEL` | Slack channel for approvals | `#finance-approvals` |

**Deploy:** import `workflows/payment_reminders.json` into n8n, set the env vars, and test with internal email first.
