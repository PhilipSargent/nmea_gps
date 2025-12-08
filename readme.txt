# nmea #
Various bits of code to archive my GPS tracks on my boat. 
Also some fragments trying to get around Navionics dreadful support for external GNSS feed.

The directory [Snowwhite]\\wsl.localhost\Ubuntu-24.04\home\philip\gps\nmea_mirror\ 
is a reflection of
[extroot]/upper/root/
on the microSD card plugged in to the Mango router 'guava' on the boat, 
which is partially mirrored (by rsync) to nmea.klebos.eu i.e.
[djangotest]/home/nmea/ 

The directory /nav_gpx/ (formerly gpx_data) is also in [djangotest]/home/nmea/ 
but it is parallel to /nmea_mirror/ on Snowwhite.
/nav_gpx/ is used for massaging .gpx export files from
the Navionics app on my phones, for when the Mango system has failed to record a trip
AND for selecting out the trip data for each crew from the Mango-recorded data.
There is no /nav_gpx/ directory on the Mango router. 

/nmea_gps/ is where most of the python and shell script code lives.

The crontab settings and shell script output files also live in /gps/[date]-alltext/ which is uploaded to the
server as alltxt.tar.gz

NOTE that 
[djangotest]/root/nmea/nmea_gps and /root/nmea/gpx_work also used to exist but were deleted on 17 Nov.2025


TO DO 2025-11-17
The nav_gpx folder has a lot of huge Navionics files and multiple versions of stuff and needs culling/abbreviating.

TO DO 2025-12-07
Document how to use the sort_nmea_file_by_timestamp.py program with the *_mashup.gpx files to produce a consolidated annual file.



INSTRUCTIONS
run nmeastich to collect all the days of a month to one file per day
run like this:
cd gps/nmea_mirror/nmea_gps
uv run nmeastitch.py /home/philip/gps/nmea_mirror/nmea_data/2025-11 nmea.stitch

run nmeagpx to convert the day files to gpx files and produce a monthly summary
run like this:
cd gps/nmea_mirror/nmea_gps
uv run nmeagpx.py /home/philip/gps/nmea_data/2024-12/ '.day' '.nmea'

# how it is deployed #
Some of the scripts run on a GL.INET "mango" router. This router is permanently mounted on the boat
and recieves NMEA sentences by tcp from the Quark-Elec A026 AIS/GPS box which has a VHF antenna for AIS
and a GPS antenna.

Things crash and hang frequently so there are timeout checks and the router is rebooted twice a day. Also the .nmea
files are restarted once they reach a certain size. There are cron jobs which manage this aslo rsync the data to
a server at nmea.klebos.eu whcih is hosted by Mythic Beasts.

EXAMPLE COMMANDS

uv run gpx_merge_sort.py -o 2025-11.mnth.gpx ../nmea_data/2025-11/2025-11*.day.gpx

uv run gpx_merge_sort.py -o 2025.gpx ../nmea_data/2025*mnth.gpx ../2025-crews/*mashup.gpx

uv run gpx_merge_sort.py -o done2.gpx 2025-11-sum.gpx


uv run nmea_time_overlap_checker.py nmeastitch.py

uv run nmeastitch.py /home/philip/gps/nmea_mirror/nmea_data/2025-11 nmea.stitch

uv run nmeagpx.py /home/philip/gps/nmea_mirror/nmea_data/2025-11/ '.day' '.nmea'


uv run nmeastitch.py ../nmea_data/2025*

uv run nmeastitch.py ../nmea_data/202*

uv run ../../nmea_gps/gpx_segment_analyzer.py 2025-11*.gpx
uv run ../../nmea_mirror/nmea_gps/gpx_segment_analyzer.py 2025-11*.gpx
uv run ../../nmea_mirror/nmea_gps/gpx_segment_analyzer.py 2025-11-ordered.gpx
uv run ../../nmea_mirror/nmea_gps/gpx_mean.py 2025-11-ordered.gpx
uv run ../../nmea_mirror/nmea_gps/gpx_mean.py ../../nmea_mirror/nmea_data/2025-11-mnth.gpx
uv run ../../nmea_mirror/nmea_gps/gpx_mean.py ../../nmea_mirror/nmea_data/2025-11.mnth.gpx

sudo apt install vulture
vulture nmea_time_overlap_checker.py nmeastitch.py

uv run ping_response_analyzer.py ../nmea_logs/nmealogger_ok.txt

