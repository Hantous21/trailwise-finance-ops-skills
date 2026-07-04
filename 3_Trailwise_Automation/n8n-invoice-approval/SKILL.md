---
name: "n8n-invoice-approval"
description: "Automate invoice approval routing using n8n. Route invoices to the right approver based on amount, vendor, and project. Send via email/Slack/Telegram, track status, and auto-post to accounting on approval."
homepage: "https://trailwise.com"
disable model invocation: true
metadata:
  trailwise:
    emoji: "⚡"
    category: "workflow-automation"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["docker"]
    optional_deps: ["n8n"]
    depends_on: "invoice-reconciliation"
---

# n8n Invoice Approval Workflow

## Overview

Automate routing of incoming invoices to the correct approver based on amount,
vendor, and project code. Approvers respond via email link, Slack button, or
Telegram. Approved invoices auto-post to QuickBooks; rejected invoices return
to AP with reason codes. The full n8n workflow definition lives in
`workflows/invoice_approval.json`.

## Workflow Steps

1. **Trigger** — n8n IMAP email trigger watches the inbox for messages whose subject contains "invoice".
2. **Extract** — The attached PDF is pulled out and converted to text.
3. **Parse** — An LLM call extracts invoice number, vendor, amount, due date, and line items as JSON.
4. **Route** — A function node selects the approver and delivery channel based on invoice amount.
5. **Deliver** — A switch node sends the approval request via email, Slack, or Telegram.
6. **Await** — A webhook captures the approver's decision (approve/reject + reason).
7. **Post** — Approved invoices post to QuickBooks and file to Dropbox; rejected invoices return to AP with a reason code.

## Controls

- **Must** set `ANTHROPIC_API_KEY` and `LLM_MODEL` environment variables before importing the workflow.
- **Must** verify the approver email addresses in the "Determine Approver" node match your org chart.
- **Should** enable auto-escalation to a backup approver when a deadline passes without response.
- **Should** add a duplicate-invoice-number check before routing.
- **May** fast-track approval when early-payment discount terms (e.g., 2/10 net 30) are detected.
- **May** add vendor credit-hold flagging before routing.

## Approval Routing

| Amount            | Approver        | Channel        | Deadline |
|-------------------|-----------------|----------------|----------|
| < $500            | AP Manager      | Telegram       | 1 day    |
| $500 – $2,000     | AP Manager      | Slack          | 1 day    |
| $2,000 – $10,000  | Controller      | Slack          | 2 days   |
| $10,000 – $50,000 | CFO             | Email          | 3 days   |
| > $50,000         | CEO + CFO       | Email + SMS    | 5 days   |

## Configuration Variables

| Variable            | Where used                          | Example                       |
|---------------------|-------------------------------------|-------------------------------|
| `ANTHROPIC_API_KEY` | Parse with LLM node (header)        | `sk-ant-…`                    |
| `LLM_MODEL`         | Parse with LLM node (model field)   | `claude-sonnet-4-20250514`    |
| `APPROVAL_BASE_URL` | Determine Approver node (approval_url) | `https://approve.trailwise.com` |
| `QUICKBOOKS_*`      | Post-approval QuickBooks integration | —                             |

→ Import `workflows/invoice_approval.json` into n8n, set the env vars above, and activate the workflow.
