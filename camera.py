"""Camera, YOLO11 tracking and detection event handling for IABS."""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from settings import (
    APP_TITLE,
    NOTIFICATION_BOTH,
    NOTIFICATION_MAIL,
    NOTIFICATION_WHATSAPP,
    PERSON_CLASS_ID,
    ensure_directories,
    format_exception_details,
    log_exception_details,
    log_startup_environment,
    write_log,
)

try:
    import winsound
except ModuleNotFoundError:
    winsound = None


TEXT_SCALE_SMALL = 0.7
TEXT_SCALE_MEDIUM = 0.8
TEXT_SCALE_LARGE = 1.0
TEXT_THICKNESS_NORMAL = 2
TEXT_THICKNESS_BOLD = 3
BOX_THICKNESS = 2
QUIT_KEY = "q"
WINDOW_FLAGS = 0
FALLBACK_DETECTION_ID = -1
PHOTO_EXTENSION = ".jpg"
DEFAULT_FRAME_SKIP = 1
MAX_FRAME_SIZE = 640


@dataclass(frozen=True)
class DetectionEvent:
    """Data transferred to background workers after a new person is detected."""

    date_text: str
    time_text: str
    person_count: int
    photo_name: str
    photo_path: str
    notification_type: str


def start_camera(config: dict[str, Any]) -> None:
    """Run the YOLO11 camera loop and close resources cleanly on exit."""
    try:
        _run_camera(config)
    except Exception as exc:  # pragma: no cover - runtime path
        log_exception_details(
            exc,
            context="Kamera hatasi",
            log_folder=config["folders"]["logs"],
        )


def _run_camera(config: dict[str, Any]) -> None:
    """Open camera, track people with YOLO11 and dispatch detection events."""
    ensure_directories(config)
    log_folder = config["folders"]["logs"]
    log_startup_environment(config)
    write_log("Kamera aciliyor", log_folder)
    cv2, yolo_class = _load_vision_dependencies()

    camera_config = config["camera"]
    runtime_config = config["runtime"]
    write_log(
        f"Camera index: {camera_config['index']}; frame size: {camera_config['frame_width']}x{camera_config['frame_height']}",
        log_folder,
    )
    capture = cv2.VideoCapture(int(camera_config["index"]))
    if not capture.isOpened():
        raise RuntimeError(
            f"cv2.VideoCapture() failed for device index {camera_config['index']}"
        )
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(camera_config["frame_width"]))
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera_config["frame_height"]))

    if not capture.isOpened():
        raise RuntimeError(
            f"cv2.VideoCapture() could not open device index {camera_config['index']}"
        )

    model_path = Path(runtime_config.get("model_name", ""))
    write_log(f"Model path resolved: {model_path}", log_folder)
    model = yolo_class(str(runtime_config["model_name"]))
    window_name = APP_TITLE
    cv2.namedWindow(window_name, WINDOW_FLAGS)
    write_log("Kamera acildi", log_folder)

    color_map: dict[int, tuple[int, int, int]] = {}
    seen_track_ids: set[int] = set()
    last_count = 0
    last_fallback_event_time = 0.0
    previous_frame_time = time.time()
    frame_counter = 0

    while True:
        success, frame = capture.read()
        if not success:
            write_log("Kamera goruntusu alinamadi", log_folder)
            break

        frame = cv2.flip(frame, 1)
        frame_counter += 1
        frame_time = time.time()
        fps = _calculate_fps(previous_frame_time, frame_time)
        previous_frame_time = frame_time

        should_process = _should_process_frame(frame_counter, int(camera_config.get("frame_skip", DEFAULT_FRAME_SKIP)))
        if should_process:
            person_count, new_track_ids = _detect_people(
                cv2=cv2,
                model=model,
                frame=frame,
                config=config,
                color_map=color_map,
            )
        else:
            person_count = last_count
            new_track_ids = []

        _draw_overlay(
            cv2=cv2,
            frame=frame,
            config=config,
            fps=fps,
            person_count=person_count,
        )

        if new_track_ids:
            fresh_ids = [
                track_id
                for track_id in new_track_ids
                if track_id not in seen_track_ids
            ]
            if fresh_ids:
                seen_track_ids.update(fresh_ids)
                _handle_new_person(frame.copy(), person_count, config)
        elif _should_use_count_fallback(
            person_count=person_count,
            last_count=last_count,
            last_event_time=last_fallback_event_time,
            mail_delay_seconds=float(runtime_config["mail_delay_seconds"]),
        ):
            last_fallback_event_time = time.time()
            _handle_new_person(frame.copy(), person_count, config)

        last_count = person_count
        cv2.imshow(window_name, frame)

        if cv2.waitKey(1) & 0xFF == ord(QUIT_KEY):
            write_log("Kamera kullanici tarafindan kapatildi", log_folder)
            break

    capture.release()
    cv2.destroyAllWindows()
    write_log("Kamera kapatildi", log_folder)


def verify_vision_dependencies() -> None:
    """Raise a clear error if camera vision dependencies are missing."""
    try:
        import cv2  # noqa: F401
        from ultralytics import YOLO  # noqa: F401
    except Exception as exc:  # pragma: no cover - runtime path
        raise RuntimeError(
            f"Vision dependency import failed: {format_exception_details(exc)}"
        ) from exc


def _load_vision_dependencies() -> tuple[Any, Any]:
    """Import OpenCV and Ultralytics only when camera is started."""
    try:
        import cv2
        from ultralytics import YOLO
    except Exception as exc:  # pragma: no cover - runtime path
        raise RuntimeError(
            f"Vision dependency import failed: {format_exception_details(exc)}"
        ) from exc

    return cv2, YOLO


def _detect_people(
    cv2: Any,
    model: Any,
    frame: Any,
    config: dict[str, Any],
    color_map: dict[int, tuple[int, int, int]],
) -> tuple[int, list[int]]:
    """Detect and draw people, returning count and newly observed track IDs."""
    camera_config = config["camera"]
    runtime_config = config["runtime"]

    if frame.shape[0] > MAX_FRAME_SIZE or frame.shape[1] > MAX_FRAME_SIZE:
        resized_frame = cv2.resize(frame, (MAX_FRAME_SIZE, MAX_FRAME_SIZE))
    else:
        resized_frame = frame

    results = model.track(
        resized_frame,
        persist=True,
        tracker=str(runtime_config["tracker_name"]),
        classes=[PERSON_CLASS_ID],
        conf=float(camera_config["confidence"]),
        imgsz=int(camera_config.get("image_size", 320)),
        verbose=False,
    )

    person_count = 0
    current_track_ids: list[int] = []

    if not results or results[0].boxes is None:
        return person_count, current_track_ids

    for index, box in enumerate(results[0].boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        box_width = x2 - x1
        box_height = y2 - y1

        if (
            box_width < int(camera_config["minimum_box_width"])
            or box_height < int(camera_config["minimum_box_height"])
        ):
            continue

        person_count += 1
        track_id = _extract_track_id(box, index)
        current_track_ids.append(track_id)
        color = _get_box_color(track_id, color_map)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, BOX_THICKNESS)

    return person_count, current_track_ids


def _should_process_frame(frame_counter: int, frame_skip: int) -> bool:
    """Return whether the current frame should run inference."""
    if frame_skip <= 0:
        return True
    return frame_counter % (frame_skip + 1) == 0


def _extract_track_id(box: Any, fallback_index: int) -> int:
    """Read a ByteTrack object ID from a YOLO box with a stable fallback."""
    if getattr(box, "id", None) is None:
        return FALLBACK_DETECTION_ID - fallback_index

    try:
        return int(box.id[0])
    except (TypeError, ValueError, IndexError):
        return FALLBACK_DETECTION_ID - fallback_index


def _get_box_color(
    track_id: int,
    color_map: dict[int, tuple[int, int, int]],
) -> tuple[int, int, int]:
    """Return a persistent random color for each tracked person."""
    if track_id not in color_map:
        color_map[track_id] = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
        )
    return color_map[track_id]


def _draw_overlay(
    cv2: Any,
    frame: Any,
    config: dict[str, Any],
    fps: float,
    person_count: int,
) -> None:
    """Draw FPS, date-time and person count according to settings."""
    camera_config = config["camera"]
    y_position = 30

    if bool(camera_config["show_fps"]):
        cv2.putText(
            frame,
            f"FPS: {fps:.1f}",
            (10, y_position),
            cv2.FONT_HERSHEY_SIMPLEX,
            TEXT_SCALE_SMALL,
            (255, 255, 0),
            TEXT_THICKNESS_NORMAL,
        )
        y_position += 40

    if bool(camera_config["show_person_count"]):
        cv2.putText(
            frame,
            f"Insan: {person_count}",
            (10, y_position),
            cv2.FONT_HERSHEY_SIMPLEX,
            TEXT_SCALE_LARGE,
            (0, 255, 255),
            TEXT_THICKNESS_BOLD,
        )
        y_position += 40

    if bool(camera_config["show_datetime"]):
        cv2.putText(
            frame,
            datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            (10, y_position),
            cv2.FONT_HERSHEY_SIMPLEX,
            TEXT_SCALE_MEDIUM,
            (255, 255, 255),
            TEXT_THICKNESS_NORMAL,
        )


def _should_use_count_fallback(
    person_count: int,
    last_count: int,
    last_event_time: float,
    mail_delay_seconds: float,
) -> bool:
    """Return true when count-based triggering should replace missing IDs."""
    if person_count <= 0:
        return False

    count_increased = person_count > last_count
    delay_finished = time.time() - last_event_time > mail_delay_seconds
    return count_increased and delay_finished


def _calculate_fps(previous_frame_time: float, current_frame_time: float) -> float:
    """Calculate frames per second while avoiding division by zero."""
    elapsed = current_frame_time - previous_frame_time
    if elapsed <= 0:
        return 0.0
    return 1.0 / elapsed


def _handle_new_person(
    frame: Any,
    person_count: int,
    config: dict[str, Any],
) -> None:
    """Start background work for a newly detected person."""
    event = _create_detection_event(person_count, config)
    write_log("Yeni kisi algilandi", config["folders"]["logs"])

    worker = threading.Thread(
        target=_process_detection_event,
        args=(frame, event, config),
        daemon=True,
    )
    worker.start()


def _create_detection_event(
    person_count: int,
    config: dict[str, Any],
) -> DetectionEvent:
    """Create filenames and metadata for a detection event."""
    now = datetime.now()
    photo_name = f"{now:%Y-%m-%d_%H-%M-%S}{PHOTO_EXTENSION}"
    photo_path = str(Path(config["folders"]["photos"]) / photo_name)

    return DetectionEvent(
        date_text=now.strftime("%Y-%m-%d"),
        time_text=now.strftime("%H:%M:%S"),
        person_count=person_count,
        photo_name=photo_name,
        photo_path=photo_path,
        notification_type=str(config["notification"]["type"]),
    )


def _process_detection_event(
    frame: Any,
    event: DetectionEvent,
    config: dict[str, Any],
) -> None:
    """Save the photo, play alarm and dispatch slow work in background."""
    try:
        _play_alarm(config)
        _save_photo(frame, event.photo_path, config)
        _start_background_tasks(event, config)
    except Exception as exc:  # pragma: no cover - runtime path
        log_exception_details(
            exc,
            context="Algilama olayi islenemedi",
            log_folder=config["folders"]["logs"],
        )


def _save_photo(frame: Any, photo_path: str, config: dict[str, Any]) -> None:
    """Write a detection frame to the selected photo folder."""
    cv2, _ = _load_vision_dependencies()
    path = Path(photo_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    saved = cv2.imwrite(str(path), frame)

    if saved:
        write_log(f"Fotograf kaydedildi: {path.name}", config["folders"]["logs"])
    else:
        write_log(f"Fotograf kaydedilemedi: {path}", config["folders"]["logs"])


def _play_alarm(config: dict[str, Any]) -> None:
    """Play the Windows alarm sound when enabled in settings."""
    alarm_config = config["alarm"]
    if not bool(alarm_config["enabled"]):
        return

    if winsound is None:
        write_log("Alarm calinamadi: winsound bulunamadi", config["folders"]["logs"])
        return

    try:
        winsound.Beep(
            int(alarm_config["frequency"]),
            int(alarm_config["duration_ms"]),
        )
    except Exception as exc:  # pragma: no cover - runtime path
        log_exception_details(
            exc,
            context="Alarm calinamadi",
            log_folder=config["folders"]["logs"],
        )


def _start_background_tasks(
    event: DetectionEvent,
    config: dict[str, Any],
) -> None:
    """Launch notification, Excel and log actions without blocking camera."""
    task_threads = [
        threading.Thread(
            target=_write_excel_event,
            args=(event, config),
            daemon=True,
        ),
        threading.Thread(
            target=_write_detection_log,
            args=(event, config),
            daemon=True,
        ),
    ]

    notification_type = event.notification_type
    if notification_type in (NOTIFICATION_MAIL, NOTIFICATION_BOTH):
        task_threads.append(
            threading.Thread(
                target=_send_mail_event,
                args=(event, config),
                daemon=True,
            )
        )

    if notification_type in (NOTIFICATION_WHATSAPP, NOTIFICATION_BOTH):
        task_threads.append(
            threading.Thread(
                target=_send_whatsapp_event,
                args=(event, config),
                daemon=True,
            )
        )

    for task_thread in task_threads:
        task_thread.start()


def _send_mail_event(event: DetectionEvent, config: dict[str, Any]) -> None:
    """Send a mail notification through the mail module when available."""
    try:
        from mail_sender import send_detection_mail

        send_detection_mail(event, config)
    except Exception as exc:  # pragma: no cover - runtime path
        log_exception_details(
            exc,
            context="Mail gonderme hatasi",
            log_folder=config["folders"]["logs"],
        )


def _send_whatsapp_event(event: DetectionEvent, config: dict[str, Any]) -> None:
    """Send a WhatsApp notification through the WhatsApp module when available."""
    try:
        from whatsapp_sender import send_detection_whatsapp

        send_detection_whatsapp(event, config)
    except Exception as exc:  # pragma: no cover - runtime path
        log_exception_details(
            exc,
            context="WhatsApp gonderme hatasi",
            log_folder=config["folders"]["logs"],
        )


def _write_excel_event(event: DetectionEvent, config: dict[str, Any]) -> None:
    """Write a detection row through the Excel module when available."""
    try:
        from excel_logger import write_detection_row

        write_detection_row(event, config)
    except Exception as exc:  # pragma: no cover - runtime path
        log_exception_details(
            exc,
            context="Excel yazma hatasi",
            log_folder=config["folders"]["logs"],
        )


def _write_detection_log(event: DetectionEvent, config: dict[str, Any]) -> None:
    """Write detailed detection information to the log file."""
    write_log(
        (
            "Algilama kaydi: "
            f"tarih={event.date_text}, "
            f"saat={event.time_text}, "
            f"kisi_sayisi={event.person_count}, "
            f"fotograf={event.photo_name}, "
            f"bildirim={event.notification_type}"
        ),
        config["folders"]["logs"],
    )
