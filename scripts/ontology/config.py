from pathlib import Path

DEFAULT_METADATA_ROOT = Path("/Users/yoonsoo.park/code/ncino/Demo-Master/orgMetadata/main/default/objects")

OBJECT_TIERS: dict[int, list[str]] = {
    1: [
        "Account",
        "Contact",
        "LLC_BI__Loan__c",
        "LLC_BI__Application__c",
        "LLC_BI__Collateral__c",
        "LLC_BI__Collateral_Group__c",
        "LLC_BI__Account_Collateral__c",
        "LLC_BI__Covenant__c",
        "LLC_BI__Account_Covenant__c",
        "LLC_BI__Branch__c",
        "LLC_BI__Product__c",
        "LLC_BI__Product_Line__c",
        "LLC_BI__Product_Type__c",
        "LLC_BI__Connection__c",
        "LLC_BI__Connection_Role__c",
        "LLC_BI__Legal_Entities__c",
        "LLC_BI__Loan_Compliance__c",
        "LLC_BI__Annual_Review__c",
        "LLC_BI__Checklist__c",
        "LLC_BI__AccountDocument__c",
        "LLC_BI__Deposit__c",
        "LLC_BI__Deposit_Product__c",
        "LLC_BI__Address__c",
        "LLC_BI__Loan_Detail__c",
        "LLC_BI__Adverse_Action__c",
        "LLC_BI__Beneficial_Owner__c",
        "LLC_BI__Pricing_Stream__c",
        "LLC_BI__Classification__c",
    ],
    2: [
        # Loan Lifecycle
        "LLC_BI__Loan_Collateral__c",
        "LLC_BI__Loan_Collateral2__c",
        "LLC_BI__Loan_Collateral_Aggregate__c",
        "LLC_BI__Loan_Covenant__c",
        "LLC_BI__Loan_Modification__c",
        "LLC_BI__LoanRenewal__c",
        "LLC_BI__Loan_Risk_Review__c",
        "LLC_BI__LoanTeam__c",
        "LLC_BI__Product_Package__c",
        "LLC_BI__Product_Feature__c",
        "LLC_BI__Selected_Product__c",
        "LLC_BI__Booking_Action__c",
        "LLC_BI__Automated_Booking_Status__c",
        "LLC_BI__Fee__c",
        "LLC_BI__Contingent_Liabilty__c",
        # Credit & Underwriting
        "LLC_BI__Credit_Memo__c",
        "LLC_BI__Credit_Decision__c",
        "LLC_BI__Credit_Report__c",
        "LLC_BI__Credit_Analysis_Summary__c",
        "LLC_BI__Credit_Protection__c",
        "LLC_BI__Credit_Memo_Modifcation__c",
        "LLC_BI__Scorecard__c",
        "LLC_BI__Scorecard_Detail__c",
        "LLC_BI__Debt__c",
        "LLC_BI__Debt_Schedule__c",
        # Collateral Extended
        "LLC_BI__Collateral_Type__c",
        "LLC_BI__Collateral_Valuation__c",
        "LLC_BI__Collateral_History__c",
        "LLC_BI__Lien__c",
        "LLC_BI__Real_Estate_Property_Details__c",
        "LLC_BI__Titled_Property_Details__c",
        "LLC_BI__UCC_Property_Details__c",
        "Insurance__c",
        # Financial Analysis
        "LLC_BI__Spread__c",
        "LLC_BI__Spread_Statement_Period__c",
        "LLC_BI__Spread_Statement_Record__c",
        "LLC_BI__Financial_Report__c",
        "LLC_BI__Budget__c",
        "LLC_BI__Budget_Line_Item__c",
        # Treasury
        "LLC_BI__Treasury_Service__c",
        "LLC_BI__Treasury_Service_Involvement__c",
        "LLC_BI__Cash_Service__c",
        "LLC_BI__Automated_Clearing_House_Service__c",
        "LLC_BI__Depository_Service__c",
        "LLC_BI__Disbursement_Service__c",
        "LLC_BI__Wire_Service__c",
        "LLC_BI__Lockbox_Service__c",
        "LLC_BI__Sweep_Service__c",
        # Covenant Extended
        "LLC_BI__Covenant_Compliance__c",
        "LLC_BI__Covenant_Type__c",
        "LLC_BI__Covenant_Rule__c",
        "LLC_BI__Covenant_Product__c",
        "LLC_BI__Covenant2__c",
        # Document Management
        "LLC_BI__ClosingChecklist__c",
        "LLC_BI__ClosingDocument__c",
        "LLC_BI__DocClass__c",
        "LLC_BI__DocManager__c",
        "LLC_BI__Document_Store__c",
        # Relationship Extended
        "LLC_BI__Account_Demographic__c",
        "LLC_BI__Contact_Demographic__c",
        "LLC_BI__Authorized_Account__c",
        "LLC_BI__Authorized_User__c",
        "LLC_BI__Beneficiary__c",
        "LLC_BI__Analyzed_Account__c",
        # Participation & Pricing
        "LLC_BI__Participation__c",
        "LLC_BI__Profitability__c",
        "LLC_BI__Pricing_Option__c",
        "LLC_BI__Pricing_Matrix__c",
        "LLC_BI__Rate__c",
        # Compliance Extended
        "LLC_BI__Deposit_Compliance__c",
        "LLC_BI__CUSO__c",
        "LLC_BI__Bill_Point__c",
        # nSBA
        "nSBA__SBA_Loan__c",
        "nSBA__SBA_Account_Detail__c",
        "nSBA__Use_Of_Proceeds__c",
        "nSBA__SBA_Loan_Purpose__c",
        "nSBA__SBA_Field_Office__c",
        # Standard SF
        "Opportunity",
        "Lead",
        "Case",
        "Campaign",
    ],
}

TIER_1_OBJECTS = OBJECT_TIERS[1]


def get_objects_for_tier(tier: int) -> list[str]:
    result: list[str] = []
    for t in range(1, tier + 1):
        result.extend(OBJECT_TIERS.get(t, []))
    return result


KNOWN_NAMESPACES: dict[str, str] = {
    "LLC_BI": "Core Banking (Loans, Accounts, Compliance)",
    "nFORCE": "UI Framework",
    "nFORMS": "Forms Engine",
    "nSBA": "SBA Lending",
    "FinServ": "Financial Services Cloud",
    "nCRED": "Credit",
    "nDOC": "Document Management",
    "nIQ": "nCino IQ / Analytics",
}

DOMAIN_MAPPING: dict[str, str] = {
    # --- Tier 1 ---
    # Loan Origination
    "LLC_BI__Loan__c": "loan-origination",
    "LLC_BI__Application__c": "loan-origination",
    "LLC_BI__Loan_Detail__c": "loan-origination",
    "LLC_BI__Product__c": "loan-origination",
    "LLC_BI__Product_Line__c": "loan-origination",
    "LLC_BI__Product_Type__c": "loan-origination",
    "LLC_BI__Pricing_Stream__c": "loan-origination",
    # Collateral Management
    "LLC_BI__Collateral__c": "collateral-management",
    "LLC_BI__Collateral_Group__c": "collateral-management",
    "LLC_BI__Account_Collateral__c": "collateral-management",
    # Credit Management
    "LLC_BI__Covenant__c": "credit-management",
    "LLC_BI__Account_Covenant__c": "credit-management",
    "LLC_BI__Classification__c": "credit-management",
    "LLC_BI__Annual_Review__c": "credit-management",
    # Compliance
    "LLC_BI__Loan_Compliance__c": "compliance",
    "LLC_BI__Adverse_Action__c": "compliance",
    # Relationship Management
    "LLC_BI__Connection__c": "relationship-management",
    "LLC_BI__Connection_Role__c": "relationship-management",
    "LLC_BI__Legal_Entities__c": "relationship-management",
    "LLC_BI__Beneficial_Owner__c": "relationship-management",
    "Account": "relationship-management",
    "Contact": "relationship-management",
    # Organization
    "LLC_BI__Branch__c": "organization",
    # Workflow
    "LLC_BI__Checklist__c": "workflow",
    # Document Management
    "LLC_BI__AccountDocument__c": "document-management",
    # Deposit Management
    "LLC_BI__Deposit__c": "deposit-management",
    "LLC_BI__Deposit_Product__c": "deposit-management",
    # Shared
    "LLC_BI__Address__c": "shared",
    # --- Tier 2 ---
    # Loan Origination (extended)
    "LLC_BI__Loan_Collateral__c": "loan-origination",
    "LLC_BI__Loan_Collateral2__c": "loan-origination",
    "LLC_BI__Loan_Collateral_Aggregate__c": "loan-origination",
    "LLC_BI__Loan_Covenant__c": "loan-origination",
    "LLC_BI__Loan_Modification__c": "loan-origination",
    "LLC_BI__LoanRenewal__c": "loan-origination",
    "LLC_BI__LoanTeam__c": "loan-origination",
    "LLC_BI__Product_Package__c": "loan-origination",
    "LLC_BI__Product_Feature__c": "loan-origination",
    "LLC_BI__Selected_Product__c": "loan-origination",
    "LLC_BI__Booking_Action__c": "loan-origination",
    "LLC_BI__Automated_Booking_Status__c": "loan-origination",
    "LLC_BI__Fee__c": "loan-origination",
    "LLC_BI__Contingent_Liabilty__c": "loan-origination",
    # Underwriting (new domain)
    "LLC_BI__Credit_Memo__c": "underwriting",
    "LLC_BI__Credit_Decision__c": "underwriting",
    "LLC_BI__Credit_Report__c": "underwriting",
    "LLC_BI__Credit_Analysis_Summary__c": "underwriting",
    "LLC_BI__Credit_Protection__c": "underwriting",
    "LLC_BI__Credit_Memo_Modifcation__c": "underwriting",
    "LLC_BI__Scorecard__c": "underwriting",
    "LLC_BI__Scorecard_Detail__c": "underwriting",
    # Risk Management (new domain)
    "LLC_BI__Loan_Risk_Review__c": "risk-management",
    "LLC_BI__Debt__c": "risk-management",
    "LLC_BI__Debt_Schedule__c": "risk-management",
    # Collateral Management (extended)
    "LLC_BI__Collateral_Type__c": "collateral-management",
    "LLC_BI__Collateral_Valuation__c": "collateral-management",
    "LLC_BI__Collateral_History__c": "collateral-management",
    "LLC_BI__Lien__c": "collateral-management",
    "LLC_BI__Real_Estate_Property_Details__c": "collateral-management",
    "LLC_BI__Titled_Property_Details__c": "collateral-management",
    "LLC_BI__UCC_Property_Details__c": "collateral-management",
    "Insurance__c": "collateral-management",
    # Financial Analysis (new domain)
    "LLC_BI__Spread__c": "financial-analysis",
    "LLC_BI__Spread_Statement_Period__c": "financial-analysis",
    "LLC_BI__Spread_Statement_Record__c": "financial-analysis",
    "LLC_BI__Financial_Report__c": "financial-analysis",
    "LLC_BI__Budget__c": "financial-analysis",
    "LLC_BI__Budget_Line_Item__c": "financial-analysis",
    # Treasury Management (new domain)
    "LLC_BI__Treasury_Service__c": "treasury-management",
    "LLC_BI__Treasury_Service_Involvement__c": "treasury-management",
    "LLC_BI__Cash_Service__c": "treasury-management",
    "LLC_BI__Automated_Clearing_House_Service__c": "treasury-management",
    "LLC_BI__Depository_Service__c": "treasury-management",
    "LLC_BI__Disbursement_Service__c": "treasury-management",
    "LLC_BI__Wire_Service__c": "treasury-management",
    "LLC_BI__Lockbox_Service__c": "treasury-management",
    "LLC_BI__Sweep_Service__c": "treasury-management",
    # Credit Management (extended)
    "LLC_BI__Covenant_Compliance__c": "credit-management",
    "LLC_BI__Covenant_Type__c": "credit-management",
    "LLC_BI__Covenant_Rule__c": "credit-management",
    "LLC_BI__Covenant_Product__c": "credit-management",
    "LLC_BI__Covenant2__c": "credit-management",
    # Document Management (extended)
    "LLC_BI__ClosingChecklist__c": "document-management",
    "LLC_BI__ClosingDocument__c": "document-management",
    "LLC_BI__DocClass__c": "document-management",
    "LLC_BI__DocManager__c": "document-management",
    "LLC_BI__Document_Store__c": "document-management",
    # Relationship Management (extended)
    "LLC_BI__Account_Demographic__c": "relationship-management",
    "LLC_BI__Contact_Demographic__c": "relationship-management",
    "LLC_BI__Authorized_Account__c": "relationship-management",
    "LLC_BI__Authorized_User__c": "relationship-management",
    "LLC_BI__Beneficiary__c": "relationship-management",
    "LLC_BI__Analyzed_Account__c": "relationship-management",
    # Pricing (new domain)
    "LLC_BI__Pricing_Option__c": "pricing",
    "LLC_BI__Pricing_Matrix__c": "pricing",
    "LLC_BI__Rate__c": "pricing",
    # Participation (new domain)
    "LLC_BI__Participation__c": "participation",
    "LLC_BI__Profitability__c": "participation",
    # Compliance (extended)
    "LLC_BI__Deposit_Compliance__c": "compliance",
    "LLC_BI__CUSO__c": "compliance",
    "LLC_BI__Bill_Point__c": "compliance",
    # SBA Lending (new domain)
    "nSBA__SBA_Loan__c": "sba-lending",
    "nSBA__SBA_Account_Detail__c": "sba-lending",
    "nSBA__Use_Of_Proceeds__c": "sba-lending",
    "nSBA__SBA_Loan_Purpose__c": "sba-lending",
    "nSBA__SBA_Field_Office__c": "sba-lending",
    # Sales (new domain)
    "Opportunity": "sales",
    "Lead": "sales",
    "Campaign": "sales",
    # Service (new domain)
    "Case": "service",
}
