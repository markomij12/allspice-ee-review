# sensor-node (seeded-error copy)

**2 error(s), 1 warning(s), 2 info, 8 pass**

## cap-derating

| Severity | Ref | Finding |
|---|---|---|
| ERROR | C2 | Rated 2.5 V but sees 3.3 V (132% of rating): over absolute rating. |
| WARNING | C3 | 52% of 10 V rating exceeds 50% X5R derating limit (needs >= 10.5 V part). |
| INFO | C4 | Working voltage unknown (net Net-(J2-Pin_2) has no rail voltage); add it under `rails:` to check this part. |
| INFO | C8 | Working voltage unknown (net Net-(U4-EN) has no rail voltage); add it under `rails:` to check this part. |

## regulator-feedback

| Severity | Ref | Finding |
|---|---|---|
| ERROR | U1 | Divider R2/R3 sets 5.51 V but rail 3V3 expects 3.3 V (>5% off). |

