from pathlib import Path

from ..config import Settings


def evaluation_frame_path(settings: Settings, session_id: str, evaluation_id: str) -> Path:
    return Path(settings.evaluation_frames_dir) / session_id / f"{evaluation_id}.jpg"


def save_evaluation_frame(settings: Settings, session_id: str, evaluation_id: str, image: bytes) -> Path:
    destination = evaluation_frame_path(settings, session_id, evaluation_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_bytes(image)
    temporary.replace(destination)
    return destination
