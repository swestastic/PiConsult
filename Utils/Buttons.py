import queue

# Global state shared across threads
button_event_queue = queue.Queue()
button_flags = {
    "peak": False,
    "peak_time": 0,
    "display": False,
    "select": False,
    "mode": False,
}

def button_listener():
    while True:
        if PeakButton.is_pressed:
            button_event_queue.put("peak")
            time.sleep(0.2)  # Debounce

        if DisplayButton.is_pressed:
            button_event_queue.put("display")
            time.sleep(0.2)  # Debounce

        if SelectButton.is_pressed:
            button_event_queue.put("select")
            time.sleep(0.2)  # Debounce

        if ModeButton.is_pressed:
            button_event_queue.put("mode")
            time.sleep(0.2)  # Debounce

        time.sleep(0.05)  # Polling rate

def process_buttons():
    # Call this from your main display/render loop
    global DisplayIndex, SettingIndex, ShowingPeak

    try:
        while not button_event_queue.empty():
            event = button_event_queue.get_nowait()
            if event == "peak":
                button_flags["peak"] = True
                button_flags["peak_time"] = time.time()
                ShowingPeak = True
            elif event == "display":
                Increment_Display()
            elif event == "select":
                Increment_Settings()
            elif event == "mode":
                pass  # Do what ModeButton is supposed to do

    except queue.Empty:
        pass

    # Reset Peak mode after 1.5s
    if ShowingPeak and (time.time() - button_flags["peak_time"] > 1.5):
        ShowingPeak = False