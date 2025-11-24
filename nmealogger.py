"""
nmealogger.py
Philip Sargent

archive raw NMEA which stays on the SD card but also filtered NMEA which gets uploaded every 7 minutes (crontab)


Run from a shell script, which terminates if this terminates.
crontab pgrep detects if the shell script is running, and if not, it restarts the shell script and thus this
programe.

Puzzle: this terminates at random, due to bad SD card, now replaced. crontab restarts fine.

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
import math
import psutil
import resource
import socket
import subprocess
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
MAX_WAIT_GNSS = 10 * 60 # 10 minutes in seconds
LONG_ENOUGH = 300000 # Max messages before restart track record in a new file

CURRENT_TRACK_RECORD = "current_nmea_file.txt"
CONNECT_FAILURE = "connect_failure.txt"
HUNG_CHECK = 13 * 60 # seconds, i.e. 13 minutes, in crontab
AIS_DEVICE = "QK A026"
SERVER = "192.168.8.60" # the AIS_DEVICE
#SERVER = "127.0.0.1" # TEST
PORT = 2000
#PORT = 65432 # TEST

SOCKET_TIMEOUT = 2
TZ = ZoneInfo('Europe/Athens')

class NewDay(Exception):
    """
    When the UTC day changes, which is about 3am Greek time in summer, 2am in winter
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
        # this does not check that all the items are within a second or so, which it should
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
    
    if totcount == 0:
        pcent = 0
    else:
        pcent = totparse/totcount

    print(f"{stamp} - Memory footprint: {resource.getrusage(resource.RUSAGE_SELF)[2] / 1024.0:.6f} MB  {msgcount:,d}  {msg}", flush=True)
    print(
    f"\n {totcount:,d} messages read in {secs:.2f} seconds ({secs/3600:.2f} hours)",
    f"\n {totgood:,d} messages with valid lat/lon logged,",
    f"\n   {totgood/secs:.3f} msgs/s {60*totgood/secs:.3f} msgs/minute",
    f"\n   {totqk:,d} QK corruptions",
    f"\n   {totparse:,d} parse errors ({pcent:.2%})",
    flush=True,
    )
    for id in msg_by_id:
        print(f"   {id}  {msg_by_id[id]} parse errors",flush=True)

def strim(nmealat):
    """Strims off the ..667 or ..333 at the end of the string
    we do not need this pointless and artificial precision"""
    st = str(nmealat)
    if len(st) < 13:
        return nmealat
    
    if st[10:] == "333":
        st = st[:11]
    if st[10:] == "667":
        st = st[:10] + "7"
    return float(st)
    

def parsestream(nmr, af, archivefilename, rawf, rawfilename):
    """Runs indefinitely unless there is a parse error or interrupt when it produces an exception,
    but it seems to hang frequently.
    """
    global msgcount, msggood, msgparse, msgqk, data_stack, msg_by_id
    runcount = 0
    PREDATE_STACK = 20
    AGED_FILE = 60 * 2 # 2 minutes
    NMR_DELAY = 0.5 # seconds when nmr iterator rus out of steam
    NMR_DELAYS = 50 # number of delays allowed before termination

    pre_date_stack = Stack(PREDATE_STACK)
    
    poor_data = Bad_stash()
    got_data_at = tm.time()
    # print(f"== Restarted parsestream")
    
    while True: # to cope with parse exception breaking the infinite generator
        nmr_delays = -200 # to cope with immediate crash in for loop
        try:
            nmr_delays = -100 # this caused crashes? Or do I just need to reboot router??
            for (raw, parsed_data) in nmr: # nmr is an infinite iterator - or is meant to be !
                nmr_delays = 0
                runcount +=1
                
                # if runcount == 1:
                    # # throw away the first sentence as it is from the previous run, not cleaned out by exception.
                    # continue
 
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
                        if now - got_data_at > MAX_WAIT_GNSS: # seconds
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

                if msgcount in [0, 1000, 10000, 50000, 100000, 200000]: 
                    print(f"{datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M %Z')} - Memory footprint: {resource.getrusage(resource.RUSAGE_SELF)[2] / 1024.0:.6f} MB  {msgcount:,d}", flush=True)
                msgcount += 1            
                # if msgcount % 100000 == 0: 
                    # print_summary(msg="")
                    
            nmr_delays += 1
            #print(f"{datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M %Z')} ~~ No more data in iterator 'nmr' {nmr_delays}. This should never happen.")
            tm.sleep(NMR_DELAY)
            if nmr_delays >= NMR_DELAYS:
                print(f"{datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M %Z')} ~~ {NMR_DELAYS*NMR_DELAY} seconds since nmr iterator response. {nmr_delays} tries. Aborting. ")
                sys.exit(1)
                    
        except nme.NMEAParseError as e:
            
            # print(f"{datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M %Z')} Parse EXCEPTION in parsestream\n {e}", flush=True)
            # if 'raw' in locals(): # this is probably not the correct one for this error!
                # print(f"raw:{raw}", flush=True)
            if 'parsed_data' in locals():
                if parsed_data.msgID not in msg_by_id:
                    msg_by_id[parsed_data.msgID] = 0
                msg_by_id[parsed_data.msgID] += 1
                msgparse += 1
            else:
                print(f"NMEAParseError exception: {e}")
            # clears exception so calling routine just continues its while True loop
            pre_date_stack.flush()

    print(f"{datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M %Z')} ~~ Dropped off end of parsestream function. This should not happen as it is in a while True loop.")

 
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
    
    # directory name to be used, e.g. 2025-11/
    month_dir = Path(start.strftime('%Y-%m'))
    # nmea_data gets rsync'd to server, nmea_rawd does not.
    parentdir = Path(__file__).parent.parent
    archivedir = parentdir / Path("nmea_data") / month_dir
    archivedir.mkdir(parents=True, exist_ok=True)
 
    rawdir = parentdir / Path("nmea_rawd") / month_dir
    rawdir.mkdir(parents=True, exist_ok=True)

    logsdir = parentdir / Path("nmea_logs") 
    logsdir.mkdir(parents=True, exist_ok=True)
  
    while True:  # when parse errors caused this to restart, this was sensible. But now all exceptions terminate except NewDay.
        msgcount = 0
        msggood = 0
        msgparse = 0
        msgqk = 0

        try:
            newstart = datetime.now(tz=TZ) # This is timezone time, not UTC which comes from the GPS signal
            fnstem = newstart.strftime('%Y-%m-%d_%H%M')
            archivefilename = archivedir / (fnstem +".nmea")
            rawfilename = rawdir / (fnstem +".nmea")
            
            current_track = logsdir / Path(CURRENT_TRACK_RECORD)
                
            print(f"Writing\n {archivefilename}\n {rawfilename}", flush=True)
            with open(current_track, 'w', buffering=file_bufsize) as fnf: 
                fnf.write(f"{month_dir}/{fnstem}.nmea")

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

def my_now():
    return datetime.now(tz=TZ).strftime('%Y-%m-%d %H:%M:%S %Z')
    
def seconds_since(start):
    dur = datetime.now(tz=TZ) - start
    return dur.seconds + dur.microseconds / 1e6

def get_seconds_since_file_creation(filepath):
    if not filepath.is_file:
        print(f"Error: File not found at path: {filepath}")
        return None

    try:
        creation_timestamp = os.path.getctime(filepath)       
        return tm.time() - creation_timestamp
    except Exception as e:
        print(f"An error occurred while accessing file '{filepath}' metadata: {e}")
        return None
        
def it_is_alive():
    """The AIS_DEVICE has failed to respond to a repeated request to open a socket,
    is it actually there at all?
    """
    COUNT = 8 
    PING_TIMEOUT = 5 
    
    conns_list = psutil.net_connections(kind='tcp')
    for conn in conns_list:
        if SERVER in f"{conn}":
            prettify_conn(conn)
    
    command = [
    "ping", 
    "-c", str(COUNT), 
    "-W", str(PING_TIMEOUT), 
    SERVER
        ]
    # we check the return code (0 for success)
    # and look for packet loss percentage.
    success_text = f"{COUNT} packets received"
        
    if not in_connect_failure_mode():
        print(f"{my_now()} ++ Pinging {AIS_DEVICE} using: {' '.join(command)}")

    try:
        # 2. Execute the command and capture output
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False  # Do NOT raise an exception on non-zero exit code (ping failure)
        )

        # 3. Check the result
        if result.returncode == 0:
            # print(f"✅ Ping successful! (Return Code 0)")
            # You can parse more details from result.stdout if needed
            return True
        else:
            # print(f"❌ Ping failed. Return Code: {result.returncode}")
            # print(result.stderr or result.stdout)
            return False

    except FileNotFoundError:
        print(f"ERROR: The 'ping' command was not found. Is it installed and in your PATH?")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during ping: {e}")
        return False
        
def prettify_conn(conn):
    # 1. Local Address
    if conn.laddr:
        local = f"{conn.laddr.ip}:{conn.laddr.port}"
    else:
        local = "-"

    # 2. Remote Address
    if conn.raddr:
        remote = f"{conn.raddr.ip}:{conn.raddr.port}"
    else:
        remote = "-"

    # 3. Status (e.g., ESTABLISHED, LISTEN, CLOSE_WAIT)
    status = conn.status

    # 4. Process ID (PID)
    pid = conn.pid if conn.pid else 0

    # 5. Process Name
    process_name = "-"
    if pid > 0:
        try:
            # Look up the process name using its PID
            p = psutil.Process(pid)
            process_name = p.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "[Unknown/Access Denied]"
     
    print(f"{my_now()} -- Conn. status:", local, remote, status, pid, process_name)
    # return (local, remote, status, pid, process_name)

def get_noconnect_flag():
    logsdir = parentdir = Path(__file__).parent.parent / Path("nmea_logs") 
    connect_failure = logsdir / Path(CONNECT_FAILURE)
    return connect_failure

def get_aliveness_filepath():
    logsdir = parentdir = Path(__file__).parent.parent / Path("nmea_logs") 
    aliveness = logsdir / Path("still_alive.txt")
    return aliveness

def format_dur(age):
    age = math.floor(age) # integer
    return f"{age // 3600:02d}h {age % 3600 // 60:02d}m {age % 60:02d}s"

def active_wait(wait):
    """Waits for 'wait' seconds, but regularly touches a heartbeat file
    so that this process does not look as if it has hung - which would
    get it terminated by the nmeacheacker.sh script which crontab runs
    every 13 minutes
    """
    touch_interval = HUNG_CHECK - 30
    
    if wait <= 0 :
        get_aliveness_filepath().touch() 
        return
    num_intervals = math.floor(wait / touch_interval)
    remaining_wait = wait % touch_interval # modulo division
    schedule =  [touch_interval] * num_intervals + [remaining_wait]
    for delay in schedule:
        # touch a marker file to that nmeachecker.sh does not think that this has hung
        get_aliveness_filepath().touch() 
        tm.sleep(delay)
    
WAIT_FOR_AIS_RESET = 60*5 # 5 minutes
WAIT_FOR_AIS_RESET = 10 # test
def wait_and_exit():
    """Insert a wait before exit to allow user to reset the AIS_DEVICE but
    mostly to prevent clogging up the log files with repeated retries which we are pretty sure will 
    not do anything useful.
    Note that the router is rebooted twice a day, so this will always run twice a day on bootup.
    """
    
    if in_connect_failure_mode():
        # This is not the first time this has happened.
        age = get_seconds_since_file_creation(get_noconnect_flag()) 
        delay = max(WAIT_FOR_AIS_RESET, age)
        # insert a geometric wait time, bounded by 24 hours
        print(f" {format_dur(age)} since most recent connection failure.")
        wait = min(24*60*60, delay*1.5) # never more than 24h
    else:
        wait = WAIT_FOR_AIS_RESET
        set_noconnect_flag()
        
    print(f"Waiting  {format_dur(wait)} before exit, and then inevitable restart (crontab).")
    active_wait(wait)
    sys.exit(1)
    
def set_noconnect_flag():
    connect_failure = get_noconnect_flag()
    with open(connect_failure, 'w') as fnf: 
        fnf.write(f"Failed to connect {AIS_DEVICE} at {SERVER}:{PORT}")
        print(f"{my_now()} SET connect failure flag.")

    
def clear_noconnect_flag():
    connect_failure = get_noconnect_flag()
    if connect_failure.is_file():
        connect_failure.unlink() # deletes flag
        print(f"{my_now()} UNSET connect failure flag.")
        
def in_connect_failure_mode():
    connect_failure = get_noconnect_flag()
    if connect_failure.is_file():
        return True
    else:
        return False
        
if __name__ == "__main__":

    WAITS_LIST = [4, 8, 16, 32, 64]
    # WAITS_LIST = [1, 2] #TEST
    max_tries = len(WAITS_LIST)
    max_total_tries = 1 + max_tries * 4
    
    if len(sys.argv) == 3:
        SERVER = sys.argv[1]
        PORT = int(sys.argv[2])


    if len(sys.argv) == 2:
        print(f"Either with no parameters or with server ip and port, e.g.\n$ python nmealogger.py 0.0.0.0 65432", flush=True)
        sys.exit(1)
        
    start_open = datetime.now(tz=TZ)
    print(f"{my_now()} ++ Starting nmealogger. Opening socket {SERVER}:{PORT}... (timeout is {SOCKET_TIMEOUT}s per try)", flush=True)  
    
    # more attempts to connect, but this time arround, suppress voluminous error printouts
    first_time = not in_connect_failure_mode()
         
    total_tries = 1
    while True:
        tries = 1
        for wait in WAITS_LIST:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock: # do not attemot to re-use, create a new socket object.
                sock.settimeout(SOCKET_TIMEOUT) 
                try:
                    sock.connect((SERVER, PORT))
                    sock.settimeout(None) # prevent blocking
                    if tries == 1:
                        # print(f"{my_now()} ++ Socket good. Connected after first try.", flush=True)
                        pass
                    else:
                        print(f"{my_now()} ++ Socket connected but maybe unreliable: Needed {total_tries} tries, after {seconds_since(start_open):.0f} seconds.", flush=True)
                except OSError as e:
                    # print(f"{my_now()} ++ Socket OSError '{e}'. After {tries} tries.", flush=True)
                    if tries >= max_tries:
                        if(first_time):
                            print(f"{my_now()} ## Socket connection failed ({tries} attempts), after {seconds_since(start_open):.0f} seconds.", flush=True)
                        if it_is_alive():
                            # keep trying, it's hung but it's there..
                            if total_tries >= max_total_tries:
                                print(f"{my_now()} ## Still no luck after {total_tries} attempts.\n == You do need to power-cycle the  {AIS_DEVICE}: 'AIS' on the boat control panel. ", flush=True)
                                wait_and_exit()
                            if(first_time):
                                print(f"{my_now()} ++ OK ping response. Trying another cycle of opening a socket: {total_tries} attempts in total so far.", flush=True)
                        else:
                            print(f"{my_now()} ## Does not respond to ping.\n == You need to power-cycle the {AIS_DEVICE}: 'AIS' on the boat control panel. ", flush=True)
                            wait_and_exit()
                            
                    tries += 1
                    total_tries += 1
                    tm.sleep(wait)
                    continue # closes attempted socket, starts loop again which creates a new socket
                except Exception as e:
                        print(f"{my_now()} -- Socket connection UNEXPECTED exception {e}\n    {tries} tries, after {seconds_since(start_open):.0f} seconds ({wait=}). Exiting.", flush=True)
                        sys.exit(1)
                        
                # socket opened fine, so clear flags  
                clear_noconnect_flag()    
                
                local_ip, local_port = sock.getsockname()
                remote_ip, remote_port = sock.getpeername()
                print(f"{my_now()} ++ readstream(sock) on {local_ip}:{local_port} to  {remote_ip}:{remote_port}", flush=True)
                readstream(sock) # should be blocking
                print(f"{my_now()} !! Should only get here if process was interrupted. readstream(sock) on {local_ip}:{local_port} to  {remote_ip}:{remote_port} has returned without doing the sys.exit()", flush=True)
