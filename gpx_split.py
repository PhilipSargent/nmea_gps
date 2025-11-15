import os
import argparse
import xml.etree.ElementTree as ET
import copy
"""write a python program which will split up a .gpx file into separate .gpx files, 
one file for each <trk> ."""

def split_gpx_by_track(input_gpx_path):
    """
    Splits a GPX file into multiple files, one for each <trk> element.

    Args:
        input_gpx_path (str): The path to the input .gpx file.
    """
    if not os.path.exists(input_gpx_path):
        print(f"Error: File not found at '{input_gpx_path}'")
        return

    # GPX files have a namespace. We must use it to find elements.
    ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
    ET.register_namespace('', ns['gpx'])

    try:
        # Parse the original GPX file
        tree = ET.parse(input_gpx_path)
        root = tree.getroot()

        # Find all track elements in the entire file
        original_tracks = root.findall('.//gpx:trk', ns)

        if not original_tracks:
            print("No <trk> elements found in the file. Nothing to do.")
            return
        
        # If there's only one track, there's nothing to split.
        if len(original_tracks) <= 1:
            print("Only one <trk> element found. No splitting is necessary.")
            return

        print(f"Found {len(original_tracks)} tracks. Creating individual files...")

        # Create a "template" tree by removing all track elements.
        # This preserves all metadata, waypoints, etc.
        template_tree = copy.deepcopy(tree)
        template_root = template_tree.getroot()
        
        # Clear all existing tracks from the template
        tracks_to_remove = template_root.findall('gpx:trk', ns)
        for trk in tracks_to_remove:
            template_root.remove(trk)
            
        # --- Loop through original tracks and create a new file for each ---
        base_filename, extension = os.path.splitext(input_gpx_path)

        for i, track in enumerate(original_tracks):
            # Create a fresh copy of the template for each new file
            new_tree = copy.deepcopy(template_tree)
            new_root = new_tree.getroot()
            
            # Append the current track to the root of the new GPX structure
            new_root.append(track)

            # Define the new output filename
            output_filename = f"{base_filename}_track_{i+1}{extension}"

            # Write the new XML tree to the file
            new_tree.write(output_filename, xml_declaration=True, encoding='utf-8')
            print(f"  -> Successfully created '{output_filename}'")

        print("\nSplitting complete.")

    except ET.ParseError as e:
        print(f"Error parsing XML in '{input_gpx_path}': {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def main():
    """Main function to parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Split a GPX file into separate files for each <trk> element.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "input_file",
        help="The path to the .gpx file you want to split."
    )
    args = parser.parse_args()
    
    split_gpx_by_track(args.input_file)

if __name__ == "__main__":
    main()

