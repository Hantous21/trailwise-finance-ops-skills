---
name: "bank-reconciliation"
description: "Use when matching bank statement transactions to ledger entries, flagging unmatched items, suggesting journal entries for discrepancies, or generating reconciliation reports."
homepage: "https://trailwise.com"
disable model invocation: true
metadata:
  trailwise:
    emoji: "🏦"
    category: "accounting-operations"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
    optional_deps: ["pandas", "openpyxl"]
---

# Bank Reconciliation

## Overview

Match bank statement transactions to general ledger entries using three-pass
fuzzy matching. Flag unmatched items on both sides (bank-only and ledger-only),
suggest journal entries for discrepancies, and generate a reconciliation report
with the adjusted book balance.

## Workflow

1. **Export** bank statement and ledger entries as CSV (see formats below).
2. **Load** both CSV files into `BankTransaction` and `LedgerEntry` lists.
3. **Reconcile** by running `BankReconciler.reconcile()` from `scripts/bank_reconciliation.py`.
4. **Review** the `MatchResult` list — investigate `UNMATCHED` and `LOW_CONFIDENCE` items first.
5. **Generate** a report via `BankReconciler.generate_report()` with ending balances.
6. **Post** suggested journal entries for bank fees and interest, then confirm `is_reconciled` is `True`.

## Controls

- **Three-pass matching**: exact → high-confidence → low-confidence — each pass only considers items unmatched by the previous pass.
- **Amount tolerance**: transactions must match within `±0.01` by default.
- **Date tolerance**: exact pass requires same date; high-confidence allows ±3 days; low-confidence allows ±7 days.
- **Description similarity**: word-overlap Jaccard index; `>0.8` for exact, `>0.6` threshold for high-confidence scoring.
- **Adjusted balance check**: reconciliation succeeds when `|adjusted_bank − adjusted_book| < 0.01`.

## Edge Cases (Reference)

1. **Timing differences** — deposit in ledger before bank; shows as deposit in transit.
2. **Bank fees not in ledger** — auto-deducted; suggest journal entry.
3. **Duplicate transactions** — bank processed same payment twice; flag as duplicate.
4. **Transposed amounts** — $1,250 vs $1,520; won't match; flag for review.
5. **Split transactions** — one bank deposit covers multiple ledger payments; manual matching required.
6. **NSF/returned items** — check bounces; bank shows reversal; ledger needs reversal entry.
7. **Multi-currency** — conversion rate mismatch; use wider amount tolerance.

## CSV Input Formats (Reference)

**Bank statement** (`date,amount,description,running_balance`):

```csv
2026-06-01,-1250.00,"CHECK #1042 PAYROLL",45200.00
2026-06-02,5000.00,"DEPOSIT CLIENT PAYMENT",50200.00
2026-06-03,-35.00,"MONTHLY ACCOUNT FEE",50165.00
```

**Ledger entries** (`date,amount,description,account,reference`):

```csv
2026-06-01,-1250.00,"Payroll run biweekly","Cash - Operating","PR-2026-06"
2026-06-02,5000.00,"Client payment invoice #1042","Cash - Operating","INV-1042"
```

All code lives in `scripts/bank_reconciliation.py` — import `BankReconciler` and run.
