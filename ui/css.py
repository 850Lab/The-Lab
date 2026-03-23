import streamlit as st

BG_0 = "#0f0f12"
BG_1 = "#1a1a1f"
BG_2 = "#242428"
TEXT_0 = "#f5f5f5"
TEXT_1 = "#a0a0a8"
BORDER = "rgba(255,215,140,0.15)"
GOLD = "#D4A017"
GOLD_DIM = "#B8860B"

LAB_VIEWPORT_META = '''<script>
(function(){
  var m = document.querySelector('meta[name="viewport"]');
  if (m) { m.setAttribute('content', 'width=device-width, initial-scale=1.0'); }
  else {
    m = document.createElement('meta');
    m.name = 'viewport';
    m.content = 'width=device-width, initial-scale=1.0';
    document.head.appendChild(m);
  }
})();
</script>'''
LAB_NOCACHE_META = '<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"><meta http-equiv="Pragma" content="no-cache"><meta http-equiv="Expires" content="0">'


LAB_THEME_CSS = f"""
<style>
html, body {{
  overflow-x: hidden !important;
  max-width: 100vw !important;
  width: 100% !important;
  color-scheme: dark only !important;
  background: {BG_0} !important;
}}
html {{
  -webkit-text-size-adjust: 100% !important;
  -ms-text-size-adjust: 100% !important;
}}
:root {{
  color-scheme: dark only !important;
}}

::selection {{
  background: rgba(212,160,23,0.35) !important;
  color: {TEXT_0} !important;
}}
::-moz-selection {{
  background: rgba(212,160,23,0.35) !important;
  color: {TEXT_0} !important;
}}

::-webkit-scrollbar {{
  width: 8px;
  height: 8px;
}}
::-webkit-scrollbar-track {{
  background: {BG_0};
}}
::-webkit-scrollbar-thumb {{
  background: rgba(160,160,168,0.25);
  border-radius: 4px;
}}
::-webkit-scrollbar-thumb:hover {{
  background: rgba(160,160,168,0.4);
}}

input::placeholder, textarea::placeholder {{
  color: rgba(160,160,168,0.6) !important;
  opacity: 1 !important;
}}
.stApp {{
  background: linear-gradient(180deg, {BG_0} 0%, {BG_1} 100%) !important;
  color: {TEXT_0} !important;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  overflow-x: hidden !important;
  max-width: 100vw !important;
}}

.stApp [data-testid="stAppViewContainer"],
.stApp [data-testid="stVerticalBlock"],
.stApp [data-testid="stMain"],
.stApp [data-testid="stMainBlockContainer"],
.stApp iframe {{
  background: transparent !important;
  color: {TEXT_0} !important;
}}
.stApp [data-testid="stSidebar"] {{
  background: {BG_1} !important;
  color: {TEXT_0} !important;
}}

.stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stMarkdown"],
.stApp .stMarkdown {{
  background: transparent !important;
  color: {TEXT_0} !important;
}}
.demo-letter-preview,
.demo-letter-preview * {{
  color: #111 !important;
  background: transparent !important;
}}
.demo-letter-preview {{
  background: #fff !important;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3) !important;
  border-radius: 10px;
}}

.stApp .element-container,
.stApp .stColumn,
.stApp [data-testid="stHorizontalBlock"],
.stApp [data-testid="stVerticalBlockBorderWrapper"],
.stApp [data-testid="column"] {{
  background: transparent !important;
  color: {TEXT_0} !important;
}}

.stApp .stButton,
.stApp .stButton > button,
.stApp .stButton > button *,
.stApp .stDownloadButton > button *,
.stApp [data-testid="stBaseButton-primary"] *,
.stApp [data-testid="stBaseButton-secondary"] *,
.stApp [data-testid="stBaseButton-tertiary"] * {{
  background-color: transparent !important;
}}

.stApp header[data-testid="stHeader"] {{
  background: {BG_0} !important;
  border-bottom: 1px solid rgba(255,215,140,0.06);
}}

@media (max-width: 768px) {{
  .stApp header[data-testid="stHeader"] {{
    height: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
  }}
}}

h1, h2, h3, h4, h5, h6 {{
  color: {TEXT_0};
  font-weight: 700;
  letter-spacing: -0.01em;
}}

p, label, div {{
  color: {TEXT_0};
}}

h1 {{ font-size: 2rem; }}
h2 {{ font-size: 1.6rem; }}
h3 {{ font-size: 1.3rem; }}

.lab-muted {{
  color: {TEXT_1} !important;
}}

.lab-card {{
  background: {BG_1};
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}}

.stTextInput input, .stTextArea textarea {{
  background: {BG_2} !important;
  color: {TEXT_0} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 10px !important;
  padding: 12px 14px !important;
  font-size: 0.95rem !important;
  transition: border-color 0.2s ease;
}}

.stTextInput input:focus, .stTextArea textarea:focus {{
  border-color: {GOLD} !important;
  box-shadow: 0 0 0 2px rgba(212,160,23,0.35) !important;
  outline: none !important;
}}
.stTextInput input:focus-visible, .stTextArea textarea:focus-visible {{
  border-color: {GOLD} !important;
  box-shadow: 0 0 0 2px rgba(212,160,23,0.45) !important;
  outline: none !important;
}}

.stSelectbox div[data-baseweb="select"] > div {{
  background: {BG_2} !important;
  color: {TEXT_0} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 10px !important;
}}

/* Selectbox dropdown menu (popover) */
div[data-baseweb="popover"] {{
  background: {BG_1} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 10px !important;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4) !important;
}}

/* Remove black overlay behind dropdowns */
div[data-baseweb="popover"] > div:first-child {{
  background: transparent !important;
}}
div[data-baseweb="select"] > div[role="listbox"] {{
  background: {BG_1} !important;
}}
div[data-testid="stPopoverBody"] {{
  background: {BG_1} !important;
  border: 1px solid {BORDER} !important;
}}
.stPopover > div:first-child {{
  background: transparent !important;
}}
div[data-modal-container="true"] {{
  background: transparent !important;
}}
div[data-baseweb="popover"] [data-baseweb="layer"] {{
  background: transparent !important;
}}

div[data-baseweb="popover"] ul {{
  background: {BG_1} !important;
}}

div[data-baseweb="popover"] li {{
  background: {BG_1} !important;
  color: {TEXT_0} !important;
}}

div[data-baseweb="popover"] li:hover {{
  background: {BG_2} !important;
}}

div[data-baseweb="popover"] li[aria-selected="true"] {{
  background: rgba(212,160,23,0.08) !important;
  color: {GOLD} !important;
}}

.stButton > button,
.stButton > button[kind="secondary"],
.stButton > button[kind="tertiary"],
div[data-testid="stButton"] > button,
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-tertiary"] {{
  background: {BG_2} !important;
  color: {TEXT_0} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 10px !important;
  padding: 8px 16px !important;
  font-weight: 500 !important;
  font-size: 0.9rem !important;
  transition: all 0.2s ease !important;
  letter-spacing: 0.01em !important;
}}

.stButton > button:hover,
.stButton > button[kind="secondary"]:hover,
.stButton > button[kind="tertiary"]:hover,
div[data-testid="stButton"] > button:hover,
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stBaseButton-tertiary"]:hover {{
  border-color: {GOLD} !important;
  color: {GOLD} !important;
  background: rgba(212,160,23,0.08) !important;
  transform: translateY(-1px);
}}

button[kind="primary"],
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {{
  background: linear-gradient(90deg, {GOLD}, #f2c94c) !important;
  color: #1a1a1f !important;
  border: 1px solid {GOLD_DIM} !important;
  font-weight: 600 !important;
  border-radius: 10px !important;
  box-shadow: 0 6px 20px rgba(212,160,23,0.25) !important;
}}

.stButton > button p,
.stButton > button span,
.stDownloadButton > button p,
.stDownloadButton > button span,
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span,
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span,
[data-testid="stBaseButton-tertiary"] p,
[data-testid="stBaseButton-tertiary"] span {{
  background: transparent !important;
  color: inherit !important;
}}

button[kind="primary"]:hover,
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover {{
  background: linear-gradient(90deg, {GOLD_DIM}, {GOLD}) !important;
  color: #1a1a1f !important;
  transform: translateY(-2px);
  box-shadow: 0 8px 28px rgba(212,160,23,0.35) !important;
}}

.stDownloadButton > button {{
  background: {BG_2} !important;
  color: {TEXT_0} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 10px !important;
  padding: 10px 20px !important;
  font-weight: 500 !important;
  font-size: 0.9rem !important;
  transition: all 0.2s ease !important;
}}

.stDownloadButton > button:hover {{
  border-color: {GOLD} !important;
  color: {GOLD} !important;
  background: rgba(212,160,23,0.08) !important;
  transform: translateY(-1px);
}}

div[data-baseweb="checkbox"] input:checked + div {{
  background-color: {GOLD} !important;
  border-color: {GOLD} !important;
}}

.lab-banner {{
  background: {BG_1};
  border: 1px solid {BORDER};
  border-left: 6px solid {GOLD};
  border-radius: 12px;
  padding: 14px;
  margin: 10px 0 12px 0;
}}

.lab-banner-title {{
  font-weight: 700;
  margin-bottom: 6px;
}}

.lab-banner-body {{
  color: {TEXT_1};
}}

.lab-banner-error {{
  background: {BG_2};
  border-left-color: {BORDER};
}}

.main-header {{
  font-size: 2.5rem;
  font-weight: bold;
  color: {GOLD};
  margin-bottom: 0.5rem;
}}

.sub-header {{
  font-size: 1.2rem;
  color: {TEXT_1};
  margin-bottom: 2rem;
}}

.section-header {{
  font-size: 1.5rem;
  font-weight: bold;
  color: {TEXT_0};
  margin-top: 1.5rem;
  margin-bottom: 1rem;
  border-bottom: 2px solid {GOLD};
  padding-bottom: 0.5rem;
}}

.data-box {{
  background-color: {BG_1};
  padding: 1rem;
  border-radius: 0.5rem;
  border-left: 4px solid {GOLD};
  margin: 1rem 0;
}}

.success-box {{
  background-color: {BG_1};
  padding: 1rem;
  border-radius: 0.5rem;
  border-left: 4px solid {GOLD};
  margin: 1rem 0;
}}

.warning-box {{
  background-color: {BG_1};
  padding: 1rem;
  border-radius: 0.5rem;
  border-left: 4px solid {GOLD_DIM};
  margin: 1rem 0;
}}

.error-box {{
  background-color: {BG_2};
  padding: 1rem;
  border-radius: 0.5rem;
  border-left: 4px solid {BORDER};
  margin: 1rem 0;
}}

.claim-card {{
  background-color: {BG_1};
  border: 1px solid {BORDER};
  border-radius: 8px;
  padding: 1rem;
  margin: 0.5rem 0;
}}

.awaiting-review {{
  border-left: 4px solid {GOLD_DIM};
}}

.low-confidence {{
  border-left: 4px solid {BORDER};
}}

.confirmed-accurate {{
  border-left: 4px solid {GOLD};
}}

.marked-inaccurate {{
  border-left: 4px solid {GOLD};
}}

.workflow-header {{
  position: sticky;
  top: 0;
  z-index: 999;
  background: {BG_1};
  border: 1px solid {BORDER};
  padding: 0.75rem 1rem;
  border-radius: 12px;
  margin-bottom: 1rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}

.workflow-steps {{
  display: flex;
  justify-content: space-around;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}}

.workflow-step {{
  color: {TEXT_1};
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-weight: 500;
  font-size: 0.9rem;
  text-align: center;
}}

.workflow-step.active {{
  background: rgba(212,160,23,0.1);
  border: 2px solid {GOLD};
  color: {GOLD};
}}

.workflow-step.completed {{
  background: rgba(212,160,23,0.15);
  color: {GOLD};
}}

.workflow-step.pending {{
  opacity: 0.5;
}}

.confidence-badge {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
  margin-left: 8px;
}}

.confidence-high {{
  background: rgba(212,160,23,0.12);
  color: {GOLD};
}}

.confidence-medium {{
  background: rgba(100,100,100,0.12);
  color: {TEXT_1};
}}

.confidence-low {{
  background: rgba(200,200,200,0.5);
  color: {TEXT_1};
}}

.disputable-reason {{
  background: {BG_1};
  border-left: 3px solid {GOLD};
  padding: 0.5rem;
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: {TEXT_1};
}}

@keyframes cardFadeIn {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.card-viewport {{
  animation: cardFadeIn 0.25s ease-out;
}}

.card-title {{
  font-size: 1.8rem;
  font-weight: 700;
  color: {GOLD};
  margin-bottom: 0.25rem;
  line-height: 1.3;
  padding-top: 0.1rem;
  overflow: visible !important;
}}

.card-body-copy {{
  color: {TEXT_1};
  font-size: 1rem;
  line-height: 1.5;
  margin-bottom: 1.25rem;
}}

.card-progress {{
  display: flex;
  gap: 8px;
  margin-bottom: 1.5rem;
}}

.card-progress-dot {{
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: {BORDER};
}}

.card-progress-dot.active {{
  background: {GOLD};
}}

.card-progress-dot.done {{
  background: {GOLD_DIM};
}}

.auth-container {{
  max-width: 440px;
  margin: 0 auto;
  padding: 1rem 1.5rem;
}}

.auth-card {{
  background: {BG_1};
  border: 1px solid {BORDER};
  border-radius: 16px;
  padding: 2.5rem 2rem;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3);
}}

.auth-logo {{
  text-align: center;
  margin-bottom: 0.75rem;
  background: none;
  border: none;
}}

.auth-logo-icon {{
  font-size: 3.5rem;
  margin-bottom: 0.5rem;
}}

.auth-logo-text {{
  font-size: 2.2rem;
  font-weight: 800;
  color: {GOLD};
  letter-spacing: -0.5px;
}}

.auth-logo-sub {{
  color: {TEXT_1};
  font-size: 0.95rem;
  margin-top: 0.25rem;
}}

.auth-divider {{
  text-align: center;
  color: {TEXT_1};
  font-size: 0.85rem;
  margin: 1rem 0;
  position: relative;
}}

.auth-divider::before, .auth-divider::after {{
  content: '';
  position: absolute;
  top: 50%;
  width: 40%;
  height: 1px;
  background: {BORDER};
}}

.auth-divider::before {{ left: 0; }}
.auth-divider::after {{ right: 0; }}

section[data-testid="stSidebar"] {{
  background: {BG_1} !important;
  border-right: 1px solid rgba(255,215,140,0.08);
}}

section[data-testid="stSidebar"][aria-expanded="false"] {{
  width: auto !important;
  min-width: auto !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] > div:first-child {{
  width: 0 !important;
  overflow: hidden !important;
  visibility: hidden !important;
}}

section[data-testid="stSidebar"] .stMarkdown {{
  padding: 0 0.25rem;
}}

.sidebar-user-card {{
  background: {BG_2};
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 1rem;
  margin-bottom: 1rem;
  text-align: center;
}}

.sidebar-user-name {{
  font-size: 1.05rem;
  font-weight: 600;
  color: {TEXT_0};
  margin-bottom: 0.25rem;
}}

.sidebar-user-tier {{
  display: inline-block;
  padding: 3px 12px;
  border-radius: 20px;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}}

.sidebar-tier-free {{
  background: rgba(100,100,100,0.1);
  color: {TEXT_1};
  border: 1px solid {BORDER};
}}

.sidebar-tier-glow {{
  background: rgba(212,160,23,0.1);
  color: {GOLD};
  border: 1px solid rgba(212,160,23,0.2);
  box-shadow: 0 0 8px rgba(212,160,23,0.08);
}}

.sidebar-entitlements {{
  display: flex;
  gap: 6px;
  margin-top: 6px;
  flex-wrap: wrap;
}}

.ent-badge {{
  display: inline-block;
  padding: 3px 10px;
  border-radius: 16px;
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(212,160,23,0.08);
  color: {GOLD};
  border: 1px solid rgba(212,160,23,0.15);
  letter-spacing: 0.02em;
}}

.sidebar-section-title {{
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: {TEXT_1};
  margin: 1rem 0 0.5rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid {BORDER};
}}

.tier-card {{
  background: {BG_1};
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 1.5rem;
  margin: 1rem 0;
  text-align: center;
}}

.tier-card.glow {{
  border-color: {GOLD};
  box-shadow: 0 0 20px rgba(212, 160, 23, 0.1);
}}

.tier-badge {{
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}}

.tier-free {{
  background: rgba(100,100,100,0.12);
  color: {TEXT_1};
}}

.tier-glow {{
  background: rgba(212,160,23,0.12);
  color: {GOLD};
}}

.user-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  margin-bottom: 1rem;
}}

[data-testid="stTable"] table th,
[data-testid="stTable"] table td {{
  white-space: nowrap !important;
}}

.findings-card {{
  background: {BG_1};
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 1.25rem;
  margin: 0.75rem 0;
}}

.findings-count {{
  font-size: 2rem;
  font-weight: 700;
  color: {GOLD};
}}

.findings-label {{
  color: {TEXT_1};
  font-size: 0.9rem;
}}

.findings-context {{
  color: {TEXT_1};
  font-size: 0.75rem;
  margin-top: 0.25rem;
  opacity: 0.7;
}}

.summary-cta {{
  text-align: center;
  margin: 2rem 0 0.5rem 0;
  padding: 1.5rem;
  border-top: 1px solid {BORDER};
}}
.summary-cta-text {{
  font-size: 0.9rem;
  color: {TEXT_1};
  margin-bottom: 0.75rem;
}}

.upsell-box {{
  background: linear-gradient(135deg, {BG_1} 0%, rgba(212,160,23,0.06) 100%);
  border: 2px solid {GOLD};
  border-radius: 16px;
  padding: 2rem;
  text-align: center;
  margin: 1.5rem 0;
}}

.upsell-title {{
  font-size: 1.3rem;
  font-weight: 700;
  color: {GOLD};
  margin-bottom: 0.5rem;
}}

.upsell-body {{
  color: {TEXT_1};
  font-size: 0.95rem;
  line-height: 1.6;
  margin-bottom: 1rem;
}}

/* ── Main content max-width wrapper ── */
.block-container {{
  max-width: 1100px !important;
  padding-left: 2rem !important;
  padding-right: 2rem !important;
  padding-top: 1rem !important;
  box-sizing: border-box !important;
  overflow-x: hidden !important;
  word-wrap: break-word !important;
}}

* {{
  box-sizing: border-box;
}}

img, video, iframe, table, pre, code {{
  max-width: 100% !important;
  overflow-x: auto !important;
}}

[data-testid="stFileUploader"],
[data-testid="stExpander"],
[data-testid="stMetric"],
[data-testid="stTabs"] {{
  max-width: 100% !important;
  overflow-x: hidden !important;
  word-wrap: break-word !important;
  overflow-wrap: break-word !important;
}}

[data-testid="stExpander"] {{
  background: rgba(255,215,120,0.04) !important;
  border: 1px solid rgba(255,215,140,0.12) !important;
  border-radius: 14px !important;
}}

[data-testid="stExpander"] summary,
[data-testid="stExpander"] [data-testid="stExpanderToggleDetails"] {{
  background: transparent !important;
  color: {TEXT_0} !important;
}}

[data-testid="stExpander"] details {{
  background: transparent !important;
}}

[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary p {{
  color: {TEXT_0} !important;
}}

[data-testid="stExpander"] summary svg {{
  color: {TEXT_1} !important;
  fill: {TEXT_1} !important;
}}

[data-testid="stExpander"] summary:hover {{
  color: {GOLD} !important;
}}

[data-testid="stExpander"] summary:hover svg {{
  color: {GOLD} !important;
  fill: {GOLD} !important;
}}

[data-testid="stMarkdown"] {{
  max-width: 100% !important;
  overflow: visible !important;
  word-wrap: break-word !important;
  overflow-wrap: break-word !important;
}}

/* ── Tablet breakpoint (768px) ── */
@media (max-width: 768px) {{
  .block-container {{
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    padding-top: 1rem !important;
  }}

  .main-header {{
    font-size: 1.5rem !important;
  }}
  .sub-header {{
    font-size: 0.9rem !important;
  }}
  .card-title {{
    font-size: 1.3rem !important;
  }}
  .card-body-copy {{
    font-size: 0.9rem !important;
  }}
  .stTable, .stDataFrame {{
    font-size: 0.8rem !important;
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
  }}
  .stDataFrame > div {{
    overflow-x: auto !important;
  }}
  section[data-testid="stSidebar"] {{
    width: 260px !important;
  }}
  .findings-count {{
    font-size: 1.5rem !important;
  }}
  .findings-card {{
    padding: 1rem;
  }}

  .auth-container {{
    max-width: 100% !important;
    padding: 0.5rem 0.75rem !important;
  }}
  .auth-card {{
    padding: 1rem 1.25rem !important;
    border-radius: 12px !important;
  }}
  .auth-logo-text {{
    font-size: 1.8rem !important;
  }}
  .auth-logo-icon {{
    font-size: 2.5rem !important;
  }}

  .workflow-header {{
    padding: 0.5rem 0.75rem !important;
    border-radius: 8px !important;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }}
  .workflow-steps {{
    flex-wrap: nowrap !important;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    gap: 0.35rem !important;
    padding-bottom: 4px;
    justify-content: flex-start !important;
  }}
  .workflow-step {{
    font-size: 0.75rem !important;
    padding: 0.35rem 0.65rem !important;
    white-space: nowrap;
    flex-shrink: 0;
  }}

  .card-progress {{
    gap: 6px !important;
  }}

  .lab-card {{
    padding: 12px !important;
    border-radius: 10px !important;
  }}

  .lab-banner {{
    padding: 10px !important;
    border-radius: 8px !important;
  }}

  .tier-card {{
    padding: 1rem !important;
  }}

  .upsell-box {{
    padding: 1.25rem !important;
    border-radius: 12px !important;
  }}
  .upsell-title {{
    font-size: 1.1rem !important;
  }}

  .sidebar-user-card {{
    padding: 0.75rem !important;
  }}

  .user-header {{
    flex-direction: column;
    gap: 0.5rem;
    text-align: center;
  }}

  .data-box, .success-box, .warning-box, .error-box {{
    padding: 0.75rem !important;
  }}

  .claim-card {{
    padding: 0.75rem !important;
  }}

  .stButton > button {{
    padding: 10px 16px !important;
    font-size: 0.85rem !important;
    width: 100%;
    min-height: 44px;
  }}

  .confidence-badge {{
    font-size: 0.65rem !important;
    padding: 2px 6px !important;
  }}

  h1 {{ font-size: 1.5rem !important; }}
  h2 {{ font-size: 1.25rem !important; }}
  h3 {{ font-size: 1.1rem !important; }}
}}

/* ── Small phone breakpoint (480px) ── */
@media (max-width: 480px) {{
  .block-container {{
    padding-left: 0.5rem !important;
    padding-right: 0.5rem !important;
    padding-top: 0.5rem !important;
  }}

  .main-header {{
    font-size: 1.2rem !important;
  }}
  .sub-header {{
    font-size: 0.8rem !important;
  }}
  .card-title {{
    font-size: 1.1rem !important;
  }}

  .auth-card {{
    padding: 1.25rem 1rem !important;
  }}
  .auth-logo-text {{
    font-size: 1.5rem !important;
  }}
  .auth-logo-icon {{
    font-size: 2rem !important;
  }}

  .workflow-step {{
    font-size: 0.75rem !important;
    padding: 0.3rem 0.5rem !important;
  }}

  .stButton > button {{
    padding: 12px 16px !important;
    font-size: 0.84rem !important;
  }}

  .sidebar-user-card {{
    padding: 0.5rem !important;
  }}
  .sidebar-user-name {{
    font-size: 0.9rem !important;
  }}

  section[data-testid="stSidebar"] {{
    width: 240px !important;
  }}

  .findings-count {{
    font-size: 1.25rem !important;
  }}
  .findings-label {{
    font-size: 0.84rem !important;
  }}

  .section-header {{
    font-size: 1.15rem !important;
  }}

  .lab-card {{
    padding: 10px !important;
    border-radius: 8px !important;
    margin-bottom: 8px !important;
  }}

  .tier-card {{
    padding: 0.75rem !important;
  }}

  .upsell-box {{
    padding: 1rem !important;
  }}
  .upsell-title {{
    font-size: 1rem !important;
  }}
  .upsell-body {{
    font-size: 0.85rem !important;
  }}

  h1 {{ font-size: 1.3rem !important; }}
  h2 {{ font-size: 1.1rem !important; }}
  h3 {{ font-size: 1rem !important; }}
}}

/* ── Landing Page — Apple-style minimal ── */
.lp-hero {{
  text-align: center;
  padding: 3.5rem 2rem 2.5rem;
  max-width: 820px;
  margin: 0 auto;
  background: {BG_0} !important;
  color: {TEXT_0} !important;
}}

.lp-cta-row {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  max-width: 420px;
  margin: 0 auto;
}}

.lp-btn-primary {{
  display: block;
  width: 100%;
  padding: 1.1rem 2rem;
  background: {GOLD};
  color: #fff !important;
  font-weight: 700;
  font-size: 1.15rem;
  text-align: center;
  text-decoration: none;
  border-radius: 10px;
  border: 2px solid {GOLD};
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s, transform 0.15s, box-shadow 0.2s;
  box-sizing: border-box;
  box-shadow: 0 4px 16px rgba(212,160,23,0.25);
}}
.lp-btn-primary:hover {{
  background: {GOLD_DIM};
  border-color: {GOLD_DIM};
  color: #fff !important;
  text-decoration: none;
  transform: translateY(-1px);
  box-shadow: 0 6px 24px rgba(212,160,23,0.35);
}}

.lp-btn-secondary {{
  display: block;
  width: 100%;
  padding: 0.85rem 1.5rem;
  background: {BG_0};
  color: {TEXT_0} !important;
  font-weight: 600;
  font-size: 1rem;
  text-align: center;
  text-decoration: none;
  border-radius: 8px;
  border: 2px solid {BORDER};
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
  box-sizing: border-box;
}}
.lp-btn-secondary:hover {{
  border-color: {GOLD};
  color: {GOLD} !important;
  text-decoration: none;
}}

.lp-btn-demo {{
  display: block;
  width: 100%;
  padding: 0.85rem 1.5rem;
  background: transparent;
  color: {GOLD} !important;
  font-weight: 600;
  font-size: 1rem;
  text-align: center;
  text-decoration: none;
  border-radius: 8px;
  border: 2px solid {GOLD};
  cursor: pointer;
  transition: background 0.2s, color 0.2s, transform 0.15s, box-shadow 0.2s;
  box-sizing: border-box;
}}
.lp-btn-demo:hover {{
  background: rgba(212,160,23,0.1);
  color: {GOLD} !important;
  text-decoration: none;
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(212,160,23,0.2);
}}

.lp-btn-login-link {{
  display: block;
  width: 100%;
  padding: 0.4rem 0;
  background: transparent;
  color: {TEXT_1} !important;
  font-weight: 400;
  font-size: 0.88rem;
  text-align: center;
  text-decoration: none;
  border: none;
  cursor: pointer;
}}
.lp-btn-login-link:hover {{
  color: {GOLD} !important;
  text-decoration: underline;
}}

.lp-demo-callout {{
  background: linear-gradient(135deg, rgba(212,160,23,0.08), rgba(212,160,23,0.02));
  border: 1px solid rgba(212,160,23,0.25);
  border-radius: 14px;
  padding: 2rem 1.5rem;
  text-align: center;
  max-width: 520px;
  margin: 0 auto;
}}
.lp-demo-callout-icon {{
  font-size: 2.2rem;
  margin-bottom: 0.5rem;
}}
.lp-demo-callout-title {{
  font-size: 1.15rem;
  font-weight: 700;
  color: {TEXT_0};
  margin-bottom: 0.4rem;
}}
.lp-demo-callout-text {{
  font-size: 0.9rem;
  color: {TEXT_1};
  line-height: 1.5;
  margin-bottom: 1rem;
}}
.lp-demo-callout-btn {{
  display: inline-block;
  padding: 0.75rem 2rem;
  background: {GOLD};
  color: #fff !important;
  font-weight: 700;
  font-size: 1rem;
  text-decoration: none;
  border-radius: 8px;
  border: 2px solid {GOLD};
  transition: background 0.2s, transform 0.15s, box-shadow 0.2s;
}}
.lp-demo-callout-btn:hover {{
  background: {GOLD_DIM};
  border-color: {GOLD_DIM};
  color: #fff !important;
  text-decoration: none;
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(212,160,23,0.3);
}}

.lp-logo {{
  width: 420px;
  height: auto;
  margin-bottom: 0.8rem;
  opacity: 0.95;
}}

.element-container:has(.lp-hero),
.element-container:has(.lp-section),
.element-container:has(.lp-footer) {{
  margin: 0 !important;
  padding: 0 !important;
  gap: 0 !important;
}}

.lp-headline {{
  font-size: 3.4rem;
  font-weight: 900;
  color: {TEXT_0};
  letter-spacing: -0.03em;
  line-height: 1.08;
  margin: 0 0 1.2rem 0;
  text-transform: none;
}}
.lp-headline .lp-accent {{
  color: {GOLD};
}}

.lp-subheadline {{
  font-size: 1.25rem;
  color: {TEXT_1};
  line-height: 1.5;
  margin: 0 0 2rem 0;
  max-width: 480px;
  margin-left: auto;
  margin-right: auto;
}}

.lp-urgency {{
  font-size: 0.88rem;
  color: {GOLD};
  line-height: 1.5;
  margin: 0 auto 1.5rem auto;
  max-width: 480px;
  padding: 0.75rem 1rem;
  border: 1px solid rgba(212,160,23,0.25);
  border-radius: 8px;
  background: rgba(212,160,23,0.05);
}}

@keyframes lpFadeUp {{
  from {{ opacity: 0; transform: translateY(28px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
.lp-animate {{
  opacity: 0;
  transform: translateY(28px);
  transition: opacity 0.6s ease-out, transform 0.6s ease-out;
}}
.lp-animate.lp-visible {{
  opacity: 1;
  transform: translateY(0);
}}
@media (prefers-reduced-motion: reduce) {{
  .lp-animate {{
    opacity: 1;
    transform: none;
    transition: none;
  }}
}}

.lp-section {{
  max-width: 800px;
  margin: 0 auto;
  padding: 3rem 1.5rem;
  background: {BG_0} !important;
  color: {TEXT_0} !important;
}}

.lp-section-title {{
  font-size: 2.4rem;
  font-weight: 900;
  color: {TEXT_0};
  text-align: center;
  letter-spacing: -0.03em;
  margin: 0 0 1.5rem 0;
}}
.lp-how-title {{
  font-size: 2.6rem !important;
}}

/* ── Steps: horizontal flow ── */
.lp-steps {{
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 0;
}}

.lp-step {{
  text-align: center;
  flex: 1;
  max-width: 220px;
  padding: 0 1rem;
}}

.lp-step-num {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: {GOLD};
  color: #fff;
  font-weight: 800;
  font-size: 1.1rem;
  margin-bottom: 0.75rem;
  box-shadow: 0 3px 12px rgba(212,160,23,0.25);
}}

.lp-step-word {{
  display: block;
  font-size: 1.3rem;
  font-weight: 700;
  color: {TEXT_0};
  margin-bottom: 0.35rem;
}}

.lp-step-detail {{
  display: block;
  font-size: 0.9rem;
  color: {TEXT_1};
  line-height: 1.45;
}}

.lp-step-divider {{
  width: 48px;
  height: 1px;
  background: {BORDER};
  margin-top: 18px;
  flex-shrink: 0;
}}

/* ── Features: clean two-column grid, no boxes ── */
.lp-features-section {{
  border-top: 1px solid {BORDER};
}}

.lp-feature-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2.5rem 4rem;
}}

.lp-feature-item {{
  padding: 0;
}}

.lp-feature-name {{
  font-size: 1.05rem;
  font-weight: 600;
  color: {TEXT_0};
  margin-bottom: 0.25rem;
}}

.lp-feature-line {{
  font-size: 0.9rem;
  color: {TEXT_1};
  line-height: 1.4;
}}

/* ── Plans: side by side, minimal ── */
.lp-plans-section {{
  border-top: 1px solid {BORDER};
}}

.lp-plans {{
  display: flex;
  gap: 1.5rem;
  justify-content: center;
  align-items: flex-start;
  flex-wrap: wrap;
}}

.lp-plan {{
  flex: 1;
  min-width: 180px;
  max-width: 240px;
  text-align: center;
  display: flex;
  flex-direction: column;
}}

.lp-plan-name {{
  font-size: 1.1rem;
  font-weight: 600;
  color: {TEXT_1};
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 0.25rem;
}}

.lp-plan-glow .lp-plan-name {{
  color: {GOLD};
}}

.lp-plan-price {{
  font-size: 2.8rem;
  font-weight: 800;
  color: {TEXT_0};
  letter-spacing: -1px;
  margin-bottom: 1rem;
}}

.lp-plan-price span {{
  font-size: 0.85rem;
  font-weight: 400;
  color: {TEXT_1};
  letter-spacing: 0;
}}

.lp-plan-list {{
  font-size: 0.9rem;
  color: {TEXT_1};
  line-height: 1.8;
  margin-bottom: 1.25rem;
}}

.lp-plan-cta {{
  display: block;
  padding: 0.6rem 1rem;
  border: 2px solid {BORDER};
  border-radius: 8px;
  text-align: center;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.9rem;
  color: {TEXT_0} !important;
  transition: border-color 0.2s, color 0.2s;
  margin-top: auto;
}}
.lp-plan-cta:hover {{
  border-color: {GOLD};
  color: {GOLD} !important;
  text-decoration: none;
}}
.lp-plan-cta-primary {{
  background: {GOLD};
  border-color: {GOLD};
  color: #fff !important;
}}
.lp-plan-cta-primary:hover {{
  background: {GOLD_DIM};
  border-color: {GOLD_DIM};
  color: #fff !important;
}}

.lp-round-explainer {{
  max-width: 560px;
  margin: 0 auto 2.5rem auto;
  padding: 1rem 1.25rem;
  background: {BG_1};
  border: 1px solid {BORDER};
  border-radius: 8px;
  font-size: 0.9rem;
  color: {TEXT_1};
  line-height: 1.5;
  text-align: center;
}}
.lp-round-explainer strong {{
  color: {TEXT_0};
}}

/* ── Trust: card grid ── */
.lp-trust-section {{
  border-top: 1px solid {BORDER};
}}

.lp-trust-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  max-width: 700px;
  margin: 0 auto;
}}

.lp-trust-card {{
  padding: 1.25rem;
  border: 1px solid {BORDER};
  border-radius: 8px;
  background: {BG_1};
}}
.lp-trust-card-title {{
  font-size: 1rem;
  font-weight: 600;
  color: {TEXT_0};
  margin-bottom: 0.35rem;
}}
.lp-trust-card-body {{
  font-size: 0.85rem;
  color: {TEXT_1};
  line-height: 1.5;
}}

/* ── FAQ ── */
.lp-faq-section {{
  border-top: 1px solid {BORDER};
}}

.lp-faq-list {{
  max-width: 640px;
  margin: 0 auto;
}}

.lp-faq-item {{
  border-bottom: 1px solid {BORDER};
  padding: 0;
}}

.lp-faq-q {{
  font-size: 1.05rem;
  font-weight: 600;
  color: {TEXT_0};
  cursor: pointer;
  padding: 1rem 0;
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
}}
.lp-faq-q::-webkit-details-marker {{
  display: none;
}}
.lp-faq-q::after {{
  content: '+';
  font-size: 1.3rem;
  color: {TEXT_1};
  transition: transform 0.2s;
  flex-shrink: 0;
  margin-left: 1rem;
}}
details[open] .lp-faq-q::after {{
  content: '\\2212';
}}

.lp-faq-a {{
  font-size: 0.9rem;
  color: {TEXT_1};
  line-height: 1.6;
  padding: 0 0 1.25rem 0;
}}

/* ── Hero value props row ── */
.lp-hero-value-row {{
  display: flex;
  justify-content: center;
  gap: 1.5rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  font-size: 0.85rem;
  color: {TEXT_1};
}}
.lp-hero-value-row span {{
  color: {GOLD};
}}

/* ── Social proof ── */
.lp-social-proof {{
  font-size: 0.85rem;
  color: {TEXT_1};
  margin-top: 1rem;
  text-align: center;
  opacity: 0.8;
}}

/* ── Hero note ── */
.lp-hero-note {{
  font-size: 0.8rem;
  color: {TEXT_1};
  margin-top: 0.75rem;
  opacity: 0.7;
}}

/* ── Stats row ── */
.lp-stats-section {{
  border-top: 1px solid {BORDER};
  border-bottom: 1px solid {BORDER};
  padding-top: 3rem !important;
  padding-bottom: 3rem !important;
}}
.lp-stats-row {{
  display: flex;
  justify-content: center;
  gap: 3rem;
  flex-wrap: wrap;
}}
.lp-stat {{
  text-align: center;
  min-width: 140px;
}}
.lp-stat-num {{
  font-size: 2.4rem;
  font-weight: 800;
  color: {GOLD};
  letter-spacing: -1px;
  line-height: 1.1;
}}
.lp-stat-label {{
  font-size: 0.85rem;
  color: {TEXT_1};
  margin-top: 0.35rem;
  line-height: 1.3;
}}
.lp-stats-source {{
  text-align: center;
  font-size: 0.72rem;
  color: {TEXT_1};
  opacity: 0.5;
  margin-top: 1.5rem;
}}

/* ── Problem section ── */
.lp-problem-section {{
  text-align: center;
}}
.lp-section-sub {{
  font-size: 1rem;
  color: {TEXT_1};
  line-height: 1.6;
  max-width: 640px;
  margin: -1.5rem auto 0 auto;
  text-align: center;
}}

/* ── Get Your Reports section ── */
.lp-get-reports {{
  text-align: center;
}}
.lp-reports-card {{
  background: {BG_1};
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 2rem;
  max-width: 680px;
  margin: 1.5rem auto 0 auto;
  text-align: left;
}}
.lp-reports-steps {{
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  margin-bottom: 1.5rem;
}}
.lp-reports-step {{
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  font-size: 0.95rem;
  color: {TEXT_0};
  line-height: 1.5;
}}
.lp-reports-step strong {{
  color: {TEXT_0};
}}
.lp-reports-icon {{
  font-size: 1.5rem;
  flex-shrink: 0;
  margin-top: 0.1rem;
}}
.lp-reports-detail {{
  color: {TEXT_1};
  font-size: 0.88rem;
}}
.lp-reports-actions {{
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}}
.lp-reports-note {{
  font-size: 0.78rem;
  color: {TEXT_1};
  opacity: 0.7;
  text-align: center;
  margin: 0;
}}

.lp-guide-tip {{
  background: rgba(212,160,23,0.08);
  border: 1px solid rgba(212,160,23,0.2);
  border-radius: 10px;
  padding: 0.8rem 1.2rem;
  font-size: 0.92rem;
  color: {GOLD};
  text-align: center;
  margin: 1rem auto 1.5rem auto;
  max-width: 520px;
}}
.lp-guide-tip strong {{
  color: {TEXT_0};
}}
.lp-guide-more {{
  max-width: 520px;
  margin: 0.8rem auto 0 auto;
}}
.lp-guide-more-toggle {{
  display: block;
  text-align: center;
  font-size: 0.88rem;
  font-weight: 600;
  color: {GOLD};
  cursor: pointer;
  padding: 0.6rem 0;
  list-style: none;
}}
.lp-guide-more-toggle::-webkit-details-marker {{
  display: none;
}}
.lp-guide-more-toggle::after {{
  content: ' \\25BE';
  font-size: 0.75rem;
}}
.lp-guide-more[open] > .lp-guide-more-toggle::after {{
  content: ' \\25B4';
}}
.lp-guide-more-list {{
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-top: 0.4rem;
  border: 1px solid {BORDER};
  border-radius: 10px;
  overflow: hidden;
}}
.lp-guide-row {{
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.7rem 1rem;
  border-bottom: 1px solid {BORDER};
  background: {BG_1};
}}
.lp-guide-row:last-child {{
  border-bottom: none;
}}
.lp-guide-row-name {{
  font-size: 0.88rem;
  font-weight: 700;
  color: {TEXT_0};
  white-space: nowrap;
}}
.lp-guide-row-desc {{
  font-size: 0.78rem;
  color: {TEXT_1};
  flex: 1;
}}
.lp-guide-row-link {{
  font-size: 0.8rem;
  font-weight: 600;
  color: {GOLD} !important;
  text-decoration: none;
  white-space: nowrap;
}}
.lp-guide-row-link:hover {{
  text-decoration: underline;
}}
.lp-guide-card {{
  background: {BG_1};
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}}
.lp-guide-featured {{
  border-color: rgba(212,160,23,0.35);
  background: linear-gradient(135deg, rgba(212,160,23,0.06), rgba(212,160,23,0.02));
  max-width: 520px;
  margin: 0 auto;
}}
.lp-guide-card-badge {{
  display: inline-block;
  background: {GOLD};
  color: #1a1a1f;
  font-size: 0.7rem;
  font-weight: 800;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.2rem;
  width: fit-content;
}}
.lp-guide-card-name {{
  font-size: 1rem;
  font-weight: 700;
  color: {TEXT_0};
}}
.lp-guide-card-desc {{
  font-size: 0.82rem;
  color: {TEXT_1};
  line-height: 1.5;
}}
.lp-guide-card-link {{
  display: inline-block;
  font-size: 0.85rem;
  font-weight: 600;
  color: {GOLD} !important;
  text-decoration: none;
  margin-top: 0.3rem;
}}
.lp-guide-card-link:hover {{
  text-decoration: underline;
  color: {GOLD} !important;
}}

/* ── Comparison table ── */
.lp-comparison-section {{
  border-top: 1px solid {BORDER};
}}
.lp-compare-table {{
  max-width: 600px;
  margin: 0 auto;
  border: 1px solid {BORDER};
  border-radius: 10px;
  overflow: hidden;
}}
.lp-compare-header,
.lp-compare-row {{
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
}}
.lp-compare-header {{
  background: {BG_1};
  border-bottom: 1px solid {BORDER};
}}
.lp-compare-row {{
  border-bottom: 1px solid {BORDER};
}}
.lp-compare-row:last-child {{
  border-bottom: none;
}}
.lp-compare-cell {{
  padding: 0.8rem 1rem;
  font-size: 0.88rem;
  color: {TEXT_1};
}}
.lp-compare-label {{
  font-weight: 600;
  color: {TEXT_0};
}}
.lp-compare-them {{
  text-align: center;
  color: {TEXT_1};
  opacity: 0.7;
}}
.lp-compare-us {{
  text-align: center;
  color: {GOLD};
  font-weight: 600;
}}
.lp-compare-header .lp-compare-them {{
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.6;
}}
.lp-compare-header .lp-compare-us {{
  font-weight: 700;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}

/* ── Testimonials ── */
.lp-testimonials-section {{
  border-top: 1px solid {BORDER};
}}
.lp-testimonial-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1.5rem;
  max-width: 800px;
  margin: 0 auto;
}}
.lp-testimonial {{
  padding: 1.5rem;
  border: 1px solid {BORDER};
  border-radius: 10px;
  background: {BG_1};
}}
.lp-testimonial-text {{
  font-size: 0.9rem;
  color: {TEXT_0};
  line-height: 1.55;
  font-style: italic;
  margin-bottom: 0.75rem;
}}
.lp-testimonial-author {{
  font-size: 0.82rem;
  color: {GOLD};
  font-weight: 600;
}}

/* ── Plan popular badge ── */
.lp-plan-popular {{
  position: relative;
  border: 2px solid {GOLD};
  border-radius: 12px;
  padding-top: 2rem;
}}
.lp-plan-badge {{
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: {GOLD};
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  padding: 0.25rem 0.9rem;
  border-radius: 20px;
  white-space: nowrap;
}}

/* ── Best Value plan ── */
.lp-plan-best-value {{
  position: relative;
  border: 2px solid {GOLD};
  border-radius: 12px;
  padding-top: 2rem;
  background: linear-gradient(180deg, rgba(212,175,55,0.06) 0%, transparent 40%);
}}
.lp-plan-best-value .lp-plan-badge-value {{
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, {GOLD}, #e8c848);
  color: #1a1a1a;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  padding: 0.25rem 0.9rem;
  border-radius: 20px;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(212,175,55,0.3);
}}
.lp-plan-best-value .lp-plan-name {{
  color: {GOLD};
}}
.lp-plan-best-value .lp-plan-price {{
  color: {GOLD};
}}

/* ── Dimmed plans ── */
.lp-plan-dimmed {{
  opacity: 0.6;
  transition: opacity 0.2s;
}}
.lp-plan-dimmed:hover {{
  opacity: 0.85;
}}

/* ── Sprint Hero Section (Lane A) ── */
.lp-sprint-hero {{
  max-width: 740px;
  margin: 0 auto 2.5rem;
  border: 2px solid {GOLD};
  border-radius: 16px;
  padding: 2.5rem 2rem;
  background: linear-gradient(180deg, rgba(212,175,55,0.10) 0%, rgba(212,175,55,0.02) 100%);
  box-shadow: 0 6px 32px rgba(212,175,55,0.12);
  text-align: center;
  position: relative;
}}
.lp-sprint-hero-badge {{
  display: inline-block;
  background: linear-gradient(135deg, {GOLD}, #e8c848);
  color: #1a1a1a;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 0.3rem 1rem;
  border-radius: 20px;
  margin-bottom: 1rem;
  box-shadow: 0 2px 8px rgba(212,175,55,0.3);
}}
.lp-sprint-hero-title {{
  font-size: 1.6rem;
  font-weight: 800;
  color: {TEXT_0};
  margin-bottom: 0.5rem;
  letter-spacing: -0.02em;
}}
.lp-sprint-hero-subtitle {{
  font-size: 1rem;
  color: {TEXT_1};
  margin-bottom: 1.2rem;
  line-height: 1.6;
}}
.lp-sprint-hero-price {{
  font-size: 2rem;
  font-weight: 800;
  color: {GOLD};
  margin-bottom: 0.5rem;
}}
.lp-sprint-hero-includes {{
  text-align: left;
  display: inline-block;
  margin: 0.5rem auto 1.5rem;
  font-size: 0.9rem;
  color: {TEXT_0};
  line-height: 1.9;
}}
.lp-sprint-hero-includes span {{
  color: {GOLD};
  margin-right: 6px;
}}
.lp-sprint-hero-guarantee {{
  font-size: 0.85rem;
  font-weight: 600;
  color: {GOLD};
  margin-bottom: 1.2rem;
}}
.lp-sprint-hero-cta {{
  display: inline-block;
  background: linear-gradient(135deg, {GOLD}, #e8c848);
  color: #1a1a1a;
  font-size: 1rem;
  font-weight: 700;
  padding: 0.85rem 2rem;
  border-radius: 8px;
  text-decoration: none;
  border: none;
  box-shadow: 0 4px 16px rgba(212,175,55,0.3);
  transition: transform 0.15s, box-shadow 0.15s;
}}
.lp-sprint-hero-cta:hover {{
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(212,175,55,0.4);
  color: #1a1a1a;
  text-decoration: none;
}}
.lp-sprint-hero-note {{
  font-size: 0.78rem;
  color: {TEXT_1};
  margin-top: 0.8rem;
}}
.lp-diy-divider {{
  text-align: center;
  margin: 2rem auto 1.5rem;
  font-size: 0.85rem;
  color: {TEXT_1};
  position: relative;
}}
.lp-diy-divider::before,
.lp-diy-divider::after {{
  content: "";
  display: inline-block;
  width: 60px;
  height: 1px;
  background: {BORDER};
  vertical-align: middle;
  margin: 0 12px;
}}
@media (max-width: 600px) {{
  .lp-sprint-hero {{
    padding: 1.5rem 1rem;
    margin: 0 auto 1.5rem;
  }}
  .lp-sprint-hero-title {{
    font-size: 1.3rem;
  }}
  .lp-sprint-hero-price {{
    font-size: 1.6rem;
  }}
}}

/* ── Founding Member Hero ── */
.lp-founder-hero {{
  max-width: 740px;
  margin: 0 auto 2.5rem;
  border: 2px solid {GOLD};
  border-radius: 16px;
  padding: 2.5rem 2rem;
  background: linear-gradient(180deg, rgba(212,175,55,0.12) 0%, rgba(212,175,55,0.02) 100%);
  box-shadow: 0 6px 32px rgba(212,175,55,0.15);
  text-align: center;
  position: relative;
  overflow: hidden;
}}
.lp-founder-hero::before {{
  content: "";
  position: absolute;
  top: -60px;
  right: -60px;
  width: 150px;
  height: 150px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(212,175,55,0.12) 0%, transparent 70%);
}}
.lp-founder-badge {{
  display: inline-block;
  background: linear-gradient(135deg, {GOLD}, #e8c848);
  color: #1a1a1a;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  padding: 0.35rem 1.2rem;
  border-radius: 20px;
  margin-bottom: 1rem;
  box-shadow: 0 2px 8px rgba(212,175,55,0.3);
}}
.lp-founder-title {{
  font-size: 2.2rem;
  font-weight: 900;
  color: {TEXT_0};
  margin-bottom: 0.6rem;
  letter-spacing: -0.03em;
  line-height: 1.1;
}}
.lp-founder-subtitle {{
  font-size: 1.1rem;
  color: {TEXT_1};
  margin-bottom: 1.5rem;
  line-height: 1.6;
}}
.lp-founder-value {{
  display: flex;
  justify-content: center;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}}
.lp-founder-value-item {{
  text-align: center;
}}
.lp-founder-value-num {{
  font-size: 2rem;
  font-weight: 900;
  color: {GOLD};
}}
.lp-founder-value-label {{
  font-size: 0.82rem;
  color: {TEXT_1};
  margin-top: 2px;
  font-weight: 600;
}}
.lp-founder-includes {{
  text-align: left;
  display: inline-block;
  margin: 0 auto 1.5rem;
  font-size: 0.92rem;
  color: {TEXT_0};
  line-height: 2;
}}
.lp-founder-includes span {{
  color: {GOLD};
  margin-right: 6px;
  font-weight: 700;
}}
.lp-founder-compare {{
  display: flex;
  gap: 1rem;
  justify-content: center;
  margin: 1.5rem auto;
  max-width: 500px;
  flex-wrap: wrap;
}}
.lp-founder-compare-item {{
  flex: 1;
  min-width: 180px;
  padding: 1rem;
  border-radius: 10px;
  text-align: center;
}}
.lp-founder-compare-them {{
  background: rgba(255,255,255,0.04);
  border: 1px solid {BORDER};
}}
.lp-founder-compare-us {{
  background: rgba(212,175,55,0.08);
  border: 1px solid rgba(212,175,55,0.3);
}}
.lp-founder-compare-label {{
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: {TEXT_1};
  margin-bottom: 0.4rem;
  font-weight: 600;
}}
.lp-founder-compare-price {{
  font-size: 1.4rem;
  font-weight: 800;
}}
.lp-founder-compare-them .lp-founder-compare-price {{
  color: #888;
  text-decoration: line-through;
}}
.lp-founder-compare-us .lp-founder-compare-price {{
  color: {GOLD};
}}
.lp-founder-counter {{
  margin: 1.2rem auto 1.5rem;
  font-size: 1rem;
  font-weight: 700;
  color: {GOLD};
}}
.lp-founder-counter-num {{
  font-size: 1.5rem;
  font-weight: 800;
}}
.lp-founder-cta {{
  display: inline-block;
  background: linear-gradient(135deg, {GOLD}, #e8c848);
  color: #1a1a1a;
  font-size: 1.05rem;
  font-weight: 700;
  padding: 0.9rem 2.5rem;
  border-radius: 8px;
  text-decoration: none;
  border: none;
  box-shadow: 0 4px 16px rgba(212,175,55,0.3);
  transition: transform 0.15s, box-shadow 0.15s;
}}
.lp-founder-cta:hover {{
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(212,175,55,0.4);
  color: #1a1a1a;
  text-decoration: none;
}}
.lp-founder-note {{
  font-size: 0.78rem;
  color: {TEXT_1};
  margin-top: 0.8rem;
}}
.lp-founder-closed {{
  opacity: 0.7;
}}
.lp-founder-closed .lp-founder-cta {{
  background: {BORDER};
  color: {TEXT_1};
  box-shadow: none;
  cursor: default;
}}
@keyframes lp-pulse {{
  0%, 100% {{ transform: scale(1); }}
  50% {{ transform: scale(1.15); }}
}}
.lp-founder-num-pulse {{
  display: inline-block;
  animation: lp-pulse 1.5s ease-in-out infinite;
  color: #ff6b6b;
}}
.lp-founder-counter-urgent {{
  color: #ff6b6b;
  font-size: 1.1rem;
}}
.lp-founder-counter-scarce {{
  color: {GOLD};
  font-size: 1.05rem;
}}
.lp-founder-cta-urgent {{
  background: linear-gradient(135deg, #ff6b6b, #ee5a24) !important;
  color: #fff !important;
  box-shadow: 0 4px 20px rgba(255,107,107,0.4);
}}
.lp-founder-cta-urgent:hover {{
  box-shadow: 0 6px 28px rgba(255,107,107,0.5);
  color: #fff !important;
}}
.lp-founder-cta-scarce {{
  box-shadow: 0 4px 20px rgba(212,175,55,0.45);
}}
.lp-founder-sidebar-badge {{
  display: inline-block;
  background: linear-gradient(135deg, {GOLD}, #e8c848);
  color: #1a1a1a;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: 6px;
  vertical-align: middle;
}}
@media (max-width: 600px) {{
  .lp-founder-hero {{
    padding: 1.5rem 1rem;
    margin: 0 auto 1.5rem;
  }}
  .lp-founder-title {{
    font-size: 1.3rem;
  }}
  .lp-founder-value {{
    gap: 0.8rem;
  }}
  .lp-founder-value-num {{
    font-size: 1.2rem;
  }}
  .lp-founder-compare {{
    flex-direction: column;
  }}
}}

/* ── Deletion Sprint plan ── */
.lp-plan-sprint {{
  position: relative;
  border: 2px solid {GOLD};
  border-radius: 12px;
  padding-top: 2rem;
  background: linear-gradient(180deg, rgba(212,175,55,0.08) 0%, transparent 40%);
  box-shadow: 0 4px 20px rgba(212,175,55,0.15);
}}
.lp-plan-sprint .lp-plan-badge-sprint {{
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, {GOLD}, #e8c848);
  color: #1a1a1a;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  padding: 0.25rem 0.9rem;
  border-radius: 20px;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(212,175,55,0.3);
}}
.lp-plan-sprint .lp-plan-name {{
  color: {GOLD};
}}
.lp-plan-sprint .lp-plan-price {{
  color: {GOLD};
  font-size: 2.2rem;
}}
.lp-plan-cta-sprint {{
  background: linear-gradient(135deg, {GOLD}, #e8c848) !important;
  color: #1a1a1a !important;
  border: none !important;
  font-weight: 700 !important;
}}

/* ── Single Round (Full Round) plan ── */
.lp-plan-diy {{
  position: relative;
  border: 2px solid {BORDER};
  border-radius: 12px;
  padding-top: 2rem;
}}
.lp-plan-diy .lp-plan-badge-diy {{
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: #1a1a1a;
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  padding: 0.25rem 0.9rem;
  border-radius: 20px;
  white-space: nowrap;
}}

/* ── Final CTA ── */
.lp-final-cta-section {{
  border-top: 1px solid {BORDER};
  text-align: center;
  padding-top: 4rem !important;
  padding-bottom: 2rem !important;
}}
.lp-final-headline {{
  font-size: 2rem;
  font-weight: 700;
  color: {TEXT_0};
  margin: 0 0 0.75rem 0;
  letter-spacing: -0.5px;
}}
.lp-final-sub {{
  font-size: 1.05rem;
  color: {TEXT_1};
  line-height: 1.5;
  margin: 0 auto 1.5rem auto;
  max-width: 480px;
}}

/* ── Footer ── */
.lp-footer {{
  text-align: center;
  padding: 3rem 1.5rem 2rem;
  color: {TEXT_1};
  font-size: 0.78rem;
  line-height: 1.5;
  opacity: 0.7;
  max-width: 600px;
  margin: 0 auto;
}}

/* ── Force light mode on landing page for dark-mode browsers ── */
@media (prefers-color-scheme: dark) {{
  .lp-hero, .lp-section, .lp-footer {{
    background: {BG_0} !important;
    color: {TEXT_0} !important;
  }}
  .lp-headline, .lp-section-title, .lp-step-word,
  .lp-feature-title, .lp-plan-name, .lp-compare-label,
  .lp-faq-q {{
    color: {TEXT_0} !important;
  }}
  .lp-subheadline, .lp-section-sub, .lp-hero-note,
  .lp-stat-label, .lp-stats-source, .lp-step-desc,
  .lp-feature-desc, .lp-compare-cell, .lp-faq-a,
  .lp-trust-text, .lp-testimonial-text {{
    color: {TEXT_1} !important;
  }}
  .lp-stat-num {{
    color: {GOLD} !important;
  }}
  .lp-plan {{
    background: {BG_0} !important;
    border-color: {BORDER} !important;
  }}
  .lp-plan.lp-plan-sprint {{
    background: {BG_0} !important;
    border-color: {GOLD} !important;
  }}
  .lp-plan.lp-plan-diy {{
    background: {BG_0} !important;
  }}
  .lp-stats-section {{
    border-color: {BORDER} !important;
  }}
  .lp-compare-header {{
    background: {BG_1} !important;
  }}
  .lp-compare-table, .lp-compare-row {{
    border-color: {BORDER} !important;
  }}
}}

/* ── Landing: tablet ── */
@media (max-width: 768px) {{
  .lp-hero {{
    padding: 2.5rem 1rem 1.5rem;
  }}
  .lp-logo {{
    width: 320px;
  }}
  .lp-headline {{
    font-size: 2.8rem;
  }}
  .lp-subheadline {{
    font-size: 1.2rem;
  }}
  .lp-section {{
    padding: 2rem 1rem;
  }}
  .lp-section-title {{
    font-size: 2rem;
  }}
  .lp-how-title {{
    font-size: 2.2rem !important;
  }}
  .lp-plans {{
    flex-direction: column;
    align-items: center;
    gap: 2.5rem;
  }}
  .lp-plan {{
    max-width: 100%;
  }}
  .lp-step-divider {{
    width: 32px;
  }}
  .lp-testimonial-grid {{
    grid-template-columns: 1fr;
    gap: 1rem;
  }}
  .lp-founder-title {{
    font-size: 1.8rem;
  }}
  .lp-founder-value-num {{
    font-size: 1.6rem;
  }}
}}

/* ── Landing: phone ── */
@media (max-width: 480px) {{
  .lp-hero {{
    padding: 2rem 1rem 1.5rem;
  }}
  .lp-logo {{
    width: 260px;
  }}
  .lp-headline {{
    font-size: 2.3rem;
  }}
  .lp-subheadline {{
    font-size: 1.15rem;
  }}
  .lp-section {{
    padding: 1.5rem 0.75rem;
  }}
  .lp-section-title {{
    font-size: 1.7rem;
    margin-bottom: 1.2rem;
  }}
  .lp-how-title {{
    font-size: 1.8rem !important;
  }}
  .lp-founder-title {{
    font-size: 1.6rem;
  }}
  .lp-steps {{
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
  }}
  .lp-step-divider {{
    width: 1px;
    height: 24px;
    margin: 0;
  }}
  .lp-feature-grid {{
    grid-template-columns: 1fr;
    gap: 1.5rem;
  }}
  .lp-plans {{
    flex-direction: column;
    align-items: center;
    gap: 2rem;
  }}
  .lp-trust-grid {{
    grid-template-columns: 1fr;
    gap: 1rem;
  }}
  .lp-faq-q {{
    font-size: 0.95rem;
  }}
  .lp-stats-row {{
    flex-direction: column;
    gap: 1.5rem;
  }}
  .lp-stat-num {{
    font-size: 1.8rem;
  }}
  .lp-compare-table {{
    border: none;
    border-radius: 0;
  }}
  .lp-compare-header,
  .lp-compare-row {{
    grid-template-columns: 1.2fr 1fr 1fr;
  }}
  .lp-compare-cell {{
    padding: 0.55rem 0.4rem;
    font-size: 0.75rem;
  }}
  .lp-final-headline {{
    font-size: 1.4rem;
  }}
  .lp-final-sub {{
    font-size: 0.92rem;
  }}
}}

/* ── Mobile column stacking ── */
@media (max-width: 768px) {{
  .stCheckbox {{
    min-width: auto !important;
  }}
  [data-testid="stHorizontalBlock"] {{
    flex-wrap: wrap !important;
    gap: 0.5rem !important;
  }}
  [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
    min-width: 0 !important;
    flex: 1 1 100% !important;
    max-width: 100% !important;
  }}
  .stExpander [data-testid="stText"],
  .stExpander p {{
    word-break: break-word;
    overflow-wrap: break-word;
  }}
  .stMarkdown p,
  .stMarkdown span {{
    word-break: break-word;
    overflow-wrap: break-word;
  }}
  .stDivider {{
    margin-top: 0.5rem !important;
    margin-bottom: 0.5rem !important;
  }}
}}

/* ── Dispute toggle row: keep checkbox inline on mobile ── */
@media (max-width: 768px) {{
  [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] .stCheckbox) {{
    flex-wrap: nowrap !important;
    gap: 0.25rem !important;
    align-items: flex-start !important;
  }}
  [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] .stCheckbox) > [data-testid="column"]:first-child {{
    min-width: 36px !important;
    max-width: 36px !important;
    flex: 0 0 36px !important;
  }}
  [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] .stCheckbox) > [data-testid="column"]:last-child {{
    min-width: 0 !important;
    flex: 1 1 0% !important;
    max-width: calc(100% - 40px) !important;
  }}
}}
@media (max-width: 480px) {{
  [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] .stCheckbox) > [data-testid="column"]:first-child {{
    min-width: 32px !important;
    max-width: 32px !important;
    flex: 0 0 32px !important;
  }}
  .lab-banner {{
    padding: 8px !important;
  }}
  .lab-banner-title {{
    font-size: 0.9rem !important;
  }}
  .lab-banner-body {{
    font-size: 0.85rem !important;
  }}
}}

/* ── Mobile: prevent card text overflow ── */
@media (max-width: 480px) {{
  .card-viewport, [data-testid="stMainBlockContainer"] {{
    overflow-x: hidden !important;
    max-width: 100vw !important;
  }}
}}

/* ── Sidebar toggle always visible ── */
[data-testid="collapsedControl"] {{
  display: flex !important;
  position: fixed !important;
  top: 0.5rem !important;
  left: 0.5rem !important;
  z-index: 1000 !important;
}}
[data-testid="collapsedControl"] button {{
  background: {BG_2} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 8px !important;
  color: {GOLD} !important;
  width: 36px !important;
  height: 36px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
}}
[data-testid="collapsedControl"] button svg {{
  fill: {GOLD} !important;
  stroke: {GOLD} !important;
}}

/* ── Mobile: sidebar overlay instead of pushing content ── */
@media (max-width: 768px) {{
  [data-testid="stSidebar"][aria-expanded="true"] {{
    position: fixed !important;
    z-index: 999 !important;
    height: 100vh !important;
    box-shadow: 4px 0 20px rgba(0,0,0,0.3);
    min-width: 280px !important;
  }}
  .stApp {{
    width: 100vw !important;
    max-width: 100vw !important;
    overflow-x: hidden !important;
  }}
  [data-testid="stAppViewContainer"] {{
    width: 100% !important;
    max-width: 100vw !important;
    overflow-x: hidden !important;
  }}
  [data-testid="stMain"] {{
    width: 100% !important;
    max-width: 100% !important;
    overflow-x: hidden !important;
  }}
  .auth-container {{
    width: 100% !important;
    max-width: 100% !important;
    padding: 0.25rem 0.5rem !important;
    box-sizing: border-box !important;
  }}
  .auth-card {{
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
  }}
  .auth-card input,
  .auth-card [data-testid="stTextInput"],
  .auth-card [data-baseweb="input"] {{
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
  }}
}}

/* ── File uploader light theme fix ── */
[data-testid="stFileUploader"] {{
  width: 100% !important;
}}

[data-testid="stFileUploader"] section {{
  background: {BG_1} !important;
  border: 2px dashed {BORDER} !important;
  border-radius: 12px !important;
  padding: 1.5rem !important;
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  text-align: center !important;
}}

[data-testid="stFileUploader"] section:hover {{
  border-color: {GOLD} !important;
  background: {BG_2} !important;
}}

[data-testid="stFileUploader"] section > div {{
  color: {TEXT_0} !important;
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  text-align: center !important;
  width: 100% !important;
  position: relative !important;
}}

[data-testid="stFileUploader"] section > div > button,
[data-testid="stFileUploader"] section > div > [data-testid="stBaseButton-secondary"] {{
  position: relative !important;
  z-index: 2 !important;
  margin-top: 0.75rem !important;
  margin-bottom: 0.5rem !important;
}}

[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {{
  width: 100% !important;
  max-width: 500px !important;
  margin: 0 auto 0.5rem auto !important;
  display: flex !important;
  align-items: center !important;
  position: relative !important;
  z-index: 3 !important;
  background: {BG_0} !important;
  border: 1px solid {BORDER} !important;
  padding: 0.75rem 1rem !important;
  border-radius: 8px !important;
}}

[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] *,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] span,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] div,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] p,
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] a {{
  color: {TEXT_0} !important;
  font-weight: 600 !important;
  font-size: 0.95rem !important;
  opacity: 1 !important;
}}

[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] small {{
  color: {TEXT_1} !important;
  font-weight: 500 !important;
  font-size: 0.85rem !important;
  opacity: 1 !important;
}}

[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] svg {{
  color: {GOLD} !important;
  fill: {GOLD} !important;
  opacity: 1 !important;
}}

[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] button {{
  color: {TEXT_0} !important;
}}

[data-testid="stFileUploadDropzone"] {{
  position: relative !important;
  z-index: 1 !important;
  margin-top: 0.5rem !important;
  max-width: 500px !important;
  margin-left: auto !important;
  margin-right: auto !important;
  background: {BG_0} !important;
  border: 2px dashed #999 !important;
  border-radius: 12px !important;
  padding: 1.5rem 1rem !important;
  color: {TEXT_0} !important;
  -webkit-text-fill-color: {TEXT_0} !important;
  opacity: 1 !important;
}}

[data-testid="stFileUploadDropzone"] * {{
  color: {TEXT_0} !important;
  opacity: 1 !important;
  -webkit-text-fill-color: {TEXT_0} !important;
}}

[data-testid="stFileUploadDropzone"] div,
[data-testid="stFileUploadDropzone"] span,
[data-testid="stFileUploadDropzone"] p {{
  color: {TEXT_0} !important;
  opacity: 1 !important;
  -webkit-text-fill-color: {TEXT_0} !important;
  font-weight: 500 !important;
}}

[data-testid="stFileUploadDropzone"] small {{
  color: {TEXT_1} !important;
  opacity: 1 !important;
  -webkit-text-fill-color: {TEXT_1} !important;
}}

[data-testid="stFileUploader"] > section {{
  display: flex !important;
  flex-direction: column-reverse !important;
}}

[data-testid="stFileUploader"] section small {{
  color: {TEXT_1} !important;
}}

[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] section span,
[data-testid="stFileUploader"] section div,
[data-testid="stFileUploader"] section p,
[data-testid="stFileUploader"] section small,
[data-testid="stFileUploader"] section * {{
  color: {TEXT_0} !important;
}}

[data-testid="stFileUploader"] section button,
[data-testid="stFileUploader"] section [data-testid="stBaseButton-secondary"] {{
  background: {BG_0} !important;
  color: {TEXT_0} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 8px !important;
  padding: 0.5rem 1.25rem !important;
  font-weight: 600 !important;
  cursor: pointer !important;
}}

[data-testid="stFileUploader"] section button:hover,
[data-testid="stFileUploader"] section [data-testid="stBaseButton-secondary"]:hover {{
  border-color: {GOLD} !important;
  color: {GOLD} !important;
}}

[data-testid="stFileUploader"] label {{
  color: {TEXT_0} !important;
  font-weight: 600 !important;
}}

/* ── Streamlit component mobile overrides ── */
@media (max-width: 768px) {{
  [data-testid="stFileUploader"] {{
    width: 100% !important;
  }}
  [data-testid="stFileUploader"] section {{
    padding: 1rem !important;
  }}
  [data-testid="stFileUploader"] section > div {{
    flex-direction: column !important;
    gap: 0.5rem;
  }}
  .stExpander {{
    border-radius: 8px !important;
  }}
  .stExpander summary {{
    font-size: 0.9rem !important;
    padding: 0.75rem !important;
  }}
  [data-testid="stMetric"] {{
    padding: 0.5rem !important;
  }}
  [data-testid="stMetric"] [data-testid="stMetricValue"] {{
    font-size: 1.2rem !important;
  }}
  [data-testid="stMetric"] [data-testid="stMetricLabel"] {{
    font-size: 0.75rem !important;
  }}
  .stTabs [data-baseweb="tab-list"] {{
    gap: 0 !important;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }}
  .stTabs [data-baseweb="tab"] {{
    font-size: 0.8rem !important;
    padding: 0.5rem 0.75rem !important;
    white-space: nowrap;
  }}
  .stDownloadButton > button {{
    width: 100% !important;
    min-height: 44px !important;
  }}
  .stCheckbox label {{
    font-size: 0.85rem !important;
  }}
  .stRadio label {{
    font-size: 0.85rem !important;
  }}
  .stSelectbox label {{
    font-size: 0.85rem !important;
  }}
}}
[data-testid="stForm"] {{
  background: transparent !important;
  border: 1px solid #E0E0E0 !important;
  border-radius: 12px !important;
  padding: 1rem !important;
}}

.gc-header {{
  text-align: center;
  padding: 1.5rem 1rem 0.5rem;
}}
.gc-title {{
  font-size: 2.2rem;
  font-weight: 900;
  color: {TEXT_0};
  line-height: 1.1;
  letter-spacing: -0.03em;
  margin-bottom: 0.6rem;
}}
.gc-title .gc-accent {{
  color: {GOLD};
}}
.gc-chips {{
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}}
.gc-chip {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 0.82rem;
  font-weight: 700;
  background: {BG_1};
  color: {TEXT_0};
  border: 1px solid {BORDER};
}}
.gc-chip.gc-chip-major {{
  background: rgba(212,160,23,0.10);
  border-color: rgba(212,160,23,0.35);
  color: {GOLD_DIM};
}}
.gc-chip.gc-chip-score {{
  background: rgba(239,83,80,0.08);
  border-color: rgba(239,83,80,0.30);
  color: #D32F2F;
}}
.gc-chip.gc-chip-dup {{
  background: rgba(66,165,245,0.08);
  border-color: rgba(66,165,245,0.30);
  color: #1565C0;
}}

.gc-card {{
  background: {BG_0};
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 16px 18px;
  margin: 10px 0;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  transition: box-shadow 0.2s ease;
}}
.gc-card:hover {{
  box-shadow: 0 2px 10px rgba(0,0,0,0.08);
}}
.gc-card-top {{
  display: flex;
  align-items: center;
  gap: 10px;
}}
.gc-card-icon {{
  font-size: 1.6rem;
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: {BG_1};
}}
.gc-card-info {{
  flex: 1;
  min-width: 0;
}}
.gc-card-name {{
  font-size: 1rem;
  font-weight: 800;
  color: {TEXT_0};
  line-height: 1.2;
}}
.gc-card-why {{
  font-size: 0.82rem;
  color: {TEXT_1};
  margin-top: 2px;
  line-height: 1.3;
}}
.gc-card-right {{
  text-align: right;
  flex-shrink: 0;
}}
.gc-card-count {{
  font-size: 1.4rem;
  font-weight: 900;
  color: {TEXT_0};
  line-height: 1;
}}
.gc-card-count-label {{
  font-size: 0.7rem;
  color: {TEXT_1};
  text-transform: uppercase;
  letter-spacing: 0.04em;
}}
.gc-card-expand {{
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid {BORDER};
}}
.gc-acct-list {{
  list-style: none;
  padding: 0;
  margin: 0;
}}
.gc-acct-list li {{
  font-size: 0.84rem;
  color: {TEXT_0};
  padding: 4px 0;
  border-bottom: 1px solid rgba(0,0,0,0.04);
  display: flex;
  align-items: center;
  gap: 6px;
}}
.gc-acct-list li:last-child {{
  border-bottom: none;
}}
.gc-acct-dot {{
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: {GOLD};
  flex-shrink: 0;
}}
.gc-acct-bureau {{
  font-size: 0.72rem;
  color: {TEXT_1};
  margin-left: auto;
}}
.gc-more {{
  font-size: 0.78rem;
  color: {GOLD};
  font-weight: 700;
  padding: 4px 0;
  cursor: default;
}}

.gc-sticky-cta {{
  position: sticky;
  bottom: 0;
  background: {BG_0};
  border-top: 1px solid {BORDER};
  padding: 14px 16px 18px;
  margin: 16px -16px -16px;
  border-radius: 0 0 12px 12px;
  z-index: 10;
  text-align: center;
  box-shadow: 0 -2px 8px rgba(0,0,0,0.06);
}}
.gc-cta-sub {{
  font-size: 0.82rem;
  color: {TEXT_1};
  margin-bottom: 6px;
  line-height: 1.4;
}}
.gc-cta-selected {{
  font-size: 0.78rem;
  color: {TEXT_0};
  font-weight: 600;
  margin-bottom: 10px;
}}

@media (max-width: 768px) {{
  .gc-title {{
    font-size: 1.7rem;
  }}
  .gc-chips {{
    gap: 5px;
  }}
  .gc-chip {{
    font-size: 0.76rem;
    padding: 4px 9px;
  }}
  .gc-card {{
    padding: 14px 14px;
  }}
  .gc-card-icon {{
    width: 36px;
    height: 36px;
    font-size: 1.3rem;
  }}
  .gc-card-name {{
    font-size: 0.92rem;
  }}
}}

@keyframes ccpGlow {{
  0%, 100% {{ box-shadow: 0 0 8px rgba(212,160,23,0.15); }}
  50% {{ box-shadow: 0 0 20px rgba(212,160,23,0.30); }}
}}
@keyframes btBarPulse {{
  0%, 100% {{ opacity: 1; }}
  50% {{ opacity: 0.7; }}
}}
@keyframes btSlideIn {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.ccp-wrap {{
  margin: 1.5rem 0;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(212,160,23,0.04) 0%, rgba(212,160,23,0.01) 100%);
  border: 1px solid rgba(212,160,23,0.18);
  padding: 20px;
  animation: btSlideIn 0.4s ease-out;
}}
.ccp-header {{
  text-align: center;
  margin-bottom: 1.2rem;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(212,160,23,0.12);
}}
.ccp-badge {{
  display: inline-block;
  font-size: 0.62rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  padding: 3px 10px;
  border-radius: 4px;
  background: linear-gradient(135deg, {GOLD}, {GOLD_DIM});
  color: #1a1a1a;
  margin-bottom: 8px;
}}
.ccp-title {{
  font-size: 1.5rem;
  font-weight: 900;
  color: {TEXT_0};
  letter-spacing: -0.03em;
  margin-bottom: 6px;
  line-height: 1.2;
}}
.ccp-subtitle {{
  font-size: 0.85rem;
  color: {TEXT_1};
  margin-bottom: 0.8rem;
  line-height: 1.4;
}}
.ccp-chips {{
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}}
.ccp-chip {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 0.76rem;
  font-weight: 700;
  border: 1px solid {BORDER};
  background: {BG_1};
  color: {TEXT_0};
}}
.ccp-chip-high {{
  background: rgba(212,160,23,0.12);
  border-color: rgba(212,160,23,0.40);
  color: {GOLD_DIM};
}}
.ccp-chip-score {{
  background: rgba(239,83,80,0.10);
  border-color: rgba(239,83,80,0.35);
  color: #D32F2F;
}}
.ccp-chip-qw {{
  background: rgba(102,187,106,0.10);
  border-color: rgba(102,187,106,0.35);
  color: #2E7D32;
}}

.ccp-day {{
  margin: 10px 0;
  border: 1px solid {BORDER};
  border-radius: 14px;
  overflow: hidden;
  background: {BG_0};
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}}
.ccp-day-active {{
  border-color: rgba(212,160,23,0.45);
  animation: ccpGlow 3s ease-in-out infinite;
}}
.ccp-day-label {{
  font-size: 0.9rem;
  font-weight: 800;
  color: {TEXT_0};
  padding: 12px 18px;
  background: {BG_1};
  border-bottom: 1px solid {BORDER};
  display: flex;
  align-items: center;
  gap: 8px;
}}
.ccp-day-active .ccp-day-label {{
  background: linear-gradient(135deg, rgba(212,160,23,0.10) 0%, rgba(212,160,23,0.04) 100%);
  color: {GOLD_DIM};
}}
.ccp-day-num {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: {BORDER};
  color: {TEXT_0};
  font-size: 0.72rem;
  font-weight: 800;
  flex-shrink: 0;
}}
.ccp-day-active .ccp-day-num {{
  background: linear-gradient(135deg, {GOLD}, {GOLD_DIM});
  color: #1a1a1a;
}}

.ccp-action {{
  padding: 14px 18px;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  transition: background 0.15s ease;
}}
.ccp-action:hover {{
  background: rgba(212,160,23,0.03);
}}
.ccp-action:last-child {{
  border-bottom: none;
}}
.ccp-action-title {{
  font-size: 0.95rem;
  font-weight: 800;
  color: {TEXT_0};
  margin-bottom: 6px;
}}
.ccp-action-why {{
  font-size: 0.82rem;
  color: {TEXT_1};
  line-height: 1.5;
  margin-bottom: 4px;
}}
.ccp-action-do {{
  font-size: 0.82rem;
  color: {GOLD_DIM};
  line-height: 1.5;
  font-weight: 600;
}}
.ccp-script-detail {{
  margin-top: 8px;
}}
.ccp-script-toggle {{
  font-size: 0.78rem;
  font-weight: 700;
  color: {GOLD};
  cursor: pointer;
  list-style: none;
  padding: 4px 0;
}}
.ccp-script-toggle::-webkit-details-marker {{
  display: none;
}}
.ccp-script-toggle::before {{
  content: "\\25B6\\FE0E ";
  font-size: 0.65rem;
}}
details[open] > .ccp-script-toggle::before {{
  content: "\\25BC\\FE0E ";
}}
.ccp-script-content {{
  font-size: 0.8rem;
  color: {TEXT_0};
  background: {BG_1};
  border-radius: 10px;
  padding: 12px 14px;
  margin-top: 6px;
  line-height: 1.6;
  font-style: italic;
  border-left: 3px solid {GOLD};
}}
.ccp-warning {{
  font-size: 0.76rem;
  color: #EF5350;
  margin-top: 6px;
  line-height: 1.4;
  padding: 4px 8px;
  background: rgba(239,83,80,0.06);
  border-radius: 6px;
}}

.bt-wrap {{
  margin: 1.5rem 0;
  animation: btSlideIn 0.4s ease-out;
}}
.bt-header {{
  text-align: center;
  margin-bottom: 1.2rem;
}}
.bt-badge {{
  display: inline-block;
  font-size: 0.62rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  padding: 3px 10px;
  border-radius: 4px;
  background: linear-gradient(135deg, {GOLD}, {GOLD_DIM});
  color: #1a1a1a;
  margin-bottom: 8px;
}}
.bt-title {{
  font-size: 1.5rem;
  font-weight: 900;
  color: {TEXT_0};
  letter-spacing: -0.03em;
  margin-bottom: 6px;
  line-height: 1.2;
}}
.bt-subtitle {{
  font-size: 0.85rem;
  color: {TEXT_1};
  line-height: 1.4;
}}

.bt-card {{
  background: {BG_0};
  border: 1px solid {BORDER};
  border-radius: 14px;
  padding: 18px 20px;
  margin: 12px 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  animation: btSlideIn 0.3s ease-out;
}}
.bt-card:hover {{
  border-color: rgba(212,160,23,0.30);
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}}
.bt-card-top {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}}
.bt-bureau-icon {{
  font-size: 1.5rem;
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(212,160,23,0.10) 0%, rgba(212,160,23,0.04) 100%);
  border: 1px solid rgba(212,160,23,0.15);
  flex-shrink: 0;
}}
.bt-bureau-info {{
  flex: 1;
  min-width: 0;
}}
.bt-bureau-name {{
  font-size: 1.05rem;
  font-weight: 800;
  color: {TEXT_0};
}}
.bt-bureau-date {{
  font-size: 0.78rem;
  color: {TEXT_1};
  margin-top: 1px;
}}
.bt-status-pill {{
  font-size: 0.72rem;
  font-weight: 700;
  padding: 5px 12px;
  border-radius: 14px;
  white-space: nowrap;
  flex-shrink: 0;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}}

.bt-countdown {{
  margin: 8px 0 12px;
}}
.bt-countdown-labels {{
  display: flex;
  justify-content: space-between;
  font-size: 0.74rem;
  color: {TEXT_1};
  margin-bottom: 4px;
  font-weight: 600;
}}
.bt-bar {{
  width: 100%;
  height: 10px;
  background: {BG_2};
  border-radius: 5px;
  overflow: hidden;
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.08);
}}
.bt-bar-fill {{
  height: 100%;
  border-radius: 5px;
  transition: width 0.8s cubic-bezier(0.25,0.46,0.45,0.94);
  background-size: 20px 20px;
  background-image: linear-gradient(
    45deg,
    rgba(255,255,255,0.08) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255,255,255,0.08) 50%,
    rgba(255,255,255,0.08) 75%,
    transparent 75%
  );
}}
.bt-bar-fill-active {{
  animation: btBarPulse 2s ease-in-out infinite;
}}

.bt-meta {{
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 4px;
}}
.bt-meta-item {{
  font-size: 0.8rem;
  color: {TEXT_1};
  font-weight: 500;
}}

.bt-escalation {{
  margin-top: 12px;
  padding: 14px 16px;
  background: linear-gradient(135deg, rgba(239,83,80,0.06) 0%, rgba(239,83,80,0.02) 100%);
  border: 1px solid rgba(239,83,80,0.25);
  border-radius: 12px;
}}
.bt-escalation-title {{
  font-size: 0.88rem;
  font-weight: 800;
  color: #EF5350;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}}
.bt-escalation-actions {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}}
.bt-esc-btn {{
  font-size: 0.76rem;
  font-weight: 700;
  padding: 6px 14px;
  border-radius: 8px;
  background: {BG_0};
  border: 1px solid rgba(239,83,80,0.25);
  color: {TEXT_0};
  cursor: pointer;
  transition: all 0.15s ease;
}}
.bt-esc-btn:hover {{
  border-color: #EF5350;
  color: #EF5350;
  background: rgba(239,83,80,0.06);
}}

@media (max-width: 768px) {{
  .ccp-wrap {{
    padding: 14px;
  }}
  .ccp-title, .bt-title {{
    font-size: 1.25rem;
  }}
  .ccp-action {{
    padding: 12px 14px;
  }}
  .ccp-action-title {{
    font-size: 0.88rem;
  }}
  .bt-card {{
    padding: 14px 16px;
  }}
  .bt-bureau-icon {{
    width: 36px;
    height: 36px;
    font-size: 1.2rem;
  }}
  .bt-escalation-actions {{
    flex-direction: column;
  }}
}}

/* ── Workspace Shell ── */
.ws-shell {{
  position: relative;
  padding-bottom: 72px;
}}
.ws-header {{
  background: linear-gradient(180deg, {BG_0} 0%, {BG_1} 100%);
  border-bottom: 1px solid {BORDER};
  padding: 16px 0 14px;
  margin-bottom: 12px;
}}
.ws-round-title {{
  font-size: 1.4rem;
  font-weight: 900;
  color: {TEXT_0};
  letter-spacing: -0.03em;
  text-align: center;
  margin-bottom: 2px;
}}
.ws-round-sub {{
  font-size: 0.82rem;
  color: {TEXT_1};
  text-align: center;
  margin-bottom: 14px;
}}
.ws-pills {{
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}}
.ws-pill {{
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 5px 12px;
  border-radius: 20px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}}
.ws-pill-ok {{
  background: rgba(102,187,106,0.15);
  color: #66BB6A;
  border: 1px solid rgba(102,187,106,0.30);
}}
.ws-pill-warn {{
  background: rgba(255,215,120,0.12);
  color: {GOLD};
  border: 1px solid rgba(255,215,120,0.30);
}}
.ws-pill-alert {{
  background: rgba(239,83,80,0.12);
  color: #EF5350;
  border: 1px solid rgba(239,83,80,0.30);
}}
.ws-pill-neutral {{
  background: rgba(255,255,255,0.05);
  color: {TEXT_1};
  border: 1px solid rgba(255,255,255,0.10);
}}
.ws-next-action {{
  background: linear-gradient(135deg, rgba(212,160,23,0.08) 0%, rgba(212,160,23,0.02) 100%);
  border: 2px solid rgba(212,160,23,0.35);
  border-radius: 14px;
  padding: 16px 18px;
  text-align: center;
}}
.ws-next-label {{
  font-size: 0.68rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: {GOLD_DIM};
  margin-bottom: 6px;
}}
.ws-next-title {{
  font-size: 1.05rem;
  font-weight: 800;
  color: {TEXT_0};
  margin-bottom: 4px;
}}
.ws-next-desc {{
  font-size: 0.82rem;
  color: {TEXT_1};
  line-height: 1.4;
}}

/* ── Golden Liquid Glass Card System ── */
.glass-card {{
  background: linear-gradient(
    145deg,
    rgba(255, 215, 120, 0.08),
    rgba(255, 190, 80, 0.04)
  );
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 215, 140, 0.18);
  border-radius: 14px;
  box-shadow:
    0 4px 20px rgba(212, 160, 23, 0.08),
    inset 0 1px 1px rgba(255, 240, 200, 0.06);
  padding: 12px 14px;
  margin-bottom: 6px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}}
.glass-card:hover {{
  border-color: rgba(255, 215, 140, 0.28);
  box-shadow:
    0 6px 24px rgba(212, 160, 23, 0.12),
    inset 0 1px 1px rgba(255, 240, 200, 0.08);
}}
.glass-header {{
  background: linear-gradient(
    145deg,
    rgba(255, 215, 120, 0.12),
    rgba(255, 190, 80, 0.05)
  );
  border-color: rgba(255, 215, 140, 0.22);
  padding: 12px 16px 10px;
}}
.glass-section-title {{
  font-size: 0.92rem;
  font-weight: 800;
  color: {TEXT_0};
  margin-bottom: 2px;
}}

/* ── 2x2 Grid ── */
.glass-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 6px;
}}
.glass-grid-card {{
  background: linear-gradient(
    145deg,
    rgba(255, 215, 120, 0.07),
    rgba(255, 190, 80, 0.02)
  );
  border: 1px solid rgba(255, 215, 140, 0.14);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 12px;
  padding: 10px 8px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 2px 12px rgba(212,160,23,0.05);
}}
.glass-grid-card:hover {{
  border-color: rgba(212,160,23,0.32);
  box-shadow: 0 4px 18px rgba(212,160,23,0.12);
}}
.glass-grid-card:active {{
  border-color: {GOLD};
  box-shadow: 0 2px 12px rgba(212,160,23,0.20);
}}
.glass-grid-icon {{
  font-size: 1.2rem;
  margin-bottom: 4px;
  line-height: 1;
}}
.glass-grid-label {{
  font-size: 0.8rem;
  font-weight: 800;
  color: {TEXT_0};
  margin-bottom: 2px;
}}
.glass-grid-summary {{
  font-size: 0.68rem;
  color: {TEXT_1};
  font-weight: 500;
}}

.glass-back-btn {{
  font-size: 0.8rem;
  color: {TEXT_1};
  padding: 4px 0;
  margin-bottom: 4px;
  border: none;
  background: transparent;
}}
.ws-compact-label {{
  font-size: 0.72rem;
  font-weight: 600;
  color: {TEXT_1};
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 2px;
}}

/* ── Progress bar ── */
.ws-progress {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}}
.ws-progress-bar {{
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
  overflow: hidden;
}}
.ws-progress-fill {{
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, {GOLD}, {GOLD_DIM});
  transition: width 0.4s ease;
}}
.ws-progress-label {{
  font-size: 0.75rem;
  font-weight: 700;
  color: {TEXT_1};
  white-space: nowrap;
}}

@media (max-width: 768px) {{
  .ws-pills {{
    gap: 5px;
  }}
  .ws-pill {{
    font-size: 0.64rem;
    padding: 4px 9px;
  }}
  .glass-card {{
    padding: 10px 12px;
    border-radius: 14px;
  }}
  .glass-grid {{
    gap: 6px;
  }}
  .glass-grid-card {{
    padding: 10px 8px;
  }}
  .glass-grid-icon {{
    font-size: 1.2rem;
  }}
  .glass-grid-label {{
    font-size: 0.76rem;
  }}
}}

@media print {{
  html, body, .stApp {{
    background: #fff !important;
    color: #000 !important;
  }}
  [data-testid="stSidebar"],
  [data-testid="collapsedControl"],
  .stButton, .workflow-header, .card-progress-dots,
  #cc-banner {{
    display: none !important;
  }}
  .card-viewport, .glass-card, div[data-testid="stVerticalBlock"] {{
    background: #fff !important;
    color: #000 !important;
    border: none !important;
    box-shadow: none !important;
  }}
  h1, h2, h3, p, li, span, td, th {{
    color: #000 !important;
  }}
  a {{
    color: #1a0dab !important;
    text-decoration: underline !important;
  }}
}}
</style>
"""


_COMBINED_CSS = LAB_NOCACHE_META + LAB_VIEWPORT_META + LAB_THEME_CSS

def inject_css():
    st.markdown(_COMBINED_CSS, unsafe_allow_html=True)
    import base64, os
    import streamlit.components.v1 as _meta_comp
    favicon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "favicon.png")
    _fav_snippet = ""
    if os.path.exists(favicon_path):
        with open(favicon_path, "rb") as f:
            fav_b64 = base64.b64encode(f.read()).decode()
        _fav_snippet = f'''
        var link = doc.querySelector('link[rel="icon"]');
        if (!link) {{ link = doc.createElement('link'); link.rel = 'icon'; doc.head.appendChild(link); }}
        link.type = 'image/png';
        link.href = 'data:image/png;base64,{fav_b64}';'''
    _meta_comp.html(f'''<script>
    (function(){{
      try {{
        var doc = window.parent.document;
        var m = doc.querySelector('meta[name="viewport"]');
        var vc = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no';
        if (m) {{ m.setAttribute('content', vc); }}
        else {{
          m = doc.createElement('meta');
          m.name = 'viewport';
          m.content = vc;
          doc.head.appendChild(m);
        }}
        {_fav_snippet}
      }} catch(e) {{}}
    }})();
    </script>''', height=0, width=0)
