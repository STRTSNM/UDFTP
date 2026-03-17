import socket
import os
import struct
import time

VPS_IP = ""
PORT = 5201          # upd
TCP_PORT = 5202
file_path = "received_randomfile.bin"
CHUNK_SIZE = 1400
HEADER_SIZE = 4

# initial transfer through udp
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(15.0)

print("Sending START to server...")
sock.sendto(b"START", (VPS_IP, PORT))

f = open(file_path, "wb+")  # read/write mode + allow seek
received = set()
total_chunks = None
total_size = None
max_id_seen = -1

print("Receiving UDP stream...")

while True:
    try:
        data, addr = sock.recvfrom(CHUNK_SIZE + HEADER_SIZE + 32)
    except socket.timeout:
        print("UDP timeout :  assuming transfer finished or stalled")
        break

    if data.startswith(b"TOTAL"):
        total_chunks, total_size = struct.unpack(">IQ", data[5:5+4+8])
        print(f"Server sent TOTAL: {total_chunks} chunks, {total_size:,} bytes expected")
        continue

    if len(data) == 4 and data == b"DONE":
        print("Received DONE from server")
        break

    if len(data) < HEADER_SIZE + 1:
        continue

    chunk_id = struct.unpack(">I", data[:4])[0]
    payload = data[4:]

    f.seek(chunk_id * CHUNK_SIZE)
    f.write(payload)

    if chunk_id not in received:
        received.add(chunk_id)
        max_id_seen = max(max_id_seen, chunk_id)

sock.close()


if total_chunks is None:
    if max_id_seen >= 0:
        total_chunks = max_id_seen + 1
        print("Warning: TOTAL packet lost → estimating from highest chunk id")
    else:
        print("Error: no chunks or TOTAL received → aborting")
        f.close()
        exit(1)

missing = [i for i in range(total_chunks) if i not in received]
print(f"UDP phase finished. Received {len(received):,} / {total_chunks:,} chunks")
print(f"Missing chunks: {len(missing):,}")

time.sleep(5)  # small grace period for server to start TCP listener

# repair phase thorugh udp
if missing:
    print(f"Starting TCP repair for {len(missing)} chunks...")
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.settimeout(90)

    try:
        tcp_sock.connect((VPS_IP, TCP_PORT))
    except Exception as e:
        print(f"TCP connection failed: {e}")
        f.close()
        exit(1)

   
    list_msg = b"LIST" + len(missing).to_bytes(4, 'big')
    for mid in missing:
        list_msg += mid.to_bytes(4, 'big')
    tcp_sock.sendall(list_msg)

   
    print(f"Waiting for {len(missing)} repair chunks...")
    repaired_count = 0

    while repaired_count < len(missing):
        # Read exactly 4 bytes for chunk ID
        header_bytes = b""
        while len(header_bytes) < 4:
            got = tcp_sock.recv(4 - len(header_bytes))
            if not got:
                print(f"Connection closed during header (repaired so far: {repaired_count})")
                break
            header_bytes += got

        if len(header_bytes) < 4:
            break

        chunk_id = struct.unpack(">I", header_bytes)[0]

        payload = b""
        to_read = CHUNK_SIZE
        while to_read > 0:
            got = tcp_sock.recv(to_read)
            if not got:
                print(f"Incomplete payload for chunk {chunk_id} (got {len(payload)}/{CHUNK_SIZE})")
                break
            payload += got
            to_read -= len(got)

        if len(payload) == 0:
            break

        f.seek(chunk_id * CHUNK_SIZE)
        f.write(payload)

        repaired_count += 1
        print(f"Repaired chunk {chunk_id}  ({repaired_count}/{len(missing)})", end="\r")

    marker = b""
    while len(marker) < 11:  # len(b"Repair done") = 11
        got = tcp_sock.recv(11 - len(marker))
        if not got:
            break
        marker += got

    if marker.startswith(b"Repair done"):
        print("\nRepair done received → success")
    else:
        print(f"\nWarning: did not receive 'Repair done' (got {marker!r})")

    tcp_sock.close()

else:
    print("No missing chunks → no TCP repair needed")


if total_size is not None:
    f.truncate(total_size)
f.close()

final_size = os.path.getsize(file_path)
print("\nTransfer finished!")
print(f"  File: {file_path}")
print(f"  Size on disk : {final_size:,} bytes")
if total_size:
    print(f"  Expected size: {total_size:,} bytes")
