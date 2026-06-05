"""
nmeajogger.py
Philip Sargent

Listens to NMEA streams over UDP on a specified port.
Saves raw logs to nmea_XXXd and filtered data to nmea_logs as standard $GPGGA strings for GPSPrune.
Usage: uv run nmeajogger.py 30305

Completely written by Gemini on verbal instructions to use udp not tcp
taking nmealogger.py as a model.
"""

import sys
import os
import io
import socket
import math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from pynmeagps.nmeareader import NMEAReader
from pynmeagps.exceptions import NMEAParseError
from pynmeagps.nmeatypes_core import ERR_RAISE

# --- Configuration & Constants ---
METERS_PER_DEGREE_AT_EQUATOR = 111320.0 
LONG_ENOUGH = 300000       # Max messages before restarting a new log file
FILE_BUFSIZE = 1024
TZ = ZoneInfo('Europe/Athens')

# --- Parse Command Line Arguments ---
if len(sys.argv) != 2:
    print("Usage: uv run nmeajogger.py <port_number>")
    print("Example: uv run nmeajogger.py 30305")
    sys.exit(1)

UDP_PORT = int(sys.argv[1])
UDP_IP = "0.0.0.0"  # Listen on all local interfaces

# Derive the 3-digit directory suffix (e.g., 30305 -> 305)
port_str = str(UDP_PORT)
dir_suffix = port_str[-3:] if len(port_str) >= 3 else port_str

# --- Establish Baseline Paths ---
parentdir = Path(__file__).parent.parent
logsdir = parentdir / "nmea_logs"
logsdir.mkdir(parents=True, exist_ok=True)

# Counter globals
msgcount = 0
msggood = 0

def strim(nmealat):
    """Strims off artificial precision at the end of the string"""
    st = str(nmealat)
    if len(st) < 13:
        return nmealat
    if st[10:] == "333":
        st = st[:11]
    if st[10:] == "667":
        st = st[:10] + "7"
    return float(st)

def my_now():
    return datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M:%S %Z')

def main():
    global msgcount, msggood
    
    # Set up UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((UDP_IP, UDP_PORT))
    except OSError:
        # Catch the "Address already in use" error and exit cleanly
        print(f"{my_now()} -- UDP collection instance already running on this port {UDP_PORT}", flush=True)
        sys.exit(0)
    print(f"{my_now()} ++ Listening for UDP NMEA on port {UDP_PORT}...", flush=True)

    last_day = None
    af = None
    last_raw_sentence = None  # Track the previous sentence to discard duplicates

    try:
        while True:
            # Receive UDP packet payload
            data, addr = sock.recvfrom(4096)
            
            # Feed raw bytes to NMEAReader via a virtual stream
            stream = io.BytesIO(data)
            nmr = NMEAReader(stream, quitonerror=ERR_RAISE)

            try:
                for (raw, parsed_data) in nmr:
                    if not parsed_data:
                        continue
                    
                    # --- DE-DUPLICATION CHECK ---
                    # Clean the raw string line for comparison
                    current_sentence = raw.decode('utf-8', errors='ignore').strip()
                    if current_sentence == last_raw_sentence:
                        continue  # Silently skip the duplicate transmission
                    
                    # Update memory tracking for the next incoming sentence
                    last_raw_sentence = current_sentence
                    
                    d = parsed_data.__dict__
                    
                    # Check for explicit GPS date to rotate files cleanly
                    if 'date' in d and d['date'] != "":
                        this_day = d['date']  # Format: DDMMYY
                    else:
                        this_day = "UNKNOWN_DATE"

                    # Trigger file rotation
                    if this_day != last_day or msgcount >= LONG_ENOUGH:
                        if af: af.close()
                        
                        msgcount = 0
                        last_day = this_day
                        
                        time_stamp = datetime.now(tz=TZ)
                        month_dir = time_stamp.strftime('%Y-%m')
                        file_stem = time_stamp.strftime('%Y-%m-%d_%H%M')

                        # Setup target path: e.g., parentdir / nmea_305d / 2026-06
                        target_dir = parentdir / f"nmea_{dir_suffix}d" / month_dir
                        target_dir.mkdir(parents=True, exist_ok=True)

                        output_filename = target_dir / f"{file_stem}.nmea"

                        print(f"{my_now()} ++ Rotating track log.\n -> Path: {output_filename}", flush=True)
                        
                        current_track = logsdir / f"current_nmea_file_{dir_suffix}.txt"
                        with open(current_track, 'w') as f:
                            f.write(f"nmea_{dir_suffix}d/{month_dir}/{file_stem}_{dir_suffix}.nmea")

                        # Open the single unified processed output file
                        af = open(output_filename, 'ab', buffering=FILE_BUFSIZE)

                        # SEED REQUIREMENT: Put ONE single raw GPRMC sentence at the absolute top 
                        # of the file so downstream date workflows function perfectly.
                        if parsed_data.msgID == "RMC" and af:
                            af.write(raw)
                            af.flush()

                    # Filter, rewrite, and append data into the single track log
                    if 'lat' in d and 'lon' in d and d['lat'] != "":
                        if af:
                            try:
                                # Safe string parsing directly from the raw NMEA payload byte-string
                                # This avoids float-conversion artifacts and keeps standard NMEA DDMM.
                                parts = current_sentence.split(',')
                                
                                if len(parts) >= 7 and "RMC" in parts[0]:
                                    time_field = parts[1]      # e.g., 193332.00
                                    lat_field = parts[3]       # e.g., 3731.067570
                                    ns_field = parts[4]        # N
                                    lon_field = parts[5]       # e.g., 02325.715887
                                    ew_field = parts[6]        # E
                                    
                                    # Strip trailing artificial precision if needed, matching your strim rules
                                    if len(lat_field) > 11 and lat_field.endswith("333"): lat_field = lat_field[:-2]
                                    if len(lat_field) > 11 and lat_field.endswith("667"): lat_field = lat_field[:-3] + "7"
                                    if len(lon_field) > 12 and lon_field.endswith("333"): lon_field = lon_field[:-2]
                                    if len(lon_field) > 12 and lon_field.endswith("667"): lon_field = lon_field[:-3] + "7"

                                    # Build standard native NMEA $GPGGA line template
                                    gga_payload = f"GPGGA,{time_field},{lat_field},{ns_field},{lon_field},{ew_field},1,06,1.0,0.0,M,0.0,M,,"
                                    
                                    # Compute NMEA standard XOR checksum
                                    checksum = 0
                                    for char in gga_payload:
                                        checksum ^= ord(char)
                                    
                                    gga_sentence = f"${gga_payload}*{checksum:02X}\r\n"
                                    af.write(gga_sentence.encode('utf-8'))
                                    af.flush()
                                    msggood += 1
                                    
                            except Exception as parse_err:
                                # Fallback safely if line splitting errors out
                                pass
                        
                    msgcount += 1
            except NMEAParseError:
                continue

    except KeyboardInterrupt:
        print(f"\n{my_now()} -- Stopped by Keyboard Interrupt.", flush=True)
    finally:
        if af: af.close()
        sock.close()
        sock.close()
if __name__ == "__main__":
    main()