#!/usr/bin/env python3
"""Simple print tracking script."""

import time
import sys
from svg_welder.prusalink.client import PrusaLinkClient

def check_print_status():
    """Check and display current print status."""
    try:
        client = PrusaLinkClient()
        job = client.get_job_status()
        
        if job:
            file_name = job.get('file', {}).get('name', 'Unknown')
            state = job.get('state', 'Unknown')
            
            # Handle progress - can be dict or float
            progress_data = job.get('progress', 0)
            if isinstance(progress_data, dict):
                progress = progress_data.get('completion', 0)
                time_left = progress_data.get('printTimeLeft')
            else:
                progress = progress_data if progress_data else 0
                time_left = None
            
            print(f"📄 File: {file_name}")
            print(f"🔄 State: {state}")
            print(f"📊 Progress: {progress:.1f}%")
            
            if time_left and time_left > 0:
                hours = int(time_left // 3600)
                minutes = int((time_left % 3600) // 60)
                print(f"⏰ Time remaining: {hours}h {minutes}m")
            
            return state, progress
        else:
            print("❌ No job running")
            return None, 0
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, 0

if __name__ == "__main__":
    print("🖨️ Tracking print progress...")
    print("=" * 40)
    
    while True:
        try:
            state, progress = check_print_status()
            print("-" * 40)
            
            if state and state.lower() in ['finished', 'completed', 'done']:
                print("✅ Print completed!")
                break
            elif state and state.lower() in ['error', 'failed', 'cancelled']:
                print(f"❌ Print failed: {state}")
                break
            elif not state:
                print("⏸️ No active print")
                break
                
            time.sleep(15)  # Check every 15 seconds
            
        except KeyboardInterrupt:
            print("\n🛑 Tracking stopped")
            break
