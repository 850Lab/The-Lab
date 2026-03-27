"""
lob_client.py | 850 Lab
Lob integration for sending certified dispute letters via USPS
Uses requests-based REST API (no SDK dependency)
"""

import os
import re
import requests
import base64
from typing import Dict, Optional, Any


LOB_API_BASE = "https://api.lob.com/v1"

BUREAU_STRUCTURED_ADDRESSES = {
    "equifax": {
        "name": "Equifax Information Services LLC",
        "address_line1": "P.O. Box 740256",
        "address_city": "Atlanta",
        "address_state": "GA",
        "address_zip": "30374",
        "address_country": "US",
    },
    "experian": {
        "name": "Experian",
        "address_line1": "P.O. Box 4500",
        "address_city": "Allen",
        "address_state": "TX",
        "address_zip": "75013",
        "address_country": "US",
    },
    "transunion": {
        "name": "TransUnion LLC",
        "address_line1": "P.O. Box 2000",
        "address_city": "Chester",
        "address_state": "PA",
        "address_zip": "19016",
        "address_country": "US",
    },
}

US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU", "AS", "MP",
]

CERTIFIED_MAIL_COST_CENTS = 1099
RETURN_RECEIPT_COST_CENTS = 400


def _get_api_key() -> Optional[str]:
    return os.environ.get("LOB_API_KEY")


def _is_test_key(api_key: str) -> bool:
    return api_key.startswith("test_")


def _auth_header(api_key: str) -> Dict[str, str]:
    encoded = base64.b64encode(f"{api_key}:".encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
    }


def validate_address(addr: Dict[str, str]) -> Dict[str, Any]:
    required = ["name", "address_line1", "address_city", "address_state", "address_zip"]
    missing = [f for f in required if not addr.get(f, "").strip()]
    if missing:
        return {"valid": False, "error": f"Missing: {', '.join(missing)}"}

    if not re.match(r"^\d{5}(-\d{4})?$", addr["address_zip"].strip()):
        return {"valid": False, "error": "ZIP code must be 5 digits (or 5+4 format)"}

    state = addr["address_state"].strip().upper()
    if state not in US_STATES:
        return {"valid": False, "error": f"Invalid state: {state}"}

    return {"valid": True}


def get_bureau_address(bureau: str) -> Optional[Dict[str, str]]:
    return BUREAU_STRUCTURED_ADDRESSES.get(bureau.lower())


def letter_text_to_html(letter_text: str) -> str:
    import html as html_mod
    escaped = html_mod.escape(letter_text)
    lines = escaped.split("\n")
    body_lines = []
    for line in lines:
        if line.strip() == "":
            body_lines.append("<br/>")
        elif line.startswith("FACTUAL DISPUTE"):
            body_lines.append(f'<h2 style="text-align:center;font-size:14px;margin-bottom:16px;">{line}</h2>')
        elif line.startswith("Re:") or line.startswith("Consumer:"):
            body_lines.append(f'<p style="margin:2px 0;"><strong>{line}</strong></p>')
        elif line.startswith("To Whom It May Concern"):
            body_lines.append(f'<p style="margin:12px 0;"><strong>{line}</strong></p>')
        elif line.strip().startswith("Sincerely"):
            body_lines.append(f'<p style="margin-top:24px;">{line}</p>')
        elif line.strip().startswith("___"):
            body_lines.append(f'<p style="margin:4px 0;">{line}</p>')
        elif re.match(r"^\d+\.", line.strip()):
            body_lines.append(f'<p style="margin:4px 0 4px 20px;">{line}</p>')
        else:
            body_lines.append(f'<p style="margin:2px 0;">{line}</p>')

    body = "\n".join(body_lines)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  body {{
    font-family: 'Times New Roman', Times, serif;
    font-size: 11px;
    line-height: 1.4;
    color: #000;
    margin: 0;
    padding: 0;
  }}
  h2 {{ font-family: 'Times New Roman', Times, serif; }}
  p {{ font-family: 'Times New Roman', Times, serif; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024


def _pdf_to_images(pdf_data: bytes) -> list:
    try:
        from pdf2image import convert_from_bytes
        import io
        images = convert_from_bytes(pdf_data, dpi=200, first_page=1, last_page=4)
        result = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            result.append(buf.getvalue())
        return result
    except Exception:
        return []


def _build_attachment_pages_html(attachments: list) -> Dict[str, Any]:
    pages = []
    errors = []
    for att in attachments:
        file_data = att.get("data", b"")
        mime_type = att.get("type", "image/png")
        label = att.get("name", "Attachment")

        if len(file_data) > MAX_ATTACHMENT_BYTES:
            errors.append(f"{label}: file exceeds 5 MB limit")
            continue

        image_blobs = []
        img_mime = "image/png"
        if mime_type == "application/pdf":
            image_blobs = _pdf_to_images(file_data)
            if not image_blobs:
                errors.append(f"{label}: could not process PDF. Please upload as a JPG or PNG image instead.")
                continue
        else:
            image_blobs = [file_data]
            if "jpeg" in mime_type or "jpg" in mime_type:
                img_mime = "image/jpeg"

        for i, blob in enumerate(image_blobs):
            b64 = base64.b64encode(blob).decode()
            page_label = f"{label} (page {i+1})" if len(image_blobs) > 1 else label
            data_uri = f"data:{img_mime};base64,{b64}"
            pages.append(
                f'<div style="page-break-before:always;padding:0.5in;">'
                f'<p style="font-family:Times New Roman,serif;font-size:12px;font-weight:bold;'
                f'margin-bottom:12px;text-align:center;">{page_label}</p>'
                f'<img src="{data_uri}" style="max-width:100%;max-height:9in;display:block;margin:0 auto;"/>'
                f'</div>'
            )
    return {"html": "\n".join(pages), "errors": errors}


def create_certified_letter(
    from_address: Dict[str, str],
    to_bureau: str,
    letter_text: str,
    return_receipt: bool = True,
    description: str = "",
    attachments: Optional[list] = None,
) -> Dict[str, Any]:
    api_key = _get_api_key()
    if not api_key:
        return {"success": False, "error": "Lob API key not configured. Please add LOB_API_KEY to your secrets."}

    to_address = get_bureau_address(to_bureau)
    if not to_address:
        return {"success": False, "error": f"Unknown bureau: {to_bureau}"}

    addr_check = validate_address(from_address)
    if not addr_check["valid"]:
        return {"success": False, "error": f"Invalid return address: {addr_check['error']}"}

    html_content = letter_text_to_html(letter_text)

    if attachments:
        att_result = _build_attachment_pages_html(attachments)
        if att_result["errors"]:
            return {"success": False, "error": "; ".join(att_result["errors"])}
        if att_result["html"]:
            html_content = html_content.replace("</body>", f"{att_result['html']}\n</body>")

    extra_services = ["certified"]
    if return_receipt:
        extra_services.append("certified_return_receipt")

    payload = {
        "description": description or f"850 Lab dispute letter to {to_bureau.title()}",
        "to": {
            "name": to_address["name"],
            "address_line1": to_address["address_line1"],
            "address_city": to_address["address_city"],
            "address_state": to_address["address_state"],
            "address_zip": to_address["address_zip"],
            "address_country": to_address.get("address_country", "US"),
        },
        "from": {
            "name": from_address["name"].strip(),
            "address_line1": from_address["address_line1"].strip(),
            "address_city": from_address["address_city"].strip(),
            "address_state": from_address["address_state"].strip().upper(),
            "address_zip": from_address["address_zip"].strip(),
            "address_country": "US",
        },
        "file": html_content,
        "color": bool(attachments),
        "mail_type": "usps_first_class",
        "extra_services": extra_services,
    }

    if from_address.get("address_line2", "").strip():
        payload["from"]["address_line2"] = from_address["address_line2"].strip()

    try:
        resp = requests.post(
            f"{LOB_API_BASE}/letters",
            headers=_auth_header(api_key),
            json=payload,
            timeout=30,
        )

        data = resp.json()

        if resp.status_code in (200, 201):
            return {
                "success": True,
                "lob_id": data.get("id", ""),
                "tracking_number": data.get("tracking_number", ""),
                "expected_delivery": data.get("expected_delivery_date", ""),
                "url": data.get("url", ""),
                "carrier": data.get("carrier", "USPS"),
                "status": "mailed",
                "is_test": _is_test_key(api_key),
            }
        else:
            error_msg = data.get("error", {}).get("message", resp.text)
            return {"success": False, "error": f"Lob API error: {error_msg}"}

    except requests.Timeout:
        return {"success": False, "error": "Request to Lob timed out. Please try again."}
    except requests.ConnectionError:
        return {"success": False, "error": "Could not connect to Lob. Please check your internet connection."}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


def get_letter_status(lob_id: str) -> Dict[str, Any]:
    api_key = _get_api_key()
    if not api_key:
        return {"success": False, "error": "Lob API key not configured"}
    if not lob_id:
        return {"success": False, "error": "No Lob ID provided"}

    try:
        resp = requests.get(
            f"{LOB_API_BASE}/letters/{lob_id}",
            headers=_auth_header(api_key),
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200:
            tracking_events = data.get("tracking_events", [])
            latest_event = tracking_events[0] if tracking_events else None
            lob_status = "mailed"
            if latest_event:
                event_type = latest_event.get("type", "")
                if event_type == "certified.delivered":
                    lob_status = "delivered"
                elif event_type == "certified.in_transit":
                    lob_status = "in_transit"
                elif event_type == "certified.re-routed":
                    lob_status = "re_routed"
                elif event_type == "certified.returned_to_sender":
                    lob_status = "returned_to_sender"
                elif event_type == "certified.processed_for_delivery":
                    lob_status = "out_for_delivery"
                elif event_type in ("certified.mailed", "certified.in_local_area"):
                    lob_status = "in_transit"
            return {
                "success": True,
                "status": lob_status,
                "tracking_number": data.get("tracking_number", ""),
                "expected_delivery": data.get("expected_delivery_date", ""),
                "tracking_events": tracking_events,
            }
        else:
            return {"success": False, "error": f"Lob API error: {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_tracking_url(tracking_number: str) -> str:
    if tracking_number:
        return f"https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking_number}"
    return ""


def estimate_cost(return_receipt: bool = True) -> Dict[str, Any]:
    base = CERTIFIED_MAIL_COST_CENTS
    receipt = RETURN_RECEIPT_COST_CENTS if return_receipt else 0
    total = base + receipt
    return {
        "certified_mail": base,
        "return_receipt": receipt,
        "total_cents": total,
        "total_display": f"${total / 100:.2f}",
        "breakdown": f"Certified mail ${base/100:.2f}" + (f" + Return receipt ${receipt/100:.2f}" if return_receipt else ""),
    }


def is_configured() -> bool:
    key = _get_api_key()
    return key is not None and len(key) > 5


def is_test_mode() -> bool:
    key = _get_api_key()
    if not key:
        return True
    return _is_test_key(key)


def require_live_lob_for_customer_send() -> bool:
    """When true, non-admin customer API must not submit real Lob sends using a test API key."""
    v = (os.environ.get("REQUIRE_LOB_LIVE_FOR_CUSTOMER_SEND") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def customer_mail_send_blocked_reason(*, is_admin: bool) -> Optional[str]:
    """
    If non-empty, customer mail send should be blocked before calling Lob.
    Admins bypass live-key enforcement for support/testing.
    """
    if is_admin:
        return None
    if not is_configured():
        return "Lob API key is not configured."
    if require_live_lob_for_customer_send() and is_test_mode():
        return (
            "Live Lob is required for customer mail (REQUIRE_LOB_LIVE_FOR_CUSTOMER_SEND), "
            "but the server is using a test Lob key."
        )
    return None
