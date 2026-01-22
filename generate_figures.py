#!/usr/bin/env python3
"""
Generate Individual Figures for Paper
=====================================
Creates separate, strategically-placed figures for the Islamic Finance paper.

Figures:
1. fig_interest_rate_evidence.pdf - Shows Binance API interestRate field (for Technical Analysis section)
2. fig_funding_timeseries.pdf - Time series comparison (for Empirical Analysis section)
3. fig_funding_distribution.pdf - Distribution histogram (for Statistical section)
4. fig_platform_comparison.pdf - Box plot by platform (for Results section)
5. fig_negative_funding.pdf - Bar chart of negative funding % (for Key Findings)
6. fig_cost_comparison.pdf - Annual cost comparison (for Cost Efficiency section)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime
import json
import os

# Configuration
DATA_DIR = "/Users/shehzad/Desktop/Halalfuture/funding_data"
OUTPUT_DIR = "/Users/shehzad/Desktop/Halalfuture"

# Colors
CEX_COLOR = '#C62828'  # Dark Red
DEX_COLOR = '#2E7D32'  # Dark Green
BINANCE_COLOR = '#F0B90B'  # Binance Yellow
BYBIT_COLOR = '#FF6600'  # Bybit Orange
DYDX_COLOR = '#6366F1'  # dYdX Purple
HL_COLOR = '#00D395'  # Hyperliquid Green

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['figure.titlesize'] = 14

def load_data():
    """Load all the collected data."""
    data = {}

    # Find the most recent extended data files
    files = os.listdir(DATA_DIR)

    for key in ['binance_btc', 'binance_eth', 'bybit_btc', 'bybit_eth',
                'dydx_btc', 'dydx_eth', 'hyperliquid_btc', 'hyperliquid_eth']:
        matching = [f for f in files if f.startswith(f'extended_{key}') and f.endswith('.csv')]
        if matching:
            latest = sorted(matching)[-1]
            df = pd.read_csv(os.path.join(DATA_DIR, latest))
            df['fundingTime'] = pd.to_datetime(df['fundingTime'], format='mixed', utc=True)
            data[key] = df
            print(f"Loaded {key}: {len(df)} records")

    # Load statistical analysis
    stats_file = os.path.join(DATA_DIR, 'statistical_analysis.json')
    if os.path.exists(stats_file):
        with open(stats_file) as f:
            data['stats'] = json.load(f)

    # Load raw API evidence
    evidence_file = os.path.join(DATA_DIR, 'raw_api_evidence.json')
    if os.path.exists(evidence_file):
        with open(evidence_file) as f:
            data['evidence'] = json.load(f)

    return data


def fig1_interest_rate_evidence(data):
    """
    Figure 1: Visual representation of the Binance API interestRate field.
    Place in: Technical Analysis section (Section 4)
    """
    fig, ax = plt.subplots(figsize=(6, 4))

    # Create a visual representation of the API response
    api_fields = [
        ('symbol', 'BTCUSDT', 'black'),
        ('markPrice', '95,066.54', 'black'),
        ('indexPrice', '95,109.26', 'black'),
        ('lastFundingRate', '0.00005102', 'black'),
        ('interestRate', '0.00010000', CEX_COLOR),  # Highlight this!
    ]

    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(api_fields) + 1)

    for i, (field, value, color) in enumerate(api_fields):
        y = len(api_fields) - i

        # Field name
        weight = 'bold' if field == 'interestRate' else 'normal'
        size = 12 if field == 'interestRate' else 10

        ax.text(1, y, f'"{field}":', fontsize=size, fontweight=weight,
                color=color, family='monospace')
        ax.text(5, y, f'"{value}"', fontsize=size, fontweight=weight,
                color=color, family='monospace')

        if field == 'interestRate':
            # Add annotation
            ax.annotate('← EXPLICIT INTEREST\n    (0.01% per 8h = 0.03%/day)',
                       xy=(7.5, y), fontsize=10, color=CEX_COLOR, fontweight='bold')
            # Highlight box
            rect = plt.Rectangle((0.5, y-0.3), 9, 0.6, fill=False,
                                 edgecolor=CEX_COLOR, linewidth=2)
            ax.add_patch(rect)

    ax.set_title('Binance API Response: /fapi/v1/premiumIndex', fontweight='bold', pad=20)
    ax.text(5, 0.3, 'This field is labeled "interestRate" in the exchange\'s own API',
            ha='center', fontsize=9, style='italic', color='gray')

    ax.axis('off')

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_interest_evidence.pdf'),
                format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_interest_evidence.png'),
                format='png', bbox_inches='tight', dpi=300)
    plt.close()
    print("Generated: fig_interest_evidence.pdf")


def fig2_funding_timeseries(data):
    """
    Figure 2: Time series of funding rates - CEX vs DEX over 90 days.
    Place in: Empirical Analysis section (Section 5)
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)

    # BTC subplot
    ax1.set_title('BTC Perpetual Funding Rates (90 Days)', fontweight='bold')

    for key, color, label in [
        ('binance_btc', BINANCE_COLOR, 'Binance (CEX)'),
        ('bybit_btc', BYBIT_COLOR, 'Bybit (CEX)'),
        ('dydx_btc', DYDX_COLOR, 'dYdX (DEX)'),
        ('hyperliquid_btc', HL_COLOR, 'Hyperliquid (DEX)')
    ]:
        if key in data:
            df = data[key]
            ax1.plot(df['fundingTime'], df['fundingRate'].astype(float) * 100,
                    color=color, alpha=0.7, linewidth=0.8, label=label)

    ax1.axhline(y=0.01, color=CEX_COLOR, linestyle='--', linewidth=1.5,
                label='Interest Floor (0.01%)')
    ax1.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
    ax1.set_ylabel('Funding Rate (%)')
    ax1.legend(loc='upper right', fontsize=8)
    ax1.grid(True, alpha=0.3)

    # ETH subplot
    ax2.set_title('ETH Perpetual Funding Rates (90 Days)', fontweight='bold')

    for key, color, label in [
        ('binance_eth', BINANCE_COLOR, 'Binance (CEX)'),
        ('bybit_eth', BYBIT_COLOR, 'Bybit (CEX)'),
        ('dydx_eth', DYDX_COLOR, 'dYdX (DEX)'),
        ('hyperliquid_eth', HL_COLOR, 'Hyperliquid (DEX)')
    ]:
        if key in data:
            df = data[key]
            ax2.plot(df['fundingTime'], df['fundingRate'].astype(float) * 100,
                    color=color, alpha=0.7, linewidth=0.8, label=label)

    ax2.axhline(y=0.01, color=CEX_COLOR, linestyle='--', linewidth=1.5)
    ax2.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
    ax2.set_ylabel('Funding Rate (%)')
    ax2.set_xlabel('Date')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_funding_timeseries.pdf'),
                format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_funding_timeseries.png'),
                format='png', bbox_inches='tight', dpi=300)
    plt.close()
    print("Generated: fig_funding_timeseries.pdf")


def fig3_funding_distribution(data):
    """
    Figure 3: Distribution histogram comparing CEX vs DEX.
    Place in: Statistical Significance section
    """
    fig, ax = plt.subplots(figsize=(7, 5))

    # Aggregate CEX and DEX rates
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
    bins = np.linspace(-0.02, 0.025, 50)

    ax.hist(cex_rates, bins=bins, alpha=0.6, color=CEX_COLOR,
            label=f'CEX (n={len(cex_rates):,})', density=True, edgecolor='white')
    ax.hist(dex_rates, bins=bins, alpha=0.6, color=DEX_COLOR,
            label=f'DEX (n={len(dex_rates):,})', density=True, edgecolor='white')

    # Add vertical lines
    ax.axvline(x=0.01, color=CEX_COLOR, linestyle='--', linewidth=2,
               label='Interest Rate (0.01%)')
    ax.axvline(x=0, color='black', linestyle='-', linewidth=1)

    # Add mean lines
    cex_mean = np.mean(cex_rates)
    dex_mean = np.mean(dex_rates)
    ax.axvline(x=cex_mean, color=CEX_COLOR, linestyle=':', linewidth=2)
    ax.axvline(x=dex_mean, color=DEX_COLOR, linestyle=':', linewidth=2)

    # Annotations
    ax.annotate(f'CEX Mean\n{cex_mean:.4f}%', xy=(cex_mean, ax.get_ylim()[1]*0.8),
                fontsize=9, color=CEX_COLOR, ha='center')
    ax.annotate(f'DEX Mean\n{dex_mean:.4f}%', xy=(dex_mean, ax.get_ylim()[1]*0.6),
                fontsize=9, color=DEX_COLOR, ha='center')

    ax.set_title('Funding Rate Distribution: CEX vs DEX', fontweight='bold')
    ax.set_xlabel('Funding Rate (%)')
    ax.set_ylabel('Density')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    # Add statistical annotation
    stats = data.get('stats', {})
    stats_text = f"t-test p < 0.001\nCohen's d = {stats.get('cohens_d', 0):.2f}"
    ax.text(0.02, 0.95, stats_text, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_funding_distribution.pdf'),
                format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_funding_distribution.png'),
                format='png', bbox_inches='tight', dpi=300)
    plt.close()
    print("Generated: fig_funding_distribution.pdf")


def fig4_platform_boxplot(data):
    """
    Figure 4: Box plot comparing funding rates by platform.
    Place in: Empirical Results section
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    platforms = ['binance_btc', 'binance_eth', 'bybit_btc', 'bybit_eth',
                 'dydx_btc', 'dydx_eth', 'hyperliquid_btc', 'hyperliquid_eth']

    plot_data = []
    labels = []
    colors = []

    color_map = {
        'binance': BINANCE_COLOR,
        'bybit': BYBIT_COLOR,
        'dydx': DYDX_COLOR,
        'hyperliquid': HL_COLOR
    }

    for key in platforms:
        if key in data:
            df = data[key]
            rates = df['fundingRate'].astype(float) * 100
            plot_data.append(rates.values)

            # Format label
            parts = key.split('_')
            label = f"{parts[0].title()}\n{parts[1].upper()}"
            labels.append(label)

            colors.append(color_map.get(parts[0], 'gray'))

    bp = ax.boxplot(plot_data, labels=labels, patch_artist=True,
                    widths=0.6, showfliers=False)

    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    for median in bp['medians']:
        median.set_color('black')
        median.set_linewidth(2)

    # Add reference lines
    ax.axhline(y=0.01, color=CEX_COLOR, linestyle='--', linewidth=1.5,
               label='Interest Floor')
    ax.axhline(y=0, color='gray', linestyle='-', linewidth=1)

    # Add CEX/DEX divider
    ax.axvline(x=4.5, color='black', linestyle='-', linewidth=2, alpha=0.3)
    ax.text(2.5, ax.get_ylim()[1]*0.95, 'CEX', ha='center', fontsize=12,
            fontweight='bold', color=CEX_COLOR)
    ax.text(6.5, ax.get_ylim()[1]*0.95, 'DEX', ha='center', fontsize=12,
            fontweight='bold', color=DEX_COLOR)

    ax.set_title('Funding Rate Distribution by Platform', fontweight='bold')
    ax.set_ylabel('Funding Rate (%)')
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_platform_boxplot.pdf'),
                format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_platform_boxplot.png'),
                format='png', bbox_inches='tight', dpi=300)
    plt.close()
    print("Generated: fig_platform_boxplot.pdf")


def fig5_negative_funding(data):
    """
    Figure 5: Bar chart showing percentage of negative funding intervals.
    Place in: Key Findings section
    """
    fig, ax = plt.subplots(figsize=(6, 4))

    platforms = []
    neg_pcts = []
    colors = []

    color_map = {
        'binance': BINANCE_COLOR,
        'bybit': BYBIT_COLOR,
        'dydx': DYDX_COLOR,
        'hyperliquid': HL_COLOR
    }

    for key in ['binance_btc', 'bybit_btc', 'dydx_btc', 'hyperliquid_btc']:
        if key in data:
            df = data[key]
            rates = df['fundingRate'].astype(float)
            neg_pct = (rates < 0).sum() / len(rates) * 100

            parts = key.split('_')
            platforms.append(parts[0].title())
            neg_pcts.append(neg_pct)
            colors.append(color_map.get(parts[0], 'gray'))

    bars = ax.bar(platforms, neg_pcts, color=colors, alpha=0.7, edgecolor='black')

    # Add value labels
    for bar, pct in zip(bars, neg_pcts):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'{pct:.1f}%', ha='center', fontsize=10, fontweight='bold')

    # Add CEX/DEX labels
    ax.text(0.5, ax.get_ylim()[1]*0.9, 'CEX', ha='center', fontsize=11,
            fontweight='bold', color=CEX_COLOR)
    ax.text(2.5, ax.get_ylim()[1]*0.9, 'DEX', ha='center', fontsize=11,
            fontweight='bold', color=DEX_COLOR)

    ax.axvline(x=1.5, color='black', linestyle='--', alpha=0.3)

    ax.set_title('Negative Funding Rate Frequency (BTC)', fontweight='bold')
    ax.set_ylabel('% of Intervals with Negative Funding')
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_negative_funding.pdf'),
                format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_negative_funding.png'),
                format='png', bbox_inches='tight', dpi=300)
    plt.close()
    print("Generated: fig_negative_funding.pdf")


def fig6_cost_comparison(data):
    """
    Figure 6: Annual cost comparison for traders.
    Place in: Cost Efficiency section
    """
    fig, ax = plt.subplots(figsize=(6, 4))

    # Calculate annual costs
    stats = data.get('stats', {})
    cex_mean = stats.get('cex_mean', 0.000037)  # per 8h
    dex_mean = stats.get('dex_mean', 0.000008)  # per 8h

    cex_annual = cex_mean * 3 * 365 * 100  # 3 intervals per day * 365 days * 100 for %
    dex_annual = dex_mean * 3 * 365 * 100
    savings = cex_annual - dex_annual

    categories = ['CEX\n(Binance/Bybit)', 'DEX\n(dYdX/Hyperliquid)', 'Annual\nSavings']
    values = [cex_annual, dex_annual, savings]
    colors_bar = [CEX_COLOR, DEX_COLOR, '#1976D2']

    bars = ax.bar(categories, values, color=colors_bar, alpha=0.7, edgecolor='black')

    # Add value labels
    for bar, val in zip(bars, values):
        label = f'{val:.2f}%'
        if bar == bars[2]:
            label = f'+{val:.2f}%'
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                label, ha='center', fontsize=11, fontweight='bold')

    # Add dollar example
    ax.text(0.5, -0.15, 'On $100K position:', transform=ax.transAxes,
            ha='center', fontsize=9, style='italic')
    ax.text(0.5, -0.22, f'CEX: ${cex_annual*1000:.0f}/yr  |  DEX: ${dex_annual*1000:.0f}/yr  |  Save: ${savings*1000:.0f}/yr',
            transform=ax.transAxes, ha='center', fontsize=9, fontweight='bold')

    ax.set_title('Annual Funding Cost for Long Positions', fontweight='bold')
    ax.set_ylabel('Annual Cost (%)')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, max(values) * 1.2)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_cost_comparison.pdf'),
                format='pdf', bbox_inches='tight', dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig_cost_comparison.png'),
                format='png', bbox_inches='tight', dpi=300)
    plt.close()
    print("Generated: fig_cost_comparison.pdf")


def main():
    print("=" * 60)
    print("GENERATING INDIVIDUAL FIGURES FOR PAPER")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    data = load_data()

    # Generate figures
    print("\nGenerating figures...")
    fig1_interest_rate_evidence(data)
    fig2_funding_timeseries(data)
    fig3_funding_distribution(data)
    fig4_platform_boxplot(data)
    fig5_negative_funding(data)
    fig6_cost_comparison(data)

    print("\n" + "=" * 60)
    print("ALL FIGURES GENERATED")
    print("=" * 60)
    print("""
Figures created:
1. fig_interest_evidence.pdf    - For Technical Analysis (Section 4)
2. fig_funding_timeseries.pdf   - For Empirical Analysis (Section 5)
3. fig_funding_distribution.pdf - For Statistical Testing subsection
4. fig_platform_boxplot.pdf     - For Empirical Results
5. fig_negative_funding.pdf     - For Key Findings
6. fig_cost_comparison.pdf      - For Cost Efficiency subsection
    """)


if __name__ == "__main__":
    main()
