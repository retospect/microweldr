import curses
import time
from pathlib import Path

from microweldr.ui.curses_ui import MicroWeldrUI


def test_ui_keys(stdscr):
    ui = MicroWeldrUI(config_file=Path("examples/config.toml"))
    ui.initialize()

    stdscr.clear()
    stdscr.addstr(0, 0, "UI Key Test - Press 1, 2, 3, 4, or q to quit")
    stdscr.addstr(1, 0, f"Printer connected: {ui.printer_connected}")
    stdscr.addstr(2, 0, f"PrinterOps available: {ui.printer_ops is not None}")
    stdscr.addstr(4, 0, "Commands:")
    stdscr.addstr(5, 0, "1 - Calibrate")
    stdscr.addstr(6, 0, "2 - Toggle Heater")
    stdscr.addstr(7, 0, "3 - Bounding Box")
    stdscr.addstr(8, 0, "4 - Load/Unload")
    stdscr.addstr(9, 0, "q - Quit")
    stdscr.addstr(11, 0, "Status: Waiting for key press...")
    stdscr.refresh()

    while True:
        key = stdscr.getch()
        stdscr.addstr(
            11,
            0,
            f"Status: Key pressed: {chr(key) if 32 <= key <= 126 else key}" + " " * 20,
        )

        if key == ord("q"):
            break
        elif key == ord("1"):
            stdscr.addstr(12, 0, "Executing calibrate..." + " " * 30)
            stdscr.refresh()
            result = ui.handle_calibrate()
            stdscr.addstr(12, 0, f"Calibrate result: {result}" + " " * 30)
        elif key == ord("2"):
            stdscr.addstr(12, 0, "Executing heater toggle..." + " " * 30)
            stdscr.refresh()
            result = ui.handle_plate_heater()
            stdscr.addstr(
                12,
                0,
                f"Heater result: {result}, State: {ui.plate_heater_on}" + " " * 30,
            )
        elif key == ord("3"):
            stdscr.addstr(12, 0, "Executing bounding box..." + " " * 30)
            stdscr.refresh()
            result = ui.handle_bounding_box()
            stdscr.addstr(12, 0, f"Bounding box result: {result}" + " " * 30)
        elif key == ord("4"):
            stdscr.addstr(12, 0, "Executing load/unload..." + " " * 30)
            stdscr.refresh()
            result = ui.handle_load_unload()
            stdscr.addstr(12, 0, f"Load/unload result: {result}" + " " * 30)

        stdscr.refresh()


if __name__ == "__main__":
    curses.wrapper(test_ui_keys)
