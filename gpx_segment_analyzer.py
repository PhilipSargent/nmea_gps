import argparse
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

# git@github.com:PhilipSargent/nmea_gps.git

# GPX Namespace definition (standard for GPX 1.1 files)
# This is necessary to correctly find elements within the GPX structure.
GPX_NS = {'gpx': 'http://www.topografix.com/GPX/1/1'}
TIME_FORMAT = '%Y-%m-%dT%H:%M:%S' # ISO 8601 format withOUT Zulu timezone

def get_xml_element_text(element, tag, namespace):
    """Safely find and return the text content of a child element, or None."""
    # ET requires the full namespace URI for XPaths in find/findall
    full_tag = f"gpx:{tag}"
    child = element.find(full_tag, namespace)
    # Strip whitespace and check if text exists
    return child.text.strip() if child is not None and child.text else None

    
def get_segment_data(gpx_file_path):
    """
    Reads a GPX file, iterates through tracks and segments, and calculates 
    the start time and duration for each segment.
    """
    
    def get_track_time(trk_element):
        time_str = get_xml_element_text(trk_element, 'time', GPX_NS)

        if time_str:
            # GPX standard time format is ISO 8601 (e.g., 2023-10-27T10:00:00Z)
            # We need to robustly handle the 'Z' (Zulu/UTC) and potential fractional seconds.
            clean_time_str = time_str.strip().replace('Z', '').split('.')[0]
            
            try:
                # Standard GPX time format: YYYY-MM-DDTHH:MM:SS
                return datetime.strptime(clean_time_str, '%Y-%m-%dT%H:%M:%S')

            except ValueError:
                print(f"  Segment {segment_count}: Time format mismatch. Check time tags. {time_str=}")

        return None
    
    try:
        tree = ET.parse(gpx_file_path)
        root = tree.getroot()
    except ET.ParseError:
        print(f"Error: Could not parse XML in '{gpx_file_path}'. Is it a valid GPX file?")
        return
    except FileNotFoundError:
        print(f"Error: File not found at '{gpx_file_path}'.")
        return

    print(f"\n--- Analyzing: {gpx_file_path} ---")
    
    # Find all tracks in the file
    tracks = root.findall('gpx:trk', GPX_NS)
    
    if not tracks:
        print("No <trk> elements found in this file.")
        return

    track_count = 0
    
    # Iterate through all tracks
    for trk in tracks:
        track_count += 1
        trk_name = get_xml_element_text(trk, 'name', GPX_NS)
        
        # Display the track name or number
        print(f"\nTrack {track_count}{f': {trk_name}' if trk_name else ''}")
        print("---------------------------------")
        
        segments = trk.findall('gpx:trkseg', GPX_NS)
        
        if not segments:
            print("  No <trkseg> elements in this track.")
            continue
            
        segment_count = 0
        
        # Iterate through all segments in the current track
        for seg in segments:
            segment_count += 1
            
            # Find all track points in the current segment
            points = seg.findall('gpx:trkpt', GPX_NS)
            
            if not points:
                print(f"  Segment {segment_count}: No <trkpt> elements found.")
                continue

            # Get the first and last point of the segment
            first_pt = points[0]
            last_pt = points[-1]
            
            # Extract time strings
            start_time = get_track_time(first_pt)
            end_time = get_track_time(last_pt)

            if not start_time or not end_time:
                print(f"  Segment {segment_count}: Start or end time missing. Cannot calculate duration.")
                continue
             
            # Calculate duration (timedelta object)
            duration = end_time - start_time
            
            # Format the output
            print(f"  Segment {segment_count}:")
            print(f"    Start Time: {start_time}")
            print(f"    Duration:   {duration}")

def main():
    """Parses command-line arguments and runs the analyzer."""
    parser = argparse.ArgumentParser(
        description="Analyzes a GPX file and reports the start time and duration of each track segment."
    )
    
    parser.add_argument(
        "gpx_file",
        help="Path to the GPX file to analyze."
    )
    
    args = parser.parse_args()
    
    get_segment_data(args.gpx_file)

if __name__ == "__main__":
    main()