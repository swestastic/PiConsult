import time

from dependencies.dtc_dict import dtc_codes as DTC_DICT

def Init_DTC(port):
    # DTC query followed by F0 begins the data stream.
    port.write(bytes([0xD1, 0xF0]))

def Parse_DTC(port):
    dtc_thread = True
    dtc_codes = []
    dtc_counts = []
    data_list = []

    while dtc_thread:
        # pyserial uses read_all(); keep a fallback for older code paths.
        read_all = getattr(port, "read_all", None)
        incoming_data = read_all() if callable(read_all) else port.readall()
        if isinstance(incoming_data, (bytes, bytearray)):
            data_list = list(incoming_data)

        if not data_list:
            time.sleep(0.01)
            continue

        try:
            for value in data_list:
                if value in DTC_DICT:
                    dtc_codes.append(value)
                else:
                    dtc_counts.append(value)
        except (ValueError, IndexError):
            print("DTC Error")

    return dtc_codes, dtc_counts