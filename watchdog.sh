#!/bin/sh
# watchdog.sh
cd /root/nmea_gps

# Blindly attempt to start an instance for each port.
# If an instance is already active, the new script hits the socket lock, 
# prints its termination message, and cleanly exits without disrupting anything.
python nmeajogger.py 30303 > /dev/null 2>&1 &
python nmeajogger.py 30304 > /dev/null 2>&1 &
python nmeajogger.py 30305 > /dev/null 2>&1 &
