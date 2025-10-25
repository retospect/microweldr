"""
Print monitoring library for SVG welder.
"""

import datetime
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

from microweldr.prusalink.client import PrusaLinkClient
from microweldr.prusalink.exceptions import PrusaLinkError


class MonitorMode(Enum):
    """Monitoring modes for different print types."""

    STANDARD = "standard"
    LAYED_BACK = "layed-back"
    PIPETTING = "pipetting"


class PrintMonitor:
    """Print monitoring with mode-specific behavior."""

    def __init__(
        self,
        mode: MonitorMode = MonitorMode.STANDARD,
        interval: int = 30,
        verbose: bool = False,
        status_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """
        Initialize print monitor.

        Args:
            mode: Monitoring mode (standard, layed-back, pipetting)
            interval: Check interval in seconds
            verbose: Show detailed output
            status_callback: Optional callback for status updates
        """
        self.mode = mode
        self.interval = interval
        self.verbose = verbose
        self.status_callback = status_callback
        self.client = PrusaLinkClient()
        self.start_time = time.time()
        self.last_progress = -1
        self.last_state = None

    def get_mode_emoji(self) -> str:
        """Get emoji for current monitoring mode."""
        mode_emojis = {
            MonitorMode.STANDARD: "🏗️",
            MonitorMode.LAYED_BACK: "🛋️",
            MonitorMode.PIPETTING: "🧪",
        }
        return mode_emojis.get(self.mode, "📊")

    def format_time_remaining(self, seconds: Optional[float]) -> str:
        """Format time remaining in human readable format."""
        if not seconds or seconds <= 0:
            return "Unknown"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def print_header(self) -> None:
        """Print monitoring header."""
        emoji = self.get_mode_emoji()
        mode_name = self.mode.value.replace("-", " ").title()

        print(f"{emoji} SVG Welder Print Monitor - {mode_name} Mode")
        print("=" * 60)
        print(f"⏱️ Started: {datetime.datetime.now().strftime('%H:%M:%S')}")

        if self.mode == MonitorMode.LAYED_BACK:
            print("🛋️ Printer: Chillin' on its back (door pointing up)")
        elif self.mode == MonitorMode.PIPETTING:
            print("🧪 Features: Pipetting stops for microfluidic devices")
        elif self.mode == MonitorMode.STANDARD:
            print("⬆️ Mode: Standard upright operation")

        print("=" * 60)

    def print_status_update(self, job: Dict[str, Any], elapsed_min: int) -> None:
        """Print status update with detailed printer information."""
        file_name = job.get("file", {}).get("name", "Unknown")
        display_name = job.get("file", {}).get("display_name", file_name)
        state = job.get("state", "Unknown")
        progress = job.get("progress", 0)
        time_printing = job.get("time_printing", 0)

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        emoji = self.get_mode_emoji()

        print(
            f"[{timestamp}] ({elapsed_min:02d}min) 📊 {progress:.1f}% | {emoji} {state}"
        )

        if self.verbose:
            print(f"    📄 File: {display_name}")

        # Get detailed printer status
        try:
            printer_status = self.client.get_printer_status()
            printer_info = printer_status.get("printer", {})

            # Show current activity estimation
            current_activity = self._estimate_current_activity(printer_info, job)
            print(f"    🎯 Activity: {current_activity}")

            # Temperature information
            temp_bed = printer_info.get("temp_bed")
            target_bed = printer_info.get("target_bed")
            temp_nozzle = printer_info.get("temp_nozzle")
            target_nozzle = printer_info.get("target_nozzle")

            if temp_bed is not None and target_bed is not None:
                temp_diff_bed = abs(temp_bed - target_bed)
                if temp_diff_bed > 2:  # More than 2°C difference
                    if temp_bed < target_bed:
                        print(
                            f"    🔥 Heating bed: {temp_bed:.1f}°C → {target_bed:.1f}°C"
                        )
                    else:
                        print(
                            f"    ❄️ Cooling bed: {temp_bed:.1f}°C → {target_bed:.1f}°C"
                        )
                elif self.verbose:
                    print(f"    🌡️ Bed: {temp_bed:.1f}°C (target: {target_bed:.1f}°C)")

            if temp_nozzle is not None and target_nozzle is not None:
                temp_diff_nozzle = abs(temp_nozzle - target_nozzle)
                if temp_diff_nozzle > 5:  # More than 5°C difference
                    if temp_nozzle < target_nozzle:
                        print(
                            f"    🔥 Heating nozzle: {temp_nozzle:.1f}°C → {target_nozzle:.1f}°C"
                        )
                    else:
                        print(
                            f"    ❄️ Cooling nozzle: {temp_nozzle:.1f}°C → {target_nozzle:.1f}°C"
                        )
                elif self.verbose:
                    print(
                        f"    🌡️ Nozzle: {temp_nozzle:.1f}°C (target: {target_nozzle:.1f}°C)"
                    )

            # Z position and other details
            if self.verbose:
                axis_z = printer_info.get("axis_z")
                if axis_z is not None:
                    print(f"    📐 Z-position: {axis_z:.2f}mm")

                speed = printer_info.get("speed")
                flow = printer_info.get("flow")
                if speed is not None:
                    print(f"    ⚡ Speed: {speed}%", end="")
                    if flow is not None:
                        print(f" | Flow: {flow}%")
                    else:
                        print()

                # Print time
                if time_printing > 0:
                    hours = int(time_printing // 3600)
                    minutes = int((time_printing % 3600) // 60)
                    if hours > 0:
                        print(f"    ⏱️ Print time: {hours}h {minutes}m")
                    else:
                        print(f"    ⏱️ Print time: {minutes}m")

        except Exception as e:
            if self.verbose:
                print(f"    ⚠️ Could not get detailed status: {e}")

        # Mode-specific status messages
        if state.lower() == "paused":
            if self.mode == MonitorMode.PIPETTING:
                print("    🧪 PIPETTING PAUSE - Check LCD for instructions!")
                print("    💉 Fill pouches as directed, then press continue")
            elif self.mode == MonitorMode.LAYED_BACK:
                print("    🛋️ PAUSE - Check LCD for instructions!")
                print("    📋 Complete the required action, then press continue")
            else:
                print("    ⏸️ PAUSED - Check printer LCD for instructions")

        # Call status callback if provided
        if self.status_callback:
            self.status_callback(
                {
                    "file_name": file_name,
                    "display_name": display_name,
                    "state": state,
                    "progress": progress,
                    "time_printing": time_printing,
                    "elapsed_min": elapsed_min,
                }
            )

    def monitor_until_complete(self, print_header: bool = True) -> bool:
        """
        Monitor print until completion.

        Args:
            print_header: Whether to print the monitoring header

        Returns:
            True if print completed successfully, False otherwise
        """
        if print_header:
            self.print_header()

        try:
            while True:
                try:
                    job = self.client.get_job_status()
                    current_time = time.time()
                    elapsed_min = int((current_time - self.start_time) / 60)

                    if job:
                        state = job.get("state", "Unknown")
                        progress_data = job.get("progress", 0)

                        if isinstance(progress_data, dict):
                            progress = progress_data.get("completion", 0)
                        else:
                            progress = progress_data if progress_data else 0

                        # Print status if changed
                        if progress != self.last_progress or state != self.last_state:
                            self.print_status_update(job, elapsed_min)
                            self.last_progress = progress
                            self.last_state = state

                        # Check for completion or failure
                        if state.lower() in ["finished", "completed", "done"]:
                            emoji = self.get_mode_emoji()
                            print(f"\n🎉 Print completed successfully!")
                            print(
                                f"✅ Your {self.mode.value.replace('-', ' ')} print finished! {emoji}"
                            )
                            return True
                        elif state.lower() in ["error", "failed", "cancelled"]:
                            print(f"\n❌ Print failed with state: {state}")
                            return False

                    else:
                        if self.last_state != "no_job":
                            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                            print(
                                f"[{timestamp}] ({elapsed_min:02d}min) ❌ No job running"
                            )
                            print("    (Printer might have rebooted or job completed)")
                            self.last_state = "no_job"
                            return False

                    time.sleep(self.interval)

                except Exception as e:
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] ⚠️ Connection error: {e}")
                    print("    (Printer might be rebooting or network issue)")
                    time.sleep(60)  # Wait longer on error

        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
            return False
        except PrusaLinkError as e:
            print(f"\n❌ PrusaLink error: {e}")
            return False
        except Exception as e:
            print(f"\n❌ Monitoring error: {e}")
            return False

    def get_current_status(self) -> Optional[Dict[str, Any]]:
        """Get current printer status without monitoring loop."""
        try:
            job = self.client.get_job_status()
            printer_status = self.client.get_printer_status()

            if job:
                progress = job.get("progress", 0)
                printer_info = printer_status.get("printer", {})

                # Estimate current activity based on temperatures and state
                current_activity = self._estimate_current_activity(printer_info, job)

                return {
                    "file_name": job.get("file", {}).get("name", "Unknown"),
                    "display_name": job.get("file", {}).get("display_name", "Unknown"),
                    "state": job.get("state", "Unknown"),
                    "progress": progress,
                    "time_printing": job.get("time_printing", 0),
                    "current_activity": current_activity,
                    "printer_info": printer_info,
                }
            return None
        except Exception:
            return None

    def _estimate_current_activity(
        self, printer_info: Dict[str, Any], job: Dict[str, Any]
    ) -> str:
        """Estimate what the printer is currently doing based on available data."""
        state = job.get("state", "").lower()
        progress = job.get("progress", 0)

        temp_bed = printer_info.get("temp_bed", 0)
        target_bed = printer_info.get("target_bed", 0)
        temp_nozzle = printer_info.get("temp_nozzle", 0)
        target_nozzle = printer_info.get("target_nozzle", 0)
        axis_z = printer_info.get("axis_z", 0)

        if state == "paused":
            return "⏸️ Paused - waiting for user action"
        elif state != "printing":
            return f"📊 {state.title()}"

        # Check if heating
        if target_bed > 0 and abs(temp_bed - target_bed) > 2:
            return f"🔥 Heating bed ({temp_bed:.1f}°C → {target_bed:.1f}°C)"
        elif target_nozzle > 0 and abs(temp_nozzle - target_nozzle) > 5:
            return f"🔥 Heating nozzle ({temp_nozzle:.1f}°C → {target_nozzle:.1f}°C)"

        # Estimate based on progress and Z position
        if progress < 1:
            if axis_z < 1:
                return "🏠 Homing and calibration"
            elif target_bed > 0 or target_nozzle > 0:
                return "🔥 Initial heating"
            else:
                return "🚀 Starting print"
        elif progress < 5:
            return "🎯 Initial layers"
        elif progress > 95:
            return "🏁 Final layers"
        else:
            if axis_z < 10:
                return f"🔧 Welding (Z: {axis_z:.1f}mm)"
            elif axis_z < 50:
                return f"⚡ Active welding (Z: {axis_z:.1f}mm)"
            else:
                return f"🔥 High-layer welding (Z: {axis_z:.1f}mm)"

    def stop_print(self, force: bool = False) -> bool:
        """Stop the current print job."""
        try:
            job = self.client.get_job_status()
            if not job:
                print("❌ No job currently running")
                return False

            file_name = job.get("file", {}).get("name", "Unknown")
            state = job.get("state", "Unknown")

            print(f"📄 Current job: {file_name}")
            print(f"🔄 State: {state}")

            if state.lower() in ["finished", "completed", "done"]:
                print("✅ Job is already completed")
                return True

            if state.lower() in ["error", "failed", "cancelled"]:
                print(f"❌ Job is already in {state} state")
                return True

            # Confirm stop unless forced
            if not force:
                try:
                    response = input(
                        "Are you sure you want to stop the current print? (y/N): "
                    )
                    if not response.lower().startswith("y"):
                        print("🛑 Stop cancelled")
                        return False
                except (EOFError, KeyboardInterrupt):
                    print("\n🛑 Stop cancelled")
                    return False

            # Stop the print
            success = self.client.stop_print()

            if success:
                print("✅ Print stopped successfully")
                return True
            else:
                print("❌ Failed to stop print")
                return False

        except PrusaLinkError as e:
            print(f"❌ PrusaLink error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
