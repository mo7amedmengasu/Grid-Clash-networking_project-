# GSync — Grid Clash (networking_project)

This small project demonstrates a simple UDP-based multiplayer grid game (server + pygame client).

- Server: `server.py` — a UDP server that maintains a GRID_N x GRID_N ownership grid, accepts ACQUIRE requests and broadcasts snapshots with optional redundancy.
- Client (pygame): `client_pygame.py` — a pygame-based client that displays the grid and sends ACQUIRE requests when the player clicks a cell.

Files of interest
- `server.py` — GridServer (defaults: host=127.0.0.1, port=10000, rate=10 Hz). Produces `server_snapshots.csv` and `server_events.csv` in the working directory for logs.
- `client_pygame.py` — GameClient and simple pygame UI. Requires `--player_id` (integer). Defaults to server_host=127.0.0.1 and server_port=10000.

Prerequisites
- Python 3.8+ (or any modern Python 3).
- The project uses `pygame` (see `requirements.txt`).

Install dependencies (PowerShell)

```powershell
# from project root (where requirements.txt lives)
python -m pip install -r requirements.txt
```

Running the server (PowerShell examples)

```powershell
# run with defaults
python server.py

# or specify host/port/rate
python server.py --host 127.0.0.1 --port 10000 --rate 10
```

Running the pygame client

Important: the pygame client requires a numeric player id.

```powershell
# example: run a client as player 1 connecting to localhost:10000
python client_pygame.py --server_host 127.0.0.1 --server_port 10000 --player_id 1

# run multiple clients on the same machine by launching additional terminals and using different --player_id values
python client_pygame.py --server_host 127.0.0.1 --server_port 10000 --player_id 2
```

Notes / Troubleshooting
- The server and client use UDP. If running the server on a different machine, ensure any firewall allows incoming UDP on the chosen port (default 10000).
- The client sends an INIT packet on start; make sure the server is running first to register clients.
- The client sends each ACQUIRE event twice for simple reliability; the server accepts the first-come-first-served acquire.
- Log files created by the server: `server_snapshots.csv` and `server_events.csv`.

Project structure (top-level)

```
networking_project/
  server.py
  client_pygame.py
other folders...
requirements.txt
```

