"""
Simple CLI utility which creates a GPX track file
from a binary NMEA dump. Dump must contain NMEA GGA messages and an initial RMG messsage to get the date.

NOTE: input file has to be CRLF line terminated as that is the NMEA standard.

EDITED by Philip Sargent to read date from GPRMC not just assume it is today.
renamed as nmeagpx.py
but also see all these : https://duckduckgo.com/?q=nmea2gpx&atb=v316-1&ia=web

Usage:
python nmeagpx.py infile="2024-05-09_0300.nmea" outdir="."

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
from datetime import datetime, date, timezone
from pathlib import Path
from sys import argv
from time import strftime

import pynmeagps.exceptions as nme
from pynmeagps.nmeareader import NMEAReader

XML_HDR = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'

GPX_NS = " ".join(
    (
        'xmlns="http://www.topografix.com/GPX/1/1"',
        'creator="pynmeagps" version="1.1"',
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        'xsi:schemaLocation="http://www.topografix.com/GPX/1/1',
        'http://www.topografix.com/GPX/1/1/gpx.xsd"',
    )
)
GITHUB_LINK = "https://github.com/semuconsulting/pynmeagps"

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
        Reads and parses UBX message data from stream
        using UBXReader iterator method
        """
        i = 0
        n = 0
        self._nmeareader = NMEAReader(self._infile, validate=validate)

        self.write_gpx_hdr()
        #print(self._nmeareader, self._infile)
        for _, msg in self._nmeareader:  # invokes iterator method
            n += 1
            try:
                d = msg.__dict__
                if 'date' in d and d['date'] != "": # only RMC, but get it anywhere if it exists
                    if not self._thisday:
                        self._thisday = d['date']
                        # print(f"++ Set date as '{self._thisday}' {msg.msgID} line:{n:6}")
                    else:
                        if self._thisday == d['date']:
                            pass # ignore, same day
                        else:
                            self._thisday = d['date']
                            print(f"++ New date as '{self._thisday}' {msg.msgID} line:{n:6} in {self._infile.name}")
                        
                    
                
                if msg.msgID == "GGA":
                    tim = msg.time
                    if not self._thisday:
                        # skip nmea lines until we get the date
                        # we could use the filename, if that has been set to have the date.. nah.
                        print(f".. Skipping, no date.. {tim}. This should NOT happen.")
                        continue
                    dat = datetime.combine(self._thisday, msg.time, timezone.utc)
                    datstr = dat.isoformat() + "Z"

                    if msg.quality == 1:
                        fix = "3d"
                    elif msg.quality == 2:
                        fix = "2d"
                    else:
                        fix = "none"
                    self.write_gpx_trkpnt(
                        strim(msg.lat),
                        strim(msg.lon),
                        ele=msg.alt,
                        time=datstr,
                        fix=fix,
                        hdop=msg.HDOP,
                    )
                    i += 1
            except (nme.NMEAMessageError, nme.NMEATypeError, nme.NMEAParseError) as err:
                print(f"Something went wrong {err}")
                continue

        self.write_gpx_tlr()

        print(f"{i:6d} GGA message{'' if i == 1 else 's'} -> trackpoints from {self._filename.name} to {self._trkfname.name}")

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
            f"<trk><name>GPX track from NMEA log {self._filename}</name>\n <trkseg>"
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


def main(indir, insuffix):
    """
    Main routine.
    """
    indir = Path(indir)
    if not indir.is_dir():
        print(f"Directory does not exist: '{INDIR}")
        sys.exit(1)    

    outdir = indir
    print(f"NMEA datalog to GPX file converter ('{insuffix}' files in {indir})")
    
    filepaths = sorted(indir.iterdir(), key=lambda p: p.name.lower())
    
    infiles = []
    for filepath in filepaths:
        if filepath.suffix == insuffix:
            infiles.append(filepath)
    print(f"{len(infiles)} files to convert to GPX")
            
    for i in infiles:
        #print(f" in", i.name)
        inpath = indir / i
        tkr = NMEATracker(inpath, outdir)
        tkr.open()
        tkr.reader()
        tkr.close()
    
    print("Finished all files")


if __name__ == "__main__":

    INDIR = "/home/philip/gps/nmea_data/2024-05/"
    INSUFFIX = ".day"
    
    if len(sys.argv) == 3:
        INDIR = sys.argv[1]
        INSUFFIX = sys.argv[2]


    if len(sys.argv) >3:
        print(f"Either with no parameters or with nmea directory and suffix e.g.\n$ python nmeagpx.py /home/philip/gps/nmea_data/2024-05/ .day", flush=True)

    main(INDIR, INSUFFIX)
