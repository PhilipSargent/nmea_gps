#!/bin/sh 
# Created 2 May to get around pgrep funnies
touch /root/nmea_logs/nmealogger-started.txt
echo `date` nmealogger.sh >>/root/nmea_logs/nmealogger_error.txt
python /root/nmea_gps/nmealogger.py  >>/root/nmea_logs/nmealogger_ok.txt 2>>/root/nmea_logs/nmealogger_error.txt

