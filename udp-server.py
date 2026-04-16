import socket
import datetime
import time
from pathlib import Path

# Configuration
PORT = 30304
client_sessions = {}

# Optimization Tips to Maximize PPS:
# If you find you are dropping packets, you can optimize your loop in the following ways:

# Remove datetime.now() from the loop: Call time-stamping functions only when necessary, 
# as they are expensive system calls.

# Increase Socket Buffer: Increase the kernel's receive buffer size so it can "queue" 
# packets during temporary CPU spikes:

# s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
# Use bytearray: If you are processing the data, avoid frequent string conversions. 
# Work with the binary raw_data directly as long as possible.

# Avoid DNS Lookups: Ensure you are not performing any reverse DNS lookups 
# on the addr (IP address) inside the loop, as this will drop your performance 
# to less than 10 PPS if a lookup hangs.

# The Fix: If you are logging, write to /tmp/ (which is RAM) first, or log in large chunks
 # rather than every single packet.

# Pro-Tip: To ensure your SD card doesn't slow down the network loop, make sure your 
# code isn't doing any file.write() or print() calls that redirect to a file on the SD
 # card inside the while True loop. Keep the processing in-memory as much as possible!

# Align the Sending Devices
# If you have control over the devices (the phones), the most efficient way for your Mango 
# router is to set both devices to send to port 30305.

# UDP doesn't care if multiple devices talk to the same port.

# Your current script will already handle this because you use addr[0] (the IP address) to 
# separate them into different files.

# This reduces CPU overhead on the Mango because you only manage one socket and one loop.

FLUSH_THRESHOLD = 50  # Number of lines to buffer in RAM before writing to SD
client_buffers = {}   # Holds the actual text data: {ip: ["line1", "line2"]}
client_sessions = {}  # Holds the file paths: {ip: Path}

# PPS Tracking Variables
packet_count = 0
last_report_time = time.time()

# Create UDP socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536) # Increase kernel buffer

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
        packet_count += 1  # Increment counter for every packet received

        # --- PPS Reporting Logic ---
        current_time = time.time()
        elapsed = current_time - last_report_time
        
        if elapsed >= 5.0:  # Every 5 second, print the stats
            pps = packet_count / elapsed
            print(f"[STATS] Current Throughput: {pps:.1f} packets/sec")
            packet_count = 0
            last_report_time = current_time
        # ---------------------------
        
        # Initialize session and buffer for new IPs
        if ip_address not in client_sessions:
            # Define the client directory path
            client_dir = Path(f"phone_{ip_address[-3:]}")
            
            # Create the directory if it doesn't exist (equivalent to mkdir -p)
            client_dir.mkdir(parents=True, exist_ok=True)
            
            # Define the filename: 2024-05-05_0300.nmea
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
            client_sessions[ip_address] = client_dir / f"{timestamp}.nmea"
            client_buffers[ip_address] = [] 
            print(f"[*] New session: {ip_address}")

        # 1. Decode and add to RAM buffer
        clean_data = raw_data.decode('utf-8', errors='ignore').strip()
        if clean_data:
            client_buffers[ip_address].append(clean_data + "\n")

        # 2. Check if it's time to flush to SD card
        if len(client_buffers[ip_address]) >= FLUSH_THRESHOLD:
            target_path = client_sessions[ip_address]
            
            # Write the entire batch at once
            with target_path.open(mode="a", encoding="utf-8") as f:
                f.writelines(client_buffers[ip_address])
            
            # print(f"[FLUSH] Saved {len(client_buffers[ip_address])} lines for {ip_address}")
            
            
            
            # Clear the RAM buffer
            client_buffers[ip_address] = []

    except KeyboardInterrupt:
        # Final flush before exiting so you don't lose data
        print("\nFlushing remaining buffers and stopping...")
        for ip, lines in client_buffers.items():
            if lines:
                with client_sessions[ip].open(mode="a") as f:
                    f.writelines(lines)
        break
    except Exception as e:
        print(f"Error: {e}")

s.close()