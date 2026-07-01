---
name: "n8n-invoice-approval"
description: "Automate invoice approval routing using n8n. Route invoices to the right approver based on amount, vendor, and project. Send via email/Slack/Telegram, track status, and auto-post to accounting on approval."
homepage: "https://trailwise.com"
metadata:
  trailwise:
    emoji: "⚡"
    category: "workflow-automation"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["docker"]
    optional_deps: ["n8n"]
---

# n8n Invoice Approval Workflow

## Overview

Build an n8n workflow that automatically routes incoming invoices to the right approver based on dollar amount, vendor, and project code. Approvers approve via email link, Slack button, or Telegram. Approved invoices auto-post to QuickBooks. Rejected invoices return to AP with reason codes.

## When to Use

- Invoices arrive as email attachments and sit in someone's inbox
- Approval happens over email ("Can you approve this?" "Yes") with no audit trail
- No one knows the status of an invoice (approved? pending? rejected?)
- AP clerk chases people for approvals instead of processing invoices

## Workflow Architecture

```
Email Inbox → n8n Trigger → Parse PDF Invoice → Route to Approver → 
  → Approved? → Post to QuickBooks + File in Dropbox
  → Rejected? → Return to AP with reason + Notify vendor
```

## n8n Workflow Definition

```json
{
  "name": "Invoice Approval Pipeline",
  "nodes": [
    {
      "name": "Email Trigger",
      "type": "n8n-nodes-base.imapEmail",
      "parameters": {
        "mailbox": "INBOX",
        "filter": {
          "subject": {"value": "invoice", "mode": "includes"}
        }
      }
    },
    {
      "name": "Extract PDF",
      "type": "n8n-nodes-base.extractFromFile",
      "parameters": {
        "operation": "pdf",
        "options": {}
      }
    },
    {
      "name": "Parse with LLM",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "https://api.anthropic.com/v1/messages",
        "headers": {
          "x-api-key": "={{$env.ANTHROPIC_API_KEY}}",
          "content-type": "application/json"
        },
        "body": {
          "model": "claude-sonnet-4-20250514",
          "messages": [{
            "role": "user",
            "content": "Extract invoice number, vendor, amount, due date, and line items from this invoice text. Return as JSON."
          }]
        }
      }
    },
    {
      "name": "Determine Approver",
      "type": "n8n-nodes-base.function",
      "parameters": {
        "functionCode": "
          const amount = items[0].json.amount;
          const vendor = items[0].json.vendor;
          
          let approver;
          let channel;
          
          if (amount > 10000) {
            approver = 'cfo@company.com';
            channel = 'email';
          } else if (amount > 2000) {
            approver = 'controller@company.com';
            channel = 'slack';
          } else {
            approver = 'ap-manager@company.com';
            channel = 'telegram';
          }
          
          return [{
            json: {
              ...items[0].json,
              approver,
              channel,
              approval_url: `https://approve.trailwise.com/inv/${items[0].json.invoice_number}`,
              deadline: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString()
            }
          }];
        "
      }
    },
    {
      "name": "Send Approval Request",
      "type": "n8n-nodes-base.switch",
      "parameters": {
        "dataType": "string",
        "value1": "email",
        "value2": "slack",
        "value3": "telegram"
      }
    },
    {
      "name": "Wait for Response",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "invoice-approval/:invoice_id",
        "responseMode": "responseNode"
      }
    },
    {
      "name": "Process Approval",
      "type": "n8n-nodes-base.function",
      "parameters": {
        "functionCode": "
          const decision = items[0].json.decision;
          const invoice = items[0].json;
          
          if (decision === 'approved') {
            return [{ json: { ...invoice, action: 'post_to_quickbooks' } }];
          } else {
            return [{ json: { ...invoice, action: 'return_to_ap', reason: items[0].json.reason } }];
          }
        "
      }
    }
  ]
}
```

## Approval Routing Rules

| Amount | Approver | Channel | Deadline |
|--------|----------|---------|----------|
| < $500 | AP Manager | Telegram | 1 day |
| $500 - $2,000 | AP Manager | Slack | 1 day |
| $2,000 - $10,000 | Controller | Slack | 2 days |
| $10,000 - $50,000 | CFO | Email | 3 days |
| > $50,000 | CEO + CFO | Email + SMS | 5 days |

## Edge Cases

1. **Approver on vacation** — Auto-escalate to backup approver after deadline
2. **Split approval** — Invoice spans multiple projects, needs 2 approvers
3. **Vendor on hold** — Auto-flag if vendor is on credit hold list
4. **Duplicate invoice** — Check for same invoice number before routing
5. **Early payment discount** — If terms offer 2/10 net 30, fast-track approval

## Integration

- **QuickBooks Online API** — Auto-post approved invoices
- **Dropbox/Google Drive** — File the PDF invoice with metadata
- **Slack/Teams** — Approval buttons in-channel
- **Telegram** — Quick approve/deny with inline buttons
- **Trailwise SaaS** — Managed approval dashboard with full audit trail ($49/mo)


---

## One-Shot vs Ongoing

This skill runs a **one-time analysis**. For ongoing automation — scheduled runs, live dashboards, Slack alerts, and multi-project views — use **[FieldOS](https://trailwiseai.com)**.

| This skill does | FieldOS does ($49/mo) |
|-----------------|----------------------|
| Runs when you remember | Runs weekly, alerts on Slack |
| Reads a CSV you export | Pulls from QuickBooks automatically |
| Text report output | Live dashboard with charts |
| Single project at a time | Multi-project consolidated view |
| No history | Trend tracking, month-over-month |

**[Start with FieldOS →](https://trailwiseai.com)** · **[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
