"""
Simple CLI utility which creates a GPX track file from a binary NMEA dump. 
Dump must contain NMEA GGA messages and an initial RMG messsage to get the date.

NOTE: input file has to be CRLF line terminated as that is the NMEA standard.

EDITED by Philip Sargent to read date from GPRMC not just assume it is 'today'.
renamed as nmeagpx.py
but also see all these : https://duckduckgo.com/?q=nmea2gpx&atb=v316-1&ia=web


https://github.com/semuconsulting/pynmeagps
    Usage originally:
    python3 gpxtracker.py infile="pygpsdata.log" outdir="."

    There are a number of free online GPX viewers
    e.g. https://gpx-viewer.com/view
    Could have used minidom for XML but didn't seem worth it.
    Created on 7 Mar 2021
    @author: semuadmin
"""

# pylint: disable=consider-using-with

import os, sys
#import math
from datetime import datetime, date, timezone, timedelta, time
from pathlib import Path
from sys import argv
from time import strftime

import pynmeagps.exceptions as nme
from pynmeagps.nmeareader import NMEAReader
from pynmeagps.nmeahelpers import planar, haversine

M_PER_NM = 1852 # 1929 First International Extraordinary Hydrographic Conference in Monaco 

JIGGLE = 3.4/5 # anything within this is considered the "same" point. This is the fifth-width of the boat
STACK_MINUTES = 90 # how long we wait before flushing the stack
MAXSTACK = 200 # maxium bumber of points to amalgamate even if they are very close
MIDNIGHT = time(0, 0, 0, 0) # midnight
NEAR_MIDNIGHT = time(0, 23, 59, 0) # one minute to midnight
NEAR_DAYLENGTH = timedelta(hours=23) # nearly a whole day
ONE_MINUTE = timedelta(minutes=1) 
EIGHT_MINUTES = timedelta(minutes=8) 
GLITCHES = []
GAPS = []
msg_stash = []

XML_HDR = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'

GPX_NS = " ".join(
    (
        'xmlns="http://www.topografix.com/GPX/1/1"',
        'creator="nmeagpx+pynmeagps" version="1.1"',
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        'xsi:schemaLocation="http://www.topografix.com/GPX/1/1',
        'http://www.topografix.com/GPX/1/1/gpx.xsd"',
    )
)
GITHUB_LINK = "https://github.com/semuconsulting/pynmeagps"

stack_max = 0

def tidy(dat):
    # A datetime object wehere we don't care about the TZ as it is always UTC
    return str(dat).replace('+00:00','')

def is_in_time_period(startTime, endTime, check_time):
    if startTime < endTime:
        return startTime <= check_time <= endTime
    else: #Over midnight
        return check_time >= startTime or check_time <= endTime

def time_diff(t1, t2):
        # cant' different two time objtecs, only datetime objects
        dateTime1 = datetime.combine(date.today(), t1)
        dateTime2 = datetime.combine(date.today(), t2)
        return dateTime1 - dateTime2
        
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

def stash_msg(n,msg):
    # don't process this msg, discard it. But keep a copy here for debugging
    msg_stash.append((n,msg))
    # print(f"-- STASH {n} {msg.msgID}  {msg.time}")
    
class Stack:
    """
    A simple stack implementation with a maximum size.
    We are using it to store NMEA sentences
    
    We want to empty the stack if the next reading is 
    - out of range of the bounding box
    - a long time after the box started, we want at least one reading an hour.
    
    We also have to manage the hdop value, ele, time and fix
    """
    def __init__(self, max_size):
        self.max_size = max_size
        self._items = []
        self._box = BoundingBox()
        self._first = None
        self.full_count = 0
        
    def first(self):
        return self._items[0]

    def last(self):
        return self._items[-1]
        
    def first_date(self):
        msg, dat = self.first()
        return dat

    def is_empty(self):
        return len(self._items) == 0

    def is_full(self):
        full = len(self._items) == self.max_size
        if full:
            self.full_count += 1
            duration = self.duration() 
            print(f"++ Stack full #{self.full_count}  box: {self.diameter():.1f} m  {duration} h:m:s from {self.first_date().strftime('%T %Z')}")        
        return full

    def pop(self):
        m, d = self._items[-1]
        return self._items.pop()

    def push(self, msg_item):
        msg, dat = msg_item
        if self.is_full():
            print("Stack Overflow! Cannot add item.", flush=True)
        else:
            if not self._first:
               self._first = dat
            self._box.update(msg.lat, msg.lon)
            self._items.append(msg_item)

    def it_fits(self, msg_item):
        """There are many changes which mean that we should use the stack, write out the median, 
        and flush"""
        msg, dat = msg_item

        if self.is_full():
            last_item, last_dat = self._items[-1]
            # print(f"STACK FULL Spread in stack:{last_dat - self._first}") # have seen 901
            return False
        if self.is_empty():
            self.push(msg_item)
            return True
            
        first_msg, _ = self._items[0]
        if msg.quality != first_msg.quality:
            print("QUALITY FIX change") # never happens!
            return False
            
        since = dat - self._first
        last_item, last_dat = self._items[-1]

        if dat < last_dat:
            # actually this is the clock running into the next day in TIME, but not changing the DATE, 
            # because there hasn't been a midnight rollover to fix that
            print(f"TIME TRAVEL: '{tidy(dat)}' < '{tidy(last_dat)}'\nGap:{dat - last_dat} h:m:s  Duration in [{len(self._items)}] stack:{last_dat - self._first} h:m:s")
            print(f"{last_item}, {last_dat}")
           
        if since > timedelta(minutes=STACK_MINUTES):
            # print(f"Gap detected:{dat - last_dat} h:m:s from {tidy(last_dat)} to {tidy(dat)}  Duration in [{len(self._items)}] stack:{last_dat - self._first} h:m:s ")
            GAPS.append((f"from {tidy(last_dat)} to {tidy(dat)}  gap: {dat - last_dat} (duration in [{len(self._items)}] stack {last_dat - self._first})"))
            return False
        
        # distance from centroid
        centroid_lat, centroid_lon  = self._box.centroid()
        distance = planar(centroid_lat, centroid_lon, msg.lat, msg.lon) # in metres
        if distance > 50:
            distance = haversine(centroid_lat, centroid_lon, msg.lat, msg.lon, radius = 6378137.0) # in metres
        if distance > JIGGLE:
            # print(f"JIGGLED {distance:.2f} m")
            return False # i.e. too far away to be averaged in, so restart the stack
        
        self.push(msg_item)
        return True

    def flush(self):
        global stack_max
        if len(self._items) > stack_max:
            stack_max =len(self._items)
        self._items = []
        self._first = None
        # self.full_count = 0
        self._box = BoundingBox()
        
    def centroid(self):
        return self._box.centroid()

    def diameter(self):
        return self._box.diameter()

    def duration(self):
        # The length of time as a timedelta object between the first and last items in the stack
        msg_first, dat_first = self.first()
        msg_last, dat_last = self.last()
        return dat_last - dat_first
        
    def median(self):
        """Weighting lat & lon by hdop is tricky
         We could use sum of squares average of hdop, but actually just picking the worst one is realistic"""
        num = len(self._items)
        # print("NUMBER", num)
        lat = 0
        lon = 0
        alt = 0
        hdop = 0
        for msg_item in self._items:
            i, dat = msg_item
            alt += i.alt 
            # should weight these averages by hdop I guess
            lat += i.lat
            lon += i.lon
            if i.HDOP > hdop:
                hdop = i.HDOP
        first, _ = self._items[0]
        quality = first.quality # use first one, they are all the same anyway
        lat = float(f"{lat/num:.6f}")
        lon = float(f"{lon/num:.6f}")
        alt = float(f"{alt/num:.1f}")  # we have no basis for weighting altitudes, but they are garbage anyway
        return lat, lon, alt, dat, quality, hdop

class BoundingBox:
    def __init__(self):
        """ Constructor.  """
        self._minlat = 90
        self._maxlat = -90
        self._minlon = 180
        self._maxlon = 0

    def update(self, lat, lon):
        if lat > self._maxlat:
            self._maxlat = lat
        if lat < self._minlat:
            self._minlat = lat

        if lon > self._maxlon:
            self._maxlon = lon
        if lon < self._minlon:
            self._minlon = lon
    
    def report(self):
        return self._minlat, self._maxlat, self._minlon, self._maxlon
        
    def size(self):
        return self._maxlat - self._minlat, self._maxlon - self._minlon

    def centroid(self):
        return (self._maxlat + self._minlat)/2, (self._maxlon + self._minlon)/2
        
    def diagonal_R(self):
        return haversine(self._minlat, self._minlon, self._maxlat, self._maxlon, radius = 6378137.0)
    def diagonal_L(self):
        return haversine(self._minlat, self._maxlon, self._maxlat, self._minlon, radius = 6378137.0)
        
    def diameter(self):
        return (self.diagonal_R() + self.diagonal_L())/2

class NMEATracker:
    """
    NMEATracker class.
    """

    def __init__(self, infile, outdir):
        """
        Constructor.
        """

        self._filename = infile
        self._outdir = outdir
        self._infile = None
        self._trkfname = None
        self._trkfile = None
        self._nmeareader = None
        self._connected = False
        self._thisday = None
        self._gpsstack = Stack(MAXSTACK)

    def open(self):
        """
         Open datalog file."""
        if not self._filename.is_file():
            print("NOT A FILE")
        else:
            #print(f"opening {self._filename}")
            pass
        try:
            self._infile = open(self._filename, "rb")
            self._connected = True
        except:
            raise 

    def close(self):
        """
        Close datalog file.
        """
        if self._connected and self._infile:
            self._infile.close()

    def reader(self, validate=False):
        """
        Reads and parses NMEA message data from stream
        
        We have a particular problem dealing with this common glitch
        where the GGA time is out of synch with the RMC time
        
        $GPRMC,000001.00,A,3705.24783,N,02509.11117,E,0.168,,021024,,,A*79
        $GPGGA,235958.00,3705.24796,N,02509.11108,E,1,11,0.77,15.7,M,32.0,M,,*66
        $GPGGA,000005.00,3705.24776,N,02509.11127,E,1,11,0.77,16.5,M,32.0,M,,*61
        """
        bb = BoundingBox()

        i = 0
        n = 0
        tp = 0
        self._nmeareader = NMEAReader(self._infile, validate=validate)

        self.write_gpx_hdr()
        #print(self._nmeareader, self._infile)
        prev_time = MIDNIGHT
        first_GGA = True
        for _, msg in self._nmeareader:  # invokes iterator method
            n += 1
            try:
                d = msg.__dict__
                if 'date' in d and d['date'] != "": # only RMC, but get it anywhere if it exists
                   first_GGA = True # first GGA after any RMC
                   # prev_time = msg.time # don't update, we do not use the time of the RMC msg
                   if not self._thisday: # first line of file usually
                        self._thisday = d['date']
                        timestamp_updated = msg.time
                        # print(f"++ First date seen '{d['date']}'  ({msg.msgID} line:{n:4} in {Path(self._infile.name).stem}")
                   else: # later RMCs in the same day, caused by router re-start and concatenated files
                        if self._thisday == d['date']:
                            # ignore, same day
                            # print(f"++ Same  date seen '{d['date']}'  ({msg.msgID} line:{n:4} in {Path(self._infile.name).stem}")
                            timestamp_updated = msg.time
                        else:
                            # Use RMC to change to next day? but this is also done by the midnight rollover on GGA, so don't do this
                            # as the rollover will immediately increment *again* on the next line
                            prev = self._thisday  
                            print(f"++ Different date  '{d['date']}' {msg.time} (was {prev}) {msg.msgID} line:{n:4} in {Path(self._infile.name).stem}")
                            if d['date'] < prev:
                                print(f"## Bad midnight rollover, RMC says we are still on previous day.")
                       
                    
                
                if msg.msgID == "GGA":
                    #tim = msg.time
                    if not self._thisday:
                        # skip nmea lines until we get the date
                        print(f"{Path(self._infile.name).stem} line:{n:6}:\n.. Skipping, no date.. {msg.time}. This should NOT happen.")
                        stash_msg(n,msg)
                        continue # ignore this msg and go on to next
                    if first_GGA:
                        # skip the first one as the timestamp is usually out of synch
                        first_GGA = False
                        if msg.time < prev_time:
                            print(f".. BACKWD  Skip first GGA {msg.time} after RMC: {prev_time} {time_diff(prev_time, msg.time)} line:{n:4} {Path(self._infile.name).stem}")
                            stash_msg(n,msg)
                            continue # ignore this msg and go on to next
                            
                        # print(f".. Skip first GGA {msg.time} after RMC: {prev_time} {time_diff(msg.time, prev_time)} {NEAR_DAYLENGTH} line:{n:4} {Path(self._infile.name).stem}")
                        if time_diff(msg.time, prev_time) > NEAR_DAYLENGTH:
                            print(f".. FOREWD Skip first GGA {msg.time} after RMC: {prev_time} {time_diff(msg.time, prev_time)} line:{n:4} {Path(self._infile.name).stem}")
                            stash_msg(n,msg)
                            continue # ignore this msg and go on to next
                        
                    if msg.time < prev_time:
                        if time_diff(prev_time, msg.time) < ONE_MINUTE:
                            print(f" Backwards, but only by less than a minute, IGNORING {Path(self._infile.name).stem} line:{n:3}")
                            stash_msg(n,msg)
                            continue
                        if time_diff(prev_time, msg.time) < EIGHT_MINUTES:
                            print(f" Backwards, but by less than 8 minutes,     IGNORING {Path(self._infile.name).stem} line:{n:3}")
                            stash_msg(n,msg)
                            continue
                        print(f"{Path(self._infile.name).stem} line:{n:6}:\n Time REVERSAL  from {prev_time} to {msg.time}\n (last RMC {timestamp_updated}) day: {self._thisday} ")
                           
                        # either bad data or midnight rollover
                        # unfortunately we do see RMC datetime not quite the same as GGA, e.g.000001.00 on the line *before* 235956
                        #   $GPRMC,000001.00,A,3706.41595,N,02652.43965,E,0.287,,060624,,,A*7A
                        #   $GPGGA,235956.00,3706.41566,N,02652.43976,E,1,10,0.94,6.6,M,32.1,M,,*50
                        # so the new date is set, but then immediately it appears that a midnight has occured.
                        # solution: Detect if the time of the GGA is within 5 seconds of midnight, if so, ignore it.
                        self._thisday += timedelta(days=1)
                        d['date'] = self._thisday
                        print(f"{Path(self._infile.name).stem} line:{n:6}:\n Midnight rollover  from {prev_time} to {msg.time}  (last RMC {timestamp_updated}) now: {self._thisday}")
                        if False:
                            # GLITCH handling not needed now that we refuse to store the first GGA msg after a RMC if it is suspect
                            if is_in_time_period(prev_time, msg.time, timestamp_updated):
                                if is_in_time_period(NEAR_MIDNIGHT, msg.time, MIDNIGHT):
                                    # print(f"{Path(self._infile.name).stem} line:{n:6}:\n GLITCH near midnight {prev_time} to {msg.time}  (last done {timestamp_updated}) now: {self._thisday}")
                                    GLITCHES.append((f"{Path(self._infile.name).stem} line:{n:4}", f"{prev_time}"))
                                    self._gpsstack.pop() # delete the previous message in the stack as it is out of order
                                    # Now re-set the 'prev' values to the previous item in the stack, ignoring the glitchy one
                                    prev_time = MIDNIGHT
                                else:
                                    print(f"{Path(self._infile.name).stem} line:{n:4}:\n Midnight NOT rolledover {prev_time} to {msg.time}  (last done {timestamp_updated}) now: {self._thisday} ")
                    dat = datetime.combine(self._thisday, msg.time, timezone.utc) # BUG! midnight rollover does not change day
                    prev_time = msg.time
 
                    lat = strim(msg.lat)
                    lon = strim(msg.lon)
                    bb.update(lat, lon) # for the whole file, not just the stack

                    # don't write immediately, push to stack and write simplified
                    msg_item = (msg, dat)
                    if not self._gpsstack.it_fits(msg_item):
                        # extract the whole stack, as averaged onto the median point,
                        # push the point onto a clean stack,
                        # then write out the median as a GPX point.
                        lat, lon, alt, dat, quality, hdop = self._gpsstack.median()
                        self._gpsstack.flush()
                        self._gpsstack.push(msg_item)
                      
                        datstr = dat.isoformat(sep="T",timespec='auto')
                        datstr = dat.strftime('%Y-%m-%dT%H:%M:%S') # no TZ as it must always be UTC
                        if quality == 1:
                            fix = "3d"
                        elif msg.quality == 2:
                            fix = "2d"
                        else:
                            fix = "none"
                         
                        self.write_gpx_trkpnt(
                            lat,
                            lon,
                            ele=alt,
                            time=datstr,
                            fix=fix,
                            hdop=hdop,
                        )
                        tp += 1
                    i += 1
            except (nme.NMEAMessageError, nme.NMEATypeError, nme.NMEAParseError) as err:
                print(f"Something went wrong {err}")
                continue # get next msg

        self.write_gpx_tlr()

        print(f"{i:6d} GGA message{'' if i == 1 else 's'} -> {tp} trackpoints  {self._filename.name} -> {self._trkfname.name} box: {bb.diameter():.1f} m ~{bb.diameter()/M_PER_NM:6.2f} NM")
        return bb

    def write_gpx_hdr(self):
        """
        Open gpx file and write GPX track header tags
        """
        timestamp = strftime("%Y-%m-%d_%H%M%S")
        self._trkfname = Path(self._outdir) / (Path(self._filename).stem + ".gpx")
        # print(f"Writing to '{self._trkfname}'")
        self._trkfile = open(self._trkfname, "w", encoding="utf-8")

        date = datetime.now().isoformat() + "EEST" # this is INCORRECT ! We should use UTC timezone. FIX THIS to'Z'
        gpxtrack = (
            XML_HDR + "<gpx " + GPX_NS + ">"
            f"<metadata>"
            f'<link href="{GITHUB_LINK}"><text>pynmeagps</text></link><time>{date}</time>'
            "</metadata>\n"
            f"<trk><name>GPX track from NMEA log {self._filename}</name>\n <trkseg><name>{self._filename}-SEG1</name>\n"
        )

        self._trkfile.write(gpxtrack)

    def write_gpx_trkpnt(self, lat: float, lon: float, **kwargs):
        """
        Write GPX track point from NAV-PVT message content
        """

        trkpnt = f'  <trkpt lat="{lat}" lon="{lon}">'

        # these are the permissible elements in the GPX schema for wptType
        # http://www.topografix.com/GPX/1/1/#type_wptType
        for tag in (
            "ele",
            "time",
            "magvar",
            "geoidheight",
            "name",
            "cmt",
            "desc",
            "src",
            "link",
            "sym",
            "type",
            "fix",
            "sat",
            "hdop",
            "vdop",
            "pdop",
            "ageofdgpsdata",
            "dgpsid",
            "extensions",
        ):
            if tag in kwargs:
                val = kwargs[tag]
                trkpnt += f"<{tag}>{val}</{tag}>"

        trkpnt += "</trkpt>\n"

        self._trkfile.write(trkpnt)

    def write_gpx_tlr(self):
        """
        Write GPX track trailer tags and close file
        """

        gpxtrack = " </trkseg>\n</trk>\n</gpx>"
        self._trkfile.write(gpxtrack)
        self._trkfile.close()


def main(indir, midsuffix, insuffix):
    """
    Main routine.
    """
    global stack_max
    global msg_stash

    indir = Path(indir)
    if not indir.is_dir():
        print(f"Directory does not exist: '{INDIR}")
        sys.exit(1)    

    outdir = indir
    print(f"NMEA datalog to GPX file converter ('{insuffix}' files in {indir})")
    
    filepaths = sorted(indir.iterdir(), key=lambda p: p.name.lower())
    
    # Create the list of files to be processed in the order we want
    trips = []
    infiles = []
    for filepath in filepaths:
        if filepath.suffix == insuffix:
            if Path(filepath.stem).suffix == midsuffix:
                infiles.append(filepath)
    print(f"{len(infiles)} {midsuffix}{insuffix} files to convert to GPX")
    
    # Process the files and do calculations
    for i in infiles:
        #print(f" in", i.name)
        msg_stash = []
        inpath = indir / i
        tkr = NMEATracker(inpath, outdir)
        tkr.open()
        bound_box = tkr.reader()
        tkr.close()
        
        if bound_box.diameter() > 0.1 * M_PER_NM : # 0.1 NM in metres
            trips.append((i.name, bound_box.diameter(),bound_box.diagonal_R(),bound_box.diagonal_L(),len(msg_stash)))
            
        if msg_stash:
            print(f"{len(msg_stash)} discarded NMEA sentences")
            for n, m in msg_stash:
                # print(n, m)    
                pass
        print("")

    if GLITCHES:
        print(f"{len(GLITCHES)} glitches:")
        for g in GLITCHES:
            fn, gtext = g
            print(f"{fn} {gtext}")
    if GAPS:
        print(f"{len(GAPS)} gaps:")
        for g in GAPS:
            print(g)
            

            
    # Print summary data in 'trips' for each file (i.e. each day) 
    for t in trips:
        name, diam, diag_R, diag_L, n_stash = t
        print(f"{name} box: ~{diam/M_PER_NM:5.1f} NM {n_stash} discards") 
    print(f"Finished all files, max stack used: {stack_max}")
    



if __name__ == "__main__":

    INDIR = "/home/philip/gps/nmea_data/2024-06/"
    MIDSUFFIX = ".day" # i.e. ".day.nmea"
    INSUFFIX = ".nmea"
    
    if len(sys.argv) == 4:
        INDIR = sys.argv[1]
        MIDSUFFIX = sys.argv[2]
        INSUFFIX = sys.argv[3]


    if len(sys.argv) >4:
        print(f"Either with no parameters or with nmea directory & suffix & midsuffix e.g.\n$ python nmeagpx.py /home/philip/gps/nmea_data/2024-05/ '.day' '.nmea'", flush=True)

    main(INDIR, MIDSUFFIX, INSUFFIX)
