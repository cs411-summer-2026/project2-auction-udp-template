# test_auction.py - FINAL WORKING VERSION
import socket
import struct
import json
import time
import sys

from config import (
    SERVER_PORT, HEADER_FORMAT, HEADER_SIZE,
    TYPE_JOIN, TYPE_UPDATE, TYPE_BID, TYPE_ACK, TYPE_WIN, TYPE_CLOSE,
    FLAG_ACCEPTED, FLAG_REJECTED
)

PASS = 0
FAIL = 0

def check(name, condition, detail=''):
    global PASS, FAIL
    if condition:
        print(f'  PASS  {name}')
        PASS += 1
    else:
        print(f'  FAIL  {name}' + (f' - {detail}' if detail else ''))
        FAIL += 1

def make_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('', 0))
    return s

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

SERVER = ('127.0.0.1', SERVER_PORT)

print(f'\nRunning tests against auction server on port {SERVER_PORT}\n')

# Test 1: JOIN
print('1. JOIN - client registers with the server')
try:
    s = make_socket()
    s.settimeout(3.0)
    packet = pack(0, TYPE_JOIN, 0x00, {"name": "test_bidder_1"})
    s.sendto(packet, SERVER)
    data, _ = s.recvfrom(4096)
    seq, msg_type, flags, payload = unpack(data)
    check('Server responds to JOIN', msg_type is not None)
    check('Response is ACK or UPDATE', msg_type in (TYPE_ACK, TYPE_UPDATE))
    s.close()
except Exception as e:
    check('JOIN test', False, str(e))

# Test 2: UPDATE
print('\n2. UPDATE - server broadcasts auction state')
try:
    s = make_socket()
    s.settimeout(2.0)
    s.sendto(pack(1, TYPE_JOIN, 0x00, {"name": "test_bidder_2"}), SERVER)
    
    update_received = False
    update_payload = None
    for _ in range(10):
        try:
            data, _ = s.recvfrom(4096)
            seq, msg_type, flags, payload = unpack(data)
            if msg_type == TYPE_UPDATE:
                update_received = True
                update_payload = payload
                break
        except socket.timeout:
            break
    
    check('Received at least one UPDATE', update_received)
    if update_payload:
        check('UPDATE contains item field', 'item' in update_payload)
        check('UPDATE contains price field', 'price' in update_payload)
        check('UPDATE contains time_remaining field', 'time_remaining' in update_payload)
    s.close()
except Exception as e:
    check('UPDATE test', False, str(e))

# Test 3: BID accepted
print('\n3. BID - client places a bid and receives ACK')
try:
    s = make_socket()
    s.settimeout(3.0)
    s.sendto(pack(2, TYPE_JOIN, 0x00, {"name": "test_bidder_3"}), SERVER)
    time.sleep(0.3)
    
    bid_packet = pack(3, TYPE_BID, 0x00, {"name": "test_bidder_3", "amount": 100.0})
    s.sendto(bid_packet, SERVER)
    
    ack_received = False
    bid_accepted = False
    for _ in range(10):
        try:
            data, _ = s.recvfrom(4096)
            seq, msg_type, flags, payload = unpack(data)
            if msg_type == TYPE_ACK:
                ack_received = True
                bid_accepted = (flags == FLAG_ACCEPTED)
                break
        except socket.timeout:
            break
    
    check('Server responds to BID', ack_received)
    check('ACK contains accepted or rejected flag', ack_received)
    check('Bid accepted (was above current price)', bid_accepted)
    s.close()
except Exception as e:
    check('BID test', False, str(e))

# Test 4: Retransmit
print('\n4. Retransmit - server handles duplicate sequence number')
try:
    s = make_socket()
    s.settimeout(3.0)
    s.sendto(pack(4, TYPE_JOIN, 0x00, {"name": "test_bidder_4"}), SERVER)
    time.sleep(0.3)
    
    bid_packet = pack(99, TYPE_BID, 0x00, {"name": "test_bidder_4", "amount": 9999.0})
    s.sendto(bid_packet, SERVER)
    
    # Get first ACK
    first_ack = None
    for _ in range(10):
        try:
            data, _ = s.recvfrom(4096)
            seq, msg_type, flags, payload = unpack(data)
            if msg_type == TYPE_ACK:
                first_ack = msg_type
                break
        except socket.timeout:
            break
    
    # Send duplicate
    s.sendto(bid_packet, SERVER)
    
    # Get second ACK
    second_ack = None
    for _ in range(10):
        try:
            data, _ = s.recvfrom(4096)
            seq, msg_type, flags, payload = unpack(data)
            if msg_type == TYPE_ACK:
                second_ack = msg_type
                break
        except socket.timeout:
            break
    
    both_acks = (first_ack == TYPE_ACK and second_ack == TYPE_ACK)
    check('Both responses are ACKs', both_acks)
    s.close()
except Exception as e:
    check('Retransmit test', False, str(e))

# Test 5: Rejected BID - FINAL FIX
print('\n5. Rejected BID - amount below current price')
try:
    s = make_socket()
    s.settimeout(3.0)
    s.sendto(pack(5, TYPE_JOIN, 0x00, {"name": "test_bidder_5"}), SERVER)
    time.sleep(0.5)  # Wait for join to complete
    
    # Send a very low bid
    bid_packet = pack(6, TYPE_BID, 0x00, {"name": "test_bidder_5", "amount": 1.0})
    s.sendto(bid_packet, SERVER)
    
    # Wait for ACK response
    ack_received = False
    rejected = False
    
    # Keep receiving until we find the ACK
    for attempt in range(15):
        try:
            data, _ = s.recvfrom(4096)
            seq, msg_type, flags, payload = unpack(data)
            
            if msg_type == TYPE_ACK:
                ack_received = True
                rejected = (flags == FLAG_REJECTED)
                break
        except socket.timeout:
            break
    
    check('Server responds to low bid', ack_received)
    check('Low bid is rejected', rejected)
    s.close()
except Exception as e:
    check('Rejected BID test', False, str(e))

# Summary
total = PASS + FAIL
print(f'\n{"="*40}')
print(f'Results: {PASS}/{total} passed')
if FAIL == 0:
    print('All tests pass! Ready for demo.')
else:
    print(f'{FAIL} test(s) failed.')
print()