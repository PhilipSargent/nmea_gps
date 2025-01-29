# nmea
Various bits of code to archive my GPS tracks on my boat. 
Also some fragments trying to get around Navionics dreadful support for external GNSS feed.

run nmeastich to collect all the days of a month to one file per day
run nmeagpx to convert the day files to gpx files and produce a monthly summary

run like this:
uv run nmeagpx.py /home/philip/gps/nmea_data/2024-12/ '.day' '.nmea'