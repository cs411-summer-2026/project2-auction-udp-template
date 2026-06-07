# resolver.py
# CS411 - Computer Networks - Summer 2026
# Local DNS-like name registry for the BidWave system.
# Do not modify this file.
#
# In a real network, your application would send a UDP query to port 53
# and receive a DNS response. Here we simulate that lookup using a
# local registry so you can observe the concept without needing a real
# DNS server.
#
# Observe in Wireshark: your client calls resolve() before any auction
# traffic begins. In a real app, this would appear as a UDP packet to
# port 53 before your application traffic starts.

REGISTRY = {
    "bidwave.server": "127.0.0.1",
    "smtp.bidwave":   "127.0.0.1",
}


def resolve(name):
    """Look up a hostname in the local registry.
    Returns the IP address string, or None if not found."""
    result = REGISTRY.get(name)
    if result:
        print(f"[DNS] Resolved '{name}' -> {result}")
    else:
        print(f"[DNS] Could not resolve '{name}'")
    return result
