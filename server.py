"""
GSync v2 - Grid Clash Server (Phase 2)
UDP server with redundancy (K=3), CRC32, and metrics logging.
"""

import argparse ,binascii ,csv ,socket ,struct ,threading ,time
import psutil
from collections import deque

# Protocol constants
HEADER_STRUCT = struct.Struct("!4s B B I I Q H I")  # 28-byte binary header
PROTO_ID = b"GSYN"
VERSION = 2

# Message types
MSG_SNAPSHOT = 0
MSG_EVENT = 1
MSG_ACK = 2
MSG_INIT = 3
MSG_GAME_OVER = 4

# Game constants
GRID_N = 10  # 10x10 grid = 100 cells
DEFAULT_RATE_HZ = 20  # 20 updates per second


def now_ms():
    """Get current timestamp in milliseconds"""
    return int(time.time() * 1000)


class GridServer:
    def __init__(self, host="127.0.0.1", port=10000, rate_hz=DEFAULT_RATE_HZ):
        # Network setup
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # IPv4 , UDP
        self.sock.bind(self.addr)

        # Server state
        self.clients = set()  # Set of (host, port) tuples
        self.running = True
        self.rate_hz = rate_hz
        self.snapshot_id = 0  # Incremental snapshot counter
        self.seq_num = 0  # Packet sequence number

        # Thread safety
        self.lock = threading.Lock()
        
        # Game state: 100 cells, 0=unclaimed, 1-8=player_id
        self.grid = [0] * (GRID_N * GRID_N)
        
        # K=3 redundancy: Keep last 3 snapshots
        self.snapshot_history = deque(maxlen=3)

        # CPU monitoring
        self.process = psutil.Process()

        # CSV Logging: Snapshot metrics
        self.snap_csv = open("server_snapshots.csv", "w", newline="")
        self.snap_writer = csv.writer(self.snap_csv)
        self.snap_writer.writerow([
            "send_time_ms", "snapshot_id", "seq_num", "clients_count",
            "cpu_percent", "payload_bytes"
        ])

        # CSV Logging: Event log (player actions)
        self.event_csv = open("server_events.csv", "w", newline="")
        self.event_writer = csv.writer(self.event_csv)
        self.event_writer.writerow([
            "recv_time_ms", "from", "player_id", "event_type",
            "cell_id", "client_ts", "accepted"
        ])

        # CSV Logging: Authoritative grid state (for position error analysis)
        self.pos_csv = open("server_authoritative_grid.csv", "w", newline="")
        self.pos_writer = csv.writer(self.pos_csv)
        self.pos_writer.writerow(["send_time_ms", "snapshot_id", "grid_state"])

    def start(self):
        """Start server: spawn threads and run until interrupted"""
        print(f"[SERVER] bind {self.addr}, rate {self.rate_hz} Hz")

        # Start receiver thread (handles INIT and EVENT messages)
        threading.Thread(target=self.recv_loop, daemon=True).start()
        
        # Start broadcast thread (sends SNAPSHOT messages at 20 Hz)
        threading.Thread(target=self.broadcast_loop, daemon=True).start()

        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("[SERVER] shutdown")
        finally:
            self.running = False
            self.snap_csv.close()
            self.event_csv.close()
            self.pos_csv.close()

    def recv_loop(self):
        """Receive and process INIT and EVENT messages from clients"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1200)
                if len(data) < HEADER_STRUCT.size:
                    continue

                # Parse header (28 bytes)
                header = data[:HEADER_STRUCT.size]
                (proto_id, version, msg_type, snapshot_id, seq_num,
                 server_ts, payload_len, checksum) = HEADER_STRUCT.unpack(header)

                # Validate protocol ID and version
                if proto_id != PROTO_ID or version != VERSION:
                    continue

                # Extract payload
                payload = data[HEADER_STRUCT.size:HEADER_STRUCT.size + payload_len]

                # Validate CRC32 checksum
                header_zero = HEADER_STRUCT.pack(
                    proto_id, version, msg_type, snapshot_id,
                    seq_num, server_ts, payload_len, 0
                )
                calc = binascii.crc32(header_zero + payload) & 0xFFFFFFFF
                if calc != checksum:
                    continue

                # Handle INIT: Client registration
                if msg_type == MSG_INIT:
                    with self.lock:
                        self.clients.add(addr)
                        print(f"[SERVER] INIT from {addr}, clients={len(self.clients)}")

                # Handle EVENT: Cell acquisition request
                elif msg_type == MSG_EVENT and len(payload) >= 12:
                    player_id = payload[0]
                    event_type = payload[1]
                    cell_id = struct.unpack("!H", payload[2:4])[0]
                    client_ts = struct.unpack("!Q", payload[4:12])[0]
                    recv_time = now_ms()
                    accepted = 0

                    # Check if cell is valid and unclaimed
                    with self.lock:
                        if 0 <= cell_id < GRID_N * GRID_N and self.grid[cell_id] == 0:
                            self.grid[cell_id] = player_id
                            accepted = 1

                    # Log event to CSV
                    self.event_writer.writerow([
                        recv_time, f"{addr}", player_id, event_type,
                        cell_id, client_ts, accepted
                    ])
                    self.event_csv.flush()

            except Exception as e:
                if self.running:
                    print("[SERVER] recv error:", e)

    def build_snapshot_payload(self):
        """Build snapshot payload: grid_n (1 byte) + grid state (100 bytes)"""
        return struct.pack("!B", GRID_N) + bytes(self.grid)

    def compute_game_over_payload(self):
        """Check if game is over and compute winner payload"""
        # Game continues if any cell is unclaimed
        if 0 in self.grid:
            return False, b""

        # Count cells per player
        scores = {}
        for owner in self.grid:
            if owner:
                scores[owner] = scores.get(owner, 0) + 1

        
        # Determine winner (player with most cells)
        winner_id = max(scores, key=scores.get)
        print(f"\n[SERVER] GAME OVER! Winner: Player {winner_id} ({scores[winner_id]} cells)")
        print(f"[SERVER] Final scores: {scores}\n")

        # Build GAME_OVER payload: winner_id + num_players + scores
        payload = struct.pack("!B B", winner_id, len(scores))
        for pid in sorted(scores):
            payload += struct.pack("!B B", pid, scores[pid])
        return True, payload

    def broadcast_loop(self):
        """Broadcast grid snapshots to all clients at configured rate"""
        interval = 1.0 / self.rate_hz  # 50ms for 20 Hz

        while self.running:
            t0 = time.time()
            
            # Build current snapshot
            payload = self.build_snapshot_payload()

            with self.lock:
                # Add to history (K=3 redundancy)
                self.snapshot_history.appendleft(payload)
                
                # Combine last 3 snapshots into one packet (303 bytes)
                combined = b"".join(self.snapshot_history)
                
                # Snapshot of current state
                clients = list(self.clients)
                grid_state = ",".join(map(str, self.grid))

            # Build packet header
            proto_id = PROTO_ID
            version = VERSION
            msg_type = MSG_SNAPSHOT
            snapshot_id = self.snapshot_id
            seq_num = self.seq_num
            server_ts = now_ms()
            payload_len = len(combined)

            # Compute CRC32 checksum
            header_zero = HEADER_STRUCT.pack(
                proto_id, version, msg_type, snapshot_id,
                seq_num, server_ts, payload_len, 0
            )
            crc = binascii.crc32(header_zero + combined) & 0xFFFFFFFF
            
            # Final header with checksum
            header = HEADER_STRUCT.pack(
                proto_id, version, msg_type, snapshot_id,
                seq_num, server_ts, payload_len, crc
            )
            packet = header + combined

            # Send to all clients
            for c in clients:
                try:
                    self.sock.sendto(packet, c)
                except Exception as e:
                    print("[SERVER] send error to", c, e)

            # Log snapshot metrics
            cpu_percent = self.process.cpu_percent(interval=None)
            self.snap_writer.writerow([
                server_ts, snapshot_id, seq_num, len(clients),
                cpu_percent, payload_len
            ])
            self.snap_csv.flush()

            # Log authoritative grid state
            self.pos_writer.writerow([server_ts, snapshot_id, grid_state])
            self.pos_csv.flush()

            # Increment counters
            self.snapshot_id += 1
            self.seq_num += 1

            # Check if game is over
            is_full, game_over_payload = self.compute_game_over_payload()
            if is_full:
                # Build GAME_OVER packet
                msg_type = MSG_GAME_OVER
                payload_len = len(game_over_payload)
                
                header_zero = HEADER_STRUCT.pack(
                    proto_id, version, msg_type, snapshot_id,
                    seq_num, server_ts, payload_len, 0
                )
                crc = binascii.crc32(header_zero + game_over_payload) & 0xFFFFFFFF
                header = HEADER_STRUCT.pack(
                    proto_id, version, msg_type, snapshot_id,
                    seq_num, server_ts, payload_len, crc
                )
                packet = header + game_over_payload

                with self.lock:
                    clients = list(self.clients)

                # Send GAME_OVER twice for reliability
                for c in clients:
                    try:
                        self.sock.sendto(packet, c)
                        self.sock.sendto(packet, c)
                    except Exception as e:
                        print("[SERVER] send game_over error", e)

                # Stop server
                self.running = False

            # Maintain target rate (sleep remaining time)
            elapsed = time.time() - t0
            sleep_for = interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10000)
    parser.add_argument("--rate", type=int, default=DEFAULT_RATE_HZ)
    args = parser.parse_args()

    GridServer(host=args.host, port=args.port, rate_hz=args.rate).start()
