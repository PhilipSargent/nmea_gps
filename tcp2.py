import socket
import time

# TCP server settings
TCP_IP = '192.168.8.60'  # The IP where the TCP server is running
TCP_PORT = 2000        # The port where the TCP server is listening

# Sample NMEA sentence
sample_nmea_sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n"

# Create a TCP socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((TCP_IP, TCP_PORT))


try:
    while True:
        msg = s.recv(1024)
        print(msg.decode("utf-8"), end="") # WOrKS, getting data from QKA026
        continue # skip the rest here..
        
        # Send the sample NMEA sentence
        s.send(sample_nmea_sentence.encode())
        print(f"Sent NMEA sentence: {sample_nmea_sentence.strip()}")
        time.sleep(1)  # Wait for a second before sending the next sentence

finally:
    # Close the socket
    s.close()