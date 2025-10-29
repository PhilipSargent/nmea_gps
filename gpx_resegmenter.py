import argparse
import os
import sys
import xml.etree.ElementTree as ET
import math
from datetime import datetime

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
    try:
        return datetime.strptime(time_str.replace('Z', ''), '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        return None

def get_xml_element_text(element, tag, namespace):
    """Safely find and return the text content of a child element, or None."""
    child = element.find(tag, namespace)
    return child.text.strip() if child is not None and child.text else None

# --- MAIN LOGIC ---

def process_gpx_file(gpx_path, max_time_gap_sec, max_distance_gap_m):
    """
    Combines segments and re-segments each track based on time and distance gaps.
    """
    print(f"--- Processing GPX File: {os.path.basename(gpx_path)} ---")
    print(f"Time break threshold: > {max_time_gap_sec/3600:.1f} hours")
    print(f"Distance break threshold: > {max_distance_gap_m:.2f} meters")

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

        print(f"[ Track {trk_idx + 1} ] Original points: {len(all_points)}. Segmenting...")
        
        # 2. Re-segmentation Logic
        new_segment = ET.Element('{http://www.topografix.com/GPX/1/1}trkseg')
        # Add the first point to the new segment
        if all_points:
            new_segment.append(all_points[0])

        current_segment_count = 1
        points_in_segment = 1
        
        for i in range(1, len(all_points)):
            current_pt = all_points[i]
            prev_pt = all_points[i-1]
            
            # Extract point data
            lat1 = float(prev_pt.attrib.get('lat', 0))
            lon1 = float(prev_pt.attrib.get('lon', 0))
            lat2 = float(current_pt.attrib.get('lat', 0))
            lon2 = float(current_pt.attrib.get('lon', 0))
            
            time1_str = get_xml_element_text(prev_pt, 'gpx:time', GPX_NS)
            time2_str = get_xml_element_text(current_pt, 'gpx:time', GPX_NS)

            break_segment = False

            # Check 1: Time Gap (if times are valid)
            time1 = parse_gpx_time(time1_str)
            time2 = parse_gpx_time(time2_str)
            
            if time1 and time2 and time2 > time1:
                time_difference = (time2 - time1).total_seconds()
                if time_difference > max_time_gap_sec:
                    break_segment = True
                    # print(f"  -> Break at index {i}: Time gap of {time_difference:.0f}s")

            # Check 2: Distance Gap
            distance = haversine(lat1, lon1, lat2, lon2)
            if distance > max_distance_gap_m:
                break_segment = True
                # print(f"  -> Break at index {i}: Distance gap of {distance:.2f}m")

            # If a break is detected, close the current segment and start a new one
            if break_segment:
                trk.append(new_segment)
                new_segment = ET.Element('{http://www.topografix.com/GPX/1/1}trkseg')
                current_segment_count += 1
                points_in_segment = 0
            
            # Add the current point to the (new or existing) segment
            new_segment.append(current_pt)
            points_in_segment += 1

        # 3. Append the last segment (unless it's empty)
        if len(new_segment.findall('gpx:trkpt', GPX_NS)) > 0:
            trk.append(new_segment)
            total_segments_created += current_segment_count
        else:
             total_segments_created += current_segment_count - 1 # Don't count the empty last segment

        print(f"  -> Track resegmented into {current_segment_count} new segments.")

    # 4. Write the modified XML to a new file
    output_path = write_gpx_file(gpx_path, tree)
    print(f"\nSuccessfully created {total_segments_created} new segments.")
    print(f"Output written to: {output_path}")

def write_gpx_file(original_path, tree):
    """Constructs the output filename and writes the modified XML tree."""
    base, ext = os.path.splitext(original_path)
    output_path = f"{base}_resegmented{ext}"
    
    # Use ET.tostring() with xml_declaration=True for a full XML header
    # and encoding='utf-8' for compliance.
    xml_string = ET.tostring(tree.getroot(), encoding='utf-8', xml_declaration=True)
    
    with open(output_path, 'wb') as f:
        f.write(xml_string)
        
    return output_path

def main():
    """Parses command-line arguments and initiates the process."""
    if 'math' not in sys.modules:
        print("Error: The built-in 'math' library is required but failed to import.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Reads a GPX file, merges all track segments, and re-segments based on time and distance gaps."
    )
    parser.add_argument(
        "gpx_file",
        help="Path to the input GPX file (.gpx)."
    )
    # 1 hour = 3600 seconds
    parser.add_argument(
        "--time-gap",
        type=int,
        default=3600, 
        help="Time gap threshold in seconds (> this value triggers a break). Default: 3600 (1 hour)."
    )
    # 100 meters
    parser.add_argument(
        "--dist-gap",
        type=float,
        default=100.0, 
        help="Distance gap threshold in meters (> this value triggers a break). Default: 100.0 meters."
    )
    
    args = parser.parse_args()
    process_gpx_file(args.gpx_file, args.time_gap, args.dist_gap)

if __name__ == "__main__":
    main()
