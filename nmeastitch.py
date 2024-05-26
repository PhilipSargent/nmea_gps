"""Gemini created code to concatenate all the nmea files in a given directory
"""
import sys
from pathlib import Path

DIR = "/home/philip/gps/nmea_data/2024-05/"
STITCH = "nmea.stitch"
BUFSIZE = 4096

def sort_filenames(filenames):
  """
  Sorts a list of filenames in dictionary order (case-insensitive).
  """
  return sorted(filenames, key=str.lower)  # Sort by lowercase filename

def concatenate_sorted_files(directory_path, sf):
    """
    Concatenates all files in a directory in dictionary order.

    Args:
      directory_path: The path to the directory containing the files (as a pathlib.Path object).
      sf: The filehandle to the target
    """

    # Get filenames sorted by lowercase name
    filenames = sorted(directory_path.iterdir(), key=lambda p: p.name.lower())

    print(f"Concatenated files in {directory_path} (dictionary order):")
    for filename in filenames:
        filepath = directory_path / filename
        if not filepath.is_file():
            print(f"Not a file: {filename}")
            sys.exit(1)
        else:
            with filepath.open('rb', buffering=BUFSIZE) as file:
                contents = file.read()
                if len(contents) == 0 :
                    print(f"Empty file {len(contents)} {filename}")
                else:
                    sf.write(contents)
                    sf.flush()

# Example usage
directory_path = Path(DIR)  # Replace with your directory path
if not directory_path.is_dir():
    print(f"Error: Directory '{directory_path}' does not exist.")
    sys.exit(1)
    
stitched_path = directory_path / STITCH
filenames = sorted(directory_path.iterdir(), key=lambda p: p.name.lower())

# for f in filenames:
    # print(f)
print(f"Writing {stitched_path}", flush=True)
with stitched_path.open('wb', buffering=BUFSIZE) as sf: #
    concatenate_sorted_files(directory_path, sf)


