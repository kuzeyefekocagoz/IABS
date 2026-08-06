"""SMTP SSL mail notification sender for IABS."""

from __future__ import annotations

import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Protocol

from settings import APP_TITLE, log_exception_details, write_log


class DetectionEventLike(Protocol):
    """Protocol for detection event values used by notification modules."""

    date_text: str
    time_text: str
    person_count: int
    photo_name: str
    photo_path: str
    notification_type: str


def send_detection_mail(
    event: DetectionEventLike,
    config: dict[str, Any],
) -> bool:
    """Send a detection e-mail with the captured photo attached."""
    log_folder = config["folders"]["logs"]

    try:
        mail_config = config["mail"]
        sender = str(mail_config["sender_gmail"]).strip()
        password = str(mail_config["app_password"]).strip()
        receiver = str(mail_config["receiver_mail"]).strip()

        if not sender or not password or not receiver:
            write_log("Mail gonderilemedi: mail ayarlari eksik", log_folder)
            return False

        message = _build_mail_message(event, config, sender, receiver)
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(
            str(mail_config["smtp_host"]),
            int(mail_config["smtp_port"]),
            context=context,
        ) as server:
            server.login(sender, password)
            server.send_message(message)

        write_log("Mail gonderildi", log_folder)
        return True
    except Exception as exc:
        log_exception_details(
            exc,
            context="Mail gonderme hatasi",
            log_folder=log_folder,
        )
        return False


def _build_mail_message(
    event: DetectionEventLike,
    config: dict[str, Any],
    sender: str,
    receiver: str,
) -> EmailMessage:
    """Create the e-mail body and attach the detection photo."""
    message = EmailMessage()
    message["Subject"] = "IABS - Yeni insan algilandi"
    message["From"] = sender
    message["To"] = receiver
    message.set_content(
        (
            f"{APP_TITLE}\n\n"
            "Kamera yeni bir insan algiladi.\n"
            f"Tarih: {event.date_text}\n"
            f"Saat: {event.time_text}\n"
            f"Kisi sayisi: {event.person_count}\n"
            f"Bildirim turu: {event.notification_type}\n"
            f"Fotograf: {event.photo_name}\n"
            f"Dosya yolu: {event.photo_path}\n"
        )
    )

    photo_path = Path(event.photo_path)
    if photo_path.exists():
        _attach_photo(message, photo_path)
    else:
        write_log(
            f"Mail eki bulunamadi: {photo_path}",
            config["folders"]["logs"],
        )

    return message


def _attach_photo(message: EmailMessage, photo_path: Path) -> None:
    """Attach the saved detection photo to an e-mail message."""
    content_type, _ = mimetypes.guess_type(photo_path)
    if content_type:
        maintype, subtype = content_type.split("/", 1)
    else:
        maintype, subtype = "image", "jpeg"

    with photo_path.open("rb") as file:
        message.add_attachment(
            file.read(),
            maintype=maintype,
            subtype=subtype,
            filename=photo_path.name,
        )
