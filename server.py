
"""
GSync v1 - Grid Clash Server (Phase 1/2)
- UDP server implementing header + snapshot redundancy.
- Resolves ACQUIRE_REQUEST events by first-come-first-served (arrival order).
- Broadcasts snapshots at configured Hz.
- Logs snapshots and events to CSV.
"""
import socket, struct, threading, time, binascii, argparse, csv
from collections import deque

# Header: 4s B B I I Q H I = 28 bytes
HEADER_STRUCT = struct.Struct('!4s B B I I Q H I')
PROTO_ID = b'GSYN'
VERSION = 1

MSG_SNAPSHOT = 0
MSG_EVENT = 1
MSG_ACK = 2
MSG_INIT = 3

GRID_N = 10  # 10x10 grid
DEFAULT_RATE_HZ = 10

def now_ms():
    return int(time.time() * 1000)

class GridServer:
    def __init__(self, host='127.0.0.1', port=10000, rate_hz=DEFAULT_RATE_HZ):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(self.addr)
        self.clients = set()  # (ip,port)
        self.running = True
        self.rate_hz = rate_hz
        self.snapshot_id = 0
        self.seq_num = 0
        self.lock = threading.Lock()
        # grid: list of owner ids (0=unclaimed, else player_id)
        self.grid = [0] * (GRID_N * GRID_N)
        # event queue (for logging)
        self.event_log = []
        # snapshot history (for redundancy). store bytes payloads
        self.snapshot_history = deque(maxlen=3)
        # csv logs
        self.snap_csv = open('server_snapshots.csv', 'w', newline='')
        self.snap_writer = csv.writer(self.snap_csv)
        self.snap_writer.writerow(['send_time_ms','snapshot_id','seq_num','clients_count'])
        self.event_csv = open('server_events.csv', 'w', newline='')
        self.event_writer = csv.writer(self.event_csv)
        self.event_writer.writerow(['recv_time_ms','from','player_id','event_type','cell_id','client_ts','accepted'])

    def start(self):
        print(f"[SERVER] bind {self.addr}, rate {self.rate_hz} Hz")
        t_recv = threading.Thread(target=self.recv_loop, daemon=True)
        t_bcast = threading.Thread(target=self.broadcast_loop, daemon=True)
        t_recv.start()
        t_bcast.start()
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("[SERVER] shutdown")
            self.running = False
            self.snap_csv.close()
            self.event_csv.close()

    def recv_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                if len(data) < HEADER_STRUCT.size:
                    continue
                header = data[:HEADER_STRUCT.size]
                (proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, checksum) = HEADER_STRUCT.unpack(header)
                payload = data[HEADER_STRUCT.size:HEADER_STRUCT.size+payload_len]
                # validate proto id
                if proto_id != PROTO_ID:
                    continue
                # validate CRC
                header_zero = HEADER_STRUCT.pack(proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, 0)
                calc = binascii.crc32(header_zero + payload) & 0xffffffff
                if calc != checksum:
                    print("[SERVER] CRC mismatch from", addr)
                    continue
                if msg_type == MSG_INIT:
                    with self.lock:
                        self.clients.add(addr)
                    print(f"[SERVER] INIT from {addr}, clients={len(self.clients)}")
                elif msg_type == MSG_EVENT:
                    # parse event: player_id (1), event_type(1), cell_id(2), client_ts(8)
                    if len(payload) >= 12:
                        player_id = payload[0]
                        event_type = payload[1]
                        cell_id = struct.unpack('!H', payload[2:4])[0]
                        client_ts = struct.unpack('!Q', payload[4:12])[0]
                        recv_time = now_ms()
                        accepted = False
                        with self.lock:
                            if 0 <= cell_id < GRID_N*GRID_N:
                                if self.grid[cell_id] == 0:
                                    # accept
                                    self.grid[cell_id] = player_id
                                    accepted = True
                                else:
                                    accepted = False
                        self.event_writer.writerow([recv_time, f"{addr}", player_id, event_type, cell_id, client_ts, int(accepted)])
                        self.event_csv.flush()
                        print(f"[SERVER] EVENT from {addr} player {player_id} cell {cell_id} accepted={accepted}")
                    else:
                        print("[SERVER] malformed EVENT")
                else:
                    # ignore other types
                    pass
            except Exception as e:
                if self.running:
                    print("[SERVER] recv error:", e)

    def build_snapshot_payload(self):
        # payload: grid_n (1 byte) + grid owners (N*N bytes)
        payload = struct.pack('!B', GRID_N)
        payload += bytes(self.grid)  # each owner fits in one byte
        return payload

    def broadcast_loop(self):
        interval = 1.0 / self.rate_hz
        while self.running:
            t0 = time.time()
            payload = self.build_snapshot_payload()
            # store for redundancy
            with self.lock:
                self.snapshot_history.appendleft(payload)
                # build redundancy payload: concatenate up to 3 snapshots
                combined = b''
                for pl in list(self.snapshot_history):
                    combined += pl
            # build header
            proto_id = PROTO_ID
            version = VERSION
            msg_type = MSG_SNAPSHOT
            snapshot_id = self.snapshot_id
            seq_num = self.seq_num
            server_ts = now_ms()
            payload_len = len(combined)
            header_zero = HEADER_STRUCT.pack(proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, 0)
            crc = binascii.crc32(header_zero + combined) & 0xffffffff
            header = HEADER_STRUCT.pack(proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, crc)
            packet = header + combined
            with self.lock:
                clients = list(self.clients)
            for c in clients:
                try:
                    self.sock.sendto(packet, c)
                except Exception as e:
                    print("[SERVER] send to", c, "error", e)
            # log
            self.snap_writer.writerow([server_ts, snapshot_id, seq_num, len(clients)])
            self.snap_csv.flush()
            # advance counters
            self.snapshot_id += 1
            self.seq_num += 1
            # sleep to maintain rate
            elapsed = time.time() - t0
            to_sleep = interval - elapsed
            if to_sleep > 0:
                time.sleep(to_sleep)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=10000)
    p.add_argument('--rate', type=int, default=DEFAULT_RATE_HZ)
    args = p.parse_args()
    srv = GridServer(host=args.host, port=args.port, rate_hz=args.rate)
    srv.start()
