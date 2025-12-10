#!/bin/bash

################################################################################
# GSync v2 - Automated Test Runner for Linux/WSL2
# Runs all 4 test scenarios with network impairments using tc/netem
################################################################################

# Configuration
SERVER_CMD="python3 server.py --rate 20"
CLIENT_CMD="python3 client_pygame.py --player_id 1 --scenario"
TEST_DURATION=60
INTERFACE="lo"  # Change to eth0, wlan0, etc. if needed

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
    echo -e "${YELLOW}⚠${NC}  $1"
}

countdown() {
    local seconds=$1
    local message="$2"
    for ((i=seconds; i>0; i--)); do
        echo -ne "\r${message} ${i}s...   "
        sleep 1
    done
    echo -e "\r${message} Done!      "
}

cleanup_netem() {
    print_step "CLEANUP" "Removing network impairment..."
    sudo tc qdisc del dev $INTERFACE root 2>/dev/null
    sleep 1
}

cleanup_processes() {
    print_step "CLEANUP" "Stopping server and client..."
    pkill -f "python3 server.py" 2>/dev/null
    pkill -f "python3 client_pygame.py" 2>/dev/null
    sleep 2
}

################################################################################
# Test Execution Function
################################################################################

run_test() {
    local scenario=$1
    local test_num=$2
    local total=$3
    local netem_cmd=$4

    print_banner "TEST $test_num/$total: ${scenario^^}"

    # Apply network impairment
    if [ "$netem_cmd" != "none" ]; then
        print_step "1/4" "Applying network impairment: $netem_cmd"
        sudo tc qdisc add dev $INTERFACE root netem $netem_cmd
        if [ $? -eq 0 ]; then
            print_success "Network impairment applied"
        else
            print_error "Failed to apply network impairment"
            return 1
        fi
    else
        print_step "1/4" "No network impairment (baseline)"
    fi

    # Start server
    print_step "2/4" "Starting server..."
    $SERVER_CMD 2>&1 | tee server_error.log &
    SERVER_PID=$!
    sleep 2

    if kill -0 $SERVER_PID 2>/dev/null; then
        print_success "Server started (PID: $SERVER_PID)"
    else
        print_error "Server failed to start"
        cleanup_netem
        return 1
    fi

    # Start client
    print_step "3/4" "Starting client..."
    $CLIENT_CMD $scenario > /dev/null 2>&1 &
    CLIENT_PID=$!
    sleep 2

    if kill -0 $CLIENT_PID 2>/dev/null; then
        print_success "Client started (PID: $CLIENT_PID)"
    else
        print_error "Client failed to start"
        kill $SERVER_PID 2>/dev/null
        cleanup_netem
        return 1
    fi

    # Run test
    print_step "4/4" "Running test for ${TEST_DURATION} seconds..."
    countdown $TEST_DURATION "   Time remaining:"

    # Cleanup
    cleanup_processes
    if [ "$netem_cmd" != "none" ]; then
        cleanup_netem
    fi

    print_success "Test '$scenario' completed!"
    echo ""
    sleep 2
}

################################################################################
# Main Script
################################################################################

main() {
    print_banner "GSync v2 Automated Test Runner"

    echo "This script will run 4 test scenarios:"
    echo "  1. Baseline (no impairment)"
    echo "  2. Loss 2%"
    echo "  3. Loss 5%"
    echo "  4. Delay 100ms"
    echo ""
    echo "Each test runs for ${TEST_DURATION} seconds."
    echo "Network interface: $INTERFACE"
    echo ""

    # Check if running as root (needed for tc)
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run with sudo privileges"
        echo "Usage: sudo ./run_tests.sh"
        exit 1
    fi

    # Check if files exist
    if [ ! -f "server.py" ]; then
        print_error "server.py not found!"
        echo "Make sure you're in the correct directory."
        exit 1
    fi

    if [ ! -f "client_pygame.py" ]; then
        print_error "client_pygame.py not found!"
        echo "Make sure you're in the correct directory."
        exit 1
    fi

    print_success "Files found: server.py, client_pygame.py"
    echo ""

    # Check if tc is available
    if ! command -v tc &> /dev/null; then
        print_error "tc command not found!"
        echo "Install with: sudo apt install iproute2"
        exit 1
    fi

    print_success "tc/netem available"
    echo ""

    # Confirm start
    read -p "Ready to start tests? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Tests cancelled."
        exit 0
    fi

    # Record start time
    START_TIME=$(date +%s)

    # Run all tests
    run_test "baseline" 1 4 "none"
    run_test "loss2" 2 4 "loss 2%"
    run_test "loss5" 3 4 "loss 5%"
    run_test "delay100" 4 4 "delay 100ms"

    # Final cleanup
    cleanup_processes
    cleanup_netem

    # Summary
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    MINUTES=$((DURATION / 60))
    SECONDS=$((DURATION % 60))

    print_banner "ALL TESTS COMPLETED!"
    echo "Total time: ${MINUTES}m ${SECONDS}s"
    echo ""
    echo "Generated files:"
    echo "  - Server CSV files (in current directory)"
    echo "  - Client CSV files (in logs/ directory)"
    echo ""
    echo "Next steps:"
    echo "  1. Check logs/ folder for client CSV files"
    echo "  2. Analyze metrics (latency, jitter, etc.)"
    echo "  3. Repeat each test 5 times for statistical significance"
    echo ""
}

################################################################################
# Trap for cleanup on interrupt
################################################################################

trap "echo ''; print_warning 'Tests interrupted by user'; cleanup_processes; cleanup_netem; exit 1" INT TERM

################################################################################
# Execute Main
################################################################################

main
