import queue
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import serial


button_event_queue: queue.Queue[str] = queue.Queue()


@dataclass(frozen=True)
class ButtonContext:
	selected_display_indices: list[int]
	setting_text: list[str]
	read_parameter_codes: list[int]
	active_test_items: list[str]
	selected_digital_registers: list[int]
	settings_adjustable_indexes: set[int]
	display_mode: int
	dtc_mode: int
	settings_mode: int
	active_test_mode: int
	digital_bits_mode: int
	mode_menu_mode: int
	mode_menu_targets: list[int]
	show_peak_fn: Callable[[int], None]
	adjust_setting_value_fn: Callable[[int, int], None]
	adjust_active_test_value_fn: Callable[[int, Optional[serial.Serial], bool, Any, Callable[[Optional[serial.Serial], int, int, bool], bool], Callable[[object], str]], None]
	run_active_test_action_fn: Callable[[Optional[serial.Serial], bool, Any, Callable[[Optional[serial.Serial], int, int, bool], bool]], None]
	update_dtc_codes_from_ecu_fn: Callable[[Any, Optional[serial.Serial], bool, Callable[[serial.Serial], list[int]]], None]
	clear_dtc_codes_fn: Callable[[Optional[serial.Serial], bool], bool]
	send_activation_command_fn: Callable[[Optional[serial.Serial], int, int, bool], bool]
	temp_unit_label_fn: Callable[[object], str]
	read_dtc_codes_fn: Callable[[serial.Serial], list[int]]
	on_speed_units_toggle_fn: Callable[[], None]
	on_temp_units_toggle_fn: Callable[[], None]
	on_default_display_cycle_fn: Callable[[], None]
	on_gauge_display_mode_toggle_fn: Callable[[], None]
	on_log_level_toggle_fn: Callable[[], None]
	on_read_parameter_toggle_fn: Callable[[int], None]
	on_read_parameters_finalize_fn: Callable[[], None]


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


def _handle_mode_event(state: Any, ctx: ButtonContext) -> None:
	finalize_read_parameters = False
	with state.acquire_lock():
		current_mode = state.current_mode
		setting_in_item = state.setting_in_item
		if current_mode in ctx.mode_menu_targets:
			state.mode_menu_index = ctx.mode_menu_targets.index(current_mode)
		if current_mode == ctx.settings_mode and (setting_in_item or state.setting_info_view):
			if setting_in_item:
				finalize_read_parameters = True
			state.setting_in_item = False
			state.setting_info_view = False
			state.setting_editing = False
		else:
			state.current_mode = ctx.mode_menu_mode
			state.dtc_clear_confirm_active = False
			state.active_test_editing = False
			state.active_test_in_test = False
			state.setting_in_item = False
			state.setting_info_view = False
			state.setting_editing = False
	if finalize_read_parameters:
		ctx.on_read_parameters_finalize_fn()


def _handle_active_test_nav(
	state: Any,
	ctx: ButtonContext,
	nav_delta: int,
	port_obj: Optional[serial.Serial],
	demo_mode: bool,
) -> None:
	should_adjust = False
	with state.acquire_lock():
		if state.active_test_in_test:
			active_idx = state.active_test_index
			if state.active_test_editing and active_idx == 4:
				state.active_test_power_balance_cursor = (state.active_test_power_balance_cursor + nav_delta) % 9
			elif state.active_test_editing:
				should_adjust = True
			else:
				state.active_test_index = (state.active_test_index + nav_delta) % len(ctx.active_test_items)
		elif state.active_test_editing:
			active_idx = state.active_test_index
			if active_idx == 4:
				state.active_test_power_balance_cursor = (state.active_test_power_balance_cursor + nav_delta) % 9
			else:
				should_adjust = True
		else:
			state.active_test_index = (state.active_test_index + nav_delta) % len(ctx.active_test_items)

	if should_adjust:
		ctx.adjust_active_test_value_fn(
			-nav_delta,
			port_obj,
			demo_mode,
			state,
			ctx.send_activation_command_fn,
			ctx.temp_unit_label_fn,
		)


def _handle_vertical_nav(
	state: Any,
	ctx: ButtonContext,
	nav_delta: int,
	port_obj: Optional[serial.Serial],
	demo_mode: bool,
) -> None:
	with state.acquire_lock():
		current_mode = state.current_mode

	if current_mode == ctx.display_mode:
		if ctx.selected_display_indices:
			with state.acquire_lock():
				state.display_index = (state.display_index + nav_delta) % len(ctx.selected_display_indices)
		return

	if current_mode == ctx.dtc_mode:
		with state.acquire_lock():
			if state.dtc_clear_confirm_active:
				state.dtc_clear_confirm_yes = not state.dtc_clear_confirm_yes
			else:
				state.dtc_index = (state.dtc_index - nav_delta) % max(len(state.dtc_codes), 1)
		return

	if current_mode == ctx.settings_mode:
		with state.acquire_lock():
			setting_index = state.setting_index
			setting_editing = state.setting_editing
			setting_info_view = state.setting_info_view
			setting_in_item = state.setting_in_item

		if setting_info_view:
			return
		if setting_in_item:
			if ctx.read_parameter_codes:
				with state.acquire_lock():
					state.read_parameter_index = (state.read_parameter_index + nav_delta) % len(ctx.read_parameter_codes)
			return
		if setting_editing and setting_index in ctx.settings_adjustable_indexes:
			ctx.adjust_setting_value_fn(setting_index, -nav_delta)
			return

		with state.acquire_lock():
			state.setting_index = (state.setting_index + nav_delta) % len(ctx.setting_text)
			state.setting_editing = False
		return

	if current_mode == ctx.active_test_mode:
		_handle_active_test_nav(state, ctx, nav_delta, port_obj, demo_mode)
		return

	if current_mode == ctx.digital_bits_mode:
		if ctx.selected_digital_registers:
			with state.acquire_lock():
				state.digital_page_index = (state.digital_page_index - nav_delta) % len(ctx.selected_digital_registers)
		return

	if current_mode == ctx.mode_menu_mode:
		with state.acquire_lock():
			state.mode_menu_index = (state.mode_menu_index + nav_delta) % len(ctx.mode_menu_targets)


def _handle_select_event(
	state: Any,
	ctx: ButtonContext,
	port_obj: Optional[serial.Serial],
	demo_mode: bool,
) -> None:
	with state.acquire_lock():
		current_mode = state.current_mode
		showing_peak = state.showing_peak
		setting_index = state.setting_index
		display_index = state.display_index

	if current_mode == ctx.display_mode:
		if not showing_peak and ctx.selected_display_indices:
			ctx.show_peak_fn(display_index)
		return

	if current_mode == ctx.dtc_mode:
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
				clear_ok = ctx.clear_dtc_codes_fn(port_obj, demo_mode)
				if clear_ok:
					ctx.update_dtc_codes_from_ecu_fn(state, port_obj, demo_mode, ctx.read_dtc_codes_fn)
				with state.acquire_lock():
					state.dtc_status_message = "Cleared" if clear_ok else "Clear Failed"
					state.dtc_status_until = time.monotonic() + 1.5
		return

	if current_mode == ctx.settings_mode:
		with state.acquire_lock():
			setting_info_view = state.setting_info_view
			setting_in_item = state.setting_in_item
			setting_editing = state.setting_editing
			setting_index = state.setting_index

		if setting_info_view:
			with state.acquire_lock():
				state.setting_info_view = False
			return
		if setting_in_item:
			if ctx.read_parameter_codes:
				with state.acquire_lock():
					current_index = state.read_parameter_index % len(ctx.read_parameter_codes)
				ctx.on_read_parameter_toggle_fn(current_index)
			return
		if setting_index in ctx.settings_adjustable_indexes:
			with state.acquire_lock():
				state.setting_editing = not setting_editing
			return
		if setting_index == 0:
			ctx.on_speed_units_toggle_fn()
			return
		if setting_index == 1:
			ctx.on_temp_units_toggle_fn()
			return
		if ctx.setting_text[setting_index] == "Gauge Display Mode":
			ctx.on_gauge_display_mode_toggle_fn()
			return
		if ctx.setting_text[setting_index] == "Log Level":
			ctx.on_log_level_toggle_fn()
			return
		if ctx.setting_text[setting_index] == "Default Display":
			ctx.on_default_display_cycle_fn()
			return
		if ctx.setting_text[setting_index] == "Read Parameters":
			with state.acquire_lock():
				state.setting_in_item = True
				state.setting_editing = False
				state.read_parameter_index = 0
			return
		if ctx.setting_text[setting_index] == "Info":
			with state.acquire_lock():
				state.setting_info_view = True
				state.setting_editing = False
			return

	if current_mode == ctx.active_test_mode:
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
				ctx.run_active_test_action_fn(port_obj, demo_mode, state, ctx.send_activation_command_fn)
		else:
			ctx.run_active_test_action_fn(port_obj, demo_mode, state, ctx.send_activation_command_fn)
		return

	if current_mode == ctx.digital_bits_mode:
		if ctx.selected_digital_registers:
			with state.acquire_lock():
				state.digital_page_index = (state.digital_page_index + 1) % len(ctx.selected_digital_registers)
		return

	if current_mode == ctx.mode_menu_mode:
		selected_mode = None
		with state.acquire_lock():
			selected_mode = ctx.mode_menu_targets[state.mode_menu_index]
			can_open_display = bool(ctx.selected_display_indices)
			can_open_digital = bool(ctx.selected_digital_registers)
			if selected_mode == ctx.display_mode and not can_open_display:
				return
			if selected_mode == ctx.digital_bits_mode and not can_open_digital:
				return
			state.current_mode = selected_mode
			if selected_mode == ctx.active_test_mode:
				state.active_test_in_test = False
				state.active_test_editing = False
			if selected_mode == ctx.settings_mode:
				state.setting_in_item = False
				state.setting_info_view = False
				state.setting_editing = False

		if selected_mode == ctx.dtc_mode:
			ctx.update_dtc_codes_from_ecu_fn(state, port_obj, demo_mode, ctx.read_dtc_codes_fn)


def process_buttons(
	state: Any,
	port_obj: Optional[serial.Serial],
	demo_mode: bool,
	ctx: ButtonContext,
) -> None:
	"""Process queued button presses and update app state."""

	while not button_event_queue.empty():
		event = button_event_queue.get_nowait()
		if event == "mode":
			_handle_mode_event(state, ctx)
		elif event == "up":
			_handle_vertical_nav(state, ctx, nav_delta=-1, port_obj=port_obj, demo_mode=demo_mode)
		elif event == "down":
			_handle_vertical_nav(state, ctx, nav_delta=1, port_obj=port_obj, demo_mode=demo_mode)
		elif event == "select":
			_handle_select_event(state, ctx, port_obj=port_obj, demo_mode=demo_mode)
