"""Entry point for the IABS desktop application."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox

from settings import (
    APP_TITLE,
    initialize_application,
    log_exception_details,
    write_log,
)


def main() -> int:
    """Initialize IABS and start the graphical interface."""
    config = initialize_application()

    try:
        from gui import IABSApp
    except Exception as exc:  # pragma: no cover - startup path
        log_exception_details(
            exc,
            context="Arayuz modulu yuklenemedi",
            log_folder=config["folders"]["logs"],
        )
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_TITLE, f"Arayuz yuklenemedi: {exc}")
        root.destroy()
        return 1

    app = IABSApp(config)
    app.run()
    write_log("Program kapandi", config["folders"]["logs"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
