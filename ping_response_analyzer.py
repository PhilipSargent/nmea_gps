import re
from datetime import datetime, timedelta

def analyze_ping_failures(log_content):
    """
    Analyzes log content to report periods when the device did not respond to a ping.

    A failure period starts when '## Does not respond to ping.' is logged.
    It ends when EITHER '++ OK ping response.' is logged, OR the bare line 'Writing' 
    is encountered, using the timestamp of the line immediately preceding 'Writing'.

    Args:
        log_content (str): The entire content of the log file.

    Returns:
        list: A list of dictionaries, each describing a failure period.
    """
    # Regex to capture the timestamp, timezone, and the status message.
    # Group 1: Full timestamp (YYYY-MM-DD HH:MM:SS)
    # Group 2: Timezone (e.g., EET)
    # Group 3: The rest of the line (status message)
    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ([A-Z]{3}) (.*)$")

    failure_start = None
    failure_tz = None
    failure_periods = []
    
    last_known_time = None
    last_known_tz = None
    
    FAILURE_MARKER = "## Does not respond to ping."
    WRITING_MARKER = "Writing"

    for line in log_content.splitlines():
        match = log_pattern.match(line)
        
        if match:
            # This is a timestamped log line
            timestamp_str, tz, message = match.groups()
            current_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            
            # Update last known time for non-timestamped lines that might follow
            last_known_time = current_time
            last_known_tz = tz

            # --- 1. Detect Failure Start ---
            if FAILURE_MARKER in message:
                if failure_start is None:
                    failure_start = current_time
                    failure_tz = tz
                continue 

            # --- 2. Detect Success/End of Failure (Condition A: OK Ping) ---
            if "++ OK ping response." in message:
                if failure_start is not None:
                    end_time = current_time
                    duration = end_time - failure_start
                    
                    failure_periods.append({
                        "start": failure_start.strftime("%Y-%m-%d %H:%M:%S") + f" {failure_tz}",
                        "end": end_time.strftime("%Y-%m-%d %H:%M:%S") + f" {tz}",
                        "duration": str(duration),
                        "duration_seconds": duration.total_seconds()
                    })
                    failure_start = None
                    failure_tz = None
                
                continue
        
        # --- 2. Detect Success/End of Failure (Condition B: Bare Writing line) ---
        elif line.strip() == WRITING_MARKER:
            if failure_start is not None and last_known_time is not None:
                # We use the last recorded time as the end time for this untimestamped marker
                end_time = last_known_time
                tz = last_known_tz
                duration = end_time - failure_start
                
                failure_periods.append({
                    "start": failure_start.strftime("%Y-%m-%d %H:%M:%S") + f" {failure_tz}",
                    "end": end_time.strftime("%Y-%m-%d %H:%M:%S") + f" {tz}",
                    "duration": str(duration),
                    "duration_seconds": duration.total_seconds()
                })
                failure_start = None
                failure_tz = None
            
            continue # Continue iterating through the rest of the lines


    # --- 3. Handle Ongoing Failure ---
    if failure_start is not None:
        failure_periods.append({
            "start": failure_start.strftime("%Y-%m-%d %H:%M:%S") + f" {failure_tz}",
            "end": "Ongoing/Log End",
            "duration": "N/A",
            "duration_seconds": float('inf')
        })

    return failure_periods

def print_report(periods):
    """Prints a structured report of the failure periods."""
    if not periods:
        print("\n--- Analysis Complete ---")
        print("No 'Does not respond to ping.' periods were found in the log.")
        return

    print("\n--- Ping Response Failure Report (OK Ping or Writing Marker End) ---")
    print(f"{'Start Time':<25} | {'End Time':<25} | {'Duration'}")
    print("-" * 80)
    
    total_seconds = 0
    
    for period in periods:
        duration_display = period['duration']
        
        if period['duration_seconds'] != float('inf'):
            total_seconds += period['duration_seconds']
        else:
            duration_display = "Ongoing"
            
        print(f"{period['start']:<25} | {period['end']:<25} | {duration_display}")
    
    # Convert total seconds to H:M:S format for a summary
    total_duration_display = str(timedelta(seconds=total_seconds))
    
    print("-" * 80)
    print(f"Total cumulative down time (excluding 'Ongoing'): {total_duration_display}")
    print("----------------------------------------------------------\n")

# Main execution block
if __name__ == "__main__":
    log_file_path = "nmealogger_ok.txt"
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            log_content = f.read()
            
        failure_periods = analyze_ping_failures(log_content)
        print_report(failure_periods)

    except FileNotFoundError:
        print(f"Error: The file '{log_file_path}' was not found. Please ensure it is available.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")