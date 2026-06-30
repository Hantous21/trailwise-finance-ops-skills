---
name: "ar-collections-automation"
description: "Automate accounts receivable collections. Generate aging reports, send tiered dunning emails, predict late payments, and track collections activity."
homepage: "https://trailwise.com"
metadata:
  trailwise:
    emoji: "📮"
    category: "accounts-receivable"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
    optional_deps: ["pandas", "openpyxl"]
---

# AR Collections Automation

## Overview

Automate the accounts receivable collections process. Generate AR aging reports with auto-categorization, send tiered dunning email sequences (friendly → firm → final notice), predict which invoices will be late based on client payment history, and maintain a collections activity log.

## When to Use

- AR aging is checked ad hoc when cash is tight
- Collections emails are written from scratch each time
- No tracking of which clients consistently pay late
- No systematic follow-up — invoices just sit unpaid until someone notices
- Cash flow is unpredictable because you don't know when payments will arrive

## Capabilities

- AR aging report (0-30, 31-60, 61-90, 90+ day buckets)
- Client payment history analysis (average days to pay, late frequency)
- Late payment prediction (which outstanding invoices will likely be late)
- Tiered dunning email generation (3 escalating stages)
- Collections activity log (every contact recorded with date, method, response)
- Collections dashboard (total outstanding, at-risk amount, expected collection date)
- Payment plan tracking (structured paydown agreements)

## Quick Start

```python
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Dict, Optional
from enum import Enum

class AgingBucket(Enum):
    CURRENT = "current"      # 0-30 days
    BUCKET_31_60 = "31_60"
    BUCKET_61_90 = "61_90"
    BUCKET_90_PLUS = "90_plus"
    PAID = "paid"

class DunningStage(Enum):
    NONE = "none"
    FRIENDLY = "friendly"        # 1-15 days late
    FIRM = "firm"                # 16-45 days late
    FINAL_NOTICE = "final"      # 46+ days late
    ESCALATED = "escalated"      # Sent to collections/legal

class PaymentRiskLevel(Enum):
    LOW = "low"                  # Usually pays on time
    MEDIUM = "medium"            # Occasionally late
    HIGH = "high"                # Frequently late
    CRITICAL = "critical"        # Chronically late, collection risk

@dataclass
class Invoice:
    id: str
    client_id: str
    client_name: str
    invoice_date: date
    due_date: date
    amount: float
    amount_paid: float = 0
    status: str = "open"         # "open", "partial", "paid", "written_off"
    payment_date: Optional[date] = None

    @property
    def balance_due(self) -> float:
        return self.amount - self.amount_paid

    @property
    def days_past_due(self) -> int:
        if self.status == "paid":
            return 0
        return max(0, (date.today() - self.due_date).days)

    @property
    def aging_bucket(self) -> AgingBucket:
        if self.status == "paid":
            return AgingBucket.PAID
        dpd = self.days_past_due
        if dpd == 0:
            return AgingBucket.CURRENT
        elif dpd <= 30:
            return AgingBucket.CURRENT
        elif dpd <= 60:
            return AgingBucket.BUCKET_31_60
        elif dpd <= 90:
            return AgingBucket.BUCKET_61_90
        else:
            return AgingBucket.BUCKET_90_PLUS

    @property
    def dunning_stage(self) -> DunningStage:
        dpd = self.days_past_due
        if dpd == 0:
            return DunningStage.NONE
        elif dpd <= 15:
            return DunningStage.FRIENDLY
        elif dpd <= 45:
            return DunningStage.FIRM
        elif dpd <= 90:
            return DunningStage.FINAL_NOTICE
        else:
            return DunningStage.ESCALATED

@dataclass
class ClientPaymentHistory:
    client_id: str
    client_name: str
    total_invoices: int = 0
    paid_on_time: int = 0
    paid_late: int = 0
    avg_days_to_pay: float = 0
    avg_days_late: float = 0
    last_payment_date: Optional[date] = None

    @property
    def on_time_rate(self) -> float:
        if self.total_invoices == 0:
            return 0
        return self.paid_on_time / self.total_invoices

    @property
    def risk_level(self) -> PaymentRiskLevel:
        if self.total_invoices < 3:
            return PaymentRiskLevel.MEDIUM  # Insufficient data
        rate = self.on_time_rate
        if rate >= 0.85:
            return PaymentRiskLevel.LOW
        elif rate >= 0.65:
            return PaymentRiskLevel.MEDIUM
        elif rate >= 0.40:
            return PaymentRiskLevel.HIGH
        else:
            return PaymentRiskLevel.CRITICAL

@dataclass
class CollectionsActivity:
    id: str
    invoice_id: str
    client_id: str
    date: date
    method: str          # "email", "phone", "letter", "meeting"
    contact_person: str
    stage: DunningStage
    response: str = ""   # "no response", "promised payment", "disputed", "paid"
    notes: str = ""
    follow_up_date: Optional[date] = None
```

## Collections Manager

```python
class CollectionsManager:
    """Manage AR collections with aging, prediction, and automated dunning."""

    def __init__(self):
        self.invoices: Dict[str, Invoice] = {}
        self.client_history: Dict[str, ClientPaymentHistory] = {}
        self.activities: List[CollectionsActivity] = []

    def add_invoice(self, invoice: Invoice):
        self.invoices[invoice.id] = invoice

    def get_aging_report(self) -> Dict:
        """Generate AR aging report by bucket."""
        buckets = {b.value: {"count": 0, "amount": 0, "invoices": []}
                   for b in AgingBucket if b != AgingBucket.PAID}

        for inv in self.invoices.values():
            if inv.status == "paid":
                continue
            bucket = inv.aging_bucket
            if bucket == AgingBucket.PAID:
                continue
            b = buckets[bucket.value]
            b["count"] += 1
            b["amount"] += inv.balance_due
            b["invoices"].append({
                "invoice_id": inv.id,
                "client": inv.client_name,
                "amount": inv.balance_due,
                "due_date": inv.due_date.isoformat(),
                "days_past_due": inv.days_past_due,
                "dunning_stage": inv.dunning_stage.value,
            })

        total_outstanding = sum(b["amount"] for b in buckets.values())

        return {
            "total_outstanding": round(total_outstanding, 2),
            "by_bucket": buckets,
            "total_invoices_open": sum(b["count"] for b in buckets.values()),
            "overdue_count": sum(b["count"] for k, b in buckets.items() if k != "current"),
            "overdue_amount": round(sum(b["amount"] for k, b in buckets.items() if k != "current"), 2),
        }

    def analyze_client_history(self) -> Dict[str, ClientPaymentHistory]:
        """Analyze payment patterns for each client."""
        client_data = {}

        for inv in self.invoices.values():
            if inv.client_id not in client_data:
                client_data[inv.client_id] = ClientPaymentHistory(
                    client_id=inv.client_id,
                    client_name=inv.client_name
                )

            hist = client_data[inv.client_id]
            if inv.status == "paid" and inv.payment_date:
                hist.total_invoices += 1
                days_to_pay = (inv.payment_date - inv.invoice_date).days
                days_late = max(0, (inv.payment_date - inv.due_date).days)

                if days_late == 0:
                    hist.paid_on_time += 1
                else:
                    hist.paid_late += 1
                    hist.avg_days_late = (
                        (hist.avg_days_late * (hist.paid_late - 1) + days_late) / hist.paid_late
                    )

                hist.avg_days_to_pay = (
                    (hist.avg_days_to_pay * (hist.total_invoices - 1) + days_to_pay) / hist.total_invoices
                )
                hist.last_payment_date = inv.payment_date

        self.client_history = client_data
        return client_data

    def predict_late_payments(self) -> List[Dict]:
        """Predict which currently-open invoices will be paid late."""
        if not self.client_history:
            self.analyze_client_history()

        predictions = []
        for inv in self.invoices.values():
            if inv.status == "paid":
                continue

            hist = self.client_history.get(inv.client_id)
            if not hist:
                predictions.append({
                    "invoice_id": inv.id, "client": inv.client_name,
                    "amount": inv.balance_due, "prediction": "unknown",
                    "confidence": 0, "reason": "No payment history"
                })
                continue

            risk = hist.risk_level
            will_be_late = risk in (PaymentRiskLevel.HIGH, PaymentRiskLevel.CRITICAL)
            confidence = 0.5 + (hist.on_time_rate * 0.5) if not will_be_late else 0.5 + ((1 - hist.on_time_rate) * 0.5)

            reason = f"Client pays on time {hist.on_time_rate*100:.0f}% of the time, avg {hist.avg_days_late:.0f} days late"

            predictions.append({
                "invoice_id": inv.id,
                "client": inv.client_name,
                "amount": inv.balance_due,
                "due_date": inv.due_date.isoformat(),
                "prediction": "late" if will_be_late else "on_time",
                "confidence": round(confidence, 2),
                "risk_level": risk.value,
                "reason": reason,
            })

        # Sort: highest risk first
        predictions.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return predictions

    def get_collections_dashboard(self) -> Dict:
        """Get collections dashboard summary."""
        aging = self.get_aging_report()
        predictions = self.predict_late_payments()
        at_risk = [p for p in predictions if p["prediction"] == "late"]
        at_risk_amount = sum(p["amount"] for p in at_risk)

        return {
            "total_outstanding": aging["total_outstanding"],
            "overdue_amount": aging["overdue_amount"],
            "at_risk_amount": round(at_risk_amount, 2),
            "at_risk_count": len(at_risk),
            "aging_summary": {k: v["amount"] for k, v in aging["by_bucket"].items()},
            "top_risk_clients": [
                {"client": p["client"], "amount": p["amount"], "risk": p["risk_level"]}
                for p in at_risk[:5]
            ],
        }
```

## Dunning Email Generator

```python
class DunningEmailGenerator:
    """Generate tiered dunning emails for overdue invoices."""

    def generate_email(self, invoice: Invoice, stage: DunningStage,
                       client_history: Optional[ClientPaymentHistory] = None,
                       sender_name: str = "Your Finance Team") -> Dict:
        """Generate a dunning email based on the invoice's dunning stage."""
        dpd = invoice.days_past_due

        if stage == DunningStage.FRIENDLY:
            subject = f"Friendly reminder: Invoice {invoice.id} - ${invoice.balance_due:,.2f}"
            tone = "We hope you're doing well! This is just a friendly reminder"
            action = "Please process payment at your earliest convenience."
            urgency = ""

        elif stage == DunningStage.FIRM:
            subject = f"Payment overdue {dpd} days: Invoice {invoice.id} - ${invoice.balance_due:,.2f}"
            tone = f"Your invoice is now {dpd} days past due"
            action = "Please remit payment within 5 business days or contact us to discuss payment arrangements."
            urgency = "If payment has already been sent, please disregard this notice."

        elif stage == DunningStage.FINAL_NOTICE:
            subject = f"FINAL NOTICE - Invoice {invoice.id} - ${invoice.balance_due:,.2f} - {dpd} days overdue"
            tone = f"This is our final notice regarding invoice {invoice.id}, which is now {dpd} days past due"
            action = "Payment must be received within 10 business days. If you are experiencing financial difficulties, please contact us immediately to discuss a payment plan. Failure to respond may result in this account being sent to collections."
            urgency = "This is our final attempt to resolve this amicably."

        elif stage == DunningStage.ESCALATED:
            subject = f"NOTICE: Account sent to collections - Invoice {invoice.id}"
            tone = f"Despite multiple attempts to collect on invoice {invoice.id} (${invoice.balance_due:,.2f}), now {dpd} days past due, no payment has been received"
            action = "This account has been escalated to our collections department. Please contact us within 5 business days to avoid further action."
            urgency = ""

        else:
            return {"error": "Invoice is not overdue or stage is NONE"}

        body = f"""Dear {invoice.client_name},

{tone}. Here are the invoice details:

Invoice #: {invoice.id}
Amount Due: ${invoice.balance_due:,.2f}
Original Due Date: {invoice.due_date}
Days Past Due: {dpd}

{action}

{urgency}

If you have any questions about this invoice, please don't hesitate to contact us.

Thank you,
{sender_name}
"""

        return {
            "to": "",  # Filled by caller from client contact data
            "subject": subject,
            "body_text": body,
            "stage": stage.value,
            "invoice_id": invoice.id,
            "client_name": invoice.client_name,
            "amount": invoice.balance_due,
            "days_past_due": dpd,
        }
```

## Dunning Schedule

| Days Past Due | Stage | Email Tone | CC | Action |
|---------------|-------|------------|-----|--------|
| 1-15 | Friendly | "Just a reminder!" | — | Send email, log activity |
| 16-45 | Firm | "Payment overdue" | Account manager | Send email, call if >$5K |
| 46-90 | Final Notice | "FINAL NOTICE" | Owner/principal | Send email + certified letter |
| 90+ | Escalated | "Sent to collections" | Owner + attorney | Send to collections agency |

## Collections Activity Log

```python
class CollectionsActivityLog:
    """Track every collections contact for audit trail."""

    def __init__(self):
        self.activities: List[CollectionsActivity] = []

    def log_activity(self, invoice_id: str, client_id: str, method: str,
                     stage: DunningStage, response: str = "", notes: str = "",
                     follow_up_date: Optional[date] = None):
        activity = CollectionsActivity(
            id=f"ACT-{len(self.activities)+1:04d}",
            invoice_id=invoice_id, client_id=client_id,
            date=date.today(), method=method,
            contact_person="", stage=stage,
            response=response, notes=notes,
            follow_up_date=follow_up_date
        )
        self.activities.append(activity)
        return activity

    def get_client_history(self, client_id: str) -> List[CollectionsActivity]:
        return [a for a in self.activities if a.client_id == client_id]

    def get_pending_follow_ups(self) -> List[CollectionsActivity]:
        """Get activities that need follow-up today or earlier."""
        return [a for a in self.activities
                if a.follow_up_date and a.follow_up_date <= date.today()
                and a.response not in ("paid", "written_off")]
```

## Edge Cases

1. **Partial payments** — Client pays half. Invoice stays open with reduced balance. Adjust dunning amount.
2. **Disputed invoices** — Client disputes quality/scope. Put hold on dunning, flag for PM review.
3. **Payment plans** — Client on structured paydown. Skip dunning if plan is current.
4. **Client bankruptcy** — Stop all dunning, write off or send to attorney.
5. **Small balances** — Don't spend $50 of effort collecting a $25 invoice. Set minimum threshold.
6. **Repeat offenders** — Client pays late every month but eventually pays. Adjust terms or require deposits.
7. **Credit memos** — Apply credit memos to outstanding invoices before dunning.

## Integration

- **QuickBooks Online** — Pull invoice data, push payment records
- **n8n** — Send dunning emails automatically based on aging
- **Stripe** — Match Stripe payments to invoices automatically
- **Email (Gmail/Outlook)** — Send dunning emails via n8n workflow
- **Slack** — Alert account manager when invoice hits FIRM stage
- **Trailwise SaaS** — Collections dashboard with automated workflows ($49/mo)
