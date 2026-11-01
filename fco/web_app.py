"""WebView2 desktop shell. All UI assets and user data stay local."""

from pathlib import Path
import re
from fco.paths import APP_ROOT, RESOURCE_ROOT
from . import VERSION
from .controller import DesktopAPI


def create_window(root=APP_ROOT, hidden=False, title=None):
    import webview

    folder = RESOURCE_ROOT / "ui"
    html = (folder / "index.html").read_text(encoding="utf-8")
    html, styles = re.subn(
        r'<link\b[^>]*\bhref="style\.css"[^>]*>',
        lambda _: "<style>" + (folder / "style.css").read_text(encoding="utf-8") + "</style>",
        html,
    )
    html, scripts = re.subn(
        r'<script\s+src="app\.js"\s*>\s*</script>',
        lambda _: "<script>" + (folder / "app.js").read_text(encoding="utf-8") + "</script>",
        html,
    )
    if styles != 1 or scripts != 1:
        raise ValueError("The UI template must reference style.css and app.js exactly once.")
    api = DesktopAPI(root)
    window = webview.create_window(
        title or f"FCO Market {VERSION}",
        html=html,
        js_api=api,
        width=1200,
        height=860,
        min_size=(980, 720),
        hidden=hidden,
        background_color="#141714",
        text_select=True,
    )
    api._window = window
    window.events.closing += api._on_closing
    return window, api


def run(root=APP_ROOT):
    import webview

    create_window(root)
    webview.start(
        gui="edgechromium",
        storage_path=str(Path(root) / "webview"),
        icon=str(RESOURCE_ROOT / "assets/fco.ico"),
    )
