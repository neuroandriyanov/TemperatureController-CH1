"""Visual theme shared by the LB02A windows; no device or transport logic."""
import tkinter as tk
from tkinter import ttk

BG = "#0c121b"
CARD = "#141e2b"
SCREEN = "#080d14"
TEXT = "#e5edf7"
MUTED = "#97a8bf"
BORDER = "#263448"
ACCENT = "#29b8a8"


def install_theme(root):
    root.configure(background=BG)
    root.option_add("*Toplevel.background", BG)
    root.option_add("*TCombobox*Listbox.background", "#172538")
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", "#245567")
    root.option_add("*TCombobox*Listbox.selectForeground", "#f4f8ff")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10),
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    troughcolor=SCREEN, selectbackground="#245567", selectforeground=TEXT)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD, borderwidth=0, relief="flat")
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"), foreground="#f4f8ff")
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Badge.TLabel", foreground="#65e5df", background="#15353b", padding=(12, 7))
    style.configure("Card.TLabel", background=CARD)
    style.configure("Section.TLabel", background=CARD, foreground="#f0f5fc", font=("Segoe UI", 12, "bold"))
    style.configure("CardMuted.TLabel", background=CARD, foreground=MUTED)
    style.configure("Card.TLabelframe", background=CARD, bordercolor=BORDER, borderwidth=1, relief="solid")
    style.configure("Card.TLabelframe.Label", background=BG, foreground="#f0f5fc", font=("Segoe UI", 11, "bold"))
    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab", background="#172334", foreground=MUTED, padding=(20, 10),
                    borderwidth=0, focuscolor=ACCENT, lightcolor=BORDER, darkcolor=BORDER, bordercolor=BORDER)
    style.map("TNotebook.Tab", background=[("selected", "#213c48"), ("active", "#223147")],
              foreground=[("selected", "#72e0d1"), ("active", TEXT)],
              lightcolor=[("selected", BORDER)], darkcolor=[("selected", BORDER)], bordercolor=[("selected", BORDER)])
    style.configure("TButton", background="#223147", foreground=TEXT, bordercolor="#344862",
                    borderwidth=1, padding=(13, 8), focuscolor="#65e5df", focusthickness=1)
    style.map("TButton", background=[("disabled", "#17202d"), ("pressed", "#172638"), ("active", "#2d425e")],
              foreground=[("disabled", "#718299")], bordercolor=[("active", "#5d7698")])
    style.configure("Primary.TButton", background=ACCENT, foreground="#071e24", bordercolor=ACCENT,
                    font=("Segoe UI", 10, "bold"), padding=(20, 9))
    style.map("Primary.TButton", background=[("disabled", "#284a50"), ("pressed", "#219b90"), ("active", "#54d3c1")],
              foreground=[("disabled", "#779b9d"), ("!disabled", "#071e24")],
              bordercolor=[("!disabled", ACCENT)])
    style.configure("TEntry", fieldbackground="#0e1723", foreground=TEXT, insertcolor=TEXT,
                    bordercolor="#34455e", padding=7)
    style.map("TEntry", fieldbackground=[("readonly", "#0e1723"), ("disabled", "#17202d")],
              foreground=[("readonly", TEXT), ("disabled", MUTED)], bordercolor=[("focus", ACCENT)])
    style.configure("TCombobox", fieldbackground="#0e1723", background="#223147", foreground=TEXT,
                    arrowcolor=MUTED, bordercolor="#34455e", padding=7, arrowsize=14)
    style.map("TCombobox", fieldbackground=[("readonly", "#0e1723"), ("disabled", "#17202d")],
              foreground=[("readonly", TEXT), ("disabled", MUTED)],
              background=[("active", "#2d425e"), ("readonly", "#223147")],
              bordercolor=[("focus", ACCENT)], selectbackground=[("readonly", "#245567")],
              selectforeground=[("readonly", TEXT)])


def instrument_key(parent, text, command):
    return tk.Button(parent, text=text, command=command, state="disabled",
        font=("Segoe UI", 9), background="#223147", foreground=TEXT,
        activebackground="#2d425e", activeforeground="#f4f8ff", disabledforeground="#8393aa",
        relief="flat", borderwidth=0, highlightthickness=1,
        highlightbackground="#344862", highlightcolor=ACCENT,
        width=17, height=3, wraplength=150, padx=5, pady=10, cursor="hand2", takefocus=True)
