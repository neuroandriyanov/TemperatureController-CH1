"""Photo and wiring reference for the LB02A viewer."""

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk
from lb02a_theme import CARD, TEXT, MUTED, BORDER


WIRES = (
    ("GPIO12", "Белый", "SCL дисплея · ближе к маркировке RCS", "#fffaf0"),
    ("GPIO11", "Белый", "SDA дисплея · ближе к маркировке LED", "#fffaf0"),
    ("GPIO9", "Чёрный", "9341-DC", "#222222"),
    ("GPIO6", "Красный", "1650-SCL · тактирование клавиатуры", "#c52e38"),
    ("GPIO5", "Коричневый", "1650-SDA · сторона контроллера LB02A", "#805237"),
    ("GND", "Фиолетовый", "GND · общий провод в жгуте AI-S3", "#7845a1"),
)


def show_wiring(parent):
    photos = Path(__file__).with_name("lb02aphoto")
    ttk.Label(parent, text="Подключение платы и фотографии", style="Title.TLabel").pack(anchor="w", pady=(2, 12))
    diagram = tk.Canvas(parent, width=670, height=242, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
    diagram.pack(fill="x", pady=(0, 12))
    diagram.create_text(20, 22, text="AI-S3", anchor="w", fill=TEXT, font=("Segoe UI", 11, "bold"))
    diagram.create_text(125, 22, text="Цвет провода", anchor="w", fill=TEXT, font=("Segoe UI", 11, "bold"))
    diagram.create_text(335, 22, text="LB02A", anchor="w", fill=TEXT, font=("Segoe UI", 11, "bold"))
    for row, (pin, name, signal, color) in enumerate(WIRES):
        y = 58 + row * 30
        diagram.create_text(20, y, text=pin, anchor="w", fill="#65e5df", font=("Segoe UI", 10, "bold"))
        diagram.create_text(125, y, text=name, anchor="w", fill=MUTED, font=("Segoe UI", 10))
        diagram.create_line(235, y, 305, y, width=6, fill="#73849b")
        diagram.create_line(235, y, 305, y, width=4, fill=color)
        for x in (235, 305):
            diagram.create_oval(x - 3, y - 3, x + 3, y + 3, fill=color, outline="#64676b")
        diagram.create_text(335, y, text=signal, anchor="w", fill=TEXT, font=("Segoe UI", 10))

    ttk.Label(parent, wraplength=1100, justify="left", style="Muted.TLabel", text=(
        "Коричневый провод GPIO5 припаян к 1650-SDA у разъёма шлейфа. "
        "Синий переключатель в положении ON размыкает SDA между TM1650 (ножка 3) и контроллером LB02A. "
        "Это положение для управления кнопками через ESP32.\n"
        "AI-S3 питается через USB. RCS указан как ориентир рядом с SCL."
    )).pack(anchor="w", pady=(0, 16))

    gallery = ttk.Frame(parent)
    gallery.pack(fill="x", pady=6)

    def preview(title, photo):
        window = tk.Toplevel(parent)
        window.title(title)
        window.transient(parent.winfo_toplevel())
        enlarged = ImageOps.contain(photo, (window.winfo_screenwidth() * 9 // 10,
                                            window.winfo_screenheight() * 8 // 10))
        label = ttk.Label(window)
        label.image = ImageTk.PhotoImage(enlarged, master=window)
        label.config(image=label.image)
        label.pack()
        window.bind("<Escape>", lambda _event: window.destroy())

    for column, (title, filename) in enumerate((
        ("Прибор в сборе", "IMG_20261104_205123.jpg"),
        ("Контакты AI-S3", "IMG_20261104_203353.jpg"),
        ("Проводка внутри", "IMG_20261104_200235.jpg"),
        ("Пайка на LB02A", "IMG_20261104_200203.jpg"),
    )):
        gallery.columnconfigure(column, weight=1)
        try:
            with Image.open(photos / filename) as original:
                photo = ImageOps.exif_transpose(original)
        except OSError:
            ttk.Label(gallery, text=f"{title}\nФото недоступно").grid(row=0, column=column)
            continue
        button = ttk.Button(gallery, text=title, compound="top",
                            command=lambda name=title, picture=photo: preview(name, picture))
        button.image = ImageTk.PhotoImage(ImageOps.contain(photo, (250, 180)), master=parent)
        button.config(image=button.image)
        button.grid(row=0, column=column, padx=6, sticky="nsew")
