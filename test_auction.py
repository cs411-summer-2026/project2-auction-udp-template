# test_auction.py
# CS411 - Computer Networks - Summer 2026
# Automated tests for Project 2 - BidWave
#
# Run with: python3 test_auction.py
# The auction server must be running before you run these tests.

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
    s.settimeout(3.0)
    return s


def pack(seq, msg_type, flags, payload_dict):
    payload = json.dumps(payload_dict).encode('utf-8')
    header  = struct.pack(HEADER_FORMAT, seq, msg_type, flags)
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


# ── Test 1: JOIN and receive ACK ───────────────────────────────────────────────
print('1. JOIN - client registers with the server')
try:
    s = make_socket()
    packet = pack(0, TYPE_JOIN, 0x00, {"name": "test_bidder_1"})
    s.sendto(packet, SERVER)
    data, _ = s.recvfrom(4096)
    seq, msg_type, flags, payload = unpack(data)
    check('Server responds to JOIN', msg_type is not None)
    check('Response is ACK or UPDATE', msg_type in (TYPE_ACK, TYPE_UPDATE))
    s.close()
except socket.timeout:
    check('Server responds to JOIN', False, 'timeout - is the server running?')
    sys.exit(1)
except Exception as e:
    check('JOIN completed', False, str(e))


# ── Test 2: Receive UPDATE broadcast ──────────────────────────────────────────
print('\n2. UPDATE - server broadcasts auction state')
try:
    s = make_socket()
    # Join first
    s.sendto(pack(1, TYPE_JOIN, 0x00, {"name": "test_bidder_2"}), SERVER)
    # Wait for an UPDATE (may arrive immediately after JOIN or within 1 second)
    updates = []
    deadline = time.time() + 3.0
    while time.time() < deadline:
        try:
            data, _ = s.recvfrom(4096)
            seq, msg_type, flags, payload = unpack(data)
            if msg_type == TYPE_UPDATE:
                updates.append(payload)
                break
        except socket.timeout:
            break
    check('Received at least one UPDATE', len(updates) > 0)
    if updates:
        p = updates[0]
        check('UPDATE contains item field', 'item' in p, f'got keys: {list(p.keys())}')
        check('UPDATE contains price field', 'price' in p)
        check('UPDATE contains time_remaining field', 'time_remaining' in p)
    s.close()
except Exception as e:
    check('UPDATE test completed', False, str(e))


# ── Test 3: BID and receive ACK ───────────────────────────────────────────────
print('\n3. BID - client places a bid and receives ACK')
try:
    s = make_socket()
    s.sendto(pack(2, TYPE_JOIN, 0x00, {"name": "test_bidder_3"}), SERVER)
    time.sleep(0.2)

    # Get current price from an UPDATE
    current_price = 0
    s.sendto(pack(3, TYPE_JOIN, 0x00, {"name": "test_bidder_3b"}), SERVER)
    deadline = time.time() + 3.0
    while time.time() < deadline:
        try:
            data, _ = s.recvfrom(4096)
            seq, msg_type, flags, payload = unpack(data)
            if msg_type == TYPE_UPDATE and 'price' in payload:
                current_price = payload['price']
                break
        except socket.timeout:
            break

    # Place a bid higher than current price
    bid_amount = current_price + 10.0
    bid_packet = pack(4, TYPE_BID, 0x00, {"name": "test_bidder_3", "amount": bid_amount})
    s.sendto(bid_packet, SERVER)

    data, _ = s.recvfrom(4096)
    seq, msg_type, flags, payload = unpack(data)
    check('Server responds to BID', msg_type == TYPE_ACK, f'got type {msg_type}')
    check('ACK contains accepted or rejected flag',
          flags in (FLAG_ACCEPTED, FLAG_REJECTED),
          f'got flags {flags}')
    check('Bid accepted (was above current price)', flags == FLAG_ACCEPTED,
          f'bid was ${bid_amount:.2f}, current was ${current_price:.2f}')
    s.close()
except Exception as e:
    check('BID test completed', False, str(e))


# ── Test 4: Duplicate BID (retransmit) ────────────────────────────────────────
print('\n4. Retransmit - server handles duplicate sequence number')
try:
    s = make_socket()
    s.sendto(pack(5, TYPE_JOIN, 0x00, {"name": "test_bidder_4"}), SERVER)
    time.sleep(0.2)

    # Send the same bid twice with the same seq number
    bid_packet = pack(99, TYPE_BID, 0x00, {"name": "test_bidder_4", "amount": 9999.0})
    s.sendto(bid_packet, SERVER)
    data, _ = s.recvfrom(4096)
    seq1, type1, flags1, _ = unpack(data)

    # Retransmit with same seq
    s.sendto(bid_packet, SERVER)
    data, _ = s.recvfrom(4096)
    seq2, type2, flags2, _ = unpack(data)

    check('Server responds to retransmit', type2 == TYPE_ACK, f'got type {type2}')
    check('Both responses are ACKs', type1 == TYPE_ACK and type2 == TYPE_ACK)
    s.close()
except Exception as e:
    check('Retransmit test completed', False, str(e))


# ── Test 5: Rejected BID (too low) ────────────────────────────────────────────
print('\n5. Rejected BID - amount below current price')
try:
    s = make_socket()
    s.sendto(pack(6, TYPE_JOIN, 0x00, {"name": "test_bidder_5"}), SERVER)
    time.sleep(0.2)

    # Send a very low bid
    bid_packet = pack(7, TYPE_BID, 0x00, {"name": "test_bidder_5", "amount": 0.01})
    s.sendto(bid_packet, SERVER)
    data, _ = s.recvfrom(4096)
    seq, msg_type, flags, payload = unpack(data)

    check('Server responds to low bid', msg_type == TYPE_ACK)
    check('Low bid is rejected', flags == FLAG_REJECTED, f'got flags {flags}')
    s.close()
except Exception as e:
    check('Rejected BID test completed', False, str(e))


# ── Summary ────────────────────────────────────────────────────────────────────
total = PASS + FAIL
print(f'\n{"=" * 40}')
print(f'Results: {PASS}/{total} passed')
if FAIL == 0:
    print('All tests pass - good to go for Thursday.')
else:
    print(f'{FAIL} test(s) failed - fix these before the demo.')
print()
