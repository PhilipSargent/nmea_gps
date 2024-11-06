#!/bin/sh 
# 2024-05-30
# Written with the rather erratic help of Gemini
# Could this be triggering erroneously, in that the file is updated, but the timestamp is not showing correctly ?

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

dir_root=`ls -pd /root/nmea_data/* | grep "/$"`
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

# Handle results
if [ $overdue_updated -ne 1 ]; then
  echo `date` "No files in '$directory' have been updated in the last $threshold minutes."
  # so kill the .py process, wich terminates the .sh script
  # cron will then restart it in 3 minutes
  touch /root/nmea_data/nmealogger-hung.txt
  echo `date` "Hung: no update in $threshold minutes.  $file_stamp nmeachecker.sh" >> /root/nmea_data/nmealogger_error.txt
  pkill -ef "python /root/nmea_gps/nmealogger.py"
  exit 1
# else
  # echo `date` "$filename updated recently"
fi

if [ $usual_updated -ne 1 ]; then
  echo `date` "No files in '$directory' have been updated in the last $usual minutes."
  echo `date` "Slow: no update in $usual minutes.  $file_stamp nmeachecker.sh" >> /root/nmea_data/nmealogger_error.txt
fi
exit 0