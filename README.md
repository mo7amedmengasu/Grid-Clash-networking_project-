================================================================================
                     GSync v2 - Grid Clash Protocol
                    CSE361 Computer Networks Project
                           Phase 2 Submission
================================================================================

PROJECT INFORMATION
-------------------
Protocol:        GSync v2 (Grid Synchronization Protocol Version 2)
Type:            UDP-based Multiplayer Game State Synchronization
Transport:       UDP with K=3 redundancy, CRC32 checksum
Team:            [Add your team member names]
Date:            [Add submission date]


================================================================================
1. OVERVIEW
================================================================================

GSync v2: Low-latency UDP protocol for multiplayer Grid Clash game (10×10 grid).

Key Features:
✓ 28-byte binary header with CRC32 validation
✓ K=3 redundancy (tolerates 5% packet loss)
✓ 20 Hz server update rate (50ms latency target)
✓ Supports 4+ concurrent clients
✓ Comprehensive CSV logging (latency, jitter, CPU, bandwidth)

Protocol Specs:
- Header: GSYN + 28 bytes (protocol_id, version, msg_type, snapshot_id, 
  seq_num, timestamp, payload_len, crc32)
- Messages: INIT, SNAPSHOT, EVENT, GAME_OVER
- Max Payload: 1200 bytes


================================================================================
2. QUICK START (WINDOWS)
================================================================================

Install Dependencies:
---------------------
pip install pygame psutil


Run Game (3 easy steps):
-------------------------
1. Start server:
   python server.py --rate 20

2. Start client (in new window):
   python client_pygame.py --player_id 1

3. Optional: Start more clients (player_id 2-8)
   python client_pygame.py --player_id 2


Game Controls:
--------------
• Click gray cells to claim them
• First click wins (server resolves conflicts)
• Game ends when all 100 cells claimed
• Winner announced on all screens


Output Files:
-------------
Server (current directory):
├── server_snapshots.csv
├── server_events.csv
└── server_authoritative_grid.csv

Client (logs\ directory):
├── client{ID}_snapshots_{scenario}_{timestamp}.csv
├── client{ID}_diagnostics_{scenario}_{timestamp}.csv
└── client{ID}_position_error_{scenario}_{timestamp}.csv


================================================================================
3. RUNNING TESTS (PHASE 2)
================================================================================

Required: 4 scenarios × 5 runs = 20 tests


Option 1: Automated Bash Script (Linux/WSL2) - RECOMMENDED
-----------------------------------------------------------
The easiest way to run all tests automatically!

### Prerequisites:

1. Install Python and dependencies in WSL2:
   sudo apt update
   sudo apt install python3 python3-pip python3-psutil python3-pygame -y

2. Make script executable:
   chmod +x run_tests.sh

### Run All Tests:

   sudo ./run_tests.sh

### What It Does:
- ✓ Runs all 4 scenarios automatically (Baseline, Loss 2%, Loss 5%, Delay 100ms)
- ✓ Applies network impairments using tc/netem (no manual setup!)
- ✓ Each test runs for 60 seconds
- ✓ Auto-cleanup after each test
- ✓ Total time: ~5 minutes

### For Phase 2 (Run 5 Times):

   sudo ./run_tests.sh  # Run 1
   sudo ./run_tests.sh  # Run 2
   sudo ./run_tests.sh  # Run 3
   sudo ./run_tests.sh  # Run 4
   sudo ./run_tests.sh  # Run 5

### Troubleshooting Bash Script:

Problem: "python: command not found"
Fix: Script uses python3 (correct for Linux/WSL2)

Problem: "No module named 'psutil'"
Fix: sudo apt install python3-psutil python3-pygame

Problem: "externally-managed-environment" when using pip
Fix: Use apt instead: sudo apt install python3-psutil python3-pygame

Problem: "RTNETLINK answers: File exists"
Fix: sudo tc qdisc del dev lo root

Problem: Display/GUI errors
Fix: Install X server (VcXsrv) or run on native Linux


Option 2: Automated Python Script (Windows)
--------------------------------------------
For Windows users without WSL2:

1. Run the script:
   python run_tests_windows.py

2. Follow prompts to configure Clumsy for each scenario

3. Each test runs for 60 seconds automatically


Option 3: Manual Testing with Clumsy (Windows)
-----------------------------------------------
1. Download & install Clumsy: https://jagt.github.io/clumsy/
2. Run as Administrator

For each scenario, repeat 5 times:

┌─────────────┬────────────────────┬─────────────────────────────────┐
│ Scenario    │ Clumsy Settings    │ Commands                        │
├─────────────┼────────────────────┼─────────────────────────────────┤
│ Baseline    │ Off (no impair)    │ python server.py --rate 20      │
│             │                    │ python client_pygame.py         │
│             │                    │   --player_id 1 --scenario      │
│             │                    │   baseline                      │
├─────────────┼────────────────────┼─────────────────────────────────┤
│ Loss 2%     │ Drop = 2.0         │ python server.py --rate 20      │
│             │ Click "Start"      │ python client_pygame.py         │
│             │                    │   --player_id 1 --scenario      │
│             │                    │   loss2                         │
├─────────────┼────────────────────┼─────────────────────────────────┤
│ Loss 5%     │ Drop = 5.0         │ python server.py --rate 20      │
│             │ Click "Start"      │ python client_pygame.py         │
│             │                    │   --player_id 1 --scenario      │
│             │                    │   loss5                         │
├─────────────┼────────────────────┼─────────────────────────────────┤
│ Delay 100ms │ Lag = 100          │ python server.py --rate 20      │
│             │ Click "Start"      │ python client_pygame.py         │
│             │                    │   --player_id 1 --scenario      │
│             │                    │   delay100                      │
└─────────────┴────────────────────┴─────────────────────────────────┘

Play each test for 60 seconds, then close. Don't forget to click "Stop" in 
Clumsy between tests!


Option 4: Manual Testing with WSL2
-----------------------------------
If automated script doesn't work:

1. Install WSL2:
   wsl --install

2. In WSL terminal, navigate to project:
   cd "/mnt/c/Users/YourName/path/to/project"

3. Install dependencies:
   sudo apt install python3-psutil python3-pygame

4. Run tests manually:
   # Baseline:
   python3 server.py --rate 20 &
   python3 client_pygame.py --player_id 1 --scenario baseline
   # After 60s: Ctrl+C both

   # Loss 2%:
   sudo tc qdisc add dev lo root netem loss 2%
   python3 server.py --rate 20 &
   python3 client_pygame.py --player_id 1 --scenario loss2
   # After 60s: Ctrl+C both
   sudo tc qdisc del dev lo root

   # Loss 5%:
   sudo tc qdisc add dev lo root netem loss 5%
   python3 server.py --rate 20 &
   python3 client_pygame.py --player_id 1 --scenario loss5
   # After 60s: Ctrl+C both
   sudo tc qdisc del dev lo root

   # Delay 100ms:
   sudo tc qdisc add dev lo root netem delay 100ms
   python3 server.py --rate 20 &
   python3 client_pygame.py --player_id 1 --scenario delay100
   # After 60s: Ctrl+C both
   sudo tc qdisc del dev lo root


Acceptance Criteria:
--------------------
✓ Baseline:    Latency ≤50ms, CPU <60%
✓ Loss 2%:     Position error ≤0.5 units (95th percentile ≤1.5)
✓ Loss 5%:     Events delivered ≥99% within 200ms
✓ Delay 100ms: System remains stable


================================================================================
4. COMMAND-LINE OPTIONS
================================================================================

Server Options:
---------------
python server.py [options]

--host <IP>      Server IP (default: 127.0.0.1)
--port <PORT>    Port (default: 10000)
--rate <HZ>      Update rate (default: 20 Hz for Phase 2)

Example:
python server.py --host 0.0.0.0 --port 10000 --rate 20


Client Options:
---------------
python client_pygame.py [options]

--server_host <IP>   Server IP (default: 127.0.0.1)
--server_port <PORT> Port (default: 10000)
--player_id <ID>     Player ID 1-8 (REQUIRED)
--scenario <NAME>    Test scenario: baseline, loss2, loss5, delay100
--smoothing <FLOAT>  Position smoothing 0.0-1.0 (default: 0.3)

Example:
python client_pygame.py --player_id 1 --scenario loss2


================================================================================
5. DESIGN DECISIONS (WHY WE CHOSE...)
================================================================================

K=3 Redundancy:
• Simple, effective for 2-5% loss
• Each packet = current + last 2 snapshots
• Trade-off: 3× bandwidth for reliability

20 Hz Update Rate:
• Balance: Low latency (50ms) vs bandwidth
• Alternative: 60 Hz for competitive games (16ms)

CRC32 Checksum:
• Fast corruption detection (4 bytes)
• Hardware-accelerated, minimal CPU cost

Double-Send for Events:
• Send ACQUIRE_REQUEST twice (1ms apart)
• 2× bandwidth, but events are rare (1-10 per game)

Binary Protocol:
• 28-byte header (10× smaller than JSON)
• Fast parsing, low overhead

Grid Clash Game:
• Simple discrete states (no physics)
• Focus on protocol testing, not game complexity


Field Sizes:
────────────────────────────────────────────────────────
Field              Size    Justification
────────────────────────────────────────────────────────
Protocol ID        4 bytes ASCII "GSYN" (human-readable)
Version            1 byte  256 versions
Message Type       1 byte  256 message types
Snapshot ID        4 bytes 4.2B snapshots (24+ hrs @ 20Hz)
Sequence Number    4 bytes Gap detection, overflow check
Server Timestamp   8 bytes ms precision (584M years)
Payload Length     2 bytes 65KB max (actual: 1200 bytes)
CRC32 Checksum     4 bytes Industry standard
────────────────────────────────────────────────────────


Rejected Alternatives:
----------------------
✗ TCP: Head-of-line blocking kills real-time performance
✗ Delta encoding: Complex, needs ACK, redundancy simpler
✗ Selective ACKs: Overhead not worth it for 5% loss
✗ Adaptive rate: Fixed 20 Hz sufficient for Phase 2


================================================================================
6. FILE STRUCTURE
================================================================================

CSE361_Project_Phase2\
├── server.py                     ← Server (refactored, commented)
├── client_pygame.py              ← Client (refactored, commented)
├── run_tests.sh                  ← Automated test script (Linux/WSL2)
├── run_tests_windows.py          ← Automated test script (Windows)
├── Mini_RFC_Phase2.pdf           ← Protocol specification (9 sections)
├── README.txt                    ← This file
│
├── logs\                         ← Auto-created by client
│   ├── client1_snapshots_*.csv
│   ├── client1_diagnostics_*.csv
│   └── client1_position_error_*.csv
│
├── server_snapshots.csv          ← Generated by server
├── server_events.csv
└── server_authoritative_grid.csv


================================================================================
7. TROUBLESHOOTING
================================================================================

Problem: "pygame not found"
Fix: pip install pygame (Windows) or sudo apt install python3-pygame (Linux)

Problem: "Permission denied" (Clumsy)
Fix: Run Clumsy as Administrator

Problem: "Permission denied" (run_tests.sh)
Fix: chmod +x run_tests.sh OR run with sudo

Problem: Client can't connect
Fix: Check firewall allows UDP port 10000
     Try: python server.py --host 0.0.0.0

Problem: High CPU usage
Fix: Normal with 4+ clients. Reduce to 2 clients or lower --rate

Problem: Logs folder not created
Fix: Run client once, logs\ folder auto-created

Problem: Game window black screen
Fix: Wait 2-3 seconds for first snapshot from server

Problem: "externally-managed-environment" (WSL2/Linux)
Fix: Use apt instead of pip: sudo apt install python3-psutil python3-pygame

Problem: "python: command not found" in WSL2
Fix: Use python3 command (script already uses python3)


================================================================================
8. SYSTEM REQUIREMENTS
================================================================================

Minimum:
• Windows 10+, Python 3.7+
• 2GB RAM, 100MB disk
• pygame 2.0.0+, psutil 5.8.0+

For Testing:
• Windows: Clumsy OR run_tests_windows.py
• Linux/WSL2: run_tests.sh (requires sudo for tc/netem)


================================================================================
9. KNOWN LIMITATIONS
================================================================================

1. Position Error: Not meaningful for discrete grid (logged as 0)
   → Grid Clash uses cells, not continuous X/Y positions

2. No Adaptive Rate: Fixed 20 Hz regardless of network conditions
   → Could optimize per-client in Phase 3

3. Max 8 Player Colors: UI limitation (protocol supports 256)

4. No Encryption: Performance focus (add TLS/DTLS for production)

5. Single Server: No load balancing (fine for 4 clients)


Performance (Windows 10, Intel i5):
• Baseline: 15-25ms latency, 30-40% CPU (4 clients)
• Bandwidth: ~12 KB/s per client @ 20 Hz
• Memory: 50MB server, 80MB client


================================================================================
10. REFERENCES
================================================================================

Standards:
• RFC 768 (UDP), RFC 1071 (Checksums), RFC 2119 (Keywords)

Tools:
• PyGame: https://www.pygame.org/
• psutil: https://github.com/giampaolo/psutil
• Clumsy: https://jagt.github.io/clumsy/
• tc/netem: https://man7.org/linux/man-pages/man8/tc-netem.8.html

Learning:
• Valve Source Networking: https://developer.valvesoftware.com/wiki/
• Gaffer On Games: https://gafferongames.com/


================================================================================
                              END OF README
================================================================================

Contact: [Your email]
Last Updated: December 2025

Quick Command Reference:
------------------------
# Automated tests (RECOMMENDED):
sudo ./run_tests.sh                # Linux/WSL2
python run_tests_windows.py        # Windows

# Manual server/client:
python server.py --rate 20
python client_pygame.py --player_id 1 --scenario baseline

# Install dependencies:
pip install pygame psutil                                    # Windows
sudo apt install python3-psutil python3-pygame               # Linux/WSL2
