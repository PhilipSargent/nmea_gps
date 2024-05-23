#!/bin/sh 
# updated 14 May 2024
# copy to nmea not to root
# started by crontab, every 7 minutes
eval $(ssh-agent -s)
ssh-add /root/.ssh/id_papaya

# Update the data archive on the server in Cambridge
cd /root/nmea_data
# wc /root/nmea_data/*/*.nmea

touch nmealogger_rsynced.txt

# this is good for 2024 to 2099
rsync -avz -e "ssh -p 10037 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"  /root/nmea_data/  root@admin.djangotest.vs.mythic-beasts.com:/home/nmea/nmea_data
pkill "ssh-agent -s"

echo nmea data copy ran ok.