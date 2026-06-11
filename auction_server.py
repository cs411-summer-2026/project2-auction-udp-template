# gui_server.py - GUI Auction Server with Pause/Resume and SMTP Display
import socket
import struct
import threading
import json
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from config import (
    SERVER_PORT, SMTP_HOST, SMTP_PORT,
    HEADER_FORMAT, HEADER_SIZE,
    TYPE_JOIN, TYPE_UPDATE, TYPE_BID, TYPE_ACK, TYPE_WIN, TYPE_CLOSE,
    FLAG_ACCEPTED, FLAG_REJECTED
)


class AuctionServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("BidWave Auction Server")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        # Auction configuration
        self.auction_item = tk.StringVar(value="Vintage Camera")
        self.starting_price = tk.DoubleVar(value=50.0)
        self.auction_duration = tk.IntVar(value=120)
        
        # Auction state
        self.state = {
            "item": "Vintage Camera",
            "price": 50.0,
            "highest_bidder": None,
            "time_remaining": 120,
            "running": False,
        }
        self.state_lock = threading.Lock()
        self.clients = {}
        self.clients_lock = threading.Lock()
        self.seen_bids = {}
        self.bid_responses = {}
        self.server_socket = None
        self.running = False
        self.paused = False
        self.broadcast_thread = None
        self.receive_thread = None
        
        # Statistics
        self.total_bids = 0
        
        # SMTP messages log
        self.smtp_messages = []
        
        self.setup_ui()
        
    def setup_ui(self):
        # Menu Bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Start Server", command=self.start_server)
        file_menu.add_command(label="Pause Server", command=self.pause_server)
        file_menu.add_command(label="Resume Server", command=self.resume_server)
        file_menu.add_command(label="Stop Server", command=self.stop_server)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Configuration Frame
        config_frame = ttk.LabelFrame(self.root, text="Auction Configuration", padding=10)
        config_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(config_frame, text="Item:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Entry(config_frame, textvariable=self.auction_item, width=30).grid(row=0, column=1, padx=5)
        
        ttk.Label(config_frame, text="Starting Price ($):").grid(row=0, column=2, sticky="w", padx=5)
        ttk.Entry(config_frame, textvariable=self.starting_price, width=15).grid(row=0, column=3, padx=5)
        
        ttk.Label(config_frame, text="Duration (seconds):").grid(row=0, column=4, sticky="w", padx=5)
        ttk.Entry(config_frame, textvariable=self.auction_duration, width=10).grid(row=0, column=5, padx=5)
        
        ttk.Button(config_frame, text="Apply Config", command=self.apply_config).grid(row=0, column=6, padx=10)
        
        # Server Control Frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", padx=10, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="▶ Start Server", command=self.start_server, width=12)
        self.start_button.pack(side="left", padx=5)
        
        self.pause_button = ttk.Button(control_frame, text="⏸ Pause", command=self.pause_server, width=10, state="disabled")
        self.pause_button.pack(side="left", padx=5)
        
        self.resume_button = ttk.Button(control_frame, text="▶ Resume", command=self.resume_server, width=10, state="disabled")
        self.resume_button.pack(side="left", padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="■ Stop", command=self.stop_server, width=10, state="disabled")
        self.stop_button.pack(side="left", padx=5)
        
        self.status_label = ttk.Label(control_frame, text="● Stopped", foreground="red")
        self.status_label.pack(side="left", padx=20)
        
        self.pause_status_label = ttk.Label(control_frame, text="", foreground="orange")
        self.pause_status_label.pack(side="left", padx=10)
        
        # Stats Frame
        stats_frame = ttk.LabelFrame(self.root, text="Server Statistics", padding=10)
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        self.clients_label = ttk.Label(stats_frame, text="Connected Clients: 0")
        self.clients_label.pack(side="left", padx=20)
        
        self.bids_label = ttk.Label(stats_frame, text="Total Bids Received: 0")
        self.bids_label.pack(side="left", padx=20)
        
        # Auction State Frame
        auction_frame = ttk.LabelFrame(self.root, text="Current Auction State", padding=10)
        auction_frame.pack(fill="x", padx=10, pady=5)
        
        self.item_label = ttk.Label(auction_frame, text="Item: --", font=("Arial", 12, "bold"))
        self.item_label.pack(anchor="w", padx=10)
        
        self.price_label = ttk.Label(auction_frame, text="Current Price: $0.00", font=("Arial", 14, "bold"), foreground="green")
        self.price_label.pack(anchor="w", padx=10)
        
        self.highest_bidder_label = ttk.Label(auction_frame, text="Highest Bidder: --", font=("Arial", 11))
        self.highest_bidder_label.pack(anchor="w", padx=10)
        
        self.time_label = ttk.Label(auction_frame, text="Time Remaining: --s", font=("Arial", 11))
        self.time_label.pack(anchor="w", padx=10)
        
        self.progress = ttk.Progressbar(auction_frame, length=400, mode='determinate')
        self.progress.pack(anchor="w", padx=10, pady=5)
        
        # Create Notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Server Log Tab
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="Server Log")
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=90)
        self.log_text.pack(fill="both", expand=True)
        
        # SMTP Log Tab
        smtp_frame = ttk.Frame(notebook)
        notebook.add(smtp_frame, text="SMTP Notifications")
        
        self.smtp_text = scrolledtext.ScrolledText(smtp_frame, height=15, width=90)
        self.smtp_text.pack(fill="both", expand=True)
        
        # Configure tags for colored text
        self.log_text.tag_config("green", foreground="green")
        self.log_text.tag_config("red", foreground="red")
        self.log_text.tag_config("orange", foreground="orange")
        self.log_text.tag_config("blue", foreground="blue")
        self.log_text.tag_config("purple", foreground="purple")
        
        self.smtp_text.tag_config("green", foreground="green")
        self.smtp_text.tag_config("red", foreground="red")
        self.smtp_text.tag_config("blue", foreground="blue")
        
    def log(self, message, color="black"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", color)
        self.log_text.see(tk.END)
        
    def log_smtp(self, message, color="black"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.smtp_text.insert(tk.END, f"[{timestamp}] {message}\n", color)
        self.smtp_text.see(tk.END)
        self.smtp_messages.append(message)
        
    def apply_config(self):
        if not self.running:
            with self.state_lock:
                self.state["item"] = self.auction_item.get()
                self.state["price"] = self.starting_price.get()
                self.state["time_remaining"] = self.auction_duration.get()
            self.log(f"Configuration updated: {self.auction_item.get()} @ ${self.starting_price.get()} for {self.auction_duration.get()}s", "blue")
        else:
            messagebox.showwarning("Server Running", "Stop the server before changing configuration")
        
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
    
    def broadcast_update(self):
        while self.running and self.state["running"]:
            # Check if paused
            while self.paused and self.running:
                time.sleep(0.5)
                continue
                
            time.sleep(1)
            
            with self.clients_lock:
                if not self.clients:
                    continue
            
            with self.state_lock:
                if self.state["time_remaining"] > 0:
                    self.state["time_remaining"] -= 1
                
                update_payload = {
                    "item": self.state["item"],
                    "price": self.state["price"],
                    "highest_bidder": self.state["highest_bidder"] if self.state["highest_bidder"] else "None",
                    "time_remaining": self.state["time_remaining"]
                }
            
            # Update GUI
            self.root.after(0, self.update_auction_display)
            
            packet = self.pack_packet(0, TYPE_UPDATE, 0x00, update_payload)
            
            with self.clients_lock:
                for addr in list(self.clients.keys()):
                    try:
                        self.server_socket.sendto(packet, addr)
                    except:
                        pass
            
            if self.state["time_remaining"] <= 0:
                with self.state_lock:
                    self.state["running"] = False
                break
        
        if self.running:
            self.close_auction()
    
    def update_auction_display(self):
        with self.state_lock:
            self.item_label.config(text=f"Item: {self.state['item']}")
            self.price_label.config(text=f"Current Price: ${self.state['price']:.2f}")
            self.highest_bidder_label.config(text=f"Highest Bidder: {self.state['highest_bidder'] or 'None'}")
            self.time_label.config(text=f"Time Remaining: {self.state['time_remaining']}s")
            
            total_time = self.auction_duration.get()
            if total_time > 0:
                progress = (total_time - self.state["time_remaining"]) / total_time * 100
                self.progress['value'] = progress
    
    def handle_join(self, addr, seq, payload):
        client_name = payload.get("name", "Unknown")
        
        with self.clients_lock:
            self.clients[addr] = client_name
        
        self.log(f"✓ Client joined: {client_name} from port {addr[1]}", "green")
        self.root.after(0, lambda: self.clients_label.config(text=f"Connected Clients: {len(self.clients)}"))
        
        # Send ACK
        ack_payload = {"status": "joined", "name": client_name}
        packet = self.pack_packet(seq, TYPE_ACK, FLAG_ACCEPTED, ack_payload)
        self.server_socket.sendto(packet, addr)
        
        # Send immediate UPDATE
        with self.state_lock:
            update_payload = {
                "item": self.state["item"],
                "price": self.state["price"],
                "highest_bidder": self.state["highest_bidder"] if self.state["highest_bidder"] else "None",
                "time_remaining": self.state["time_remaining"]
            }
        update_packet = self.pack_packet(0, TYPE_UPDATE, 0x00, update_payload)
        self.server_socket.sendto(update_packet, addr)
    
    def handle_bid(self, addr, seq, payload):
        # Check for duplicate
        if addr in self.seen_bids and self.seen_bids[addr] == seq:
            if addr in self.bid_responses and seq in self.bid_responses[addr]:
                self.server_socket.sendto(self.bid_responses[addr][seq], addr)
                self.log(f"↻ Retransmit: resent ACK for seq={seq}", "orange")
            return
        
        bidder_name = payload.get("name", "Unknown")
        bid_amount = payload.get("amount", 0)
        
        self.total_bids += 1
        self.root.after(0, lambda: self.bids_label.config(text=f"Total Bids Received: {self.total_bids}"))
        
        with self.state_lock:
            current_price = self.state["price"]
            auction_running = self.state["running"]
        
        if auction_running and bid_amount > current_price:
            with self.state_lock:
                self.state["price"] = bid_amount
                self.state["highest_bidder"] = bidder_name
            
            self.log(f"💰 ACCEPTED: ${bid_amount:.2f} from {bidder_name}", "green")
            self.root.after(0, self.update_auction_display)
            
            ack_payload = {"status": "accepted", "price": bid_amount, "message": "Bid accepted!"}
            packet = self.pack_packet(seq, TYPE_ACK, FLAG_ACCEPTED, ack_payload)
            self.server_socket.sendto(packet, addr)
            
            if addr not in self.bid_responses:
                self.bid_responses[addr] = {}
            self.bid_responses[addr][seq] = packet
            self.seen_bids[addr] = seq
            
        else:
            reason = "Auction ended" if not auction_running else f"Must be > ${current_price:.2f}"
            self.log(f"❌ REJECTED: ${bid_amount:.2f} from {bidder_name} - {reason}", "red")
            
            ack_payload = {"status": "rejected", "reason": reason, "current_price": current_price}
            packet = self.pack_packet(seq, TYPE_ACK, FLAG_REJECTED, ack_payload)
            self.server_socket.sendto(packet, addr)
    
    def receive_loop(self):
        while self.running:
            try:
                self.server_socket.settimeout(0.5)
                data, addr = self.server_socket.recvfrom(4096)
                
                # Skip processing if paused but still receive to clear buffer
                if self.paused:
                    continue
                    
                seq, msg_type, flags, payload = self.unpack_packet(data)
                
                if msg_type == TYPE_JOIN:
                    self.handle_join(addr, seq, payload)
                elif msg_type == TYPE_BID:
                    self.handle_bid(addr, seq, payload)
                    
            except socket.timeout:
                continue
            except Exception as e:
                if "10054" not in str(e):
                    self.log(f"Error: {e}", "red")
                continue
    
    def close_auction(self):
        self.log("\n" + "="*50, "blue")
        self.log("AUCTION CLOSED", "blue")
        self.log(f"Winner: {self.state['highest_bidder'] or 'None'}", "blue")
        self.log(f"Final price: ${self.state['price']:.2f}", "blue")
        self.log("="*50 + "\n", "blue")
        
        # Send CLOSE to all
        close_payload = {"message": "Auction ended"}
        close_packet = self.pack_packet(0, TYPE_CLOSE, 0x00, close_payload)
        
        with self.clients_lock:
            for addr in self.clients.keys():
                try:
                    self.server_socket.sendto(close_packet, addr)
                except:
                    pass
        
        # Send WIN to winner and SMTP
        if self.state["highest_bidder"]:
            winner_addr = None
            with self.clients_lock:
                for addr, name in self.clients.items():
                    if name == self.state["highest_bidder"]:
                        winner_addr = addr
                        break
            
            if winner_addr:
                win_payload = {
                    "message": f"You won {self.state['item']} for ${self.state['price']:.2f}!",
                    "item": self.state["item"],
                    "price": self.state["price"]
                }
                win_packet = self.pack_packet(0, TYPE_WIN, 0x00, win_payload)
                self.server_socket.sendto(win_packet, winner_addr)
                self.log(f"🏆 Winner notification sent to {self.state['highest_bidder']}", "purple")
                
                # Send SMTP
                self.send_smtp_notification()
    
    def send_smtp_notification(self):
        """Send SMTP notification and log to SMTP tab"""
        winner_name = self.state['highest_bidder']
        item = self.state['item']
        final_price = self.state['price']
        
        self.log_smtp("="*50, "blue")
        self.log_smtp(f"Sending SMTP notification to {winner_name}", "blue")
        self.log_smtp("="*50, "blue")
        
        try:
            smtp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            smtp.connect((SMTP_HOST, SMTP_PORT))
            
            # Receive greeting
            greeting = smtp.recv(1024).decode('utf-8')
            self.log_smtp(f"✓ Received: {greeting.strip()}", "green")
            
            # Send EHLO
            smtp.send(b"EHLO bidwave.local\r\n")
            ehlo_response = smtp.recv(1024).decode('utf-8')
            self.log_smtp(f"✓ EHLO response: {ehlo_response.strip()}", "green")
            
            # Send MAIL FROM
            smtp.send(b"MAIL FROM:<auction@bidwave.local>\r\n")
            mail_response = smtp.recv(1024).decode('utf-8')
            self.log_smtp(f"✓ MAIL FROM accepted: {mail_response.strip()}", "green")
            
            # Send RCPT TO
            smtp.send(f"RCPT TO:<{winner_name}@bidwave.local>\r\n".encode())
            rcpt_response = smtp.recv(1024).decode('utf-8')
            self.log_smtp(f"✓ RCPT TO accepted: {rcpt_response.strip()}", "green")
            
            # Send DATA
            smtp.send(b"DATA\r\n")
            data_response = smtp.recv(1024).decode('utf-8')
            self.log_smtp(f"✓ DATA command accepted: {data_response.strip()}", "green")
            
            # Send email content
            email_content = f"""Subject: You won the auction!

From: BidWave Auction <auction@bidwave.local>
To: {winner_name} <{winner_name}@bidwave.local>

Congratulations {winner_name}!

You have won the auction for "{item}" with a winning bid of ${final_price:.2f}.

Thank you for participating in BidWave!

--
BidWave Auction System
CS411 - Computer Networks
"""
            smtp.send(email_content.encode())
            smtp.send(b"\r\n.\r\n")
            
            # Receive final response
            final_response = smtp.recv(1024).decode('utf-8')
            self.log_smtp(f"✓ Email accepted: {final_response.strip()}", "green")
            
            # Send QUIT
            smtp.send(b"QUIT\r\n")
            quit_response = smtp.recv(1024).decode('utf-8')
            self.log_smtp(f"✓ Connection closed: {quit_response.strip()}", "green")
            
            smtp.close()
            
            self.log_smtp("="*50, "blue")
            self.log_smtp(f"✅ SMTP notification sent successfully to {winner_name}!", "green")
            self.log_smtp(f"📧 Email content:", "blue")
            self.log_smtp(f"   To: {winner_name}@bidwave.local", "blue")
            self.log_smtp(f"   Subject: You won the auction!", "blue")
            self.log_smtp(f"   Message: Congratulations! You won {item} for ${final_price:.2f}", "blue")
            self.log_smtp("="*50 + "\n", "blue")
            
            self.log(f"📧 SMTP notification sent to {winner_name}", "purple")
            
        except Exception as e:
            error_msg = f"SMTP error: {e}"
            self.log_smtp(f"❌ {error_msg}", "red")
            self.log(error_msg, "red")
    
    def start_server(self):
        if self.running:
            messagebox.showinfo("Info", "Server is already running")
            return
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.bind(('', SERVER_PORT))
            
            self.running = True
            self.paused = False
            self.pause_status_label.config(text="")
            
            with self.state_lock:
                self.state["running"] = True
                self.state["price"] = self.starting_price.get()
                self.state["item"] = self.auction_item.get()
                self.state["time_remaining"] = self.auction_duration.get()
                self.state["highest_bidder"] = None
            
            # Reset stats
            self.total_bids = 0
            self.clients = {}
            self.seen_bids = {}
            self.bid_responses = {}
            self.root.after(0, lambda: self.clients_label.config(text="Connected Clients: 0"))
            self.root.after(0, lambda: self.bids_label.config(text=f"Total Bids Received: 0"))
            
            # Start threads
            self.receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.receive_thread.start()
            
            self.broadcast_thread = threading.Thread(target=self.broadcast_update, daemon=True)
            self.broadcast_thread.start()
            
            # Update UI
            self.start_button.config(state="disabled")
            self.pause_button.config(state="normal")
            self.resume_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.status_label.config(text="● Running", foreground="green")
            
            self.log(f"🚀 Server started on port {SERVER_PORT}", "green")
            self.log(f"📦 Auction: {self.state['item']} @ ${self.state['price']:.2f} for {self.state['time_remaining']}s", "blue")
            
        except Exception as e:
            self.log(f"Failed to start server: {e}", "red")
            messagebox.showerror("Error", f"Failed to start server: {e}")
    
    def pause_server(self):
        if not self.running:
            messagebox.showinfo("Info", "Server is not running")
            return
        
        if self.paused:
            messagebox.showinfo("Info", "Server is already paused")
            return
        
        self.paused = True
        self.pause_status_label.config(text="⏸ PAUSED", foreground="orange")
        self.pause_button.config(state="disabled")
        self.resume_button.config(state="normal")
        self.status_label.config(text="● Paused", foreground="orange")
        
        self.log("⏸ Server paused - auction timer stopped", "orange")
        self.log("   Clients will not receive updates until resumed", "orange")
    
    def resume_server(self):
        if not self.running:
            messagebox.showinfo("Info", "Server is not running")
            return
        
        if not self.paused:
            messagebox.showinfo("Info", "Server is not paused")
            return
        
        self.paused = False
        self.pause_status_label.config(text="")
        self.pause_button.config(state="normal")
        self.resume_button.config(state="disabled")
        self.status_label.config(text="● Running", foreground="green")
        
        self.log("▶ Server resumed - auction continuing", "green")
    
    def stop_server(self):
        if not self.running:
            return
        
        self.log("Stopping server...", "orange")
        self.running = False
        self.paused = False
        
        with self.state_lock:
            self.state["running"] = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Update UI
        self.start_button.config(state="normal")
        self.pause_button.config(state="disabled")
        self.resume_button.config(state="disabled")
        self.stop_button.config(state="disabled")
        self.status_label.config(text="● Stopped", foreground="red")
        self.pause_status_label.config(text="")
        
        self.log("Server stopped", "orange")
        self.log("Press 'Start Server' to begin a new auction", "blue")


if __name__ == '__main__':
    root = tk.Tk()
    app = AuctionServerGUI(root)
    root.mainloop()