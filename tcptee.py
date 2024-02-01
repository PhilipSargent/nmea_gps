"""Written by Bard initially
2024-02-01
"""

import socket
import time

SOURCE = '192.168.8.60'
PORT1 = 2000
PORT2 = 2001
PORT3 = 2002
RECONNECT_DELAY = 15  # Seconds to wait before reconnecting

while True:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((SOURCE, PORT1))
            s.listen()
            conn, addr = s.accept()
            with conn:
                print('Connected by', addr)
                while True:
                    data = conn.recv(1024)
                    if not data:
                        break

                    # Republish data to ports 2001 and 2002
                    for target_port in (PORT2, PORT3):
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as target_socket:
                            target_socket.connect((SOURCE, target_port))
                            target_socket.sendall(data)
                            target_socket.close()

                    print('Received and republished:', data.decode())
    except socket.error as e:
        print(f"Cannot connect to {SOURCE} '{e}'")
        print(f"Retrying in {RECONNECT_DELAY} seconds...")
        time.sleep(RECONNECT_DELAY)
