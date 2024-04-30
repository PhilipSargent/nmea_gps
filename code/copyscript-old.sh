#!/bin/sh 
eval $(ssh-agent -s)
ssh-add /root/.ssh/id_papaya
printf "put -p /root/code/touchme.txt /root/code/touchme.txt\nbye" | sftp -P 10037 root@admin.djangotest.vs.mythic-beasts.com
echo script ran.