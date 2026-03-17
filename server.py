import socket
import time
import os
import struct

PORT = 5201
TCP_PORT = 5202

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

sock.bind(('0.0.0.0', PORT))


CHUNK_SIZE = 1400

bPS = 40

TBPS = bPS*1024*1024/8 #target bytes per second


file_path = "100MB.bin"

file_size = os.path.getsize(file_path)


data, addr = sock.recvfrom(1024)

print(f"Client is  : {addr}")


with open(file_path, "rb") as f:

    chunk_id = 0

    bytes_sent = 0

    startTime = time.time()

    while True:

        chunk = f.read(CHUNK_SIZE)

        if not chunk:

            break

        header = chunk_id.to_bytes(4, 'big')

        packet = header+chunk

        sock.sendto(packet, addr)

        bytes_sent += len(packet)

        chunk_id += 1

        expectedTime = bytes_sent/TBPS

        actualTime = time.time() - startTime

        if actualTime < expectedTime:

            time.sleep(expectedTime - actualTime)


print("File sent – sending DONE markers...")
for _ in range(30):
    sock.sendto(b"DONE", addr)
    time.sleep(0.15)          


print(f"Sent {bytes_sent} payload bytes ({chunk_id} chunks)")

# tcp repair sequence: 

tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
tcp_sock.bind(('0.0.0.0', TCP_PORT))
tcp_sock.listen(1)

print("TCP listener ready on port 5202 - waiting for repair...")

try:
    conn, taddr = tcp_sock.accept()
    print(f"TCP repair request from {taddr}")
    conn.settimeout(60)

    req = b""
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            print("Client closed connection before sending full LIST")
            break
        req += chunk
        if len(req) >= 8 and req.startswith(b"LIST"):
            num = struct.unpack(">I", req[4:8])[0]
            expected_size = 8 + num * 4
            if len(req) >= expected_size:
                break 

    print(f"Received complete LIST for {num} missing chunks")

    
    missing_ids = []
    pos = 8
    for _ in range(num):
        if pos + 4 > len(req):
            print("Incomplete LIST data - something went wrong")
            break
        mid = struct.unpack(">I", req[pos:pos+4])[0]
        missing_ids.append(mid)
        pos += 4

    print(f"Parsed {len(missing_ids)} missing chunks. Starting repair...")

    
    with open(file_path, "rb") as sf:
        for mid in missing_ids:
            sf.seek(mid * CHUNK_SIZE)
            chunk = sf.read(CHUNK_SIZE)
            if not chunk:
                print(f"File ended early at chunk {mid}")
                break
            packet = mid.to_bytes(4, 'big') + chunk
            conn.sendall(packet)

    conn.sendall(b"Repair done")
    print("All repairs sent + 'Repair done' signal")

except Exception as e:
    print(f"TCP repair error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

finally:
    if 'conn' in locals():
        conn.close()
    tcp_sock.close()

print("Repair phase finished")
