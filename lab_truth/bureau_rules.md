# 850 Lab Bureau ID Gate Rules

**The Golden Rule: We do not scan what we can't clearly identify.**

---

## What is the Bureau ID Gate?

Before we even start reading a credit report, we need to know who wrote it. TransUnion, Experian, and Equifax each format their reports differently. If we guess wrong, we read it wrong. Wrong bureau = wrong truth.

The Bureau ID Gate is our checkpoint. Every report must pass through it before scanning begins.

---

## How It Works

### Step 1: Look for Bureau Markers

We search the raw report text for clear bureau identifiers:

| Bureau | What We Look For |
|--------|------------------|
| **TransUnion** | "TransUnion", "TransUnion LLC", "P.O. Box 2000, Chester, PA", "transunion.com", "TU File Number" |
| **Experian** | "Experian", "Experian Information Solutions", "P.O. Box 4500, Allen, TX", "experian.com" |
| **Equifax** | "Equifax", "Equifax Information Services", "P.O. Box 740241, Atlanta, GA", "equifax.com", "EFX File" |

### Step 2: Count What We Found

- **Found markers from exactly ONE bureau** → Gate passes, proceed with scanning
- **Found markers from ZERO bureaus** → Red Light Rule (stop)
- **Found markers from MULTIPLE bureaus** → Red Light Rule (stop)

### Step 3: Record the Receipt

When we identify the bureau, we save:
- Which bureau we found
- How sure we are (based on how many markers we found)
- Where we found it (page, section, exact text)

---

## Red Light Rules

These situations trigger an immediate stop:

### Red Light #1: No Bureau Found
**What happened:** We searched the entire report and couldn't find any bureau markers.

**Why we stop:** This isn't a credit report we recognize, or the text extraction failed badly. We can't guess which bureau format to use.

**Message:** "Could not identify the credit bureau. None of our known markers (TransUnion, Experian, Equifax) were found in this report."

### Red Light #2: Multiple Bureaus Found
**What happened:** We found markers from more than one bureau in the same document.

**Why we stop:** This could be a merged tri-bureau report, a comparison document, or corrupted data. We need exactly one bureau per scan.

**Message:** "Found markers for multiple bureaus. We need exactly one bureau per report."

### Red Light #3: Empty Report
**What happened:** There's no text to analyze.

**Why we stop:** Nothing to scan means nothing to identify.

**Message:** "No report text to analyze. We need actual report content to identify the bureau."

---

## Confidence Levels

After we identify the bureau, we rate our confidence:

| Confidence | What It Means |
|------------|---------------|
| **HIGH** | Found 3 or more bureau markers. Crystal clear. |
| **MED** | Found 2 bureau markers. Pretty sure, but not 100%. |
| **LOW** | Found only 1 bureau marker. We're going with it, but proceed with care. |

---

## What Goes in the Truth Sheet

When the gate passes, the bureau info goes into the Truth Sheet meta section:

```json
{
  "meta": {
    "bureau": {
      "value": "TRANSUNION",
      "how_sure_we_are": "HIGH",
      "receipt": {
        "page": "1",
        "section": "Report Header / Bureau Identification",
        "snippet": "...TransUnion Credit Report File Number..."
      }
    }
  }
}
```

---

## Gate Check Response

The gate returns a structured response (not a crash):

**When Gate Passes:**
```json
{
  "passed": true,
  "bureau": "TRANSUNION",
  "truth_field": { ... },
  "error": null,
  "confidence": "HIGH"
}
```

**When Gate Fails (Red Light):**
```json
{
  "passed": false,
  "bureau": null,
  "truth_field": { "value": "NOT_FOUND", ... },
  "error": {
    "type": "bureau_gate_failed",
    "red_light": true,
    "reason": "Red Light Rule: Could not identify...",
    "bureaus_detected": [],
    "markers_found": []
  }
}
```

---

## Using the Gate

```python
from lab_truth.bureau_detector import gate_check

# Before any scanning
result = gate_check(raw_report_text)

if not result["passed"]:
    # Stop here - don't try to scan
    print(result["error"]["reason"])
    return result["error"]

# Gate passed - proceed with bureau-specific scanning
bureau = result["bureau"]
truth_field = result["truth_field"]
```

---

## Why This Matters

Each bureau formats things differently:
- **Account sections** have different headers
- **Payment history grids** use different layouts
- **Dates and amounts** appear in different places
- **Score sections** vary significantly

If we use TransUnion parsing rules on an Experian report, we'll extract garbage. The Bureau ID Gate ensures we use the right rules for the right report.

---

*Remember: Wrong bureau = wrong truth. Always gate check first.*
