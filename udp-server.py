import socket
import datetime
from pathlib import Path

# Configuration
PORT = 30304
client_sessions = {}

# Create UDP socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    s.bind(("0.0.0.0", PORT))
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    print(f"UDP NMEA Listener active at {timestamp} on port {PORT}...")
except Exception as e:
    print(f"Error binding: {e}")
    exit()

while True:
    try:
        raw_data, addr = s.recvfrom(4096)
        ip_address = addr[0]
        
        # 1. Directory and Filename Management using pathlib
        if ip_address not in client_sessions:
            # Define the client directory path
            client_dir = Path(f"phone_{ip_address[-3:]}")
            
            # Create the directory if it doesn't exist (equivalent to mkdir -p)
            client_dir.mkdir(parents=True, exist_ok=True)
            
            # Define the filename: 2024-05-05_0300.nmea
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
            file_path = client_dir / f"{timestamp}.nmea"
            
            client_sessions[ip_address] = file_path
            print(f"[*] New session from {ip_address}. Saving to: {file_path}")
        
        target_path = client_sessions[ip_address]

        # 2. Clean the NMEA data (Strip CRLF and the extra LF)
        clean_data = raw_data.decode('utf-8', errors='ignore').strip()
        
        if clean_data:
            # 3. Append to file using pathlib's open() method
            # Mode 'a' ensures we append rather than overwrite
            with target_path.open(mode="a", encoding="utf-8") as f:
                f.write(clean_data + "\n")
            
            # Console output for monitoring
            print(f"[{ip_address}] {clean_data}")

    except KeyboardInterrupt:
        print("\nStopping listener...")
        break
    except Exception as e:
        print(f"Error: {e}")

s.close()