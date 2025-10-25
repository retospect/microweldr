"""
Print monitoring library for SVG welder.
"""

import time
import datetime
from enum import Enum
from typing import Optional, Callable, Dict, Any
from svg_welder.prusalink.client import PrusaLinkClient
from svg_welder.prusalink.exceptions import PrusaLinkError


class MonitorMode(Enum):
    """Monitoring modes for different print types."""
    STANDARD = "standard"
    LAYED_BACK = "layed-back"
    PIPETTING = "pipetting"


class PrintMonitor:
    """Print monitoring with mode-specific behavior."""
    
    def __init__(self, 
                 mode: MonitorMode = MonitorMode.STANDARD,
                 interval: int = 30,
                 verbose: bool = False,
                 status_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
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
            MonitorMode.PIPETTING: "🧪"
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
        """Print status update."""
        file_name = job.get('file', {}).get('name', 'Unknown')
        state = job.get('state', 'Unknown')
        progress_data = job.get('progress', 0)
        
        if isinstance(progress_data, dict):
            progress = progress_data.get('completion', 0)
            time_left = progress_data.get('printTimeLeft')
        else:
            progress = progress_data if progress_data else 0
            time_left = None
        
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        emoji = self.get_mode_emoji()
        
        print(f"[{timestamp}] ({elapsed_min:02d}min) 📊 {progress:.1f}% | {emoji} {state}")
        
        if self.verbose:
            print(f"    📄 File: {file_name}")
        
        if time_left and time_left > 0:
            print(f"    ⏰ Time remaining: {self.format_time_remaining(time_left)}")
        
        # Mode-specific status messages
        if state.lower() == 'paused':
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
            self.status_callback({
                'file_name': file_name,
                'state': state,
                'progress': progress,
                'time_left': time_left,
                'elapsed_min': elapsed_min
            })
    
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
                        state = job.get('state', 'Unknown')
                        progress_data = job.get('progress', 0)
                        
                        if isinstance(progress_data, dict):
                            progress = progress_data.get('completion', 0)
                        else:
                            progress = progress_data if progress_data else 0
                        
                        # Print status if changed
                        if progress != self.last_progress or state != self.last_state:
                            self.print_status_update(job, elapsed_min)
                            self.last_progress = progress
                            self.last_state = state
                        
                        # Check for completion or failure
                        if state.lower() in ['finished', 'completed', 'done']:
                            emoji = self.get_mode_emoji()
                            print(f"\n🎉 Print completed successfully!")
                            print(f"✅ Your {self.mode.value.replace('-', ' ')} print finished! {emoji}")
                            return True
                        elif state.lower() in ['error', 'failed', 'cancelled']:
                            print(f"\n❌ Print failed with state: {state}")
                            return False
                            
                    else:
                        if self.last_state != 'no_job':
                            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
                            print(f"[{timestamp}] ({elapsed_min:02d}min) ❌ No job running")
                            print("    (Printer might have rebooted or job completed)")
                            self.last_state = 'no_job'
                            return False
                    
                    time.sleep(self.interval)
                    
                except Exception as e:
                    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
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
            if job:
                progress_data = job.get('progress', 0)
                if isinstance(progress_data, dict):
                    progress = progress_data.get('completion', 0)
                    time_left = progress_data.get('printTimeLeft')
                else:
                    progress = progress_data if progress_data else 0
                    time_left = None
                
                return {
                    'file_name': job.get('file', {}).get('name', 'Unknown'),
                    'state': job.get('state', 'Unknown'),
                    'progress': progress,
                    'time_left': time_left
                }
            return None
        except Exception:
            return None
    
    def stop_print(self, force: bool = False) -> bool:
        """Stop the current print job."""
        try:
            job = self.client.get_job_status()
            if not job:
                print("❌ No job currently running")
                return False
            
            file_name = job.get('file', {}).get('name', 'Unknown')
            state = job.get('state', 'Unknown')
            
            print(f"📄 Current job: {file_name}")
            print(f"🔄 State: {state}")
            
            if state.lower() in ['finished', 'completed', 'done']:
                print("✅ Job is already completed")
                return True
            
            if state.lower() in ['error', 'failed', 'cancelled']:
                print(f"❌ Job is already in {state} state")
                return True
            
            # Confirm stop unless forced
            if not force:
                try:
                    response = input("Are you sure you want to stop the current print? (y/N): ")
                    if not response.lower().startswith('y'):
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
