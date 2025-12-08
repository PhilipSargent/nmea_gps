#!/bin/sh
# Gemini
# to see how long it is before crontab next runs nmealogger.sh 
M=$(date +%M); S=$(date +%S); T=$(( (3 - (M % 3)) * 60 - S )); echo "$((T/60)) minutes and $((T%60)) seconds"