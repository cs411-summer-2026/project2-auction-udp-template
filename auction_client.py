# gui_client.py - GUI Auction Client
import socket
import struct
import threading
import json
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from config import (
    SERVER_PORT, HEADER_FORMAT, HEADER_SIZE,
    TYPE_JOIN, TYPE_UPDATE, TYPE_BID, TYPE_ACK, TYPE_WIN, TYPE_CLOSE,
    FLAG_ACCEPTED, FLAG_REJECTED
)
from resolver import resolve


class AuctionClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("BidWave Auction Client")
        self.root.geometry("700x500")
        self.root.resizable(True, True)
        
        # Client state
        self.bidder_name = ""
        self.server_addr = None
        self.client_socket = None
        self.connected = False
        self.auction_active = True
        self.seq_counter = 0
        self.seq_lock = threading.Lock()
        self.BID_TIMEOUT = 2.0
        self.MAX_RETRIES = 5
        
        self.setup_ui()
        self.show_join_dialog()
        
    def setup_ui(self):
        # Status Bar
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill="x", padx=10, pady=5)
        
        self.status_label = ttk.Label(self.status_frame, text="● Disconnected", foreground="red")
        self.status_label.pack(side="left", padx=5)
        
        self.server_label = ttk.Label(self.status_frame, text="Server: Not connected")
        self.server_label.pack(side="left", padx=20)
        
        self.name_label = ttk.Label(self.status_frame, text="Bidder: --")
        self.name_label.pack(side="left", padx=20)
        
        # Auction Display Frame
        auction_frame = ttk.LabelFrame(self.root, text="Live Auction Feed", padding=10)
        auction_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.auction_text = scrolledtext.ScrolledText(auction_frame, height=12, font=("Courier", 10))
        self.auction_text.pack(fill="both", expand=True)
        
        # Current State Frame
        state_frame = ttk.LabelFrame(self.root, text="Current Auction State", padding=10)
        state_frame.pack(fill="x", padx=10, pady=5)
        
        self.item_var = tk.StringVar(value="--")
        self.price_var = tk.StringVar(value="$0.00")
        self.highest_var = tk.StringVar(value="--")
        self.time_var = tk.StringVar(value="--")
        
        ttk.Label(state_frame, text="Item:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(state_frame, textvariable=self.item_var, font=("Arial", 10)).grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(state_frame, text="Price:", font=("Arial", 12, "bold")).grid(row=1, column=0, sticky="w", padx=5)
        ttk.Label(state_frame, textvariable=self.price_var, font=("Arial", 14, "bold"), foreground="green").grid(row=1, column=1, sticky="w", padx=5)
        
        ttk.Label(state_frame, text="Highest Bidder:", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w", padx=5)
        ttk.Label(state_frame, textvariable=self.highest_var, font=("Arial", 10)).grid(row=2, column=1, sticky="w", padx=5)
        
        ttk.Label(state_frame, text="Time Left:", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky="w", padx=5)
        ttk.Label(state_frame, textvariable=self.time_var, font=("Arial", 10)).grid(row=3, column=1, sticky="w", padx=5)
        
        # Bid Controls
        bid_frame = ttk.LabelFrame(self.root, text="Place Your Bid", padding=10)
        bid_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(bid_frame, text="Bid Amount ($):", font=("Arial", 11)).pack(side="left", padx=5)
        self.bid_entry = ttk.Entry(bid_frame, width=15, font=("Arial", 12))
        self.bid_entry.pack(side="left", padx=5)
        self.bid_entry.bind('<Return>', lambda e: self.place_bid())
        
        self.bid_button = ttk.Button(bid_frame, text="Place Bid", command=self.place_bid, width=12)
        self.bid_button.pack(side="left", padx=10)
        
        # Connection controls
        conn_frame = ttk.Frame(self.root)
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        self.reconnect_button = ttk.Button(conn_frame, text="Reconnect", command=self.reconnect, width=12)
        self.reconnect_button.pack(side="right", padx=5)
        
    def show_join_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Join Auction")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Enter your bidder name:", font=("Arial", 11)).pack(pady=20)
        
        name_entry = ttk.Entry(dialog, width=25, font=("Arial", 11))
        name_entry.pack(pady=10)
        name_entry.focus()
        
        def join():
            name = name_entry.get().strip()
            if name:
                self.bidder_name = name
                dialog.destroy()
                self.connect_to_server()
            else:
                messagebox.showwarning("Invalid Name", "Please enter a valid name")
        
        ttk.Button(dialog, text="Join Auction", command=join).pack(pady=10)
        
        # Bind Enter key
        name_entry.bind('<Return>', lambda e: join())
    
    def connect_to_server(self):
        server_ip = resolve("bidwave.server")
        if server_ip is None:
            messagebox.showerror("Error", "Could not resolve server address")
            return
        
        self.server_addr = (server_ip, SERVER_PORT)
        
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.client_socket.bind(('', 0))
            self.client_socket.settimeout(2.0)
            
            # Send JOIN
            join_payload = {"name": self.bidder_name}
            packet = self.pack_packet(0, TYPE_JOIN, 0x00, join_payload)
            self.client_socket.sendto(packet, self.server_addr)
            
            # Wait for response
            data, _ = self.client_socket.recvfrom(4096)
            seq, msg_type, flags, payload = self.unpack_packet(data)
            
            if msg_type == TYPE_ACK and flags == FLAG_ACCEPTED:
                self.connected = True
                self.auction_active = True
                
                self.status_label.config(text="● Connected", foreground="green")
                self.server_label.config(text=f"Server: {self.server_addr[0]}:{self.server_addr[1]}")
                self.name_label.config(text=f"Bidder: {self.bidder_name}")
                self.bid_button.config(state="normal")
                self.bid_entry.config(state="normal")
                
                self.log_message(f"✓ Successfully joined auction as {self.bidder_name}", "green")
                
                # Start receive thread
                recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
                recv_thread.start()
            else:
                messagebox.showerror("Error", f"Join failed: {payload}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {e}")
            self.connected = False
    
    def pack_packet(self, seq, msg_type, flags, payload_dict):
        payload = json.dumps(payload_dict).encode('utf-8')
        header = struct.pack(HEADER_FORMAT, seq, msg_type, flags)
        return header + payload
    
    def unpack_packet(self, data):
        if len(data) < HEADER_SIZE:
            return None, None, None, None
        try:
            seq, msg_type, flags = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
            payload = json.loads(data[HEADER_SIZE:].decode('utf-8'))
            return seq, msg_type, flags, payload
        except Exception:
            return None, None, None, None
    
    def log_message(self, message, color="black"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.auction_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.auction_text.see(tk.END)
    
    def display_update(self, payload):
        item = payload.get("item", "Unknown")
        price = payload.get("price", 0)
        highest_bidder = payload.get("highest_bidder", "None")
        time_remaining = payload.get("time_remaining", 0)
        
        # Update display
        self.item_var.set(item)
        self.price_var.set(f"${price:.2f}")
        self.highest_var.set(highest_bidder)
        self.time_var.set(f"{time_remaining}s")
        
        # Log to feed
        self.log_message(f"📢 UPDATE: {item} | ${price:.2f} | Highest: {highest_bidder} | Time: {time_remaining}s", "blue")
    
    def place_bid(self):
        if not self.connected or not self.auction_active:
            messagebox.showwarning("Not Connected", "You are not connected to the auction")
            return
        
        try:
            amount = float(self.bid_entry.get().strip())
            if amount <= 0:
                messagebox.showwarning("Invalid Bid", "Bid amount must be positive")
                return
            
            self.bid_entry.delete(0, tk.END)
            self.send_bid(amount)
            
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid number")
    
    def send_bid(self, amount):
        with self.seq_lock:
            seq = self.seq_counter
            self.seq_counter += 1
        
        bid_payload = {"name": self.bidder_name, "amount": amount}
        packet = self.pack_packet(seq, TYPE_BID, 0x00, bid_payload)
        
        for attempt in range(self.MAX_RETRIES):
            self.log_message(f"💵 Sending bid ${amount:.2f} (seq={seq}, attempt={attempt+1})", "orange")
            self.client_socket.sendto(packet, self.server_addr)
            
            try:
                self.client_socket.settimeout(self.BID_TIMEOUT)
                data, _ = self.client_socket.recvfrom(4096)
                resp_seq, msg_type, flags, payload = self.unpack_packet(data)
                
                if msg_type == TYPE_ACK:
                    if flags == FLAG_ACCEPTED:
                        self.log_message(f"✅ Bid accepted! ${amount:.2f} is now the highest bid!", "green")
                        return True
                    elif flags == FLAG_REJECTED:
                        reason = payload.get('reason', 'Bid too low')
                        self.log_message(f"❌ Bid rejected: {reason}", "red")
                        return False
                        
            except socket.timeout:
                self.log_message(f"⏰ Timeout waiting for ACK (attempt {attempt+1})", "orange")
                if attempt == self.MAX_RETRIES - 1:
                    self.log_message("❌ Max retries reached. Bid may not have been received.", "red")
                    return False
                continue
            except Exception as e:
                self.log_message(f"Error: {e}", "red")
                return False
            finally:
                self.client_socket.settimeout(None)
        
        return False
    
    def receive_loop(self):
        while self.connected and self.auction_active:
            try:
                self.client_socket.settimeout(0.5)
                data, _ = self.client_socket.recvfrom(4096)
                seq, msg_type, flags, payload = self.unpack_packet(data)
                
                if msg_type == TYPE_UPDATE:
                    self.display_update(payload)
                elif msg_type == TYPE_WIN:
                    self.log_message("\n" + "🎉"*20, "purple")
                    self.log_message(payload.get("message", "YOU WON THE AUCTION!"), "purple")
                    self.log_message("🎉"*20 + "\n", "purple")
                    self.auction_active = False
                    self.bid_button.config(state="disabled")
                    self.bid_entry.config(state="disabled")
                    break
                elif msg_type == TYPE_CLOSE:
                    self.log_message("\n" + "="*40, "orange")
                    self.log_message("AUCTION HAS ENDED", "orange")
                    self.log_message(payload.get("message", "Thanks for participating!"), "orange")
                    self.log_message("="*40 + "\n", "orange")
                    self.auction_active = False
                    self.bid_button.config(state="disabled")
                    self.bid_entry.config(state="disabled")
                    break
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.connected:
                    self.log_message(f"Error in receive loop: {e}", "red")
                break
    
    def reconnect(self):
        if self.client_socket:
            self.client_socket.close()
        
        self.connected = False
        self.auction_active = True
        self.status_label.config(text="● Disconnected", foreground="red")
        self.bid_button.config(state="disabled")
        self.bid_entry.config(state="disabled")
        
        self.show_join_dialog()


if __name__ == '__main__':
    root = tk.Tk()
    app = AuctionClientGUI(root)
    root.mainloop()