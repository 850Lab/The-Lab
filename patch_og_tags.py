"""Patch Streamlit's index.html with 850 Lab OG meta tags."""
import os

STREAMLIT_INDEX = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".pythonlibs", "lib", "python3.11", "site-packages",
    "streamlit", "static", "index.html"
)

OG_BLOCK = """    <title>850 Lab — Find Credit Report Errors in 60 Seconds</title>

    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website" />
    <meta property="og:url" content="https://850.life/" />
    <meta property="og:title" content="850 Lab — Find Credit Report Errors in 60 Seconds" />
    <meta property="og:description" content="Upload your credit report. Our AI scans every account, flags mistakes, and writes dispute letters with real legal citations. Free to start." />
    <meta property="og:image" content="https://850.life/app/static/og_image.png" />
    <meta property="og:image:width" content="1024" />
    <meta property="og:image:height" content="1024" />

    <!-- Twitter -->
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:url" content="https://850.life/" />
    <meta name="twitter:title" content="850 Lab — Find Credit Report Errors in 60 Seconds" />
    <meta name="twitter:description" content="Upload your credit report. Our AI scans every account, flags mistakes, and writes dispute letters with real legal citations. Free to start." />
    <meta name="twitter:image" content="https://850.life/app/static/og_image.png" />

    <!-- General meta -->
    <meta name="description" content="Upload your credit report. Our AI scans every account, flags mistakes, and writes dispute letters with real legal citations. Free to start." />"""

def patch():
    if not os.path.exists(STREAMLIT_INDEX):
        return
    with open(STREAMLIT_INDEX, "r") as f:
        html = f.read()
    if "og:title" in html:
        return
    html = html.replace("<title>Streamlit</title>", OG_BLOCK)
    with open(STREAMLIT_INDEX, "w") as f:
        f.write(html)

if __name__ == "__main__":
    patch()
