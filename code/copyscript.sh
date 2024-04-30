#!/bin/sh 
# updated remotely 30 April 2024
eval $(ssh-agent -s)
ssh-add /root/.ssh/id_papaya
printf "put -p /root/code/touchme.txt /root/code/touchme.txt\nbye" | sftp -P 10037 root@admin.djangotest.vs.mythic-beasts.com
cd /root/nmea_gps
git status
git fetch
git pull
cd /root/code
tar -czvf alltxt.tar.gz *.txt *.sh 
printf "put -p /root/code/alltxt.tar.gz /root/code/alltxt.tar.gz\nbye" | sftp -P 10037 root@admin.djangotest.vs.mythic-beasts.com
# Update the data archive on the server in Cambridge
cd /root/nmea_gps
wc /root/nmea_gps/*/*.nmea
#tar -czvf allnmea.tar.gz /root/nmea_gps/*/*.nmea
#printf "put -p /root/nmea_gps/allnmea.tar.gz /root/code/allnmea.tar.gz\nbye" | sftp -P 10037 root@admin.djangotest.vs.mythic-beasts.com
rsync -avz -e "ssh -p 10037 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"  /root/nmea_gps/202*/*  root@admin.djangotest.vs.mythic-beasts.com:/root/nmea_data
echo copyscript  ran.