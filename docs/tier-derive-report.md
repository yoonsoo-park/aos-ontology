# Tier Auto-Derive Validation Report

- manifest objects: 243
- metadata objects parsed: 615
- candidates after Pass 1: 307
- T1 size: 28, T2 size: 80, T3 size: 205

## Recall vs hardcoded

| metric | value |
|---|---|
| T1 recall | 92.9% |
| T2 recall | 95.1% |
| T1+T2 recall | 98.2% |

## Missing from auto-derived (in baseline T1, not in derived T1) — 2

- LLC_BI__Branch__c
- LLC_BI__Product_Type__c

## Missing from auto-derived T2 — 4

- LLC_BI__Spread_Statement_Period__c
- LLC_BI__Treasury_Service__c
- LLC_BI__Covenant2__c
- LLC_BI__ClosingChecklist__c

## Missing from T1+T2 combined — 2

- LLC_BI__Covenant2__c
- LLC_BI__ClosingChecklist__c

## Extras (auto-derived but not in baseline) — 1

- LLC_BI__Underwriting_Bundle__c

## Top 30 derived T1 with scores

| rank | api_name | namespace | in | out | rt | manifest | score |
|---|---|---|---|---|---|---|---|
| 1 | Account | std | 95 | 6 | ✓ | ✓ | 233.0 |
| 2 | LLC_BI__Loan__c | LLC_BI | 71 | 21 | ✓ | ✓ | 192.5 |
| 3 | Contact | std | 38 | 5 | ✓ | ✓ | 118.5 |
| 4 | LLC_BI__Deposit__c | LLC_BI | 25 | 14 | ✓ | ✓ | 97.0 |
| 5 | LLC_BI__Treasury_Service__c | LLC_BI | 26 | 29 |  | ✓ | 96.5 |
| 6 | LLC_BI__Product__c | LLC_BI | 26 | 8 | ✓ | ✓ | 96.0 |
| 7 | LLC_BI__Product_Package__c | LLC_BI | 24 | 13 | ✓ | ✓ | 94.5 |
| 8 | LLC_BI__Collateral__c | LLC_BI | 21 | 10 | ✓ | ✓ | 87.0 |
| 9 | LLC_BI__Legal_Entities__c | LLC_BI | 14 | 9 | ✓ | ✓ | 72.5 |
| 10 | LLC_BI__Spread_Statement_Period__c | LLC_BI | 15 | 10 |  | ✓ | 65.0 |
| 11 | LLC_BI__Application__c | LLC_BI | 13 | 15 |  | ✓ | 63.5 |
| 12 | LLC_BI__Spread_Statement_Record__c | LLC_BI | 12 | 7 |  | ✓ | 57.5 |
| 13 | Opportunity | std | 5 | 7 | ✓ | ✓ | 53.5 |
| 14 | LLC_BI__Underwriting_Bundle__c | LLC_BI | 10 | 6 |  | ✓ | 53.0 |
| 15 | LLC_BI__DocType__c | LLC_BI | 10 | 2 |  | ✓ | 51.0 |
| 16 | LLC_BI__Requirement__c | LLC_BI | 10 | 2 |  | ✓ | 51.0 |
| 17 | LLC_BI__ClosingChecklist__c | LLC_BI | 9 | 5 |  | ✓ | 50.5 |
| 18 | LLC_BI__Covenant2__c | LLC_BI | 8 | 7 |  | ✓ | 49.5 |
| 19 | LLC_BI__Product_Type__c | LLC_BI | 8 | 6 |  | ✓ | 49.0 |
| 20 | LLC_BI__Spread_Statement_Record_Total__c | LLC_BI | 9 | 2 |  | ✓ | 49.0 |
| 21 | LLC_BI__DocManager__c | LLC_BI | 9 | 0 |  | ✓ | 48.0 |
| 22 | LLC_BI__Spread_Statement_Type__c | LLC_BI | 7 | 8 |  | ✓ | 48.0 |
| 23 | LLC_BI__Fee__c | LLC_BI | 1 | 11 | ✓ | ✓ | 47.5 |
| 24 | LLC_BI__Review__c | LLC_BI | 3 | 3 | ✓ | ✓ | 47.5 |
| 25 | LLC_BI__Branch__c | LLC_BI | 8 | 2 |  | ✓ | 47.0 |
| 26 | LLC_BI__DocTab__c | LLC_BI | 8 | 1 |  | ✓ | 46.5 |
| 27 | LLC_BI__Pricing_Option__c | LLC_BI | 6 | 9 |  | ✓ | 46.5 |
| 28 | LLC_BI__Risk_Grade_Template__c | LLC_BI | 8 | 1 |  | ✓ | 46.5 |
| 29 | LLC_BI__Annual_Review__c | LLC_BI | 2 | 4 | ✓ | ✓ | 46.0 |
| 30 | LLC_BI__DocClass__c | LLC_BI | 7 | 2 |  | ✓ | 45.0 |
