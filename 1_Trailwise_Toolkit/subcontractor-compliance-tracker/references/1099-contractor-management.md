# 1099 Contractor Management — Domain Reference

For use alongside the subcontractor-compliance-tracker. The script tracks W-9
status (on file / missing) and YTD payments against 1099-NEC filing thresholds.

## Filing Thresholds

| Tax Year | Threshold | Notes |
|----------|-----------|-------|
| 2025 | $600 | Classic threshold — file 1099-NEC for any non-corporate contractor paid >= $600 |
| 2026+ | $2,000 | New threshold starting tax year 2026. Fewer 1099s required, but track ALL payments — threshold may change again. |

## Who Needs a 1099-NEC?

| Payee Type | 1099-NEC Required? | Notes |
|------------|-------------------|-------|
| Individual (sole proprietor, freelancer) | **Yes** if >= threshold | Most common |
| Single-member LLC (disregarded entity) | **Yes** if >= threshold | Treated as individual |
| Partnership / Multi-member LLC | **Yes** if >= threshold | |
| S-Corporation | **Generally no** | **Exception:** legal services and medical/health care services always require 1099 regardless of entity type |
| C-Corporation | **Generally no** | Same exceptions as S-Corp |
| Payments via credit/debit card or 3rd-party networks | **No** | Payment processor (Stripe, PayPal, Venmo, Square) reports on **1099-K** instead. Don't double-report. |
| Employees | **No** | They get a W-2 |
| Rent paid to real estate agents | **No (1099-NEC)** | Gets 1099-MISC instead |
| Payments for merchandise/inventory | **No** | 1099-NEC is for services, not goods |

## W-9 Collection

- Collect Form W-9 from every contractor **before making the first payment**.
- W-9 provides: legal name, business name, federal tax classification, address, TIN (SSN or EIN).
- **No W-9 = backup withholding required** at 24% of all future payments. Remit withheld amounts to IRS via Form 945. Failing to withhold when required makes you liable for the tax.
- Best practice: No W-9, no first payment. Make it part of onboarding.
- Store W-9s securely — they contain SSNs.

## Filing Deadline

- **January 31** — both contractor copy AND IRS filing due. **No extension** for 1099-NEC (unlike 1099-MISC which has a March IRS deadline).
- **Electronic filing required** if filing 10+ information returns (any combination of 1099s, W-2s, etc.). Threshold was 250 until 2024, dropped to 10.
- File via IRS FIRE system, or use Tax1099.com, Track1099, QuickBooks, Gusto.

## Penalty Schedule

| When You File | Penalty Per Form |
|---------------|-----------------|
| Within 30 days of deadline (by Mar 2) | $60 |
| By Aug 1 | $130 |
| After Aug 1 or not at all | $330 |
| **Intentional disregard** | $660/form, **no maximum cap** |

Annual maximums (small businesses, gross receipts <= $5M): $232,500 (30-day tier), $664,500 (Aug tier), $1,328,500 (after-Aug tier). Intentional disregard has no maximum.

Penalties are **per form** — 20 contractors missed = 20x the penalty.

## Correcting 1099s

- **Type 1:** Wrong amount/code/checkbox → file new 1099-NEC with "CORRECTED" box checked.
- **Type 2:** Wrong payee name/TIN → two forms: one zeroing out incorrect payee, one with correct payee.
- File corrections as soon as discovered. Correcting before IRS notices = generally no penalty.

## Worker Classification Risk

Misclassifying an employee as a contractor exposes you to:
- Back employment taxes (employer FICA: 7.65% of all payments)
- Penalties for failure to withhold income tax
- Penalties for failure to file W-2s
- Interest on all of the above
- State-level penalties (many states more aggressive than IRS)

**IRS Common Law Test:**
- **Behavioral control:** Do you control how work is done (hours, tools, processes, location)? Contractors control their own methods.
- **Financial control:** Does worker have unreimbursed expenses, own tools, profit/loss potential, offer services to public?
- **Relationship:** Written contract? Benefits? Permanent vs project-based? Is work core to your regular business?

When in doubt: File Form SS-8 for IRS determination, or consult an employment attorney.

## Year-End Checklist

By December 15:
- Review all contractor YTD totals
- Verify W-9 on file for every contractor above threshold
- Request W-9s from any contractor without one
- Verify TINs match contractor names (consider TIN matching via IRS e-Services)

By January 31:
- Generate 1099-NEC forms for all qualifying contractors
- Mail or electronically deliver Copy B to each contractor
- File Copy A with IRS (electronically if >= 10 forms)
- Retain Copy C for records

After filing:
- Monitor for IRS notices about mismatches
- File corrections promptly if errors discovered

## Integration with Compliance Tracker

The compliance tracker script (`subcontractor_compliance.py`) now supports:
- `W9` document type (already existed — tracks on-file/missing status)
- `ContractorPayment` dataclass — tracks individual payments per contractor
- `get_1099_report()` — generates YTD payment summary with threshold flags
- Monthly close Step 7 references this report — check during every monthly close

## Sources

- IRS Pub. 15 (Circular E) — backup withholding rules
- IRS Instructions for Form 1099-NEC
- IRS Form SS-8 — worker classification determination
- Source skill: bookkeeping.md/skills/contractor-1099 (MIT, Receiptor-AI) — threshold research and penalty schedule adapted from this skill
