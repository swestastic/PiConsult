import queue
from typing import Any, Callable, Optional

import serial


button_event_queue: queue.Queue[str] = queue.Queue()


def setup_button_callbacks(mode_button: Any, select_button: Any, up_button: Any, down_button: Any) -> None:
    """Attach press handlers that enqueue button events."""

    def make_callback(name: str) -> Callable[[], None]:
        def callback() -> None:
            button_event_queue.put(name)

        return callback

    mode_button.when_pressed = make_callback("mode")
    select_button.when_pressed = make_callback("select")
    up_button.when_pressed = make_callback("up")
    down_button.when_pressed = make_callback("down")


def process_buttons(
    state: Any,
    port_obj: Optional[serial.Serial],
    demo_mode: bool,
    display_text: list[str],
    setting_text: list[str],
    active_test_items: list[str],
    digital_register_order: list[int],
    settings_adjustable_indexes: set[int],
    display_mode: int,
    dtc_mode: int,
    settings_mode: int,
    active_test_mode: int,
    digital_bits_mode: int,
    mode_menu_mode: int,
    mode_menu_targets: list[int],
    mode_count: int,
    show_peak_fn: Callable[[int], None],
    adjust_setting_value_fn: Callable[[int, int], None],
    adjust_active_test_value_fn: Callable[[int, Optional[serial.Serial], bool, Any, Callable[[Optional[serial.Serial], int, int, bool], bool], Callable[[object], str]], None],
    run_active_test_action_fn: Callable[[Optional[serial.Serial], bool, Any, Callable[[Optional[serial.Serial], int, int, bool], bool]], None],
    update_dtc_codes_from_ecu_fn: Callable[[Any, Optional[serial.Serial], bool, Callable[[serial.Serial], list[int]]], None],
    clear_dtc_codes_fn: Callable[[Optional[serial.Serial], bool], bool],
    send_activation_command_fn: Callable[[Optional[serial.Serial], int, int, bool], bool],
    temp_unit_label_fn: Callable[[object], str],
    read_dtc_codes_fn: Callable[[serial.Serial], list[int]],
    on_speed_units_toggle_fn: Callable[[], None],
    on_temp_units_toggle_fn: Callable[[], None],
    on_default_display_cycle_fn: Callable[[], None],
    on_gauge_display_mode_toggle_fn: Callable[[], None],
) -> None:
    """Process queued button presses and update app state."""
    import time

    while not button_event_queue.empty():
        event = button_event_queue.get_nowait()

        if event == "mode":
            with state.acquire_lock():
                current_mode = state.current_mode
                if current_mode in mode_menu_targets:
                    state.mode_menu_index = mode_menu_targets.index(current_mode)
                state.current_mode = mode_menu_mode
                state.dtc_clear_confirm_active = False
                state.active_test_editing = False
                state.active_test_in_test = False
                state.setting_in_item = False
                state.setting_info_view = False
                state.setting_editing = False

        elif event == "up":
            with state.acquire_lock():
                current_mode = state.current_mode

            if current_mode == display_mode:
                with state.acquire_lock():
                    state.display_index = (state.display_index - 1) % len(display_text)
            elif current_mode == dtc_mode:
                with state.acquire_lock():
                    if state.dtc_clear_confirm_active:
                        state.dtc_clear_confirm_yes = not state.dtc_clear_confirm_yes
                    else:
                        state.dtc_index = (state.dtc_index - 1) % max(len(state.dtc_codes), 1)
            elif current_mode == settings_mode:
                with state.acquire_lock():
                    setting_index = state.setting_index
                    setting_editing = state.setting_editing
                    setting_info_view = state.setting_info_view

                if setting_info_view:
                    pass
                elif setting_editing and setting_index in settings_adjustable_indexes:
                    adjust_setting_value_fn(setting_index, -1)
                else:
                    with state.acquire_lock():
                        state.setting_index = (state.setting_index - 1) % len(setting_text)
                        state.setting_editing = False
            elif current_mode == active_test_mode:
                with state.acquire_lock():
                    if state.active_test_in_test:
                        active_idx = state.active_test_index
                        if state.active_test_editing and active_idx == 4:
                            state.active_test_power_balance_cursor = (state.active_test_power_balance_cursor - 1) % 9
                            should_adjust = False
                        elif state.active_test_editing:
                            should_adjust = True
                        else:
                            state.active_test_index = (state.active_test_index - 1) % len(active_test_items)
                            should_adjust = False
                    elif state.active_test_editing:
                        active_idx = state.active_test_index
                        if active_idx == 4:
                            state.active_test_power_balance_cursor = (state.active_test_power_balance_cursor - 1) % 9
                            should_adjust = False
                        else:
                            should_adjust = True
                    else:
                        state.active_test_index = (state.active_test_index - 1) % len(active_test_items)
                        should_adjust = False

                if should_adjust:
                    adjust_active_test_value_fn(-1, port_obj, demo_mode, state, send_activation_command_fn, temp_unit_label_fn)
            elif current_mode == digital_bits_mode:
                with state.acquire_lock():
                    state.digital_page_index = (state.digital_page_index - 1) % len(digital_register_order)
            elif current_mode == mode_menu_mode:
                with state.acquire_lock():
                    state.mode_menu_index = (state.mode_menu_index - 1) % len(mode_menu_targets)

        elif event == "down":
            with state.acquire_lock():
                current_mode = state.current_mode

            if current_mode == display_mode:
                with state.acquire_lock():
                    state.display_index = (state.display_index + 1) % len(display_text)
            elif current_mode == dtc_mode:
                with state.acquire_lock():
                    if state.dtc_clear_confirm_active:
                        state.dtc_clear_confirm_yes = not state.dtc_clear_confirm_yes
                    else:
                        state.dtc_index = (state.dtc_index + 1) % max(len(state.dtc_codes), 1)
            elif current_mode == settings_mode:
                with state.acquire_lock():
                    setting_index = state.setting_index
                    setting_editing = state.setting_editing
                    setting_info_view = state.setting_info_view

                if setting_info_view:
                    pass
                elif setting_editing and setting_index in settings_adjustable_indexes:
                    adjust_setting_value_fn(setting_index, 1)
                else:
                    with state.acquire_lock():
                        state.setting_index = (state.setting_index + 1) % len(setting_text)
                        state.setting_editing = False
            elif current_mode == active_test_mode:
                with state.acquire_lock():
                    if state.active_test_in_test:
                        active_idx = state.active_test_index
                        if state.active_test_editing and active_idx == 4:
                            state.active_test_power_balance_cursor = (state.active_test_power_balance_cursor + 1) % 9
                            should_adjust = False
                        elif state.active_test_editing:
                            should_adjust = True
                        else:
                            state.active_test_index = (state.active_test_index + 1) % len(active_test_items)
                            should_adjust = False
                    elif state.active_test_editing:
                        active_idx = state.active_test_index
                        if active_idx == 4:
                            state.active_test_power_balance_cursor = (state.active_test_power_balance_cursor + 1) % 9
                            should_adjust = False
                        else:
                            should_adjust = True
                    else:
                        state.active_test_index = (state.active_test_index + 1) % len(active_test_items)
                        should_adjust = False

                if should_adjust:
                    adjust_active_test_value_fn(1, port_obj, demo_mode, state, send_activation_command_fn, temp_unit_label_fn)
            elif current_mode == digital_bits_mode:
                with state.acquire_lock():
                    state.digital_page_index = (state.digital_page_index + 1) % len(digital_register_order)
            elif current_mode == mode_menu_mode:
                with state.acquire_lock():
                    state.mode_menu_index = (state.mode_menu_index + 1) % len(mode_menu_targets)

        elif event == "select":
            with state.acquire_lock():
                current_mode = state.current_mode
                showing_peak = state.showing_peak
                setting_index = state.setting_index
                display_index = state.display_index

            if current_mode == display_mode:
                if not showing_peak:
                    show_peak_fn(display_index)
            elif current_mode == dtc_mode:
                with state.acquire_lock():
                    confirm_active = state.dtc_clear_confirm_active
                    confirm_yes = state.dtc_clear_confirm_yes

                if not confirm_active:
                    with state.acquire_lock():
                        state.dtc_clear_confirm_active = True
                        state.dtc_clear_confirm_yes = False
                else:
                    with state.acquire_lock():
                        state.dtc_clear_confirm_active = False

                    if confirm_yes:
                        clear_ok = clear_dtc_codes_fn(port_obj, demo_mode=demo_mode)
                        if clear_ok:
                            update_dtc_codes_from_ecu_fn(state, port_obj, demo_mode, read_dtc_codes_fn)
                        with state.acquire_lock():
                            state.dtc_status_message = "Cleared" if clear_ok else "Clear Failed"
                            state.dtc_status_until = time.monotonic() + 1.5
            elif current_mode == settings_mode:
                with state.acquire_lock():
                    setting_editing = state.setting_editing
                    setting_info_view = state.setting_info_view

                if setting_info_view:
                    with state.acquire_lock():
                        state.setting_info_view = False
                elif setting_index in settings_adjustable_indexes:
                    with state.acquire_lock():
                        state.setting_editing = not state.setting_editing
                elif setting_index == 0:
                    on_speed_units_toggle_fn()
                elif setting_index == 1:
                    on_temp_units_toggle_fn()
                elif setting_text[setting_index] == "Gauge Display Mode":
                    on_gauge_display_mode_toggle_fn()
                elif setting_text[setting_index] == "Default Display":
                    on_default_display_cycle_fn()
                elif setting_text[setting_index] == "Info":
                    with state.acquire_lock():
                        state.setting_info_view = True
                        state.setting_editing = False
            elif current_mode == active_test_mode:
                with state.acquire_lock():
                    in_test = state.active_test_in_test
                    active_idx = state.active_test_index

                if not in_test:
                    if active_idx == 4:
                        with state.acquire_lock():
                            state.active_test_in_test = True
                            state.active_test_editing = True
                            selected_cylinders = set(state.active_test_power_balance_cylinders_off)
                            state.active_test_power_balance_cursor = min(selected_cylinders) if selected_cylinders else 0
                    elif active_idx in {0, 1, 2, 3, 5}:
                        with state.acquire_lock():
                            state.active_test_editing = not state.active_test_editing
                    else:
                        run_active_test_action_fn(port_obj, demo_mode, state, send_activation_command_fn)
                else:
                    run_active_test_action_fn(port_obj, demo_mode, state, send_activation_command_fn)
            elif current_mode == digital_bits_mode:
                with state.acquire_lock():
                    state.digital_page_index = (state.digital_page_index + 1) % len(digital_register_order)
            elif current_mode == mode_menu_mode:
                with state.acquire_lock():
                    selected_mode = mode_menu_targets[state.mode_menu_index]
                    state.current_mode = selected_mode
                    if selected_mode == active_test_mode:
                        state.active_test_in_test = False
                        state.active_test_editing = False
                    if selected_mode == settings_mode:
                        state.setting_in_item = False
                        state.setting_info_view = False
                        state.setting_editing = False

                if selected_mode == dtc_mode:
                    update_dtc_codes_from_ecu_fn(state, port_obj, demo_mode, read_dtc_codes_fn)