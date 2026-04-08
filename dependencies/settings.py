import json
import os


def _resolve_config_path(file_path):
    # Normalize and sanitize mixed path inputs (quoted, whitespace padded, PathLike).
    raw_path = os.fspath(file_path) if file_path is not None else ""
    raw_path = raw_path.strip().strip('"').strip("'")
    expanded_path = os.path.expanduser(raw_path)
    return os.path.abspath(os.path.normpath(expanded_path))

# Load settings from the config file
def Load_Config(FILE):
    resolved_file = _resolve_config_path(FILE)
    try:
        with open(resolved_file, 'r', encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        print("Config file not found, using default settings")
        # Default settings if config file doesn't exist
        return {

            "Units_Speed": "MPH",
            "Units_Temp": "F",
            "Speed_Correction": 1.0,
            "Gauge_Display_Mode": "Gauge + Value",

            "Default_Display": 0,

            "Coolant_Warning": 200,

            "RPM_Warning": 7000,

            "Read_Parameters": [0x0B, 0x01, 0x08, 0x0C, 0x0D, 0x05, 0x09, 0x13, 0x16, 0x17, 0x1A, 0x1C, 0x1E, 0x1F, 0x21],

            "Log_Index": 0
        }

# Save settings to the config file
def Save_Config(FILE,settings):
    resolved_file = _resolve_config_path(FILE)
    parent_dir = os.path.dirname(resolved_file)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    try:
        with open(resolved_file, 'w', encoding='utf-8') as file:
            json.dump(settings, file)
        return
    except OSError:
        # Fallback to local dependencies path when the primary path is invalid for the active runtime.
        fallback_file = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.basename(resolved_file)))
        if fallback_file == resolved_file:
            raise
        fallback_parent = os.path.dirname(fallback_file)
        if fallback_parent:
            os.makedirs(fallback_parent, exist_ok=True)
        with open(fallback_file, 'w', encoding='utf-8') as file:
            json.dump(settings, file)