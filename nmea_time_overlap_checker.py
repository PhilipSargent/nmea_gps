import os
from pathlib import Path

def format_duration(seconds):
    """Converts a duration in seconds into Hh Mm Ss format."""
    seconds = int(seconds)
    if seconds < 0:
        return "N/A" # Should not happen with valid GPX
        
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    # Include minutes if there are hours, or if minutes > 0
    if minutes > 0 or (hours > 0 and secs == 0):
        parts.append(f"{minutes}m")
    # Only include seconds if no hours/minutes, or if secs > 0
    if secs > 0 or (not hours and not minutes): 
        parts.append(f"{secs}s")
    
    return " ".join(parts)
    
def get_seconds_since_midnight(nmea_time_str):
    """
    Converts an NMEA time string (e.g., '123519.00') into total seconds since midnight.
    NMEA time is HHMMSS.ss.
    """
    try:
        # Strip fractional seconds if present, as datetime.time only stores up to microseconds
        if '.' in nmea_time_str:
            t_str = nmea_time_str.split('.')[0]
        else:
            t_str = nmea_time_str
        
        # HHMMSS format
        hour = int(t_str[0:2])
        minute = int(t_str[2:4])
        second = int(t_str[4:6])
        
        # Total seconds since midnight
        return (hour * 3600) + (minute * 60) + second
    except ValueError:
        # Return None if the time string is malformed
        return None
        
def format_nmea_timestamp(t_str):
        hour = int(t_str[0:2])
        minute = int(t_str[2:4])
        second = int(t_str[4:6])
        return f"{hour:02}:{minute:02}:{second:02}"

def get_nmea_date(filepath):
    """
    Reads the file and extracts the date (DDMMYY) from the first GPRMC sentence.
    ddmmyy	Date in day, month, year format
    $GPRMC,000001.00,A,3731.08693,N,02325.72333,E,0.107,,021125,,,A*70 => 02/11/2025
      
    Returns:
        The date string (DDMMYY) or None if not found.
    """
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                # Check for GPRMC sentence
                if line.startswith('$GPRMC'):
                    
                    parts = line.split(',')
                    # Date is field 9 (index 9)
                    if len(parts) > 9 and parts[9]:
                        return parts[9].split('.')[0] # DDMMYY string
                        # return parts[9] # DDMMYY string
        return None
    except IOError:
        return None
        
def same_day(file_a, file_b):
    """every .nmea file SHOULD be all within a single UTC day.
     """    
    # if file_a.name[:10] == file_b.name[:10]:
       # return True
    if get_nmea_date(file_a) == get_nmea_date(file_b):
        return True
    return False
              
     
        
def get_file_time_range(filepath):
    """
    Reads an NMEA file and finds the minimum and maximum time (in seconds
    since midnight) contained within its data.
    
    BUT the lines are in time SEQUENCE and Must/should-not go backwards
    but we do often have:
    $GPRMC,000001.00,A,3731.08693,N,02325.72333,E,0.107,,021125,,,A*70
    $GPGGA,235958.00,3731.08672,N,02325.72359,E,1,08,1.17,1.8,M,32.5,M,,*5F
    $GPGGA,000005.00,3731.08717,N,02325.72305,E,1,08,1.17,1.1,M,32.5,M,,*58
    $GPGGA,000011.00,3731.08760,N,02325.72262,E,1,09,0.91,0.4,M,32.5,M,,*57
    
    where the new day file has a glitch of getting a timestamp from the UTC day before. 
    We should ignore any glitch.
    
    DOES NOT YET check that the first line and last line are in sequence, 
    or that the file as a whole is in sequence.
    Returns:
        (min_seconds, max_seconds) tuple, or None if no valid time data is found.
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found at path: {filepath}")
        return None

    min_time_s = float('inf')
    max_time_s = -float('inf')
    
    times = []
    stamps = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                # Basic check for NMEA sentence start and minimum length
                if not line.startswith('$') or len(line) < 10:
                    continue
                
                # NMEA time is typically the 2nd field (index 1)
                parts = line.split(',')
                if len(parts) < 2:
                    continue
                    
                time_str = parts[1]
                current_time_s = get_seconds_since_midnight(time_str)
                times.append(current_time_s)
                stamps.append(time_str)

    except IOError as e:
        print(f"I/O error reading {filepath}: {e}")
        return None, None
        
    ordered = (int(times[0]), int(times[-1]))    
    stamp_pair = (format_nmea_timestamp(stamps[0]), format_nmea_timestamp(stamps[-1]))
    return ordered, stamp_pair



def check_ranges(filepaths):
    """
    Checks whether the time range of any file overlaps with the time range 
    of any other file in the provided list.
    
    USES NMEA date, not filestamp date, for each file.
    By construction, each .nmea file is within a single "UTC day"
    
    Returns:
        True if all files are disjoint in time, False otherwise.
    """
    if filepaths:
        dir_name = filepaths[0].name[:7]
    else:
        return False
        
    file_ranges = {}
    paths ={}
    stamp_pairs = {}
    # First pass: Calculate time range for every file
    for fp in filepaths:
        range_data, stamp_pair = get_file_time_range(fp)
        if range_data is None:
            print(f"Warning: File '{fp.name}' contains no parseable time data and will be skipped.")
            continue
        file_ranges[fp] = range_data
        stamp_pairs[fp.name] = stamp_pair
        paths[fp.name] = fp
        
    if len(file_ranges) < 2:
        print(f"Not enough files in {dir_name} with valid time data to check for overlaps.")
        return True
        
    # Second pass: Check for overlaps (compare every unique pair)
    files = list(file_ranges.keys())
    has_overlap = False
    
    includes = {}
    for fp in filepaths:
        includes[fp.name] = set()
        
    for i in range(len(files)):
        
        for j in range(i + 1, len(files)):
            file_a = files[i]
            file_b = files[j]
            # are these the same day?
            if not same_day(file_a, file_b):
                # skip overlap detection if they are different UTC days
                continue
            
            # Range A is (start_A, end_A)
            start_A, end_A = file_ranges[file_a]
            # Range B is (start_B, end_B)
            start_B, end_B = file_ranges[file_b]
            
            has_inclusion = False
            # Overlap condition:
            # Overlap occurs if (A starts before B ends) AND (B starts before A ends).
            if start_A < end_B and start_B < end_A:
                has_overlap = True
                overlap = end_A - start_B
                                
                # Case 1: File A completely includes File B
                # A starts before or at B's start AND B ends before or at A's end
                if start_A <= start_B and end_B <= end_A:
                    has_inclusion = True
                    includes[file_a.name].add(file_b.name)
                    #print(f"--> INCLUSION REPORT: File {file_a.name} COMPLETELY INCLUDES the time range of File {file_b.name}.")
                
                # Case 2: File B completely includes File A
                # B starts before or at A's start AND A ends before or at B's end
                elif start_B <= start_A and end_A <= end_B:
                    has_inclusion = True
                    includes[file_b.name].add(file_a.name)
                    #print(f"--> INCLUSION REPORT: File {file_b.name} COMPLETELY INCLUDES the time range of File {file_a.name}.")
                    
                if has_inclusion:
                    pass
                else:
                    print(f"\n--- OVERLAP DETECTED --- {format_duration(overlap)}")
                    print(f"   {file_a.name} ({start_A}s to {end_A}s) {stamp_pairs[file_a.name]} {format_duration(end_A-start_A)}")
                    print(f"   {file_b.name} ({start_B}s to {end_B}s) {stamp_pairs[file_b.name]} {format_duration(end_B-start_B)}")

    all_empty = all(not inc for inc in includes.values())
    if not all_empty:
        print(f"\n--> INCLUSION REPORTS")
        for inc in includes:
            if includes[inc]:
                print(f"   {inc} {file_ranges[paths[inc]]} {stamp_pairs[inc]} COMPLETELY INCLUDES:")
                for f in sorted(list(includes[inc])):
                    start, end = file_ranges[paths[f]]
                    duration = format_duration(end - start)
                    print("  ",f, file_ranges[paths[f]], stamp_pairs[f], duration)
                print("")

    if not has_overlap:
        pass
        # print("Success: No time overlaps were detected between any pair of files.")
        
    return not has_overlap


# --- Example Setup and Usage ---
def get_file_time_strings(filepath):
    """
    Reads an NMEA file and finds the minimum and maximum time strings
    contained within its data.
    
    Returns:
        (min_time_str, max_time_str) tuple, or None if no valid time data is found.
    """
    if not os.path.exists(filepath):
        return None

    min_time_str = None
    max_time_str = None
    
    # We use time in seconds for the comparison logic, but store the string
    min_time_s = float('inf')
    max_time_s = -float('inf')
    
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('$') or len(line) < 10:
                    continue
                    
                parts = line.split(',')
                if len(parts) < 2:
                    continue
                    
                time_str = parts[1].split('.')[0] # Use only HHMMSS part for simple comparison
                current_time_s = get_seconds_since_midnight(time_str)
                
                if current_time_s is not None:
                    if current_time_s < min_time_s:
                        min_time_s = current_time_s
                        min_time_str = time_str
                    
                    if current_time_s > max_time_s:
                        max_time_s = current_time_s
                        max_time_str = time_str

    except IOError:
        return None
        
    if min_time_str is None:
        return None
        
    # Return the minimum and maximum time strings found in the file
    return (min_time_str, max_time_str)
    
def create_dummy_nmea_file(filename, start_time, end_time):
    """
    Creates a dummy NMEA file with specified start and end times
    and verifies that the minimum and maximum time strings extracted from the 
    file match the input strings.
    """
    # 1. Create the file content with the specified start and end times
    content = [
        f"$GPGGA,{start_time},4807.000,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",
        f"$GPRMC,{start_time},A,4807.000,N,01131.000,E,022.4,084.4,230394,003.1,W*6A",
        f"$GPVTG,054.7,T,034.4,M,005.5,N,010.2,K,A*58",
        f"$GPGGA,{end_time},4807.001,N,01131.001,E,1,08,0.9,545.4,M,46.9,M,,*47",
    ]
    with open(filename, 'w') as f:
        f.write('\n'.join(content))
    print(f"Created file: {filename} (Requested Range: {start_time} to {end_time})")

    # Verification Logic Start
    
    # 1. Get actual min/max time strings from the file
    actual_range_strs = get_file_time_strings(filename)
    
    # 2. Define the expected time strings (using the input arguments)
    expected_range_strs = (start_time.split('.')[0], end_time.split('.')[0])
    
    # 3. Verify
    if actual_range_strs is None:
        print("Verification FAILED: Could not extract time strings from the created file.")
    elif actual_range_strs == expected_range_strs:
        # print(f"Verification SUCCESS: Actual range strings {actual_range_strs} match expected {expected_range_strs}")
        pass
    else:
        print(f"Verification FAILED: Actual range strings {actual_range_strs} DOES NOT match expected {expected_range_strs}")
        
    # Verification Logic End
    

if __name__ == "__main__":
    FILE_A = Path("log_a.nmea") # Range: 10:00:00 (NMEA: 100000) to 10:00:10 (NMEA: 100010)
    FILE_B = Path("log_b.nmea") # Range: 10:00:05 (NMEA: 100005) to 10:00:15 (NMEA: 100015) (OVERLAPS with A)
    FILE_C = Path("log_c.nmea") # Range: 10:00:20 (NMEA: 100020) to 10:00:30 (NMEA: 100030) (DISJOINT from A and B)

    # Create test files
    create_dummy_nmea_file(FILE_A, "100000", "100010") 
    create_dummy_nmea_file(FILE_B, "100005", "100015")
    create_dummy_nmea_file(FILE_C, "100020", "100030")

    print("\n--- Running Overlap Check ---")
    
    test_files = [FILE_A, FILE_B, FILE_C]
    are_disjoint = check_ranges(test_files)
    
    print(f"\nFinal Result: All files are disjoint: {are_disjoint}")

    # Cleanup test files
    for f in test_files:
        if os.path.exists(f):
            os.remove(f)