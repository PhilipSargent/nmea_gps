# server.py

import socket

# Ask OS for the socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
port = 2000
# Bind the socket to an address and port
print(f"Listening on port {port}")
s.bind(("0.0.0.0", port))


# Listen for incoming connections
s.listen(5)

while True:
    # Accept a connection
    conn, addr = s.accept()
    print("Connected by", addr)

    try:
        # Inner loop: keep reading data from this specific client
        while True:
            raw_data = conn.recv(1024) 
            # Convert binary to text
            text_data = raw_data.decode('utf-8').strip()
            if not raw_data:
                print(f"Client {addr} disconnected.")
                break # Exit inner loop if no data (client closed connection)

            print(f"Received from {addr}:", text_data)
            
            # Optional: Send a response back
            conn.sendall("OK\n".encode('utf-8'))
    except ConnectionResetError:
        print("Connection was reset by the client.")
    finally:
        # Close this specific connection before waiting for a new one
        conn.close()