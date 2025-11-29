import os

"""MUST make sure that teh file does not contain lines from a 
different UTC DATE before doing this !

ie MUST remove anything at LINE 2 which is the PREVIOUS DAY, e.g. 235953.3 
when everything is starting at 000000.1

MUST DETECT if this bogus previous day line is GPRMC which has the DATE, as that woukd then be
quiet wrong.
"""

def read_file_lines(filepath):
    """
    Reads a file into a list of strings, stripping leading/trailing whitespace.
    Returns an empty list if the file is not found.
    """
    try:
        # Use 'r' for read mode and 'with open' for safe file handling
        with open(filepath, 'r') as f:
            # Use a list comprehension to strip the newline from each line
            lines = [line.strip() for line in f]
            return lines
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return []
    except Exception as e:
        print(f"An error occurred reading the file: {e}")
        return []


def sort_nmea_lines_by_timestamp(lines):
    """
    Sorts a list of NMEA sentences based on the time field (the second field, index 1).
    
    Args:
        lines (list): A list of strings, where each string is an NMEA sentence.
        
        
    This will do something stupid for $GPGLL which have a lat long but NO TIMESTAMP,
    they should be preserved in th eposition in the file, not sorted.
        
    Returns:
        list: The sorted list of NMEA sentences.
    """
    def get_sort_key(line):
        """
        The key function used by list.sort() to extract the time for comparison.
        NMEA sentences are comma-delimited, and the time (UTC) is the second field (index 1).
        Example: '$GPGGA,123519.23,4807.038,N,...' -> '123519.23'
        """
        try:
            # 1. Split the line by comma
            parts = line.split(',')
            
            # 2. Check if the line has enough fields and starts with '$'
            # We need at least 2 fields (Type, Time)
            if len(parts) >= 2 and parts[0].startswith('$'):
                # Return the second element (index 1), which is the time string
                return parts[1]
            
            # 3. Handle invalid or non-NMEA lines
            # Non-valid lines are sorted to the end by returning a value that is lexicographically large
            return "Z" * 10 
            
        except Exception:
            # Catch all exceptions (e.g., malformed line)
            return "Z" * 10

    # The sorted() function creates a new sorted list, leaving the original list unchanged.
    # The sort is lexicographical (string comparison), which works perfectly for HHMMSS.ss format.
    # For example, "100000" < "100005" < "120000".
    sorted_lines = sorted(lines, key=get_sort_key)
    return sorted_lines


# --- Example Usage ---

if __name__ == "__main__":
    # Create a dummy file with lines out of order
    DUMMY_FILE = "unsorted_data.nmea"
    
    # Time field i
    unsorted_content = [
        # Line 1: Early time
        "$GPGGA,090000.01,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",
        # Line 2: Late time
        "$GPGGA,113000.00,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",
        # Line 3: Time between 1 and 2
        "$GPGGA,101530.00,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",
        # Line 4: Invalid line (should be sorted to the end)
        "This is a comment line.",
        # Line 5: Earliest time
        "$GPGGA,090000.00,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",
    ]
    
    with open(DUMMY_FILE, 'w') as f:
        f.write('\n'.join(unsorted_content))
    
    print(f"--- Original lines read from {DUMMY_FILE} ---")
    
    # 1. Read the file into a list
    all_lines = read_file_lines(DUMMY_FILE)
    for i, line in enumerate(all_lines):
        # Only print the first 20 characters for clean display
        print(f"[{i:3d}] {line[:20]:20s}...") 
        
    print("\n--- Sorted lines by NMEA Timestamp (Field 2) ---")
    
    # 2. Sort the lines
    sorted_lines = sort_nmea_lines_by_timestamp(all_lines)
    
    # 3. Print the sorted lines
    for i, line in enumerate(sorted_lines):
        print(f"[{i:3d}] {line[:20]:20s}...")
        
    # Cleanup
    os.remove(DUMMY_FILE)