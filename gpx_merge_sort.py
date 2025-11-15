import argparse
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

# GPX Namespace definition (standard for GPX 1.1 files)
GPX_NS = {'gpx': 'http://www.topografix.com/GPX/1/1'}
GPX_NS_URL = GPX_NS['gpx']

def get_xml_element_text(element, tag, namespace):
    """Safely find and return the text content of a child element, or None."""
    # ET requires the full namespace URI for XPaths in find/findall
    full_tag = f"gpx:{tag}"
    child = element.find(full_tag, namespace)
    return child.text.strip() if child is not None and child.text else None

def get_track_start_time(trk_element):
    """
    Finds and parses the time of the first track point found in any segment of the track,
    this allows for empty segments.  The nested loop ensures that if the first, second, or third segment is empty, 
    it continues searching the subsequent segments and points until it finds a valid timestamp. 

    This time is used for sorting.
    """
    
    try:
        # 1. Iterate over all track segments
        for trkseg in trk_element.findall('gpx:trkseg', GPX_NS):
            
            # 2. Iterate over all track points within the current segment
            for first_pt in trkseg.findall('gpx:trkpt', GPX_NS):
                
                # 3. Get the time string from the point
                time_str = get_xml_element_text(first_pt, 'time', GPX_NS)
                
                if time_str:
                    # GPX standard time format is ISO 8601 (e.g., 2023-10-27T10:00:00Z)
                    # We need to robustly handle the 'Z' (Zulu/UTC) and potential fractional seconds.
                    clean_time_str = time_str.strip().replace('Z', '').split('.')[0]
                    
                    # Standard GPX time format: YYYY-MM-DDTHH:MM:SS
                    return datetime.strptime(clean_time_str, '%Y-%m-%dT%H:%M:%S')
            
    except Exception as e:
        # Log error but return None to skip or treat as unsortable
        print(f"Warning: Could not extract/parse start time for a track. Error: {e}")
        return None
    
    return None

def merge_gpx_files(input_files, output_file):
    """
    Merges tracks from multiple GPX files into a single GPX file, sorted by start time.
    """
    # List to store tuples: (datetime_object, xml_track_element)
    all_tracks = []
    
    print(f"Processing {len(input_files)} input files...")

    # 1. Extract all tracks and their start times
    for file_path in input_files:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError:
            print(f"Error: Skipping '{file_path}' - Could not parse XML.")
            continue
        except FileNotFoundError:
            print(f"Error: Skipping '{file_path}' - File not found.")
            continue

        # Find all tracks in the current file
        tracks = root.findall('gpx:trk', GPX_NS)
        
        if not tracks:
            print(f"Warning: No <trk> elements found in '{file_path}'.")
        
        for trk in tracks:
            start_time = get_track_start_time(trk)
            
            # Store the track element along with its start time for sorting
            # If no time is found, use a very old date so it sorts to the beginning
            if start_time is None:
                start_time = datetime.min
            
            all_tracks.append((start_time, trk))
            
    if not all_tracks:
        print("No valid tracks found across all input files. Output file not created.")
        return

    # 2. Sort the tracks by the start time (index 0 of the tuple)
    all_tracks.sort(key=lambda x: x[0])
    print(f"Found and sorted {len(all_tracks)} tracks by start time.")

    # 3. Create the new GPX root element
    # ET requires special handling for namespaces to ensure they are added as attributes
    # The 'gpx' prefix must be mapped to the URL for the root element.
    ET.register_namespace('', GPX_NS_URL)
    gpx_root = ET.Element(
        f"{{{GPX_NS_URL}}}gpx", 
        version="1.1", 
        creator="GPX Merge Sort Script"
    )

    # Add simple metadata to the new file
    metadata = ET.SubElement(gpx_root, f"{{{GPX_NS_URL}}}metadata")
    time_tag = ET.SubElement(metadata, f"{{{GPX_NS_URL}}}time")
    time_tag.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # 4. Append the sorted tracks to the new root
    for _, trk_element in all_tracks:
        # Append the track (index 1) to the new root
        gpx_root.append(trk_element)

    # 5. Write the final XML to the output file
    try:
        tree = ET.ElementTree(gpx_root)
        
        # Use pretty print to make the XML readable
        ET.indent(tree, space="  ", level=0) 
        
        # Write the file, ensuring UTF-8 encoding
        tree.write(output_file, encoding='utf-8', xml_declaration=True)
        print(f"\nSuccessfully created merged and sorted GPX file: '{output_file}'")
    except Exception as e:
        print(f"Error writing output file '{output_file}': {e}")


def main():
    """Parses command-line arguments and initiates the merge process."""
    parser = argparse.ArgumentParser(
        description="Merges multiple GPX files into one, sorting tracks by their earliest timestamp."
    )
    
    # Accept one or more input GPX files
    parser.add_argument(
        "input_files",
        nargs='+',
        help="One or more paths to input GPX files to merge."
    )
    
    # Accept a single output file path
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Path for the resulting merged and sorted GPX file."
    )
    
    args = parser.parse_args()
    
    # Check if any input file is the same as the output file
    if args.output in args.input_files:
        print(f"Error: Output file '{args.output}' cannot be one of the input files.")
        sys.exit(1)

    merge_gpx_files(args.input_files, args.output)

if __name__ == "__main__":
    main()