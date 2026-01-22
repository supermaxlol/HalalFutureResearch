#!/usr/bin/env python3
"""
Generate Publication-Quality Figures v2
=======================================
Fixed version with:
- Consistent color theme across ALL figures
- Full data usage
- Correct 0.03%/day (0.01%/8h) interest rate representation
- Extended Hyperliquid data fetch
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from datetime import datetime, timedelta
import json
import os
import requests
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_DIR = "/Users/shehzad/Desktop/Halalfuture/funding_data"
OUTPUT_DIR = "/Users/shehzad/Desktop/Halalfuture"

# UNIFIED COLOR SCHEME
COLORS = {
    # CEX - Red tones
    'binance': '#E53935',      # Red
    'bybit': '#FF7043',        # Deep Orange
    'cex': '#C62828',          # Dark Red (aggregate)

    # DEX - Green/Teal tones
    'dydx': '#00897B',         # Teal
    'hyperliquid': '#43A047',  # Green
    'dex': '#2E7D32',          # Dark Green (aggregate)

    # Neutral
    'interest_line': '#B71C1C',  # Very dark red for interest floor
    'zero_line': '#424242',      # Dark gray
    'grid': '#E0E0E0',           # Light gray
}

# Figure style
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['figure.titlesize'] = 14
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.alpha'] = 0.3
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['savefig.facecolor'] = 'white'
plt.rcParams['savefig.edgecolor'] = 'white'


# ============================================================================
# FETCH EXTENDED HYPERLIQUID DATA
# ============================================================================

def fetch_extended_hyperliquid(coin: str, days: int = 90) -> pd.DataFrame:
    """Fetch extended Hyperliquid data with pagination to get full 90 days."""
    print(f"  Fetching extended Hyperliquid {coin} data...")

    url = "https://api.hyperliquid.xyz/info"
    all_records = []

    # Start from 90 days ago
    current_start = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    end_time = int(datetime.now().timestamp() * 1000)

    max_iterations = 10  # Safety limit
    iteration = 0

    try:
        while current_start < end_time and iteration < max_iterations:
            payload = {
                "type": "fundingHistory",
                "coin": coin,
                "startTime": current_start
            }
            response = requests.post(url, json=payload, timeout=60)
            data = response.json()

            if not data or len(data) == 0:
                break

            all_records.extend(data)

            # Get the latest timestamp and continue from there
            last_time = max(int(d['time']) for d in data)

            # If we didn't get new data, break
            if last_time <= current_start:
                break

            current_start = last_time + 1  # Start from the next millisecond
            iteration += 1

            print(f"    -> Batch {iteration}: {len(data)} records (total: {len(all_records)})")

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        if all_records:
            # Remove duplicates by time
            seen = set()
            unique_records = []
            for r in all_records:
                if r['time'] not in seen:
                    seen.add(r['time'])
                    unique_records.append(r)

            df = pd.DataFrame(unique_records)
            df['fundingTime'] = pd.to_datetime(df['time'], unit='ms')
            df['fundingRate'] = df['fundingRate'].astype(float)
            df['symbol'] = coin
            df['source'] = 'hyperliquid'
            df['type'] = 'DEX'
            df = df.sort_values('fundingTime').reset_index(drop=True)
            print(f"    -> Total: {len(df)} unique records over {(df['fundingTime'].max() - df['fundingTime'].min()).days} days")
            return df

    except Exception as e:
        print(f"    Error: {e}")

    return pd.DataFrame()


# ============================================================================
# LOAD ALL DATA
# ============================================================================

def load_all_data():
    """Load all data and fetch extended Hyperliquid if needed."""
    print("\n" + "=" * 60)
    print("LOADING DATA")
    print("=" * 60)

    data = {}
    files = os.listdir(DATA_DIR)

    # Load existing CSV files
    for key in ['binance_btc', 'binance_eth', 'bybit_btc', 'bybit_eth',
                'dydx_btc', 'dydx_eth', 'hyperliquid_btc', 'hyperliquid_eth']:
        matching = [f for f in files if f.startswith(f'extended_{key}') and f.endswith('.csv')]
        if matching:
            latest = sorted(matching)[-1]
            df = pd.read_csv(os.path.join(DATA_DIR, latest))
            df['fundingTime'] = pd.to_datetime(df['fundingTime'], format='mixed', utc=True)
            df['fundingTime'] = df['fundingTime'].dt.tz_localize(None)  # Remove timezone for plotting
            data[key] = df
            print(f"  Loaded {key}: {len(df)} records, date range: {df['fundingTime'].min()} to {df['fundingTime'].max()}")

    # Check if Hyperliquid data is short, try to extend it
    for key in ['hyperliquid_btc', 'hyperliquid_eth']:
        if key in data and len(data[key]) < 1000:
            coin = 'BTC' if 'btc' in key else 'ETH'
            extended = fetch_extended_hyperliquid(coin, days=90)
            if not extended.empty and len(extended) > len(data[key]):
                data[key] = extended
                print(f"  Extended {key}: now {len(extended)} records")

    # Load stats
    stats_file = os.path.join(DATA_DIR, 'statistical_analysis.json')
    if os.path.exists(stats_file):
        with open(stats_file) as f:
            data['stats'] = json.load(f)

    return data


# ============================================================================
# NORMALIZE DATA TO SAME TIME RANGE
# ============================================================================

def get_common_date_range(data):
    """Find common date range across all datasets."""
    min_dates = []
    max_dates = []

    for key, df in data.items():
        if isinstance(df, pd.DataFrame) and 'fundingTime' in df.columns:
            min_dates.append(df['fundingTime'].min())
            max_dates.append(df['fundingTime'].max())

    if min_dates and max_dates:
        return max(min_dates), min(max_dates)
    return None, None


# ============================================================================
# FIGURE 1: INTEREST RATE EVIDENCE
# ============================================================================

def fig1_interest_evidence():
    """Visual representation of the Binance API interestRate field."""
    print("\n  Generating: fig_interest_evidence")

    fig, ax = plt.subplots(figsize=(7, 4.5))

    # API Response visualization
    api_fields = [
        ('symbol', '"BTCUSDT"', COLORS['zero_line']),
        ('markPrice', '"95,066.54"', COLORS['zero_line']),
        ('indexPrice', '"95,109.26"', COLORS['zero_line']),
        ('lastFundingRate', '"0.00005102"', COLORS['zero_line']),
        ('interestRate', '"0.00010000"', COLORS['cex']),
    ]

    ax.set_xlim(0, 12)
    ax.set_ylim(0, len(api_fields) + 2)

    # Title box
    ax.text(6, len(api_fields) + 1.3, 'Binance API: /fapi/v1/premiumIndex',
            fontsize=12, fontweight='bold', ha='center',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#ECEFF1', edgecolor='#90A4AE'))

    # JSON bracket
    ax.text(0.5, len(api_fields) + 0.5, '{', fontsize=14, family='monospace')
    ax.text(0.5, 0.5, '}', fontsize=14, family='monospace')

    for i, (field, value, color) in enumerate(api_fields):
        y = len(api_fields) - i

        weight = 'bold' if field == 'interestRate' else 'normal'
        size = 11 if field == 'interestRate' else 10

        # Field name and value
        ax.text(1.2, y, f'"{field}":', fontsize=size, fontweight=weight,
                color=color, family='monospace')
        ax.text(5.5, y, value, fontsize=size, fontweight=weight,
                color=color, family='monospace')

        if field == 'interestRate':
            # Highlight box
            rect = plt.Rectangle((0.8, y-0.35), 10, 0.7, fill=True,
                                 facecolor='#FFEBEE', edgecolor=COLORS['cex'],
                                 linewidth=2, alpha=0.8)
            ax.add_patch(rect)

            # Re-draw text on top
            ax.text(1.2, y, f'"{field}":', fontsize=size, fontweight=weight,
                    color=COLORS['cex'], family='monospace', zorder=10)
            ax.text(5.5, y, value, fontsize=size, fontweight=weight,
                    color=COLORS['cex'], family='monospace', zorder=10)

            # Annotation
            ax.annotate('', xy=(10.5, y), xytext=(8.5, y),
                       arrowprops=dict(arrowstyle='->', color=COLORS['cex'], lw=2))
            ax.text(10.7, y+0.3, 'EXPLICIT RIBA', fontsize=10, fontweight='bold',
                    color=COLORS['cex'])
            ax.text(10.7, y-0.3, '0.01%/8h = 0.03%/day', fontsize=9,
                    color=COLORS['cex'])

    ax.axis('off')

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_interest_evidence.pdf'), format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_interest_evidence.png'), format='png', bbox_inches='tight', dpi=300)
    plt.close()


# ============================================================================
# FIGURE 2: TIME SERIES (FULL DATA)
# ============================================================================

def fig2_timeseries(data):
    """Time series showing funding rates over time."""
    print("\n  Generating: fig_funding_timeseries")

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    # Get date range for x-axis
    start_date, end_date = get_common_date_range(data)

    for idx, asset in enumerate(['btc', 'eth']):
        ax = axes[idx]
        ax.set_title(f'{asset.upper()} Perpetual Funding Rates', fontweight='bold', fontsize=12)

        # Plot each platform
        platforms = [
            (f'binance_{asset}', 'Binance', COLORS['binance'], '-', 2),
            (f'bybit_{asset}', 'Bybit', COLORS['bybit'], '-', 2),
            (f'dydx_{asset}', 'dYdX', COLORS['dydx'], '-', 1.5),
            (f'hyperliquid_{asset}', 'Hyperliquid', COLORS['hyperliquid'], '-', 1.5),
        ]

        for key, label, color, style, lw in platforms:
            if key in data and not data[key].empty:
                df = data[key].copy()
                # Resample hourly data to 8h for fair visual comparison
                if 'dydx' in key or 'hyperliquid' in key:
                    df['fundingRate'] = pd.to_numeric(df['fundingRate'], errors='coerce')
                    df = df[['fundingTime', 'fundingRate']].set_index('fundingTime').resample('8h').mean().reset_index()
                    df = df.dropna()

                ax.plot(df['fundingTime'], df['fundingRate'].astype(float) * 100,
                       color=color, linestyle=style, linewidth=lw,
                       label=f'{label} ({"CEX" if "binance" in key or "bybit" in key else "DEX"})',
                       alpha=0.85)

        # Interest rate floor line
        ax.axhline(y=0.01, color=COLORS['interest_line'], linestyle='--',
                   linewidth=2.5, label='Interest Floor (0.01%/8h)', zorder=5)
        ax.axhline(y=0, color=COLORS['zero_line'], linestyle='-', linewidth=1, alpha=0.5)

        ax.set_ylabel('Funding Rate (%)')
        ax.legend(loc='upper right', fontsize=8, ncol=2)
        ax.grid(True, alpha=0.3, color=COLORS['grid'])
        ax.set_ylim(-0.015, 0.025)

    axes[1].set_xlabel('Date')

    # Add annotation about interest
    fig.text(0.5, 0.02,
             'CEX Interest Component: 0.01% per 8-hour interval = 0.03% daily = 10.95% annually',
             ha='center', fontsize=9, style='italic', color=COLORS['cex'])

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_funding_timeseries.pdf'), format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_funding_timeseries.png'), format='png', bbox_inches='tight', dpi=300)
    plt.close()


# ============================================================================
# FIGURE 3: DISTRIBUTION HISTOGRAM
# ============================================================================

def fig3_distribution(data):
    """Distribution comparison."""
    print("\n  Generating: fig_funding_distribution")

    fig, ax = plt.subplots(figsize=(8, 5))

    # Aggregate data
    cex_rates = []
    dex_rates = []

    for key, df in data.items():
        if isinstance(df, pd.DataFrame) and 'fundingRate' in df.columns:
            rates = df['fundingRate'].astype(float) * 100
            if 'binance' in key or 'bybit' in key:
                cex_rates.extend(rates.tolist())
            elif 'dydx' in key or 'hyperliquid' in key:
                dex_rates.extend(rates.tolist())

    # Create histogram
    bins = np.linspace(-0.02, 0.025, 60)

    ax.hist(cex_rates, bins=bins, alpha=0.65, color=COLORS['cex'],
            label=f'CEX - Binance & Bybit (n={len(cex_rates):,})',
            density=True, edgecolor='white', linewidth=0.5)
    ax.hist(dex_rates, bins=bins, alpha=0.65, color=COLORS['dex'],
            label=f'DEX - dYdX & Hyperliquid (n={len(dex_rates):,})',
            density=True, edgecolor='white', linewidth=0.5)

    # Add vertical lines
    ax.axvline(x=0.01, color=COLORS['interest_line'], linestyle='--', linewidth=2.5,
               label='Interest Rate (0.01%/8h)')
    ax.axvline(x=0, color=COLORS['zero_line'], linestyle='-', linewidth=1.5, alpha=0.7)

    # Add means
    cex_mean = np.mean(cex_rates)
    dex_mean = np.mean(dex_rates)
    ax.axvline(x=cex_mean, color=COLORS['cex'], linestyle=':', linewidth=2, alpha=0.8)
    ax.axvline(x=dex_mean, color=COLORS['dex'], linestyle=':', linewidth=2, alpha=0.8)

    # Annotations
    ymax = ax.get_ylim()[1]
    ax.annotate(f'CEX Mean\n{cex_mean:.4f}%', xy=(cex_mean, ymax*0.85),
                fontsize=9, color=COLORS['cex'], ha='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    ax.annotate(f'DEX Mean\n{dex_mean:.4f}%', xy=(dex_mean, ymax*0.65),
                fontsize=9, color=COLORS['dex'], ha='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

    ax.set_title('Funding Rate Distribution: CEX vs DEX', fontweight='bold', fontsize=12)
    ax.set_xlabel('Funding Rate (%)')
    ax.set_ylabel('Density')
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3, color=COLORS['grid'])

    # Stats annotation
    stats = data.get('stats', {})
    if stats:
        stats_text = f"t-test p < 0.001 | Cohen's d = {stats.get('cohens_d', 0):.2f}"
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=9,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='#FFF9C4', alpha=0.9, edgecolor='#FBC02D'))

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_funding_distribution.pdf'), format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_funding_distribution.png'), format='png', bbox_inches='tight', dpi=300)
    plt.close()


# ============================================================================
# FIGURE 4: PLATFORM BOX PLOT
# ============================================================================

def fig4_boxplot(data):
    """Box plot by platform."""
    print("\n  Generating: fig_platform_boxplot")

    fig, ax = plt.subplots(figsize=(9, 5))

    platforms = [
        ('binance_btc', 'Binance\nBTC', COLORS['binance']),
        ('binance_eth', 'Binance\nETH', COLORS['binance']),
        ('bybit_btc', 'Bybit\nBTC', COLORS['bybit']),
        ('bybit_eth', 'Bybit\nETH', COLORS['bybit']),
        ('dydx_btc', 'dYdX\nBTC', COLORS['dydx']),
        ('dydx_eth', 'dYdX\nETH', COLORS['dydx']),
        ('hyperliquid_btc', 'Hyperliquid\nBTC', COLORS['hyperliquid']),
        ('hyperliquid_eth', 'Hyperliquid\nETH', COLORS['hyperliquid']),
    ]

    plot_data = []
    labels = []
    colors = []

    for key, label, color in platforms:
        if key in data and not data[key].empty:
            rates = data[key]['fundingRate'].astype(float) * 100
            plot_data.append(rates.values)
            labels.append(label)
            colors.append(color)

    bp = ax.boxplot(plot_data, labels=labels, patch_artist=True,
                    widths=0.6, showfliers=False)

    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.65)
        patch.set_edgecolor('black')
    for median in bp['medians']:
        median.set_color('black')
        median.set_linewidth(2)
    for whisker in bp['whiskers']:
        whisker.set_color('gray')
    for cap in bp['caps']:
        cap.set_color('gray')

    # Reference lines
    ax.axhline(y=0.01, color=COLORS['interest_line'], linestyle='--',
               linewidth=2.5, label='Interest Floor (0.01%/8h)', zorder=0)
    ax.axhline(y=0, color=COLORS['zero_line'], linestyle='-', linewidth=1, alpha=0.5)

    # CEX/DEX separator
    ax.axvline(x=4.5, color='black', linestyle='-', linewidth=2, alpha=0.3)

    # Labels
    ax.text(2.5, ax.get_ylim()[1]*0.92, 'CEX', ha='center', fontsize=14,
            fontweight='bold', color=COLORS['cex'],
            bbox=dict(boxstyle='round', facecolor='#FFEBEE', alpha=0.8))
    ax.text(6.5, ax.get_ylim()[1]*0.92, 'DEX', ha='center', fontsize=14,
            fontweight='bold', color=COLORS['dex'],
            bbox=dict(boxstyle='round', facecolor='#E8F5E9', alpha=0.8))

    ax.set_title('Funding Rate Distribution by Platform', fontweight='bold', fontsize=12)
    ax.set_ylabel('Funding Rate (%)')
    ax.grid(True, alpha=0.3, axis='y', color=COLORS['grid'])
    ax.legend(loc='lower right', fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_platform_boxplot.pdf'), format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_platform_boxplot.png'), format='png', bbox_inches='tight', dpi=300)
    plt.close()


# ============================================================================
# FIGURE 5: NEGATIVE FUNDING BAR CHART
# ============================================================================

def fig5_negative_funding(data):
    """Bar chart of negative funding frequency."""
    print("\n  Generating: fig_negative_funding")

    fig, ax = plt.subplots(figsize=(8, 5))

    platforms = [
        ('binance_btc', 'Binance', COLORS['binance']),
        ('bybit_btc', 'Bybit', COLORS['bybit']),
        ('dydx_btc', 'dYdX', COLORS['dydx']),
        ('hyperliquid_btc', 'Hyperliquid', COLORS['hyperliquid']),
    ]

    names = []
    neg_pcts = []
    colors = []

    for key, name, color in platforms:
        if key in data and not data[key].empty:
            rates = data[key]['fundingRate'].astype(float)
            neg_pct = (rates < 0).sum() / len(rates) * 100
            names.append(name)
            neg_pcts.append(neg_pct)
            colors.append(color)

    x = np.arange(len(names))
    bars = ax.bar(x, neg_pcts, color=colors, alpha=0.75, edgecolor='black', linewidth=1.5)

    # Value labels
    for bar, pct in zip(bars, neg_pcts):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{pct:.1f}%', ha='center', fontsize=11, fontweight='bold')

    # CEX/DEX divider and labels
    ax.axvline(x=1.5, color='black', linestyle='--', linewidth=1.5, alpha=0.4)

    ax.text(0.5, ax.get_ylim()[1]*0.9, 'CEX', ha='center', fontsize=12,
            fontweight='bold', color=COLORS['cex'],
            bbox=dict(boxstyle='round', facecolor='#FFEBEE', alpha=0.8))
    ax.text(2.5, ax.get_ylim()[1]*0.9, 'DEX', ha='center', fontsize=12,
            fontweight='bold', color=COLORS['dex'],
            bbox=dict(boxstyle='round', facecolor='#E8F5E9', alpha=0.8))

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=11)
    ax.set_title('Negative Funding Rate Frequency (BTC Perpetuals)', fontweight='bold', fontsize=12)
    ax.set_ylabel('% of Intervals with Negative Funding')
    ax.grid(True, alpha=0.3, axis='y', color=COLORS['grid'])

    # Explanation
    ax.text(0.5, -0.12,
            'Higher negative funding % indicates symmetric premium-only mechanism (no interest floor)',
            transform=ax.transAxes, ha='center', fontsize=9, style='italic', color='gray')

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_negative_funding.pdf'), format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_negative_funding.png'), format='png', bbox_inches='tight', dpi=300)
    plt.close()


# ============================================================================
# FIGURE 6: COST COMPARISON
# ============================================================================

def fig6_cost_comparison(data):
    """Annual cost comparison."""
    print("\n  Generating: fig_cost_comparison")

    fig, ax = plt.subplots(figsize=(7, 5))

    stats = data.get('stats', {})
    cex_mean = stats.get('cex_mean', 0.000037)
    dex_mean = stats.get('dex_mean', 0.000008)

    # Calculate annual costs (3 intervals per day * 365 days)
    cex_annual = cex_mean * 3 * 365 * 100
    dex_annual = dex_mean * 3 * 365 * 100
    savings = cex_annual - dex_annual

    categories = ['CEX\n(Binance/Bybit)', 'DEX\n(dYdX/Hyperliquid)', 'Annual\nSavings']
    values = [cex_annual, dex_annual, savings]
    bar_colors = [COLORS['cex'], COLORS['dex'], '#1565C0']

    bars = ax.bar(categories, values, color=bar_colors, alpha=0.75,
                  edgecolor='black', linewidth=1.5)

    # Value labels
    for i, (bar, val) in enumerate(zip(bars, values)):
        label = f'{val:.2f}%'
        if i == 2:
            label = f'+{val:.2f}%'
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15,
                label, ha='center', fontsize=12, fontweight='bold')

    # Dollar amounts
    ax.text(0.5, -0.18,
            f'On $100,000 position: CEX costs ${cex_annual*1000:.0f}/year | DEX costs ${dex_annual*1000:.0f}/year | Save ${savings*1000:.0f}/year',
            transform=ax.transAxes, ha='center', fontsize=10, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='#E3F2FD', alpha=0.9, edgecolor='#1565C0'))

    ax.set_title('Annual Funding Cost for Long Positions', fontweight='bold', fontsize=12)
    ax.set_ylabel('Annual Cost (%)')
    ax.grid(True, alpha=0.3, axis='y', color=COLORS['grid'])
    ax.set_ylim(0, max(values) * 1.25)

    # Interest rate note
    ax.text(0.02, 0.98, 'CEX includes 0.03%/day\nfixed interest rate',
            transform=ax.transAxes, fontsize=9, va='top', color=COLORS['cex'],
            bbox=dict(boxstyle='round', facecolor='#FFEBEE', alpha=0.8))

    plt.tight_layout(rect=[0, 0.08, 1, 1])
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_cost_comparison.pdf'), format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_cost_comparison.png'), format='png', bbox_inches='tight', dpi=300)
    plt.close()


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("GENERATING PUBLICATION-QUALITY FIGURES (v2)")
    print("Consistent color theme + Full data + Correct interest rates")
    print("=" * 70)

    # Load data
    data = load_all_data()

    # Generate figures
    print("\n" + "=" * 60)
    print("GENERATING FIGURES")
    print("=" * 60)

    fig1_interest_evidence()
    fig2_timeseries(data)
    fig3_distribution(data)
    fig4_boxplot(data)
    fig5_negative_funding(data)
    fig6_cost_comparison(data)

    print("\n" + "=" * 70)
    print("ALL FIGURES GENERATED SUCCESSFULLY")
    print("=" * 70)
    print(f"""
Color Scheme:
  CEX (Binance):     {COLORS['binance']}
  CEX (Bybit):       {COLORS['bybit']}
  DEX (dYdX):        {COLORS['dydx']}
  DEX (Hyperliquid): {COLORS['hyperliquid']}
  Interest Floor:    {COLORS['interest_line']}

Files saved to: {OUTPUT_DIR}
    """)


if __name__ == "__main__":
    main()
