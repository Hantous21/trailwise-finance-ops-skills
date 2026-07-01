---
name: "n8n-payment-reminders"
description: "Send automated payment reminders for outstanding invoices. Tiered dunning (friendly → firm → final) via email/Slack/Telegram. Deployment layer for the AR collections skill."
homepage: "https://trailwise.com"
metadata:
  trailwise:
    emoji: "⏰"
    category: "workflow-automation"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["docker"]
    optional_deps: ["n8n"]
    depends_on: "ar-collections-automation"
---

# n8n Payment Reminders

## Overview

Automated payment reminder system using n8n. Scans outstanding invoices daily, determines the correct dunning stage (friendly, firm, final notice), sends reminders via email/Slack/Telegram, and logs all activity. This is the deployment layer for the `ar-collections-automation` skill — it turns the dunning logic into an automated, running system.

## When to Use

- Invoices sit unpaid with no systematic follow-up
- Collections emails are written manually each time
- No tracking of which reminders were sent, when, or what the response was
- Cash flow is unpredictable because nobody chases overdue invoices

## Safety & Approvals

**This skill sends emails to your clients.** Before activating:

1. **Test with internal email addresses first** — send reminders to yourself, not clients
2. **Set a minimum invoice amount** — don't auto-dun a $25 invoice (costs more in effort than it's worth)
3. **Exclude disputed invoices** — flag invoices with a "disputed" status to skip dunning
4. **Human review before FIRM stage** — auto-send FRIENDLY reminders, but require human approval before FIRM/FINAL
5. **Log every email** — for audit trail and to prevent duplicate sends

## Workflow Architecture

```
Daily Trigger (9am) → Query Outstanding Invoices → 
  → Determine Dunning Stage →
    → FRIENDLY? → Auto-send email
    → FIRM? → Send to Slack for human approval → (if approved) send email
    → FINAL? → Send to Slack for human approval → (if approved) send email + letter
    → ESCALATED? → Skip, flag for manual collections
  → Log Activity to Google Sheets/DB
```

## n8n Workflow Definition

```json
{
  "name": "Payment Reminder Pipeline",
  "nodes": [
    {
      "name": "Daily Trigger",
      "type": "n8n-nodes-base.scheduleTrigger",
      "parameters": {
        "rule": {
          "interval": [{"field": "cronExpression", "expression": "0 9 * * *"}]
        }
      }
    },
    {
      "name": "Fetch Outstanding Invoices",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "GET",
        "url": "={{$env.ACCOUNTING_API_URL}}/invoices?status=open&overdue=true",
        "headers": {"Authorization": "Bearer {{{{$env.ACCOUNTING_API_KEY}}}}"}
      }
    },
    {
      "name": "Filter by Minimum Amount",
      "type": "n8n-nodes-base.filter",
      "parameters": {
        "conditions": {
          "number": [{"value1": "={{$json.balance_due}}", "operation": "larger", "value2": 100}]
        }
      }
    },
    {
      "name": "Check Already Sent Today",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "GET",
        "url": "={{$env.LOG_API_URL}}/activities?invoice_id=={{$json.id}}&date=today",
        "responseFormat": "json"
      }
    },
    {
      "name": "Determine Dunning Stage",
      "type": "n8n-nodes-base.function",
      "parameters": {
        "functionCode": "
          const daysPastDue = Math.floor(
            (Date.now() - new Date(items[0].json.due_date).getTime()) / 86400000
          );
          
          let stage;
          if (daysPastDue <= 0) stage = 'none';
          else if (daysPastDue <= 15) stage = 'friendly';
          else if (daysPastDue <= 45) stage = 'firm';
          else if (daysPastDue <= 90) stage = 'final';
          else stage = 'escalated';
          
          // Skip if already sent today or disputed
          if (items[0].json.disputed) stage = 'skip_disputed';
          if (items[0].json.already_sent_today) stage = 'skip_duplicate';
          
          return [{
            json: {
              ...items[0].json,
              days_past_due: daysPastDue,
              dunning_stage: stage
            }
          }];
        "
      }
    },
    {
      "name": "Route by Stage",
      "type": "n8n-nodes-base.switch",
      "parameters": {
        "dataType": "string",
        "value1": "friendly",
        "value2": "firm",
        "value3": "final"
      }
    },
    {
      "name": "Send Friendly Email",
      "type": "n8n-nodes-base.emailSend",
      "parameters": {
        "fromEmail": "={{$env.FINANCE_EMAIL}}",
        "toEmail": "={{$json.client_email}}",
        "subject": "=Friendly reminder: Invoice {{$json.invoice_number}} - ${{$json.balance_due}}",
        "text": "=Hi {{$json.client_name}},\n\nWe hope you're doing well! This is a friendly reminder that invoice {{$json.invoice_number}} for ${{$json.balance_due}} was due on {{$json.due_date}} ({{$json.days_past_due}} days ago).\n\nPlease process payment at your earliest convenience.\n\nThank you,\n{{$env.SENDER_NAME}}"
      }
    },
    {
      "name": "FIRM: Request Human Approval",
      "type": "n8n-nodes-base.slack",
      "parameters": {
        "channel": "#finance-approvals",
        "text": "=Payment reminder approval needed:\n*Invoice:* {{$json.invoice_number}}\n*Client:* {{$json.client_name}}\n*Amount:* ${{$json.balance_due}}\n*Days Past Due:* {{$json.days_past_due}}\n*Stage:* FIRM\n\nReact with ✅ to approve sending, ❌ to skip."
      }
    },
    {
      "name": "Wait for Approval (24h)",
      "type": "n8n-nodes-base.wait",
      "parameters": {
        "amount": 24,
        "unit": "hours"
      }
    },
    {
      "name": "Send FIRM Email (if approved)",
      "type": "n8n-nodes-base.emailSend",
      "parameters": {
        "fromEmail": "={{$env.FINANCE_EMAIL}}",
        "toEmail": "={{$json.client_email}}",
        "ccEmail": "={{$env.ACCOUNT_MANAGER_EMAIL}}",
        "subject": "=Payment overdue {{$json.days_past_due}} days: Invoice {{$json.invoice_number}} - ${{$json.balance_due}}",
        "text": "=Dear {{$json.client_name}},\n\nYour invoice {{$json.invoice_number}} for ${{$json.balance_due}} is now {{$json.days_past_due}} days past due.\n\nPlease remit payment within 5 business days or contact us to discuss payment arrangements.\n\nIf payment has already been sent, please disregard this notice.\n\nThank you,\n{{$env.SENDER_NAME}}"
      }
    },
    {
      "name": "Log Activity",
      "type": "n8n-nodes-base.googleSheets",
      "parameters": {
        "operation": "append",
        "documentId": "={{$env.LOG_SHEET_ID}}",
        "sheetName": "Collections Log",
        "columns": {
          "mappingMode": "defineBelow",
          "value": {
            "date": "={{$today}}",
            "invoice_id": "={{$json.invoice_number}}",
            "client": "={{$json.client_name}}",
            "amount": "={{$json.balance_due}}",
            "stage": "={{$json.dunning_stage}}",
            "method": "email",
            "response": ""
          }
        }
      }
    }
  ]
}
```

## Dunning Schedule

| Days Past Due | Stage | Auto-Send? | Channel | CC |
|---------------|-------|-----------|---------|-----|
| 1-15 | Friendly | ✅ Yes | Email | — |
| 16-45 | Firm | ❌ Needs approval | Email | Account manager |
| 46-90 | Final Notice | ❌ Needs approval | Email + Letter | Owner/principal |
| 90+ | Escalated | ❌ Manual | Collections agency | Owner + attorney |

## Configuration Variables

Set these in your n8n environment:

| Variable | Description | Example |
|----------|-------------|---------|
| `FINANCE_EMAIL` | From address for reminders | `ar@yourcompany.com` |
| `SENDER_NAME` | Name in email signature | `Your Finance Team` |
| `ACCOUNT_MANAGER_EMAIL` | CC for firm reminders | `manager@yourcompany.com` |
| `ACCOUNTING_API_URL` | Your accounting system API | `https://api.quickbooks.com/v1` |
| `ACCOUNTING_API_KEY` | API key for accounting system | `***` |
| `LOG_SHEET_ID` | Google Sheet ID for activity log | `abc123...` |
| `SLACK_CHANNEL` | Slack channel for approvals | `#finance-approvals` |

## Edge Cases

1. **Client disputes invoice** — Set `disputed = true` in invoice data. Workflow skips dunning until resolved.
2. **Payment plan in place** — If client is on a payment plan and current, skip dunning. Check `payment_plan_status = "current"`.
3. **Already sent today** — Check activity log before sending. Prevents duplicate emails if workflow runs twice.
4. **Email bounce** — Log bounce, flag on dashboard for manual follow-up via phone.
5. **Small balance** — Minimum threshold ($100 default). Don't auto-dun small amounts — costs more in effort.
6. **Weekend timing** — Daily trigger at 9am on weekdays only. No reminders on weekends.
7. **Client on hold** — If client has a "credit hold" status, escalate immediately to account manager instead of sending standard reminder.

## Integration

- **ar-collections-automation** — This workflow is the deployment layer for that skill's dunning logic
- **QuickBooks Online API** — Fetch outstanding invoices, update payment status
- **Google Sheets** — Log all collections activity for audit trail
- **Slack** — Approval routing for FIRM and FINAL stages
- **Gmail/Outlook** — Send reminder emails
- **Telegram** — Alternative notification channel for smaller teams
- **Trailwise SaaS** — Managed version with dashboard ($49/mo)


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
