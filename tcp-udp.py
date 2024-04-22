"""please write a python program that reads a continuous input of NMEA senetences on a TCP socket and republishes them on a different UDP stream

Certainly! Below is a Python program that sets up a TCP server to read NMEA sentences and then republishes them on a UDP stream. The program uses the socket library for network communication.

Python
AI-generated code. Review and use carefully. More info on FAQ."""

import socket 

hostname = socket.gethostbyname( '127.0.0.1' )

# TCP server settings
TCP_IP = '192.168.8.60'  # Localhost (change to your TCP server IP)
TCP_PORT = 2000        # Change to your TCP server port
BUFFER_SIZE = 1024     # Buffer size for data read

TCP_IP2 = hostname  # Localhost (change to your TCP server IP)
TCP_PORT2 = 1999        # Change to your TCP server port

# UDP client settings
UDP_IP = '192.168.8.255'   # Localhost (change to your UDP client IP)
UDP_PORT = 52000        # Change to your UDP client port

print(f"TCP server listening on {TCP_IP}:{TCP_PORT}")
print(f"UDP stream will be sent to {UDP_IP}:{UDP_PORT}")

# Create a TCP socket
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_socket.connect((TCP_IP, TCP_PORT))
#tcp_socket.bind((TCP_IP, TCP_PORT))
#tcp_socket.listen(1)


# Create a UDP socket
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"{hostname=}")


try:
    # Accept a connection from the TCP client
    #conn, addr = tcp_socket.accept()
    #print(f"Connection address: {addr}")

    while True:
        # Read NMEA sentence from TCP client
        data = tcp_socket.recv(BUFFER_SIZE)
        #data = conn.recv(BUFFER_SIZE)
        if not data:
            break # continue?

        # Republish the NMEA sentence on UDP stream
        udp_socket.sendto(data, (UDP_IP, UDP_PORT))
        print(data) # working.. but OPenCPN can't read it..

 

finally:
    # Close the sockets
    tcp_socket.close()
    udp_socket.close()
    
exit()
#################

"""Listen for UDP Stream:
Use a UDP client tool or write a Python script to listen to the UDP port where the sentences are being republished. Here’s an example Python script that acts as a UDP client listening for NMEA sentences:
Python
AI-generated code. Review and use carefully. More info on FAQ."""

import socket

# UDP client settings
UDP_IP = '127.0.0.1'   # The IP where the UDP server is running
UDP_PORT = 52000        # The port where the UDP server is listening
BUFFER_SIZE = 1024     # Buffer size for data read

# Create a UDP socket
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.bind((UDP_IP, UDP_PORT))

print(f"Listening for NMEA sentences on UDP {UDP_IP}:{UDP_PORT}")

try:
    while True:
        # Receive NMEA sentence
        data, addr = udp_socket.recvfrom(BUFFER_SIZE)
        print(f"Received NMEA sentence: {data.decode().strip()} from {addr}")

finally:
    # Close the socket
    udp_socket.close()
    """
Make sure to run the TCP client and UDP listener scripts on the same machine where the TCP to UDP relay program is running, or adjust the IP addresses accordingly if they are on different machines. This setup will allow you to simulate the sending of NMEA sentences over TCP and verify that they are correctly being republished over UDP. """