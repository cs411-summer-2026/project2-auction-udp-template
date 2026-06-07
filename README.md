# Project 2 - BidWave: A Real-Time Auction System over UDP

**Course:** CS411 - Computer Networks - Summer 2026
**Layer:** Transport Layer
**Team size:** 2 students
**Duration:** Monday to Thursday (4 sessions x 1.5h)
**Language:** Python 3.8+
**Demo:** Thursday, live, 8 minutes per team

---

## The problem

Online auctions are time-sensitive. When you place a bid on eBay, every millisecond counts. But what happens at the network level when hundreds of bidders are watching the same item tick down to zero?

Most real-time systems - auctions, games, live dashboards - make a deliberate choice: they use **UDP instead of TCP**. UDP is faster but unreliable. Packets can be lost, arrive out of order, or never arrive at all. The application must decide what to do about that.

This week you build **BidWave**, a real-time auction platform where:

- A server broadcasts live auction updates to all connected bidders every second
- Clients receive updates and display the current item, price, and time remaining
- When a bidder places a bid, it must be reliably delivered and acknowledged
- When the auction closes, the server constructs and sends a winner notification email using raw SMTP

The core question you will answer by Thursday: **when do you need reliability, and when do you not?**

---

## What you will build

The system has two programs:

**`auction_server.py`** - the auctioneer

- Maintains the auction state: item name, current price, highest bidder, time remaining
- Broadcasts auction updates to all known clients every second over UDP (no reliability needed)
- Receives bids from clients, validates them, sends back an ACK
- Retransmits ACK if a client retransmits a bid (detect duplicate sequence numbers)
- Closes the auction when time runs out and announces the winner
- Sends a winner notification by constructing a raw SMTP message

**`auction_client.py`** - the bidder

- Registers with the server by sending a JOIN message
- Listens for broadcast updates and displays them in the terminal
- Accepts a bid amount from the user (typed in the terminal)
- Sends the bid over UDP and waits for an ACK
- Retransmits the bid if no ACK arrives within a timeout period
- Displays confirmation when the bid is accepted or rejected

---

## What you do NOT need to build

- A graphical interface
- Authentication or user accounts
- Persistent storage of auction history
- Multiple simultaneous auctions
- A real SMTP server (you simulate the email sending)

---

## Key concepts

### Why UDP for auction broadcasts?

TCP guarantees delivery. That sounds better - so why would anyone use UDP?

Consider the auction broadcast: every second the server sends the current price to all bidders. If one of those packets is lost, the client simply waits for the next one a second later. The lost packet is stale data - retransmitting it a second later is worse than doing nothing, because the client would briefly see old information.

This is the fundamental insight of the transport layer: **reliability has a cost**, and sometimes that cost is not worth paying. Real-time data that expires quickly is a classic case where UDP is the right choice.

Bids are different. If your bid packet is lost, you do not find out until the auction closes and someone else won. That is unacceptable. Bids need reliability - which you implement yourself on top of UDP.

### UDP vs TCP - the key differences

| Property | TCP | UDP |
|----------|-----|-----|
| Connection | Established before data flows | No connection, just send |
| Reliability | Guaranteed delivery | Best effort only |
| Ordering | Packets arrive in order | May arrive out of order |
| Speed | Slower (overhead) | Faster (no overhead) |
| Use cases | HTTP, email, file transfer | Streaming, gaming, DNS, auctions |

With UDP you use `SOCK_DGRAM` instead of `SOCK_STREAM`. There is no `accept()`, no `connect()` for the server. You just bind and call `recvfrom()` which returns both the data and the sender's address.

```python
# UDP server - no accept(), no connection setup
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('', 9000))

data, addr = sock.recvfrom(4096)   # addr is (ip, port) of the sender
sock.sendto(response, addr)         # send back to that specific address
```

### Multiplexing - one socket, many clients

Your server uses **one UDP socket** for everything. Multiple clients send to the same port. The server tells them apart using the `addr` returned by `recvfrom()` - that is the client's IP address and port number combined.

This is transport-layer multiplexing in its purest form. The (source IP, source port, destination IP, destination port) tuple uniquely identifies each client. You do not need separate sockets.

### Reliability over UDP - what you implement for bids

Since you cannot use TCP for bids, you implement a minimal reliability mechanism yourself:

**Stop-and-wait:** the client sends one bid packet, starts a timer, and waits for an ACK. If the timer expires before the ACK arrives, the client retransmits the same packet with the same sequence number. The server detects duplicate sequence numbers and ignores duplicates (but still sends the ACK, because the first one might have been lost).

This is exactly what TCP does internally, but you implement it yourself for bids only.

### The custom packet format

All messages in BidWave use a fixed binary header. You pack and unpack it using Python's `struct` module.

```
Byte layout (network byte order, big-endian):

 0        1        2        3
+--------+--------+--------+--------+
|    SEQUENCE NUMBER (2 bytes)       |
+--------+--------+--------+--------+
|  TYPE  |  FLAGS |   PAYLOAD ...   |
+--------+--------+                  +

Total header size: 4 bytes
```

**TYPE values:**

| Value | Name | Direction | Description |
|-------|------|-----------|-------------|
| `0x01` | JOIN | client to server | client registers to participate |
| `0x02` | UPDATE | server to clients | broadcast: current auction state |
| `0x03` | BID | client to server | a bid amount |
| `0x04` | ACK | server to client | bid received and processed |
| `0x05` | WIN | server to winner | you won the auction |
| `0x06` | CLOSE | server to all | auction is over |

**FLAGS byte:**

| Bit | Meaning |
|-----|---------|
| `0x01` | BID_ACCEPTED - the bid is the new highest |
| `0x02` | BID_REJECTED - bid is too low or auction closed |
| `0x04` | RETRANSMIT - this is a retransmitted packet |

Packing and unpacking with struct:

```python
import struct

HEADER_FORMAT = '!HBB'   # unsigned short (2) + unsigned char (1) + unsigned char (1)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)   # = 4 bytes

# Pack a header
header = struct.pack(HEADER_FORMAT, seq_num, msg_type, flags)

# Unpack a received header
seq_num, msg_type, flags = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
payload = data[HEADER_SIZE:]
```

### The payload format

After the 4-byte header, the payload is JSON encoded as UTF-8 bytes. This keeps the payload human-readable in Wireshark.

```python
import json

# Sending an UPDATE packet
payload = json.dumps({
    "item": "Vintage Camera",
    "price": 145.00,
    "highest_bidder": "alice",
    "time_remaining": 42
}).encode('utf-8')

packet = struct.pack(HEADER_FORMAT, seq, 0x02, 0x00) + payload
sock.sendto(packet, client_addr)
```

### SMTP - what it is and what you do with it

SMTP (Simple Mail Transfer Protocol) is the protocol email servers use to send messages. Like HTTP, it is plain text over a TCP connection. When the auction closes, your server will open a TCP connection to a local SMTP server (or simulate one) and send a winner notification.

A raw SMTP exchange looks like this:

```
CLIENT: (connects to port 25)
SERVER: 220 mail.example.com ESMTP ready
CLIENT: EHLO bidwave.local
SERVER: 250 Hello
CLIENT: MAIL FROM:<auction@bidwave.local>
SERVER: 250 OK
CLIENT: RCPT TO:<winner@bidwave.local>
SERVER: 250 OK
CLIENT: DATA
SERVER: 354 Start mail input
CLIENT: Subject: You won the auction!
CLIENT: From: BidWave <auction@bidwave.local>
CLIENT: To: winner@bidwave.local
CLIENT:
CLIENT: Congratulations! You won "Vintage Camera" with a bid of $145.00.
CLIENT: .
SERVER: 250 Message accepted
CLIENT: QUIT
SERVER: 221 Bye
```

You will implement this exchange yourself using a raw TCP socket - the same way you built your HTTP server last week.

For the demo, you use a local SMTP testing server called **aiosmtpd** which accepts connections on port 8025 and prints everything it receives to the terminal without actually sending any email.

Install it once:
```bash
pip install aiosmtpd
```

Run it alongside your auction server:
```bash
python3 -m aiosmtpd -n -l localhost:8025
```

### DNS - what it is and how it appears here

DNS (Domain Name System) translates human-readable names like `bidwave.local` into IP addresses. It runs over UDP on port 53.

Before your auction client connects to the server, it performs a simulated DNS lookup. The repo includes a tiny `resolver.py` that acts as a local DNS registry - a Python dict mapping names to addresses. Your client calls it before connecting, just as a real application would query a DNS server before opening a connection.

This lets you observe in Wireshark the distinct phases of a real network interaction: name resolution first, then the application protocol.

---

## Repository structure

```
project2-auction/
|-- README.md               this file
|-- auction_server.py       the auctioneer - you implement this
|-- auction_client.py       the bidder - you implement this
|-- resolver.py             local DNS registry - provided, do not modify
|-- test_auction.py         automated tests - do not modify
|-- config.py               shared constants (ports, timeouts) - do not modify
```

---

## Constraints

### Hard constraints

- `socket.SOCK_DGRAM` only for auction traffic - no TCP for bids or broadcasts
- Binary header using `struct.pack` - no text-based or JSON-only packets
- One server socket for all clients - no separate socket per client
- Bids must be reliably delivered: retransmit on timeout, detect duplicates
- SMTP winner notification over a raw TCP socket - no `smtplib`
- Wireshark capture must be live during the demo

### Your choices

- The item being auctioned and its starting price
- Auction duration (minimum 60 seconds for the demo)
- Timeout value for bid retransmission and how you justify it
- What BID_REJECTED looks like on the client side
- Any display formatting in the client terminal
- One optional feature (see below)

---

## Optional feature - pick one

| Feature | Description |
|---------|-------------|
| **Bid history** | Server tracks and broadcasts the last 3 bids alongside the current price |
| **Reserve price** | Auction only closes if the final bid exceeds a hidden minimum set at startup |
| **Multi-item** | Server runs two sequential auctions, clients stay connected between them |
| **Late join** | A client that joins mid-auction immediately receives the current state |

---

## Wireshark guide

For this project you will see two distinct types of traffic:

**UDP traffic - the auction**

Filter: `udp.port == 9000`

You will see:
- Periodic UPDATE packets from the server to all clients (one per second)
- BID packets from clients to the server
- ACK packets from the server back to bidding clients
- A CLOSE or WIN packet at the end

Click any packet, go to the **Data** section in the middle panel. You will see your raw bytes - the 4-byte header followed by the JSON payload. You must be able to identify the TYPE byte and the sequence number.

**TCP traffic - the SMTP notification**

Filter: `tcp.port == 8025`

After the auction closes you will see a TCP connection open to the SMTP server. Right-click any packet and select **Follow TCP Stream** to read the full SMTP exchange as text.

**What you must explain in the demo:**

- Why the UPDATE packets have no ACK from clients (intentional, justify it)
- Point to a BID packet and its corresponding ACK
- Show a retransmitted BID if packet loss was introduced
- Point to the SMTP exchange and walk through each command

---

## Running the tests

```bash
# Terminal 1 - start the local SMTP server
python3 -m aiosmtpd -n -l localhost:8025

# Terminal 2 - start the auction server
python3 auction_server.py

# Terminal 3 - start a client
python3 auction_client.py

# Terminal 4 - run the automated tests
python3 test_auction.py
```

---

## Simulating packet loss

On Linux you can introduce artificial packet loss using `tc netem`.
This will make your bid retransmission visible in Wireshark:

```bash
# Add 15% packet loss on loopback
sudo tc qdisc add dev lo root netem loss 15%

# Remove it after the demo
sudo tc qdisc del dev lo root

# Check current settings
tc qdisc show dev lo
```

During the demo, turn on loss mid-auction and show a BID being retransmitted.

---

## Demo checklist

- [ ] `auction_server.py` starts and prints the auction item and starting price
- [ ] At least 2 clients connect and display live updates
- [ ] A bid is placed, ACK received, price updates for all clients
- [ ] Wireshark shows UDP packets with correct TYPE bytes visible in hex
- [ ] A retransmit is demonstrated (manually or via netem)
- [ ] Auction closes, SMTP exchange visible in Wireshark
- [ ] aiosmtpd terminal shows the winner notification email content
- [ ] Automated tests pass: `python3 test_auction.py`

---

## Demo structure (8 minutes)

| Time | What |
|------|------|
| 0:00 - 1:00 | Start server and two clients, show live updates appearing |
| 1:00 - 3:00 | Place a bid, Wireshark: point to BID packet, ACK, header bytes |
| 3:00 - 4:00 | Show UPDATE packets, explain why there is no ACK for them |
| 4:00 - 5:00 | Demonstrate retransmission under packet loss |
| 5:00 - 6:30 | Auction closes, walk through SMTP exchange in Wireshark |
| 6:30 - 8:00 | Peer Q&A |

---

*CS411 - Computer Networks - Summer 2026*
