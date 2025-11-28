"""Concatenate all the nmea files in a given directory,
and to create a concatenated file for each day. 

Note that 'day' means in EET,EEST timezone
as it works from the filenames, it is not a UTC 'day'.

Rewritten from a skeleton created by Gemini.

Uses
https://github.com/semuconsulting/pynmeagps
"""
import datetime
import os
import time
import sys
import shutil
import zoneinfo

from pathlib import Path

import nmea_time_overlap_checker as overlap


BUFSIZE = 4096
SUFFIX = ".day.nmea"

def get_eet_utc_offset_hours(timestamp):
    """
    Calculates the UTC offset (2 or 3 hours) for a given POSIX timestamp,
    explicitly using the Europe/Athens timezone (EET/EEST rules).
    
    This approach ensures the calculation is correct regardless of the 
    Python environment's local timezone setting.
    
    Returns:
        The UTC offset in hours (integer: 2 for EET, 3 for EEST).
    """
    try:
        # 1. Convert the UTC timestamp to a timezone-aware datetime object (in UTC)
        # os.path.getmtime returns a UTC timestamp (seconds since epoch)
        dt_utc = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
        
        # 2. Convert the UTC datetime object to the target timezone (EET/EEST)
        # 'Europe/Athens' is a reliable ZoneInfo name for EET/EEST
        eet_tz = zoneinfo.ZoneInfo("Europe/Athens")
        dt_eet = dt_utc.astimezone(eet_tz)
        
        # 3. Calculate the offset from UTC (as a timedelta object)
        offset = dt_eet.utcoffset()
        
        # 4. Convert the timedelta offset to hours (2 or 3)
        if offset is not None:
            # total_seconds() is reliable for converting timedelta to a number
            return int(offset.total_seconds() // 3600), dt_utc
        else:
            # Fallback to standard time (EET)
            return 2, dt_utc
            
    except Exception as e:
        print(f"Error during offset calculation: {e}")
        return 2 # Default fallback

        
def get_os_file_date(filepath):
    """
    Returns the file's last modification date as a YYYYMMDD string.
    """
    timestamp = os.path.getmtime(filepath)
    offset, dt_utc = get_eet_utc_offset_hours(timestamp)
    
   # Format as YYYYMMDD for easy comparison/logging
    dt_object = datetime.datetime.fromtimestamp(timestamp)

    return dt_object.strftime("%Y%m%d"), offset, dt_utc.strftime("%Y-%m-%d")
 


def get_minutes_since_midnight_eet(timestamp):
    """
    Calculates the number of minutes elapsed since midnight for a given POSIX 
    timestamp, adjusted for the Europe/Athens (EET/EEST) timezone.

    The minutes are calculated based on the local time (HH:MM) in the EET/EEST zone.
    
    Args:
        timestamp (float): The POSIX timestamp (seconds since epoch, UTC).

    Returns:
        int: The number of minutes since midnight (0-1439).
    """
    try:
        # 1. Define the target timezone
        eet_tz = zoneinfo.ZoneInfo("Europe/Athens")
        
        # 2. Convert the UTC timestamp to a timezone-aware datetime object in EET/EEST
        dt_utc = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
        dt_eet = dt_utc.astimezone(eet_tz)
        
        # 3. Calculate seconds since midnight in the local EET/EEST time
        seconds_since_midnight = (
            dt_eet.hour * 3600 +
            dt_eet.minute * 60 +
            dt_eet.second
        )
        
        # 4. Convert to minutes 
        minutes_since_midnight = seconds_since_midnight / 60
        
        return minutes_since_midnight

    except Exception as e:
        print(f"Error calculating minutes since midnight: {e}")
        # Default fallback to 0 or another suitable error value
        return 0

def check_file_and_nmea_dates(filepaths):
    """
    Compares the operating system's modification date for a file with the date 
    contained within the NMEA data (GPRMC sentence). Reports any mismatches.
    
    The OS filestamp can be ONE DAY after the UTC date because the OS is 
    in EET, EEST  which is 2 or 3 hours AHEAD of UTC. 
    And the timestamp must be between 00:00 and 02:00 (or 03:00)
    Any other mismatch is an error.
    """
    ALLOWANCE = 2 # minutes. Less tahn this triggers no warnings.
    def explain_mismatch():
        if os_utc_str != str(nmea_date): # nmea_date <class 'datetime.date'>
            # But thsi is often because the timestamp on the file is only a few seconds late, 
            # after the actual time the UTC day flipped. SO look at the file timestamp more closely
            timestamp = os.path.getmtime(filepath)
            dt_object = datetime.datetime.fromtimestamp(timestamp)
            mins = get_minutes_since_midnight_eet(timestamp)
            overdue = mins - offset*60
            if overdue > ALLOWANCE:
                print(f"{filepath.name} UTC date MISMATCH: OVERDUE: {overdue:.3} minutes")
            
        
    mismatches = 0
    
    for filepath in filepaths:
        os_date_str, offset, os_utc_str = get_os_file_date(filepath)
        nmea_date_str = overlap.get_nmea_date(filepath)
        
        if not os_date_str or not nmea_date_str:
            print(f"Skipping '{filepath}': Missing OS date ({os_date_str}) or NMEA date ({nmea_date_str}).")
            continue
            
        try:
            # OS date (YYYYMMDD)
            os_date = datetime.datetime.strptime(os_date_str, "%Y%m%d").date()
            
            # NMEA date (DDMMYY) - assuming 21st century (2000-2099) for simplicity
            nmea_date = datetime.datetime.strptime(nmea_date_str, "%d%m%y").date() # because that is the NMEA format
            if os_date != nmea_date:
                mismatches += 1
                explain_mismatch()

        except ValueError as e:
            print(f"Error parsing date in '{filepath}': {e}")
            mismatches += 1
            
    # print(f"\nCompleted check. Total mismatches found: {mismatches}")
    return mismatches == 0


def file_is_empty(filepath):
    """
    Checks if a file exists and has a size of exactly zero bytes.
    """
    if not os.path.exists(filepath):
        # Handle case where the file doesn't exist
        return False
    return os.path.getsize(filepath) == 0


def get_filepaths(directory_path):
    filepaths = sorted(directory_path.iterdir(), key=lambda p: p.name.lower())
    # print(f"{len(filepaths)} All files in {directory_path} (dictionary order):")
    not_wanted = set()
    if stitched_path in filepaths:
        #filepaths.remove(stitched_path)
        not_wanted.add(stitched_path)
    for filepath in filepaths:
        if not filepath.is_file():
            print(f"Not a file: {filepath} \nSomething serious went wrong.")
            sys.exit(1)
        if file_is_empty(filepath):
            # skip empty files
            not_wanted.add(filepath)
        if filepath.suffix != ".nmea":
            not_wanted.add(filepath)
        # if filepath.name[:7] != directory_path.name:
            # # valid files all start with the directory name, e.g. '2024-05'
            # # NO DO NOT DO THIS. Filename may be the next month but still before 3am (2am) so in same UTC month.
            # not_wanted.add(filepath)
        if ".day" in filepath.suffixes:
            # we don't want previously generated .day.nmea files
            if filepath in filepaths:
                not_wanted.add(filepath)
        if ".gpx" in filepath.suffixes:
            if filepath in filepaths:
                not_wanted.add(filepath)
        if STITCH_SUFFICES in filepath.name:
                not_wanted.add(filepath)
                
                

    for f in not_wanted:
        filepaths.remove(f)
        
    # print(f"{len(filepaths)} selected files in {directory_path} (excl. .gpx, .day.nmea etc.):")
    return filepaths

  
def concatenate_sorted_files(filepaths, directory_path, stitched_path):
    """
    Concatenates all files in a directory in dictionary order.
    This DOES NOT CHECK that the GNSS timestamps are actually in  the correct order.
    
    This DOES NOT CHECK if there are overlaps in the timestamps from different files.

    Args:
      directory_path: The path to the directory containing the files (as a pathlib.Path object).
      sf: The filehandle to the target
    """
        
    # Get nmea filepaths (Path objects) sorted by lowercase name. We have made these in datetime UTC order.
    # DO NOT chnage the members of a list while the list is being iterated !
    with stitched_path.open('wb', buffering=BUFSIZE) as sf: #
        for filepath in filepaths:
            with filepath.open('rb', buffering=BUFSIZE) as ifile:
                # print(f"{filepath.stem[-7:]},", end="")
                if ".gpx" in filepath.suffixes:
                    print(f"! (has  .gpx) {filepath.name}")
                shutil.copyfileobj(ifile, sf)
        # print(f"  {filepath.suffixes}")
    
    # Construct a file for each 'day' midnight to midnight EEST
    daypaths = {}
    for filepath in filepaths:
        if filepath.name[:2] == "20" and len(filepath.stem) == 15:
            dayname = filepath.name[:10]
            
            daypath = directory_path / (dayname + SUFFIX)
            if daypath.is_file():
                daypath.unlink() # deletes pre-existing dayfiles
            daypaths[dayname] = daypath
        else: 
            print(f"{len(filepaths)} REJECT {filepath} ") 
            

    if len(daypaths) > 0:
        print(f"{directory_path.name}: {len(daypaths):3d} whole-day .nmea files generated from {len(filepaths):3d} individual .nmea files ")

        for filepath in filepaths:
            dn = filepath.name[:10]
            if dn in daypaths:
                with daypaths[dn].open('ab', buffering=BUFSIZE) as afile: # APPEND mode
                    with filepath.open('rb', buffering=BUFSIZE) as ifile:
                        shutil.copyfileobj(ifile, afile)
            
if __name__ == "__main__":
    DIR = "/home/philip/gps/nmea_mirror/nmea_data/2025-11/"
    STITCH_SUFFICES = ".mnth.stitch.nmea"
    
    if len(sys.argv) == 2:
        DIR = [sys.argv[1]] # list with one element
        print(f"Processing just {DIR}")
        
    if len(sys.argv) > 2:
        # probably a sequence of directories, e.g. nmea_data/*/*.nmea which is expanded by the shell
        directories = sys.argv[1:-1] # first one is the name of the program, last is the stich filename

    files = 0
    for directory_path in directories:
        directory_path = Path(directory_path)
        if directory_path.is_file():
            # print(f"Error: path '{directory_path}' is a file.")
            files += 1
            continue
        if not directory_path.is_dir():
            print(f"Error: Directory '{directory_path}' does not exist.")
            sys.exit(1)
            
    print(f"Processing {len(directories)-files:3d} directories")
    for directory_path in directories:       
        directory_path = Path(directory_path)
        STITCH = directory_path.name + STITCH_SUFFICES
        stitched_path = directory_path / STITCH
        if directory_path.is_file():
            continue
        filepaths = get_filepaths(directory_path)
        check_file_and_nmea_dates(filepaths)
        overlap.check_ranges(filepaths)        
        concatenate_sorted_files(filepaths, directory_path, stitched_path)


