#!/bin/bash

################################################################################
# GSync v2 - Automated Test Runner for Linux/WSL2 (Fixed Version)
# Runs all 4 test scenarios with network impairments using tc/netem
# Now includes: PCAP capture, multiple runs, 4 concurrent clients
################################################################################

# Configuration
SERVER_CMD="python3 server.py --rate 20"
CLIENT_CMD="python3 client_pygame.py"
TEST_DURATION=60
INTERFACE="lo"  # Change to eth0, wlan0, etc. if needed
NUM_CLIENTS=4   # Number of concurrent clients
NUM_RUNS=5      # Number of repetitions per test scenario

# Export display for headless pygame (if needed)
export SDL_VIDEODRIVER="dummy"
export DISPLAY=:0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

################################################################################
# Helper Functions
################################################################################

print_banner() {
    echo ""
    echo "======================================================================"
    echo "  $1"
    echo "======================================================================"
    echo ""
}

print_step() {
    echo -e "${BLUE}[$1]${NC} $2"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

countdown() {
    local seconds=$1
    local message="$2"
    for ((i=seconds; i>0; i--)); do
        echo -ne "\r${message} ${i}s...    "
        sleep 1
    done
    echo -e "\r${message} Done!          "
}

cleanup_netem() {
    print_step "CLEANUP" "Removing network impairment..."
    sudo tc qdisc del dev $INTERFACE root 2>/dev/null
    sleep 1
}

cleanup_processes() {
    print_step "CLEANUP" "Stopping all processes..."
    pkill -f "python3 server.py" 2>/dev/null
    pkill -f "python3 client_pygame.py" 2>/dev/null
    pkill -f "tcpdump" 2>/dev/null
    sleep 2
}

################################################################################
# Test Execution Function
################################################################################

run_test() {
    local scenario=$1
    local run_number=$2
    local netem_cmd=$3

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local test_id="${scenario}_run${run_number}_${timestamp}"

    print_banner "TEST: ${scenario^^} - Run ${run_number}/${NUM_RUNS}"

    # Create directories for outputs
    mkdir -p pcap logs results

    # Apply network impairment
    if [ "$netem_cmd" != "none" ]; then
        print_step "1/6" "Applying network impairment: $netem_cmd"
        sudo tc qdisc add dev $INTERFACE root netem $netem_cmd
        if [ $? -eq 0 ]; then
            print_success "Network impairment applied"
        else
            print_error "Failed to apply network impairment"
            return 1
        fi
    else
        print_step "1/6" "No network impairment (baseline)"
    fi

    # Start packet capture (if tcpdump available)
    print_step "2/6" "Starting packet capture..."
    if command -v tcpdump &> /dev/null; then
        tcpdump -i $INTERFACE -w "pcap/${test_id}.pcap" udp port 10000 > /dev/null 2>&1 &
        TCPDUMP_PID=$!
        sleep 1
        if kill -0 $TCPDUMP_PID 2>/dev/null; then
            print_success "Packet capture started (PID: $TCPDUMP_PID)"
        fi
    else
        print_warning "tcpdump not available, skipping packet capture"
        TCPDUMP_PID=""
    fi

    # Start server
    print_step "3/6" "Starting server..."
    $SERVER_CMD > "logs/server_${test_id}.log" 2>&1 &
    SERVER_PID=$!
    sleep 2

    if ! kill -0 $SERVER_PID 2>/dev/null; then
        print_error "Server failed to start"
        cat "logs/server_${test_id}.log"
        [ -n "$TCPDUMP_PID" ] && kill $TCPDUMP_PID 2>/dev/null
        cleanup_netem
        return 1
    fi
    print_success "Server started (PID: $SERVER_PID)"

    # Start multiple clients
    print_step "4/6" "Starting ${NUM_CLIENTS} clients..."
    declare -a CLIENT_PIDS
    local clients_started=0

    for client_id in $(seq 1 $NUM_CLIENTS); do
        # Run client in background, suppress pygame window
        PYGAME_HIDE_SUPPORT_PROMPT=1 $CLIENT_CMD \
            --player_id $client_id \
            --scenario $scenario \
            > "logs/client_${client_id}_${test_id}.log" 2>&1 &

        local pid=$!
        CLIENT_PIDS[$client_id]=$pid
        sleep 0.5

        # Check if client started successfully
        if kill -0 $pid 2>/dev/null; then
            ((clients_started++))
        else
            print_warning "Client $client_id failed to start"
            # Show error log
            if [ -f "logs/client_${client_id}_${test_id}.log" ]; then
                tail -n 5 "logs/client_${client_id}_${test_id}.log"
            fi
        fi
    done

    if [ $clients_started -eq 0 ]; then
        print_error "No clients started successfully"
        kill $SERVER_PID 2>/dev/null
        [ -n "$TCPDUMP_PID" ] && kill $TCPDUMP_PID 2>/dev/null
        cleanup_netem
        return 1
    elif [ $clients_started -lt $NUM_CLIENTS ]; then
        print_warning "Only ${clients_started}/${NUM_CLIENTS} clients started"
    else
        print_success "All ${NUM_CLIENTS} clients started"
    fi

    # Run test
    print_step "5/6" "Running test for ${TEST_DURATION} seconds..."
    countdown $TEST_DURATION "  Time remaining:"

    # Stop packet capture
    if [ -n "$TCPDUMP_PID" ]; then
        print_step "6/6" "Stopping packet capture..."
        kill $TCPDUMP_PID 2>/dev/null
        sleep 1
    fi

    # Cleanup processes
    cleanup_processes

    # Remove network impairment
    if [ "$netem_cmd" != "none" ]; then
        cleanup_netem
    fi

    # Move generated CSV files to results directory
    mv server*.csv "results/" 2>/dev/null

    # Show brief summary
    local csv_count=$(ls logs/client*_snapshots_${scenario}_*.csv 2>/dev/null | wc -l)
    print_success "Test '${scenario}' run ${run_number} completed! (Generated ${csv_count} client CSV files)"

    echo ""
    sleep 2
}

################################################################################
# Main Script
################################################################################

main() {
    print_banner "GSync v2 Enhanced Automated Test Runner"

    echo "Configuration:"
    echo "  • Test scenarios: 4 (baseline, loss2, loss5, delay100)"
    echo "  • Runs per scenario: ${NUM_RUNS}"
    echo "  • Clients per test: ${NUM_CLIENTS}"
    echo "  • Test duration: ${TEST_DURATION}s"
    echo "  • Network interface: $INTERFACE"
    echo "  • Total tests: $((4 * NUM_RUNS))"
    echo "  • Estimated time: ~$((4 * NUM_RUNS * (TEST_DURATION + 10) / 60)) minutes"
    echo ""

    # Check if running with sudo
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run with sudo privileges"
        echo "Usage: sudo ./run_tests_enhanced.sh"
        exit 1
    fi

    # Check required files
    if [ ! -f "server.py" ]; then
        print_error "server.py not found!"
        exit 1
    fi

    if [ ! -f "client_pygame.py" ]; then
        print_error "client_pygame.py not found!"
        exit 1
    fi

    print_success "Files found: server.py, client_pygame.py"

    # Check if tc is available
    if ! command -v tc &> /dev/null; then
        print_error "tc command not found!"
        echo "Install with: sudo apt install iproute2"
        exit 1
    fi
    print_success "tc/netem available"

    # Check if tcpdump is available
    if ! command -v tcpdump &> /dev/null; then
        print_warning "tcpdump not found - packet capture will be skipped"
        echo "Install with: sudo apt install tcpdump"
        read -p "Continue without packet capture? (y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 0
        fi
    else
        print_success "tcpdump available"
    fi

    # Check if python3 and pygame are available
    if ! command -v python3 &> /dev/null; then
        print_error "python3 not found!"
        exit 1
    fi

    if ! python3 -c "import pygame" 2>/dev/null; then
        print_warning "pygame not installed"
        echo "Install with: pip3 install pygame"
        exit 1
    fi
    print_success "python3 and pygame available"

    echo ""

    # Confirm start
    read -p "Ready to start all tests? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Tests cancelled."
        exit 0
    fi

    # Create output directories
    mkdir -p pcap logs results

    # Record start time
    START_TIME=$(date +%s)

    # Run all test scenarios with multiple runs
    print_banner "STARTING ALL TESTS"

    # Baseline tests
    for run in $(seq 1 $NUM_RUNS); do
        run_test "baseline" $run "none"
    done

    # Loss 2% tests
    for run in $(seq 1 $NUM_RUNS); do
        run_test "loss2" $run "loss 2%"
    done

    # Loss 5% tests
    for run in $(seq 1 $NUM_RUNS); do
        run_test "loss5" $run "loss 5%"
    done

    # Delay 100ms tests
    for run in $(seq 1 $NUM_RUNS); do
        run_test "delay100" $run "delay 100ms"
    done

    # Final cleanup
    cleanup_processes
    cleanup_netem

    # Calculate duration
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    MINUTES=$((DURATION / 60))
    SECONDS=$((DURATION % 60))

    # Summary
    print_banner "ALL TESTS COMPLETED!"

    echo "Test Summary:"
    echo "  • Total tests run: $((4 * NUM_RUNS))"
    echo "  • Total time: ${MINUTES}m ${SECONDS}s"
    echo ""

    echo "Generated files:"
    echo "  • PCAP files: $(ls pcap/*.pcap 2>/dev/null | wc -l) files in pcap/"
    echo "  • Server CSV files: $(ls results/server*.csv 2>/dev/null | wc -l) files in results/"
    echo "  • Client CSV files: $(ls logs/client*_snapshots_*.csv 2>/dev/null | wc -l) files in logs/"
    echo "  • Log files: $(ls logs/*.log 2>/dev/null | wc -l) files in logs/"
    echo ""

    echo "Next steps:"
    echo "  1. Analyze results: python analyze_results.py"
    echo "  2. Examine PCAP files with Wireshark/tshark"
    echo "  3. Review generated plots in analysis_results/"
    echo "  4. Document results in Mini-RFC and technical report"
    echo ""

    print_success "All tests completed successfully!"
}

################################################################################
# Trap for cleanup on interrupt
################################################################################

trap "echo ''; print_warning 'Tests interrupted by user'; cleanup_processes; cleanup_netem; exit 1" INT TERM

################################################################################
# Execute Main
################################################################################

main
