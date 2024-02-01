"""Written by Bard initially
2024-02-01
"""

import socket
import time
# Replace with your actual TCP server details

PORT = 2000


RECONNECT_DELAY = 15 # seconds
LINE_DELAY = 0.333

nmea_data = """$GPGGA,202610.461,5231.594,N,01322.139,E,1,12,1.0,0.0,M,0.0,M,,*6E
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,202610.461,A,5231.594,N,01322.139,E,8629.7,078.9,010224,000.0,W*4B
$GPGGA,202611.461,5232.327,N,01325.888,E,1,12,1.0,0.0,M,0.0,M,,*66
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,202611.461,A,5232.327,N,01325.888,E,6691.3,117.7,010224,000.0,W*4C
$GPGGA,202612.461,5231.117,N,01328.206,E,1,12,1.0,0.0,M,0.0,M,,*66
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,202612.461,A,5231.117,N,01328.206,E,3092.5,222.0,010224,000.0,W*48
$GPGGA,202613.461,5230.365,N,01327.526,E,1,12,1.0,0.0,M,0.0,M,,*6B
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,202613.461,A,5230.365,N,01327.526,E,4808.4,232.3,010224,000.0,W*4A
$GPGGA,202614.461,5229.318,N,01326.166,E,1,12,1.0,0.0,M,0.0,M,,*6F
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,202614.461,A,5229.318,N,01326.166,E,8205.3,284.1,010224,000.0,W*4D
$GPGGA,202615.461,5230.183,N,01322.706,E,1,12,1.0,0.0,M,0.0,M,,*62
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,202615.461,A,5230.183,N,01322.706,E,3670.5,080.7,010224,000.0,W*4B
$GPGGA,202616.461,5230.447,N,01324.323,E,1,12,1.0,0.0,M,0.0,M,,*69
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,202616.461,A,5230.447,N,01324.323,E,2476.2,323.6,010224,000.0,W*49
$GPGGA,202617.461,5231.074,N,01323.859,E,1,12,1.0,0.0,M,0.0,M,,*6C
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,202617.461,A,5231.074,N,01323.859,E,3375.0,272.8,010224,000.0,W*40
$GPGGA,202618.461,5231.149,N,01322.325,E,1,12,1.0,0.0,M,0.0,M,,*6D
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,202618.461,A,5231.149,N,01322.325,E,1271.1,329.6,010224,000.0,W*46
$GPGGA,202619.461,5231.481,N,01322.129,E,1,12,1.0,0.0,M,0.0,M,,*63
$GPGSA,A,3,01,02,03,04,05,06,07,08,09,10,11,12,1.0,1.0,1.0*30
$GPRMC,202619.461,A,5231.481,N,01322.129,E,1271.1,329.6,010224,000.0,W*48
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
 

def main():
    # Create the endless generator
    nmea_generator = endless_lines_generator(nmea_data)
    
    hostname = socket.gethostname()
    host = '' 
    s = socket.socket()  # Create a socket object
    s.bind(('localhost', PORT))  # Bind to the port
    s.listen(5)  # Now wait for client connection.
    print('Server listening....')   
    conn, address = s.accept()  # Establish connection with client.                    
    print('Got connection from', address)
    
    # while True:
        # try:
            # data = conn.recv(1024)
            # print('Server received', data.decode())

        # except socket.error as e:
            # print(f"Cannot connect to {hostname} '{e}'")
            # print(f"Retrying in {RECONNECT_DELAY} seconds...")
            # time.sleep(RECONNECT_DELAY)   

         
    while True:
        # Adjust delay as needed
        time.sleep(LINE_DELAY)
        line = next(nmea_generator)
        print(line)
        byt = line.encode()
        conn.send(byt)

    
if __name__ == "__main__":
  main()