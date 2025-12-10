"""
GSync v2 - Automated Test Results Analysis
Analyzes CSV logs from all test scenarios and generates summary report
"""

import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime

# Configuration
LOGS_DIR = "logs"
OUTPUT_DIR = "analysis_results"
SCENARIOS = ["baseline", "loss2", "loss5", "delay100"]

def print_section(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")

def analyze_snapshots(csv_file):
    """Analyze snapshot metrics: latency, jitter, redundancy"""
    df = pd.read_csv(csv_file)

    results = {
        'file': os.path.basename(csv_file),
        'total_packets': len(df),
        'mean_latency': df['latency_ms'].mean(),
        'median_latency': df['latency_ms'].median(),
        'min_latency': df['latency_ms'].min(),
        'max_latency': df['latency_ms'].max(),
        'p95_latency': df['latency_ms'].quantile(0.95),
        'mean_jitter': df['jitter_ms'].mean(),
        'median_jitter': df['jitter_ms'].median(),
        'max_jitter': df['jitter_ms'].max(),
        'p95_jitter': df['jitter_ms'].quantile(0.95),
        'mean_redundancy': df['redundancy_used'].mean(),
    }

    return results

def analyze_diagnostics(csv_file):
    """Analyze diagnostics: packet loss, duplicates"""
    df = pd.read_csv(csv_file)

    # Get final row (cumulative stats)
    final = df.iloc[-1]

    results = {
        'file': os.path.basename(csv_file),
        'total_packets_received': final['packets_received'],
        'duplicate_rate': final['duplicate_rate'] * 100,  # Convert to %
        'sequence_gaps': final['sequence_gaps'],
        'packet_loss_rate': (final['sequence_gaps'] / final['packets_received'] * 100) if final['packets_received'] > 0 else 0,
        'delivery_rate': 100 - (final['sequence_gaps'] / final['packets_received'] * 100) if final['packets_received'] > 0 else 100,
    }

    return results

def find_scenario_files(scenario):
    """Find all CSV files for a given scenario"""
    pattern = f"{LOGS_DIR}/client*_snapshots_{scenario}_*.csv"
    snapshot_files = sorted(glob.glob(pattern))

    diag_files = []
    for snap in snapshot_files:
        diag = snap.replace('_snapshots_', '_diagnostics_')
        if os.path.exists(diag):
            diag_files.append(diag)

    return snapshot_files, diag_files

def analyze_scenario(scenario):
    """Analyze all runs of a specific scenario"""
    print_section(f"Analyzing Scenario: {scenario.upper()}")

    snapshot_files, diag_files = find_scenario_files(scenario)

    if not snapshot_files:
        print(f"⚠️  No files found for scenario: {scenario}")
        print(f"   Looking for pattern: {LOGS_DIR}/client*_snapshots_{scenario}_*.csv")
        return None

    print(f"Found {len(snapshot_files)} test run(s) for {scenario}\n")

    # Analyze each run
    snapshot_results = []
    diag_results = []

    for i, (snap_file, diag_file) in enumerate(zip(snapshot_files, diag_files), 1):
        print(f"Run {i}: {os.path.basename(snap_file)}")

        snap_res = analyze_snapshots(snap_file)
        diag_res = analyze_diagnostics(diag_file)

        snapshot_results.append(snap_res)
        diag_results.append(diag_res)

    # Calculate aggregate statistics across all runs
    snap_df = pd.DataFrame(snapshot_results)
    diag_df = pd.DataFrame(diag_results)

    aggregate = {
        'scenario': scenario,
        'num_runs': len(snapshot_files),

        # Latency stats
        'mean_latency': snap_df['mean_latency'].mean(),
        'median_latency': snap_df['median_latency'].median(),
        'min_latency': snap_df['min_latency'].min(),
        'max_latency': snap_df['max_latency'].max(),
        'p95_latency': snap_df['p95_latency'].mean(),

        # Jitter stats
        'mean_jitter': snap_df['mean_jitter'].mean(),
        'median_jitter': snap_df['median_jitter'].median(),
        'max_jitter': snap_df['max_jitter'].max(),
        'p95_jitter': snap_df['p95_jitter'].mean(),

        # Packet stats
        'total_packets': snap_df['total_packets'].sum(),
        'packet_loss_rate': diag_df['packet_loss_rate'].mean(),
        'delivery_rate': diag_df['delivery_rate'].mean(),
        'duplicate_rate': diag_df['duplicate_rate'].mean(),
        'mean_redundancy': snap_df['mean_redundancy'].mean(),
    }

    # Print summary
    print(f"\n{scenario.upper()} Summary (across {len(snapshot_files)} run(s)):")
    print(f"  Latency (ms):")
    print(f"    Mean:   {aggregate['mean_latency']:6.2f} ms")
    print(f"    Median: {aggregate['median_latency']:6.2f} ms")
    print(f"    Min:    {aggregate['min_latency']:6.2f} ms")
    print(f"    Max:    {aggregate['max_latency']:6.2f} ms")
    print(f"    95th %: {aggregate['p95_latency']:6.2f} ms")

    print(f"\n  Jitter (ms):")
    print(f"    Mean:   {aggregate['mean_jitter']:6.2f} ms")
    print(f"    Median: {aggregate['median_jitter']:6.2f} ms")
    print(f"    Max:    {aggregate['max_jitter']:6.2f} ms")
    print(f"    95th %: {aggregate['p95_jitter']:6.2f} ms")

    print(f"\n  Packet Statistics:")
    print(f"    Total packets:    {aggregate['total_packets']}")
    print(f"    Delivery rate:    {aggregate['delivery_rate']:6.2f}%")
    print(f"    Loss rate:        {aggregate['packet_loss_rate']:6.2f}%")
    print(f"    Duplicate rate:   {aggregate['duplicate_rate']:6.2f}%")
    print(f"    Avg redundancy:   {aggregate['mean_redundancy']:6.2f}")

    # Check against acceptance criteria
    print(f"\n  Acceptance Criteria Check:")

    if scenario == 'baseline':
        latency_ok = aggregate['mean_latency'] <= 50
        jitter_ok = aggregate['mean_jitter'] < 10
        delivery_ok = aggregate['delivery_rate'] >= 99

        print(f"    Latency ≤50ms:     {'✓ PASS' if latency_ok else '✗ FAIL'} ({aggregate['mean_latency']:.2f} ms)")
        print(f"    Jitter <10ms:      {'✓ PASS' if jitter_ok else '✗ FAIL'} ({aggregate['mean_jitter']:.2f} ms)")
        print(f"    Delivery ≥99%:     {'✓ PASS' if delivery_ok else '✗ FAIL'} ({aggregate['delivery_rate']:.2f}%)")

    elif scenario == 'loss2':
        latency_ok = aggregate['mean_latency'] <= 75
        delivery_ok = aggregate['delivery_rate'] >= 95

        print(f"    Latency ≤75ms:     {'✓ PASS' if latency_ok else '✗ FAIL'} ({aggregate['mean_latency']:.2f} ms)")
        print(f"    Delivery ≥95%:     {'✓ PASS' if delivery_ok else '✗ FAIL'} ({aggregate['delivery_rate']:.2f}%)")

    elif scenario == 'loss5':
        latency_ok = aggregate['mean_latency'] <= 75
        delivery_ok = aggregate['delivery_rate'] >= 95

        print(f"    Latency ≤75ms:     {'✓ PASS' if latency_ok else '✗ FAIL'} ({aggregate['mean_latency']:.2f} ms)")
        print(f"    Delivery ≥95%:     {'✓ PASS' if delivery_ok else '✗ FAIL'} ({aggregate['delivery_rate']:.2f}%)")

    elif scenario == 'delay100':
        latency_ok = aggregate['mean_latency'] >= 100 and aggregate['mean_latency'] <= 150
        stable_ok = aggregate['delivery_rate'] >= 95

        print(f"    Latency 100-150ms: {'✓ PASS' if latency_ok else '✗ FAIL'} ({aggregate['mean_latency']:.2f} ms)")
        print(f"    System stable:     {'✓ PASS' if stable_ok else '✗ FAIL'} ({aggregate['delivery_rate']:.2f}% delivery)")

    return aggregate

def save_summary_csv(all_results):
    """Save summary results to CSV"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = pd.DataFrame(all_results)
    output_file = f"{OUTPUT_DIR}/summary_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(output_file, index=False)

    print(f"\n✓ Summary saved to: {output_file}")
    return output_file

def generate_comparison_table(all_results):
    """Generate comparison table across scenarios"""
    print_section("COMPARISON TABLE: All Scenarios")

    if not all_results:
        print("⚠️  No results to compare")
        return

    df = pd.DataFrame(all_results)

    print(f"{'Scenario':<12} {'Latency (ms)':<15} {'Jitter (ms)':<15} {'Delivery %':<12} {'Loss %':<10}")
    print(f"{'='*12} {'='*15} {'='*15} {'='*12} {'='*10}")

    for _, row in df.iterrows():
        print(f"{row['scenario']:<12} "
              f"{row['mean_latency']:>6.2f} (±{row['p95_latency']-row['mean_latency']:>4.2f}) "
              f"{row['mean_jitter']:>6.2f} (max:{row['max_jitter']:>5.2f}) "
              f"{row['delivery_rate']:>10.2f}% "
              f"{row['packet_loss_rate']:>8.2f}%")

def main():
    print_section("GSync v2 - Test Results Analysis")

    print(f"Analyzing test results from: {LOGS_DIR}/")
    print(f"Scenarios: {', '.join(SCENARIOS)}")
    print(f"Output directory: {OUTPUT_DIR}/\n")

    # Check if logs directory exists
    if not os.path.exists(LOGS_DIR):
        print(f"❌ ERROR: Logs directory not found: {LOGS_DIR}/")
        print(f"   Make sure you've run tests and have CSV files in {LOGS_DIR}/")
        return

    # Analyze each scenario
    all_results = []

    for scenario in SCENARIOS:
        result = analyze_scenario(scenario)
        if result:
            all_results.append(result)

    # Generate comparison
    if all_results:
        generate_comparison_table(all_results)
        save_summary_csv(all_results)
    else:
        print("\n⚠️  No test results found!")
        print("   Run tests first: sudo ./run_tests.sh")

    print_section("Analysis Complete!")
    print("Next steps:")
    print("  1. Review summary CSV in analysis_results/ folder")
    print("  2. Run tests 5 times for statistical significance")
    print("  3. Create plots for your report\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
