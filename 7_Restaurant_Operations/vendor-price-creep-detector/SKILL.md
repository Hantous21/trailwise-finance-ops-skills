---
name: vendor-price-creep-detector
description: Detect vendor price creep from purchase history — the same case of chicken drifting up 2% per order until it's 10% and nobody noticed. Use when unit prices only get looked at when an invoice looks "off", when food cost rose but the menu didn't change, or before a vendor negotiation.
---

# Vendor Price Creep Detector

## Overview

Per-(vendor, item) price history from purchase records. Catches the slow
creep no single invoice reveals: the same Sysco chicken case drifting 2%
per order until it's 10.4% and nobody noticed.

Grouped by (vendor, item), sorted by date. Each group reports:
- `baseline_price` — first observed unit price
- `latest_price` — most recent unit price
- `creep_pct` — percentage change from baseline
- `price_creep` flag — when creep > threshold (strictly)
- `price_spike` flag — when any consecutive jump > spike threshold (strictly)
- `excess_cost_to_date` — total dollars over baseline across all purchases

Groups with only one purchase get `insufficient_history: true` — no flags,
no excess.

## Workflow

1. Export purchase history as `purchase_history.csv` (date, vendor, item,
   quantity, unit, unit_price).
2. Run the script:
   ```bash
   python3 scripts/vendor_price_creep.py purchase_history.csv \
       --creep-threshold 5.0 --spike-threshold 10.0 --json report.json
   ```
3. Review flagged items — a `price_spike` is a phone call today. `price_creep`
   is a quarterly negotiation agenda item.
4. Keep history per vendor AND item — switching vendors resets the baseline
   honestly.

## Controls

- **Creep hides below invoice-approval attention** — no single Sysco invoice
  in the fixture jumps more than 3.12%, yet chicken is up 10.4% and has
  already cost $117 above baseline.
- **Check creep BEFORE** renewing a vendor or repricing a menu.
- **A spike is a phone call today** — a creep flag is a quarterly
  negotiation agenda item.
- Keep the history per vendor AND item — switching vendors resets the
  baseline honestly.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.