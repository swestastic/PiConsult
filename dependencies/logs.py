import os
import datetime
from pathlib import Path
from typing import Union, Optional

# Use user's home directory for logs (always writable, no sudo needed)
_LOG_DIR = Path.home() / ".consult_box_logs"
_LOG_PATH_CACHE = None


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


def Create_Log_File(Log_Index: Union[int, str]) -> str:
    """Create or initialize a log file. Returns the log path or empty string if logging fails."""
    log_path = _get_log_path(Log_Index)
    if log_path is None:
        print(f"Warning: Could not create log directory. Logging to console only.")
        return ""
    
    try:
        if not log_path.exists():
            log_path.write_text(
                f"Log file created on {datetime.datetime.now()}\n"
                f"Log Index: {Log_Index}\n",
                encoding="utf-8"
            )
        else:
            # Append to existing file
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"Session started: {datetime.datetime.now()}\n")
        
        return str(log_path)
    except (OSError, PermissionError) as e:
        print(f"Warning: Could not write to log file: {e}")
        return ""


def WriteLog(Log_Index: Union[int, str], exception: object, occurrence: object) -> None:
    """Write an entry to the log file. Fails silently if logging is not possible."""
    log_path = _get_log_path(Log_Index)
    if log_path is None:
        return
    
    try:
        timestamp = datetime.datetime.now().isoformat(timespec="seconds")
        message = f"[{timestamp}] {occurrence}: {exception}\n"
        
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(message)
    except (OSError, PermissionError):
        # Silently fail - don't crash the program due to logging errors
        pass
