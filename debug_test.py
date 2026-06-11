# debug_test.py - Debug version to see what flags are being sent
import socket
import struct
import json
import time

from config import (
    SERVER_PORT, HEADER_FORMAT, HEADER_SIZE,
    TYPE_JOIN, TYPE_UPDATE, TYPE_BID, TYPE_ACK,
    FLAG_ACCEPTED, FLAG_REJECTED
)

def pack(seq, msg_type, flags, payload_dict):
    payload = json.dumps(payload_dict).encode('utf-8')
    header = struct.pack(HEADER_FORMAT, seq, msg_type, flags)
    return header + payload

def unpack(data):
    if len(data) < HEADER_SIZE:
        return None, None, None, None
    seq, msg_type, flags = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    try:
        payload = json.loads(data[HEADER_SIZE:].decode('utf-8'))
    except Exception:
        payload = {}
    return seq, msg_type, flags, payload

print("=== DEBUG: Testing rejected bid ===\n")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3.0)
sock.bind(('', 0))

# Send JOIN
print("1. Sending JOIN...")
join_packet = pack(1, TYPE_JOIN, 0x00, {"name": "debug_client"})
sock.sendto(join_packet, ('127.0.0.1', SERVER_PORT))

# Wait for response (clear any pending packets)
time.sleep(0.5)
# Flush any pending packets
try:
    while True:
        data, _ = sock.recvfrom(4096)
        print(f"   Received initial packet")
except socket.timeout:
    pass

# Send a low bid
print("\n2. Sending low bid ($1.00)...")
bid_packet = pack(2, TYPE_BID, 0x00, {"name": "debug_client", "amount": 1.0})
sock.sendto(bid_packet, ('127.0.0.1', SERVER_PORT))

# Receive responses
print("\n3. Receiving responses:")
for i in range(10):
    try:
        data, addr = sock.recvfrom(4096)
        seq, msg_type, flags, payload = unpack(data)
        
        print(f"\n   Packet {i+1}:")
        print(f"     Type: {msg_type} ", end="")
        if msg_type == TYPE_ACK:
            print("(ACK)")
        elif msg_type == TYPE_UPDATE:
            print("(UPDATE)")
        else:
            print(f"(Unknown: {msg_type})")
        
        print(f"     Flags: {flags} ", end="")
        if flags == FLAG_ACCEPTED:
            print("(FLAG_ACCEPTED)")
        elif flags == FLAG_REJECTED:
            print("(FLAG_REJECTED)")
        else:
            print(f"(Unknown flag value)")
        
        print(f"     Payload: {payload}")
        
        if msg_type == TYPE_ACK:
            print(f"\n*** ACK received with flags={flags} ***")
            if flags == FLAG_REJECTED:
                print("*** CORRECT: Flag is REJECTED ***")
            else:
                print(f"*** ERROR: Expected FLAG_REJECTED({FLAG_REJECTED}), got {flags} ***")
            break
            
    except socket.timeout:
        print("\n   Timeout - no more packets")
        break

sock.close()
print("\n=== Debug complete ===")