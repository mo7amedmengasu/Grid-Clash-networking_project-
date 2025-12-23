"""
GSync v1 - Enhanced Test Results Analysis
Analyzes CSV logs from all test scenarios and generates comprehensive reports
Supports multiple clients and multiple runs per scenario
"""

import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

# Configuration
LOGS_DIR = "logs"
RESULTS_DIR = "results"
OUTPUT_DIR = "analysis_results"
SCENARIOS = ["baseline", "loss2", "loss5", "delay100"]

# Set plotting style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")

def print_subsection(title):
    print("\n" + "-"*80)
    print(f"  {title}")
    print("-"*80)

def analyze_snapshots(csv_file):
    """Analyze snapshot metrics: latency, jitter, redundancy"""
    try:
        df = pd.read_csv(csv_file)
        if df.empty:
            return None

        results = {
            'file': os.path.basename(csv_file),
            'total_packets': len(df),
            'mean_latency': df['latency_ms'].mean(),
            'median_latency': df['latency_ms'].median(),
            'min_latency': df['latency_ms'].min(),
            'max_latency': df['latency_ms'].max(),
            'p95_latency': df['latency_ms'].quantile(0.95),
            'std_latency': df['latency_ms'].std(),
            'mean_jitter': df['jitter_ms'].mean(),
            'median_jitter': df['jitter_ms'].median(),
            'max_jitter': df['jitter_ms'].max(),
            'p95_jitter': df['jitter_ms'].quantile(0.95),
            'std_jitter': df['jitter_ms'].std(),
            'mean_redundancy': df['redundancy_used'].mean(),
        }
        return results
    except Exception as e:
        print(f"  ⚠️  Error analyzing {csv_file}: {e}")
        return None

def analyze_diagnostics(csv_file):
    """Analyze diagnostics: packet loss, duplicates"""
    try:
        df = pd.read_csv(csv_file)
        if df.empty:
            return None

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
    except Exception as e:
        print(f"  ⚠️  Error analyzing {csv_file}: {e}")
        return None

def analyze_server_snapshots():
    """Analyze server snapshot CSV files"""
    try:
        server_files = glob.glob(f"{RESULTS_DIR}/server_snapshots*.csv")
        if not server_files:
            return None

        all_data = []
        for f in server_files:
            df = pd.read_csv(f)
            all_data.append(df)

        combined = pd.concat(all_data, ignore_index=True)

        results = {
            'total_snapshots_sent': len(combined),
            'mean_cpu': combined['cpu_percent'].mean(),
            'max_cpu': combined['cpu_percent'].max(),
            'mean_payload_bytes': combined['payload_bytes'].mean(),
            'total_clients': combined['clients_count'].max(),
        }
        return results
    except Exception as e:
        print(f"  ⚠️  Error analyzing server snapshots: {e}")
        return None

def find_scenario_files(scenario):
    """Find all CSV files for a given scenario (all clients, all runs)"""
    # Pattern matches: client_<pid>_snapshots_<scenario>_<timestamp>.csv
    pattern = f"{LOGS_DIR}/client*_snapshots_{scenario}_*.csv"
    snapshot_files = sorted(glob.glob(pattern))

    diag_files = []
    for snap in snapshot_files:
        diag = snap.replace('_snapshots_', '_diagnostics_')
        if os.path.exists(diag):
            diag_files.append(diag)

    return snapshot_files, diag_files

def analyze_scenario(scenario):
    """Analyze all runs and all clients of a specific scenario"""
    print_section(f"Analyzing Scenario: {scenario.upper()}")

    snapshot_files, diag_files = find_scenario_files(scenario)

    if not snapshot_files:
        print(f"  ⚠️  No files found for scenario: {scenario}")
        print(f"     Looking for pattern: {LOGS_DIR}/client*_snapshots_{scenario}_*.csv")
        return None

    print(f"  Found {len(snapshot_files)} client log file(s) for {scenario}\n")

    # Analyze each client file
    snapshot_results = []
    diag_results = []

    for i, (snap_file, diag_file) in enumerate(zip(snapshot_files, diag_files), 1):
        snap_res = analyze_snapshots(snap_file)
        diag_res = analyze_diagnostics(diag_file)

        if snap_res and diag_res:
            snapshot_results.append(snap_res)
            diag_results.append(diag_res)

    if not snapshot_results:
        print(f"  ⚠️  No valid data found for {scenario}")
        return None

    # Calculate aggregate statistics across all runs and clients
    snap_df = pd.DataFrame(snapshot_results)
    diag_df = pd.DataFrame(diag_results)

    aggregate = {
        'scenario': scenario,
        'num_files': len(snapshot_files),

        # Latency stats (mean of means, median of medians, etc.)
        'mean_latency': snap_df['mean_latency'].mean(),
        'median_latency': snap_df['median_latency'].median(),
        'min_latency': snap_df['min_latency'].min(),
        'max_latency': snap_df['max_latency'].max(),
        'p95_latency': snap_df['p95_latency'].mean(),
        'std_latency': snap_df['std_latency'].mean(),

        # Jitter stats
        'mean_jitter': snap_df['mean_jitter'].mean(),
        'median_jitter': snap_df['median_jitter'].median(),
        'max_jitter': snap_df['max_jitter'].max(),
        'p95_jitter': snap_df['p95_jitter'].mean(),
        'std_jitter': snap_df['std_jitter'].mean(),

        # Packet stats
        'total_packets': snap_df['total_packets'].sum(),
        'packet_loss_rate': diag_df['packet_loss_rate'].mean(),
        'delivery_rate': diag_df['delivery_rate'].mean(),
        'duplicate_rate': diag_df['duplicate_rate'].mean(),
        'mean_redundancy': snap_df['mean_redundancy'].mean(),

        # Ranges for reporting (min, median, max)
        'latency_range': f"{snap_df['min_latency'].min():.2f} / {snap_df['median_latency'].median():.2f} / {snap_df['max_latency'].max():.2f}",
        'jitter_range': f"{snap_df['min_latency'].min():.2f} / {snap_df['median_jitter'].median():.2f} / {snap_df['max_jitter'].max():.2f}",
    }

    # Print detailed summary
    print_subsection(f"{scenario.upper()} Summary (across {len(snapshot_files)} file(s))")
    print(f"  Latency (ms):")
    print(f"    Mean:        {aggregate['mean_latency']:>8.2f} ms  (±{aggregate['std_latency']:.2f})")
    print(f"    Median:      {aggregate['median_latency']:>8.2f} ms")
    print(f"    Range:       {aggregate['min_latency']:>8.2f} - {aggregate['max_latency']:.2f} ms")
    print(f"    95th %ile:   {aggregate['p95_latency']:>8.2f} ms")

    print(f"\n  Jitter (ms):")
    print(f"    Mean:        {aggregate['mean_jitter']:>8.2f} ms  (±{aggregate['std_jitter']:.2f})")
    print(f"    Median:      {aggregate['median_jitter']:>8.2f} ms")
    print(f"    Max:         {aggregate['max_jitter']:>8.2f} ms")
    print(f"    95th %ile:   {aggregate['p95_jitter']:>8.2f} ms")

    print(f"\n  Packet Statistics:")
    print(f"    Total packets:   {aggregate['total_packets']:>10,}")
    print(f"    Delivery rate:   {aggregate['delivery_rate']:>10.2f}%")
    print(f"    Loss rate:       {aggregate['packet_loss_rate']:>10.2f}%")
    print(f"    Duplicate rate:  {aggregate['duplicate_rate']:>10.2f}%")
    print(f"    Avg redundancy:  {aggregate['mean_redundancy']:>10.2f}")

    # Check against acceptance criteria
    check_acceptance_criteria(scenario, aggregate)

    return aggregate

def check_acceptance_criteria(scenario, aggregate):
    """Check if results meet Project 2 acceptance criteria"""
    print(f"\n  Acceptance Criteria Check:")

    if scenario == 'baseline':
        latency_ok = aggregate['mean_latency'] <= 50
        delivery_ok = aggregate['delivery_rate'] >= 99

        print(f"    Average latency ≤50ms:  {'✓ PASS' if latency_ok else '✗ FAIL':>10}  ({aggregate['mean_latency']:.2f} ms)")
        print(f"    Delivery rate ≥99%:     {'✓ PASS' if delivery_ok else '✗ FAIL':>10}  ({aggregate['delivery_rate']:.2f}%)")

    elif scenario == 'loss2':
        # Position error would need separate calculation - placeholder check
        delivery_ok = aggregate['delivery_rate'] >= 98
        print(f"    Graceful degradation:   {'✓ PASS' if delivery_ok else '✗ FAIL':>10}  ({aggregate['delivery_rate']:.2f}% delivery)")

    elif scenario == 'loss5':
        delivery_ok = aggregate['delivery_rate'] >= 95
        stable = aggregate['mean_latency'] < 200

        print(f"    Delivery rate ≥95%:     {'✓ PASS' if delivery_ok else '✗ FAIL':>10}  ({aggregate['delivery_rate']:.2f}%)")
        print(f"    System stable:          {'✓ PASS' if stable else '✗ FAIL':>10}  ({aggregate['mean_latency']:.2f} ms)")

    elif scenario == 'delay100':
        latency_ok = aggregate['mean_latency'] >= 100
        stable = aggregate['delivery_rate'] >= 95

        print(f"    Latency reflects delay: {'✓ PASS' if latency_ok else '✗ FAIL':>10}  ({aggregate['mean_latency']:.2f} ms)")
        print(f"    System continues:       {'✓ PASS' if stable else '✗ FAIL':>10}  ({aggregate['delivery_rate']:.2f}% delivery)")

def save_summary_csv(all_results):
    """Save summary results to CSV"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = pd.DataFrame(all_results)
    output_file = f"{OUTPUT_DIR}/summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(output_file, index=False)

    print(f"\n  ✓ Summary saved to: {output_file}")
    return output_file

def generate_comparison_table(all_results):
    """Generate comparison table across scenarios"""
    print_section("COMPARISON TABLE: All Scenarios")

    if not all_results:
        print("  ⚠️  No results to compare")
        return

    df = pd.DataFrame(all_results)

    # Print formatted table
    print(f"{'Scenario':<12} | {'Latency (ms)':<20} | {'Jitter (ms)':<15} | {'Delivery %':<12} | {'Loss %':<10}")
    print("-" * 80)

    for _, row in df.iterrows():
        print(f"{row['scenario']:<12} | "
              f"{row['mean_latency']:>6.2f} ± {row['std_latency']:>5.2f}     | "
              f"{row['mean_jitter']:>6.2f} (p95:{row['p95_jitter']:>5.1f}) | "
              f"{row['delivery_rate']:>10.2f}% | "
              f"{row['packet_loss_rate']:>8.2f}%")

    print()

def create_plots(all_results):
    """Generate visualization plots"""
    if not all_results:
        return

    print_subsection("Generating Plots")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = pd.DataFrame(all_results)

    # Plot 1: Latency comparison
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    scenarios = df['scenario'].values
    x_pos = np.arange(len(scenarios))

    # Latency
    axes[0].bar(x_pos, df['mean_latency'], yerr=df['std_latency'], 
                capsize=5, color='steelblue', alpha=0.7)
    axes[0].set_xlabel('Scenario', fontsize=12)
    axes[0].set_ylabel('Latency (ms)', fontsize=12)
    axes[0].set_title('Average Latency by Scenario', fontsize=14, fontweight='bold')
    axes[0].set_xticks(x_pos)
    axes[0].set_xticklabels(scenarios)
    axes[0].grid(axis='y', alpha=0.3)

    # Jitter
    axes[1].bar(x_pos, df['mean_jitter'], yerr=df['std_jitter'], 
                capsize=5, color='coral', alpha=0.7)
    axes[1].set_xlabel('Scenario', fontsize=12)
    axes[1].set_ylabel('Jitter (ms)', fontsize=12)
    axes[1].set_title('Average Jitter by Scenario', fontsize=14, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels(scenarios)
    axes[1].grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plot1_file = f"{OUTPUT_DIR}/latency_jitter_comparison.png"
    plt.savefig(plot1_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Saved: {plot1_file}")

    # Plot 2: Packet delivery and loss
    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(scenarios))
    width = 0.35

    ax.bar(x - width/2, df['delivery_rate'], width, label='Delivery Rate', 
           color='green', alpha=0.7)
    ax.bar(x + width/2, df['packet_loss_rate'], width, label='Loss Rate', 
           color='red', alpha=0.7)

    ax.set_xlabel('Scenario', fontsize=12)
    ax.set_ylabel('Percentage (%)', fontsize=12)
    ax.set_title('Packet Delivery and Loss Rates', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plot2_file = f"{OUTPUT_DIR}/delivery_loss_comparison.png"
    plt.savefig(plot2_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Saved: {plot2_file}")

    # Plot 3: Combined metrics
    fig, ax = plt.subplots(figsize=(12, 6))

    metrics_data = {
        'Latency (ms)': df['mean_latency'].values,
        'Jitter (ms)': df['mean_jitter'].values,
        'Loss Rate (%)': df['packet_loss_rate'].values
    }

    x = np.arange(len(scenarios))
    width = 0.25
    multiplier = 0

    for metric, values in metrics_data.items():
        offset = width * multiplier
        ax.bar(x + offset, values, width, label=metric, alpha=0.8)
        multiplier += 1

    ax.set_xlabel('Scenario', fontsize=12)
    ax.set_ylabel('Value', fontsize=12)
    ax.set_title('Combined Metrics Comparison', fontsize=14, fontweight='bold')
    ax.set_xticks(x + width)
    ax.set_xticklabels(scenarios)
    ax.legend(loc='upper left')
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plot3_file = f"{OUTPUT_DIR}/combined_metrics.png"
    plt.savefig(plot3_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Saved: {plot3_file}")

def main():
    print_section("GSync v2 - Enhanced Test Results Analysis")

    print(f"  Configuration:")
    print(f"    Client logs:   {LOGS_DIR}/")
    print(f"    Server CSVs:   {RESULTS_DIR}/")
    print(f"    Output:        {OUTPUT_DIR}/")
    print(f"    Scenarios:     {', '.join(SCENARIOS)}")

    # Check if directories exist
    if not os.path.exists(LOGS_DIR):
        print(f"\n  ❌ ERROR: Client logs directory not found: {LOGS_DIR}/")
        print(f"     Run tests first: sudo ./run_tests_enhanced.sh")
        return

    # Analyze server data
    print_subsection("Server Statistics")
    server_stats = analyze_server_snapshots()
    if server_stats:
        print(f"  Total snapshots sent:  {server_stats['total_snapshots_sent']:>10,}")
        print(f"  Mean CPU usage:        {server_stats['mean_cpu']:>10.2f}%")
        print(f"  Max CPU usage:         {server_stats['max_cpu']:>10.2f}%")
        print(f"  Avg payload size:      {server_stats['mean_payload_bytes']:>10.1f} bytes")
        print(f"  Max concurrent clients:{server_stats['total_clients']:>10}")
    else:
        print("  ⚠️  No server data found")

    # Analyze each scenario
    all_results = []
    for scenario in SCENARIOS:
        result = analyze_scenario(scenario)
        if result:
            all_results.append(result)

    # Generate comparison and save results
    if all_results:
        generate_comparison_table(all_results)
        save_summary_csv(all_results)
        create_plots(all_results)
    else:
        print("\n  ⚠️  No test results found!")
        print("     Run tests first: sudo ./run_tests_enhanced.sh")

    print_section("Analysis Complete!")

    if all_results:
        print("  Generated outputs:")
        print(f"    • Summary CSV in {OUTPUT_DIR}/")
        print(f"    • Comparison plots in {OUTPUT_DIR}/")
        print()
        print("  Next steps:")
        print("    1. Review plots and summary CSV")
        print("    2. Include plots in your technical report")
        print("    3. Document methodology and interpretation")
        print("    4. Check acceptance criteria results")

    print()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()