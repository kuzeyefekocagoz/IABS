"""WhatsApp Cloud API and Twilio notification sender for IABS."""

from __future__ import annotations

from typing import Any, Protocol

from settings import APP_TITLE, log_exception_details, write_log


CLOUD_API_URL = "https://graph.facebook.com/v20.0/{phone_number_id}/messages"
CLOUD_API_TIMEOUT = 20
TWILIO_TIMEOUT = 20
TWILIO_API_URL = (
    "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
)


class DetectionEventLike(Protocol):
    """Protocol for detection event values used by notification modules."""

    date_text: str
    time_text: str
    person_count: int
    photo_name: str
    photo_path: str
    notification_type: str


def send_detection_whatsapp(
    event: DetectionEventLike,
    config: dict[str, Any],
) -> bool:
    """Send a WhatsApp alert using the selected provider."""
    provider = str(config["whatsapp"]["provider"]).strip().lower()

    if provider == "twilio":
        return send_with_twilio(event, config)

    return send_with_cloud_api(event, config)


def send_with_cloud_api(
    event: DetectionEventLike,
    config: dict[str, Any],
) -> bool:
    """Send a WhatsApp message through Meta WhatsApp Cloud API."""
    log_folder = config["folders"]["logs"]

    try:
        requests = _load_requests()
        whatsapp_config = config["whatsapp"]
        cloud_config = whatsapp_config["cloud_api"]
        phone_number = str(whatsapp_config["phone_number"]).strip()
        access_token = str(cloud_config["access_token"]).strip()
        phone_number_id = str(cloud_config["phone_number_id"]).strip()

        if not phone_number or not access_token or not phone_number_id:
            write_log("WhatsApp gonderilemedi: Cloud API ayarlari eksik", log_folder)
            return False

        response = requests.post(
            CLOUD_API_URL.format(phone_number_id=phone_number_id),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=_build_cloud_payload(event, config),
            timeout=CLOUD_API_TIMEOUT,
        )

        if response.ok:
            write_log("WhatsApp gonderildi", log_folder)
            return True

        write_log(
            f"WhatsApp Cloud API hatasi: {response.status_code} {response.text}",
            log_folder,
        )
        return False
    except Exception as exc:
        log_exception_details(
            exc,
            context="WhatsApp Cloud API gonderme hatasi",
            log_folder=log_folder,
        )
        return False


def send_with_twilio(
    event: DetectionEventLike,
    config: dict[str, Any],
) -> bool:
    """Send a WhatsApp message through Twilio's REST API."""
    log_folder = config["folders"]["logs"]

    try:
        requests = _load_requests()
        whatsapp_config = config["whatsapp"]
        twilio_config = whatsapp_config["twilio"]
        account_sid = str(twilio_config["account_sid"]).strip()
        auth_token = str(twilio_config["auth_token"]).strip()
        from_number = _normalize_twilio_whatsapp_number(
            str(twilio_config["from_number"]).strip()
        )
        to_number = _normalize_twilio_whatsapp_number(
            str(whatsapp_config["phone_number"]).strip()
        )

        if not account_sid or not auth_token or not from_number or not to_number:
            write_log("WhatsApp gonderilemedi: Twilio ayarlari eksik", log_folder)
            return False

        response = requests.post(
            TWILIO_API_URL.format(account_sid=account_sid),
            auth=(account_sid, auth_token),
            data={
                "From": from_number,
                "To": to_number,
                "Body": _build_text_message(event),
            },
            timeout=TWILIO_TIMEOUT,
        )

        if 200 <= response.status_code < 300:
            write_log("WhatsApp gonderildi", log_folder)
            return True

        write_log(
            f"Twilio WhatsApp hatasi: {response.status_code} {response.text}",
            log_folder,
        )
        return False
    except Exception as exc:
        log_exception_details(
            exc,
            context="Twilio WhatsApp gonderme hatasi",
            log_folder=log_folder,
        )
        return False


def _build_cloud_payload(
    event: DetectionEventLike,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build a Cloud API text message payload."""
    phone_number = _normalize_plain_phone(config["whatsapp"]["phone_number"])
    return {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": _build_text_message(event),
        },
    }


def _build_text_message(event: DetectionEventLike) -> str:
    """Create the WhatsApp notification text."""
    return (
        f"{APP_TITLE}\n"
        "Yeni insan algilandi.\n"
        f"Tarih: {event.date_text}\n"
        f"Saat: {event.time_text}\n"
        f"Kisi sayisi: {event.person_count}\n"
        f"Fotograf: {event.photo_name}\n"
        f"Dosya yolu: {event.photo_path}"
    )


def _load_requests() -> Any:
    """Import requests only when a WhatsApp message is being sent."""
    try:
        import requests
    except Exception as exc:
        raise RuntimeError(
            f"requests kutuphanesi yuklu degil veya import edilemedi: {exc}"
        ) from exc

    return requests


def _normalize_plain_phone(phone_number: str) -> str:
    """Return a Cloud API compatible phone number without plus sign."""
    return str(phone_number).strip().replace(" ", "").replace("+", "")


def _normalize_twilio_whatsapp_number(phone_number: str) -> str:
    """Return a Twilio WhatsApp channel address."""
    cleaned = str(phone_number).strip().replace(" ", "")
    if not cleaned:
        return ""

    if cleaned.startswith("whatsapp:"):
        return cleaned

    return f"whatsapp:{cleaned}"
