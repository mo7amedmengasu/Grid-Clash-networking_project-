"""
GSync v2 - Test Results Analysis for Phase 2 Report
Generates analysis plots and summary CSV
"""

import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# Configuration
LOGS_DIR = "logs"
OUTPUT_DIR = "analysis_results"
SCENARIOS = ["baseline", "loss2", "loss5", "delay100"]
SCENARIO_LABELS = {
    "baseline": "Baseline",
    "loss2": "2% Loss",
    "loss5": "5% Loss", 
    "delay100": "100ms Delay"
}

# Plot styling
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 11
COLORS = ['#2ecc71', '#3498db', '#e74c3c', '#9b59b6']


def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def analyze_snapshots(csv_file):
    """Analyze snapshot metrics from a single CSV file"""
    try:
        df = pd.read_csv(csv_file)
        if df.empty:
            return None
        return {
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
            'latency_values': df['latency_ms'].values,
            'jitter_values': df['jitter_ms'].values,
        }
    except Exception as e:
        return None


def analyze_diagnostics(csv_file):
    """Analyze diagnostics from a single CSV file"""
    try:
        df = pd.read_csv(csv_file)
        if df.empty:
            return None
        final = df.iloc[-1]
        packets = final['packets_received']
        gaps = final['sequence_gaps']
        return {
            'total_packets_received': packets,
            'sequence_gaps': gaps,
            'packet_loss_rate': (gaps / packets * 100) if packets > 0 else 0,
            'delivery_rate': 100 - (gaps / packets * 100) if packets > 0 else 100,
        }
    except Exception as e:
        return None


def analyze_scenario(scenario):
    """Analyze all data for a scenario"""
    pattern = f"{LOGS_DIR}/client*_snapshots_{scenario}_*.csv"
    snapshot_files = sorted(glob.glob(pattern))
    
    if not snapshot_files:
        return None

    snapshot_results = []
    diag_results = []
    all_latencies = []
    all_jitters = []

    for snap_file in snapshot_files:
        diag_file = snap_file.replace('_snapshots_', '_diagnostics_')
        
        snap_res = analyze_snapshots(snap_file)
        diag_res = analyze_diagnostics(diag_file) if os.path.exists(diag_file) else None
        
        if snap_res:
            snapshot_results.append(snap_res)
            all_latencies.extend(snap_res['latency_values'])
            all_jitters.extend(snap_res['jitter_values'])
        if diag_res:
            diag_results.append(diag_res)

    if not snapshot_results:
        return None

    snap_df = pd.DataFrame(snapshot_results)
    
    result = {
        'scenario': scenario,
        'label': SCENARIO_LABELS[scenario],
        'num_files': len(snapshot_files),
        'mean_latency': snap_df['mean_latency'].mean(),
        'median_latency': snap_df['median_latency'].median(),
        'min_latency': snap_df['min_latency'].min(),
        'max_latency': snap_df['max_latency'].max(),
        'p95_latency': snap_df['p95_latency'].mean(),
        'std_latency': snap_df['std_latency'].mean(),
        'mean_jitter': snap_df['mean_jitter'].mean(),
        'median_jitter': snap_df['median_jitter'].median(),
        'max_jitter': snap_df['max_jitter'].max(),
        'p95_jitter': snap_df['p95_jitter'].mean(),
        'std_jitter': snap_df['std_jitter'].mean(),
        'total_packets': snap_df['total_packets'].sum(),
        'all_latencies': np.array(all_latencies),
        'all_jitters': np.array(all_jitters),
    }
    
    if diag_results:
        diag_df = pd.DataFrame(diag_results)
        result['packet_loss_rate'] = diag_df['packet_loss_rate'].mean()
        result['delivery_rate'] = diag_df['delivery_rate'].mean()
    else:
        result['packet_loss_rate'] = 0
        result['delivery_rate'] = 100
    
    return result


def create_plots(all_results):
    """Generate all plots"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = pd.DataFrame(all_results)
    scenarios = df['scenario'].values
    labels = [SCENARIO_LABELS[s] for s in scenarios]
    x = np.arange(len(scenarios))

    # Plot 1: Latency Bar Chart
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(x, df['mean_latency'], yerr=df['std_latency'], 
                  capsize=5, color=COLORS, alpha=0.8, edgecolor='black')
    ax.set_xlabel('Test Scenario', fontsize=12)
    ax.set_ylabel('Latency (ms)', fontsize=12)
    ax.set_title('Average Latency by Scenario', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.axhline(y=50, color='red', linestyle='--', label='Target (50ms)')
    ax.legend()
    for i, bar in enumerate(bars):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + df['std_latency'].iloc[i] + 1,
                f'{df["mean_latency"].iloc[i]:.1f}', ha='center', va='bottom', fontsize=10)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/latency_comparison.png", dpi=300)
    plt.close()
    print(f"  ✓ latency_comparison.png")

    # Plot 2: Jitter Bar Chart
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(x, df['mean_jitter'], yerr=df['std_jitter'],
                  capsize=5, color=COLORS, alpha=0.8, edgecolor='black')
    ax.set_xlabel('Test Scenario', fontsize=12)
    ax.set_ylabel('Jitter (ms)', fontsize=12)
    ax.set_title('Average Jitter by Scenario', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    for i, bar in enumerate(bars):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + df['std_jitter'].iloc[i] + 0.2,
                f'{df["mean_jitter"].iloc[i]:.1f}', ha='center', va='bottom', fontsize=10)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/jitter_comparison.png", dpi=300)
    plt.close()
    print(f"  ✓ jitter_comparison.png")

    # Plot 3: Delivery Rate
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(x, df['delivery_rate'], color=COLORS, alpha=0.8, edgecolor='black')
    ax.set_xlabel('Test Scenario', fontsize=12)
    ax.set_ylabel('Delivery Rate (%)', fontsize=12)
    ax.set_title('Packet Delivery Rate by Scenario', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(90, 101)
    ax.axhline(y=99, color='red', linestyle='--', label='Target (99%)')
    ax.legend()
    for i, bar in enumerate(bars):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                f'{df["delivery_rate"].iloc[i]:.1f}%', ha='center', va='bottom', fontsize=10)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/delivery_rate.png", dpi=300)
    plt.close()
    print(f"  ✓ delivery_rate.png")

    # Plot 4: Packet Loss Rate
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(x, df['packet_loss_rate'], color=['green', 'orange', 'red', 'blue'], 
                  alpha=0.8, edgecolor='black')
    ax.set_xlabel('Test Scenario', fontsize=12)
    ax.set_ylabel('Packet Loss Rate (%)', fontsize=12)
    ax.set_title('Packet Loss Rate by Scenario', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    for i, bar in enumerate(bars):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f'{df["packet_loss_rate"].iloc[i]:.2f}%', ha='center', va='bottom', fontsize=10)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/packet_loss.png", dpi=300)
    plt.close()
    print(f"  ✓ packet_loss.png")

    # Plot 5: Latency Box Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    latency_data = [r['all_latencies'] for r in all_results]
    bp = ax.boxplot(latency_data, labels=labels, patch_artist=True)
    for patch, color in zip(bp['boxes'], COLORS):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xlabel('Test Scenario', fontsize=12)
    ax.set_ylabel('Latency (ms)', fontsize=12)
    ax.set_title('Latency Distribution by Scenario', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/latency_boxplot.png", dpi=300)
    plt.close()
    print(f"  ✓ latency_boxplot.png")

    # Plot 6: Combined Summary (2x2)
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    axes[0, 0].bar(x, df['mean_latency'], color=COLORS, alpha=0.8)
    axes[0, 0].set_title('Mean Latency (ms)', fontweight='bold')
    axes[0, 0].set_xticks(x)
    axes[0, 0].set_xticklabels(labels)
    axes[0, 0].axhline(y=50, color='red', linestyle='--', alpha=0.7)
    
    axes[0, 1].bar(x, df['mean_jitter'], color=COLORS, alpha=0.8)
    axes[0, 1].set_title('Mean Jitter (ms)', fontweight='bold')
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(labels)
    
    axes[1, 0].bar(x, df['delivery_rate'], color=COLORS, alpha=0.8)
    axes[1, 0].set_title('Delivery Rate (%)', fontweight='bold')
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels(labels)
    axes[1, 0].set_ylim(90, 101)
    
    axes[1, 1].bar(x, df['packet_loss_rate'], color=COLORS, alpha=0.8)
    axes[1, 1].set_title('Packet Loss Rate (%)', fontweight='bold')
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(labels)
    
    plt.suptitle('GSync v2 Protocol Performance Summary', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/combined_summary.png", dpi=300)
    plt.close()
    print(f"  ✓ combined_summary.png")


def save_summary(all_results):
    """Save single summary CSV"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    rows = []
    for r in all_results:
        rows.append({
            'Scenario': r['label'],
            'Files': r['num_files'],
            'Packets': r['total_packets'],
            'Mean_Latency_ms': round(r['mean_latency'], 2),
            'Median_Latency_ms': round(r['median_latency'], 2),
            'P95_Latency_ms': round(r['p95_latency'], 2),
            'Std_Latency_ms': round(r['std_latency'], 2),
            'Mean_Jitter_ms': round(r['mean_jitter'], 2),
            'P95_Jitter_ms': round(r['p95_jitter'], 2),
            'Delivery_Rate_%': round(r['delivery_rate'], 2),
            'Loss_Rate_%': round(r['packet_loss_rate'], 2),
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUTPUT_DIR}/summary.csv", index=False)
    print(f"  ✓ summary.csv")


def main():
    print_section("GSync v2 - Results Analysis")
    
    if not os.path.exists(LOGS_DIR):
        print(f"  ERROR: Logs directory not found: {LOGS_DIR}/")
        return
    
    # Analyze all scenarios
    all_results = []
    for scenario in SCENARIOS:
        print(f"  Analyzing {scenario}...", end=" ")
        result = analyze_scenario(scenario)
        if result:
            all_results.append(result)
            print(f"OK ({result['num_files']} files)")
        else:
            print("No data")
    
    if not all_results:
        print("\n  ERROR: No test results found!")
        return
    
    print_section("Generating Outputs")
    create_plots(all_results)
    save_summary(all_results)
    
    # Print summary table
    print_section("Results Summary")
    print(f"  {'Scenario':<15} {'Latency':<12} {'Jitter':<12} {'Delivery':<12} {'Loss':<10}")
    print("  " + "-" * 60)
    for r in all_results:
        print(f"  {r['label']:<15} {r['mean_latency']:<12.2f} {r['mean_jitter']:<12.2f} "
              f"{r['delivery_rate']:<12.2f} {r['packet_loss_rate']:<10.2f}")
    
    print(f"\n  Output saved to: {OUTPUT_DIR}/")
    print("  Done!\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
