# auction_server.py
# CS411 - Computer Networks - Summer 2026
# Project 2 - BidWave: Real-Time Auction System
#
# Team: <Lastname1-Lastname2>
#
# Run:  python3 auction_server.py
# Test: python3 test_auction.py  (server must be running first)

import socket
import struct
import threading
import json
import time

from config import (
    SERVER_PORT, SMTP_HOST, SMTP_PORT,
    HEADER_FORMAT, HEADER_SIZE,
    TYPE_JOIN, TYPE_UPDATE, TYPE_BID, TYPE_ACK, TYPE_WIN, TYPE_CLOSE,
    FLAG_ACCEPTED, FLAG_REJECTED
)


# ── Auction state ──────────────────────────────────────────────────────────────
# Modify these to set up your auction item
AUCTION_ITEM    = "Vintage Camera"
STARTING_PRICE  = 50.0
AUCTION_DURATION = 120   # seconds

# Do not modify below - shared state accessed by multiple threads
state = {
    "item":            AUCTION_ITEM,
    "price":           STARTING_PRICE,
    "highest_bidder":  None,
    "time_remaining":  AUCTION_DURATION,
    "running":         False,
}
state_lock = threading.Lock()

# Registry of connected clients: maps addr -> client_name
clients = {}
clients_lock = threading.Lock()

# Track seen bid sequence numbers to detect retransmits: maps addr -> last_seq
seen_bids = {}


# ── Packet helpers ─────────────────────────────────────────────────────────────

def pack_packet(seq, msg_type, flags, payload_dict):
    """Pack a header + JSON payload into bytes ready to send."""
    # TODO: use struct.pack with HEADER_FORMAT
    # then append the JSON-encoded payload as UTF-8 bytes
    pass


def unpack_packet(data):
    """Unpack received bytes into (seq, msg_type, flags, payload_dict).
    Return None if the packet is malformed."""
    # TODO: use struct.unpack on the first HEADER_SIZE bytes
    # then JSON-decode the rest
    pass


# ── Core server logic ──────────────────────────────────────────────────────────

def broadcast_update(sock):
    """Send the current auction state to all registered clients.
    This is called every second. No ACK expected - fire and forget."""
    # TODO:
    # 1. Build an UPDATE packet with the current state dict
    # 2. Send it to every addr in clients using sock.sendto()
    pass


def handle_join(sock, addr, seq, payload):
    """Register a new client."""
    # TODO:
    # 1. Add addr to the clients dict with the client's chosen name
    # 2. Send back an ACK so the client knows it is registered
    # 3. Print a log message
    pass


def handle_bid(sock, addr, seq, payload):
    """Process an incoming bid.
    Must handle retransmits (same seq from same addr)."""
    # TODO:
    # 1. Check if this is a duplicate (same seq from same addr) - if so, resend ACK only
    # 2. Validate the bid amount (must be higher than current price)
    # 3. If valid: update state, record this client as highest bidder, FLAG_ACCEPTED
    # 4. If invalid: FLAG_REJECTED
    # 5. Send ACK with the appropriate flag
    # 6. Update seen_bids[addr] = seq
    pass


def receive_loop(sock):
    """Main receive loop - runs in its own thread.
    Dispatches incoming packets to the right handler."""
    # TODO:
    # Use sock.recvfrom() in a loop
    # Unpack each packet and call handle_join or handle_bid based on TYPE
    pass


def countdown_loop(sock):
    """Decrements time_remaining every second and broadcasts an update.
    Closes the auction when time runs out."""
    # TODO:
    # Every second: decrement state["time_remaining"], call broadcast_update()
    # When time_remaining reaches 0: set state["running"] = False
    # Then call close_auction()
    pass


def close_auction(sock):
    """Broadcast auction closed, send WIN to the winner, send SMTP notification."""
    # TODO:
    # 1. Send a CLOSE packet to all clients
    # 2. Send a WIN packet specifically to the winner's addr
    # 3. Call send_smtp_notification() for the winner
    pass


# ── SMTP notification ──────────────────────────────────────────────────────────

def send_smtp_notification(winner_name, item, final_price):
    """Open a raw TCP connection to the SMTP server and send the winner email.
    Do NOT use smtplib. Use socket.SOCK_STREAM and implement the SMTP
    command exchange yourself."""
    # TODO:
    # 1. Connect to SMTP_HOST:SMTP_PORT using a TCP socket
    # 2. Read the server greeting (220 ...)
    # 3. Send EHLO, MAIL FROM, RCPT TO, DATA, the email body, ".", QUIT
    # 4. Read and print each server response
    # 5. Close the connection
    #
    # Hint: each SMTP command ends with \r\n
    # Hint: the email body ends with a line containing only "."
    pass


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', SERVER_PORT))

    print(f"BidWave Auction Server started on port {SERVER_PORT}")
    print(f"Item: {AUCTION_ITEM} | Starting price: ${STARTING_PRICE:.2f} | Duration: {AUCTION_DURATION}s")
    print("Waiting for clients to join...\n")

    # Give clients 10 seconds to join before starting the countdown
    time.sleep(10)

    with state_lock:
        state["running"] = True

    recv_thread = threading.Thread(target=receive_loop, args=(sock,), daemon=True)
    recv_thread.start()

    countdown_loop(sock)

    sock.close()
    print("Server shut down.")


if __name__ == '__main__':
    main()
