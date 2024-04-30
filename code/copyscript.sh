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
cd /root/nmea_gps/code
tar -czvf /root/code_data/alltxt.tar.gz *.txt *.sh 
printf "put -p /root/code_data/alltxt.tar.gz /root/code_data/alltxt.tar.gz\nbye" | sftp -P 10037 root@admin.djangotest.vs.mythic-beasts.com

echo Revised copyscript  ran.