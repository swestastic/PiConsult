import datetime
from collections.abc import Iterable
from pathlib import Path
from typing import Optional, Union

# Use user's home directory for logs (always writable, no sudo needed)
_LOG_DIR = Path.home() / ".consult_box_logs"
_LOG_LEVELS = {"quiet": 0, "critical": 1, "verbose": 2}
_CURRENT_LOG_LEVEL = _LOG_LEVELS["critical"]


def _get_log_path(log_index: Union[int, str]) -> Optional[Path]:
    """Get the full path to the log file. Returns None if directory cannot be created."""
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        return _LOG_DIR / f"log_{log_index}.txt"
    except (OSError, PermissionError):
        # If we can't write to home dir, try /tmp
        try:
            tmp_log_dir = Path("/tmp/consult_box_logs")
            tmp_log_dir.mkdir(parents=True, exist_ok=True)
            return tmp_log_dir / f"log_{log_index}.txt"
        except (OSError, PermissionError):
            # Last resort: use current directory
            try:
                log_dir = Path("Logs")
                log_dir.mkdir(exist_ok=True)
                return log_dir / f"log_{log_index}.txt"
            except (OSError, PermissionError):
                return None


def normalize_log_level(level: object) -> str:
    value = str(level).strip().lower()
    if value in _LOG_LEVELS:
        return value
    return "critical"


def set_log_level(level: object) -> str:
    global _CURRENT_LOG_LEVEL
    normalized_level = normalize_log_level(level)
    _CURRENT_LOG_LEVEL = _LOG_LEVELS[normalized_level]
    return normalized_level


def get_log_level() -> str:
    for name, value in _LOG_LEVELS.items():
        if value == _CURRENT_LOG_LEVEL:
            return name
    return "critical"


def should_log(level: object) -> bool:
    normalized_level = normalize_log_level(level)
    return _LOG_LEVELS[normalized_level] <= _CURRENT_LOG_LEVEL


def create_log_file(log_index: Union[int, str], log_level: Optional[object] = None) -> str:
    """Create or initialize a log file. Returns the log path or empty string if logging fails."""
    log_path = _get_log_path(log_index)
    if log_path is None:
        print(f"Warning: Could not create log directory. Logging to console only.")
        return ""
    
    try:
        if not log_path.exists():
            log_path.write_text(
                f"Log file created on {datetime.datetime.now()}\n"
                f"Log Index: {log_index}\n"
                f"Log Level: {normalize_log_level(log_level) if log_level is not None else get_log_level()}\n",
                encoding="utf-8"
            )
        else:
            # Append to existing file
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"Session started: {datetime.datetime.now()}\n")
                if log_level is not None:
                    f.write(f"Log Level: {normalize_log_level(log_level)}\n")
        
        return str(log_path)
    except (OSError, PermissionError) as e:
        print(f"Warning: Could not write to log file: {e}")
        return ""


def log_message(log_index: Union[int, str], occurrence: object, message: object, *, level: object = "critical") -> None:
    """Write a structured log entry if the current level permits it."""
    if not should_log(level):
        return

    log_path = _get_log_path(log_index)
    if log_path is None:
        return

    try:
        timestamp = datetime.datetime.now().isoformat(timespec="seconds")
        normalized_level = normalize_log_level(level)
        entry = f"[{timestamp}] [{normalized_level}] {occurrence}: {message}\n"

        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(entry)
    except (OSError, PermissionError):
        pass


def write_log(log_index: Union[int, str], exception: object, occurrence: object, level: object = "critical") -> None:
    """Write an entry to the log file. Fails silently if logging is not possible."""
    log_message(log_index, occurrence, exception, level=level)


def log_command(
    log_index: Union[int, str],
    occurrence: object,
    command: object,
    *,
    level: object = "verbose",
    demo_mode: bool = False,
) -> None:
    if isinstance(command, (bytes, bytearray, memoryview)):
        payload = bytes(command)
    else:
        try:
            payload = bytes(int(value) & 0xFF for value in command)  # type: ignore[arg-type]
        except TypeError:
            payload = str(command).encode("utf-8", errors="replace")

    command_hex = " ".join(f"{byte:02X}" for byte in payload)
    if demo_mode:
        log_message(log_index, occurrence, f"DEMO MODE - NOT SENT: TX {command_hex}", level=level)
        return

    log_message(log_index, occurrence, f"TX {command_hex}", level=level)
