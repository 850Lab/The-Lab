"""
views/admin_dashboard.py | 850 Lab
Admin Dashboard — user management, entitlement controls, platform stats
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import json
import auth
import database as db
from ui.css import GOLD, GOLD_DIM, BG_0, BG_1, BG_2, TEXT_0, TEXT_1, BORDER
from nudge_rules import evaluate_rules, NUDGE_SEVERITY_COLORS, NUDGE_SEVERITY_LABELS


def _get_admin_proof_docs(uid):
    if not uid:
        return None
    try:
        docs = []
        id_docs = db.get_proof_docs_for_user(uid, doc_types=['government_id'])
        if id_docs:
            id_file = db.get_proof_doc_file(id_docs[0]['id'], uid)
            if id_file and id_file.get('file_data'):
                docs.append({'label': 'Government-Issued Photo ID', 'data': bytes(id_file['file_data']),
                             'type': id_file.get('file_type', 'image/png')})
        addr_docs = db.get_proof_docs_for_user(uid, doc_types=['address_proof'])
        if addr_docs:
            addr_file = db.get_proof_doc_file(addr_docs[0]['id'], uid)
            if addr_file and addr_file.get('file_data'):
                docs.append({'label': 'Proof of Current Address', 'data': bytes(addr_file['file_data']),
                             'type': addr_file.get('file_type', 'image/png')})
        return docs if docs else None
    except Exception:
        return None


def _stat_card(label, value, sub=None):
    sub_html = f'<div style="font-size:0.75rem;color:{TEXT_1};margin-top:2px;">{sub}</div>' if sub else ''
    return (
        f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;'
        f'padding:16px 18px;text-align:center;">'
        f'<div style="font-size:1.6rem;font-weight:700;color:{GOLD};">{value}</div>'
        f'<div style="font-size:0.82rem;color:{TEXT_1};margin-top:4px;">{label}</div>'
        f'{sub_html}'
        f'</div>'
    )


def render_admin_dashboard():
    st.markdown(
        f'<div style="font-size:1.3rem;font-weight:700;color:{TEXT_0};margin-bottom:4px;">'
        f'Admin Dashboard</div>'
        f'<div style="font-size:0.85rem;color:{TEXT_1};margin-bottom:20px;">'
        f'Manage users, entitlements, and monitor platform activity.</div>',
        unsafe_allow_html=True,
    )

    try:
        stats = auth.get_platform_stats()
    except Exception:
        stats = {}

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(_stat_card("Total Users", stats.get('total_users', 0),
                               f"+{stats.get('new_users_7d', 0)} this week"), unsafe_allow_html=True)
    with c2:
        st.markdown(_stat_card("Verified", stats.get('verified_count', 0),
                               f"{stats.get('admin_count', 0)} admins"), unsafe_allow_html=True)
    with c3:
        st.markdown(_stat_card("Purchases", stats.get('total_purchases', 0),
                               f"{stats.get('total_usage_events', 0)} usage events"), unsafe_allow_html=True)
    with c4:
        pool_parts = []
        if stats.get('total_ai_rounds', 0):
            pool_parts.append(f"{stats['total_ai_rounds']} AI")
        if stats.get('total_letters', 0):
            pool_parts.append(f"{stats['total_letters']} Ltr")
        if stats.get('total_mailings', 0):
            pool_parts.append(f"{stats['total_mailings']} Mail")
        pool_sub = ", ".join(pool_parts) if pool_parts else "None allocated"
        st.markdown(_stat_card("Credit Pool", sum([
            stats.get('total_ai_rounds', 0),
            stats.get('total_letters', 0),
            stats.get('total_mailings', 0),
        ]), pool_sub), unsafe_allow_html=True)

    try:
        activity_stats = db.get_activity_stats()
    except Exception:
        activity_stats = {'active_now': 0, 'idle': 0, 'active_today': 0}

    c5, c6, c7 = st.columns(3)
    with c5:
        st.markdown(_stat_card("Active Now", activity_stats.get('active_now', 0),
                               "Last 5 minutes"), unsafe_allow_html=True)
    with c6:
        st.markdown(_stat_card("Idle", activity_stats.get('idle', 0),
                               "5-30 min inactive"), unsafe_allow_html=True)
    with c7:
        st.markdown(_stat_card("Today", activity_stats.get('active_today', 0),
                               "Last 24 hours"), unsafe_allow_html=True)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    tab_analytics, tab_sources, tab_live, tab_founders, tab_users, tab_grant, tab_txns, tab_leads = st.tabs([
        "Analytics & Levers", "Signup Sources", "Live Activity", "Founder Health", "Users", "Grant Credits", "Transactions", "Sprint Leads"
    ])

    with tab_analytics:
        _render_analytics_tab()

    with tab_sources:
        _render_signup_sources_tab()

    with tab_live:
        _render_live_activity_tab()

    with tab_founders:
        _render_founder_health_tab()

    with tab_users:
        _render_users_tab()

    with tab_grant:
        _render_grant_tab()

    with tab_txns:
        _render_transactions_tab()

    with tab_leads:
        _render_sprint_leads_tab()


def _render_signup_sources_tab():
    st.markdown(
        f'<div style="font-size:1.05rem;font-weight:600;color:{TEXT_0};margin-bottom:12px;">'
        f'Signup Attribution</div>',
        unsafe_allow_html=True,
    )

    period_options = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "All time": None}
    period_label = st.selectbox("Period", list(period_options.keys()), index=1, key="sources_period")
    days = period_options[period_label]

    try:
        data = db.get_signup_sources(days)
    except Exception as e:
        st.error(f"Could not load signup sources: {e}")
        return

    summary = data.get('summary', {})
    total = summary.get('total', 0) or 0
    tracked = summary.get('tracked', 0) or 0
    direct = summary.get('direct', 0) or 0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(_stat_card("Total Signups", total), unsafe_allow_html=True)
    with c2:
        st.markdown(_stat_card("Tracked (UTM)", tracked, f"{tracked/total*100:.0f}%" if total else "0%"), unsafe_allow_html=True)
    with c3:
        st.markdown(_stat_card("Direct / Unknown", direct, f"{direct/total*100:.0f}%" if total else "0%"), unsafe_allow_html=True)

    st.markdown(
        f'<div style="margin-top:16px;font-size:0.85rem;color:{TEXT_1};">'
        f'Add <code>?utm_source=reddit&amp;utm_medium=post&amp;utm_campaign=launch</code> to your links to track where signups come from.</div>',
        unsafe_allow_html=True,
    )

    by_source = data.get('by_source', [])
    if by_source:
        st.markdown(f'<div style="font-weight:600;color:{TEXT_0};margin-top:20px;margin-bottom:8px;">By Source</div>', unsafe_allow_html=True)
        for row in by_source:
            pct = row['signups'] / total * 100 if total else 0
            verified = row.get('verified', 0) or 0
            founders = row.get('founders', 0) or 0
            bar_width = max(pct, 2)
            extras = []
            if verified:
                extras.append(f"{verified} verified")
            if founders:
                extras.append(f"{founders} founders")
            extra_text = f' &mdash; {", ".join(extras)}' if extras else ''
            st.markdown(
                f'<div style="margin-bottom:8px;">'
                f'<div style="display:flex;justify-content:space-between;font-size:0.85rem;color:{TEXT_0};margin-bottom:2px;">'
                f'<span style="font-weight:600;">{row["source"]}</span>'
                f'<span>{row["signups"]} ({pct:.0f}%){extra_text}</span></div>'
                f'<div style="background:{BG_2};border-radius:4px;height:8px;overflow:hidden;">'
                f'<div style="background:{GOLD};width:{bar_width}%;height:100%;border-radius:4px;"></div></div></div>',
                unsafe_allow_html=True,
            )

    by_medium = data.get('by_medium', [])
    by_campaign = data.get('by_campaign', [])

    col_m, col_c = st.columns(2)
    with col_m:
        if by_medium:
            st.markdown(f'<div style="font-weight:600;color:{TEXT_0};margin-top:12px;margin-bottom:8px;">By Medium</div>', unsafe_allow_html=True)
            for row in by_medium:
                st.markdown(
                    f'<div style="font-size:0.85rem;color:{TEXT_1};padding:4px 0;">'
                    f'<span style="color:{TEXT_0};font-weight:500;">{row["medium"]}</span> &mdash; {row["signups"]} signups</div>',
                    unsafe_allow_html=True,
                )
    with col_c:
        if by_campaign:
            st.markdown(f'<div style="font-weight:600;color:{TEXT_0};margin-top:12px;margin-bottom:8px;">By Campaign</div>', unsafe_allow_html=True)
            for row in by_campaign:
                st.markdown(
                    f'<div style="font-size:0.85rem;color:{TEXT_1};padding:4px 0;">'
                    f'<span style="color:{TEXT_0};font-weight:500;">{row["campaign"]}</span> &mdash; {row["signups"]} signups</div>',
                    unsafe_allow_html=True,
                )

    daily = data.get('daily', [])
    if daily:
        st.markdown(f'<div style="font-weight:600;color:{TEXT_0};margin-top:20px;margin-bottom:8px;">Daily Signups by Source</div>', unsafe_allow_html=True)
        df = pd.DataFrame(daily)
        df['day'] = pd.to_datetime(df['day'])
        pivot = df.pivot_table(index='day', columns='source', values='signups', aggfunc='sum', fill_value=0)
        st.bar_chart(pivot)


def _render_founder_health_tab():
    try:
        fm = db.get_founder_health_metrics()
    except Exception as e:
        st.error(f"Could not load founder metrics: {e}")
        return

    st.markdown(
        f'<div style="font-size:1.1rem;font-weight:700;color:{TEXT_0};margin-bottom:16px;">'
        f'Founding Member Program</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(_stat_card("Total Founders", fm['total_founders'],
                               f"{fm['spots_remaining']} spots remaining"), unsafe_allow_html=True)
    with c2:
        st.markdown(_stat_card("Active (30d)", fm['active_founders_30d'],
                               f"of {fm['total_founders']} founders"), unsafe_allow_html=True)
    with c3:
        st.markdown(_stat_card("Uploaded Report", fm['founders_uploaded'],
                               _pct_safe(fm['founders_uploaded'], fm['total_founders']) + " of founders"), unsafe_allow_html=True)
    with c4:
        st.markdown(_stat_card("Founder → Paid", fm['founder_to_paid'],
                               _pct_safe(fm['founder_to_paid'], fm['total_founders']) + " conversion"), unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(_stat_card("AI Rounds Used", fm['ai_rounds_used'],
                               f"of {fm['total_founders'] * 9} granted"), unsafe_allow_html=True)
    with c6:
        st.markdown(_stat_card("Letters Used", fm['letters_used'],
                               f"of {fm['total_founders'] * 9} granted"), unsafe_allow_html=True)
    with c7:
        st.markdown(_stat_card("Total Transfers", fm['total_transfers'],
                               f"{fm['ai_transferred']} AI + {fm['letters_transferred']} letters"), unsafe_allow_html=True)
    with c8:
        st.markdown(_stat_card("Transfers (7d)", fm['transfers_7d'],
                               "transfer velocity"), unsafe_allow_html=True)

    if fm['total_founders'] > 0:
        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        activation_rate = fm['founders_uploaded'] / fm['total_founders'] * 100
        engagement_rate = fm['active_founders_30d'] / fm['total_founders'] * 100
        conversion_rate = fm['founder_to_paid'] / fm['total_founders'] * 100

        biggest_gap = "Low activation — founders aren't uploading reports" if activation_rate < 50 else \
                      "Low engagement — founders uploaded but aren't coming back" if engagement_rate < 40 else \
                      "Low conversion — founders aren't becoming paid users" if conversion_rate < 10 else \
                      "Healthy — activation, engagement, and conversion look good"

        gap_color = "#66BB6A" if "Healthy" in biggest_gap else "#ff6b6b"
        st.markdown(
            f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;padding:16px 20px;">'
            f'<div style="font-size:0.9rem;font-weight:700;color:{gap_color};margin-bottom:6px;">'
            f'Program Insight</div>'
            f'<div style="font-size:0.84rem;color:{TEXT_0};line-height:1.6;">{biggest_gap}</div>'
            f'<div style="font-size:0.78rem;color:{TEXT_1};margin-top:8px;">'
            f'Activation: {activation_rate:.0f}% &bull; Engagement: {engagement_rate:.0f}% &bull; '
            f'Conversion: {conversion_rate:.0f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _pct_safe(num, denom):
    if not denom:
        return '0%'
    return f'{num / denom * 100:.0f}%'


def _pct(num, denom):
    if not denom:
        return '0%'
    return f'{num / denom * 100:.1f}%'


def _conversion_arrow(from_count, to_count, from_label, to_label):
    if from_count and from_count > 0:
        rate = to_count / from_count * 100
        color = '#66BB6A' if rate >= 50 else (GOLD if rate >= 20 else '#EF5350')
    else:
        rate = 0.0
        color = TEXT_1
    return (
        f'<div style="display:flex;align-items:center;justify-content:center;gap:6px;'
        f'padding:2px 0;margin:-4px 0;">'
        f'<div style="font-size:0.7rem;color:{TEXT_1};">{from_label}</div>'
        f'<div style="color:{TEXT_1};font-size:0.7rem;">&#x2193;</div>'
        f'<div style="font-size:0.78rem;font-weight:700;color:{color};">{rate:.1f}%</div>'
        f'<div style="color:{TEXT_1};font-size:0.7rem;">&#x2193;</div>'
        f'<div style="font-size:0.7rem;color:{TEXT_1};">{to_label}</div>'
        f'</div>'
    )


def _funnel_bar(label, count, total, color, sub=None):
    pct = (count / total * 100) if total else 0
    sub_html = f'<span style="font-size:0.72rem;color:{TEXT_1};margin-left:6px;">{sub}</span>' if sub else ''
    return (
        f'<div style="margin-bottom:10px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px;">'
        f'<span style="font-size:0.82rem;color:{TEXT_0};font-weight:600;">{label}{sub_html}</span>'
        f'<span style="font-size:0.86rem;font-weight:700;color:{color};">{count}'
        f'<span style="font-size:0.72rem;color:{TEXT_1};font-weight:400;margin-left:4px;">'
        f'({pct:.1f}%)</span></span>'
        f'</div>'
        f'<div style="background:{BG_0};border-radius:6px;height:22px;overflow:hidden;border:1px solid {BORDER};">'
        f'<div style="width:{max(pct, 1.5)}%;height:100%;background:{color};border-radius:5px;'
        f'transition:width 0.4s ease;"></div>'
        f'</div>'
        f'</div>'
    )


def _lever_card(label, value, direction, color, sub=None):
    arrow = '&#9650;' if direction == 'up' else ('&#9660;' if direction == 'down' else '&#9679;')
    dir_color = '#66BB6A' if direction == 'up' else ('#EF5350' if direction == 'down' else TEXT_1)
    sub_html = f'<div style="font-size:0.72rem;color:{TEXT_1};margin-top:2px;">{sub}</div>' if sub else ''
    return (
        f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;padding:14px 16px;">'
        f'<div style="font-size:0.78rem;color:{TEXT_1};margin-bottom:4px;">{label}</div>'
        f'<div style="display:flex;align-items:baseline;gap:6px;">'
        f'<span style="font-size:1.4rem;font-weight:700;color:{color};">{value}</span>'
        f'<span style="font-size:0.82rem;color:{dir_color};">{arrow}</span>'
        f'</div>'
        f'{sub_html}'
        f'</div>'
    )


def _render_analytics_tab():
    days_options = {'Last 7 Days': 7, 'Last 30 Days': 30, 'Last 90 Days': 90, 'All Time': 3650}
    selected_period = st.selectbox("Period", list(days_options.keys()), index=1, key="analytics_period")
    days = days_options[selected_period]

    try:
        data = db.get_funnel_analytics(days)
    except Exception as e:
        st.error(f"Could not load analytics: {e}")
        return

    c2c = data.get('click_to_close', {})
    c2r = data.get('close_to_resell', {})
    rev = data.get('revenue', {})
    tiers = data.get('tier_distribution', {})

    all_time = c2c.get('all_time', {})
    period = c2c.get('period', {})

    total_rev = rev.get('total_cents', 0) / 100
    period_rev = rev.get('period_cents', 0) / 100
    arpu = rev.get('arpu', 0)

    rc1, rc2, rc3, rc4 = st.columns(4)
    with rc1:
        st.markdown(_lever_card("Total Revenue", f"${total_rev:,.2f}", 'up' if total_rev > 0 else 'flat', GOLD,
                                 f"${period_rev:,.2f} this period"), unsafe_allow_html=True)
    with rc2:
        st.markdown(_lever_card("ARPU", f"${arpu:.2f}", 'up' if arpu > 5 else 'flat', '#42A5F5',
                                 f"Per paying customer"), unsafe_allow_html=True)
    with rc3:
        signup_to_buy = _pct(all_time.get('purchased', 0), all_time.get('signups', 0))
        st.markdown(_lever_card("Click → Close", signup_to_buy,
                                 'up' if all_time.get('purchased', 0) > 0 else 'flat', '#66BB6A',
                                 "Signup to purchase"), unsafe_allow_html=True)
    with rc4:
        resell_rate = _pct(c2r.get('repeat_buyers', 0), c2r.get('first_time_buyers', 0))
        st.markdown(_lever_card("Close → Resell", resell_rate,
                                 'up' if c2r.get('repeat_buyers', 0) > 0 else 'flat', '#7E57C2',
                                 "Repeat / upgrade rate"), unsafe_allow_html=True)

    st.markdown(f'<div style="height:28px;"></div>', unsafe_allow_html=True)

    fc1, fc2 = st.columns(2)

    with fc1:
        st.markdown(
            f'<div style="font-size:1.05rem;font-weight:700;color:{GOLD};margin-bottom:4px;">'
            f'Click → Close</div>'
            f'<div style="font-size:0.78rem;color:{TEXT_1};margin-bottom:14px;">'
            f'Visitor journey from signup to first purchase</div>',
            unsafe_allow_html=True,
        )

        base = all_time.get('signups', 0) or 1
        signups = all_time.get('signups', 0)
        verified = all_time.get('verified', 0)
        uploaded = all_time.get('uploaded', 0)
        purchased = all_time.get('purchased', 0)
        mailed = all_time.get('mailed', 0)

        st.markdown(_funnel_bar("Signups", signups, base, '#42A5F5',
                                 f"+{period.get('signups', 0)} this period"), unsafe_allow_html=True)
        st.markdown(_conversion_arrow(signups, verified, "Signup", "Verified"), unsafe_allow_html=True)
        st.markdown(_funnel_bar("Verified Email", verified, base, '#26C6DA',
                                 _pct(verified, signups) + ' of signups'), unsafe_allow_html=True)
        st.markdown(_conversion_arrow(verified, uploaded, "Verified", "Uploaded"), unsafe_allow_html=True)
        st.markdown(_funnel_bar("Uploaded Report", uploaded, base, GOLD,
                                 _pct(uploaded, verified) + ' of verified'), unsafe_allow_html=True)
        st.markdown(_conversion_arrow(uploaded, purchased, "Uploaded", "Purchased"), unsafe_allow_html=True)
        st.markdown(_funnel_bar("First Purchase", purchased, base, '#66BB6A',
                                 _pct(purchased, uploaded) + ' of uploaders'), unsafe_allow_html=True)
        st.markdown(_conversion_arrow(purchased, mailed, "Purchased", "Mailed"), unsafe_allow_html=True)
        st.markdown(_funnel_bar("Mailed Letters", mailed, base, '#7E57C2',
                                 _pct(mailed, purchased) + ' of buyers'), unsafe_allow_html=True)

        drop_verify = all_time.get('signups', 0) - all_time.get('verified', 0)
        drop_upload = all_time.get('verified', 0) - all_time.get('uploaded', 0)
        drop_buy = all_time.get('uploaded', 0) - all_time.get('purchased', 0)
        worst_drop = max(
            ('Signup → Verify', drop_verify, all_time.get('signups', 0)),
            ('Verify → Upload', drop_upload, all_time.get('verified', 0)),
            ('Upload → Purchase', drop_buy, all_time.get('uploaded', 0)),
            key=lambda x: (x[1] / x[2]) if x[2] else 0,
        )
        if worst_drop[2] > 0:
            leak_pct = worst_drop[1] / worst_drop[2] * 100
            st.markdown(
                f'<div style="background:rgba(239,83,80,0.08);border:1px solid rgba(239,83,80,0.25);'
                f'border-radius:8px;padding:10px 14px;margin-top:12px;">'
                f'<div style="font-size:0.78rem;font-weight:600;color:#EF5350;">Biggest Leak</div>'
                f'<div style="font-size:0.86rem;color:{TEXT_0};margin-top:2px;">'
                f'{worst_drop[0]}: {worst_drop[1]} users lost ({leak_pct:.0f}%)</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with fc2:
        st.markdown(
            f'<div style="font-size:1.05rem;font-weight:700;color:#7E57C2;margin-bottom:4px;">'
            f'Close → Resell</div>'
            f'<div style="font-size:0.78rem;color:{TEXT_1};margin-bottom:14px;">'
            f'First purchase to repeat buy / tier upgrade</div>',
            unsafe_allow_html=True,
        )

        buyer_base = c2r.get('first_time_buyers', 0) or 1
        st.markdown(_funnel_bar("First-Time Buyers", c2r.get('first_time_buyers', 0), buyer_base, '#66BB6A'), unsafe_allow_html=True)
        st.markdown(_funnel_bar("Repeat Buyers", c2r.get('repeat_buyers', 0), buyer_base, '#7E57C2',
                                 f"2+ purchases"), unsafe_allow_html=True)
        st.markdown(_funnel_bar("Tier Upgraders", c2r.get('upgraders', 0), buyer_base, GOLD,
                                 f"Bought different packs"), unsafe_allow_html=True)

        st.markdown(
            f'<div style="font-size:0.92rem;font-weight:700;color:{TEXT_0};margin:20px 0 10px 0;">'
            f'Revenue by Tier</div>',
            unsafe_allow_html=True,
        )
        tp = c2r.get('tier_purchases', {})
        tr = c2r.get('tier_revenue', {})
        tier_total = sum(tp.values()) or 1
        tier_colors = {'digital_only': GOLD, 'full_round': '#66BB6A', 'deletion_sprint': '#7E57C2'}
        tier_labels = {'digital_only': 'Digital Only ($4.99)', 'full_round': 'Full Round ($24.99)', 'deletion_sprint': 'Deletion Sprint ($199)'}

        for tier_key in ('digital_only', 'full_round', 'deletion_sprint'):
            cnt = tp.get(tier_key, 0)
            tier_rev_cents = tr.get(tier_key, 0)
            st.markdown(_funnel_bar(
                tier_labels.get(tier_key, tier_key),
                cnt, tier_total, tier_colors.get(tier_key, TEXT_1),
                f"${tier_rev_cents / 100:,.2f} revenue"
            ), unsafe_allow_html=True)

        st.markdown(
            f'<div style="font-size:0.92rem;font-weight:700;color:{TEXT_0};margin:20px 0 10px 0;">'
            f'User Tier Distribution</div>',
            unsafe_allow_html=True,
        )
        tier_total_users = sum(tiers.values()) or 1
        dist_colors = {'free': TEXT_1, 'digital_only': GOLD, 'full_round': '#66BB6A', 'deletion_sprint': '#7E57C2'}
        dist_labels = {'free': 'Free', 'digital_only': 'Digital Only', 'full_round': 'Full Round', 'deletion_sprint': 'Deletion Sprint'}
        for tk in ('free', 'digital_only', 'full_round', 'deletion_sprint'):
            st.markdown(_funnel_bar(
                dist_labels.get(tk, tk), tiers.get(tk, 0), tier_total_users,
                dist_colors.get(tk, TEXT_1)
            ), unsafe_allow_html=True)

        one_time_only = c2r.get('first_time_buyers', 0) - c2r.get('repeat_buyers', 0)
        if c2r.get('first_time_buyers', 0) > 0:
            st.markdown(
                f'<div style="background:rgba(126,87,194,0.08);border:1px solid rgba(126,87,194,0.25);'
                f'border-radius:8px;padding:10px 14px;margin-top:12px;">'
                f'<div style="font-size:0.78rem;font-weight:600;color:#7E57C2;">Resell Opportunity</div>'
                f'<div style="font-size:0.86rem;color:{TEXT_0};margin-top:2px;">'
                f'{one_time_only} one-time buyer{"s" if one_time_only != 1 else ""} haven\'t upgraded yet'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown(f'<div style="height:28px;"></div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="font-size:1.05rem;font-weight:700;color:{TEXT_0};margin-bottom:4px;">'
        f'Key Conversion Levers</div>'
        f'<div style="font-size:0.78rem;color:{TEXT_1};margin-bottom:14px;">'
        f'Step-by-step conversion rates across the funnel</div>',
        unsafe_allow_html=True,
    )

    lc1, lc2, lc3, lc4, lc5 = st.columns(5)
    with lc1:
        st.markdown(_lever_card("Signup → Verify",
                                 _pct(all_time.get('verified', 0), all_time.get('signups', 0)),
                                 'up' if all_time.get('verified', 0) > 0 else 'flat', '#26C6DA',
                                 "Email verification"), unsafe_allow_html=True)
    with lc2:
        st.markdown(_lever_card("Verify → Upload",
                                 _pct(all_time.get('uploaded', 0), all_time.get('verified', 0)),
                                 'up' if all_time.get('uploaded', 0) > 0 else 'flat', GOLD,
                                 "Report submission"), unsafe_allow_html=True)
    with lc3:
        st.markdown(_lever_card("Upload → Buy",
                                 _pct(all_time.get('purchased', 0), all_time.get('uploaded', 0)),
                                 'up' if all_time.get('purchased', 0) > 0 else 'flat', '#66BB6A',
                                 "First purchase"), unsafe_allow_html=True)
    with lc4:
        st.markdown(_lever_card("Buy → Mail",
                                 _pct(all_time.get('mailed', 0), all_time.get('purchased', 0)),
                                 'up' if all_time.get('mailed', 0) > 0 else 'flat', '#7E57C2',
                                 "Letter mailing"), unsafe_allow_html=True)
    with lc5:
        st.markdown(_lever_card("Buy → Resell",
                                 _pct(c2r.get('repeat_buyers', 0), c2r.get('first_time_buyers', 0)),
                                 'up' if c2r.get('repeat_buyers', 0) > 0 else 'flat', '#AB47BC',
                                 "Repeat purchase"), unsafe_allow_html=True)


ACTION_LABELS = {
    'login': ('Logged in', '#66BB6A'),
    'signup': ('Signed up', '#42A5F5'),
    'session_load': ('Opened app', TEXT_1),
    'view_card': ('Viewing', TEXT_1),
    'upload': ('Uploaded report', GOLD),
    'generate_letters': ('Generated letters', GOLD),
    'purchase': ('Made purchase', '#66BB6A'),
    'mail_sent': ('Sent certified mail', '#7E57C2'),
}


def _render_live_activity_tab():
    if st.button("Refresh", key="refresh_activity", type="secondary"):
        st.rerun()

    st.markdown(
        f'<div style="font-size:1rem;font-weight:700;color:{TEXT_0};margin-bottom:12px;">'
        f'Who\'s Online</div>',
        unsafe_allow_html=True,
    )

    try:
        active_users = db.get_active_users(minutes=30)
    except Exception:
        active_users = []

    if not active_users:
        st.markdown(
            f'<div style="font-size:0.86rem;color:{TEXT_1};padding:16px 0;">'
            f'No active users in the last 30 minutes.</div>',
            unsafe_allow_html=True,
        )
    else:
        for u in active_users:
            idle_sec = float(u.get('idle_seconds', 0))
            if idle_sec < 300:
                status_dot = '#66BB6A'
                status_text = 'Active'
            else:
                status_dot = GOLD
                idle_min = int(idle_sec / 60)
                status_text = f'Idle {idle_min}m'

            email = u.get('email', 'Unknown')
            display = u.get('display_name') or email.split('@')[0]
            last_action = u.get('last_action', '')
            last_detail = u.get('last_detail', '')
            card = u.get('current_card', '')

            action_label, _ = ACTION_LABELS.get(last_action, (last_action, TEXT_1))
            action_info = action_label
            if last_detail and last_action not in ('session_load', 'login', 'signup'):
                action_info = f"{action_label}: {last_detail}"
            elif last_action == 'view_card' and last_detail:
                action_info = f"Viewing {last_detail}"

            last_seen = u.get('last_seen')
            time_str = ''
            if last_seen:
                if hasattr(last_seen, 'strftime'):
                    time_str = last_seen.strftime('%I:%M %p')
                else:
                    time_str = str(last_seen)[-8:]

            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;'
                f'background:{BG_1};border:1px solid {BORDER};border-radius:10px;margin-bottom:6px;">'
                f'<div style="width:10px;height:10px;border-radius:50%;background:{status_dot};flex-shrink:0;"></div>'
                f'<div style="flex:1;min-width:0;">'
                f'<div style="font-size:0.86rem;font-weight:600;color:{TEXT_0};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                f'{display} <span style="font-size:0.76rem;color:{TEXT_1};font-weight:400;">{email}</span></div>'
                f'<div style="font-size:0.78rem;color:{TEXT_1};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                f'{action_info}</div>'
                f'</div>'
                f'<div style="text-align:right;flex-shrink:0;">'
                f'<div style="font-size:0.76rem;font-weight:600;color:{status_dot};">{status_text}</div>'
                f'<div style="font-size:0.72rem;color:{TEXT_1};">{time_str}</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        f'<div style="font-size:1rem;font-weight:700;color:{TEXT_0};margin:20px 0 12px 0;">'
        f'Activity Feed</div>',
        unsafe_allow_html=True,
    )

    try:
        recent = db.get_recent_activity(limit=50)
    except Exception:
        recent = []

    if not recent:
        st.markdown(
            f'<div style="font-size:0.86rem;color:{TEXT_1};padding:16px 0;">'
            f'No activity recorded yet. Activity will appear here as users interact with the app.</div>',
            unsafe_allow_html=True,
        )
    else:
        for event in recent:
            action = event.get('action', '')
            action_label, action_color = ACTION_LABELS.get(action, (action, TEXT_1))
            detail = event.get('detail', '')
            email = event.get('email', '')
            display = event.get('display_name') or email.split('@')[0]
            ts = event.get('created_at')
            time_str = ''
            if ts:
                if hasattr(ts, 'strftime'):
                    now = datetime.now()
                    diff = (now - ts).total_seconds()
                    if diff < 60:
                        time_str = 'Just now'
                    elif diff < 3600:
                        time_str = f'{int(diff/60)}m ago'
                    elif diff < 86400:
                        time_str = f'{int(diff/3600)}h ago'
                    else:
                        time_str = ts.strftime('%b %d %I:%M %p')
                else:
                    time_str = str(ts)

            detail_html = ''
            if detail and action not in ('session_load', 'login', 'signup'):
                detail_html = f' &mdash; {detail}'
            elif action == 'view_card' and detail:
                action_label = f'Viewing {detail}'
                detail_html = ''

            st.markdown(
                f'<div style="display:flex;align-items:flex-start;gap:10px;padding:6px 0;'
                f'border-bottom:1px solid {BORDER};">'
                f'<div style="font-size:0.76rem;color:{TEXT_1};min-width:70px;text-align:right;padding-top:2px;">{time_str}</div>'
                f'<div style="flex:1;min-width:0;">'
                f'<span style="font-size:0.82rem;font-weight:600;color:{action_color};">{action_label}</span>'
                f'<span style="font-size:0.82rem;color:{TEXT_1};">{detail_html}</span>'
                f'<div style="font-size:0.74rem;color:{TEXT_1};margin-top:1px;">{display} ({email})</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_users_tab():
    if st.session_state.get('admin_detail_user_id'):
        _render_user_detail(st.session_state['admin_detail_user_id'])
        return

    try:
        users = auth.get_all_users_with_entitlements()
    except Exception as e:
        st.error(f"Could not load users: {e}")
        return

    if not users:
        st.info("No users found.")
        return

    search_q = st.text_input("Search users", placeholder="Email or display name...", key="admin_user_search")
    if search_q:
        q = search_q.lower()
        users = [u for u in users if q in (u.get('email', '') or '').lower() or q in (u.get('display_name', '') or '').lower()]

    rows = []
    for u in users:
        created = u.get('created_at')
        if hasattr(created, 'strftime'):
            created_str = created.strftime('%Y-%m-%d')
        else:
            created_str = str(created)[:10] if created else '—'
        rows.append({
            'ID': u['id'],
            'Email': u.get('email', ''),
            'Display Name': u.get('display_name', '') or '—',
            'Role': u.get('role', 'consumer'),
            'Tier': (u.get('tier', '') or 'free').title(),
            'Verified': 'Yes' if u.get('email_verified') else 'No',
            'AI': u.get('ai_rounds', 0),
            'Letters': u.get('letters', 0),
            'Mailings': u.get('mailings', 0),
            'Joined': created_str,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, height=min(400, 40 + len(rows) * 35))

    st.markdown(
        f'<div style="font-size:0.82rem;color:{TEXT_1};margin-top:8px;">'
        f'{len(users)} user{"s" if len(users) != 1 else ""} total</div>',
        unsafe_allow_html=True,
    )

    detail_uid = st.number_input("View User Detail (enter User ID)", min_value=1, step=1, key="admin_detail_uid_input")
    if st.button("View User Detail", key="admin_view_detail_btn"):
        st.session_state['admin_detail_user_id'] = int(detail_uid)
        st.rerun()

    with st.expander("Change User Role"):
        role_user_id = st.number_input("User ID", min_value=1, step=1, key="admin_role_uid")
        new_role = st.selectbox("New Role", ["consumer", "admin"], key="admin_role_select")
        if st.button("Update Role", key="admin_update_role"):
            if auth.update_user_role(int(role_user_id), new_role):
                st.success(f"User {role_user_id} role updated to {new_role}.")
                st.rerun()
            else:
                st.error("Failed to update role. Check the user ID.")

    with st.expander("Verify User Email"):
        verify_user_id = st.number_input("User ID", min_value=1, step=1, key="admin_verify_uid")
        if st.button("Mark Email Verified", key="admin_verify_email"):
            try:
                auth.mark_email_verified(int(verify_user_id))
                st.success(f"User {verify_user_id} email marked as verified.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to verify email: {e}")


def _render_user_detail(user_id):
    if st.button("\u2190 Back to Users List", key="admin_back_to_users"):
        st.session_state.pop('admin_detail_user_id', None)
        st.rerun()

    try:
        detail = db.get_user_detail_for_admin(user_id)
    except Exception as e:
        st.error(f"Could not load user detail: {e}")
        return

    if not detail:
        st.warning(f"User {user_id} not found.")
        return

    email = detail.get('email', '—')
    display_name = detail.get('display_name', '') or '—'
    role = detail.get('role', 'consumer')
    joined = detail.get('created_at')
    if hasattr(joined, 'strftime'):
        joined_str = joined.strftime('%Y-%m-%d %H:%M')
    else:
        joined_str = str(joined)[:16] if joined else '—'

    st.markdown(f'''
    <div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;padding:16px 20px;margin-bottom:16px;">
        <div style="font-size:1.15rem;font-weight:700;color:{TEXT_0};">{email}</div>
        <div style="font-size:0.82rem;color:{TEXT_1};margin-top:4px;">
            {display_name} &middot; {role.title()} &middot; Joined {joined_str}
            &middot; AI: {detail.get('ai_rounds', 0)} &middot; Letters: {detail.get('letters', 0)} &middot; Mailings: {detail.get('mailings', 0)}
        </div>
    </div>
    ''', unsafe_allow_html=True)

    _adm_ul_token = db.get_or_create_upload_token(user_id)
    if _adm_ul_token:
        import os as _adm_os
        _adm_host = _adm_os.environ.get('REPLIT_DEPLOYMENT_URL') or _adm_os.environ.get('REPLIT_DEV_DOMAIN', '')
        if _adm_host and not _adm_host.startswith('http'):
            _adm_base = f"https://{_adm_host}"
        elif _adm_host:
            _adm_base = _adm_host
        else:
            _adm_base = "https://850lab.replit.app"
        _adm_ul_url = f"{_adm_base}/?upload={_adm_ul_token}"
        _adm_proof = db.has_proof_docs(user_id)
        _adm_doc_status = "&#x2705; Docs on file" if _adm_proof.get('both') else ("&#x26A0;&#xFE0F; Partial" if (_adm_proof.get('has_id') or _adm_proof.get('has_address')) else "&#x274C; No docs")
        st.markdown(f'''
        <div style="background:{BG_1};border:1px solid rgba(212,160,23,0.25);border-radius:10px;padding:14px 18px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <div style="font-size:0.72rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:{GOLD_DIM};">Upload Link</div>
                <div style="font-size:0.78rem;">{_adm_doc_status}</div>
            </div>
            <code style="font-size:0.72rem;color:{GOLD};word-break:break-all;display:block;margin-bottom:8px;">{_adm_ul_url}</code>
        </div>
        ''', unsafe_allow_html=True)
        import streamlit.components.v1 as _adm_comp
        _adm_comp.html(f'''
        <button onclick="copyAdmUL()" id="copyAdmULBtn" style="width:100%;padding:10px 16px;margin-bottom:8px;
            background:{BG_2};border:1px solid rgba(212,160,23,0.25);color:{GOLD};
            font-weight:600;font-size:0.85rem;border-radius:8px;cursor:pointer;
            font-family:'Inter',-apple-system,sans-serif;transition:all 0.15s ease;">
            &#x1F4CB; Copy Upload Link to Clipboard</button>
        <script>
        function copyAdmUL(){{
            var link="{_adm_ul_url}";
            if(navigator.clipboard){{
                navigator.clipboard.writeText(link).then(function(){{
                    document.getElementById('copyAdmULBtn').innerHTML='&#x2705; Copied!';
                    setTimeout(function(){{document.getElementById('copyAdmULBtn').innerHTML='&#x1F4CB; Copy Upload Link to Clipboard';}},2000);
                }});
            }} else {{
                var t=document.createElement('textarea');t.value=link;
                document.body.appendChild(t);t.select();document.execCommand('copy');
                document.body.removeChild(t);
                document.getElementById('copyAdmULBtn').innerHTML='&#x2705; Copied!';
                setTimeout(function(){{document.getElementById('copyAdmULBtn').innerHTML='&#x1F4CB; Copy Upload Link to Clipboard';}},2000);
            }}
        }}
        </script>
        ''', height=50)

    mission = detail.get('active_mission')
    if mission:
        risk = mission.get('risk_level', '—')
        lever = mission.get('primary_lever', '—')
        risk_colors = {'HIGH': '#EF5350', 'MODERATE': '#FFA726', 'CONTROLLED': '#66BB6A'}
        risk_c = risk_colors.get(risk, TEXT_1)
        lever_colors = {'UTILIZATION': '#EF5350', 'DELETION': '#FFA726', 'STABILITY': '#42A5F5', 'OPTIMIZATION': '#66BB6A'}
        lever_c = lever_colors.get(lever, TEXT_1)

        created = mission.get('created_at')
        if hasattr(created, 'strftime'):
            mission_date = created.strftime('%Y-%m-%d')
        else:
            mission_date = str(created)[:10] if created else '—'

        st.markdown(f'''
        <div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;padding:14px 18px;margin-bottom:12px;">
            <div style="font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:{GOLD_DIM};margin-bottom:6px;">Active Mission</div>
            <div style="font-size:0.95rem;font-weight:700;color:{TEXT_0};margin-bottom:4px;">
                {mission.get('goal', '—')} &middot; {mission.get('timeline', '—')}
            </div>
            <div style="font-size:0.82rem;">
                <span style="color:{risk_c};font-weight:600;">Risk: {risk}</span>
                <span style="color:{TEXT_1};margin:0 6px;">&middot;</span>
                <span style="color:{lever_c};font-weight:600;">Lever: {lever}</span>
                <span style="color:{TEXT_1};margin:0 6px;">&middot;</span>
                <span style="color:{TEXT_1};">Started {mission_date}</span>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        sm_snap = mission.get('strike_metrics_snapshot')
        if sm_snap and isinstance(sm_snap, dict) and sm_snap:
            with st.expander("Strike Metrics Snapshot", expanded=False):
                metrics_rows = []
                for k, v in sm_snap.items():
                    if k == 'data_quality':
                        continue
                    metrics_rows.append({'Metric': k, 'Value': str(v)})
                if metrics_rows:
                    st.dataframe(pd.DataFrame(metrics_rows), use_container_width=True, hide_index=True)

        wp_snap = mission.get('war_plan_snapshot')
        if wp_snap and isinstance(wp_snap, dict) and wp_snap:
            with st.expander("War Room Plan Snapshot", expanded=False):
                st.json(wp_snap)
    else:
        st.markdown(f'<div style="font-size:0.85rem;color:{TEXT_1};margin-bottom:12px;">No active mission.</div>', unsafe_allow_html=True)

    tracker = detail.get('tracker')
    if tracker:
        mailed = tracker.get('mailed_at')
        if mailed:
            if hasattr(mailed, 'strftime'):
                mailed_str = mailed.strftime('%Y-%m-%d')
            else:
                mailed_str = str(mailed)[:10]
            now = datetime.utcnow()
            if hasattr(mailed, 'date'):
                days = (now.date() - mailed.date()).days
            else:
                days = 0
            st.markdown(
                f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;padding:12px 16px;margin-bottom:12px;">'
                f'<div style="font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:{GOLD_DIM};margin-bottom:4px;">Investigation Tracker</div>'
                f'<div style="font-size:0.88rem;color:{TEXT_0};">Round {tracker.get("round_number", 1)} &middot; Mailed {mailed_str} &middot; Day {days}/30</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    vp = detail.get('voice_profile')
    if vp:
        st.markdown(
            f'<div style="background:{BG_1};border:1px solid {BORDER};border-radius:10px;padding:12px 16px;margin-bottom:12px;">'
            f'<div style="font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:{GOLD_DIM};margin-bottom:4px;">Voice Profile</div>'
            f'<div style="font-size:0.85rem;color:{TEXT_0};">'
            f'Tone: {vp.get("tone", "—")} &middot; Detail: {vp.get("detail_level", "—")} &middot; Closing: {vp.get("closing", "—")}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    report = detail.get('latest_report')
    if report:
        upload_date = report.get('upload_date')
        if hasattr(upload_date, 'strftime'):
            upload_str = upload_date.strftime('%Y-%m-%d %H:%M')
        else:
            upload_str = str(upload_date)[:16] if upload_date else '—'
        st.markdown(
            f'<div style="font-size:0.85rem;color:{TEXT_1};margin-bottom:8px;">'
            f'Latest report: {report.get("bureau", "—")} &middot; {report.get("file_name", "—")} &middot; {upload_str}</div>',
            unsafe_allow_html=True,
        )

    lob = detail.get('lob_sends', [])
    if lob:
        with st.expander(f"Lob Sends ({len(lob)})", expanded=False):
            for s in lob:
                created = s.get('created_at')
                if hasattr(created, 'strftime'):
                    c_str = created.strftime('%Y-%m-%d')
                else:
                    c_str = str(created)[:10] if created else '—'
                st.markdown(
                    f'<div style="font-size:0.85rem;color:{TEXT_0};padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
                    f'{s.get("bureau", "—")} &middot; {s.get("status", "—")} &middot; {c_str}'
                    f' &middot; Tracking: {s.get("tracking_number", "—")}</div>',
                    unsafe_allow_html=True,
                )

    all_letters = db.get_all_letters_for_user(user_id)
    if all_letters:
        with st.expander(f"📄 Letters ({len(all_letters)})", expanded=False):
            from letter_generator import generate_letter_pdf, format_letter_filename
            from io import BytesIO
            import zipfile
            import base64
            import streamlit.components.v1 as _adm_letter_comp

            _adm_sig = db.get_user_signature(user_id)
            _adm_proof = _get_admin_proof_docs(user_id)

            if len(all_letters) > 1:
                _zip_buf = BytesIO()
                with zipfile.ZipFile(_zip_buf, 'w', zipfile.ZIP_DEFLATED) as _zf_adm:
                    for _lt_z in all_letters:
                        _fn_z = format_letter_filename(_lt_z.get('bureau', 'unknown'))
                        _round_z = _lt_z.get('round_number', 1) or 1
                        _zf_adm.writestr(f"round{_round_z}/{_fn_z}.pdf",
                                         generate_letter_pdf(_lt_z['letter_text'], signature_image=_adm_sig, proof_documents=_adm_proof))
                        _zf_adm.writestr(f"round{_round_z}/{_fn_z}.txt", _lt_z['letter_text'])
                _zip_b64 = base64.b64encode(_zip_buf.getvalue()).decode()
                _zip_fn = f"all_letters_user{user_id}.zip"
                _adm_letter_comp.html(
                    f'''<script>var _azd="{_zip_b64}";</script>
                    <button onclick="(function(){{var b=atob(_azd);var a=new Uint8Array(b.length);for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);
                    var bl=new Blob([a],{{type:'application/zip'}});var u=URL.createObjectURL(bl);var l=document.createElement('a');
                    l.href=u;l.download='{_zip_fn}';l.click();URL.revokeObjectURL(u)}})()" style="width:100%;padding:10px 14px;margin-bottom:12px;
                    background:{BG_2};border:1px solid rgba(212,160,23,0.25);color:{GOLD};
                    font-weight:600;font-size:0.85rem;border-radius:8px;cursor:pointer;
                    font-family:'Inter',-apple-system,sans-serif;">&#x1F4E5; Download All Letters (ZIP)</button>''',
                    height=55)

            for _lt in all_letters:
                _bureau_lt = (_lt.get('bureau') or 'unknown').title()
                _round_lt = _lt.get('round_number', 1) or 1
                _created_lt = _lt.get('created_at')
                if hasattr(_created_lt, 'strftime'):
                    _dt_str = _created_lt.strftime('%Y-%m-%d %H:%M')
                else:
                    _dt_str = str(_created_lt)[:16] if _created_lt else '—'
                _snippet = (_lt.get('letter_text', '')[:120] + '...') if len(_lt.get('letter_text', '')) > 120 else _lt.get('letter_text', '')
                _snippet = _snippet.replace('\n', ' ')

                st.markdown(
                    f'<div style="background:{BG_2};border:1px solid {BORDER};border-radius:8px;padding:10px 14px;margin-bottom:8px;">'
                    f'<div style="font-size:0.88rem;font-weight:700;color:{TEXT_0};">{_bureau_lt} — Round {_round_lt}</div>'
                    f'<div style="font-size:0.78rem;color:{TEXT_1};margin:2px 0 6px;">{_dt_str}</div>'
                    f'<div style="font-size:0.78rem;color:{TEXT_1};font-style:italic;">{_snippet}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                _lt_id = _lt.get('id', 0)
                _pdf_bytes = generate_letter_pdf(_lt['letter_text'], signature_image=_adm_sig, proof_documents=_adm_proof)
                _pdf_b64 = base64.b64encode(_pdf_bytes).decode()
                _pdf_fn = f"dispute_letter_{_lt.get('bureau', 'unknown')}_r{_round_lt}.pdf"
                _adm_letter_comp.html(
                    f'''<script>var _ald{_lt_id}="{_pdf_b64}";</script>
                    <button onclick="(function(){{var b=atob(_ald{_lt_id});var a=new Uint8Array(b.length);for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);
                    var bl=new Blob([a],{{type:'application/pdf'}});var u=URL.createObjectURL(bl);var l=document.createElement('a');
                    l.href=u;l.download='{_pdf_fn}';l.click();URL.revokeObjectURL(u)}})()" style="width:100%;padding:8px 12px;margin-bottom:4px;
                    background:{BG_1};border:1px solid {BORDER};color:{GOLD};
                    font-weight:600;font-size:0.8rem;border-radius:6px;cursor:pointer;
                    font-family:'Inter',-apple-system,sans-serif;">&#x1F4E5; Download PDF</button>''',
                    height=48)

            st.markdown(f'<div style="margin-top:16px;padding-top:12px;border-top:1px solid {BORDER};">'
                        f'<div style="font-size:0.72rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:{GOLD_DIM};margin-bottom:8px;">Send via Lob Certified Mail</div>'
                        f'</div>', unsafe_allow_html=True)

            _adm_letter_choices = {f"{(_lt.get('bureau','?')).title()} — R{_lt.get('round_number',1) or 1} ({str(_lt.get('created_at',''))[:10]})": _lt for _lt in all_letters}
            _selected_label = st.selectbox("Select letter to mail", list(_adm_letter_choices.keys()), key=f"adm_lob_letter_{user_id}")
            _selected_letter = _adm_letter_choices.get(_selected_label)

            if _selected_letter:
                st.markdown(f'<div style="font-size:0.82rem;color:{TEXT_1};margin-bottom:8px;">Return address for this user:</div>', unsafe_allow_html=True)
                _lob_cols = st.columns(2)
                with _lob_cols[0]:
                    _lob_name = st.text_input("Full Name", key=f"adm_lob_name_{user_id}", value=detail.get('display_name', ''))
                    _lob_addr1 = st.text_input("Address Line 1", key=f"adm_lob_addr1_{user_id}")
                    _lob_addr2 = st.text_input("Address Line 2 (opt)", key=f"adm_lob_addr2_{user_id}")
                with _lob_cols[1]:
                    _lob_city = st.text_input("City", key=f"adm_lob_city_{user_id}")
                    _lob_state = st.text_input("State", key=f"adm_lob_state_{user_id}")
                    _lob_zip = st.text_input("ZIP", key=f"adm_lob_zip_{user_id}")

                if st.button("📬 Send Certified Mail via Lob", key=f"adm_lob_send_{user_id}", type="primary", use_container_width=True):
                    if not all([_lob_name, _lob_addr1, _lob_city, _lob_state, _lob_zip]):
                        st.error("Please fill in all required address fields.")
                    else:
                        import lob_client
                        _from_addr = {
                            "name": _lob_name.strip(),
                            "address_line1": _lob_addr1.strip(),
                            "address_line2": _lob_addr2.strip() if _lob_addr2 else "",
                            "address_city": _lob_city.strip(),
                            "address_state": _lob_state.strip(),
                            "address_zip": _lob_zip.strip(),
                        }
                        _bureau_key = (_selected_letter.get('bureau') or '').lower()
                        _attachments = []
                        if _adm_proof:
                            for _pd in _adm_proof:
                                _attachments.append({"name": _pd['label'], "data": _pd['data'], "type": _pd.get('type', 'image/png')})

                        with st.spinner(f"Sending certified letter to {_bureau_key.title()}..."):
                            _lob_result = lob_client.create_certified_letter(
                                from_address=_from_addr,
                                to_bureau=_bureau_key,
                                letter_text=_selected_letter['letter_text'],
                                description=f"Admin send for user {user_id}",
                                attachments=_attachments if _attachments else None,
                            )

                        if _lob_result.get('success'):
                            db.save_lob_send(
                                user_id=user_id,
                                report_id=_selected_letter.get('report_id'),
                                bureau=_bureau_key,
                                lob_id=_lob_result.get('lob_id', ''),
                                tracking_number=_lob_result.get('tracking_number', ''),
                                status='mailed',
                                from_address=_from_addr,
                                to_address=lob_client.get_bureau_address(_bureau_key) or {},
                                cost_cents=_lob_result.get('cost_cents', 1099),
                                return_receipt=True,
                                is_test=_lob_result.get('is_test', False),
                                expected_delivery=_lob_result.get('expected_delivery'),
                            )
                            st.success(f"Letter sent! Tracking: {_lob_result.get('tracking_number', '—')}")
                        else:
                            st.error(f"Failed: {_lob_result.get('error', 'Unknown error')}")
    else:
        st.markdown(f'<div style="font-size:0.85rem;color:{TEXT_1};margin-bottom:12px;">No letters generated yet.</div>', unsafe_allow_html=True)

    nudges = detail.get('nudge_history', [])
    if nudges:
        with st.expander(f"Nudge History ({len(nudges)})", expanded=False):
            for n in nudges:
                sev = n.get('severity', 'info')
                sev_color = NUDGE_SEVERITY_COLORS.get(sev, TEXT_1)
                created = n.get('created_at')
                if hasattr(created, 'strftime'):
                    n_str = created.strftime('%Y-%m-%d %H:%M')
                else:
                    n_str = str(created)[:16] if created else '—'
                st.markdown(
                    f'<div style="font-size:0.85rem;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
                    f'<span style="color:{sev_color};font-weight:600;">[{NUDGE_SEVERITY_LABELS.get(sev, sev)}]</span> '
                    f'<span style="color:{TEXT_0};">{n.get("nudge_id", "—")}</span> '
                    f'<span style="color:{TEXT_1};">&middot; {n_str}</span></div>',
                    unsafe_allow_html=True,
                )

    mission_history = detail.get('mission_history', [])
    if len(mission_history) > 1:
        with st.expander(f"Mission History ({len(mission_history)})", expanded=False):
            for m in mission_history:
                status = m.get('status', 'active')
                created = m.get('created_at')
                if hasattr(created, 'strftime'):
                    m_str = created.strftime('%Y-%m-%d')
                else:
                    m_str = str(created)[:10] if created else '—'
                status_pill = f'<span style="color:{"#66BB6A" if status == "active" else TEXT_1};font-weight:600;">{status.upper()}</span>'
                st.markdown(
                    f'<div style="font-size:0.85rem;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
                    f'{status_pill} &middot; {m.get("goal", "—")} &middot; {m.get("timeline", "—")} &middot; {m_str}</div>',
                    unsafe_allow_html=True,
                )


def _render_grant_tab():
    st.markdown(
        f'<div style="font-size:0.92rem;color:{TEXT_0};font-weight:600;margin-bottom:12px;">'
        f'Grant credits to a user</div>',
        unsafe_allow_html=True,
    )

    grant_uid = st.number_input("User ID", min_value=1, step=1, key="admin_grant_uid")
    gc1, gc2, gc3 = st.columns(3)
    with gc1:
        grant_ai = st.number_input("AI Rounds", min_value=0, value=0, step=1, key="admin_grant_ai")
    with gc2:
        grant_letters = st.number_input("Letters", min_value=0, value=0, step=1, key="admin_grant_letters")
    with gc3:
        grant_mailings = st.number_input("Mailings", min_value=0, value=0, step=1, key="admin_grant_mailings")

    grant_note = st.text_input("Note (optional)", placeholder="e.g. Promo, support fix, beta tester...", key="admin_grant_note")

    if st.button("Grant Credits", key="admin_grant_btn", type="primary"):
        if grant_ai == 0 and grant_letters == 0 and grant_mailings == 0:
            st.warning("Enter at least one credit amount to grant.")
        else:
            try:
                auth.add_entitlements(
                    user_id=int(grant_uid),
                    ai_rounds=grant_ai,
                    letters=grant_letters,
                    mailings=grant_mailings,
                    source='admin_grant',
                    note=grant_note or f'Admin grant',
                )
                parts = []
                if grant_ai:
                    parts.append(f"{grant_ai} AI rounds")
                if grant_letters:
                    parts.append(f"{grant_letters} letters")
                if grant_mailings:
                    parts.append(f"{grant_mailings} mailings")
                st.success(f"Granted {', '.join(parts)} to user {grant_uid}.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to grant credits: {e}")

    st.markdown(
        f'<div style="font-size:0.78rem;color:{TEXT_1};margin-top:12px;font-style:italic;">'
        f'Credits are added to the user\'s existing balance. All grants are logged in the Transactions tab.</div>',
        unsafe_allow_html=True,
    )


def _render_transactions_tab():
    st.markdown(
        f'<div style="font-size:0.92rem;color:{TEXT_0};font-weight:600;margin-bottom:12px;">'
        f'Recent entitlement transactions</div>',
        unsafe_allow_html=True,
    )

    txn_uid = st.number_input("Filter by User ID (0 = all)", min_value=0, step=1, key="admin_txn_uid")
    txn_limit = st.selectbox("Show last", [20, 50, 100], key="admin_txn_limit")

    if txn_uid > 0:
        try:
            txns = auth.get_entitlement_transactions(int(txn_uid), limit=txn_limit)
        except Exception as e:
            st.error(f"Could not load transactions: {e}")
            return
    else:
        try:
            txns = _get_all_transactions(limit=txn_limit)
        except Exception as e:
            st.error(f"Could not load transactions: {e}")
            return

    if not txns:
        st.info("No transactions found.")
        return

    rows = []
    for t in txns:
        created = t.get('created_at')
        if hasattr(created, 'strftime'):
            ts = created.strftime('%Y-%m-%d %H:%M')
        else:
            ts = str(created)[:16] if created else '—'
        rows.append({
            'User': t.get('user_id', '—') if 'user_id' in t else '—',
            'Type': t.get('transaction_type', '').upper(),
            'Source': t.get('source', ''),
            'AI': t.get('ai_rounds', 0),
            'Letters': t.get('letters', 0),
            'Mailings': t.get('mailings', 0),
            'Note': t.get('note', '') or '',
            'Date': ts,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _get_all_transactions(limit=20):
    from database import get_db
    with get_db(dict_cursor=True) as (conn, cur):
        cur.execute('''
            SELECT user_id, transaction_type, source, ai_rounds, letters, mailings, note, created_at
            FROM entitlement_transactions
            ORDER BY created_at DESC
            LIMIT %s
        ''', (limit,))
        return [dict(t) for t in cur.fetchall()]


def _render_sprint_leads_tab():
    st.markdown(
        f'<div style="font-size:1.05rem;font-weight:700;color:{TEXT_0};margin-bottom:12px;">'
        f'Sprint Intake Leads</div>',
        unsafe_allow_html=True,
    )

    leads = db.get_sprint_leads(limit=100)

    if not leads:
        st.info("No Sprint leads yet. Leads appear here when someone submits the Sprint intake form.")
        return

    new_count = sum(1 for l in leads if not l.get('contacted'))
    total = len(leads)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(_stat_card("Total Leads", total), unsafe_allow_html=True)
    with c2:
        st.markdown(_stat_card("Awaiting Contact", new_count,
                               "Need follow-up" if new_count else "All contacted"), unsafe_allow_html=True)

    for lead in leads:
        contacted = lead.get('contacted', False)
        badge_color = "#4caf50" if contacted else GOLD
        badge_text = "Contacted" if contacted else "New"
        created = lead.get('created_at', '')
        if hasattr(created, 'strftime'):
            created = created.strftime('%b %d, %Y %I:%M %p')

        with st.expander(f"{lead['name']}  —  {lead['email']}  |  {badge_text}", expanded=not contacted):
            st.markdown(
                f'<span style="display:inline-block;background:{badge_color};color:#fff;'
                f'font-size:0.7rem;font-weight:700;padding:2px 8px;border-radius:10px;">'
                f'{badge_text}</span>',
                unsafe_allow_html=True,
            )
            lc1, lc2 = st.columns(2)
            with lc1:
                st.markdown(f"**Phone:** {lead.get('phone', '—')}")
                st.markdown(f"**Preferred:** {lead.get('preferred_contact', '—').title()}")
                st.markdown(f"**Best time:** {lead.get('best_time', '—').title()}")
            with lc2:
                st.markdown(f"**Timeline:** {lead.get('timeline', '—')}")
                st.markdown(f"**Submitted:** {created}")

            if lead.get('goal'):
                st.markdown(f"**Goal:** {lead['goal']}")

            if not contacted:
                if st.button("Mark as contacted", key=f"contact_lead_{lead['id']}"):
                    db.mark_sprint_lead_contacted(lead['id'])
                    st.rerun()
