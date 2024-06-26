"""
nmealogger.py
Philip Sargent

archive raw NMEA which stays on the SD card but also filtered NMEA which gets uploaded every 7 minutes (crontab)


Run from a shell script, which terminates if this terminates.
crontab pgrep detects isf the shell script is running, and if not, it restarts the shell script and thus this
programe.

Puzzle: this terminates at random, and I don't know why yet. But crontab restarts fine.

Problem: over-stressing anchor winch got the router into a strange condition where 
it did not load extroot and so nothing was running. Thsi can only be detected by something
running on another machine, i.e. the server to which regular uploads are made by copynmea.sh

Derived from nmeasocket.py
https://github.com/semuconsulting/pynmeagps
    A simple example implementation of a GNSS socket reader
    using the pynmeagps.NMEAReader iterator functions.
    Created on 05 May 2022
    @author: semuadmin
"""
import errno, os

import resource
import socket
import sys
import time as tm
import pynmeagps.exceptions as nme

from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo

from pynmeagps.nmeareader import NMEAReader

from pynmeagps.nmeatypes_core import (
    ERR_LOG,
    ERR_RAISE,
    GET,
    NMEA_HDR,
    VALCKSUM,
    VALMSGID,
)
global msgcount, msggood, msgparse, msgqk
msg_by_id = {}

totcount = 0
totgood = 0
totparse = 0
totqk = 0

HDOP_LIMIT = 3
MAX_WAIT = 10 * 60 # 10 minutes in seconds
LONG_ENOUGH = 300000 # Max messages before restart logs


TZ = ZoneInfo('Europe/Athens')

class NewDay(Exception):
    """
    When the UTC day changes, which is about 3am Greek time in Summer
    """
class NewLogs(Exception):
    """
    Finish logs and start new ones
    """
    
class Bad_stash:
    """We keep the most recent, but poor data location, so that when time is up
    we can output the best guess from the whole poor period
    """
    def __init__(self):
        self.hdop = 99
        self.raw = None
        self.parsed = None
        self.lat = None
        self.lon = None
        self.t = None
    
    def put(self, raw, parsed, hdop, lat, lon, t):
        if hdop <= self.hdop: # overwrite even if equal, a later estimate better?
            self.raw = raw
            self.parsed = parsed
            self.hdop = hdop
            self.lat = lat
            self.lon = lon
            self.t = t
            
    def get(self):
        if not self.raw: #  None
            print("Stash empty. Cannot remove item.", flush=True)
            return None
        else:
            return (self.raw, self.parsed, self.hdop, self.lat, self.lon, self.t)
            
    def flush(self):
        self.__init__()
        
    def is_available(self):
        if self.raw:
            return True
        else:
            return False
    
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
            print("Stack Overflow! Cannot add item.", flush=True)
        else:
            self.items.append(item)

    def first(self, msg=None):
        if self.is_empty():
            print("Queue Underflow! Cannot remove item. {msg}", flush=True)
            return None
        else:
            first = self.items.pop(0)
            return first

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

# Create a module-level instance of the Stack class which is unique, i.e. a singleton
RUNNING_STACK = 6
data_stack = Stack(RUNNING_STACK)

def print_summary(msg=None):
    global totcount, totgood, totparse, totqk,  start, msg_by_id
    
    totcount = msgcount
    totgood = msggood
    totparse = msgparse
    totqk = msgqk
    
    stamp = datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M %Z')
    dur = datetime.now(tz=TZ) - start
    secs = dur.seconds + dur.microseconds / 1e6

    print(f"{stamp} - Memory footprint: {resource.getrusage(resource.RUSAGE_SELF)[2] / 1024.0:.6f} MB  {msgcount:,d}  {msg}", flush=True)
    print(
    f"\n {totcount:,d} messages read in {secs:.2f} seconds ({secs/3600:.2f} hours)",
    f"\n {totgood:,d} messages with valid lat/lon logged,",
    f"\n   {totgood/secs:.2f} msgs per second",
    f"\n   {totqk:,d} QK corruptions",
    f"\n   {totparse:,d} parse errors ({totparse/totcount:.2%})",
    flush=True,
    )
    for id in msg_by_id:
        print(f"   {id}  {msg_by_id[id]} parse errors",flush=True)

def strim(nmealat):
    """Strims off the ..667 or ..333 at the end of the string
    we do not need this pointless precision"""
    st = str(nmealat)
    if len(st) < 13:
        return nmealat
    
    if st[10:] == "333":
        st = st[:11]
    if st[10:] == "667":
        st = st[:10] + "7"
    return float(st)
    

def parsestream(nmr, af, archivefilename, rawf, rawfilename):
    """Runs indefinitely unless there is a parse error or interrupt when it produces an exception
    """
    global msgcount, msggood, msgparse, msgqk, data_stack, msg_by_id
    PREDATE_STACK = 20
    AGED_FILE = 60 * 2 # 2 minutes

    pre_date_stack = Stack(PREDATE_STACK)
    
    poor_data = Bad_stash()
    got_data_at = tm.time()
    # print(f"== Restarted parsestream")
    
    while True: # to cope with parse exception breaking the infinite generator
        try:
            for (raw, parsed_data) in nmr: # nmr is an infinite iterator - or is meant to be !
                if msgcount > LONG_ENOUGH - 1:
                    raise NewLogs
                    
                if not archivefilename.is_file():
                    raise FileNotFoundError( errno.ENOENT, os.strerror(errno.ENOENT), archivefilename)
                if not rawfilename.is_file():
                    raise FileNotFoundError( errno.ENOENT, os.strerror(errno.ENOENT), rawfilename)
                    
                pre_size = rawfilename.stat()
                pre_mod_time = rawfilename.stat().st_mtime # modification time - check if process hung somehow
                pre_time = tm.time()
                
                # This is to check for hung process, but it never gets triggered. Hang must be somewhere else.. inside nmr ?
                since = pre_time - pre_mod_time
                if  since > 2 * AGED_FILE:
                    print_summary(f"\n__ Very long time since last {rawfilename.name} modification: {since/60:.2f} minutes")        
                elif  since > AGED_FILE:
                    print(f"_  Long time since last {rawfilename.name} modification: {since/60:.2f} minutes")    
                    
            
                if not parsed_data:
                    # skip unparseable, even if there is no exception thrown - happens when QK butts in.
                    # Hmm. this is not working...
                    try:
                        if "Quark-elec:No valid AIS signal." in raw.decode("utf-8", "strict"):
                            print(f"Quark-elec corruption (utf8):",raw.decode("utf-8", "strict"), flush=True)
                            msgqk += 1
                        else:
                            print(f"Unparsed data (utf8):",raw.decode("utf-8", "strict"), flush=True)
                    except:
                        print(f"Unparsed data: (binary)",raw, flush=True)
                        msgparse += 1
                    continue
                else:
                    d = parsed_data.__dict__
                
                # GSV is the number of satellites in view.. drop
                # GSA gives PDOP as well as HDOP and VDOP, but we don't need it. This is the only source for VDOP
                # VTG is course over ground, but this is instantaneous so useless for us.
                    
                # We need RMC for the date. Others only give time. 
                # Sometimes the RMC sentence is corrupted, but still has valid checksum, so date is invalid.
                if 'date' in d and d['date'] != "":
                    if 'thisday' not in locals(): # first date seen in this run of parsestream
                        thisday = d['date']
                        lastday = thisday
                        print(f"++ Set today's date {thisday} '{len(pre_date_stack.items)}' lat/lon items in pre_date queue", flush=True)
                        af.write(raw) # write the date line to the filtered archive just the once
                        af.flush()
                        good_data_at = tm.time()
                        
                        if not pre_date_stack.is_empty():
                            while not pre_date_stack.is_empty():
                                i_raw, i_hdop = pre_date_stack.first(msg="pre_date items")
                                # but just throw them away
                                print(">> ",i_raw.decode("utf-8", "strict"), end="")
                            print(f"-- over {tm.time() - pre_time:.4f} seconds")
                    else:
                        thisday = d['date']   
                        if thisday != lastday: # happens at UTC, i.e. 0300 Europe/Athens timezone.
                            # print("++ NEXT DAY", flush=True)
                            pre_date_stack.flush()
                            raise NewDay
                            
                if 'time' in d:
                    t = d['time']
                else: 
                    t = 0
                                   
                if 'thisday' not in locals(): # ie first time since restart
                    stamp = datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M %Z')
                    # print(f"{stamp} -- {parsed_data.msgID} No date yet... (utf8):",raw.decode("utf-8", "strict")[:-2], flush=True)
                    if 'lat' in d and 'lon' in d and 'HDOP' in d: # note HDOP does not mean there is a lat/lon, GPGSA gives HDOP too.
                        pre_date_stack.push((raw, float(d['HDOP'])))
                        # print(f"{parsed_data.msgID}  {t} pre_date ADD", flush=True)
                        if pre_date_stack.is_full():
                            print(f"{stamp} -- {parsed_data.msgID} pre_date queue full. Flushing..|", flush=True)
                            pre_date_stack.flush()
                    continue # next NMEA sentence..

                        
                    
                if 'HDOP' not in d:
                    hdop = ""
                else:
                    hdop = f"{float(d['HDOP']):4.2f}"

                if 'lat' in d and 'lon' in d:
                    lat = strim(d['lat'])    
                    lon = strim(d['lon'])
                    if 'HDOP' in d:
                        if float(d['HDOP']) > HDOP_LIMIT or lat =="":
                            print(f"{parsed_data.msgID}  {thisday} {t} UTC  {lat=:<13} {lon=:<13} {hdop=} {d['HDOP']}", flush=True) # last 2 digits always 33 or 67. They are strings.
                    if lat != "":
                        rawf.write(raw)
                        rawf.flush()
                        post_size = rawfilename.stat()
                        if post_size <= pre_size:
                            print(f"{parsed_data.msgID}  {thisday} {t} UTC  - FAILED TO UPDATE RAW FILE, aborting.. ", flush=True) 
                            pre_date_stack.flush()
                            raise NewDay

                        if 'HDOP' in d:
                            if float(d['HDOP']) >= HDOP_LIMIT: # rather crude.. 
                                poor_data.put(raw, parsed_data, float(d['HDOP']), lat, lon, t)
                            else:
                                # TO DO
                                # a 6-deep queue and ideally, calc average, weighted by HDOP.. hang on, this is actually a bit tricky...
                                # just pick the best out of the 6 then.
                                
                                # TO DO : CHECK that these data points are all within a second or two ! Otherwise we throw away data we need.
                                
                                # Push data to the stack
                                data_stack.push((raw, float(d['HDOP'])))
                                if data_stack.is_full():
                                    af.write(data_stack.best())
                                    af.flush()
                                    data_stack.flush()
                                    got_data_at = tm.time()
                                    msggood += 1
                                
                                
                        now = tm.time()
                        if now - got_data_at > MAX_WAIT: # seconds
                            # Add to log anyway, even if bad quality data
                            # should write an extra log file about these..
                            if poor_data.is_available():
                                poor_raw, poor_parsed_data, poor_hdop, poor_lat, poor_lon, poor_t = poor_data.get()
                                af.write(poor_raw)
                                af.flush()
                                print(f"{poor_parsed_data.msgID}  {thisday} {poor_t} {poor_lat=:<13} {poor_lon=:<13} {poor_hdop=} POOR DATA BUT USING ANYWAY AS TIMEOUT") 
                                poor_data.flush()
                                got_data_at = tm.time()
                            else:
                                print(f"Empty poor data stash.  {thisday} computer time: {now} TIMEOUT but not even poor data available") 
                            got_data_at = tm.time()
                    else:
                            lat = 0
                            lon = 0

                if msgcount in [0, 500, 1000, 10000, 50000, 100000, 200000]: 
                    print(f"{datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M %Z')} - Memory footprint: {resource.getrusage(resource.RUSAGE_SELF)[2] / 1024.0:.6f} MB  {msgcount:,d}", flush=True)
                msgcount += 1            
                # if msgcount % 100000 == 0: 
                    # print_summary(msg="")
                    
            print(f"~~ No more data in iterator 'nmr'. This should never happen.")
                    
        except nme.NMEAParseError as e:
            
            # print(f"{datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M %Z')} Parse EXCEPTION in parsestream\n {e}", flush=True)
            # if 'raw' in locals(): # this is probably not the correct one for this error!
                # print(f"raw:{raw}", flush=True)
            if parsed_data.msgID not in msg_by_id:
                msg_by_id[parsed_data.msgID] = 0
            msg_by_id[parsed_data.msgID] += 1
            msgparse += 1
            # clears exception so calling routine just continues its while True loop
            pre_date_stack.flush()

    print(f"~~ Dropped off end of parsestream function. This should not happen as it is in a while True loop.")

 
def readstream(stream: socket.socket):
    """
    Reads and parses NMEA message from socket stream.
    """
    global totcount, totgood, totparse, totqk, msgcount, msggood, msgparse, msgqk, start, msg_by_id 

    start = datetime.now(tz=TZ) # This is timezone time, not UTC which comes from the GPS signal
    
    # print(f"{start.strftime('%Y-%m-%d %H:%M %Z')} - Memory footprint on starting: {resource.getrusage(resource.RUSAGE_SELF)[2] / 1024.0:.6f} MB", flush=True)
 

    # Note that NMEAreader skips any lines which are not NMEA GPS,
    # so all the !AI... AIS messages are skipped as if they never existed.
    nmr = NMEAReader(
        stream,
        quitonerror = ERR_RAISE,
    )
    file_bufsize = 1024
    
    # nmea_data gets rsync'd to server, nmea_raw does not.
    parentdir = Path(__file__).parent.parent
    archivedir = parentdir / Path("nmea_data") / Path(start.strftime('%Y-%m'))
    archivedir.mkdir(parents=True, exist_ok=True)
 
    rawdir = parentdir / Path("nmea_rawd") / Path(start.strftime('%Y-%m'))
    rawdir.mkdir(parents=True, exist_ok=True)
 
    while True:  # when parse errors caused this to restart, this was sensible. But now all exceptions terminate except NewDay.
        msgcount = 0
        msggood = 0
        msgparse = 0
        msgqk = 0

        try:
            newstart = datetime.now(tz=TZ) # This is timezone time, not UTC which comes from the GPS signal
            archivefilename = archivedir / (newstart.strftime('%Y-%m-%d_%H%M') +".nmea")
            rawfilename = rawdir / (newstart.strftime('%Y-%m-%d_%H%M') +".nmea")
                
            print(f"Writing\n {archivefilename}\n {rawfilename}", flush=True)
            with open(archivefilename, 'ab', buffering=file_bufsize) as af: # ab not wr just in case the filename is unchanged.. 
                with open(rawfilename, 'ab', buffering=file_bufsize) as rawf: # ab not wr just in case the filename is unchanged.. 
                    while True:
                        try:
                            parsestream(nmr, af, archivefilename, rawf, rawfilename)
                        except nme.NMEAParseError as e:
                            print(f"{datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M %Z')} ParseError EXCEPTION caught OUTSIDE parsestream\n {e}", flush=True)
                            msgparse += 1
                            continue
        except NewDay:
            # this is bad style. Really a GOTO statement.
            print_summary("-- Next Day - restart logfiles")
            msg_by_id = {}
            continue
        except NewLogs:
            # this is bad style. Really a GOTO statement.
            print_summary("-- Same day, but restart logfiles")
            msg_by_id = {}
            continue

        except KeyboardInterrupt:
            print_summary("Keyboard interrupt")
            break
        except FileNotFoundError as e:
            # This was raised explicitly in parsestream
            print_summary(f"FileNotFound error: {archivefilename}  or  {rawfilename}, restarting with new file.\n {e}")
            break
        except Exception as e: 
            print_summary(f"generic EXCEPTION\n {e}")
            raise e
            break

        sys.exit(1)

if __name__ == "__main__":

    SERVER = "192.168.8.60" # the QK-A026
    PORT = 2000
    max_tries = 200
    socket_delay = 0.1 # seconds
    
    if len(sys.argv) == 3:
        SERVER = sys.argv[1]
        PORT = int(sys.argv[2])


    if len(sys.argv) == 2:
        print(f"Either with no parameters or with server ip and port, e.g.\n$ python nmealogger.py 0.0.0.0 65432", flush=True)
        sys.exit(1)
        
    
    print(f"Opening socket {SERVER}:{PORT}...", flush=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        tries = 1
        while True:
            try:
                sock.connect((SERVER, PORT))
                if tries > 1:
                    print(f"++ Socket connected after {tries} tries")
                break
            except OSError:
                if tries >= max_tries:
                    print(f"++ Socket connection failed after {tries} tries = {tries*socket_delay} seconds. Exiting.")
                    sys.exit(1)
                tries += 1
                tm.sleep(socket_delay)

                continue
        readstream(sock)