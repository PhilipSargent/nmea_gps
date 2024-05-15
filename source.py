"""Written by Bard initially
2024-02-01

I got the example NMEA data from making a circular route on https://nmeagen.org/
so it is a rather speedy circumnavigation of Poros, so that it works for testing
Navionics where the location  must be within the scope of a purchased chart.
"""

import socket
import signal
import time
import errno

RECONNECT_DELAY = 5 # seconds
LINE_DELAY = 0.333

nmea_data = """$GPGGA,213340.649,3729.856,N,02327.091,E,1,12,1.0,0.0,M,0.0,M,,*6A
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213340.649,A,3729.856,N,02327.091,E,783.8,089.7,010224,000.0,W*79
$GPGGA,213341.649,3729.858,N,02327.365,E,1,12,1.0,0.0,M,0.0,M,,*6D
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213341.649,A,3729.858,N,02327.365,E,311.9,103.8,010224,000.0,W*7C
$GPGGA,213342.649,3729.832,N,02327.470,E,1,12,1.0,0.0,M,0.0,M,,*61
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213342.649,A,3729.832,N,02327.470,E,403.5,130.3,010224,000.0,W*73
$GPGGA,213343.649,3729.751,N,02327.566,E,1,12,1.0,0.0,M,0.0,M,,*6C
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213343.649,A,3729.751,N,02327.566,E,317.2,155.4,010224,000.0,W*7F
$GPGGA,213344.649,3729.668,N,02327.604,E,1,12,1.0,0.0,M,0.0,M,,*67
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213344.649,A,3729.668,N,02327.604,E,431.9,134.7,010224,000.0,W*78
$GPGGA,213345.649,3729.574,N,02327.699,E,1,12,1.0,0.0,M,0.0,M,,*6C
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213345.649,A,3729.574,N,02327.699,E,2340.8,090.9,010224,000.0,W*40
$GPGGA,213346.649,3729.562,N,02328.518,E,1,12,1.0,0.0,M,0.0,M,,*6D
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213346.649,A,3729.562,N,02328.518,E,4434.1,070.4,010224,000.0,W*49
$GPGGA,213347.649,3730.065,N,02329.934,E,1,12,1.0,0.0,M,0.0,M,,*65
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213347.649,A,3730.065,N,02329.934,E,4667.9,072.2,010224,000.0,W*49
$GPGGA,213348.649,3730.551,N,02331.448,E,1,12,1.0,0.0,M,0.0,M,,*67
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213348.649,A,3730.551,N,02331.448,E,3648.3,012.8,010224,000.0,W*47
$GPGGA,213349.649,3731.548,N,02331.674,E,1,12,1.0,0.0,M,0.0,M,,*62
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213349.649,A,3731.548,N,02331.674,E,10887.5,312.6,010224,000.0,W*76
$GPGGA,213350.649,3733.834,N,02329.182,E,1,12,1.0,0.0,M,0.0,M,,*69
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213350.649,A,3733.834,N,02329.182,E,5367.5,247.6,010224,000.0,W*4D
$GPGGA,213351.649,3733.148,N,02327.513,E,1,12,1.0,0.0,M,0.0,M,,*68
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213351.649,A,3733.148,N,02327.513,E,8123.4,237.7,010224,000.0,W*44
$GPGGA,213352.649,3731.744,N,02325.289,E,1,12,1.0,0.0,M,0.0,M,,*65
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213352.649,A,3731.744,N,02325.289,E,2458.5,193.8,010224,000.0,W*49
$GPGGA,213353.649,3731.074,N,02325.124,E,1,12,1.0,0.0,M,0.0,M,,*64
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213353.649,A,3731.074,N,02325.124,E,2791.5,126.0,010224,000.0,W*48
$GPGGA,213354.649,3730.551,N,02325.845,E,1,12,1.0,0.0,M,0.0,M,,*6E
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213354.649,A,3730.551,N,02325.845,E,1703.3,104.6,010224,000.0,W*4A
$GPGGA,213355.649,3730.404,N,02326.411,E,1,12,1.0,0.0,M,0.0,M,,*60
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213355.649,A,3730.404,N,02326.411,E,1225.3,125.0,010224,000.0,W*40
$GPGGA,213356.649,3730.179,N,02326.733,E,1,12,1.0,0.0,M,0.0,M,,*6F
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213356.649,A,3730.179,N,02326.733,E,845.3,132.7,010224,000.0,W*73
$GPGGA,213357.649,3730.001,N,02326.926,E,1,12,1.0,0.0,M,0.0,M,,*6A
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213357.649,A,3730.001,N,02326.926,E,453.0,130.4,010224,000.0,W*7F
$GPGGA,213358.649,3729.909,N,02327.034,E,1,12,1.0,0.0,M,0.0,M,,*67
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,213358.649,A,3729.909,N,02327.034,E,453.0,130.4,010224,000.0,W*72

"""
def endless_lines_generator(long_string):
    """
    This generator continuously produces lines from the given string,
    returning to the beginning when all lines are yielded.

    Args:
    long_string: The long string containing lines.

    Yields:
    Lines from the long string, one at a time.
    """
    while True:
        for line in long_string.splitlines():
            yield line
 

def main2():

    hostname = socket.gethostname()
    host = '' 
    PORT = 65432
    CONTROL_CODES = [b'\x03', b'\x04', b'\x06', b'\x1b']  # ^C, ^D, ^F, ESC
    # telnet always sends ^F \x06 when user types ^Z or ^C
     
    def handle_client(conn):
        try:
            while True:
                time.sleep(LINE_DELAY)
                # Send data to the client, a line every 0.3s or so
                line = next(nmea_generator)
                print(line)
                line = line + "\r\n"
                byt = line.encode()
                conn.sendall(byt)

                # Check for control sequences from the client. This is non-blocking, so an exception will happen every time.
                try:
                    data = conn.recv(1)
                except socket.error as e:
                    err = e.args[0]
                    if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                        #time.sleep(1)
                        #print('No data available')
                        continue
                    else:
                        # a "real" error occurred
                        print(e)
                        sys.exit(1)
                if data in CONTROL_CODES:
                    print(f"Client indicated a wish to quit with '{data}'")
                    conn.sendall("The server respects the wish of the client to detach.\r\n".encode())
                    return
                else:
                    print(f"Mystery data '{data}'")
        except ConnectionError:
            # Client disconnected gracefully
            print("Connection error")

    def signal_handler(sig, frame):
        """Clean exit when pressing ^C at the terminal when running this code manually,
         but ^Z still leaves all the sockets hanging"""
        print("\nReceived shutdown signal, exiting...")
        server.shutdown(socket.SHUT_RDWR)
        server.close()
        quit()

    # Register signal handler for graceful shutdown of server
    # from ctrl-C on the server process
    signal.signal(signal.SIGINT, signal_handler)

    # Create a server socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind the socket to the address and port
    server.bind((host, PORT))

    # Listen for incoming connections
    server.listen(5) # 5 allowable unaccepted connectins waiting
    print(f"Server listening on {host}:{PORT}")

    while True:
        try:
            # Accept a new connection
            #print(f"Attempting connection to interested client")
            conn, addr = server.accept()
            print(f"Connected by {addr}")
            conn.setblocking(False)

            handle_client(conn) # will only return if error or client closes down

            break
            
        except BlockingIOError:
            # No connection available, continue waiting
            print("..waiting")
 
        time.sleep(RECONNECT_DELAY)

    server.shutdown(socket.SHUT_RDWR)
    server.close()

if __name__ == "__main__":
    nmea_generator = endless_lines_generator(nmea_data)
    main2()