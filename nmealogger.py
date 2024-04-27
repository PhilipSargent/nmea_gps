"""
nmealogger.py
Philip Sargent

Derived from nmeasocket.py
    A simple example implementation of a GNSS socket reader
    using the pynmeagps.NMEAReader iterator functions.
    Created on 05 May 2022
    @author: semuadmin
"""

import socket
import pynmeagps.exceptions as nme

from pathlib import Path
from datetime import datetime, date, time

from pynmeagps.nmeareader import NMEAReader

global msgcount, msggood

class NewDay(Exception):
    """
    When the UTC day changes, which is about 3am Greek time in Summer
    """

def parsestream(nmr, af):
    """Runs indefinitely unless there is a parse error or interrupt when it produces an exception
    """
    global msgcount, msggood

    for (raw, parsed_data) in nmr:
        if not parsed_data:
            # skip unparseable, even if there is no exception thrown
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
            else:
                thisday = d['date']            
                if thisday != lastday:
                    print("++ NEXT DAY")
                    raise NewDay
                # if msggood > 5000:
                    # raise NewDay
                           
        if 'thisday' not in locals():
            # print("-- No date yet...")
            continue # ignore all NMEA until we get a date       

        if 'time' in d:
            t = d['time']
            if 'thistime' not in locals():
                thistime = t
                lasttime = thistime
            else:
                thistime = t
                today = date.today()
                thisd = datetime.combine(today, thistime)
                lastd = datetime.combine(today, lasttime)
                duration = thisd - lastd
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
                if float(d['HDOP']) > 10 or lat =="":
                    print(f"{parsed_data.msgID}  {thisday} {t} {lat=:<13} {lon=:<13} {hdop=} ") # last 2 digits always 33 or 67. They are strings.
            if lat != "":
                af.write(raw)
                msggood += 1
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
    )
    file_bufsize = 1024
    archivedir = Path(start.strftime('%Y-%m'))
    archivedir.mkdir(exist_ok=True)
    
    while True:
        msgcount = 0
        msggood = 0

        try:
            newstart = datetime.now() # This is timezone time, not UTC which comes from the GPS signal
            archivefilename = archivedir / (newstart.strftime('%Y-%m-%d_%H%M') +".nmea")
                
            print(f"Writing {archivefilename}")
            with open(archivefilename, 'ab', buffering=file_bufsize) as af: # ab not wr just in case the filename is unchanged.. 
                while True:
                    try:
                        parsestream(nmr, af)
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
            print("-- Next Day - restart logfile")
            totcount += msgcount
            totgood += msggood

            continue


if __name__ == "__main__":

    SERVER = "192.168.8.60"
    PORT = 2000

    print(f"Opening socket {SERVER}:{PORT}...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((SERVER, PORT))
        readstream(sock)