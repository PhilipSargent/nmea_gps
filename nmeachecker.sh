#!/bin/sh 
# Originally written by Gemini

# Define threshold (in minutes)
threshold=1

# define directory, on Guava router, to check for updates.
directory=/root/nmea_data/2024-05
directory=../nmea_data/2024-05

# Get the current time (in seconds since epoch)
current_time=$(date +%s)

# Calculate the threshold time (current time minus threshold in minutes)
threshold_time=$((current_time - (threshold * 60)))

# Loop through files in the directory
found_updated=0  # Flag to track if any updated file is found

for filename in $(ls -1 "$directory"); do
  filepath="$directory/$filename"
  # echo "$directory/$filename"

  # Check if it's a regular file (skip directories, etc.)
  if [ -f "$filepath" ]; then
    # Get the file modification time
    
    # stat requires coreutils
    # file_mtime=$(stat -c %Y "$filepath")
    ls -l "$filepath"
    file_mtime=$(date -r "$filepath" +%s)

    # Compare with threshold time
    if [ $file_mtime -gt $threshold_time ]; then
      echo "File '$filepath' has been updated in the last $threshold minutes."
      found_updated=1
    fi
  fi
done

# Handle results
if [ $found_updated -ne 1 ]; then
  echo "No files in '$directory' have been updated in the last $threshold minutes."
  touch /root/nmea_data/nmealogger-hung.txt
  ./nmealogger.sh &
  exit 1
fi

exit 0