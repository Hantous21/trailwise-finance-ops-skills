# Tier 7: Restaurant Operations

Restaurant finance ops — daily controls first. Cash leaks the same day it happens; reconcile POS to bank deposits before you reconcile anything else, name a person per drawer, and tie out card-processor fees against the statement every week.

| Status | Skill | Description |
|---|---|---|
| Shipped | `daily-sales-reconciliation` | Tie out daily POS sales to bank deposits — cash variances, missing deposits, and card-processor fee drift. |
| Shipped | `prime-cost-tracker` | Track weekly prime cost (food + beverage COGS + labor) against the 60/65 benchmark band. |
| Shipped | `vendor-price-creep-detector` | Detect per-item vendor price creep from purchase history with configurable creep and spike thresholds. |
| Shipped | `tip-pool-calculator` | Penny-exact daily tip pool splitting by role-weighted hours with compliance-safe reporting. |

More restaurant skills ship as the prime-cost platform work matures.