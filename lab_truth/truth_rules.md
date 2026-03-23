# 850 Lab Truth Sheet Rules

**The Golden Rule: If it ain't on the report, we don't make it up.**

---

## What is the Truth Sheet?

The Truth Sheet is our honest record of what we found (and didn't find) on a credit report. Every piece of data has receipts. No guessing. No filler. No "best guesses."

---

## The Three Laws of Truth

### Law 1: Every Field Lives
Every field in the Truth Template must exist in your output. No skipping fields because you "didn't need them." If it's in the template, it's in your output.

**Wrong:** Leaving out `date_closed` because the account is open.
**Right:** Setting `date_closed.value` to `"NOT_FOUND"` with `how_sure_we_are: "NOT_FOUND"`

### Law 2: Every Value Has Receipts
If you say you found something, you better be able to point to exactly where on the report. No receipt? No claim.

Every truth field has three parts:
- **value** - What you actually found (or `"NOT_FOUND"`)
- **how_sure_we_are** - Your confidence level
- **receipt** - Where you found it (page, section, snippet)

### Law 3: No Guessing, Ever (The Red Light Rule)
If the report doesn't clearly say it, we don't fill it in. Period.

🚫 **Red Light Violations:**
- Calculating a date based on "common practice"
- Assuming an account type because "it looks like a credit card"
- Filling in a creditor name from memory
- Guessing a status because "it's probably closed by now"
- Inferring date_first_delinquency from other dates

---

## Confidence Levels (how_sure_we_are)

| Level | What it means | When to use it |
|-------|---------------|----------------|
| **HIGH** | Crystal clear on the report | The value is printed plain as day, no ambiguity |
| **MED** | Found it, but there's some fuzziness | OCR might have struggled, or formatting is weird |
| **LOW** | We found something, but we're not confident | Text is garbled, multiple possible values, unclear context |
| **NOT_FOUND** | Not on the report | Searched and couldn't find it anywhere |

**Rule:** If `how_sure_we_are` is `NOT_FOUND`, then `value` must be `"NOT_FOUND"` and `receipt` must be `null`.

---

## Receipt Requirements

Every receipt needs:
- **page** - Page number or section identifier (can be `"1"`, `"Page 3"`, `"Summary Section"`)
- **section** - What part of the page (`"Account Details"`, `"Payment History"`, `"Personal Information"`)
- **snippet** - The actual text you're referencing (copy it exactly!)

**Good Receipt:**
```json
{
  "page": "2",
  "section": "Account Information",
  "snippet": "Account Status: OPEN"
}
```

**Bad Receipt:**
```json
{
  "page": null,
  "section": null,
  "snippet": "I think it said open somewhere"
}
```

---

## Section Markers (The Scoreboard)

Every array section now has a **_marker** that tells us:
- `section_found`: Did this section exist on the report at all?
- `item_count`: How many items did we find?
- `receipt`: Where we found the section header

**Why?** Because "no collections found" is different from "couldn't find the collections section."

**Example - Collections section exists but is empty:**
```json
{
  "_marker": {
    "section_found": true,
    "item_count": 0,
    "receipt": {
      "page": "5",
      "section": "Collection Accounts"
    }
  },
  "items": []
}
```

**Example - Collections section not on report:**
```json
{
  "_marker": {
    "section_found": false,
    "item_count": 0,
    "receipt": null
  },
  "items": []
}
```

---

## Mismatch Alerts

The validator will throw a **Mismatch Alert** if:

1. **Missing Field** - A required field from the template is missing
2. **Bad Confidence** - `how_sure_we_are` isn't one of: `LOW`, `MED`, `HIGH`, `NOT_FOUND`
3. **Receipt Without Value** - You have a receipt but `value` is `NOT_FOUND`
4. **Value Without Receipt** - You have a value but no receipt (and it's not `NOT_FOUND`)
5. **Phantom Field** - You added a field that's not in the template
6. **Confidence Mismatch** - `value` is `NOT_FOUND` but `how_sure_we_are` isn't `NOT_FOUND`
7. **Bad Section Marker** - Array section missing `_marker` or `item_count` doesn't match array length
8. **Empty Receipt** - Receipt exists but has no page, section, or snippet

---

## Required Sections

Every Truth Sheet MUST have these sections:

| Section | What's in it |
|---------|--------------|
| **meta** | Bureau name, report date, file ID, report type |
| **consumer_identity** | Name, SSN last 4, DOB, addresses, phones, AKAs |
| **employment** | Employers reported on file |
| **credit_scores** | Score, model, range, factors |
| **accounts** | All tradelines (credit cards, loans, mortgages) |
| **inquiries** | Hard and soft inquiries |
| **public_records** | Bankruptcies, judgments, liens |
| **collections** | Collection accounts |
| **consumer_statements** | Statements the consumer added |
| **alerts** | Fraud alerts, active duty alerts, freezes |

---

## Key Account Fields

Each account must track these fields (or mark them NOT_FOUND):

- `creditor_name` - Who reports this account
- `account_number` - Usually masked
- `account_type` - Revolving, Installment, Mortgage, etc.
- `account_status` - Open, Closed, ChargeOff, etc.
- `responsibility` - Individual, Joint, Authorized User, Cosigner
- `date_opened` - When account was opened
- `date_closed` - When closed (NOT_FOUND if still open)
- `date_last_active` - Last activity date
- `date_first_delinquency` - CRITICAL for 7-year clock
- `credit_limit` / `high_balance`
- `current_balance`
- `payment_status` - Current, 30, 60, 90, 120
- `past_due_amount`
- `monthly_payment`
- `terms` - Loan term or "Revolving"
- `dispute_status` - Is it being disputed?
- `payment_history` - Month-by-month status grid
- `remarks` - Special comments on the account

---

## Example Truth Field

**Found on the report:**
```json
{
  "value": "CHASE BANK USA",
  "how_sure_we_are": "HIGH",
  "receipt": {
    "page": "3",
    "section": "Revolving Accounts",
    "snippet": "Creditor Name: CHASE BANK USA"
  }
}
```

**Not found on the report:**
```json
{
  "value": "NOT_FOUND",
  "how_sure_we_are": "NOT_FOUND",
  "receipt": null
}
```

---

## The Scanner Promise

When the 850 Lab scanner processes a credit report, it promises:

1. ✅ Output matches the Truth Template exactly
2. ✅ Every field exists (no missing pieces)
3. ✅ Every found value has a receipt
4. ✅ No guessed or inferred values
5. ✅ Clear confidence levels on everything
6. ✅ Section markers track what sections exist
7. ✅ Fails loudly if something's wrong (no silent errors)

---

## Quick Reference

| Situation | value | how_sure_we_are | receipt |
|-----------|-------|-----------------|---------|
| Clear text on report | Exact value | HIGH | Full receipt |
| Fuzzy/unclear text | Best read | MED or LOW | Full receipt |
| Not on report at all | "NOT_FOUND" | NOT_FOUND | null |

---

*Remember: The Truth Sheet is our foundation. If we build on lies, everything falls apart. Keep it honest.*
