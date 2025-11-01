
"""
GSync v1 - Grid Clash pygame Client
- Displays GRID_N x GRID_N cells
- Click an unclaimed cell to try to acquire it (sends EVENT twice)
- Receives SNAPSHOT packets and updates grid display
"""
import pygame, socket, struct, threading, time, binascii, argparse
from math import floor

# header struct must match server
HEADER_STRUCT = struct.Struct('!4s B B I I Q H I')
PROTO_ID = b'GSYN'
VERSION = 1

MSG_SNAPSHOT = 0
MSG_EVENT = 1
MSG_INIT = 3

GRID_N = 10
CELL_SIZE = 40
MARGIN = 4

def now_ms():
    return int(time.time() * 1000)

class GameClient:
    def __init__(self, server_host='127.0.0.1', server_port=10000, player_id=1, listen_port=0):
        self.server_addr = (server_host, server_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', listen_port))
        self.player_id = player_id
        self.running = True
        self.grid = [0] * (GRID_N * GRID_N)  # authoritative view from server
        self.lock = threading.Lock()
        # start recv thread
        t = threading.Thread(target=self.recv_loop, daemon=True)
        t.start()
        # send INIT
        self.send_init()

    def send_init(self):
        proto_id = PROTO_ID
        version = VERSION
        msg_type = MSG_INIT
        snapshot_id = 0
        seq_num = 0
        server_ts = now_ms()
        payload = struct.pack('!B', self.player_id)
        payload_len = len(payload)
        header_zero = HEADER_STRUCT.pack(proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, 0)
        crc = binascii.crc32(header_zero + payload) & 0xffffffff
        header = HEADER_STRUCT.pack(proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, crc)
        self.sock.sendto(header + payload, self.server_addr)
        print("[CLIENT] Sent INIT")

    def send_event_acquire(self, cell_id):
        # build payload: player_id(1), event_type(1), cell_id(2), client_ts(8)
        player_id = self.player_id
        event_type = 0  # ACQUIRE_REQUEST
        client_ts = now_ms()
        payload = struct.pack('!B B H Q', player_id, event_type, cell_id, client_ts)
        # pack header
        proto_id = PROTO_ID
        version = VERSION
        msg_type = MSG_EVENT
        snapshot_id = 0
        seq_num = 0
        server_ts = client_ts
        payload_len = len(payload)
        header_zero = HEADER_STRUCT.pack(proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, 0)
        crc = binascii.crc32(header_zero + payload) & 0xffffffff
        header = HEADER_STRUCT.pack(proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, crc)
        packet = header + payload
        # send twice (simple reliability)
        try:
            self.sock.sendto(packet, self.server_addr)
            self.sock.sendto(packet, self.server_addr)
            print(f"[CLIENT] Sent ACQUIRE for cell {cell_id}")
        except Exception as e:
            print("[CLIENT] send error", e)

    def recv_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(8192)
                if len(data) < HEADER_STRUCT.size:
                    continue
                header = data[:HEADER_STRUCT.size]
                (proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, checksum) = HEADER_STRUCT.unpack(header)
                payload = data[HEADER_STRUCT.size:HEADER_STRUCT.size+payload_len]
                # validate
                if proto_id != PROTO_ID:
                    continue
                header_zero = HEADER_STRUCT.pack(proto_id, version, msg_type, snapshot_id, seq_num, server_ts, payload_len, 0)
                calc = binascii.crc32(header_zero + payload) & 0xffffffff
                if calc != checksum:
                    print("[CLIENT] CRC mismatch")
                    continue
                if msg_type == MSG_SNAPSHOT:
                    # payload may contain up to 3 concatenated snapshots (redundancy)
                    ptr = 0
                    updated = False
                    while ptr + 1 <= len(payload):
                        grid_n = payload[ptr]
                        ptr += 1
                        if grid_n != GRID_N:
                            # unexpected size; stop
                            break
                        needed = GRID_N * GRID_N
                        if ptr + needed > len(payload):
                            break
                        chunk = payload[ptr:ptr+needed]
                        ptr += needed
                        # apply this snapshot (we apply the first one in packet - most recent)
                        # but to be safe, we will apply the first encountered
                        if not updated:
                            with self.lock:
                                self.grid = list(chunk)
                            updated = True
                    # done
                else:
                    # ignore other types
                    pass
            except Exception as e:
                if self.running:
                    print("[CLIENT] recv error:", e)

    def close(self):
        self.running = False
        try:
            self.sock.close()
        except:
            pass

# Simple pygame UI
def run_pygame(client: GameClient):
    pygame.init()
    grid_pix = GRID_N * CELL_SIZE + (GRID_N + 1) * MARGIN
    win = pygame.display.set_mode((grid_pix, grid_pix))
    pygame.display.set_caption(f"Grid Clash - Player {client.player_id}")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 20)

    colors = {
        0: (200, 200, 200),  # unclaimed
        1: (255, 100, 100),
        2: (100, 255, 100),
        3: (100, 100, 255),
        4: (255, 255, 100)
    }

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = pygame.mouse.get_pos()
                # compute cell
                # grid origin top-left margin
                x = mx
                y = my
                # cell index:
                col = (x - MARGIN) // (CELL_SIZE + MARGIN)
                row = (y - MARGIN) // (CELL_SIZE + MARGIN)
                if 0 <= col < GRID_N and 0 <= row < GRID_N:
                    cell_id = row * GRID_N + col
                    # try to acquire
                    with client.lock:
                        # local optimistic: if unclaimed in view, send request
                        if client.grid[cell_id] == 0:
                            client.send_event_acquire(cell_id)
        # draw
        win.fill((30,30,30))
        with client.lock:
            grid_copy = client.grid.copy()
        for r in range(GRID_N):
            for c in range(GRID_N):
                cell_id = r * GRID_N + c
                owner = grid_copy[cell_id]
                color = colors.get(owner, (180,180,180))
                x = MARGIN + c * (CELL_SIZE + MARGIN)
                y = MARGIN + r * (CELL_SIZE + MARGIN)
                pygame.draw.rect(win, color, (x, y, CELL_SIZE, CELL_SIZE))
                # draw owner id
                if owner != 0:
                    txt = font.render(str(owner), True, (0,0,0))
                    win.blit(txt, (x+4, y+4))

        pygame.display.flip()
        clock.tick(30)
    client.close()
    pygame.quit()

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--server_host', default='127.0.0.1')
    p.add_argument('--server_port', type=int, default=10000)
    p.add_argument('--player_id', type=int, required=True)
    args = p.parse_args()
    client = GameClient(server_host=args.server_host, server_port=args.server_port, player_id=args.player_id)
    try:
        run_pygame(client)
    except KeyboardInterrupt:
        client.close()
