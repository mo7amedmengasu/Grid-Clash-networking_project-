"""
GSync v2 - Grid Clash Client (Phase 2)
UDP client with K=3 redundancy parsing, metrics logging, and PyGame UI.
"""

import argparse
import binascii
import csv
import os
import socket
import struct
import threading
import time
from datetime import datetime

import pygame

# Protocol constants
HEADER_STRUCT = struct.Struct("!4s B B I I Q H I")  # 28-byte binary header
PROTO_ID = b"GSYN"
VERSION = 1

# Message types
MSG_SNAPSHOT = 0
MSG_EVENT = 1
MSG_ACK = 2
MSG_INIT = 3
MSG_GAME_OVER = 4

# UI constants
GRID_N = 10
CELL_SIZE = 40
MARGIN = 4


def now_ms():
    """Get current timestamp in milliseconds"""
    return int(time.time() * 1000)


class GameClient:
    def __init__(self, server_host="127.0.0.1", server_port=10000, player_id=1,
                 test_scenario="baseline", smoothing_factor=0.3):
        # Network setup
        self.server_addr = (server_host, server_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 0))  # Bind to any available port

        # Client identity and configuration
        self.player_id = player_id
        self.test_scenario = test_scenario  # For CSV logging
        self.smoothing_factor = smoothing_factor  # For position error calculation
        self.running = True

        # Game state
        self.grid = [0] * (GRID_N * GRID_N)  # Local copy of grid
        self.game_over = False
        self.winner_id = 0
        self.final_scores = {}

        # Thread safety
        self.lock = threading.Lock()

        # Metrics tracking
        self.metrics = {
            "total_packets_received": 0,
            "duplicate_packets": 0,
            "lost_sequences": 0,
            "last_seq_num": -1,
            "last_recv_time": None,
            "last_latency": None,
        }

        # Create logs directory
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # CSV Logging: Snapshot metrics (latency, jitter, etc.)
        self.snap_csv = open(
            f"logs/client{player_id}_snapshots_{test_scenario}_{timestamp}.csv",
            "w", newline=""
        )
        self.snap_writer = csv.writer(self.snap_csv)
        self.snap_writer.writerow([
            "recv_time_ms", "snapshot_id", "seq_num", "server_ts_ms",
            "latency_ms", "jitter_ms", "redundancy_used", "scenario"
        ])

        # CSV Logging: Position error (for Grid Clash, this is mostly 0)
        self.error_csv = open(
            f"logs/client{player_id}_position_error_{test_scenario}_{timestamp}.csv",
            "w", newline=""
        )
        self.error_writer = csv.writer(self.error_csv)
        self.error_writer.writerow([
            "timestamp_ms", "smoothing_factor", "estimated_error", "scenario"
        ])

        # CSV Logging: Diagnostics (aggregate stats)
        self.diag_csv = open(
            f"logs/client{player_id}_diagnostics_{test_scenario}_{timestamp}.csv",
            "w", newline=""
        )
        self.diag_writer = csv.writer(self.diag_csv)
        self.diag_writer.writerow([
            "timestamp_ms", "packets_received", "duplicate_rate",
            "sequence_gaps", "scenario"
        ])

        # Start background threads
        threading.Thread(target=self.recv_loop, daemon=True).start()
        threading.Thread(target=self.metrics_logging_loop, daemon=True).start()

        # Send INIT message to register with server
        self.send_init()
        print(f"[CLIENT {player_id}] Connected to {server_host}:{server_port}")
        print(f"[CLIENT {player_id}] Scenario: {test_scenario}")

    def send_init(self):
        """Send INIT message to register with server"""
        payload = struct.pack("!B", self.player_id)
        ts = now_ms()
        
        # Build header with checksum
        header_zero = HEADER_STRUCT.pack(
            PROTO_ID, VERSION, MSG_INIT, 0, 0, ts, len(payload), 0
        )
        crc = binascii.crc32(header_zero + payload) & 0xFFFFFFFF
        header = HEADER_STRUCT.pack(
            PROTO_ID, VERSION, MSG_INIT, 0, 0, ts, len(payload), crc
        )
        
        self.sock.sendto(header + payload, self.server_addr)

    def send_event_acquire(self, cell_id):
        """Send cell acquisition request (with double-send for reliability)"""
        if self.game_over:
            return
            
        client_ts = now_ms()
        
        # Build EVENT payload: player_id + event_type + cell_id + timestamp
        payload = struct.pack("!B B H Q", self.player_id, 0, cell_id, client_ts)
        
        # Build header with checksum
        header_zero = HEADER_STRUCT.pack(
            PROTO_ID, VERSION, MSG_EVENT, 0, 0, client_ts, len(payload), 0
        )
        crc = binascii.crc32(header_zero + payload) & 0xFFFFFFFF
        header = HEADER_STRUCT.pack(
            PROTO_ID, VERSION, MSG_EVENT, 0, 0, client_ts, len(payload), crc
        )
        packet = header + payload
        
        # Send twice for critical event reliability
        self.sock.sendto(packet, self.server_addr)
        time.sleep(0.001)  # 1ms spacing
        self.sock.sendto(packet, self.server_addr)

    def recv_loop(self):
        """Receive and process messages from server"""
        while self.running:
            try:
                data, _ = self.sock.recvfrom(8192)
                if len(data) < HEADER_STRUCT.size:
                    continue

                # Parse header
                header = data[:HEADER_STRUCT.size]
                (proto_id, version, msg_type, snapshot_id, seq_num,
                 server_ts, payload_len, checksum) = HEADER_STRUCT.unpack(header)

                # Validate protocol
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

                recv_time = now_ms()

                # Route message to appropriate handler
                if msg_type == MSG_SNAPSHOT:
                    self.handle_snapshot(payload, snapshot_id, seq_num, server_ts, recv_time)
                elif msg_type == MSG_GAME_OVER:
                    self.handle_game_over(payload)

            except Exception as e:
                if self.running:
                    print(f"[CLIENT {self.player_id}] recv error:", e)

    def handle_snapshot(self, payload, snapshot_id, seq_num, server_ts, recv_time):
        """Process SNAPSHOT message: parse K=3 redundancy and log metrics"""
        # Calculate latency
        latency = recv_time - server_ts

        # Calculate latency jitter
        jitter = 0
        if self.metrics["last_latency"] is not None:
            jitter = abs(latency - self.metrics["last_latency"])
        self.metrics["last_latency"] = latency

        # Calculate inter-arrival jitter
        inter_arrival_jitter = 0
        if self.metrics["last_recv_time"] is not None:
            expected_interval = 50  # 20 Hz = 50ms
            inter_arrival_jitter = abs(
                (recv_time - self.metrics["last_recv_time"]) - expected_interval
            )
        self.metrics["last_recv_time"] = recv_time

        # Update packet metrics
        self.metrics["total_packets_received"] += 1
        
        # Detect duplicates
        if seq_num <= self.metrics["last_seq_num"]:
            self.metrics["duplicate_packets"] += 1
            
        # Detect sequence gaps (lost packets)
        if self.metrics["last_seq_num"] != -1 and seq_num > self.metrics["last_seq_num"] + 1:
            self.metrics["lost_sequences"] += (seq_num - self.metrics["last_seq_num"] - 1)
        self.metrics["last_seq_num"] = seq_num

        # Parse K=3 redundant snapshots
        ptr = 0
        redundancy_used = 0
        updated = False

        while ptr + 1 <= len(payload):
            grid_n = payload[ptr]
            ptr += 1
            if grid_n != GRID_N:
                break

            needed = GRID_N * GRID_N
            if ptr + needed > len(payload):
                break

            chunk = payload[ptr:ptr + needed]
            ptr += needed

            # Apply first (newest) snapshot only
            if not updated:
                with self.lock:
                    self.grid = list(chunk)
                updated = True
            else:
                redundancy_used += 1  # Count redundant snapshots

        # Log snapshot metrics to CSV
        self.snap_writer.writerow([
            recv_time, snapshot_id, seq_num, server_ts,
            latency, inter_arrival_jitter, redundancy_used, self.test_scenario
        ])
        self.snap_csv.flush()

    def handle_game_over(self, payload):
        """Process GAME_OVER message: extract winner and scores"""
        if len(payload) < 2:
            return
            
        winner_id = payload[0]
        num_players = payload[1]
        
        # Parse scores
        scores = {}
        for i in range(num_players):
            idx = 2 + i * 2
            if idx + 2 <= len(payload):
                pid = payload[idx]
                score = payload[idx + 1]
                scores[pid] = score

        # Update game state
        with self.lock:
            self.game_over = True
            self.winner_id = winner_id
            self.final_scores = scores

    def metrics_logging_loop(self):
        """Periodically log aggregate metrics to CSV"""
        while self.running:
            time.sleep(2.0)  # Log every 2 seconds
            
            with self.lock:
                ts = now_ms()
                
                # Calculate duplicate rate
                dup_rate = 0.0
                if self.metrics["total_packets_received"] > 0:
                    dup_rate = (self.metrics["duplicate_packets"] /
                               self.metrics["total_packets_received"])
                
                # Write diagnostics to CSV
                self.diag_writer.writerow([
                    ts, self.metrics["total_packets_received"],
                    dup_rate, self.metrics["lost_sequences"], self.test_scenario
                ])
                self.diag_csv.flush()

    def close(self):
        """Cleanup: close socket and CSV files, print summary"""
        self.running = False
        try:
            self.sock.close()
            self.snap_csv.close()
            self.error_csv.close()
            self.diag_csv.close()

            # Print summary statistics
            print(f"\n[CLIENT {self.player_id}] Summary:")
            print(f" Packets received: {self.metrics['total_packets_received']}")
            if self.metrics["total_packets_received"] > 0:
                dup_rate = (self.metrics["duplicate_packets"] /
                           self.metrics["total_packets_received"])
                print(f" Duplicate rate: {dup_rate:.2%}")
                print(f" Sequence gaps: {self.metrics['lost_sequences']}")
        except Exception:
            pass


def run_pygame(client):
    """Run PyGame UI for Grid Clash"""
    pygame.init()

    # Calculate window size
    grid_pix = GRID_N * CELL_SIZE + (GRID_N + 1) * MARGIN
    win = pygame.display.set_mode((grid_pix, grid_pix))
    pygame.display.set_caption(f"Grid Clash - Player {client.player_id}")

    # Setup rendering
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 20)
    title_font = pygame.font.SysFont(None, 50, bold=True)
    score_font = pygame.font.SysFont(None, 35)
    detail_font = pygame.font.SysFont(None, 32)

    # Color mapping for players (0=gray, 1-8=unique colors)
    colors = {
        0: (200, 200, 200), 1: (255, 100, 100), 2: (100, 255, 100),
        3: (100, 100, 255), 4: (255, 255, 100), 5: (255, 100, 255),
        6: (100, 255, 255), 7: (255, 200, 100), 8: (200, 100, 255),
    }

    running = True
    while running:
        # Handle events
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                # Left click: try to acquire cell
                mx, my = pygame.mouse.get_pos()
                col = (mx - MARGIN) // (CELL_SIZE + MARGIN)
                row = (my - MARGIN) // (CELL_SIZE + MARGIN)
                
                if 0 <= col < GRID_N and 0 <= row < GRID_N:
                    cell_id = row * GRID_N + col
                    with client.lock:
                        if client.grid[cell_id] == 0 and not client.game_over:
                            client.send_event_acquire(cell_id)

        # Clear screen
        win.fill((30, 30, 30))

        # Get thread-safe copy of game state
        with client.lock:
            grid_copy = client.grid.copy()
            game_over = client.game_over
            winner_id = client.winner_id
            final_scores = dict(client.final_scores)

        # Draw grid cells
        for r in range(GRID_N):
            for c in range(GRID_N):
                cell_id = r * GRID_N + c
                owner = grid_copy[cell_id]
                color = colors.get(owner, (180, 180, 180))
                
                x = MARGIN + c * (CELL_SIZE + MARGIN)
                y = MARGIN + r * (CELL_SIZE + MARGIN)
                
                pygame.draw.rect(win, color, (x, y, CELL_SIZE, CELL_SIZE))
                
                # Draw player ID if cell is claimed
                if owner:
                    txt = font.render(str(owner), True, (0, 0, 0))
                    win.blit(txt, (x + 4, y + 4))

        # Draw game over overlay
        if game_over and winner_id > 0:
            # Semi-transparent overlay
            overlay = pygame.Surface((grid_pix, grid_pix))
            overlay.set_alpha(240)
            overlay.fill((0, 0, 0))
            win.blit(overlay, (0, 0))

            # Title
            title = title_font.render("GAME OVER!", True, (255, 215, 0))
            win.blit(title, title.get_rect(center=(grid_pix // 2, 80)))

            # Winner announcement
            winner_font = pygame.font.SysFont(None, 55, bold=True)
            winner_txt = winner_font.render(
                f"Player {winner_id} Wins!", True, (0, 255, 0)
            )
            winner_rect = winner_txt.get_rect(center=(grid_pix // 2, 150))
            
            # Draw box behind winner text
            box_rect = winner_rect.inflate(30, 20)
            pygame.draw.rect(win, (0, 80, 0), box_rect, border_radius=10)
            pygame.draw.rect(win, (0, 255, 0), box_rect, 3, border_radius=10)
            win.blit(winner_txt, winner_rect)

            # Final scores label
            score_label = score_font.render("Final Scores:", True, (220, 220, 220))
            win.blit(score_label, score_label.get_rect(center=(grid_pix // 2, 220)))

            # List all player scores (sorted by score)
            score_y = 270
            if final_scores:
                for pid, score in sorted(final_scores.items(), key=lambda x: x[1], reverse=True):
                    # Highlight winner in green
                    color = (100, 255, 100) if pid == winner_id else (200, 200, 200)
                    text = detail_font.render(f"Player {pid}: {score} cells", True, color)
                    win.blit(text, text.get_rect(center=(grid_pix // 2, score_y)))
                    score_y += 40

        # Update display
        pygame.display.flip()
        clock.tick(60)  # 60 FPS

    # Cleanup
    client.close()
    pygame.quit()


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="GSync v2 Grid Clash Client")
    parser.add_argument("--server_host", default="127.0.0.1")
    parser.add_argument("--server_port", type=int, default=10000)
    parser.add_argument("--player_id", type=int, required=True)
    parser.add_argument("--scenario", default="baseline",
                       choices=["baseline", "loss2", "loss5", "delay100"])
    parser.add_argument("--smoothing", type=float, default=0.3)
    args = parser.parse_args()

    # Create client
    client = GameClient(
        server_host=args.server_host,
        server_port=args.server_port,
        player_id=args.player_id,
        test_scenario=args.scenario,
        smoothing_factor=args.smoothing
    )

    # Run game
    try:
        run_pygame(client)
    except KeyboardInterrupt:
        client.close()
    except Exception as e:
        print(f"\n[CLIENT {args.player_id}] Error: {e}")
        client.close()
