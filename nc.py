import socket
import sys
import threading

# Gemini written

def listen(protocol, port):
    sock_type = socket.SOCK_DGRAM if protocol == 'udp' else socket.SOCK_STREAM
    sock = socket.socket(socket.AF_INET, sock_type)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', port))

    if protocol == 'tcp':
        sock.listen(1)
        print(f"Listening on TCP port {port}...")
        conn, addr = sock.accept()
        print(f"Connected by {addr}")
        handle_stream(conn)
    else:
        print(f"Listening on UDP port {port}...")
        while True:
            data, addr = sock.recvfrom(4096)
            sys.stdout.buffer.write(data)
            sys.stdout.flush()

def connect(protocol, host, port):
    sock_type = socket.SOCK_DGRAM if protocol == 'udp' else socket.SOCK_STREAM
    sock = socket.socket(socket.AF_INET, sock_type)
    
    if protocol == 'tcp':
        sock.connect((host, port))
        handle_stream(sock)
    else:
        print(f"Sending UDP to {host}:{port}. Type and press Enter.")
        while True:
            line = sys.stdin.readline()
            if not line: break
            sock.sendto(line.encode(), (host, port))

def handle_stream(sock):
    # Thread to read from socket and print to stdout
    def receive():
        while True:
            try:
                data = sock.recv(4096)
                if not data: break
                sys.stdout.buffer.write(data)
                sys.stdout.flush()
            except: break

    threading.Thread(target=receive, daemon=True).start()
    
    # Main thread reads from stdin and sends to socket
    while True:
        line = sys.stdin.readline()
        if not line: break
        try:
            sock.sendall(line.encode())
        except: break

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:\n  Listen: python3 nc.py -l [tcp|udp] [port]\n  Client: python3 nc.py [tcp|udp] [host] [port]")
        sys.exit(1)

    if sys.argv[1] == "-l":
        listen(sys.argv[2], int(sys.argv[3]))
    else:
        connect(sys.argv[1], sys.argv[2], int(sys.argv[3]))