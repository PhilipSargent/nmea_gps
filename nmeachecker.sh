#!/bin/sh 
# 2024-05-30
# Written with the rather erratic help of Gemini
# Could this be triggering erroneously, in that the file is updated, but the timestamp is not showing correctly ?


# This checks for recent file updates in nmea_data/2020-*/*
# it does not check for the file touch in nmea_logs

# Define threshold (in minutes)
threshold=13
usual=1

# Get the current time (in seconds since epoch)
current_time=$(date +%s)

# Calculate the threshold time (current time minus threshold in minutes)
threshold_time=$((current_time - (threshold * 60)))
usual_time=$((current_time - (usual * 60)))

# Loop through files in the directory
overdue_updated=0  # Flag to track if any hung updated file is found
usual_updated=0  # Flag to track if any late updated file is found

dir_root=`ls -pd ../nmea_data/* | grep "/$"`
for directory in $dir_root; do
    for filename in $(ls -1 "$directory"); do
      filepath="$directory$filename"
      # echo "$directory$filename"

      # Check if it's a regular file (skip directories, etc.)
      if [ -f "$filepath" ]; then
        # Get the file modification time
        file_mtime=$(date -r "$filepath" +%s)
        file_stamp=$(date -r "$filepath" +"%T %Z")

        # Compare with threshold time
        if [ $file_mtime -gt $threshold_time ]; then
          overdue_updated=1
          updated=$filename
        fi
        # Compare with usual time
        if [ $file_mtime -gt $usual_time ]; then
          usual_updated=1
          usual_fn=$filename
        fi
      fi
    done
done

stillalive=0 # flag to see if the heartbeat still_alive.txt is still alive =0 means alive
alivepath="$../nmea_logs/still_alive.txt"
if [ -f "$alivepath" ]; then
    alive_mtime=$(date -r "$alivepath" +%s)
    alive_stamp=$(date -r "$alivepath" +"%T %Z")

     if [ $alive_mtime -gt $threshold_time ]; then
         stillalive=1 # means it is dead
     fi
fi

if [$stillalive -eq 0 ] ; then
    echo `date` "Still alive: $alive_stamp even though no recent updates in $directory."
    # no data copied to any log though
else
    if [ $overdue_updated -ne 1 ]; then
      # so kill the .py process, which terminates the .sh script
      # cron will then restart it in 3 minutes
      touch /root/nmea_logs/nmealogger-hung.txt
      echo `date` "Hung: no update in $threshold minutes.  $updated $file_stamp nmeachecker.sh" >> ../nmea_logs/nmealogger_error.txt
      pkill -ef "python /root/nmea_gps/nmealogger.py"
      exit 1
    fi

    if [ $usual_updated -ne 1 ]; then
      echo `date` "No files in '$directory' have been updated in the last $usual minutes."
      echo `date` "Slow: no update in $usual minutes.  $usual_fn $file_stamp nmeachecker.sh" >> ../nmea_logs/nmealogger_error.txt
    fi
fi
exit 0