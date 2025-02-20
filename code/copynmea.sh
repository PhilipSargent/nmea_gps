#!/bin/sh 
# updated 20 Feb.2025
# copies to /home/nmea not to /root
# started by crontab, every 7 minutes
pkill ssh-agent
eval $(ssh-agent -s)
ssh-add /root/.ssh/id_papaya

# Update the data archive on the server in Cambridge
cd /root/nmea_data
# wc /root/nmea_data/*/*.nmea

touch nmealogger_rsynced.txt

# this is good for 2024 to 2099
rsync -avz -e "ssh -p 10037 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"  /root/nmea_data/  root@admin.djangotest.vs.mythic-beasts.com:/home/nmea/nmea_data
rsync -avz -e "ssh -p 10037 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"  /root/nmea_rawd/  root@admin.djangotest.vs.mythic-beasts.com:/home/nmea/nmea_rawd
#pkill "ssh-agent -s"

# reverse copy from server to laptop:
# rsync -avz -e "ssh -p 10037 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"   root@admin.djangotest.vs.mythic-beasts.com:/home/nmea/nmea_data ../nmea_data

echo nmea data copy ran ok.
# Here's the part you need to append, provided here separately for easy copy/pasting:
# https://healthchecks.io/checks/9cac10d3-757d-4ff3-96cc-e7714825e35f/details/
# using wget (10 second timeout, retry up to 5 times):
# NB OpenWRT/busybox wget does not do -t
# wget https://hc-ping.com/9cac10d3-757d-4ff3-96cc-e7714825e35f -T 10 -t 5 -O /dev/null
wget https://hc-ping.com/9cac10d3-757d-4ff3-96cc-e7714825e35f -T 10 -O /dev/null
echo healthchecks.io GET ran ok