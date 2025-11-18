import psutil
import socket
import sys

def get_process_name(pid):
    """Safely retrieves the name of a process given its PID."""
    try:
        return psutil.Process(pid).name()
    except psutil.NoSuchProcess:
        return "[Process Not Found]"
    except Exception:
        return "[Unknown Process]"

def find_and_report_connections(target_ip, target_port):
    """
    Finds open TCP connections to a specific remote IP and port.

    Args:
        target_ip (str): The remote IP address to look for.
        target_port (int): The remote port number to look for.

    Returns:
        list: A list of dictionaries containing connection details (pid, laddr, raddr, status, process_name).
    """
    print(f"--- Scanning connections targeting {target_ip}:{target_port} ---")
    
    # 1. Get all network connections (TCP only)
    connections = psutil.net_connections('tcp')
    
    found_connections = []
    
    # 2. Iterate through connections and filter by remote address/port
    for conn in connections:
        # psutil returns a tuple for remote address (ip, port)
        if conn.raddr and conn.raddr.ip == target_ip and conn.raddr.port == target_port:
            
            # Skip connections without a known PID (often kernel/system connections)
            if conn.pid is None:
                continue

            found_connections.append({
                'pid': conn.pid,
                'laddr_ip': conn.laddr.ip,
                'laddr_port': conn.laddr.port,
                'status': conn.status,
                'process_name': get_process_name(conn.pid)
            })
            
    return found_connections

def close_connections_by_process(target_ip, target_port):
    """
    Identifies and reports processes holding the target connections.
    It does not automatically terminate the processes.
    """
    # Validate the IP address format
    try:
        socket.inet_aton(target_ip)
    except socket.error:
        print(f"Error: '{target_ip}' is not a valid IPv4 address.")
        sys.exit(1)
        
    # Validate the port number
    if not 0 < target_port <= 65535:
        print(f"Error: Port number {target_port} is invalid. Must be between 1 and 65535.")
        sys.exit(1)

    connections_to_close = find_and_report_connections(target_ip, target_port)
    
    if not connections_to_close:
        print("\n✅ Success: No matching open connections found.")
        return

    print(f"\nFound {len(connections_to_close)} connections targeting {target_ip}:{target_port}:")
    print("-" * 50)
    
    # Use a set to only list unique processes (a single process might have multiple sockets)
    unique_processes = {}
    
    for conn in connections_to_close:
        pid = conn['pid']
        
        # Report the connection details
        print(f"| PID: {pid:<6} | Status: {conn['status']:<10} | Process: {conn['process_name']:<20}")
        print(f"|   Local: {conn['laddr_ip']}:{conn['laddr_port']} -> Remote: {target_ip}:{target_port}")
        
        # Collect unique processes
        unique_processes[pid] = conn['process_name']

    print("-" * 50)
    
    print("\n💡 Action Required: To close these sockets, you must terminate the owning processes listed below.")
    print("   (The script cannot safely terminate processes across all operating systems.)")
    print("   ---------------------------------------------------------------------------------")
    
    for pid, name in unique_processes.items():
        print(f"   Process to terminate: PID={pid:<6} | Name='{name}'")
    
    print("   ---------------------------------------------------------------------------------")
    
    # Provide OS-specific termination commands
    print("\n**How to terminate these processes manually:**")
    if sys.platform.startswith('win'):
        print(f"  > Windows: For PID {pid}, run: taskkill /F /PID {pid}")
        print("    (You need to run Command Prompt/PowerShell as Administrator.)")
    elif sys.platform.startswith('linux') or sys.platform == 'darwin': # Linux and macOS
        print(f"  > Linux/macOS: For PID {pid}, run: kill -9 {pid}")
        print("    (You might need 'sudo' if the process owner is not your user.)")
    else:
        print("  > Your OS is not explicitly supported for automated termination instructions.")


if __name__ == "__main__":
    # Example usage (you would typically run this from the command line)
    # python socket_terminator.py 192.168.1.1 80
    
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <Target_IP> <Target_Port>")
        print("\nExample: python socket_terminator.py 10.0.0.5 443")
        sys.exit(1)
        
    try:
        ip = sys.argv[1]
        port = int(sys.argv[2])
        
        # Check if psutil is installed
        if 'psutil' not in sys.modules:
            print("\nError: The 'psutil' library is required but not found.")
            print("Please install it using: pip install psutil")
            sys.exit(1)
            
        close_connections_by_process(ip, port)
        
    except ValueError:
        print("Error: The port number must be an integer.")
        sys.exit(1)