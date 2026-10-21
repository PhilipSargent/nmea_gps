#!/bin/sh 
# updated  21 oct 2026
# now under git
# started by crontab, once a day at 01:11
eval $(ssh-agent -s)
ssh-add /root/.ssh/id_papaya
# printf "put -p /root/code_data/touchme.txt /root/code_data/touchme.txt\nbye" | sftp -P 41061 root@sshproxy.mythic-beasts.com
cd /root/nmea_gps
git status
git pull
cd /root/nmea_gps/code
tar -czvf /root/code_data/alltxt.tar.gz *.txt *.sh /root/code_data/*.txt
printf "put -p /root/code_data/alltxt.tar.gz /root/code_data/alltxt.tar.gz\nbye" |  sftp -P 41061 root@sshproxy.mythic-beasts.com

crontab -l >/root/code_data/crontab.txt
printf "put -p /root/code_data/crontab.txt /root/code_data/crontab.txt\nbye" | sftp -P  sftp -P 41061 root@sshproxy.mythic-beasts.com
#pkill "ssh-agent -s"
echo Revised copyscript  (sshproxy) ran.
