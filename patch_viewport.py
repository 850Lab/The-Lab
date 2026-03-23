import os

def patch():
    try:
        import streamlit
        p = os.path.join(os.path.dirname(streamlit.__file__), 'static', 'index.html')
        if not os.path.exists(p):
            return
        content = open(p).read()
        old = 'content="width=device-width, initial-scale=1, shrink-to-fit=no"'
        new = 'content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, shrink-to-fit=no"'
        if old in content:
            content = content.replace(old, new)
            open(p, 'w').write(content)
    except Exception:
        pass

if __name__ == '__main__':
    patch()
