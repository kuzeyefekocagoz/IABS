"""Modern graphical user interface for the IABS desktop application."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from settings import (
    APP_TITLE,
    APP_VERSION,
    EXCEL_FILE_NAME,
    NOTIFICATION_MAIL,
    NOTIFICATION_TYPES,
    ensure_directories,
    load_config,
    save_config,
    write_log,
    log_exception_details,
)

try:
    import customtkinter as ctk
except ModuleNotFoundError:
    ctk = None


WINDOW_WIDTH = 1040
WINDOW_HEIGHT = 700
SIDEBAR_WIDTH = 240
ENTRY_WIDTH = 360
COMPACT_ENTRY_WIDTH = 170
PRIMARY_COLOR = "#2563EB"
SUCCESS_COLOR = "#16A34A"
WARNING_COLOR = "#D97706"
DARK_COLOR = "#111827"
MUTED_COLOR = "#6B7280"
LIGHT_BG = "#F3F4F6"
CARD_BG = "#FFFFFF"
SECTION_PAD = 18


class IABSApp:
    """Main application window and navigation controller."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Create the main window and show the dashboard."""
        self.config = config
        self.camera_thread: threading.Thread | None = None
        self.active_page = "dashboard"
        self.root = self._create_root()
        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)
        self._configure_style()
        self._set_window_size(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.show_main_menu()

    def run(self) -> None:
        """Start the Tkinter event loop."""
        self.root.mainloop()

    def show_main_menu(self) -> None:
        """Render the dashboard page."""
        self.active_page = "dashboard"
        self.config = load_config()
        content = self._build_shell("Kontrol Paneli", "Sistem hazir")

        hero = self._card(content)
        hero.pack(fill="x", padx=SECTION_PAD, pady=(SECTION_PAD, 12))
        self._label(hero, "IABS", 34, "bold", DARK_COLOR).pack(anchor="w")
        self._label(
            hero,
            "Insan Algilama ve Anlik Bildirim Sistemi",
            15,
            "normal",
            MUTED_COLOR,
        ).pack(anchor="w", pady=(4, 18))

        action_row = self._plain_frame(hero)
        action_row.pack(fill="x")
        self._button(
            action_row,
            "Kamerayi Baslat",
            self.start_camera,
            width=190,
            color=SUCCESS_COLOR,
        ).pack(side="left")
        self._button(
            action_row,
            "Ayarlar",
            self.show_settings,
            width=150,
        ).pack(side="left", padx=10)

        cards = self._plain_frame(content)
        cards.pack(fill="x", padx=SECTION_PAD, pady=8)
        self._status_card(
            cards,
            "Kamera",
            "Calisiyor" if self._camera_is_running() else "Kapali",
            SUCCESS_COLOR if self._camera_is_running() else WARNING_COLOR,
        ).pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._status_card(
            cards,
            "Bildirim",
            str(self.config["notification"]["type"]),
            PRIMARY_COLOR,
        ).pack(side="left", fill="both", expand=True, padx=8)
        self._status_card(
            cards,
            "Confidence",
            str(self.config["camera"]["confidence"]),
            DARK_COLOR,
        ).pack(side="left", fill="both", expand=True, padx=(8, 0))

        paths = self._card(content)
        paths.pack(fill="both", expand=True, padx=SECTION_PAD, pady=(12, 18))
        self._section_title(paths, "Kayit Konumlari")
        self._path_line(paths, "Fotograf", self.config["folders"]["photos"])
        self._path_line(paths, "Excel", self.config["folders"]["excel"])
        self._path_line(paths, "Log", self.config["folders"]["logs"])

    def show_settings(self) -> None:
        """Render the settings page and bind editable values."""
        self.active_page = "settings"
        self.config = load_config()
        variables = self._build_settings_variables()
        content = self._build_shell(
            "Ayarlar",
            "Tum tercihler config.json icinde saklanir",
        )

        scroll_container, body = self._scrollable_frame(content)
        scroll_container.pack(
            fill="both",
            expand=True,
            padx=SECTION_PAD,
            pady=SECTION_PAD,
        )
        left = self._plain_frame(body)
        right = self._plain_frame(body)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        self._build_general_card(left, variables)
        self._build_mail_card(left, variables)
        self._build_camera_card(right, variables)
        self._build_folder_card(right, variables)
        self._build_whatsapp_card(right, variables)

        footer = self._card(content)
        footer.pack(fill="x", padx=SECTION_PAD, pady=(0, SECTION_PAD))
        self._button(
            footer,
            "Kaydet",
            lambda: self.save_settings(variables),
            width=150,
            color=SUCCESS_COLOR,
        ).pack(side="right")
        self._button(
            footer,
            "Iptal",
            self.show_main_menu,
            width=130,
            color=MUTED_COLOR,
        ).pack(side="right", padx=(0, 10))

    def show_records(self) -> None:
        """Render the records page with folder shortcuts and log preview."""
        self.active_page = "records"
        self.config = load_config()
        content = self._build_shell("Kayitlar", "Fotograf, Excel ve log dosyalari")
        folders = self.config.get("folders", {})

        shortcut_row = self._plain_frame(content)
        shortcut_row.pack(fill="x", padx=SECTION_PAD, pady=SECTION_PAD)
        self._shortcut_card(
            shortcut_row,
            "Fotograflar",
            "Algilama aninda kaydedilen kareler",
            lambda: self.open_folder(folders.get("photos", "")),
        ).pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._shortcut_card(
            shortcut_row,
            "Excel",
            "Algilama kayit tablosu",
            lambda: self.open_folder(folders.get("excel", "")),
        ).pack(side="left", fill="both", expand=True, padx=8)
        self._shortcut_card(
            shortcut_row,
            "Log",
            "Program olay kayitlari",
            lambda: self.open_folder(folders.get("logs", "")),
        ).pack(side="left", fill="both", expand=True, padx=(8, 0))

        log_card = self._card(content)
        log_card.pack(fill="both", expand=True, padx=SECTION_PAD, pady=(0, SECTION_PAD))
        self._section_title(log_card, "Son Log Kayitlari")
        text = self._text_box(log_card)
        text.pack(fill="both", expand=True, pady=(10, 0))
        text.insert("1.0", self._read_recent_logs())
        text.configure(state="disabled")

    def show_about(self) -> None:
        """Display program information."""
        messagebox.showinfo(
            "Hakkinda",
            (
                f"{APP_TITLE}\n"
                f"Surum: {APP_VERSION}\n\n"
                "Python, Ultralytics YOLO11, OpenCV, Tkinter, ByteTrack, "
                "threading, SMTP ve WhatsApp API destegi ile hazirlandi."
            ),
        )

    def start_camera(self) -> None:
        """Start the camera module without blocking the interface."""
        if self._camera_is_running():
            messagebox.showinfo(APP_TITLE, "Kamera zaten calisiyor.")
            return

        self.config = load_config()
        ensure_directories(self.config)
        write_log("Kamera baslatma istegi alindi", self.config["folders"]["logs"])

        try:
            from camera import start_camera, verify_vision_dependencies
        except Exception as exc:  # pragma: no cover - runtime path
            log_exception_details(
                exc,
                context="Kamera modulu yuklenemedi",
                log_folder=self.config["folders"]["logs"],
            )
            messagebox.showerror(APP_TITLE, f"Kamera modulu yuklenemedi: {exc}")
            return

        try:
            verify_vision_dependencies()
        except RuntimeError as exc:
            log_exception_details(
                exc,
                context="Kamera bagimlilikleri kontrol edilemedi",
                log_folder=self.config["folders"]["logs"],
            )
            messagebox.showerror(APP_TITLE, str(exc))
            return

        self.camera_thread = threading.Thread(
            target=start_camera,
            args=(self.config,),
            daemon=True,
        )
        self.camera_thread.start()
        self.show_main_menu()

    def save_settings(self, variables: dict[str, tk.Variable]) -> None:
        """Validate and save all settings from the settings screen."""
        try:
            new_config = self._variables_to_config(variables)
            ensure_directories(new_config)
            save_config(new_config)
            self.config = new_config
            write_log("Ayarlar kaydedildi", self.config["folders"]["logs"])
        except (OSError, ValueError, tk.TclError) as exc:
            write_log(f"Ayar kaydetme hatasi: {exc}")
            messagebox.showerror("Hata", f"Ayarlar kaydedilemedi:\n{exc}")
            return

        messagebox.showinfo(APP_TITLE, "Ayarlar kaydedildi.")
        self.show_main_menu()

    def open_folder(self, folder_path: str) -> None:
        """Open a record folder in Windows File Explorer."""
        if not folder_path:
            messagebox.showwarning("Uyari", "Klasor yolu bulunamadi.")
            return

        path = Path(folder_path)
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(path)
        except OSError as exc:
            write_log(f"Klasor acma hatasi: {exc}", self.config["folders"]["logs"])
            messagebox.showerror("Hata", f"Klasor acilamadi:\n{path}")

    def exit_application(self) -> None:
        """Close the application cleanly."""
        write_log("Program kapandi", self.config["folders"]["logs"])
        self.root.destroy()

    def _build_shell(self, title: str, subtitle: str) -> tk.Widget:
        """Create the app chrome with sidebar and content area."""
        self._clear_window()
        shell = self._plain_frame(self.root)
        shell.pack(fill="both", expand=True)

        sidebar = self._sidebar(shell)
        sidebar.pack(side="left", fill="y")
        content = self._plain_frame(shell)
        content.pack(side="left", fill="both", expand=True)

        header = self._plain_frame(content)
        header.pack(fill="x", padx=SECTION_PAD, pady=(SECTION_PAD, 0))
        self._label(header, title, 26, "bold", DARK_COLOR).pack(anchor="w")
        self._label(header, subtitle, 13, "normal", MUTED_COLOR).pack(anchor="w")
        return content

    def _sidebar(self, parent: tk.Widget) -> tk.Widget:
        """Create the left navigation sidebar."""
        sidebar = self._colored_frame(parent, DARK_COLOR, width=SIDEBAR_WIDTH)
        sidebar.pack_propagate(False)
        brand = self._plain_frame(sidebar, bg=DARK_COLOR)
        brand.pack(fill="x", padx=18, pady=(24, 26))
        self._label(brand, "IABS", 30, "bold", "#FFFFFF", bg=DARK_COLOR).pack(
            anchor="w"
        )
        self._label(
            brand,
            "Anlik Bildirim Sistemi",
            12,
            "normal",
            "#CBD5E1",
            bg=DARK_COLOR,
        ).pack(anchor="w")

        self._nav_button(sidebar, "Kontrol Paneli", self.show_main_menu, "dashboard")
        self._nav_button(sidebar, "Kamerayi Baslat", self.start_camera, "camera")
        self._nav_button(sidebar, "Ayarlar", self.show_settings, "settings")
        self._nav_button(sidebar, "Kayitlar", self.show_records, "records")
        self._nav_button(sidebar, "Hakkinda", self.show_about, "about")

        bottom = self._plain_frame(sidebar, bg=DARK_COLOR)
        bottom.pack(side="bottom", fill="x", padx=18, pady=18)
        self._button(
            bottom,
            "Cikis",
            self.exit_application,
            width=185,
            color="#374151",
        ).pack(fill="x")
        return sidebar

    def _build_general_card(
        self,
        parent: tk.Widget,
        variables: dict[str, tk.Variable],
    ) -> None:
        """Build notification and alarm settings card."""
        card = self._card(parent)
        card.pack(fill="x", pady=(0, 12))
        self._section_title(card, "Genel")
        self._field_label(card, "Bildirim Turu")
        self._option_menu(
            card,
            variables["notification_type"],
            list(NOTIFICATION_TYPES),
        ).pack(fill="x", pady=(0, 10))
        self._check(card, "Alarm sesi acik", variables["alarm_enabled"]).pack(
            anchor="w", pady=6
        )
        self._entry_row(card, "Mail bekleme suresi", variables["mail_delay"])

    def _build_mail_card(
        self,
        parent: tk.Widget,
        variables: dict[str, tk.Variable],
    ) -> None:
        """Build mail settings card."""
        card = self._card(parent)
        card.pack(fill="x", pady=(0, 12))
        self._section_title(card, "Mail")
        self._entry_row(card, "Gonderen Gmail", variables["mail_sender"])
        self._entry_row(card, "Gmail uygulama sifresi", variables["mail_password"], "*")
        self._entry_row(card, "Alici Mail", variables["mail_receiver"])

    def _build_camera_card(
        self,
        parent: tk.Widget,
        variables: dict[str, tk.Variable],
    ) -> None:
        """Build camera settings card."""
        card = self._card(parent)
        card.pack(fill="x", pady=(0, 12))
        self._section_title(card, "Kamera")
        grid = self._plain_frame(card)
        grid.pack(fill="x")
        self._compact_entry(grid, "Kamera No", variables["camera_index"], 0, 0)
        self._compact_entry(grid, "Confidence", variables["confidence"], 0, 1)
        self._compact_entry(grid, "Min Genislik", variables["min_box_width"], 1, 0)
        self._compact_entry(grid, "Min Yukseklik", variables["min_box_height"], 1, 1)
        self._check(card, "FPS goster", variables["show_fps"]).pack(anchor="w", pady=4)
        self._check(card, "Tarih saat goster", variables["show_datetime"]).pack(
            anchor="w", pady=4
        )
        self._check(card, "Kisi sayisi goster", variables["show_count"]).pack(
            anchor="w", pady=4
        )

    def _build_folder_card(
        self,
        parent: tk.Widget,
        variables: dict[str, tk.Variable],
    ) -> None:
        """Build folder selector card."""
        card = self._card(parent)
        card.pack(fill="x", pady=(0, 12))
        self._section_title(card, "Klasorler")
        self._folder_row(card, "Fotograf", variables["photos_folder"])
        self._folder_row(card, "Excel", variables["excel_folder"])
        self._folder_row(card, "Log", variables["logs_folder"])

    def _build_whatsapp_card(
        self,
        parent: tk.Widget,
        variables: dict[str, tk.Variable],
    ) -> None:
        """Build WhatsApp settings card."""
        card = self._card(parent)
        card.pack(fill="x")
        self._section_title(card, "WhatsApp")
        self._field_label(card, "Saglayici")
        self._option_menu(
            card,
            variables["whatsapp_provider"],
            ["cloud_api", "twilio"],
        ).pack(fill="x", pady=(0, 8))
        self._entry_row(card, "Telefon", variables["whatsapp_phone"])
        self._entry_row(card, "Cloud API token", variables["cloud_token"])
        self._entry_row(card, "Cloud telefon ID", variables["cloud_phone_id"])
        self._entry_row(card, "Cloud sablon adi", variables["cloud_template"])
        self._entry_row(card, "Cloud dil kodu", variables["cloud_language"])
        self._entry_row(card, "Twilio account SID", variables["twilio_sid"])
        self._entry_row(card, "Twilio auth token", variables["twilio_token"], "*")
        self._entry_row(card, "Twilio gonderen no", variables["twilio_from"])

    def _build_settings_variables(self) -> dict[str, tk.Variable]:
        """Create Tk variables from the active configuration."""
        config = self.config
        return {
            "notification_type": tk.StringVar(value=config["notification"]["type"]),
            "mail_sender": tk.StringVar(value=config["mail"]["sender_gmail"]),
            "mail_password": tk.StringVar(value=config["mail"]["app_password"]),
            "mail_receiver": tk.StringVar(value=config["mail"]["receiver_mail"]),
            "whatsapp_provider": tk.StringVar(value=config["whatsapp"]["provider"]),
            "whatsapp_phone": tk.StringVar(value=config["whatsapp"]["phone_number"]),
            "cloud_token": tk.StringVar(
                value=config["whatsapp"]["cloud_api"]["access_token"]
            ),
            "cloud_phone_id": tk.StringVar(
                value=config["whatsapp"]["cloud_api"]["phone_number_id"]
            ),
            "cloud_template": tk.StringVar(
                value=config["whatsapp"]["cloud_api"]["template_name"]
            ),
            "cloud_language": tk.StringVar(
                value=config["whatsapp"]["cloud_api"]["language_code"]
            ),
            "twilio_sid": tk.StringVar(
                value=config["whatsapp"]["twilio"]["account_sid"]
            ),
            "twilio_token": tk.StringVar(
                value=config["whatsapp"]["twilio"]["auth_token"]
            ),
            "twilio_from": tk.StringVar(
                value=config["whatsapp"]["twilio"]["from_number"]
            ),
            "photos_folder": tk.StringVar(value=config["folders"]["photos"]),
            "excel_folder": tk.StringVar(value=config["folders"]["excel"]),
            "logs_folder": tk.StringVar(value=config["folders"]["logs"]),
            "alarm_enabled": tk.BooleanVar(value=config["alarm"]["enabled"]),
            "mail_delay": tk.StringVar(
                value=str(config["runtime"]["mail_delay_seconds"])
            ),
            "camera_index": tk.StringVar(value=str(config["camera"]["index"])),
            "confidence": tk.StringVar(value=str(config["camera"]["confidence"])),
            "min_box_width": tk.StringVar(
                value=str(config["camera"]["minimum_box_width"])
            ),
            "min_box_height": tk.StringVar(
                value=str(config["camera"]["minimum_box_height"])
            ),
            "show_fps": tk.BooleanVar(value=config["camera"]["show_fps"]),
            "show_datetime": tk.BooleanVar(value=config["camera"]["show_datetime"]),
            "show_count": tk.BooleanVar(value=config["camera"]["show_person_count"]),
        }

    def _variables_to_config(
        self,
        variables: dict[str, tk.Variable],
    ) -> dict[str, Any]:
        """Convert form variables into the nested config dictionary."""
        confidence = float(variables["confidence"].get())
        if not 0.0 < confidence <= 1.0:
            raise ValueError("YOLO confidence 0 ile 1 arasinda olmalidir.")

        notification_type = str(variables["notification_type"].get())
        if notification_type not in NOTIFICATION_TYPES:
            notification_type = NOTIFICATION_MAIL

        return {
            "notification": {"type": notification_type},
            "mail": {
                "sender_gmail": str(variables["mail_sender"].get()).strip(),
                "app_password": str(variables["mail_password"].get()).strip(),
                "receiver_mail": str(variables["mail_receiver"].get()).strip(),
                "smtp_host": self.config["mail"]["smtp_host"],
                "smtp_port": int(self.config["mail"]["smtp_port"]),
            },
            "whatsapp": {
                "provider": str(variables["whatsapp_provider"].get()),
                "phone_number": str(variables["whatsapp_phone"].get()).strip(),
                "cloud_api": {
                    "access_token": str(variables["cloud_token"].get()).strip(),
                    "phone_number_id": str(
                        variables["cloud_phone_id"].get()
                    ).strip(),
                    "template_name": str(variables["cloud_template"].get()).strip(),
                    "language_code": str(variables["cloud_language"].get()).strip(),
                },
                "twilio": {
                    "account_sid": str(variables["twilio_sid"].get()).strip(),
                    "auth_token": str(variables["twilio_token"].get()).strip(),
                    "from_number": str(variables["twilio_from"].get()).strip(),
                },
            },
            "folders": {
                "photos": str(variables["photos_folder"].get()).strip(),
                "excel": str(variables["excel_folder"].get()).strip(),
                "logs": str(variables["logs_folder"].get()).strip(),
            },
            "camera": {
                "index": int(variables["camera_index"].get()),
                "frame_width": int(self.config["camera"]["frame_width"]),
                "frame_height": int(self.config["camera"]["frame_height"]),
                "confidence": confidence,
                "minimum_box_width": int(variables["min_box_width"].get()),
                "minimum_box_height": int(variables["min_box_height"].get()),
                "image_size": int(self.config["camera"]["image_size"]),
                "show_fps": bool(variables["show_fps"].get()),
                "show_datetime": bool(variables["show_datetime"].get()),
                "show_person_count": bool(variables["show_count"].get()),
            },
            "alarm": {
                "enabled": bool(variables["alarm_enabled"].get()),
                "frequency": int(self.config["alarm"]["frequency"]),
                "duration_ms": int(self.config["alarm"]["duration_ms"]),
            },
            "runtime": {
                "mail_delay_seconds": int(variables["mail_delay"].get()),
                "excel_file_name": EXCEL_FILE_NAME,
                "model_name": str(self.config["runtime"]["model_name"]),
                "tracker_name": str(self.config["runtime"]["tracker_name"]),
            },
        }

    def _status_card(
        self,
        parent: tk.Widget,
        title: str,
        value: str,
        color: str,
    ) -> tk.Widget:
        """Create a compact dashboard status card."""
        card = self._card(parent)
        self._label(card, title, 13, "bold", MUTED_COLOR).pack(anchor="w")
        self._label(card, value, 24, "bold", color).pack(anchor="w", pady=(8, 0))
        return card

    def _shortcut_card(
        self,
        parent: tk.Widget,
        title: str,
        description: str,
        command: Callable[[], None],
    ) -> tk.Widget:
        """Create a record shortcut card."""
        card = self._card(parent)
        self._label(card, title, 18, "bold", DARK_COLOR).pack(anchor="w")
        self._label(card, description, 12, "normal", MUTED_COLOR).pack(
            anchor="w", pady=(4, 14)
        )
        self._button(card, "Ac", command, width=95).pack(anchor="w")
        return card

    def _path_line(self, parent: tk.Widget, label: str, path: str) -> None:
        """Create a readable path display row."""
        row = self._plain_frame(parent)
        row.pack(fill="x", pady=6)
        self._label(row, label, 13, "bold", DARK_COLOR).pack(side="left")
        self._label(row, path, 12, "normal", MUTED_COLOR).pack(side="left", padx=12)

    def _folder_row(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.Variable,
    ) -> None:
        """Create a folder selector row."""
        self._field_label(parent, label)
        row = self._plain_frame(parent)
        row.pack(fill="x", pady=(0, 8))
        self._entry(row, variable).pack(side="left", fill="x", expand=True)
        self._button(
            row,
            "Sec",
            lambda: self._select_folder(variable),
            width=70,
            color=MUTED_COLOR,
        ).pack(side="left", padx=(8, 0))

    def _entry_row(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.Variable,
        show: str | None = None,
    ) -> None:
        """Create a labeled input row."""
        self._field_label(parent, label)
        self._entry(parent, variable, show=show).pack(fill="x", pady=(0, 8))

    def _compact_entry(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.Variable,
        row_index: int,
        column_index: int,
    ) -> None:
        """Create a compact grid input."""
        box = self._plain_frame(parent)
        box.grid(row=row_index, column=column_index, sticky="ew", padx=4, pady=4)
        parent.grid_columnconfigure(column_index, weight=1)
        self._field_label(box, label)
        self._entry(box, variable, width=COMPACT_ENTRY_WIDTH).pack(fill="x")

    def _section_title(self, parent: tk.Widget, text: str) -> None:
        """Create a section title."""
        self._label(parent, text, 18, "bold", DARK_COLOR).pack(anchor="w", pady=(0, 10))

    def _field_label(self, parent: tk.Widget, text: str) -> None:
        """Create a compact form label."""
        self._label(parent, text, 12, "bold", MUTED_COLOR).pack(anchor="w", pady=(6, 4))

    def _select_folder(self, variable: tk.Variable) -> None:
        """Open folder picker and write the selected path to a variable."""
        selected = filedialog.askdirectory()
        if selected:
            variable.set(selected)

    def _read_recent_logs(self) -> str:
        """Return the latest log lines for the records page."""
        log_path = Path(self.config["folders"]["logs"]) / "log.txt"
        if not log_path.exists():
            return "Log kaydi bulunamadi."

        lines = log_path.read_text(encoding="utf-8").splitlines()
        recent_lines = lines[-40:]
        return "\n".join(recent_lines) if recent_lines else "Log kaydi bulunamadi."

    def _camera_is_running(self) -> bool:
        """Return whether the camera worker thread is alive."""
        return bool(self.camera_thread and self.camera_thread.is_alive())

    def _clear_window(self) -> None:
        """Remove all widgets from the root window."""
        for child in self.root.winfo_children():
            child.destroy()

    def _set_window_size(self, width: int, height: int) -> None:
        """Resize and center the application window."""
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(width, height)
        self.root.update_idletasks()
        x_position = int((self.root.winfo_screenwidth() - width) / 2)
        y_position = int((self.root.winfo_screenheight() - height) / 2)
        self.root.geometry(f"{width}x{height}+{x_position}+{y_position}")

    def _create_root(self) -> tk.Tk:
        """Create a CustomTkinter or standard Tk root window."""
        if ctk:
            ctk.set_appearance_mode("light")
            ctk.set_default_color_theme("blue")
            root = ctk.CTk(fg_color=LIGHT_BG)
        else:
            root = tk.Tk()
            root.configure(bg=LIGHT_BG)

        root.title(APP_TITLE)
        return root

    def _configure_style(self) -> None:
        """Configure ttk widgets for the fallback interface."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=LIGHT_BG)
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("TLabel", background=LIGHT_BG, foreground=DARK_COLOR)
        style.configure("TButton", padding=(12, 8))
        style.configure("TEntry", padding=6)

    def _plain_frame(self, parent: tk.Widget, bg: str | None = None) -> tk.Widget:
        """Create a transparent frame for layout."""
        color = bg or LIGHT_BG
        if ctk:
            return ctk.CTkFrame(parent, fg_color=color, corner_radius=0)
        return tk.Frame(parent, bg=color)

    def _scrollable_frame(self, parent: tk.Widget) -> tuple[tk.Widget, tk.Widget]:
        """Create a scrollable frame for long settings pages."""
        if ctk:
            frame = ctk.CTkScrollableFrame(
                parent,
                fg_color=LIGHT_BG,
                corner_radius=0,
                scrollbar_button_color="#CBD5E1",
                scrollbar_button_hover_color="#94A3B8",
            )
            return frame, frame

        container = tk.Frame(parent, bg=LIGHT_BG)
        canvas = tk.Canvas(
            container,
            bg=LIGHT_BG,
            highlightthickness=0,
            bd=0,
        )
        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=canvas.yview,
        )
        inner = tk.Frame(canvas, bg=LIGHT_BG)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )
        canvas.bind_all(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(
                int(-1 * (event.delta / 120)),
                "units",
            ),
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return container, inner

    def _colored_frame(
        self,
        parent: tk.Widget,
        color: str,
        width: int | None = None,
    ) -> tk.Widget:
        """Create a colored frame."""
        if ctk:
            return ctk.CTkFrame(parent, fg_color=color, corner_radius=0, width=width)
        return tk.Frame(parent, bg=color, width=width)

    def _card(self, parent: tk.Widget) -> tk.Widget:
        """Create a card container."""
        if ctk:
            return ctk.CTkFrame(
                parent,
                fg_color=CARD_BG,
                corner_radius=12,
                border_width=1,
                border_color="#E5E7EB",
            )
        return ttk.Frame(parent, style="Card.TFrame", padding=16)

    def _label(
        self,
        parent: tk.Widget,
        text: str,
        font_size: int = 13,
        weight: str = "normal",
        color: str = DARK_COLOR,
        bg: str | None = None,
    ) -> tk.Widget:
        """Create a label compatible with the selected UI toolkit."""
        if ctk:
            return ctk.CTkLabel(
                parent,
                text=text,
                font=("Segoe UI", font_size, weight),
                text_color=color,
            )
        return tk.Label(
            parent,
            text=text,
            font=("Segoe UI", font_size, weight),
            fg=color,
            bg=bg or CARD_BG,
        )

    def _button(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        width: int = 150,
        color: str = PRIMARY_COLOR,
    ) -> tk.Widget:
        """Create a modern button."""
        if ctk:
            return ctk.CTkButton(
                parent,
                text=text,
                command=command,
                width=width,
                height=38,
                corner_radius=8,
                fg_color=color,
                hover_color="#1D4ED8",
                font=("Segoe UI", 13, "bold"),
            )
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=max(8, int(width / 10)),
            bg=color,
            fg="#FFFFFF",
            activebackground=color,
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            padx=12,
            pady=8,
        )

    def _nav_button(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        page_key: str,
    ) -> None:
        """Create a sidebar navigation button."""
        active = self.active_page == page_key
        color = PRIMARY_COLOR if active else "#1F2937"
        button = self._button(parent, text, command, width=198, color=color)
        button.pack(fill="x", padx=18, pady=5)

    def _entry(
        self,
        parent: tk.Widget,
        variable: tk.Variable,
        show: str | None = None,
        width: int = ENTRY_WIDTH,
    ) -> tk.Widget:
        """Create an entry compatible with the selected UI toolkit."""
        if ctk:
            return ctk.CTkEntry(
                parent,
                textvariable=variable,
                width=width,
                height=34,
                show=show,
                corner_radius=8,
            )
        return ttk.Entry(parent, textvariable=variable, show=show)

    def _option_menu(
        self,
        parent: tk.Widget,
        variable: tk.Variable,
        values: list[str],
    ) -> tk.Widget:
        """Create an option menu compatible with the selected UI toolkit."""
        if ctk:
            return ctk.CTkOptionMenu(
                parent,
                variable=variable,
                values=values,
                height=34,
                corner_radius=8,
            )
        return ttk.OptionMenu(parent, variable, variable.get(), *values)

    def _check(
        self,
        parent: tk.Widget,
        text: str,
        variable: tk.Variable,
    ) -> tk.Widget:
        """Create a checkbox compatible with the selected UI toolkit."""
        if ctk:
            return ctk.CTkSwitch(parent, text=text, variable=variable)
        return ttk.Checkbutton(parent, text=text, variable=variable)

    def _text_box(self, parent: tk.Widget) -> tk.Widget:
        """Create a read-only log preview text box."""
        if ctk:
            return ctk.CTkTextbox(parent, font=("Consolas", 12), corner_radius=8)
        return tk.Text(parent, font=("Consolas", 10), relief="flat", height=14)
