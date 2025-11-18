import subprocess
import platform
import sys
import os

def ping_ip_address(ip_address, count=1, timeout=2):
    """
    Pings a specified IP address using the native system command.

    Args:
        ip_address (str): The target IP address or hostname.
        count (int): The number of echo requests to send (packets).
        timeout (int): The timeout in seconds for each request.

    Returns:
        bool: True if at least one packet was received, False otherwise.
    """
    
    # 1. Determine OS-specific command syntax
    # Windows uses -n for count, Linux/macOS use -c
    if platform.system().lower() == "windows":
        # Windows ping command: ping -n 1 -w 2000 8.8.8.8
        # -n <count> (number of echoes), -w <timeout_ms> (timeout in milliseconds)
        command = [
            "ping", 
            "-n", str(count), 
            "-w", str(timeout * 1000), 
            ip_address
        ]
        # In Windows, we check stdout for the string "Reply from"
        success_text = "Reply from"
    else:
        # Linux/macOS/OpenWrt ping command: ping -c 1 -W 2 8.8.8.8
        # -c <count> (number of echoes), -W <timeout_s> (timeout in seconds)
        command = [
            "ping", 
            "-c", str(count), 
            "-W", str(timeout), 
            ip_address
        ]
        # In Linux/OpenWrt, we check the return code (0 for success)
        # and look for packet loss percentage.
        success_text = f"{count} packets received"
        
    print(f"Pinging {ip_address} using command: {' '.join(command)}")

    try:
        # 2. Execute the command and capture output
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False  # Do NOT raise an exception on non-zero exit code (ping failure)
        )

        # 3. Check the result
        if result.returncode == 0:
            print(f"✅ Ping successful! (Return Code 0)")
            # You can parse more details from result.stdout if needed
            return True
        else:
            # On non-Windows, a return code of 1 or 2 often means no reply
            # On Windows, we need to inspect the output text.
            if platform.system().lower() == "windows":
                 if success_text in result.stdout:
                     print(f"✅ Ping successful! (Found '{success_text}' in output)")
                     return True
                 else:
                     print(f"❌ Ping failed. Output did not contain '{success_text}'.")
                     print(result.stdout)
                     return False
            else:
                 # Standard Linux/OpenWrt failure
                 print(f"❌ Ping failed. Return Code: {result.returncode}")
                 # For details on the failure:
                 # print(result.stderr or result.stdout)
                 return False

    except FileNotFoundError:
        print(f"ERROR: The 'ping' command was not found. Is it installed and in your PATH?")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during ping: {e}")
        return False

if __name__ == "__main__":
    # Test cases
    target_ip = "8.8.8.8" # Google DNS (should succeed)
    fail_ip = "192.0.2.1" # Reserved documentation IP (should fail)
    qk_ip = "192.168.8.60" # QK Elec A-026

    print("\n--- Running Test 1 (Success Expectation) ---")
    if ping_ip_address(target_ip, count=2):
        print(f"Result for {target_ip}: Reachable.")
    else:
        print(f"Result for {target_ip}: Unreachable.")

    print("\n--- Running Test 2 (Failure Expectation) ---")
    if ping_ip_address(fail_ip, count=1):
        print(f"Result for {fail_ip}: Reachable.")
    else:
        print(f"Result for {fail_ip}: Unreachable.")
        
   print("\n--- Checking QK A-026 ---")
    if ping_ip_address(fail_ip, count=1):
        print(f"Result for {qk_ip}: Reachable.")
    else:
        print(f"Result for {qk_ip}: Unreachable.")        