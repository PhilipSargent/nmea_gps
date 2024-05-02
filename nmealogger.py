"""
nmealogger.py
Philip Sargent

TO DO Stop it starting if it is already running and working!, or kill the one that is running and force it to start a new 
nmea output file - instead of relying on the crontab line:
*/3 * * * * pgrep  "python"> /dev/null || python /root/nmea_gps/nmealogger.py
which kills _every_ python process!

archive raw NMEA which stays on the SD card but also filtered NMEA which gets uploaded once an hour.

Derived from nmeasocket.py
    A simple example implementation of a GNSS socket reader
    using the pynmeagps.NMEAReader iterator functions.
    Created on 05 May 2022
    @author: semuadmin
"""

import socket
import time as tm
import pynmeagps.exceptions as nme

from pathlib import Path
from datetime import datetime, date

from pynmeagps.nmeareader import NMEAReader
from pynmeagps.nmeatypes_core import (
    ERR_LOG,
    ERR_RAISE,
    GET,
    NMEA_HDR,
    VALCKSUM,
    VALMSGID,
)
global msgcount, msggood

class NewDay(Exception):
    """
    When the UTC day changes, which is about 3am Greek time in Summer
    """
class Stack:
  """
  A simple stack implementation with a maximum size.
  We are using it to store tuples of (raw, hdop)
  """
  def __init__(self, max_size):
    self.max_size = max_size
    self.items = []

  def is_empty(self):
    return len(self.items) == 0

  def is_full(self):
    return len(self.items) == self.max_size

  def push(self, item):
    if self.is_full():
      print("Stack Overflow! Cannot add item.")
    else:
      self.items.append(item)

  def pop(self):
    if self.is_empty():
      print("Stack Underflow! Cannot remove item.")
      return None
    else:
      return self.items.pop()

  def flush(self):
    self.items = []
 
  def best(self):
    # for (raw, hdop) tuple, return raw value with lowest HDOP
    besthdop = 99
    for i in self.items:
        raw, hdop = i
        if hdop < besthdop:
            besthdop = hdop
            bestnmea = raw
    return bestnmea


def parsestream(nmr, af, rawf):
    """Runs indefinitely unless there is a parse error or interrupt when it produces an exception
    """
    global msgcount, msggood
    # Create an instance of the Stack class
    stack_size = 6
    data_stack = Stack(stack_size)

    for (raw, parsed_data) in nmr:
        if not parsed_data:
            # skip unparseable, even if there is no exception thrown - never happens ?
            print(raw)
            continue
        else:
            d = parsed_data.__dict__
        
        # GSV is the number of satellites in view.. drop
        # GSA gives PDOP as well as HDOP and VDOP, but we don't need it. This is the only source for VDOP
        # VTG is course over ground, but this is instantaneous so useless for us.
        #if parsed_data.msgID not in ['GSV', 'GSA', 'VTG']:
            #print(f"{raw}")
            #pass
            
        # We need RMC for the date. Others only give time.
        if 'date' in d:
            if 'thisday' not in locals(): # first date seen
                thisday = d['date']
                lastday = thisday
                print("++ Set today's date")
                af.write(raw) # write the date line to the filtered archive just the once
                good_data_at = tm.time()
            else:
                thisday = d['date']   
                if thisday != lastday:
                    # print("++ NEXT DAY")
                    raise NewDay
                           
        if 'thisday' not in locals():
            # print("-- No date yet...")
            continue # ignore all NMEA until we get a date       

        if 'time' in d:
            t = d['time']
            # if 'thistime' not in locals():
                # thistime = t
                # lasttime = thistime
            # else:
                # thistime = t
                # today = date.today()
                # thisd = datetime.combine(today, thistime)
                # lastd = datetime.combine(today, lasttime)
                # duration = thisd - lastd
                # if duration.seconds > 60:
                    # print("++ NEXT ~")
                    # raise NewDay
        else: 
            t = 0
            
        if 'HDOP' not in d:
            hdop = ""
        else:
            hdop = f"{float(d['HDOP']):4.2f}"

        if 'lat' in d:
            lat = d['lat']
            lon = d['lon']
            if 'HDOP' in d:
                if float(d['HDOP']) > 3 or lat =="":
                    print(f"{parsed_data.msgID}  {thisday} {t} {lat=:<13} {lon=:<13} {hdop=} ") # last 2 digits always 33 or 67. They are strings.
            if lat != "":
                rawf.write(raw)
                if 'HDOP' in d and float(d['HDOP']) < 3: # rather crude.. 
                    # TO DO
                    # a 6-deep queue and ideally, calc average, weighted by HDOP.. hang on, this is actually a bit tricky...
                    # just pick the best out of the 6 then.
                    
                    # Push data to the stack
                    data_stack.push((raw, float(d['HDOP'])))
                    if data_stack.is_full():
                        af.write(data_stack.best())
                        data_stack.flush()
                        good_data_at = tm.time()
                        msggood += 1
                        # print(f"{parsed_data.msgID}  {thisday} {t} {lat=:<13} {lon=:<13} {hdop=} ")
                now = tm.time()
                time_since_good = 10 * 60 # ten minutes
                if now - good_data_at > time_since_good: # seconds
                    # log anyway, even if bad quality data
                    # should write an extra log file about these..
                    af.write(raw)
                    print(f"{parsed_data.msgID}  {thisday} {t} {lat=:<13} {lon=:<13} {hdop=} BAD DATA BUT USING ANYWAY ") 
                    good_data_at = start = tm.time()
            else:
                    lat = 0
                    lon = 0

        msgcount += 1
        

def readstream(stream: socket.socket):
    """
    Reads and parses NMEA message from socket stream.
    """
    global msgcount, msggood

    start = datetime.now() # This is timezone time, not UTC which comes from the GPS signal
    totcount = 0
    totgood = 0
 

    nmr = NMEAReader(
        stream,
        quitonerror = ERR_RAISE,
    )
    file_bufsize = 1024
    
    # nmea_data gets rsync'd to server, nmea_raw does not.
    parentdir = Path(__file__).parent.parent
    archivedir = parentdir / Path("nmea_data") / Path(start.strftime('%Y-%m'))
    archivedir.mkdir(parents=True, exist_ok=True)
 
    rawdir = parentdir / Path("nmea_raw") / Path(start.strftime('%Y-%m'))
    rawdir.mkdir(parents=True, exist_ok=True)
 
    while True:
        msgcount = 0
        msggood = 0

        try:
            newstart = datetime.now() # This is timezone time, not UTC which comes from the GPS signal
            archivefilename = archivedir / (newstart.strftime('%Y-%m-%d_%H%M') +".nmea")
            rawfilename = rawdir / (newstart.strftime('%Y-%m-%d_%H%M') +".nmea")
                
            print(f"Writing {archivefilename}  and  {rawfilename}")
            with open(archivefilename, 'ab', buffering=file_bufsize) as af: # ab not wr just in case the filename is unchanged.. 
                with open(rawfilename, 'ab', buffering=file_bufsize) as rawf: # ab not wr just in case the filename is unchanged.. 
                    while True:
                        # why is FIleNotFound exception not thrown here if the file is deleted ?
                        try:
                            parsestream(nmr, af, rawf)
                        except nme.NMEAParseError:
                            # ignore whole sentence and continue
                            print("-- PARSE ERROR")
                            continue
        except KeyboardInterrupt:
            totcount += msgcount
            totgood += msggood
            dur = datetime.now() - start
            secs = dur.seconds + dur.microseconds / 1e6
            print("Session terminated by user")
            print(
                f"{totcount:,d} messages read in {secs:.2f} seconds.",
                f"{totgood:,d} lat/lon messages logged, at",
                f"{totgood/secs:.2f} msgs per second",
            )
            break
        except NewDay:
            # this is bad style. Really a GOTO statement.
            print("-- Next Day - restart logfile")
            totcount += msgcount
            totgood += msggood

            continue


if __name__ == "__main__":

    SERVER = "192.168.8.60" # the QK-A026
    PORT = 2000

    print(f"Opening socket {SERVER}:{PORT}...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((SERVER, PORT))
        readstream(sock)