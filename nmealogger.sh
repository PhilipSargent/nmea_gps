#!/bin/sh 
# Created 2 May to get around pgrep funnies
python /root/nmea_gps/nmealogger.py
touch /root/nmea_data/nmealogger-started.txt
