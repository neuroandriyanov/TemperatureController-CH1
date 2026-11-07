"""Display the live LB02A screen from the ESP32's binary serial stream."""

import argparse
from contextlib import contextmanager
from pathlib import Path
import queue
import socket
import struct
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk
import serial
from serial.tools.list_ports import comports
from decode_display import replay_frames
from lb02a_control import start_control
from lb02a_reading import read_display, frame_is_fresh
from lb02a_wiring import show_wiring
from lb02a_theme import install_theme, instrument_key, CARD, MUTED, SCREEN


def serial_stream(read, write, stats, stop, *, raw=None, commands=None, wifi_info=None):
    sync = b"LB03"
    keypad_sync = b"LBK2"
    legacy_keypad_sync = b"LBK1"
    wifi_sync = b"LBW1"
    buffer = bytearray()
    previous = None
    snapshot = time.monotonic() + 0.15
    while not stop.is_set():
        if commands is not None:
            try:
                command = commands.get_nowait()
            except queue.Empty:
                pass
            else:
                if stats.get("keypad_mode") == 1 and time.monotonic() - stats["keypad_seen"] < 1.5:
                    write(bytes((0xA0 + command,)))
        incoming = read()
        buffer.extend(incoming)
        while True:
            starts = [offset for marker in (sync, keypad_sync, legacy_keypad_sync, wifi_sync)
                      if (offset := buffer.find(marker)) >= 0]
            if not starts:
                del buffer[:-3]
                break
            start = min(starts)
            if start:
                del buffer[:start]
            if len(buffer) < 10:
                break
            if buffer.startswith(wifi_sync):
                if len(buffer) < 28:
                    break
                if wifi_info:
                    stats["wifi_ap_ready"] = True
                    wifi_info((buffer[4:16].decode("ascii", errors="replace"),
                               buffer[16:28].decode("ascii", errors="replace")))
                del buffer[:28]
                continue
            if buffer.startswith(keypad_sync) or buffer.startswith(legacy_keypad_sync):
                length = 19 if buffer.startswith(keypad_sync) else 10
                if len(buffer) < length:
                    break
                if raw is not None and raw.tell() < 8 * 1024 * 1024:
                    raw.write(buffer[:length])
                mode, code, reads = struct.unpack_from("<BBI", buffer, 4)
                if stats.get("key_reads") != reads:
                    stats["instrument_seen"] = time.monotonic()
                stats.update(keypad_mode=mode, key_code=code, key_reads=reads, keypad_seen=time.monotonic())
                if length == 19:
                    edges, starts, levels = struct.unpack_from("<IIB", buffer, 10)
                    stats.update(key_clock=edges, key_starts=starts, key_levels=levels)
                del buffer[:length]
                continue
            sequence, length = struct.unpack_from("<IH", buffer, 4)
            if not 0 < length <= 514:
                del buffer[0]
                continue
            if len(buffer) < 10 + length:
                break
            if raw is not None and raw.tell() < 8 * 1024 * 1024:
                raw.write(buffer[:10 + length])
            payload = buffer[10:10 + length]
            del buffer[:10 + length]
            stats["packets"] += 1
            if previous is not None and sequence != ((previous + 1) & 0xFFFFFFFF):
                stats["gaps"] += 1
                yield None, 0
            previous = sequence
            index = 0
            while index < len(payload):
                token = payload[index]
                index += 1
                count = (token & 63) + 1
                repeat = bool(token & 64)
                pair = (token & 127) == 63
                size = 3 if pair else 1 if repeat else count
                if index + size > len(payload):
                    stats["gaps"] += 1
                    yield None, 0
                    break
                values = payload[index:index + size]
                index += size
                if pair:
                    values = values[1:] * values[0]
                elif repeat:
                    values *= count
                stats["bytes"] += len(values)
                mode = bool(token & 128)
                for value in values:
                    yield mode, value
        if time.monotonic() >= snapshot:
            yield None
            snapshot = time.monotonic() + 0.15


@contextmanager
def open_link(args):
    if args.host:
        with socket.create_connection((args.host, args.tcp_port), timeout=2) as link:
            link.settimeout(0.05)
            link.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            last_data = time.monotonic()

            def read():
                nonlocal last_data
                try:
                    chunk = link.recv(8192)
                except socket.timeout:
                    if time.monotonic() - last_data >= 3:
                        raise TimeoutError("ESP32 не передаёт данные по Wi-Fi")
                    return b""
                if not chunk:
                    raise ConnectionError("ESP32 закрыл подключение Wi-Fi")
                last_data = time.monotonic()
                return chunk

            yield read, link.sendall
        return

    with serial.Serial() as port:
        port.port = args.port
        port.baudrate = args.baud
        port.timeout = 0.05
        port.write_timeout = 0.1
        port.dtr = port.rts = False
        port.open()
        yield lambda: port.read(min(8192, port.in_waiting or 1)), port.write


def receive(args, stop, publish, commands=None, wifi_info=None):
    stats = {"packets": 0, "bytes": 0, "gaps": 0}
    with open_link(args) as (read, write):
        raw = args.raw.open("wb", buffering=0) if args.raw else None
        try:
            stream = serial_stream(read, write, stats, stop, raw=raw, commands=commands,
                                   wifi_info=wifi_info if not args.host else None)
            # The LB02A leaves unchanged areas of its white screen untouched.
            base = Image.new("RGB", (320, 240), "white")
            for frame, pixels in replay_frames(stream, base=base):
                publish(frame, pixels, stats.copy())
        finally:
            if raw:
                raw.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="serial port of your ESP32 bridge; select in GUI if omitted")
    parser.add_argument("--baud", type=int, default=4_000_000)
    parser.add_argument("--host", help="connect to the ESP32 over Wi-Fi")
    parser.add_argument("--tcp-port", type=int, default=8769)
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--latest", type=Path, help="save the latest live frame once a second")
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--control-port", type=int, help="enable local HTTP control")
    args = parser.parse_args()
    autoconnect = bool(args.port or args.host)
    args.port = args.port or ""
    if args.snapshot and not autoconnect:
        parser.error("--snapshot requires --port or --host")
    stop = threading.Event()
    if args.snapshot:
        until = time.monotonic() + args.seconds

        def save(frame, pixels, stats):
            if time.monotonic() >= until:
                frame.save(args.snapshot)
                print(f"{stats}, pixels={pixels}")
                stop.set()

        receive(args, stop, save)
        return

    root = tk.Tk()
    root.title("LB02A")
    install_theme(root)
    root.geometry(f"{min(1460, root.winfo_screenwidth()-80)}x{min(880, root.winfo_screenheight()-100)}")
    root.minsize(1360, 860)
    header = ttk.Frame(root, padding=(20, 16, 20, 14))
    header.pack(fill="x")
    ttk.Label(header, text="LB02A", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(header, text="Калибратор · экран и управление прибором", style="Muted.TLabel").grid(
        row=1, column=0, sticky="w", pady=(4, 0))
    header.columnconfigure(0, weight=1)
    ttk.Label(header, text="ESP32  ·  USB / Wi-Fi", style="Badge.TLabel").grid(row=0, column=1, rowspan=2)
    tabs = ttk.Notebook(root)
    tabs.pack(fill="both", expand=True, padx=20, pady=(0, 16))
    controls = ttk.Frame(tabs, padding=(0, 12, 0, 0))
    wiring = ttk.Frame(tabs, padding=(0, 12, 0, 0))
    tabs.add(controls, text="Управление")
    tabs.add(wiring, text="Подключение платы")
    show_wiring(wiring)
    connection = ttk.Frame(controls, style="Card.TFrame", padding=(14, 12))
    connection.pack(fill="x", pady=(0, 16))
    connection.columnconfigure(1, weight=1)
    ttk.Label(connection, text="Подключение", style="Section.TLabel").grid(
        row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
    transport = tk.StringVar(value="Wi-Fi" if args.host else "USB")
    port_name = tk.StringVar(value=args.port)
    baud = tk.StringVar(value=str(args.baud))
    host = tk.StringVar(value=args.host or "192.168.4.1")
    tcp_port = tk.StringVar(value=str(args.tcp_port))
    selector = ttk.Combobox(connection, textvariable=transport, values=("USB", "Wi-Fi"),
                            width=7, state="readonly")
    selector.grid(row=1, column=0, padx=(0, 12))
    usb = ttk.Frame(connection, style="Card.TFrame")
    wifi = ttk.Frame(connection, style="Card.TFrame")
    for panel in (usb, wifi):
        panel.grid(row=1, column=1, sticky="w")
    ports = ttk.Combobox(usb, textvariable=port_name, width=11)
    ports.pack(side="left")
    ttk.Button(usb, text="Обновить", command=lambda: scan_ports()).pack(side="left", padx=4)
    ttk.Label(usb, text="Бод", style="CardMuted.TLabel").pack(side="left", padx=(10, 4))
    ttk.Entry(usb, textvariable=baud, width=10).pack(side="left", padx=4)
    ttk.Label(wifi, text="IP", style="CardMuted.TLabel").pack(side="left")
    ttk.Entry(wifi, textvariable=host, width=16).pack(side="left", padx=4)
    ttk.Label(wifi, text="TCP", style="CardMuted.TLabel").pack(side="left", padx=(10, 4))
    ttk.Entry(wifi, textvariable=tcp_port, width=6).pack(side="left", padx=4)
    action = ttk.Button(connection, text="Подключить", style="Primary.TButton", command=lambda: toggle_connection())
    action.grid(row=1, column=2, padx=12)
    credentials = ttk.Button(connection, text="Данные сети ESP32", state="disabled",
                             command=lambda: show_wifi_info())
    credentials.grid(row=1, column=3, padx=4)

    def scan_ports():
        ports.config(values=[port.device for port in sorted(comports())])

    def show_transport(_event=None):
        (usb if transport.get() == "Wi-Fi" else wifi).grid_remove()
        (wifi if transport.get() == "Wi-Fi" else usb).grid()

    selector.bind("<<ComboboxSelected>>", show_transport)
    show_transport()
    scan_ports()
    body = ttk.Frame(controls)
    body.pack(fill="both", expand=True)
    body.columnconfigure(0, weight=1, minsize=672)
    body.columnconfigure(1, weight=1)
    body.rowconfigure(0, weight=1)
    display_card = ttk.Frame(body, style="Card.TFrame", padding=14)
    display_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
    display_title = ttk.Frame(display_card, style="Card.TFrame")
    display_title.pack(fill="x", pady=(0, 12))
    ttk.Label(display_title, text="01  Экран прибора", style="Section.TLabel").pack(side="left")
    ttk.Label(display_title, text="320 × 240  ·  ×2", style="CardMuted.TLabel").pack(side="right")
    screen_host = tk.Frame(display_card, background=SCREEN, width=640, height=480)
    screen_host.pack(fill="both", expand=True)
    screen_host.pack_propagate(False)
    screen = tk.Label(screen_host, text="Ожидание данных дисплея", width=64, height=20,
                      background=SCREEN, foreground=MUTED, borderwidth=0, font=("Segoe UI", 10))
    screen.place(relx=.5, rely=.5, anchor="center")
    status = tk.Label(display_card, text="Выберите подключение", background=CARD, foreground=MUTED,
                      anchor="w", justify="left", wraplength=640, height=2, font=("Segoe UI", 10))
    status.pack(fill="x", pady=(10, 0))
    keypad = ttk.Frame(body, style="Card.TFrame", padding=(12, 14))
    keypad.grid(row=0, column=1, sticky="nsew")
    ttk.Label(keypad, text="02  Клавиатура прибора", style="Section.TLabel").grid(
        row=0, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 10))
    ttk.Label(keypad, text="Сверху — основное действие.\nСнизу — дополнительная функция.",
              style="CardMuted.TLabel").grid(row=1, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 12))
    keypad_status = tk.Label(keypad, text="Клавиатура: ожидание данных", background=CARD, foreground=MUTED,
                             anchor="w", justify="left", wraplength=520, height=3, font=("Segoe UI", 10))
    keypad_status.grid(row=6, column=0, columnspan=4, sticky="ew", padx=4, pady=(14, 0))
    commands = queue.Queue(maxsize=1)
    keys = (
        ("↗ Увеличить", "Цифра 1"), ("↘ Уменьшить", "Цифра 2"),
        ("Шаг вверх", "Цифра 3"), ("Шаг вниз", "Переключить экран"),
        ("Напряжение · V", "Цифра 4"), ("Ток · mA", "Цифра 5"),
        ("Питание петли · 24 V", "Цифра 6"), ("Частота · Hz", "Стереть · Del"),
        ("← Предыдущий тип", "Цифра 7"), ("Термопара / mV", "Цифра 8"),
        ("Термосопротивление / Ω", "Цифра 9"), ("Следующий тип →", "Применить · Enter"),
        ("Питание прибора", "Сменить знак · ±"), ("HART", "Цифра 0"),
        ("Modbus", "Десятичная точка"), ("Доп. экран · F-Fn", ""),
    )
    buttons = []
    next_press = 0.0
    key_requested_at = 0.0
    control_lock = threading.Lock()
    current = (None, {"connected": False})
    last_pixels = 0
    last_pixel_update = 0.0
    reading_gap_baseline = 0
    session = None
    thread = None
    wifi_details = None

    def control_state():
        with control_lock:
            return current

    def send_key(number):
        nonlocal next_press, key_requested_at, reading_gap_baseline
        with control_lock:
            now = time.monotonic()
            if session is None or session.is_set() or current[1].get("keypad_mode") != 1 or now < next_press:
                return False
            try:
                commands.put_nowait(number)
            except queue.Full:
                return False
            next_press = now + 0.35
            key_requested_at = now
            reading_gap_baseline = current[1].get("gaps", 0)
            current[1].update(reading=None)
            return True

    for number, (action_label, entry_label) in enumerate(keys, 1):
        row, column = divmod(number - 1, 4)
        button = instrument_key(keypad, text=f"{action_label}\n{entry_label}",
                                command=lambda key=number: send_key(key))
        button.grid(row=row + 2, column=column, sticky="nsew", padx=4, pady=4)
        keypad.columnconfigure(column, weight=1, uniform="key")
        keypad.rowconfigure(row + 2, weight=1)
        buttons.append(button)
    latest = queue.Queue(maxsize=1)
    last_saved = 0.0

    def publish(frame, pixels, stats):
        nonlocal last_saved, current, last_pixels, last_pixel_update
        now = time.monotonic()
        instrument_seen = stats.pop("instrument_seen", 0) if isinstance(stats, dict) else 0
        if isinstance(stats, dict) and now - stats.pop("keypad_seen", 0) >= 1.5:
            stats["keypad_mode"] = None
        with control_lock:
            if session.is_set():
                return
            if frame is None:
                current = (None, {"connected": False, "error": stats})
            else:
                if pixels != last_pixels:
                    last_pixels, last_pixel_update = pixels, now
                valid = frame_is_fresh(pixels=pixels, now=now,
                    ready_after=next_press + 0.15, requested_at=key_requested_at,
                    updated_at=last_pixel_update, instrument_seen=instrument_seen,
                    gaps=stats["gaps"], baseline=reading_gap_baseline)
                reading = read_display(frame) if valid else None
                current = (frame if pixels else None,
                           {**stats, "connected": True, "pixels": pixels, "reading": reading})
        if args.latest and pixels and now - last_saved >= 1:
            frame.save(args.latest)
            last_saved = now
        try:
            latest.get_nowait()
        except queue.Empty:
            pass
        latest.put_nowait((frame, pixels, stats))

    def remember_wifi_info(info):
        nonlocal wifi_details
        wifi_details = info

    def show_wifi_info():
        if not wifi_details:
            return
        ssid, password = wifi_details
        dialog = tk.Toplevel(root)
        dialog.title("Данные сети ESP32")
        dialog.transient(root)
        dialog.resizable(False, False)
        copied = ttk.Label(dialog)

        def copy_value(label, value):
            root.clipboard_clear()
            root.clipboard_append(value)
            copied.config(text=f"Скопировано: {label}")

        fields = (("Имя сети", ssid), ("Пароль", password),
                  ("IP-адрес", "192.168.4.1"), ("TCP-порт", "8769"))
        for row, (label, value) in enumerate(fields):
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
            entry = ttk.Entry(dialog, width=20)
            entry.insert(0, value)
            entry.config(state="readonly")
            entry.grid(row=row, column=1, pady=4)
            ttk.Button(dialog, text="Копировать",
                       command=lambda name=label, text=value: copy_value(name, text)).grid(
                           row=row, column=2, padx=8, pady=4)
        copied.grid(row=len(fields), column=0, columnspan=2, sticky="w", padx=8)
        ttk.Button(dialog, text="Закрыть", command=dialog.destroy).grid(
            row=len(fields), column=2, padx=8, pady=8)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.grab_set()

    def worker(options, cancelled):
        try:
            receive(options, cancelled, publish, commands, remember_wifi_info)
        except (OSError, ValueError) as error:
            publish(None, 0, str(error))

    def toggle_connection():
        nonlocal session, thread, current, last_pixels, last_pixel_update, next_press
        nonlocal reading_gap_baseline, wifi_details, keypad_mode
        if thread and thread.is_alive():
            session.set()
            with control_lock:
                current = (None, {"connected": False})
            action.config(text="Отключаю…", state="disabled")
            return
        try:
            options = argparse.Namespace(**vars(args))
            options.host = host.get().strip() if transport.get() == "Wi-Fi" else None
            if transport.get() == "Wi-Fi":
                options.tcp_port = int(tcp_port.get())
                if not options.host or not 1 <= options.tcp_port <= 65535:
                    raise ValueError
            else:
                options.port, options.baud = port_name.get().strip(), int(baud.get())
                if not options.port or options.baud <= 0:
                    raise ValueError
        except ValueError:
            status.config(text="Проверьте адрес, порт и скорость подключения")
            return
        for pending in (latest, commands):
            try:
                pending.get_nowait()
            except queue.Empty:
                pass
        with control_lock:
            current = (None, {"connected": False})
            last_pixels = reading_gap_baseline = 0
            last_pixel_update = next_press = 0.0
            session = threading.Event()
        if not options.host:
            wifi_details = None
        keypad_mode = None
        screen.config(image="", width=64, height=20)
        keypad_status.config(text="Клавиатура: ожидание данных")
        target = f"{options.host}:{options.tcp_port}" if options.host else options.port
        root.title(f"LB02A • {target}")
        status.config(text=f"Подключение к {target}…")
        action.config(text="Отключить", state="normal")
        thread = threading.Thread(target=worker, args=(options, session), daemon=True)
        thread.start()

    def refresh():
        nonlocal keypad_mode, thread, current
        try:
            frame, pixels, stats = latest.get_nowait()
        except queue.Empty:
            pass
        else:
            if frame is None:
                status.config(text=stats)
                keypad_mode = None
            elif pixels:
                screen.image = ImageTk.PhotoImage(frame.resize(
                    (frame.width * 2, frame.height * 2), resample=0))
                screen.config(image=screen.image, width=0, height=0)
            if frame is not None:
                status.config(text=f"Байт {stats['bytes']}  ·  Пикселей {pixels}  ·  Пропусков {stats['gaps']}")
                keypad_mode = stats.get("keypad_mode")
                if keypad_mode is not None:
                    label = "управление" if keypad_mode == 1 else "наблюдение"
                    keypad_status.config(text=f"Клавиатура: {label}  ·  Опросов {stats['key_reads']}  ·  "
                                              f"Код 0x{stats['key_code']:02X}  ·  SCL {stats.get('key_clock', '—')}")
        if thread and not thread.is_alive():
            if session.is_set():
                status.config(text="Отключено")
            thread = None
            keypad_mode = None
            with control_lock:
                current = (None, {"connected": False, "error": current[1].get("error")})
            action.config(text="Подключить", state="normal")
        credentials.config(state="normal" if wifi_details else "disabled")
        enabled = thread is not None and not session.is_set() and keypad_mode == 1 and time.monotonic() >= next_press
        for number, button in enumerate(buttons, 1):
            state = "normal" if enabled and number != 13 else "disabled"
            if button.cget("state") != state:
                button.config(state=state)
        root.after(50, refresh)

    keypad_mode = None
    server = start_control(args.control_port, control_state, send_key) if args.control_port else None
    if autoconnect:
        toggle_connection()
    root.after(50, refresh)
    try:
        root.mainloop()
    finally:
        if session:
            session.set()
        if server:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
