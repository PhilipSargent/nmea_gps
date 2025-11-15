import argparse
import os
import sys
import xml.etree.ElementTree as ET
import math
from datetime import datetime

# git@github.com:PhilipSargent/nmea_gps.git

# GPX Namespace definition (standard for GPX 1.1 files)
GPX_NS = {'gpx': 'http://www.topografix.com/GPX/1/1'}
# Register the namespace for clean output
ET.register_namespace('', GPX_NS['gpx'])

# Earth constant: Mean Earth Radius in meters (for Haversine formula)
EARTH_RADIUS_M = 6371000.0 

# --- UTILITY FUNCTIONS ---

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculates the distance (in meters) between two GPS points using 
    the Haversine formula.
    """
    # Convert degrees to radians
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Haversine formula
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = EARTH_RADIUS_M * c
    return distance

def parse_gpx_time(time_str):
    """Parses a standard GPX time string (YYYY-MM-DDTHH:MM:SS[Z])."""
    if not time_str:
        return None
    # Use the format that works for timestamps with or without the trailing 'Z'
    # .replace('Z', '') handles the 'Z'. We try to handle milliseconds/microseconds
    # often present in timestamps (e.g., '...:SS.mmm')
    time_str_clean = time_str.replace('Z', '')
    
    try:
        # Try parsing with microseconds
        return datetime.strptime(time_str_clean, '%Y-%m-%dT%H:%M:%S.%f')
    except ValueError:
        try:
            # Fallback to parsing without microseconds
            return datetime.strptime(time_str_clean, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            return None

def reformat_point_timestamp(point):
    """
    Finds the <time> element within a trkpt, reformats the timestamp string,
    and replaces the element to ensure no lingering Z/timezone artifacts remain.
    (Kept for consistency with required output format from previous fixes)
    """
    # Use a list comprehension to safely find the time element and its index
    time_info = [(i, child) for i, child in enumerate(point) if child.tag == '{http://www.topografix.com/GPX/1/1}time']
    
    if time_info:
        index, time_element = time_info[0]
        
        if time_element.text:
            dt_obj = parse_gpx_time(time_element.text)
            
            if dt_obj:
                # Get the new formatted string (explicitly no Z/offset)
                new_time_str = dt_obj.strftime('%Y-%m-%dT%H:%M:%S')
                
                # Create a brand new <time> element
                new_time_element = ET.Element('{http://www.topografix.com/GPX/1/1}time')
                new_time_element.text = new_time_str
                
                # Preserve tail for indentation
                new_time_element.tail = time_element.tail
                
                # Replace the old element with the new one
                point[index] = new_time_element

def add_name_and_print(segment_element, count, reason):
    """
    Creates and inserts the <name> element into the segment, and prints 
    the result to the console.
    """
    name = f"Segment {count} ({reason})"
    name_element = ET.SubElement(segment_element, '{http://www.topografix.com/GPX/1/1}name')
    name_element.text = name
    # The tail ensures the subsequent <trkpt> starts on a new line with 6 spaces indentation
    name_element.tail = '\n      ' 
    print(f"    - NEW SEGMENT STARTED: {name}")
    return name

# --- MAIN LOGIC ---

def process_gpx_file(gpx_path, box_distance_m):
    """
    Combines segments and re-segments each track based on the 'box' criterion:
    a segment breaks if the distance between two consecutive points exceeds the box distance.
    """
    print(f"--- Processing GPX File: {os.path.basename(gpx_path)} ---")
    print(f"Contiguity distance threshold: {box_distance_m:.2f} meters (Break if distance > threshold)")

    try:
        tree = ET.parse(gpx_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error: Could not parse XML file. Details: {e}")
        return
    except FileNotFoundError:
        print(f"Error: File not found at path: {gpx_path}")
        return

    tracks = root.findall('gpx:trk', GPX_NS)
    
    if not tracks:
        print("No <trk> elements found. Nothing to re-segment.")
        return

    total_segments_created = 0

    for trk_idx, trk in enumerate(tracks):
        # 1. Combine all existing <trkseg> points into one list
        all_points = []
        old_segments = trk.findall('gpx:trkseg', GPX_NS)
        
        # Remove all old segments from the XML tree before processing
        for seg in old_segments:
            all_points.extend(seg.findall('gpx:trkpt', GPX_NS))
            trk.remove(seg) 
        
        if not all_points:
            print(f"[ Track {trk_idx + 1} ] No points found. Skipping.")
            continue

        # Reformat all timestamps for consistent output format
        for point in all_points:
            reformat_point_timestamp(point)

        print(f"[ Track {trk_idx + 1} ] Original points: {len(all_points)}. Segmenting by proximity...")
        
        # 2. Re-segmentation Logic
        new_segment = ET.Element('{http://www.topografix.com/GPX/1/1}trkseg')
        # Force the first child (<name>) to be indented on a new line (6 spaces)
        new_segment.text = '\n      '
        current_segment_count = 1
        
        # Initialize the first segment's name immediately
        segment_start_reason = "Continuous (Start of Track)"
        add_name_and_print(new_segment, current_segment_count, segment_start_reason)

        # Add the first point to the new segment
        if all_points:
            new_segment.append(all_points[0])
            # Set tail for the first point to ensure the next point is indented
            all_points[0].tail = '\n      '

        
        for i in range(1, len(all_points)):
            current_pt = all_points[i]
            prev_pt = all_points[i-1]
            
            # Extract point data
            lat1 = float(prev_pt.attrib.get('lat', 0))
            lon1 = float(prev_pt.attrib.get('lon', 0))
            lat2 = float(current_pt.attrib.get('lat', 0))
            lon2 = float(current_pt.attrib.get('lon', 0))
            
            # Check for break: distance between consecutive points
            distance = haversine(lat1, lon1, lat2, lon2)

            break_segment = (distance > box_distance_m)

            # If a break is detected, close the current segment and start a new one
            if break_segment:
                
                segment_break_reason = f"Distance Gap ({distance:.2f} m)"
                
                # 1. Append the closed segment 
                # Fix indentation for the closing </trkseg> tag: last point's tail must be parent's indentation (4 spaces)
                prev_pt.tail = '\n    ' 
                trk.append(new_segment)
                
                # 2. Start a new segment
                current_segment_count += 1
                segment_start_reason = f"Break: {segment_break_reason}"
                
                # 3. Start the new segment (Element, Text, Name, Print)
                new_segment = ET.Element('{http://www.topografix.com/GPX/1/1}trkseg')
                new_segment.text = '\n      ' # Indent first child
                add_name_and_print(new_segment, current_segment_count, segment_start_reason)
            
            # 4. Add the current point to the (new or existing) segment
            new_segment.append(current_pt)
            # Set tail for current point to push the next item to a new line
            current_pt.tail = '\n      ' 

        # 3. Append the last segment (unless it's empty)
        if len(new_segment.findall('gpx:trkpt', GPX_NS)) > 0:
            
            # Fix indentation for the closing </trkseg> tag: 
            # The last point's tail must be set to the parent's indentation (4 spaces)
            last_pt = new_segment.findall('gpx:trkpt', GPX_NS)[-1]
            last_pt.tail = '\n    '
            
            trk.append(new_segment)
            total_segments_created += current_segment_count
        else:
             # Only count the segments that were actually created and appended
             total_segments_created += current_segment_count - 1 

        print(f"  -> Track resegmented into {current_segment_count} new segments.")

    # 4. Write the modified XML to a new file
    output_path = write_gpx_file(gpx_path, tree)
    print(f"\nSuccessfully created {total_segments_created} new segments.")
    print(f"Output written to: {output_path}")

def write_gpx_file(original_path, tree):
    """
    Constructs the output filename, writes the modified XML tree, 
    and performs a final string-level cleanup to remove unwanted timezone offsets.
    """
    # Use 'boxsegmented' instead of 'resegmented' for the new file name
    base, ext = os.path.splitext(original_path)
    output_path = f"{base}_boxsegmented{ext}"
    
    # 1. Serialize the ElementTree to a string
    # ElementTree often adds timezone information like +00:00Z automatically.
    xml_string_bytes = ET.tostring(tree.getroot(), encoding='utf-8', xml_declaration=True)
    xml_string = xml_string_bytes.decode('utf-8')
    
    # 2. FIX: Perform string replacements to force the exact required format (YYYY-MM-DDTHH:MM:SS)
    # This aggressively removes the unwanted timezone data from the end of the time tag content.
    xml_string = xml_string.replace('+00:00Z</time>', '</time>')
    xml_string = xml_string.replace('Z</time>', '</time>')
    
    # 3. Write the cleaned string to the output file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_string)
        
    return output_path

def main():
    """Parses command-line arguments and initiates the process."""
    if 'math' not in sys.modules:
        print("Error: The built-in 'math' library is required but failed to import.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Reads a GPX file, merges all track segments, and re-segments based on proximity (points must be within a 'box' distance of each other)."
    )
    parser.add_argument(
        "gpx_file",
        help="Path to the input GPX file (.gpx)."
    )
    # New argument for box distance, defaulting to 10.0 meters
    parser.add_argument(
        "--box-distance",
        type=float,
        default=10.0, 
        help="Maximum distance in METERS between consecutive track points for them to remain in the same segment. Default: 10.0 meters."
    )
    
    args = parser.parse_args()
    
    process_gpx_file(args.gpx_file, args.box_distance)

if __name__ == "__main__":
    main()
