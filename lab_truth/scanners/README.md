# 850 Lab Report Scanners

**One bureau, one scanner. No cross-bureau logic.**

---

## TransUnion Scanner Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     RAW REPORT TEXT                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   BUREAU ID GATE                            │
│                                                             │
│  • Detects exactly one bureau from markers                  │
│  • RED LIGHT if no bureau or multiple bureaus               │
│  • Must pass before any scanning begins                     │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  Gate Passed?     │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         TRANSUNION      EXPERIAN        EQUIFAX
              │               │               │
              ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                TRANSUNION SCANNER                           │
│                                                             │
│  Extracts:                                                  │
│  • Consumer Identity (name, SSN, DOB, addresses)            │
│  • Employment (if present)                                  │
│  • Credit Scores (if present)                               │
│  • Accounts/Tradelines                                      │
│  • Inquiries (hard + soft)                                  │
│  • Public Records                                           │
│  • Collections                                              │
│  • Consumer Statements                                      │
│  • Alerts (fraud, active duty, freeze)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  TRUTH SHEET OUTPUT                         │
│                                                             │
│  • Every field has: value, confidence, receipt              │
│  • Missing data → NOT_FOUND (no guessing)                   │
│  • Validated against Truth Template                         │
│  • RED LIGHT if validation fails                            │
└─────────────────────────────────────────────────────────────┘
```

┌─────────────────────────────────────────────────────────────┐
│                 EXPERIAN SCANNER                            │
│                                                             │
│  Experian-Specific Layout:                                  │
│  • "Creditor Name" (not "Subscriber Name")                  │
│  • "Requests Viewed by Others" = Hard Inquiries             │
│  • "Requests Viewed Only By You" = Soft Inquiries           │
│                                                             │
│  Extracts same sections as TransUnion:                      │
│  • Consumer Identity, Employment, Credit Scores             │
│  • Accounts/Tradelines, Inquiries (hard + soft)             │
│  • Public Records, Collections, Statements, Alerts          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 EQUIFAX HANDLER                             │
│                                                             │
│  Status: NOT SUPPORTED YET                                  │
│                                                             │
│  What happens:                                              │
│  • Confirms report is from Equifax (with receipt)           │
│  • All sections marked as NOT_FOUND                         │
│  • Returns Red Light with clear message                     │
│  • User is informed, not blocked by error                   │
│                                                             │
│  Why not parse yet:                                         │
│  • Equifax has different layouts                            │
│  • Need verified patterns before extracting                 │
│  • No guessing — partial truth is worse than no truth       │
└─────────────────────────────────────────────────────────────┘

---

## Usage

### Basic TransUnion Scan

```python
from lab_truth.scanners import scan_transunion_report

# After extracting text from PDF...
result = scan_transunion_report(raw_text)

if result.success:
    truth_sheet = result.truth_sheet
    
    # Access extracted data
    bureau = truth_sheet["meta"]["bureau"]["value"]  # "TRANSUNION"
    name = truth_sheet["consumer_identity"]["full_name"]["value"]
    score = truth_sheet["credit_scores"]["score"]["value"]
    
    # Check number of accounts
    account_count = truth_sheet["accounts"]["_marker"]["item_count"]
    
    # Iterate over accounts
    for account in truth_sheet["accounts"]["items"]:
        creditor = account["creditor_name"]["value"]
        balance = account["current_balance"]["value"]
        print(f"{creditor}: ${balance}")
else:
    # Scanner hit a Red Light
    print(f"Scan failed: {result.red_light_reason}")
```

### Basic Experian Scan

```python
from lab_truth.scanners import scan_experian_report

result = scan_experian_report(raw_text)

if result.success:
    truth_sheet = result.truth_sheet
    
    # Access extracted data
    bureau = truth_sheet["meta"]["bureau"]["value"]  # "EXPERIAN"
    name = truth_sheet["consumer_identity"]["full_name"]["value"]
    score = truth_sheet["credit_scores"]["score"]["value"]
    
    # Experian separates inquiries clearly
    hard_count = len(truth_sheet["inquiries"]["hard_inquiries"])
    soft_count = len(truth_sheet["inquiries"]["soft_inquiries"])
    print(f"Hard inquiries: {hard_count}, Soft: {soft_count}")
else:
    print(f"Scan failed: {result.red_light_reason}")
```

### Equifax Report (Not Yet Supported)

```python
from lab_truth.scanners import handle_equifax_report

result = handle_equifax_report(raw_text)

# Equifax always triggers Red Light (not supported yet)
if result.red_light:
    print(result.red_light_reason)
    # "Equifax scanning is not yet active. We identified this as an 
    #  Equifax report, but we cannot extract data from it yet.
    #  No guessing — we only scan what we can verify."

# Truth Sheet is still valid, just all NOT_FOUND
if result.truth_sheet:
    bureau = result.truth_sheet["meta"]["bureau"]["value"]  # "EQUIFAX"
    # All other fields are NOT_FOUND
```

### With Bureau Gate Pre-Check

```python
from lab_truth.bureau_detector import gate_check
from lab_truth.scanners import TransUnionScanner, ExperianScanner, EquifaxHandler

# Step 1: Run the Bureau ID Gate
gate_result = gate_check(raw_text)

if not gate_result["passed"]:
    print(f"Gate failed: {gate_result['error']['reason']}")
    exit()

if gate_result["bureau"] != "TRANSUNION":
    print(f"Wrong bureau: {gate_result['bureau']}")
    exit()

# Step 2: Scan with TransUnion scanner
scanner = TransUnionScanner(raw_text)
result = scanner.scan(bureau_gate_result=gate_result)

if result.success:
    # Process truth_sheet...
    pass
```

---

## What the Scanner Extracts

### Meta Section
| Field | Description |
|-------|-------------|
| bureau | "TRANSUNION" with HIGH confidence |
| report_date | Date the report was generated |
| file_id | TransUnion file number |
| report_type | "Consumer Disclosure" etc. |
| scanned_at | When we scanned it |

### Consumer Identity
| Field | Description |
|-------|-------------|
| full_name | Consumer's name as shown |
| ssn_last_four | Last 4 digits of SSN |
| date_of_birth | DOB from report |
| current_address | Current residence |
| previous_addresses | Array of past addresses |
| phone_numbers | Array of phone numbers |
| aka_names | Array of aliases |

### Accounts (Tradelines)
Each account includes:
- creditor_name, account_number, account_type
- account_status, responsibility
- date_opened, date_closed, date_last_active, date_first_delinquency
- credit_limit, high_balance, current_balance
- payment_status, past_due_amount, monthly_payment, terms
- last_payment_date, last_reported_date
- dispute_status
- payment_history (array of month/status entries)
- remarks (array)

### Inquiries
- hard_inquiries: Array of inquiries from credit applications
- soft_inquiries: Array of promotional/account review inquiries

Each inquiry has: inquiry_date, creditor_name, inquiry_type

### Other Sections
- **employment**: Employer info if present
- **credit_scores**: Score, model, range, factors
- **public_records**: Bankruptcies, judgments, liens
- **collections**: Collection accounts
- **consumer_statements**: Statements added by consumer
- **alerts**: Fraud alerts, active duty alerts, freeze status

---

## Red Light Conditions

The scanner will stop with a Red Light if:

1. **Bureau Gate Fails** - No bureau or multiple bureaus detected
2. **Wrong Bureau** - Report is from Experian or Equifax
3. **Validation Fails** - Truth Sheet doesn't match template

Red Light errors return structured data (not crashes):

```python
if result.red_light:
    print(result.red_light_reason)
    # "Red Light Rule: This scanner is for TransUnion only..."
```

---

## Receipt Tracking

Every extracted value includes a receipt showing where it came from:

```python
account = truth_sheet["accounts"]["items"][0]

print(account["creditor_name"])
# {
#   "value": "CHASE BANK USA",
#   "how_sure_we_are": "HIGH",
#   "receipt": {
#     "page": "3",
#     "section": "Account Information",
#     "snippet": "...Subscriber Name: CHASE BANK USA..."
#   }
# }
```

If a value wasn't found:

```python
print(account["date_closed"])
# {
#   "value": "NOT_FOUND",
#   "how_sure_we_are": "NOT_FOUND",
#   "receipt": null
# }
```

---

*Remember: If it's not clearly on the report, we say NOT_FOUND. No guessing.*
