from socket import socket, gethostbyname, AF_INET, SOCK_DGRAM
import sys
PORT_NUMBER = 1999
SIZE = 1024

hostName = gethostbyname( '0.0.0.0' )

mySocket = socket( AF_INET, SOCK_DGRAM )
mySocket.bind( (hostName, PORT_NUMBER) )

print (f"Test server listening on port {PORT_NUMBER}\n")

while True:
    (data,addr) = mySocket.recvfrom(SIZE)
    print(data)
sys.exit()