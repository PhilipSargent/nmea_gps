import subprocess
import sys
import os

def reboot_openwrt():
    """
    Executes the 'reboot' command using the subprocess module.
    This function should only be run on the OpenWrt router itself.
    """
    
    # 1. Define the system command
    reboot_command = ["/sbin/reboot"] 
    # Using the full path /sbin/reboot ensures the command is found regardless of the shell's current PATH.
    
    print("-" * 50)
    print("WARNING: You are about to reboot the router.")
    print("This will terminate all connections and services momentarily.")
    print("-" * 50)
    
    try:
        # 2. Execute the command
        # check=True raises an exception if the command returns a non-zero exit code (failure)
        # capture_output=True prevents output from cluttering the terminal, though reboot rarely has any.
        print(f"Executing system command: {' '.join(reboot_command)}")
        
        # NOTE: Once this command is executed, the router will immediately start shutting down.
        # The Python script will likely be terminated before this line completes.
        result = subprocess.run(
            reboot_command,
            check=True, 
            capture_output=True,
            text=True,
            timeout=5 # Give the command a short timeout just in case it hangs (unlikely for reboot)
        )
        
        # This code should technically not be reached unless the command fails instantly.
        print("\nReboot command sent successfully.")
        
        if result.stdout:
            print("Stdout:", result.stdout)
        if result.stderr:
            # If the command fails, the error will be in stderr
            print("Stderr:", result.stderr)

    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Reboot command failed with exit code {e.returncode}.")
        print(f"Details: {e.stderr}")
        print("Check if the Python script has the necessary permissions (usually root/admin).")
    except subprocess.TimeoutExpired:
        print("\nINFO: The reboot command was sent, but the script timed out while waiting.")
        print("This is normal, as the system started shutting down immediately.")
    except FileNotFoundError:
        print("\nFATAL ERROR: The 'reboot' command was not found in the specified path.")
        print("Please verify the path /sbin/reboot.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        
    print("-" * 50)


if __name__ == "__main__":
    # Ensure the script is running with root privileges, which is often necessary for reboot
    if os.geteuid() != 0:
        print("Warning: It is highly recommended to run this script as the 'root' user.")
        print("The reboot command may fail without proper permissions.")
        
    reboot_openwrt()