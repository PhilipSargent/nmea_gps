# nmea #
Various bits of code to archive my GPS tracks on my boat. 
Also some fragments trying to get around Navionics dreadful support for external GNSS feed.

run nmeastich to collect all the days of a month to one file per day
run nmeagpx to convert the day files to gpx files and produce a monthly summary

run like this:
uv run nmeagpx.py /home/philip/gps/nmea_data/2024-12/ '.day' '.nmea'

# how it is deployed #
Some of the scripts run on a GL.INET "mango" router. This router is permanently mounted on the boat
and recieves NMEA sentences by tcp from the Quark-Elec A026 AIS/GPS box which has a VHF antenna for AIS
and a GPS antenna.

Things crash and hang frequently so there are timeout checks and the router is rebooted twice a day. Also the .nmea
files are restarted once they reach a certain size. There are cron jobs which manage this aslo rsync the data to
a server at nmea.klebos.eu whcih is hosted by Mythic Beasts.
