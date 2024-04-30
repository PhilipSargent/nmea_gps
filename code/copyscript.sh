#!/bin/sh 
# updated  30 April 2024
# now under git
eval $(ssh-agent -s)
ssh-add /root/.ssh/id_papaya
printf "put -p /root/code/touchme.txt /root/code/touchme.txt\nbye" | sftp -P 10037 root@admin.djangotest.vs.mythic-beasts.com
cd /root/nmea_gps
git status
git pull
cd /root/nmea_gps/code
tar -czvf /root/code_data/alltxt.tar.gz *.txt *.sh /root/code_data/*.txt
printf "put -p /root/code_data/alltxt.tar.gz /root/code_data/alltxt.tar.gz\nbye" | sftp -P 10037 root@admin.djangotest.vs.mythic-beasts.com

crontab -l >/root/code_data/crontab.txt
printf "put -p /root/code_data/crontab.txt /root/code_data/crontab.txt\nbye" | sftp -P 10037 root@admin.djangotest.vs.mythic-beasts.com

echo Revised copyscript  ran.