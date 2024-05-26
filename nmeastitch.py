"""Concatenate all the nmea files in a given directory,
and to create a concatenated file for each day. 

Note that 'day' means in EEST timezone
as it works from the filenames, it is not a UTC 'day'.

Rewritten from a skeleton created by Gemini.

Uses
https://github.com/semuconsulting/pynmeagps
"""

import sys
import shutil
from pathlib import Path

BUFSIZE = 4096

def concatenate_sorted_files(directory_path, stitched_path):
    """
    Concatenates all files in a directory in dictionary order.

    Args:
      directory_path: The path to the directory containing the files (as a pathlib.Path object).
      sf: The filehandle to the target
    """
        
    # Get nmea filepaths (Path objects) sorted by lowercase name. We have made these in datetime UTC order.
    filepaths = sorted(directory_path.iterdir(), key=lambda p: p.name.lower())
    filepaths.remove(stitched_path)
    for filepath in filepaths:
        if not filepath.is_file():
            print(f"Not a file: {filepath} \nSomething serious went wrong.")
            sys.exit(1)
        if filepath.suffix != ".nmea":
            filepaths.remove(filepath)

    print(f"{len(filepaths)} Concatenated files in {directory_path} (dictionary order):")
    with stitched_path.open('wb', buffering=BUFSIZE) as sf: #
        for filepath in filepaths:
            with filepath.open('rb', buffering=BUFSIZE) as ifile:
                print(filepath.name)
                shutil.copyfileobj(ifile, sf)
    
    # COnstruct a file for each 'day' midnight to midnight EEST
    daypaths = {}
    for filepath in filepaths:
        if filepath.name[:2] == "20" and len(filepath.stem) == 15:
            dayname = filepath.name[:10]
            
            daypath = directory_path / (dayname + ".day")
            if daypath.is_file():
                daypath.unlink() # deletes pre-existing dayfiles
            daypaths[dayname] = daypath
    print(daypaths)
    
    for filepath in filepaths:
        dn = filepath.name[:10]
        if dn in daypaths:
            with daypaths[dn].open('ab', buffering=BUFSIZE) as afile: # APPEND mode
                with filepath.open('rb', buffering=BUFSIZE) as ifile:
                    shutil.copyfileobj(ifile, afile)


                
if __name__ == "__main__":
    DIR = "/home/philip/gps/nmea_data/2024-05/"
    STITCH = "nmea.stitch"
    
    if len(sys.argv) == 3:
        DIR = sys.argv[1]
        STITCH = sys.argv[2]


    if len(sys.argv) == 2:
        print(f"Either with no parameters or with directory and stitch filename, e.g.\n$ python nmeastich.py /home/philip/gps/nmea_data/2024-05 nmea.stitch", flush=True)
        sys.exit(1)    

    directory_path = Path(DIR)  
    if not directory_path.is_dir():
        print(f"Error: Directory '{directory_path}' does not exist.")
        sys.exit(1)
        
    stitched_path = directory_path / STITCH
    filepaths = sorted(directory_path.iterdir(), key=lambda p: p.name.lower())

    print(f"Writing {stitched_path}", flush=True)
    concatenate_sorted_files(directory_path, stitched_path)


