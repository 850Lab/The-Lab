import streamlit as st
import streamlit.components.v1 as components
from ui.css import BG_1, BG_2, GOLD, GOLD_DIM, BORDER, TEXT_0, TEXT_1

SIGNATURE_PAD_HTML = f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_1};
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 12px;
    overflow: hidden;
  }}
  .sig-label {{
    color: {TEXT_1};
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
    text-align: center;
  }}
  .sig-canvas-wrap {{
    position: relative;
    width: 100%;
    max-width: 460px;
    border: 2px solid {BORDER};
    border-radius: 12px;
    overflow: hidden;
    background: {BG_2};
    touch-action: none;
  }}
  .sig-canvas-wrap.active {{
    border-color: {GOLD};
    box-shadow: 0 0 12px rgba(212,160,23,0.2);
  }}
  canvas {{
    display: block;
    width: 100%;
    cursor: crosshair;
    touch-action: none;
  }}
  .sig-placeholder {{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: {TEXT_1};
    opacity: 0.4;
    font-size: 0.85rem;
    pointer-events: none;
    text-align: center;
    transition: opacity 0.2s;
  }}
  .sig-placeholder.hidden {{ opacity: 0; }}
  .sig-line {{
    position: absolute;
    bottom: 30px;
    left: 10%;
    width: 80%;
    height: 1px;
    background: {BORDER};
    pointer-events: none;
  }}
  .sig-controls {{
    display: flex;
    gap: 10px;
    margin-top: 10px;
    width: 100%;
    max-width: 460px;
    justify-content: center;
  }}
  .sig-btn {{
    padding: 8px 20px;
    border-radius: 10px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid {BORDER};
    background: {BG_2};
    color: {TEXT_0};
    transition: all 0.2s ease;
    letter-spacing: 0.01em;
  }}
  .sig-btn:hover {{
    border-color: {GOLD};
    color: {GOLD};
    background: rgba(212,160,23,0.08);
  }}
  .sig-btn.confirm {{
    background: linear-gradient(90deg, {GOLD}, #f2c94c);
    color: #1a1a1f;
    border-color: {GOLD_DIM};
    font-weight: 700;
  }}
  .sig-btn.confirm:hover {{
    background: linear-gradient(90deg, {GOLD_DIM}, {GOLD});
    box-shadow: 0 4px 16px rgba(212,160,23,0.3);
  }}
  .sig-btn.confirm:disabled {{
    opacity: 0.4;
    cursor: not-allowed;
    box-shadow: none;
  }}
  .sig-status {{
    margin-top: 6px;
    font-size: 0.75rem;
    color: {TEXT_1};
    opacity: 0.6;
    text-align: center;
    height: 16px;
  }}
</style>
</head>
<body>
<div class="sig-label">Draw your signature below</div>
<div class="sig-canvas-wrap" id="canvasWrap">
  <canvas id="sigCanvas" width="920" height="260"></canvas>
  <div class="sig-placeholder" id="placeholder">&#x270D; Sign here with your finger or mouse</div>
  <div class="sig-line"></div>
</div>
<div class="sig-controls">
  <button class="sig-btn" id="clearBtn" type="button">Clear</button>
  <button class="sig-btn confirm" id="confirmBtn" type="button" disabled>Confirm Signature</button>
</div>
<div class="sig-status" id="status"></div>

<script>
(function() {{
  const canvas = document.getElementById('sigCanvas');
  const ctx = canvas.getContext('2d');
  const wrap = document.getElementById('canvasWrap');
  const placeholder = document.getElementById('placeholder');
  const clearBtn = document.getElementById('clearBtn');
  const confirmBtn = document.getElementById('confirmBtn');
  const status = document.getElementById('status');

  let drawing = false;
  let hasDrawn = false;
  let lastX = 0, lastY = 0;

  ctx.strokeStyle = '{GOLD}';
  ctx.lineWidth = 2.5;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.shadowColor = 'rgba(212,160,23,0.3)';
  ctx.shadowBlur = 2;

  function getPos(e) {{
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    let clientX, clientY;
    if (e.touches && e.touches.length > 0) {{
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    }} else {{
      clientX = e.clientX;
      clientY = e.clientY;
    }}
    return {{
      x: (clientX - rect.left) * scaleX,
      y: (clientY - rect.top) * scaleY
    }};
  }}

  function startDraw(e) {{
    e.preventDefault();
    drawing = true;
    const pos = getPos(e);
    lastX = pos.x;
    lastY = pos.y;
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    wrap.classList.add('active');
    placeholder.classList.add('hidden');
  }}

  function draw(e) {{
    if (!drawing) return;
    e.preventDefault();
    const pos = getPos(e);
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
    lastX = pos.x;
    lastY = pos.y;
    hasDrawn = true;
  }}

  function endDraw(e) {{
    if (!drawing) return;
    e.preventDefault();
    drawing = false;
    wrap.classList.remove('active');
    if (hasDrawn) {{
      confirmBtn.disabled = false;
      status.textContent = 'Signature captured — tap Confirm when ready';
    }}
  }}

  canvas.addEventListener('mousedown', startDraw);
  canvas.addEventListener('mousemove', draw);
  canvas.addEventListener('mouseup', endDraw);
  canvas.addEventListener('mouseleave', endDraw);
  canvas.addEventListener('touchstart', startDraw, {{ passive: false }});
  canvas.addEventListener('touchmove', draw, {{ passive: false }});
  canvas.addEventListener('touchend', endDraw, {{ passive: false }});
  canvas.addEventListener('touchcancel', endDraw, {{ passive: false }});

  clearBtn.addEventListener('click', function() {{
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    hasDrawn = false;
    confirmBtn.disabled = true;
    placeholder.classList.remove('hidden');
    status.textContent = '';
  }});

  function findAndSetTextarea(dataURL, attempt) {{
    attempt = attempt || 0;
    try {{
      var docs = [window.parent.document];
      try {{ if (window.top.document !== window.parent.document) docs.push(window.top.document); }} catch(e) {{}}
      for (var di = 0; di < docs.length; di++) {{
        var textareas = docs[di].querySelectorAll('textarea');
        for (var ti = 0; ti < textareas.length; ti++) {{
          var ta = textareas[ti];
          if (ta.getAttribute('aria-label') === 'sig_data_transfer') {{
            var nativeSetter = Object.getOwnPropertyDescriptor(
              window.HTMLTextAreaElement.prototype, 'value'
            ).set;
            nativeSetter.call(ta, dataURL);
            ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            setTimeout(function() {{
              ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}, 100);
            status.textContent = '\u2713 Signature confirmed';
            status.style.color = '{GOLD}';
            status.style.opacity = '1';
            confirmBtn.textContent = '\u2713 Saved';
            confirmBtn.disabled = true;
            return true;
          }}
        }}
      }}
    }} catch(e) {{}}
    if (attempt < 10) {{
      status.textContent = 'Saving... (' + (attempt+1) + '/10)';
      setTimeout(function() {{ findAndSetTextarea(dataURL, attempt+1); }}, 500);
    }} else {{
      status.textContent = 'Could not save — please try again';
      status.style.color = '#EF5350';
    }}
    return false;
  }}

  confirmBtn.addEventListener('click', function() {{
    if (!hasDrawn) return;
    var dataURL = canvas.toDataURL('image/png');
    findAndSetTextarea(dataURL, 0);
  }});
}})();
</script>
</body>
</html>
"""


def render_signature_pad(existing_signature: bytes = None):
    if "user_signature_confirmed" not in st.session_state:
        st.session_state["user_signature_confirmed"] = None
    if "sig_redrawing" not in st.session_state:
        st.session_state["sig_redrawing"] = False

    if st.session_state["user_signature_confirmed"] is None and existing_signature and not st.session_state["sig_redrawing"]:
        import base64 as _sig_b64
        _data_uri = "data:image/png;base64," + _sig_b64.b64encode(existing_signature).decode()
        st.session_state["user_signature_confirmed"] = _data_uri

    existing = st.session_state.get("user_signature_confirmed")
    if existing:
        st.session_state["sig_redrawing"] = False
        st.markdown(
            f'<div style="background:{BG_2};border:1px solid {BORDER};border-radius:12px;'
            f'padding:12px;text-align:center;margin-bottom:12px;">'
            f'<div style="color:{TEXT_1};font-size:0.75rem;font-weight:600;'
            f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">'
            f'Current Signature</div>'
            f'<img src="{existing}" style="max-width:280px;height:auto;'
            f'border-radius:8px;margin-bottom:8px;" />'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("✏️ Redraw Signature", key="redraw_sig"):
            st.session_state["user_signature_confirmed"] = None
            st.session_state["sig_redrawing"] = True
            st.rerun()
        return existing

    components.html(SIGNATURE_PAD_HTML, height=370, scrolling=False)

    sig_transfer = st.text_area(
        "sig_data_transfer",
        value="",
        key="sig_data_transfer_area",
        height=1,
        label_visibility="collapsed",
    )

    st.markdown(
        "<style>"
        "[data-testid='stTextArea']:has(textarea[aria-label='sig_data_transfer']) {"
        "  position: fixed !important;"
        "  left: -9999px !important;"
        "  top: -9999px !important;"
        "  opacity: 0 !important;"
        "  pointer-events: none !important;"
        "}"
        "</style>",
        unsafe_allow_html=True,
    )

    if sig_transfer and sig_transfer.startswith("data:image"):
        st.session_state["user_signature_confirmed"] = sig_transfer
        st.rerun()

    return None
