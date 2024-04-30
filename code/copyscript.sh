#!/bin/sh 
# updated remotely 30 April 2024
# now under git
eval $(ssh-agent -s)
ssh-add /root/.ssh/id_papaya
printf "put -p /root/code/touchme.txt /root/code/touchme.txt\nbye" | sftp -P 10037 root@admin.djangotest.vs.mythic-beasts.com
cd /root/nmea_gps
git status
git fetch
git pull
cd /root/code
tar -czvf /root/code_data/alltxt.tar.gz *.txt *.sh 
printf "put -p /root/code_data/alltxt.tar.gz /root/code_data/alltxt.tar.gz\nbye" | sftp -P 10037 root@admin.djangotest.vs.mythic-beasts.com
# Update the data archive on the server in Cambridge
cd /root/nmea_data
wc /root/nmea_data/*/*.nmea
#tar -czvf allnmea.tar.gz /root/nmea_data/*/*.nmea
#printf "put -p /root/nmea_data/allnmea.tar.gz /root/code/allnmea.tar.gz\nbye" | sftp -P 10037 root@admin.djangotest.vs.mythic-beasts.com
rsync -avz -e "ssh -p 10037 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"  /root/nmea_data/202*/*  root@admin.djangotest.vs.mythic-beasts.com:/root/nmea_data
echo Revised copyscript  ran.