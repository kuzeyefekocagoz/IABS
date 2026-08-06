"""Application settings and configuration helpers for IABS."""

from __future__ import annotations

import importlib
import json
import os
import sys
import traceback
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


APP_NAME = "IABS"
APP_TITLE = "IABS (Insan Algilama ve Anlik Bildirim Sistemi)"
APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
PHOTOS_DIR = BASE_DIR / "photos"
LOGS_DIR = BASE_DIR / "logs"
EXCEL_DIR = BASE_DIR / "excel"
LOG_FILE = LOGS_DIR / "log.txt"
EXCEL_FILE_NAME = "iabs_kayitlari.xlsx"

DEFAULT_CAMERA_INDEX = 0
DEFAULT_MAIL_DELAY_SECONDS = 30
DEFAULT_YOLO_CONFIDENCE = 0.75
DEFAULT_MIN_BOX_WIDTH = 70
DEFAULT_MIN_BOX_HEIGHT = 120
DEFAULT_FRAME_WIDTH = 1280
DEFAULT_FRAME_HEIGHT = 720
DEFAULT_IMAGE_SIZE = 320
DEFAULT_FRAME_SKIP = 1
DEFAULT_ALARM_FREQUENCY = 1200
DEFAULT_ALARM_DURATION_MS = 80
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 465
PERSON_CLASS_ID = 0

NOTIFICATION_MAIL = "Mail"
NOTIFICATION_WHATSAPP = "WhatsApp"
NOTIFICATION_BOTH = "Mail + WhatsApp"
NOTIFICATION_TYPES = (
    NOTIFICATION_MAIL,
    NOTIFICATION_WHATSAPP,
    NOTIFICATION_BOTH,
)

DEFAULT_CONFIG: dict[str, Any] = {
    "notification": {
        "type": NOTIFICATION_MAIL,
    },
    "mail": {
        "sender_gmail": "",
        "app_password": "",
        "receiver_mail": "",
        "smtp_host": DEFAULT_SMTP_HOST,
        "smtp_port": DEFAULT_SMTP_PORT,
    },
    "whatsapp": {
        "provider": "cloud_api",
        "phone_number": "",
        "cloud_api": {
            "access_token": "",
            "phone_number_id": "",
            "template_name": "iabs_alert",
            "language_code": "tr",
        },
        "twilio": {
            "account_sid": "",
            "auth_token": "",
            "from_number": "",
        },
    },
    "folders": {
        "photos": str(PHOTOS_DIR),
        "excel": str(EXCEL_DIR),
        "logs": str(LOGS_DIR),
    },
    "camera": {
        "index": DEFAULT_CAMERA_INDEX,
        "frame_width": DEFAULT_FRAME_WIDTH,
        "frame_height": DEFAULT_FRAME_HEIGHT,
        "confidence": DEFAULT_YOLO_CONFIDENCE,
        "minimum_box_width": DEFAULT_MIN_BOX_WIDTH,
        "minimum_box_height": DEFAULT_MIN_BOX_HEIGHT,
        "image_size": DEFAULT_IMAGE_SIZE,
        "frame_skip": DEFAULT_FRAME_SKIP,
        "show_fps": True,
        "show_datetime": True,
        "show_person_count": True,
    },
    "alarm": {
        "enabled": True,
        "frequency": DEFAULT_ALARM_FREQUENCY,
        "duration_ms": DEFAULT_ALARM_DURATION_MS,
    },
    "runtime": {
        "mail_delay_seconds": DEFAULT_MAIL_DELAY_SECONDS,
        "excel_file_name": EXCEL_FILE_NAME,
        "model_name": "yolo11s.pt",
        "tracker_name": "bytetrack.yaml",
    },
}


def ensure_directories(config: dict[str, Any] | None = None) -> None:
    """Create all directories required by the application."""
    active_config = config or DEFAULT_CONFIG
    folder_config = active_config.get("folders", {})
    required_paths = {
        PHOTOS_DIR,
        LOGS_DIR,
        EXCEL_DIR,
        Path(folder_config.get("photos", PHOTOS_DIR)),
        Path(folder_config.get("excel", EXCEL_DIR)),
        Path(folder_config.get("logs", LOGS_DIR)),
    }

    for folder_path in required_paths:
        folder_path.mkdir(parents=True, exist_ok=True)


def merge_with_defaults(config: dict[str, Any]) -> dict[str, Any]:
    """Return a configuration dictionary completed with default values."""
    merged = deepcopy(DEFAULT_CONFIG)
    _merge_dict(merged, config)
    return merged


def load_config() -> dict[str, Any]:
    """Load the JSON configuration file and create it when missing."""
    if not CONFIG_FILE.exists():
        config = deepcopy(DEFAULT_CONFIG)
        ensure_directories(config)
        save_config(config)
        return config

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            loaded_config = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        backup_file = CONFIG_FILE.with_suffix(
            f".broken-{datetime.now():%Y%m%d-%H%M%S}.json"
        )
        CONFIG_FILE.replace(backup_file)
        config = deepcopy(DEFAULT_CONFIG)
        ensure_directories(config)
        save_config(config)
        write_log(f"Config okunamadi, varsayilan ayarlar olusturuldu: {exc}")
        return config

    config = merge_with_defaults(loaded_config)
    ensure_directories(config)
    save_config(config)
    return config


def save_config(config: dict[str, Any]) -> None:
    """Persist configuration values to config.json."""
    ensure_directories(config)
    with CONFIG_FILE.open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)


def write_log(message: str, log_folder: str | Path | None = None) -> None:
    """Append a timestamped message to the application log file."""
    target_folder = Path(log_folder) if log_folder else LOGS_DIR
    target_folder.mkdir(parents=True, exist_ok=True)
    log_file = target_folder / "log.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with log_file.open("a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def format_exception_details(exc: BaseException) -> str:
    """Return a readable exception summary including type, location and traceback."""
    tb = exc.__traceback__
    location = "unknown"
    if tb is not None:
        frame = tb.tb_frame
        location = f"{frame.f_code.co_filename}:{tb.tb_lineno}"

    return (
        f"{type(exc).__name__}: {exc}\n"
        f"Location: {location}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )


def log_exception_details(exc: BaseException, *, context: str, log_folder: str | Path | None = None) -> None:
    """Log the full traceback and exception context to the application log."""
    details = format_exception_details(exc)
    write_log(f"{context}: {details}", log_folder)


def collect_dependency_status() -> list[dict[str, str]]:
    """Attempt to import the most important runtime dependencies and record results."""
    modules = [
        "cv2",
        "ultralytics",
        "numpy",
        "openpyxl",
        "requests",
        "customtkinter",
        "PIL",
        "winsound",
        "lap",
        "torch",
        "torchvision",
    ]
    results: list[dict[str, str]] = []
    for module_name in modules:
        try:
            importlib.import_module(module_name)
            results.append({"module": module_name, "status": "ok", "error": ""})
        except Exception as exc:  # pragma: no cover - diagnostics path
            results.append(
                {
                    "module": module_name,
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return results


def log_startup_environment(config: dict[str, Any]) -> None:
    """Write environment and dependency diagnostics before camera startup."""
    log_folder = Path(config["folders"]["logs"])
    log_folder.mkdir(parents=True, exist_ok=True)
    camera_path = BASE_DIR / "camera.py"
    model_path = Path(config["runtime"].get("model_name", ""))
    tracker_path = BASE_DIR / config["runtime"].get("tracker_name", "")
    config_path = CONFIG_FILE

    write_log(f"Python executable: {sys.executable}", log_folder)
    write_log(f"Python version: {sys.version}", log_folder)
    write_log(f"sys.path: {sys.path}", log_folder)
    write_log(f"Working directory: {os.getcwd()}", log_folder)
    write_log(f"camera.py path: {camera_path}", log_folder)
    write_log(f"model file exists: {model_path.exists()}", log_folder)
    write_log(f"bytetrack.yaml exists: {tracker_path.exists()}", log_folder)
    write_log(f"config.json read: {config_path.exists()}", log_folder)

    for item in collect_dependency_status():
        if item["status"] == "ok":
            write_log(f"Dependency check: {item['module']} imported successfully", log_folder)
        else:
            write_log(
                f"Dependency check failed: {item['module']} -> {item['error']}",
                log_folder,
            )


def initialize_application() -> dict[str, Any]:
    """Prepare folders, config file and startup log for the application."""
    config = load_config()
    ensure_directories(config)
    write_log("Program basladi", config["folders"]["logs"])
    return config


def _merge_dict(base: dict[str, Any], updates: dict[str, Any]) -> None:
    """Merge nested dictionaries without removing unknown future keys."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge_dict(base[key], value)
        else:
            base[key] = value
