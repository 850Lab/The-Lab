import os
import base64
import logging
from io import BytesIO

logger = logging.getLogger('850lab.doc_validator')

GOVERNMENT_ID_PROMPT = """Look at this image. Is this a government-issued photo ID document?

Valid examples: driver's license, passport, state ID card, military ID, permanent resident card.

Check for:
1. Does it look like an official ID card or document (not a selfie, screenshot, or random image)?
2. Can you see a name printed on it?
3. Does it appear to have a photo on it?

If this looks like a real government ID document, respond with: VALID
If this does NOT look like a government ID, respond with: INVALID

Then on the next line, give a short reason (1 sentence, simple language a child could understand).

Examples of INVALID: a selfie, a blank page, a screenshot of an app, a credit card, a utility bill, a random photo.

Respond ONLY in this format:
VALID or INVALID
Reason: [your reason]"""

ADDRESS_PROOF_PROMPT = """Look at this image. Is this a document that shows a person's name and mailing address?

Valid examples: utility bill, bank statement, insurance statement, mortgage statement, phone bill, government letter, lease agreement.

Check for:
1. Does it look like an official document or statement (not a selfie, screenshot of an app, or random image)?
2. Can you see a name and a mailing address printed on it?

If this looks like a real document showing a name and address, respond with: VALID
If this does NOT look like proof of address, respond with: INVALID

Then on the next line, give a short reason (1 sentence, simple language a child could understand).

Examples of INVALID: a selfie, a blank page, a screenshot of a social media app, a credit card, a driver's license, a random photo.

Respond ONLY in this format:
VALID or INVALID
Reason: [your reason]"""


def _pdf_first_page_to_image(pdf_bytes: bytes) -> bytes:
    try:
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, dpi=150)
        if images:
            buf = BytesIO()
            images[0].save(buf, format='PNG')
            return buf.getvalue()
    except Exception as e:
        logger.warning(f"Failed to convert PDF to image for validation: {e}")
    return None


def validate_proof_document(file_data: bytes, doc_type: str, file_type: str = 'image/png') -> dict:
    if not file_data:
        return {'valid': False, 'reason': 'No file data provided.', 'confidence': 'high', 'checked': True}

    image_bytes = file_data
    mime = file_type or 'image/png'

    if file_data[:5] == b'%PDF-' or 'pdf' in (file_type or '').lower():
        image_bytes = _pdf_first_page_to_image(file_data)
        if not image_bytes:
            return {'valid': True, 'reason': 'PDF could not be previewed for checking.', 'confidence': 'low', 'checked': False}
        mime = 'image/png'

    if mime not in ('image/png', 'image/jpeg', 'image/jpg', 'image/webp'):
        mime = 'image/png'

    b64_image = base64.b64encode(image_bytes).decode()

    if doc_type == 'government_id':
        prompt = GOVERNMENT_ID_PROMPT
    elif doc_type == 'address_proof':
        prompt = ADDRESS_PROOF_PROMPT
    else:
        return {'valid': True, 'reason': 'Unknown document type.', 'confidence': 'low', 'checked': False}

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL"),
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY"),
        )

        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64_image}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
            max_completion_tokens=150,
        )

        result_text = (response.choices[0].message.content or "").strip()
        logger.info(f"Doc validation result for {doc_type}: {result_text[:100]}")

        lines = result_text.strip().split('\n')
        verdict_line = lines[0].strip().upper() if lines else ''
        reason_line = ''
        for line in lines[1:]:
            if line.strip().lower().startswith('reason:'):
                reason_line = line.strip()[7:].strip()
                break
            elif line.strip():
                reason_line = line.strip()
                break

        if 'VALID' in verdict_line and 'INVALID' not in verdict_line:
            return {'valid': True, 'reason': reason_line or 'Document looks good.', 'confidence': 'high', 'checked': True}
        elif 'INVALID' in verdict_line:
            if not reason_line:
                if doc_type == 'government_id':
                    reason_line = "This doesn't look like a government ID. Please upload a photo of your driver's license, passport, or state ID."
                else:
                    reason_line = "This doesn't look like proof of address. Please upload a utility bill, bank statement, or insurance statement that shows your name and address."
            return {'valid': False, 'reason': reason_line, 'confidence': 'high', 'checked': True}
        else:
            return {'valid': True, 'reason': 'Could not determine document type.', 'confidence': 'low', 'checked': False}

    except Exception as e:
        logger.warning(f"Document validation API error for {doc_type}: {e}")
        return {'valid': True, 'reason': 'Validation unavailable.', 'confidence': 'low', 'checked': False}
