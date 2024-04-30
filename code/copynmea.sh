#!/bin/sh 
# updated 30 April 2024
# now under git
# started by crontab, every 7 minutes
eval $(ssh-agent -s)
ssh-add /root/.ssh/id_papaya

# Update the data archive on the server in Cambridge
cd /root/nmea_data
wc /root/nmea_data/*/*.nmea

# this is good for 2024 to 2099
rsync -avz -e "ssh -p 10037 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"  /root/nmea_data/20??/*  root@admin.djangotest.vs.mythic-beasts.com:/root/nmea_data
pkill "ssh-agent -s"

echo nmea data copy ran ok.