from tkinter import ttk

BG = "#0c1422"
PANEL = "#152134"
TEXT = "#ecf3fc"
MUTED = "#93a7c1"
GREEN = "#53ddb0"


def apply(root):
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=("Segoe UI", 10), background=BG, foreground=TEXT)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=PANEL)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Card.TLabel", background=PANEL)
    style.configure("CardMuted.TLabel", background=PANEL, foreground=MUTED)
    style.configure(
        "TButton",
        font=("Segoe UI", 10, "bold"),
        background="#263a56",
        foreground=TEXT,
        borderwidth=0,
        padding=(15, 10),
    )
    style.map(
        "TButton",
        background=[("disabled", "#1c293b"), ("active", "#355370")],
        foreground=[("disabled", "#61738b")],
    )
    style.configure("Primary.TButton", background=GREEN, foreground="#092b22")
    style.map(
        "Primary.TButton",
        background=[("disabled", "#234039"), ("active", "#84edc9")],
        foreground=[("disabled", "#6b9284")],
    )
    style.configure("Danger.TButton", background="#442c3a", foreground="#ffbec7")
    style.map("Danger.TButton", background=[("active", "#633b4b")])
    style.configure(
        "TEntry",
        fieldbackground="#0d1829",
        foreground=TEXT,
        insertcolor=TEXT,
        padding=10,
        bordercolor="#2c405d",
        lightcolor="#2c405d",
        darkcolor="#2c405d",
    )
    style.map("TEntry", bordercolor=[("focus", GREEN)])
    style.configure("TCheckbutton", background=PANEL, foreground=TEXT, padding=7)
    style.map("TCheckbutton", background=[("active", PANEL)])
    style.configure(
        "TNotebook", background=BG, borderwidth=0, bordercolor=BG, lightcolor=BG, darkcolor=BG
    )
    style.configure("TNotebook.Tab", padding=(24, 12), background=BG, foreground=MUTED)
    style.map(
        "TNotebook.Tab",
        background=[("selected", PANEL)],
        foreground=[("selected", GREEN)],
        padding=[("selected", (24, 12)), ("!selected", (24, 12))],
        expand=[("selected", (0, 0, 0, 0))],
        bordercolor=[("selected", PANEL), ("!selected", BG)],
        lightcolor=[("selected", PANEL), ("!selected", BG)],
        darkcolor=[("selected", PANEL), ("!selected", BG)],
    )
