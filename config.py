# config.py
# CS411 - Computer Networks - Summer 2026
# Shared constants for the BidWave auction system.
# Do not modify this file.

import struct

# Network configuration
SERVER_PORT = 9000
SMTP_HOST   = 'localhost'
SMTP_PORT   = 8025

# Packet header: unsigned short (seq) + unsigned char (type) + unsigned char (flags)
HEADER_FORMAT = '!HBB'
HEADER_SIZE   = struct.calcsize(HEADER_FORMAT)   # 4 bytes

# Message types
TYPE_JOIN   = 0x01
TYPE_UPDATE = 0x02
TYPE_BID    = 0x03
TYPE_ACK    = 0x04
TYPE_WIN    = 0x05
TYPE_CLOSE  = 0x06

# Flags
FLAG_ACCEPTED  = 0x01
FLAG_REJECTED  = 0x02
FLAG_RETRANSMIT = 0x04