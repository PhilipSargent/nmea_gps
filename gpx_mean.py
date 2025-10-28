import argparse
import os
import sys
import xml.etree.ElementTree as ET
import math
from datetime import datetime # Added datetime for time parsing and calculation

# GPX Namespace definition (standard for GPX 1.1 files)
GPX_NS = {'gpx': 'http://www.topografix.com/GPX/1/1'}

# --- DYNAMIC PRECISION FUNCTION ---
def get_precision_and_format(stddev, min_decimals=2):
    """
    Determines a dynamic formatting string for reporting based on standard deviation.
    The goal is to report to a precision slightly better than the variability.
    
    Precision is set to at least one decimal place beyond the first significant 
    digit of the standard deviation, ensuring a minimum of 'min_decimals'.
    """
    if stddev == 0.0:
        # Use a high fixed precision for perfect data
        precision_decimals = min_decimals + 4  
    else:
        try:
            # math.ceil(-math.log10(stddev)) gives the power of 10 of the smallest significant digit.
            # We add 1 to report one more decimal place than the error indicates.
            calculated_precision = math.ceil(-math.log10(stddev)) + 1
        except ValueError:
            # Catch exceptions for extreme values, falling back to high precision
            calculated_precision = min_decimals + 4
            
        # Ensure we always report at least min_decimals (e.g., 6 for Lat/Lon)
        precision_decimals = max(min_decimals, calculated_precision)
        
    # Return ONLY the format string (e.g., ".8f") without the leading colon
    return f".{precision_decimals}f"
# ----------------------------------

# --- PURE PYTHON STATISTICAL FUNCTIONS ---
def calculate_mean(data):
    """Calculates the arithmetic mean of a list of numbers."""
    if not data:
        return 0.0
    return sum(data) / len(data)

def calculate_stddev(data, mean):
    """
    Calculates the population standard deviation of a list of numbers.
    It uses the population formula (dividing by N).
    """
    n = len(data)
    if n <= 1:
        return 0.0
    # Variance: sum of squared differences from the mean, divided by N (population)
    variance = sum([(x - mean) ** 2 for x in data]) / n
    return math.sqrt(variance)
# ----------------------------------------

def get_xml_element_text(element, tag, namespace):
    """Safely find and return the text content of a child element, or None."""
    child = element.find(tag, namespace)
    return child.text.strip() if child is not None and child.text else None

def analyze_gpx_file(gpx_path):
    """
    Reads a GPX file, filters track points by HDOP, and calculates 
    mean and standard deviation for latitude, longitude, and elevation per segment.
    """
    print(f"--- Analyzing GPX File: {os.path.basename(gpx_path)} ---")
    
    try:
        tree = ET.parse(gpx_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error: Could not parse XML file. Details: {e}")
        return
    except FileNotFoundError:
        print(f"Error: File not found at path: {gpx_path}")
        return

    # Find all tracks
    tracks = root.findall('gpx:trk', GPX_NS)
    
    if not tracks:
        print("No <trk> elements found in the GPX file.")
        return

    # Iterate through all tracks
    for trk_idx, trk in enumerate(tracks, 1):
        trk_name = get_xml_element_text(trk, 'gpx:name', GPX_NS) or f"Track {trk_idx}"
        print(f"\n[ TRACK: {trk_name} ]")

        # Find all track segments within the current track
        segments = trk.findall('gpx:trkseg', GPX_NS)
        
        if not segments:
            print("  No <trkseg> elements found in this track.")
            continue

        # Iterate through all segments
        for seg_idx, trkseg in enumerate(segments, 1):
            
            # Data containers for the filtered points
            lat_data = []
            lon_data = []
            ele_data = []
            omissions_count = 0
            
            # Variables for time calculation
            first_valid_time_str = None
            last_valid_time_str = None
            
            # Iterate through all track points
            for pt in trkseg.findall('gpx:trkpt', GPX_NS):
                try:
                    # 1. Extract core attributes
                    lat = float(pt.attrib.get('lat'))
                    lon = float(pt.attrib.get('lon'))

                    # 2. Extract Time
                    time_text = get_xml_element_text(pt, 'gpx:time', GPX_NS)

                    # 3. Extract and check HDOP (Horizontal Dilution of Precision)
                    hdop_text = get_xml_element_text(pt, 'gpx:hdop', GPX_NS)
                    hdop = float(hdop_text) if hdop_text else 0.0 # Assume 0 if hdop tag is missing

                    # Filter condition: Omit if hdop > 4.0
                    if hdop > 4.0:
                        omissions_count += 1
                        continue
                        
                    # --- If we reach here, the point is VALID ---
                    
                    # Capture the first valid time string
                    if first_valid_time_str is None and time_text is not None:
                        first_valid_time_str = time_text
                    
                    # Always capture the last valid time string
                    if time_text is not None:
                        last_valid_time_str = time_text

                    # 4. Extract Elevation (Altitude)
                    ele_text = get_xml_element_text(pt, 'gpx:ele', GPX_NS)
                    
                    # Ensure elevation exists before trying to convert/collect
                    if ele_text is not None:
                        ele = float(ele_text)
                        lat_data.append(lat)
                        lon_data.append(lon)
                        ele_data.append(ele)
                    else:
                        # Optional: You might want to omit points without elevation too
                        pass 

                except (ValueError, TypeError, AttributeError) as e:
                    # Catch errors from missing or invalid data in a point
                    # print(f"Warning: Skipping point due to malformed data: {e}")
                    continue

            # --- Calculation and Reporting for the Segment ---
            total_points = len(lat_data)
            
            print(f"  [ SEGMENT {seg_idx} ]")
            
            # --- TIME AND DURATION REPORTING (FIXED PARSING) ---
            start_time_report = "N/A (No valid time found)"
            duration_report = "N/A"
            
            if first_valid_time_str and last_valid_time_str:
                # GPX standard time format is YYYY-MM-DDTHH:MM:SS[Z]. 
                # We use the format without the timezone designator (%z) to handle missing 'Z'.
                try:
                    # NOTE: We assume the time is UTC, as is standard for GPX files.
                    time_format = '%Y-%m-%dT%H:%M:%S'
                    
                    # Remove the 'Z' if present, then parse the simple format.
                    first_dt = datetime.strptime(first_valid_time_str.replace('Z', ''), time_format)
                    last_dt = datetime.strptime(last_valid_time_str.replace('Z', ''), time_format)
                    
                    # Calculate duration (timedelta)
                    segment_duration = last_dt - first_dt
                    
                    # Prepare reports
                    # We print the parsed time but explicitly indicate it is UTC.
                    start_time_report = first_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                    
                    # Format duration nicely: "X hours, Y minutes, Z seconds"
                    total_seconds = int(segment_duration.total_seconds())
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    duration_report = f"{hours}h {minutes}m {seconds}s"
                    
                except ValueError:
                    # Handle cases where the time string is malformed or not the expected format
                    pass
            
            print(f"    Start Time (First Valid Point): {start_time_report}")
            print(f"    Segment Duration: {duration_report}")
            
            # --- Continue with existing reporting ---
            
            print(f"    Points Analyzed (HDOP ≤ 4.0): {total_points}")
            print(f"    Points Omitted (HDOP > 4.0): {omissions_count}")
            
            if total_points > 0:
                # Calculate means and standard deviations
                mean_lat = calculate_mean(lat_data)
                mean_lon = calculate_mean(lon_data)
                mean_ele = calculate_mean(ele_data)
                
                stddev_lat = calculate_stddev(lat_data, mean_lat)
                stddev_lon = calculate_stddev(lon_data, mean_lon)
                stddev_ele = calculate_stddev(ele_data, mean_ele)

                # Dynamic Formatting Setup: Lat/Lon usually requires 6+ decimals, Ele 2+
                lat_lon_format = get_precision_and_format(stddev_lat, min_decimals=6)
                ele_format = get_precision_and_format(stddev_ele, min_decimals=2)
                
                # Calculate Confidence Intervals (Mean +/- 2 StdDev)
                lat_ci_low = mean_lat - 2 * stddev_lat
                lat_ci_high = mean_lat + 2 * stddev_lat
                
                lon_ci_low = mean_lon - 2 * stddev_lon
                lon_ci_high = mean_lon + 2 * stddev_lon
                
                ele_ci_low = mean_ele - 2 * stddev_ele
                ele_ci_high = mean_ele + 2 * stddev_ele


                print("    --- Statistics ---")
                
                # Report Latitude 
                print(f"      Latitude (lat): Mean={mean_lat:{lat_lon_format}}, StdDev={stddev_lat:{lat_lon_format}}")
                print(f"        (Mean ± 2 StdDev): {lat_ci_low:{lat_lon_format}} to {lat_ci_high:{lat_lon_format}}")
                
                # Report Longitude 
                print(f"      Longitude (lon): Mean={mean_lon:{lat_lon_format}}, StdDev={stddev_lon:{lat_lon_format}}")
                print(f"        (Mean ± 2 StdDev): {lon_ci_low:{lat_lon_format}} to {lon_ci_high:{lat_lon_format}}")

                # Report Altitude 
                print(f"      Altitude (ele): Mean={mean_ele:{ele_format}} m, StdDev={stddev_ele:{ele_format}} m")
                print(f"        (Mean ± 2 StdDev): {ele_ci_low:{ele_format}} m to {ele_ci_high:{ele_format}} m")
            else:
                print("    No valid points remained after filtering.")
                
            print("-" * 30)

def main():
    """Parses command-line arguments and initiates the analysis."""
    # A simple check to ensure math is available (should always be true)
    if 'math' not in sys.modules:
        try:
            import math 
        except ImportError:
            print("Error: The built-in 'math' library is required but failed to import.")
            sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Calculate mean/stddev of GPX track segments, omitting high-HDOP points."
    )
    parser.add_argument(
        "gpx_file",
        help="Path to the GPX file (.gpx) to analyze."
    )
    
    args = parser.parse_args()
    analyze_gpx_file(args.gpx_file)

if __name__ == "__main__":
    main()
