import os

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

def get_file_time_range(filepath):
    """
    Reads an NMEA file and finds the minimum and maximum time (in seconds
    since midnight) contained within its data.
    
    Returns:
        (min_seconds, max_seconds) tuple, or None if no valid time data is found.
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found at path: {filepath}")
        return None

    min_time_s = float('inf')
    max_time_s = -float('inf')
    
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
                
                if current_time_s is not None:
                    min_time_s = min(min_time_s, current_time_s)
                    max_time_s = max(max_time_s, current_time_s)

    except IOError as e:
        print(f"I/O error reading {filepath}: {e}")
        return None
        
    if min_time_s == float('inf'):
        return None
        
    return (int(min_time_s), int(max_time_s))


def check_ranges(filepaths):
    """
    Checks whether the time range of any file overlaps with the time range 
    of any other file in the provided list.
    
    Returns:
        True if all files are disjoint in time, False otherwise.
    """
    file_ranges = {}
    
    # First pass: Calculate time range for every file
    for fp in filepaths:
        range_data = get_file_time_range(fp)
        if range_data is None:
            print(f"Warning: File '{fp}' contains no parseable time data and will be skipped.")
            continue
        file_ranges[fp] = range_data
        
    if len(file_ranges) < 2:
        print("Not enough files with valid time data to check for overlaps.")
        return True
        
    # Second pass: Check for overlaps (compare every unique pair)
    files = list(file_ranges.keys())
    has_overlap = False
    
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            file_a = files[i]
            file_b = files[j]
            
            # Range A is (start_A, end_A)
            start_A, end_A = file_ranges[file_a]
            # Range B is (start_B, end_B)
            start_B, end_B = file_ranges[file_b]
            
            # Overlap condition:
            # Overlap occurs if (A starts before B ends) AND (B starts before A ends).
            if start_A < end_B and start_B < end_A:
                has_overlap = True
                print("\n--- OVERLAP DETECTED ---")
                print(f"File A: {file_a} (Range: {start_A}s to {end_A}s)")
                print(f"File B: {file_b} (Range: {start_B}s to {end_B}s)")
                
    if not has_overlap:
        print("\nSuccess: No time overlaps were detected between any pair of files.")
        
    return not has_overlap


# --- Example Setup and Usage ---

def create_dummy_nmea_file(filename, start_time, end_time):
    """
    Creates a dummy NMEA file with specified start and end times
    and verifies that the minimum and maximum time strings extracted from the 
    file match the input strings.
    """
    # 1. Create the file content with the specified start and end times
    content = [
        f"$GPGGA,{start_time},4807.000,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",
        f"$GPRMC,123519,A,4807.000,N,01131.000,E,022.4,084.4,230394,003.1,W*6A",
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
        print(f"Verification SUCCESS: Actual range strings {actual_range_strs} match expected {expected_range_strs}")
    else:
        print(f"Verification FAILED: Actual range strings {actual_range_strs} DOES NOT match expected {expected_range_strs}")
        
    # Verification Logic End
    

if __name__ == "__main__":
    FILE_A = "log_a.nmea" # Range: 10:00:00 to 10:00:10
    FILE_B = "log_b.nmea" # Range: 10:00:05 to 10:00:15 (OVERLAPS with A)
    FILE_C = "log_c.nmea" # Range: 10:00:20 to 10:00:30 (DISJOINT from A and B)

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