# NOTE PORT is passed into ReadStream from Main.py.

import serial #type: ignore
import threading
import datetime
import time
import os
from typing import Optional

from dependencies.consult_protocol import extract_first_consult_frame
from dependencies.consult_registers import DEFAULT_READ_PARAMETERS, build_stream_request, normalize_read_parameters
from dependencies.settings import Load_Config


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "configJSON.json")


def get_stream_value_for_code(
    code: int,
    reader: Optional[object],
    demo_value_map: dict[int, float],
    speed_correction: float,
    units_temp: object,
) -> float:
    if code == 0x0B:
        return float(demo_value_map.get(code, 0.0) * speed_correction) if reader is None else float(getattr(reader, "SPEED_Value", 0.0)) * speed_correction
    if code == 0x01:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "RPM_Value", 0.0))
    if code == 0x08:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "TEMP_Value", 0.0))
    if code == 0x0C:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "BATT_Value", 0.0))
    if code == 0x0D:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "TPS_Value", 0.0))
    if code == 0x03:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "MAF_Value", 0.0))
    if code == 0x09:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "INJ_Value", 0.0))
    if code == 0x16:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "TIM_Value", 0.0))
    if code == 0x17:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "AAC_Value", 0.0))

    if reader is None:
        return float(demo_value_map.get(code, 0.0))

    raw_values = getattr(reader, "register_values", {})
    raw_value = float(raw_values.get(code, 0.0))

    if code in {0x03, 0x04, 0x05, 0x06, 0x07, 0x12, 0x27, 0x29, 0x2F, 0x35, 0x36, 0x39}:
        return raw_value * 5.0 / 1000.0

    if code in {0x0A}:
        return raw_value * 10.0 / 1000.0

    if code in {0x0F, 0x11, 0x26}:
        temp_c = raw_value - 50.0
        if str(units_temp).upper() == "F":
            return (temp_c * 9.0 / 5.0) + 32.0
        return temp_c

    if code in {0x15}:
        msb = int(raw_values.get(0x14, 0)) & 0xFF
        lsb = int(raw_values.get(0x15, 0)) & 0xFF
        return float(((msb << 8) | lsb) / 100.0)

    if code in {0x23}:
        msb = int(raw_values.get(0x22, 0)) & 0xFF
        lsb = int(raw_values.get(0x23, 0)) & 0xFF
        return float(((msb << 8) | lsb) / 100.0)

    if code in {0x1A, 0x1B, 0x1C, 0x1D}:
        return raw_value

    if code in {0x28}:
        return raw_value / 2.0

    if code in {0x33}:
        return raw_value / 2.55

    if code in {0x38}:
        return raw_value

    return float(raw_values.get(code, 0.0))

class ReadStream(threading.Thread):
    def __init__(self, port, daemon, settings=None):
        threading.Thread.__init__(self)
        self.daemon = daemon
        self.port = port
        self._settings_lock = threading.Lock()

        self.RPM_Value = 0
        self.MAF_Value = 0
        self.MAF_RH_Value = 0
        self.TEMP_Value = 0
        self.O2_Value =0
        self.O2_RH_Value = 0
        self.SPEED_Value = 0
        self.BATT_Value = 0
        self.TPS_Value = 0
        self.FUELTEMP_Value = 0
        self.IAT_Value = 0
        self.EGT_Value = 0
        self.INJ_Value = 0  
        self.INJ_RH_Value = 0
        self.TIM_Value = 0
        self.AAC_Value = 0

        self.AFAlpha_Value = 0
        self.AFAlpha_RH_Value = 0
        self.AFAlpha_SL_Value = 0
        self.AFAlpha_RH_SL_Value = 0

        self.DIGITAL_13 = 0
        self.DIGITAL_1E = 0
        self.DIGITAL_1F = 0
        self.DIGITAL_21 = 0

        self.register_values: dict[int, int] = {}
        self._stream_buffer = bytearray()
        self._stream_started = False
        self._last_payload_time = time.monotonic()
        self._last_stream_command_time = 0.0

        initial_settings = settings if isinstance(settings, dict) else Load_Config(CONFIG_FILE)
        self.read_parameters = list(DEFAULT_READ_PARAMETERS)
        self._stream_needs_restart = True
        self.update_settings(initial_settings)
        
        self.start()

    def update_settings(self, settings_obj):
        """Update conversion settings at runtime from config JSON values."""
        source = settings_obj if isinstance(settings_obj, dict) else {}
        with self._settings_lock:
            self.settings = dict(source)
            self.units_speed = str(self.settings.get("Units_Speed", "MPH")).upper()
            self.units_temp = str(self.settings.get("Units_Temp", "F")).upper()
            new_read_parameters = normalize_read_parameters(
                self.settings.get("Read_Parameters", DEFAULT_READ_PARAMETERS),
            )
            if new_read_parameters != self.read_parameters:
                self.read_parameters = new_read_parameters
                self._stream_needs_restart = True
            self._stream_command = build_stream_request(self.read_parameters)

    def _reset_sensor_values(self) -> None:
        self.RPM_Value = 0
        self.MAF_Value = 0
        self.MAF_RH_Value = 0
        self.TEMP_Value = 0
        self.O2_Value =0
        self.O2_RH_Value = 0
        self.SPEED_Value = 0
        self.BATT_Value = 0
        self.TPS_Value = 0
        self.FUELTEMP_Value = 0
        self.IAT_Value = 0
        self.EGT_Value = 0
        self.INJ_Value = 0
        self.INJ_RH_Value = 0
        self.TIM_Value = 0
        self.AAC_Value = 0

        self.AFAlpha_Value = 0
        self.AFAlpha_RH_Value = 0
        self.AFAlpha_SL_Value = 0
        self.AFAlpha_RH_SL_Value = 0

        self.DIGITAL_13 = 0
        self.DIGITAL_1E = 0
        self.DIGITAL_1F = 0
        self.DIGITAL_21 = 0
        self.register_values = {}

    def _write_stream_command(self) -> bool:
        try:
            if hasattr(self.port, "reset_input_buffer"):
                self.port.reset_input_buffer()
            self.port.write(self._stream_command)
            return True
        except (serial.SerialException, OSError, ValueError):
            return False

    def _stop_stream_command(self) -> bool:
        try:
            self.port.write(bytes([0x30]))
            if hasattr(self.port, "reset_input_buffer"):
                self.port.reset_input_buffer()
            return True
        except (serial.SerialException, OSError, ValueError):
            return False

    def _read_next_payload(self) -> Optional[bytes]:
        try:
            if hasattr(self.port, "read_all"):
                chunk = self.port.read_all()
            else:
                chunk = self.port.read(max(1, self._current_frame_length()))
        except (serial.SerialException, OSError, ValueError):
            return None

        if chunk:
            self._stream_buffer.extend(chunk)

        payload = extract_first_consult_frame(bytes(self._stream_buffer))
        if payload is None:
            if len(self._stream_buffer) > 1024:
                del self._stream_buffer[:-256]
            return None

        buffer_bytes = bytes(self._stream_buffer)
        frame_start = buffer_bytes.find(b"\xFF")
        if frame_start >= 0:
            frame_end = frame_start + 2 + len(payload)
            del self._stream_buffer[:frame_end]
        else:
            self._stream_buffer.clear()

        return payload

    def _apply_register_value(self, register_code: int, raw_value: int) -> None:
        if register_code == 0x01:
            self.RPM_Value = int(self.convertToRev(int(raw_value)))

        elif register_code == 0x05:
            self.MAF_Value = self.convertToMAF(int(raw_value))
        elif register_code == 0x07:
            self.MAF_RH_Value = self.convertToMAF(int(raw_value))

        elif register_code == 0x08:
            self.TEMP_Value = self.convertToTemp(int(raw_value))

        elif register_code == 0x09:
            self.O2_Value = self.convertToO2(int(raw_value))
        elif register_code == 0x0A:
            self.O2_RH_Value = self.convertToO2(int(raw_value))

        elif register_code == 0x0B:
            self.SPEED_Value = self.convertToSpeed(int(raw_value))
        elif register_code == 0x0C:
            self.BATT_Value = self.convertToBattery(float(raw_value))
        elif register_code == 0x0D:
            self.TPS_Value = self.convertToTPS(float(raw_value))
        elif register_code == 0x0F:
            self.FUELTEMP_Value = self.convertToTemp(int(raw_value))
        elif register_code == 0x11:
            self.IAT_Value = self.convertToTemp(int(raw_value))
        elif register_code == 0x12:
            self.EGT_Value = self.convertToEGT(int(raw_value))
        elif register_code == 0x15:
            self.INJ_Value = self.convertToInjection(int(raw_value))
        elif register_code == 0x23:
            self.INJ_RH_Value = self.convertToInjection(int(raw_value))
        elif register_code == 0x16:
            self.TIM_Value = self.convertToTiming(int(raw_value))
        elif register_code == 0x17:
            self.AAC_Value = self.convertToAAC(int(raw_value))

        elif register_code == 0x1A:
            self.AFALpha_Value = float(raw_value)
        elif register_code == 0x1B:
            self.AFAlpha_RH_Value = float(raw_value)
        elif register_code == 0x1C:
            self.AFAlpha_SL_Value = float(raw_value)
        elif register_code == 0x1D:
            self.AFAlpha_RH_SL_Value = float(raw_value)

        elif register_code == 0x13:
            self.DIGITAL_13 = int(raw_value)
        elif register_code == 0x1E:
            self.DIGITAL_1E = int(raw_value)
        elif register_code == 0x1F:
            self.DIGITAL_1F = int(raw_value)
        elif register_code == 0x21:
            self.DIGITAL_21 = int(raw_value)
        else:
            self.register_values[register_code & 0xFF] = int(raw_value)

    def _current_frame_length(self) -> int:
        with self._settings_lock:
            return len(self.read_parameters) + 2
                
    def consume_data(self):
        read_thread = True
        while read_thread == True:
            if self._stream_needs_restart:
                if self._stream_started:
                    self._stop_stream_command()
                    time.sleep(0.01)
                if self._write_stream_command():
                    self._stream_needs_restart = False
                    self._stream_started = True
                    self._stream_buffer.clear()
                    self._last_stream_command_time = time.monotonic()
                    self._last_payload_time = self._last_stream_command_time
                else:
                    time.sleep(0.05)
                    continue

            incomingData = self._read_next_payload()
            if not incomingData:
                now = time.monotonic()
                no_payload_timeout = 0.75
                if (
                    self._stream_started
                    and not self._stream_needs_restart
                    and (now - self._last_payload_time) >= no_payload_timeout
                    and (now - self._last_stream_command_time) >= no_payload_timeout
                ):
                    self._stream_needs_restart = True
                    self._stream_started = False
                    self._stream_buffer.clear()
                time.sleep(0.002)
                continue

            dataList = list(incomingData)
            self._last_payload_time = time.monotonic()
                
            try:
                self._reset_sensor_values()

                with self._settings_lock:
                    active_parameters = list(self.read_parameters)

                for register_code, raw_value in zip(active_parameters, dataList):
                    self._apply_register_value(int(register_code), int(raw_value))

            except (ValueError, IndexError):
                pass
            time.sleep(0.002)
        return self.SPEED_Value, self.RPM_Value, self.TEMP_Value, self.BATT_Value, self.TPS_Value, self.MAF_Value, self.AAC_Value, self.INJ_Value, self.TIM_Value

    def run(self):
        self.consume_data()

    def convertToRev(self,inputData): # RPM
        return int(round((inputData * 12.5),2)) 

    def convertToMAF(self,inputData): # Volts
        return inputData * 5 / 1000
    
    def convertToTemp(self,inputData):
        with self._settings_lock:
            units_temp = self.units_temp
        if units_temp == 'F':
            return (inputData - 50) * 9/5 + 32
        return inputData - 50
    
    def convertToO2(self,inputData): # Volts
        return inputData * 10 / 1000

    def convertToSpeed(self,inputData):
        with self._settings_lock:
            units_speed = self.units_speed
        if units_speed == 'MPH':
            return int(round((inputData * 2.11) * 0.621371192237334))
        return int(round((inputData * 2.11)))

    def convertToBattery(self,inputData): # Volts
        return round(((inputData * 80) / 1000),1)
    
    def convertToTPS(self,inputData): # Volts
        return inputData * 20 / 1000

    def convertToEGT(self,inputData): # Degrees F
        return inputData * 20 / 1000

    def convertToAAC(self,inputData):  # % Duty Cycle
        return inputData / 2

    def convertToInjection(self,inputData): # % Duty Cycle
        return inputData / 100

    def convertToTiming(self,inputData): # Degrees BTDC
        return 110 - inputData