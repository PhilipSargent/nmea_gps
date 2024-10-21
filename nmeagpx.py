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

JIGGLE = 3.4/2 # anything within 3m is considered the "same" point. This is the half-width of the boat
STACK_MINUTES = 90 # how long we wait before flushing the stack
MAXSTACK = 300

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

def is_in_time_period(startTime, endTime, check_time):
    if startTime < endTime:
        return startTime <= check_time <= endTime
    else: #Over midnight
        return check_time >= startTime or check_time <= endTime
        
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

    def is_empty(self):
        return len(self._items) == 0

    def is_full(self):
        return len(self._items) == self.max_size

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
            
        duration = dat - self._first
        last_item, last_dat = self._items[-1]

        if dat < last_dat:
            # actually this is the clock running into the next day in TIME, but not changing the DATE, 
            # because there hasn't been an RMC to do that..
            print(f"TIME TRAVEL: '{dat}' < '{last_dat}'\nGap:{dat - last_dat} h:m:s  Spread in stack:{last_dat - self._first} h:m:s")
           
        if duration > timedelta(minutes=STACK_MINUTES):
            print(f"Gap:{dat - last_dat} h:m:s  Spread in stack:{last_dat - self._first} h:m:s")
            return False
        
        # distance from centroid
        centroid_lat, centroid_lon  = self._box.centroid()
        distance = planar(centroid_lat, centroid_lon, msg.lat, msg.lon)
        if distance > JIGGLE:
            # print(f"JIGGLED {distance:.2f} m")
            return False
        
        self.push(msg_item)
        return True

    def flush(self):
        global stack_max
        if len(self._items) > stack_max:
            stack_max =len(self._items)
        self._items = []
        self._first = None
        self._box = BoundingBox()
        
    def centroid(self):
        return self._box.centroid()
        
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
        return planar(self._minlat, self._minlon, self._maxlat, self._maxlon)
    def diagonal_L(self):
        return planar(self._minlat, self._maxlon, self._maxlat, self._minlon)
        
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
        """
        bb = BoundingBox()

        i = 0
        n = 0
        self._nmeareader = NMEAReader(self._infile, validate=validate)

        self.write_gpx_hdr()
        #print(self._nmeareader, self._infile)
        prev_time = time(0, 0, 0, 0) # midnight
        date_updated = False
        for _, msg in self._nmeareader:  # invokes iterator method
            n += 1
            try:
                d = msg.__dict__
                if 'date' in d and d['date'] != "": # only RMC, but get it anywhere if it exists
                    # if self._infile.name == "/home/philip/gps/nmea_data/2024-06/2024-06-06.day.nmea":
                        # print(f"++ RMC date '{d['date']}'   {msg.msgID} line:{n:6} in {self._infile.name}")
                    if not self._thisday:
                        self._thisday = d['date']
                        date_updated = True
                        timestamp_updated = msg.time
                        # print(f"++ Set date as '{self._thisday}' {msg.msgID} line:{n:6}")
                    else:
                        if self._thisday == d['date']:
                            pass # ignore, same day
                        else:
                            prev = self._thisday
                            self._thisday = d['date']
                            print(f"++ New date as '{self._thisday}'  (was {prev}) {msg.msgID} line:{n:6} in {self._infile.name}")
                            date_updated = True
                        
                    
                
                if msg.msgID == "GGA":
                    tim = msg.time
                    if not self._thisday:
                        # skip nmea lines until we get the date
                        # we could use the filename, if that has been set to have the date.. nah.
                        print(f".. Skipping, no date.. {tim}. This should NOT happen.")
                        continue
                    if msg.time < prev_time:
                        # either bad data or midnight rollover
                        # unfortunately we do see RMC datetime not quite the same as GGA, e.g.000001.00 on the line *before* 235956
                        # GPRMC,000001.00,A,3706.41595,N,02652.43965,E,0.287,,060624,,,A*7A
                        # $GPGGA,235956.00,3706.41566,N,02652.43976,E,1,10,0.94,6.6,M,32.1,M,,*50
                        # so the new date is set, but then immediately it appears that a midnight has occured.
                        # solution: re-order RMC sentences into GGA order.. but how?
                        if not date_updated:
                            if is_in_time_period(prev_time, msg.time, timestamp_updated):
                                print(f"Midnight NOT rolledover {prev_time} to {msg.time}  (last done {timestamp_updated}) now: {self._thisday} line:{n:6} in {self._infile.name}")
                            else:
                                self._thisday += timedelta(days=1)
                                d['date'] = self._thisday
                                print(f"Midnight rollover  from {prev_time} to {msg.time}  (last done {timestamp_updated}) now: {self._thisday} line:{n:6} in {self._infile.name}")
                    dat = datetime.combine(self._thisday, msg.time, timezone.utc) # BUG! midnight rollover does not change day
                    prev_time = msg.time
                    date_updated = False # reset to wait for next RMC update

                       
                    lat = strim(msg.lat)
                    lon = strim(msg.lon)
                    bb.update(lat, lon) # for the whole file, not just the stack

                    # don't write immediately, push to stack and write simplified
                    msg_item = (msg, dat)
                    if not self._gpsstack.it_fits(msg_item):
                        # write out whole stack, simplified
                        # then re-push item onto a new stack.
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
                    i += 1
            except (nme.NMEAMessageError, nme.NMEATypeError, nme.NMEAParseError) as err:
                print(f"Something went wrong {err}")
                continue

        self.write_gpx_tlr()

        print(f"{i:6d} GGA message{'' if i == 1 else 's'} -> trackpoints from {self._filename.name} to {self._trkfname.name} box: {bb.diameter():.1f} m")
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

    indir = Path(indir)
    if not indir.is_dir():
        print(f"Directory does not exist: '{INDIR}")
        sys.exit(1)    

    outdir = indir
    print(f"NMEA datalog to GPX file converter ('{insuffix}' files in {indir})")
    
    filepaths = sorted(indir.iterdir(), key=lambda p: p.name.lower())
    
    trips = []
    infiles = []
    for filepath in filepaths:
        if filepath.suffix == insuffix:
            if Path(filepath.stem).suffix == midsuffix:
                infiles.append(filepath)
    print(f"{len(infiles)} {midsuffix}{insuffix} files to convert to GPX")
            
    for i in infiles:
        #print(f" in", i.name)
        inpath = indir / i
        tkr = NMEATracker(inpath, outdir)
        tkr.open()
        bound_box = tkr.reader()
        tkr.close()
        
        # print(f"Box diameter: {bound_box.diameter():.1f} m", bound_box.report())
        if bound_box.diameter() > 100: # 100 metres
            trips.append((i.name, bound_box.diameter()))
            
        
    for t in trips:
        name, diam = t
        print(f"{name} ~{diam/M_PER_NM:6.2f} NM")
    print(f"Finished all files, max stack used: {stack_max}")


if __name__ == "__main__":

    INDIR = "/home/philip/gps/nmea_data/2024-06/"
    MIDSUFFIX = ".day" # i.e. ".day.nmea"
    INSUFFIX = ".nmea"
    
    if len(sys.argv) == 3:
        INDIR = sys.argv[1]
        MIDSUFFIX = sys.argv[2]
        INSUFFIX = sys.argv[3]


    if len(sys.argv) >4:
        print(f"Either with no parameters or with nmea directory & suffix & midsuffix e.g.\n$ python nmeagpx.py /home/philip/gps/nmea_data/2024-05/ '.day' '.nmea'", flush=True)

    main(INDIR, MIDSUFFIX, INSUFFIX)
