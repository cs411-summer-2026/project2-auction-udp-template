# auction_client.py
# CS411 - Computer Networks - Summer 2026
# Project 2 - BidWave: Real-Time Auction System
#
# Team: <Lastname1-Lastname2>
#
# Run:  python3 auction_client.py

import socket
import struct
import threading
import json
import time

from config import (
    SERVER_PORT, HEADER_FORMAT, HEADER_SIZE,
    TYPE_JOIN, TYPE_UPDATE, TYPE_BID, TYPE_ACK, TYPE_WIN, TYPE_CLOSE,
    FLAG_ACCEPTED, FLAG_REJECTED
)
from resolver import resolve


# ── Configuration ──────────────────────────────────────────────────────────────
BIDDER_NAME = input("Enter your bidder name: ")
SERVER_NAME = "bidwave.server"   # resolved via resolver.py

BID_TIMEOUT  = 2.0   # seconds to wait for an ACK before retransmitting
MAX_RETRIES  = 5     # maximum number of retransmit attempts

# Sequence number for outgoing bid packets - increment for each new bid
seq_counter = 0
seq_lock    = threading.Lock()

# Shared flag so threads know when the auction is over
auction_over = threading.Event()


# ── Packet helpers ─────────────────────────────────────────────────────────────

def pack_packet(seq, msg_type, flags, payload_dict):
    """Pack a header + JSON payload into bytes ready to send."""
    # TODO: same as server - struct.pack + JSON encode
    pass


def unpack_packet(data):
    """Unpack received bytes into (seq, msg_type, flags, payload_dict)."""
    # TODO: same as server - struct.unpack + JSON decode
    pass


# ── Core client logic ──────────────────────────────────────────────────────────

def join_server(sock, server_addr):
    """Send a JOIN packet to register with the server."""
    # TODO:
    # 1. Build a JOIN packet with payload {"name": BIDDER_NAME}
    # 2. Send it to server_addr
    # 3. Print confirmation
    pass


def display_update(payload):
    """Print the current auction state in a readable format."""
    # TODO: print item, current price, highest bidder, time remaining
    # Make it clear and readable - this is what bidders watch
    pass


def send_bid(sock, server_addr, amount):
    """Send a bid and wait for ACK. Retransmit on timeout.
    Returns True if the bid was accepted, False otherwise."""
    global seq_counter

    with seq_lock:
        seq = seq_counter
        seq_counter += 1

    # TODO:
    # 1. Build a BID packet with payload {"name": BIDDER_NAME, "amount": amount}
    # 2. Send it to server_addr
    # 3. Set a timeout on the socket and wait for ACK
    # 4. If timeout expires: retransmit (up to MAX_RETRIES times)
    # 5. When ACK arrives: check FLAG_ACCEPTED or FLAG_REJECTED and return accordingly
    # 6. If all retries exhausted: print error and return False
    pass


def receive_loop(sock):
    """Listen for incoming packets (UPDATE, WIN, CLOSE) in a background thread."""
    # TODO:
    # Use sock.recvfrom() in a loop until auction_over is set
    # For UPDATE: call display_update()
    # For WIN: print congratulations message, set auction_over
    # For CLOSE: print auction ended message, set auction_over
    pass


def bid_loop(sock, server_addr):
    """Read bid amounts from the user and send them."""
    # TODO:
    # Loop until auction_over is set
    # Read a number from input()
    # Call send_bid() and display the result
    # Handle non-numeric input gracefully
    pass


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    # Resolve server address via local DNS registry
    server_ip = resolve(SERVER_NAME)
    if server_ip is None:
        print(f"Could not resolve {SERVER_NAME}. Is the server running?")
        return

    server_addr = (server_ip, SERVER_PORT)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Bind to a random available port so the server can identify this client
    sock.bind(('', 0))

    print(f"Connecting to auction server at {server_addr}...")

    join_server(sock, server_addr)

    recv_thread = threading.Thread(target=receive_loop, args=(sock,), daemon=True)
    recv_thread.start()

    bid_loop(sock, server_addr)

    auction_over.wait()
    sock.close()
    print("Disconnected.")


if __name__ == '__main__':
    main()
