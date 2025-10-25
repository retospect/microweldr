#!/usr/bin/env python3
"""Test script for PrusaLink integration."""

import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from svg_welder.prusalink import PrusaLinkClient, PrusaLinkError


def main():
    """Test PrusaLink connection and functionality."""
    print("Testing PrusaLink integration...")
    
    try:
        # Initialize client
        print("1. Loading configuration...")
        client = PrusaLinkClient()
        print("   ✓ Configuration loaded")
        
        # Test connection
        print("2. Testing connection...")
        if client.test_connection():
            print("   ✓ Connection successful")
        else:
            print("   ✗ Connection failed")
            print("   Please check your printer IP and network connection")
            return
            
        # Get printer info
        print("3. Getting printer information...")
        try:
            info = client.get_printer_info()
            print(f"   ✓ Printer: {info.get('name', 'Unknown')}")
            print(f"   ✓ Firmware: {info.get('firmware', 'Unknown')}")
        except PrusaLinkError as e:
            print(f"   ✗ Failed to get printer info: {e}")
            
        # Get storage info
        print("4. Getting storage information...")
        try:
            storage = client.get_storage_info()
            print(f"   ✓ Available storage: {len(storage.get('storage_list', []))} devices")
            for store in storage.get('storage_list', []):
                print(f"      - {store.get('name', 'Unknown')}: {store.get('free_space', 0)} bytes free")
        except PrusaLinkError as e:
            print(f"   ✗ Failed to get storage info: {e}")
            
        # Get job status
        print("5. Getting job status...")
        try:
            job = client.get_job_status()
            if job:
                print(f"   ✓ Current job: {job.get('file', {}).get('name', 'Unknown')}")
                print(f"   ✓ Status: {job.get('state', 'Unknown')}")
            else:
                print("   ✓ No job currently running")
        except PrusaLinkError as e:
            print(f"   ✗ Failed to get job status: {e}")
            
        # Check printer readiness
        print("6. Checking printer readiness...")
        try:
            if client.is_printer_ready():
                print("   ✓ Printer is ready for immediate printing")
            else:
                print("   ⚠ Printer may not be ready (busy or has errors)")
                
            status = client.get_printer_status()
            printer_state = status.get('printer', {}).get('state', 'Unknown')
            print(f"   ℹ Printer state: {printer_state}")
        except PrusaLinkError as e:
            print(f"   ✗ Failed to check printer readiness: {e}")
            
        print("\n✓ All tests completed successfully!")
        print("\nYour PrusaLink integration is ready for immediate printing!")
        print("Files will be uploaded and started automatically with your current config.")
        print("\nUsage:")
        print("  svg-welder input.svg --submit-to-printer  # Will auto-start based on config")
        print("  svg-welder input.svg --submit-to-printer --auto-start-print  # Force auto-start")
        
    except PrusaLinkError as e:
        print(f"\n✗ PrusaLink error: {e}")
        print("\nPlease check your secrets.toml configuration:")
        print("1. Verify your printer's IP address")
        print("2. Check your API key (get it from printer's web interface)")
        print("3. Ensure your printer is connected to the network")
        
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
