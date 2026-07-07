# Tier 7: Restaurant Operations

Restaurant finance ops — daily controls first. Cash leaks the same day it happens; reconcile POS to bank deposits before you reconcile anything else, name a person per drawer, and tie out card-processor fees against the statement every week.

| Status | Skill | Description |
|---|---|---|
| Shipped | `daily-sales-reconciliation` | Tie out daily POS sales to bank deposits — cash variances, missing deposits, and card-processor fee drift. |
| Planned | `prime-cost-tracker` | Food + labor cost as a % of sales, by period and by menu category. |
| Planned | `vendor-price-creep-detector` | Compare invoice unit prices to a baseline; flag drift above a configurable threshold. |
| Planned | `tip-pool-calculator` | Allocate tips by hours, points, or sales with compliance-safe reporting. |
