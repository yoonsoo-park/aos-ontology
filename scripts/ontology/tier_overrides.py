"""Manual tier overrides on top of auto-derived tiers.

The auto-derive algorithm in `tier_deriver.py` reaches ~50% recall vs the
hardcoded baseline because:

1. Some baseline objects (e.g. `LLC_BI__Deposit_Product__c`,
   `LLC_BI__Beneficial_Owner__c`) don't exist in the dm-amer metadata at
   all — no algorithm can reach them.
2. ~40% of baseline objects have no manifest signal and low in_degree
   (orphan-like in the schema graph), so scoring can't rank them above
   higher-degree non-business LLC_BI objects.
3. Standard objects like `Campaign` aren't in the manifest and have
   in_degree=0 — purely curation-driven inclusions.

This file documents *why* each entry exists. When metadata changes upstream
or auto-derive heuristics improve, prune entries that auto-derive starts
to catch on its own.

Lists below preserve the baseline T1/T2 split: FORCE_T1 is the subset of
the original hardcoded T1 that auto-derive misses, FORCE_T2 likewise for T2.
This guarantees the override layer maintains parity with the
domain-expert-curated baseline.

See issue #2: https://github.com/yoonsoo-park/aos-ontology/issues/2
"""

from __future__ import annotations

# --- Force-include in TIER 1 ------------------------------------------------
# Baseline-T1 entries auto-derive misses entirely.
# (See validation report for why each one fails the auto algorithm.)
FORCE_T1: list[str] = [
    "LLC_BI__Collateral_Group__c",
    "LLC_BI__Account_Collateral__c",
    "LLC_BI__Covenant__c",
    "LLC_BI__Account_Covenant__c",
    "LLC_BI__Product_Line__c",
    "LLC_BI__Connection__c",
    "LLC_BI__Connection_Role__c",
    "LLC_BI__Loan_Compliance__c",
    "LLC_BI__Annual_Review__c",
    "LLC_BI__Checklist__c",
    "LLC_BI__AccountDocument__c",
    "LLC_BI__Deposit_Product__c",       # NOT in metadata — keep until upstream adds
    "LLC_BI__Address__c",
    "LLC_BI__Loan_Detail__c",
    "LLC_BI__Adverse_Action__c",
    "LLC_BI__Beneficial_Owner__c",      # NOT in metadata — keep until upstream adds
    "LLC_BI__Pricing_Stream__c",
    "LLC_BI__Classification__c",
]

# --- Force-include in TIER 2 ------------------------------------------------
# Baseline-T2 entries auto-derive misses. Mostly low-degree LLC_BI
# subdomain entities (collateral / credit / treasury / covenants) plus
# standard CRM objects (Lead/Case/Campaign).
FORCE_T2: list[str] = [
    # --- Loan lifecycle ---
    "LLC_BI__Loan_Collateral__c",
    "LLC_BI__Loan_Modification__c",
    "LLC_BI__Loan_Risk_Review__c",
    "LLC_BI__LoanTeam__c",
    "LLC_BI__Product_Package__c",
    "LLC_BI__Selected_Product__c",
    "LLC_BI__Booking_Action__c",
    "LLC_BI__Automated_Booking_Status__c",
    "LLC_BI__Fee__c",
    # --- Credit / underwriting ---
    "LLC_BI__Credit_Decision__c",
    "LLC_BI__Credit_Report__c",
    "LLC_BI__Credit_Analysis_Summary__c",
    "LLC_BI__Credit_Protection__c",
    "LLC_BI__Scorecard_Detail__c",
    "LLC_BI__Financial_Report__c",
    # --- Collateral subdomain ---
    "LLC_BI__Collateral_History__c",
    "LLC_BI__Lien__c",
    "LLC_BI__Real_Estate_Property_Details__c",
    "LLC_BI__Titled_Property_Details__c",
    "LLC_BI__UCC_Property_Details__c",
    "Insurance__c",
    # --- Treasury services ---
    "LLC_BI__Treasury_Service_Involvement__c",
    "LLC_BI__Cash_Service__c",
    "LLC_BI__Automated_Clearing_House_Service__c",
    "LLC_BI__Depository_Service__c",
    "LLC_BI__Disbursement_Service__c",
    "LLC_BI__Lockbox_Service__c",
    "LLC_BI__Sweep_Service__c",
    # --- Covenants ---
    "LLC_BI__Covenant_Compliance__c",
    "LLC_BI__Covenant_Rule__c",
    "LLC_BI__Covenant_Product__c",
    # --- Documents ---
    "LLC_BI__ClosingDocument__c",
    "LLC_BI__Document_Store__c",
    # --- Customer / account ---
    "LLC_BI__Account_Demographic__c",
    "LLC_BI__Contact_Demographic__c",
    "LLC_BI__Authorized_Account__c",
    "LLC_BI__Beneficiary__c",
    "LLC_BI__Participation__c",
    # --- Pricing ---
    "LLC_BI__Pricing_Matrix__c",
    "LLC_BI__Rate__c",
    # --- Deposit ---
    "LLC_BI__Deposit_Compliance__c",
    "LLC_BI__CUSO__c",
    # --- nSBA ---
    "nSBA__SBA_Loan__c",
    "nSBA__SBA_Account_Detail__c",
    "nSBA__SBA_Loan_Purpose__c",
    "nSBA__SBA_Field_Office__c",
    # --- Standard CRM ---
    "Lead",
    "Case",
    "Campaign",
    # --- Lower-degree baseline T2 entries ---
    "LLC_BI__Loan_Collateral2__c",
    "LLC_BI__Loan_Collateral_Aggregate__c",
    "LLC_BI__Loan_Covenant__c",
    "LLC_BI__LoanRenewal__c",
    "LLC_BI__Product_Feature__c",
    "LLC_BI__Credit_Memo_Modifcation__c",
    "LLC_BI__Scorecard__c",
    "LLC_BI__Collateral_Valuation__c",
    "LLC_BI__Spread__c",
    "LLC_BI__Budget_Line_Item__c",
    "LLC_BI__Wire_Service__c",
    "LLC_BI__Covenant_Type__c",
    "LLC_BI__Authorized_User__c",
    "LLC_BI__Bill_Point__c",
    "nSBA__Use_Of_Proceeds__c",
    # --- Additional baseline T2 entries auto-derive ranks below cutoff ---
    "LLC_BI__Contingent_Liabilty__c",
    "LLC_BI__Credit_Memo__c",
    "LLC_BI__Debt__c",
    "LLC_BI__Debt_Schedule__c",
    "LLC_BI__Collateral_Type__c",
    "LLC_BI__Budget__c",
    "LLC_BI__DocClass__c",
    "LLC_BI__Analyzed_Account__c",
    "LLC_BI__Profitability__c",
    "LLC_BI__Branch__c",
    "LLC_BI__Product_Type__c",
    "LLC_BI__DocManager__c",
    "LLC_BI__Pricing_Option__c",
]

# --- Force-exclude from all tiers -------------------------------------------
# Objects auto-derive ranks high but domain experts excluded from baseline.
FORCE_EXCLUDE: list[str] = [
    # (none yet — populate after first validation pass)
]
