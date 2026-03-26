import streamlit as st
from ui.css import GOLD, GOLD_DIM, BG_0, BG_1, BG_2, TEXT_0, TEXT_1, BORDER

STEPS = [
    {"num": 1, "label": "Upload", "icon": "&#x1F4C4;"},
    {"num": 2, "label": "Review", "icon": "&#x1F50D;"},
    {"num": 3, "label": "Letters", "icon": "&#x2709;&#xFE0F;"},
    {"num": 4, "label": "Proof", "icon": "&#x1F4F7;"},
    {"num": 5, "label": "Mail", "icon": "&#x1F4EC;"},
    {"num": 6, "label": "Track", "icon": "&#x23F0;"},
]

STEPPER_CSS = f"""
<style>
.stepper-bar {{
    position: sticky;
    top: 0;
    z-index: 100;
    background: {BG_0};
    padding: 12px 8px 10px 8px;
    border-bottom: 1px solid {BORDER};
    margin: 0 0 16px 0;
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
}}
.stepper-round {{
    text-align: center;
    font-size: 0.62rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {GOLD_DIM};
    margin-bottom: 8px;
}}
.stepper-track {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    max-width: 600px;
    margin: 0 auto;
}}
.stepper-step {{
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    position: relative;
    cursor: default;
}}
.stepper-step.clickable {{
    cursor: pointer;
}}
.stepper-dot {{
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    font-weight: 800;
    transition: all 0.2s ease;
    position: relative;
    z-index: 2;
}}
.stepper-step.completed .stepper-dot {{
    background: #2ecc71;
    color: #fff;
    box-shadow: 0 0 8px rgba(46,204,113,0.3);
}}
.stepper-step.active .stepper-dot {{
    background: {GOLD};
    color: {BG_0};
    box-shadow: 0 0 8px rgba(212,160,23,0.25);
}}
.stepper-step.upcoming .stepper-dot {{
    background: {BG_2};
    color: {TEXT_1};
    border: 1px solid {BORDER};
}}
.stepper-label {{
    font-size: 0.62rem;
    font-weight: 700;
    margin-top: 4px;
    text-align: center;
    line-height: 1.2;
}}
.stepper-step.completed .stepper-label {{
    color: #2ecc71;
}}
.stepper-step.active .stepper-label {{
    color: {GOLD};
}}
.stepper-step.upcoming .stepper-label {{
    color: {TEXT_1};
    opacity: 0.6;
}}
.stepper-connector {{
    flex: 0.5;
    height: 2px;
    position: relative;
    top: -8px;
    z-index: 1;
}}
.stepper-connector.done {{
    background: #2ecc71;
}}
.stepper-connector.partial {{
    background: {GOLD};
}}
.stepper-connector.pending {{
    background: {BG_2};
}}
@media (max-width: 480px) {{
    .stepper-bar {{
        padding: 8px 4px 6px 4px;
    }}
    .stepper-dot {{
        width: 22px;
        height: 22px;
        font-size: 0.58rem;
    }}
    .stepper-label {{
        font-size: 0.52rem;
    }}
    .stepper-round {{
        font-size: 0.55rem;
    }}
}}
</style>
"""


def render_stepper_bar(current_step, completed_steps, round_number=1):
    elements = []
    for i, step in enumerate(STEPS):
        num = step["num"]
        if num in completed_steps and num != current_step:
            state = "completed clickable"
            dot_content = "&#x2713;"
        elif num == current_step:
            state = "active"
            dot_content = str(num)
        else:
            state = "upcoming"
            dot_content = str(num)

        elements.append(
            f'<div class="stepper-step {state}">'
            f'<div class="stepper-dot">{dot_content}</div>'
            f'<div class="stepper-label">{step["label"]}</div>'
            f'</div>'
        )

        if i < len(STEPS) - 1:
            next_num = STEPS[i + 1]["num"]
            if num in completed_steps and next_num in completed_steps:
                conn_cls = "done"
            elif num in completed_steps and next_num == current_step:
                conn_cls = "partial"
            else:
                conn_cls = "pending"
            elements.append(f'<div class="stepper-connector {conn_cls}"></div>')

    round_label = f"Round {round_number}" if round_number else ""

    html = (
        f'{STEPPER_CSS}'
        f'<div class="stepper-bar">'
        f'<div class="stepper-round">{round_label}</div>'
        f'<div class="stepper-track">{"".join(elements)}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
