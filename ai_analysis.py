"""
ai_analysis.py | 850 Lab
AI-Enhanced Credit Report Analysis Layer

Provides a lightweight AI second-pass on parsed credit report data
to surface deeper insights, patterns, and actionable recommendations
that deterministic parsing alone may miss.

Cost: ~$0.01-0.03 per report (gpt-5-nano)
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are a consumer credit report analyst. You review extracted credit report data and provide clear, factual insights.

RULES:
- Be factual and specific. Reference actual data from the report.
- Never provide legal advice or guarantee outcomes.
- Focus on patterns, inconsistencies, and items that may be costing the consumer.
- Use plain language a non-expert can understand.
- Be concise. Each insight should be 1-2 sentences max.

OUTPUT FORMAT (JSON):
{
  "score_impact_summary": "One sentence about what's most likely hurting their score",
  "key_findings": [
    {"title": "short title", "detail": "1-2 sentence explanation", "severity": "high|medium|low"}
  ],
  "patterns_detected": [
    {"pattern": "short name", "detail": "explanation"}
  ],
  "quick_wins": [
    "actionable thing they can dispute or address"
  ],
  "estimated_dispute_value": "low|medium|high"
}"""


def _build_analysis_payload(parsed_data: Dict, bureau: str) -> str:
    accounts = parsed_data.get('accounts', [])
    inquiries = parsed_data.get('inquiries', [])
    negatives = parsed_data.get('negative_items', []) or parsed_data.get('public_records', [])
    personal_info = parsed_data.get('personal_info', {})

    summary = {
        'bureau': bureau,
        'total_accounts': len(accounts),
        'accounts': [],
        'negative_items': [],
        'inquiry_count': len(inquiries),
        'recent_inquiries': [],
    }

    for acct in accounts[:30]:
        entry = {
            'name': acct.get('creditor_name', acct.get('name', 'Unknown')),
            'type': acct.get('account_type', 'Unknown'),
            'status': acct.get('status', 'Unknown'),
            'balance': acct.get('balance', 'Unknown'),
            'classification': acct.get('classification', 'UNKNOWN'),
        }
        if acct.get('payment_status'):
            entry['payment_status'] = acct['payment_status']
        if acct.get('date_opened'):
            entry['opened'] = acct['date_opened']
        if acct.get('high_credit') or acct.get('credit_limit'):
            entry['limit'] = acct.get('high_credit') or acct.get('credit_limit')
        summary['accounts'].append(entry)

    for neg in negatives[:10]:
        summary['negative_items'].append({
            'name': neg.get('creditor_name', neg.get('name', 'Unknown')),
            'type': neg.get('type', neg.get('account_type', 'Unknown')),
            'status': neg.get('status', 'Unknown'),
            'amount': neg.get('balance', neg.get('amount', 'Unknown')),
        })

    for inq in inquiries[:10]:
        summary['recent_inquiries'].append({
            'name': inq.get('creditor_name', inq.get('name', 'Unknown')),
            'date': inq.get('date', 'Unknown'),
            'type': inq.get('type', 'Unknown'),
        })

    return json.dumps(summary, indent=2, default=str)


def analyze_report_with_ai(parsed_data: Dict, bureau: str) -> Optional[Dict]:
    payload = _build_analysis_payload(parsed_data, bureau)

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL"),
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY"),
        )

        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this {bureau} credit report data:\n\n{payload}"},
            ],
            max_completion_tokens=1000,
        )

        response_text = response.choices[0].message.content or ""

        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start >= 0 and end > start:
            result = json.loads(response_text[start:end])
            result['source'] = 'ai'
            result['bureau'] = bureau
            return result

        logger.warning(f"Could not parse AI analysis response for {bureau}")
        return None

    except Exception as e:
        logger.warning(f"AI analysis failed for {bureau}: {e}")
        return None


def build_deterministic_insights(parsed_data: Dict, bureau: str) -> Dict:
    accounts = parsed_data.get('accounts', [])
    negatives = parsed_data.get('negative_items', []) or []
    inquiries = parsed_data.get('inquiries', []) or []

    findings = []
    patterns = []
    quick_wins = []

    adverse_count = sum(1 for a in accounts if a.get('classification') == 'ADVERSE')
    if adverse_count > 0:
        findings.append({
            'title': f'{adverse_count} Adverse Account{"s" if adverse_count > 1 else ""}',
            'detail': f'Found {adverse_count} account{"s" if adverse_count > 1 else ""} classified as adverse. These are the biggest drag on your score.',
            'severity': 'high',
        })

    collections = [a for a in accounts if 'collection' in (a.get('account_type', '') or '').lower() or 'collection' in (a.get('status', '') or '').lower()]
    if collections:
        findings.append({
            'title': f'{len(collections)} Collection Account{"s" if len(collections) > 1 else ""}',
            'detail': f'{len(collections)} account{"s are" if len(collections) > 1 else " is"} in collections. Each one significantly impacts your score.',
            'severity': 'high',
        })
        quick_wins.append(f'Dispute {len(collections)} collection account{"s" if len(collections) > 1 else ""} for accuracy and verification')

    late_accounts = [a for a in accounts if 'late' in (a.get('payment_status', '') or '').lower() or 'delinquent' in (a.get('status', '') or '').lower()]
    if late_accounts:
        findings.append({
            'title': f'{len(late_accounts)} Late Payment{"s" if len(late_accounts) > 1 else ""}',
            'detail': f'{len(late_accounts)} account{"s show" if len(late_accounts) > 1 else " shows"} late payment history.',
            'severity': 'medium',
        })

    hard_inquiries = [i for i in inquiries if (i.get('type', '') or '').lower() != 'soft']
    if len(hard_inquiries) > 5:
        findings.append({
            'title': f'{len(hard_inquiries)} Hard Inquiries',
            'detail': f'You have {len(hard_inquiries)} hard inquiries. Multiple inquiries in a short period can lower your score.',
            'severity': 'medium',
        })
        quick_wins.append('Dispute unauthorized or unrecognized hard inquiries')

    if adverse_count > 0 and len(collections) > 0:
        patterns.append({
            'pattern': 'Mixed Adverse & Collections',
            'detail': 'Having both adverse accounts and collections suggests multiple reporting issues worth disputing.',
        })

    if negatives:
        quick_wins.append(f'Review {len(negatives)} negative item{"s" if len(negatives) > 1 else ""} for inaccuracies')

    if adverse_count > 3:
        value = 'high'
    elif adverse_count > 0 or len(collections) > 0:
        value = 'medium'
    else:
        value = 'low'

    score_summary = ''
    if collections:
        score_summary = f'{len(collections)} collection account{"s are" if len(collections) > 1 else " is"} likely the biggest factor hurting your score.'
    elif adverse_count > 0:
        score_summary = f'{adverse_count} adverse account{"s are" if adverse_count > 1 else " is"} negatively impacting your credit profile.'
    elif len(hard_inquiries) > 5:
        score_summary = f'{len(hard_inquiries)} hard inquiries may be affecting your score.'
    else:
        score_summary = 'Your report looks relatively clean. Minor issues may still be worth addressing.'

    return {
        'source': 'deterministic',
        'bureau': bureau,
        'score_impact_summary': score_summary,
        'key_findings': findings,
        'patterns_detected': patterns,
        'quick_wins': quick_wins,
        'estimated_dispute_value': value,
    }


def get_report_insights(parsed_data: Dict, bureau: str, use_ai: bool = True) -> Dict:
    if use_ai:
        ai_result = analyze_report_with_ai(parsed_data, bureau)
        if ai_result:
            return ai_result

    return build_deterministic_insights(parsed_data, bureau)
