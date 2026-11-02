# sensor-node (upstream, unmodified)

**0 error(s), 9 warning(s), 2 info, 2 pass**

## cap-derating

| Severity | Ref | Finding |
|---|---|---|
| WARNING | C1 | No voltage rating in BOM (Voltage field, MPN, or value) for a part across 4.2 V; cannot verify derating. |
| WARNING | C10 | No voltage rating in BOM (Voltage field, MPN, or value) for a part across 3.3 V; cannot verify derating. |
| WARNING | C11 | No voltage rating in BOM (Voltage field, MPN, or value) for a part across 3.3 V; cannot verify derating. |
| WARNING | C2 | No voltage rating in BOM (Voltage field, MPN, or value) for a part across 3.3 V; cannot verify derating. |
| WARNING | C3 | No voltage rating in BOM (Voltage field, MPN, or value) for a part across 5.25 V; cannot verify derating. |
| WARNING | C5 | No voltage rating in BOM (Voltage field, MPN, or value) for a part across 4.2 V; cannot verify derating. |
| WARNING | C6 | No voltage rating in BOM (Voltage field, MPN, or value) for a part across 3.3 V; cannot verify derating. |
| WARNING | C7 | No voltage rating in BOM (Voltage field, MPN, or value) for a part across 3.3 V; cannot verify derating. |
| WARNING | C9 | No voltage rating in BOM (Voltage field, MPN, or value) for a part across 3.3 V; cannot verify derating. |
| INFO | C4 | Working voltage unknown (net Net-(J2-Pin_2) has no rail voltage); add it under `rails:` to check this part. |
| INFO | C8 | Working voltage unknown (net Net-(U4-EN) has no rail voltage); add it under `rails:` to check this part. |

## power-budget

| Severity | Ref | Finding |
|---|---|---|
| PASS | U1 | 3V3: 500 mA of 2000 mA (25%). |

## regulator-feedback

| Severity | Ref | Finding |
|---|---|---|
| PASS | U1 | Divider R2/R3 sets 3.31 V (rail 3V3 3.3 V). |

