#!/bin/sh 
eval $(ssh-agent -s)
ssh-add /root/.ssh/id_papaya
git pull
