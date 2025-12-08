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

# Calculate the threshold time in the past
threshold_time=$((current_time - (threshold * 60))) # 13 minutes ago
usual_time=$((current_time - (usual * 60))) # a minute ago

root_dir="/root/" # Has to be tooted in filesystem as this runs under crontab
# root_dir="/home/philip/gps/nmea_mirror/"

error_file=${root_dir}nmea_logs/nmealogger_error.txt

overdue_updated=1  # Flag to say they are all old
usual_updated=1  # Flag to say they are all old
youngest_fn="None"
youngest_mtime="0"
track=0000000000

track_id=${root_dir}nmea_logs/current_nmea_file.txt
if [ -f ${track_id}  ]; then
    track=`cat $track_id`
    # echo "  EXPECTED most recent nmea TRACK file is: `cat $track_id` == $track"
fi
# format of $track is 2025-11/2025-11-21_1234.nmea
directory=$(echo "$track" | cut -c 1-7)
trackpath=${root_dir}nmea_data/$track
if [ -f $trackpath  ]; then
    # echo "which EXISTS in $directory"  
    filepath=$trackpath
    # Get the file modification time
    file_mtime=$(date -r "$filepath" +%s)
    file_stamp=$(date -r "$filepath" +"%F %T %Z")

    # Compare with threshold time
    if [ $file_mtime -gt $threshold_time ]; then
      overdue_updated=0
      updated=$filename
      update_dir=$directory
    fi
    # Compare with usual time
    if [ $file_mtime -gt $usual_time ]; then
      # echo "DIFFERENCE=$(( $file_mtime - $usual_time ))"
      usual_updated=0
      usual_fn=$filename
      usual_dir=$directory
    fi    
else
    echo "TRACK file $trackpath not found, searching for recent .nmea files "
    # This checks every single .nmea file we have. 
    # it will always find lots of old files, we are looking for just one which is younger.
    # Loop through files in the directory
    dir_root=`ls -pd ${root_dir}nmea_data/* | grep "/$"`
    for directory in $dir_root; do
        for filename in $(ls -1 "$directory"); do
          filepath="$directory$filename"
          # is it is a .nmea file ?
          if [ "$filename" != "${filename%.nmea}" ]; then # ash idiom
              # here it DOES end in .nmea
              # NB includes .day.nmea
              # Check if it's a regular file (skip directories, etc.)
              nmeafilepath=$filepath
              if [ -f "$filepath"  ]; then
                # Get the file modification time
                file_mtime=$(date -r "$filepath" +%s)
                file_stamp=$(date -r "$filepath" +"%F %T %Z")
                
                if [ $file_mtime -gt $youngest_mtime ]; then
                  youngest_mtime=$file_mtime
                  youngest_fn=$filename
                fi

                # Compare with threshold time
                if [ $file_mtime -gt $threshold_time ]; then
                  # it is 
                  # echo "DIFFERENCE=$(( $file_mtime - $threshold_time ))"
                  overdue_updated=0
                  updated=$filename
                  update_dir=$directory
                fi
                # Compare with usual time
                if [ $file_mtime -gt $usual_time ]; then
                  echo " .nmea file found $file_stamp, but checked all against limits"
                  usual_DIFFERENCE=$(( $file_mtime - $usual_time ))
                  usual_updated=0
                  usual_fn=$filename
                  usual_dir=$directory
                fi
              fi
          else
            # files which do NOT have the .nmea extension
            continue
          fi
        done
    done
    echo "YOUNGEST    $youngest_mtime $youngest_fn"

fi

stillalive=0 # flag to see if the heartbeat still_alive.txt is still alive, =0 means alive
alivepath="${root_dir}nmea_logs/still_alive.txt"

if [ -f $alivepath ]; then
    alive_mtime=$(date -r "$alivepath" +%s)
    alive_stamp=$(date -r "$alivepath" +"%F %T %Z")
    # echo "There is an alive timestamp:$alive_stamp mod time:$alive_mtime thresh_time:$threshold_time"
    # echo "13 DIFFERENCE=$(( $alive_mtime - $threshold_time ))"
    # echo "01 DIFFERENCE=$(( $alive_mtime - $usual_time ))"

     if [ $alive_mtime -lt $threshold_time ]; then
         stillalive=1 # means it is dead
     fi

    if [ $stillalive -ne 1 ] ; then
        echo `date` "Still alive: $alive_stamp "
        # no data copied to any log though
    else
        deadduration=$(($threshold_time - $alive_mtime))
        HOURS=$(( deadduration / 3600 ))
        REMAINING_SECONDS=$(( deadduration % 3600 ))
        MINUTES=$(( REMAINING_SECONDS / 60 ))
        echo `date` "Keep_alive is OLD: by ${HOURS}h${MINUTES}m  (${deadduration}s) $alive_stamp "
    fi
fi

if [ $overdue_updated -ne 0 ]; then
  touch ${root_dir}nmea_logs/nmealogger-hung.txt     
  # we are overdue, but is there a keep_alive? 
  if [ $stillalive -ne 0 ]; then
      echo `date` "Alive: but no .nmea update in $threshold minutes. $updated $file_stamp nmeachecker.sh" >> error_file
  else
      # so kill the .py process, which terminates the .sh script
      # cron will then restart it in 3 minutes
      echo `date` "Hung: no .nmea update in $threshold minutes.  $updated $file_stamp nmeachecker.sh" 
      echo `date` "Hung: no .nmea update in $threshold minutes.  $updated $file_stamp nmeachecker.sh" >> error_file
      pkill -ef "python /root/nmea_gps/nmealogger.py"
      exit 1
  fi
fi

# if it is between 1 and 13 minutes overdue, just make a note.
if [ $usual_updated -ne 0 ]; then
    echo `date` "No .nmea files in '$directory' have been updated in the last $usual minutes. "
    echo `date` "Slow: no .nmea update in $usual minutes.  nmeachecker.sh $youngest_mtime $youngest_fn" >> error_file
fi
exit 0