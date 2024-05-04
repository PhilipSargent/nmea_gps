#!/bin/sh 
# Created 2 May to get around pgrep funnies
touch /root/nmea_data/nmealogger-started.txt
python /root/nmea_gps/nmealogger.py 

