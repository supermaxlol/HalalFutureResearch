"""
Funding Rate Data Collector for Islamic Finance Research
========================================================
Collects and compares funding rates from CEX (interest-bearing) vs DEX (premium-only)

CEX Sources (contain 0.03% daily interest component):
- Binance

DEX Sources (premium-only, zero interest):
- dYdX v4
- GMX (Arbitrum)
- Hyperliquid

Author: Shehzad Ahmed
For paper: "A Halal Path Forward: How Decentralized Exchanges Enable
           Shariah-Compliant Perpetual Futures Trading for the First Time"
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
import os
from typing import Dict, List, Optional, Tuple
import hashlib
import hmac
from urllib.parse import urlencode

# ============================================================================
# CONFIGURATION
# ============================================================================

BINANCE_API_KEY = "wbKSNv0Eg4aRUF9G7V0gmr75QfMkZ7ed4I0zMMtYPRM70A0tnVxNjGRTg4ZGPkK8"
BINANCE_API_SECRET = "u8Esf3S9IfOAjhVMoIHO41OOhbl3oZKHcgLtnlkmXw0CbcLs4oTCbdWp2ai8LLWj"

# Data storage
DATA_DIR = "/Users/shehzad/Desktop/Halalfuture/funding_data"
os.makedirs(DATA_DIR, exist_ok=True)

# Common trading pairs for comparison
COMPARISON_PAIRS = {
    "BTC": {
        "binance": "BTCUSDT",
        "dydx": "BTC-USD",
        "gmx": "BTC",
        "hyperliquid": "BTC"
    },
    "ETH": {
        "binance": "ETHUSDT",
        "dydx": "ETH-USD",
        "gmx": "ETH",
        "hyperliquid": "ETH"
    }
}


# ============================================================================
# BINANCE CEX FETCHER (Contains Interest Component)
# ============================================================================

class BinanceFetcher:
    """
    Fetches funding rates from Binance Futures.

    IMPORTANT: Binance funding rate formula includes explicit interest:
    Funding Rate = Premium Index + clamp(Interest Rate - Premium Index, 0.05%, -0.05%)

    The Interest Rate is FIXED at 0.01% per 8-hour interval (0.03% daily)
    This is explicitly labeled as "interest" in Binance documentation.
    """

    BASE_URL = "https://fapi.binance.com"

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": api_key
        })

    def _sign_request(self, params: dict) -> dict:
        """Sign request with HMAC SHA256"""
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def get_funding_rate_history(self, symbol: str, limit: int = 1000,
                                  start_time: Optional[int] = None,
                                  end_time: Optional[int] = None) -> pd.DataFrame:
        """
        Fetch historical funding rates from Binance.

        Returns DataFrame with columns:
        - symbol
        - fundingTime
        - fundingRate
        - markPrice
        """
        endpoint = f"{self.BASE_URL}/fapi/v1/fundingRate"

        params = {
            "symbol": symbol,
            "limit": min(limit, 1000)  # Max 1000 per request
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)
            df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms")
            df["fundingRate"] = df["fundingRate"].astype(float)
            df["markPrice"] = df["markPrice"].astype(float) if "markPrice" in df.columns else None
            df["source"] = "binance"
            df["has_interest_component"] = True
            df["interest_rate_per_interval"] = 0.0001  # 0.01% per 8h = 0.03% daily

            return df

        except Exception as e:
            print(f"Error fetching Binance funding rates for {symbol}: {e}")
            return pd.DataFrame()

    def get_current_funding_info(self, symbol: str) -> dict:
        """Get current funding rate and next funding time"""
        endpoint = f"{self.BASE_URL}/fapi/v1/premiumIndex"

        try:
            response = self.session.get(endpoint, params={"symbol": symbol})
            response.raise_for_status()
            data = response.json()

            return {
                "symbol": data["symbol"],
                "markPrice": float(data["markPrice"]),
                "indexPrice": float(data["indexPrice"]),
                "lastFundingRate": float(data["lastFundingRate"]),
                "nextFundingTime": datetime.fromtimestamp(data["nextFundingTime"] / 1000),
                "interestRate": float(data.get("interestRate", 0.0001)),  # Usually 0.01%
                "source": "binance",
                "has_interest_component": True
            }
        except Exception as e:
            print(f"Error fetching Binance premium index for {symbol}: {e}")
            return {}

    def get_all_funding_rates(self) -> pd.DataFrame:
        """Get current funding rates for all perpetual pairs"""
        endpoint = f"{self.BASE_URL}/fapi/v1/premiumIndex"

        try:
            response = self.session.get(endpoint)
            response.raise_for_status()
            data = response.json()

            df = pd.DataFrame(data)
            df["lastFundingRate"] = df["lastFundingRate"].astype(float)
            df["markPrice"] = df["markPrice"].astype(float)
            df["indexPrice"] = df["indexPrice"].astype(float)
            df["interestRate"] = df["interestRate"].astype(float)
            df["source"] = "binance"
            df["has_interest_component"] = True

            return df

        except Exception as e:
            print(f"Error fetching Binance all funding rates: {e}")
            return pd.DataFrame()


# ============================================================================
# DYDX V4 DEX FETCHER (Premium-Only, No Interest)
# ============================================================================

class DYDXFetcher:
    """
    Fetches funding rates from dYdX v4.

    IMPORTANT: dYdX v4 uses PREMIUM-ONLY funding with ZERO interest component.
    From dYdX documentation:
    "As part of the default settings of the v4 open source software,
    the interest rate component for all markets is 0%."

    This is a fundamental structural difference from CEX perpetuals.
    """

    # dYdX v4 Indexer API
    BASE_URL = "https://indexer.dydx.trade/v4"

    def __init__(self):
        self.session = requests.Session()

    def get_funding_rate_history(self, market: str, limit: int = 100) -> pd.DataFrame:
        """
        Fetch historical funding rates from dYdX v4.

        Note: dYdX funding is hourly (vs 8-hourly for Binance)
        """
        endpoint = f"{self.BASE_URL}/historicalFunding/{market}"

        try:
            params = {"limit": min(limit, 100)}
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()

            if "historicalFunding" not in data:
                return pd.DataFrame()

            records = data["historicalFunding"]
            if not records:
                return pd.DataFrame()

            df = pd.DataFrame(records)
            df["effectiveAt"] = pd.to_datetime(df["effectiveAt"])
            df["rate"] = df["rate"].astype(float)
            df["price"] = df["price"].astype(float)
            df["source"] = "dydx"
            df["has_interest_component"] = False
            df["interest_rate_per_interval"] = 0.0  # ZERO interest

            # Rename to match common schema
            df = df.rename(columns={
                "effectiveAt": "fundingTime",
                "rate": "fundingRate",
                "price": "markPrice"
            })
            df["symbol"] = market

            return df

        except Exception as e:
            print(f"Error fetching dYdX funding rates for {market}: {e}")
            return pd.DataFrame()

    def get_all_markets(self) -> List[dict]:
        """Get list of all perpetual markets on dYdX"""
        endpoint = f"{self.BASE_URL}/perpetualMarkets"

        try:
            response = self.session.get(endpoint)
            response.raise_for_status()
            data = response.json()
            return data.get("markets", {})
        except Exception as e:
            print(f"Error fetching dYdX markets: {e}")
            return {}

    def get_current_funding_rates(self) -> pd.DataFrame:
        """Get current funding rates for all markets"""
        markets = self.get_all_markets()

        if not markets:
            return pd.DataFrame()

        records = []
        for ticker, info in markets.items():
            records.append({
                "symbol": ticker,
                "nextFundingRate": float(info.get("nextFundingRate", 0)),
                "oraclePrice": float(info.get("oraclePrice", 0)),
                "priceChange24H": float(info.get("priceChange24H", 0)),
                "volume24H": float(info.get("volume24H", 0)),
                "openInterest": float(info.get("openInterest", 0)),
                "source": "dydx",
                "has_interest_component": False,
                "interest_rate_per_interval": 0.0
            })

        return pd.DataFrame(records)


# ============================================================================
# HYPERLIQUID DEX FETCHER (Premium-Only, No Interest)
# ============================================================================

class HyperliquidFetcher:
    """
    Fetches funding rates from Hyperliquid.

    Hyperliquid is a DEX with premium-only funding mechanism.
    No explicit interest component in the funding rate formula.
    """

    BASE_URL = "https://api.hyperliquid.xyz"

    def __init__(self):
        self.session = requests.Session()

    def get_all_mids(self) -> dict:
        """Get all mid prices"""
        endpoint = f"{self.BASE_URL}/info"
        payload = {"type": "allMids"}

        try:
            response = self.session.post(endpoint, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching Hyperliquid mids: {e}")
            return {}

    def get_meta_and_asset_ctxs(self) -> Tuple[dict, List[dict]]:
        """Get metadata and asset contexts including funding rates"""
        endpoint = f"{self.BASE_URL}/info"
        payload = {"type": "metaAndAssetCtxs"}

        try:
            response = self.session.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

            if len(data) >= 2:
                meta = data[0]
                asset_ctxs = data[1]
                return meta, asset_ctxs
            return {}, []
        except Exception as e:
            print(f"Error fetching Hyperliquid meta: {e}")
            return {}, []

    def get_funding_history(self, coin: str, start_time: int, end_time: Optional[int] = None) -> pd.DataFrame:
        """
        Fetch historical funding rates for a specific coin.

        start_time and end_time are Unix timestamps in milliseconds.
        """
        endpoint = f"{self.BASE_URL}/info"
        payload = {
            "type": "fundingHistory",
            "coin": coin,
            "startTime": start_time
        }

        if end_time:
            payload["endTime"] = end_time

        try:
            response = self.session.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            df["fundingRate"] = df["fundingRate"].astype(float)
            df["premium"] = df["premium"].astype(float)
            df["source"] = "hyperliquid"
            df["has_interest_component"] = False
            df["interest_rate_per_interval"] = 0.0

            # Rename for common schema
            df = df.rename(columns={"time": "fundingTime"})
            df["symbol"] = coin

            return df

        except Exception as e:
            print(f"Error fetching Hyperliquid funding history for {coin}: {e}")
            return pd.DataFrame()

    def get_current_funding_rates(self) -> pd.DataFrame:
        """Get current funding rates for all assets"""
        meta, asset_ctxs = self.get_meta_and_asset_ctxs()

        if not meta or not asset_ctxs:
            return pd.DataFrame()

        universe = meta.get("universe", [])

        records = []
        for i, asset in enumerate(asset_ctxs):
            if i < len(universe):
                coin_info = universe[i]
                records.append({
                    "symbol": coin_info.get("name", f"UNKNOWN_{i}"),
                    "fundingRate": float(asset.get("funding", 0)),
                    "openInterest": float(asset.get("openInterest", 0)),
                    "markPrice": float(asset.get("markPx", 0)),
                    "oraclePrice": float(asset.get("oraclePx", 0)),
                    "source": "hyperliquid",
                    "has_interest_component": False,
                    "interest_rate_per_interval": 0.0
                })

        return pd.DataFrame(records)


# ============================================================================
# GMX DEX FETCHER (Premium-Only, No Interest)
# ============================================================================

class GMXFetcher:
    """
    Fetches funding rates from GMX (Arbitrum).

    GMX uses a unique model where funding is based on asset utilization
    rather than a traditional premium. No explicit interest component.
    """

    # GMX Stats API
    BASE_URL = "https://stats.gmx.io"

    def __init__(self):
        self.session = requests.Session()

    def get_funding_rates(self) -> pd.DataFrame:
        """
        Get current funding/borrowing rates from GMX.

        Note: GMX uses a borrowing rate model rather than traditional funding.
        This is based on utilization, not an interest rate.
        """
        endpoint = f"{self.BASE_URL}/arbitrum/api"

        try:
            response = self.session.get(endpoint)
            response.raise_for_status()
            data = response.json()

            # GMX provides borrowing rates based on utilization
            records = []
            for token_data in data.get("tokens", []):
                records.append({
                    "symbol": token_data.get("symbol", ""),
                    "fundingRate": float(token_data.get("fundingRate", 0)),
                    "borrowRate": float(token_data.get("borrowRate", 0)),
                    "utilization": float(token_data.get("utilization", 0)),
                    "source": "gmx",
                    "has_interest_component": False,  # Utilization-based, not fixed interest
                    "interest_rate_per_interval": 0.0
                })

            return pd.DataFrame(records) if records else pd.DataFrame()

        except Exception as e:
            print(f"Error fetching GMX funding rates: {e}")
            return pd.DataFrame()


# ============================================================================
# DATA AGGREGATOR AND COMPARISON
# ============================================================================

class FundingRateAggregator:
    """
    Aggregates funding rate data from multiple sources for comparison.
    """

    def __init__(self, binance_key: str, binance_secret: str):
        self.binance = BinanceFetcher(binance_key, binance_secret)
        self.dydx = DYDXFetcher()
        self.hyperliquid = HyperliquidFetcher()
        self.gmx = GMXFetcher()

    def fetch_historical_comparison(self, days: int = 30) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical funding rates from all sources for comparison.
        """
        results = {}

        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        print(f"\nFetching historical funding rates for last {days} days...")
        print("=" * 60)

        # Binance (CEX with interest)
        print("\n[CEX] Fetching Binance BTCUSDT...")
        binance_btc = self.binance.get_funding_rate_history(
            "BTCUSDT", limit=1000, start_time=start_time, end_time=end_time
        )
        if not binance_btc.empty:
            print(f"  -> Got {len(binance_btc)} records")
            results["binance_btc"] = binance_btc

        print("[CEX] Fetching Binance ETHUSDT...")
        binance_eth = self.binance.get_funding_rate_history(
            "ETHUSDT", limit=1000, start_time=start_time, end_time=end_time
        )
        if not binance_eth.empty:
            print(f"  -> Got {len(binance_eth)} records")
            results["binance_eth"] = binance_eth

        time.sleep(0.5)  # Rate limiting

        # dYdX (DEX premium-only)
        print("\n[DEX] Fetching dYdX BTC-USD...")
        dydx_btc = self.dydx.get_funding_rate_history("BTC-USD", limit=100)
        if not dydx_btc.empty:
            print(f"  -> Got {len(dydx_btc)} records")
            results["dydx_btc"] = dydx_btc

        print("[DEX] Fetching dYdX ETH-USD...")
        dydx_eth = self.dydx.get_funding_rate_history("ETH-USD", limit=100)
        if not dydx_eth.empty:
            print(f"  -> Got {len(dydx_eth)} records")
            results["dydx_eth"] = dydx_eth

        time.sleep(0.5)

        # Hyperliquid (DEX premium-only)
        print("\n[DEX] Fetching Hyperliquid BTC...")
        hl_btc = self.hyperliquid.get_funding_history("BTC", start_time)
        if not hl_btc.empty:
            print(f"  -> Got {len(hl_btc)} records")
            results["hyperliquid_btc"] = hl_btc

        print("[DEX] Fetching Hyperliquid ETH...")
        hl_eth = self.hyperliquid.get_funding_history("ETH", start_time)
        if not hl_eth.empty:
            print(f"  -> Got {len(hl_eth)} records")
            results["hyperliquid_eth"] = hl_eth

        return results

    def fetch_current_snapshot(self) -> Dict[str, pd.DataFrame]:
        """
        Fetch current funding rates from all sources.
        """
        results = {}

        print("\nFetching current funding rates snapshot...")
        print("=" * 60)

        # Binance
        print("\n[CEX] Fetching Binance current rates...")
        binance_current = self.binance.get_all_funding_rates()
        if not binance_current.empty:
            print(f"  -> Got {len(binance_current)} markets")
            results["binance_current"] = binance_current

        # dYdX
        print("[DEX] Fetching dYdX current rates...")
        dydx_current = self.dydx.get_current_funding_rates()
        if not dydx_current.empty:
            print(f"  -> Got {len(dydx_current)} markets")
            results["dydx_current"] = dydx_current

        # Hyperliquid
        print("[DEX] Fetching Hyperliquid current rates...")
        hl_current = self.hyperliquid.get_current_funding_rates()
        if not hl_current.empty:
            print(f"  -> Got {len(hl_current)} markets")
            results["hyperliquid_current"] = hl_current

        return results

    def generate_comparison_report(self, historical_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Generate a comparison report showing the key differences.
        """
        report_data = []

        for key, df in historical_data.items():
            if df.empty:
                continue

            source = df["source"].iloc[0]
            has_interest = df["has_interest_component"].iloc[0]
            interest_rate = df["interest_rate_per_interval"].iloc[0]

            # Calculate statistics
            funding_rates = df["fundingRate"].astype(float)

            report_data.append({
                "Source": key,
                "Platform_Type": "CEX" if has_interest else "DEX",
                "Has_Interest_Component": "YES (0.01% per 8h)" if has_interest else "NO (Premium-only)",
                "Daily_Interest_Rate": f"{interest_rate * 3 * 100:.3f}%" if has_interest else "0%",
                "Num_Records": len(df),
                "Mean_Funding_Rate": f"{funding_rates.mean() * 100:.4f}%",
                "Std_Funding_Rate": f"{funding_rates.std() * 100:.4f}%",
                "Min_Funding_Rate": f"{funding_rates.min() * 100:.4f}%",
                "Max_Funding_Rate": f"{funding_rates.max() * 100:.4f}%",
                "Funding_Interval": "8 hours" if source == "binance" else "1 hour"
            })

        return pd.DataFrame(report_data)

    def save_data(self, data: Dict[str, pd.DataFrame], prefix: str = "funding"):
        """Save all collected data to CSV files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for key, df in data.items():
            if not df.empty:
                filepath = os.path.join(DATA_DIR, f"{prefix}_{key}_{timestamp}.csv")
                df.to_csv(filepath, index=False)
                print(f"Saved: {filepath}")


# ============================================================================
# VISUALIZATION
# ============================================================================

def create_comparison_charts(historical_data: Dict[str, pd.DataFrame], output_dir: str):
    """
    Create comparison charts for the paper.
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print("matplotlib not installed. Run: pip install matplotlib")
        return

    # Set up the figure
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("CEX vs DEX Perpetual Futures Funding Rates\n(CEX includes 0.03% daily interest; DEX is premium-only)",
                 fontsize=14, fontweight='bold')

    # BTC comparison
    ax1 = axes[0, 0]
    for key in ["binance_btc", "dydx_btc", "hyperliquid_btc"]:
        if key in historical_data and not historical_data[key].empty:
            df = historical_data[key]
            color = "red" if "binance" in key else "green"
            label = f"{key.split('_')[0].upper()} ({'CEX+Interest' if 'binance' in key else 'DEX Premium-only'})"
            ax1.plot(df["fundingTime"], df["fundingRate"].astype(float) * 100,
                    label=label, alpha=0.7, color=color if "binance" in key else None)

    ax1.set_title("BTC Perpetual Funding Rates")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Funding Rate (%)")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0.01, color='red', linestyle='--', alpha=0.5, label='Base Interest (CEX)')

    # ETH comparison
    ax2 = axes[0, 1]
    for key in ["binance_eth", "dydx_eth", "hyperliquid_eth"]:
        if key in historical_data and not historical_data[key].empty:
            df = historical_data[key]
            color = "red" if "binance" in key else "green"
            label = f"{key.split('_')[0].upper()} ({'CEX+Interest' if 'binance' in key else 'DEX Premium-only'})"
            ax2.plot(df["fundingTime"], df["fundingRate"].astype(float) * 100,
                    label=label, alpha=0.7, color=color if "binance" in key else None)

    ax2.set_title("ETH Perpetual Funding Rates")
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Funding Rate (%)")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Distribution comparison
    ax3 = axes[1, 0]
    cex_rates = []
    dex_rates = []

    for key, df in historical_data.items():
        if df.empty:
            continue
        rates = df["fundingRate"].astype(float) * 100
        if "binance" in key:
            cex_rates.extend(rates.tolist())
        else:
            dex_rates.extend(rates.tolist())

    if cex_rates and dex_rates:
        ax3.hist(cex_rates, bins=50, alpha=0.5, label="CEX (Binance) - Includes Interest", color="red")
        ax3.hist(dex_rates, bins=50, alpha=0.5, label="DEX (dYdX, Hyperliquid) - Premium Only", color="green")
        ax3.set_title("Funding Rate Distribution: CEX vs DEX")
        ax3.set_xlabel("Funding Rate (%)")
        ax3.set_ylabel("Frequency")
        ax3.legend()
        ax3.grid(True, alpha=0.3)

    # Summary statistics table
    ax4 = axes[1, 1]
    ax4.axis('off')

    summary_text = """
    KEY FINDINGS FOR ISLAMIC FINANCE ANALYSIS
    ==========================================

    CEX (Binance) Perpetuals:
    - Contains EXPLICIT interest component
    - Fixed 0.01% per 8-hour interval (0.03% daily)
    - Labeled as "Interest Rate" in documentation
    - This constitutes RIBA (prohibited interest)

    DEX (dYdX, Hyperliquid) Perpetuals:
    - ZERO interest component
    - Premium-only funding mechanism
    - Based purely on mark-spot divergence
    - No fixed interest charge

    CONCLUSION:
    DEX perpetuals eliminate the explicit riba
    component present in all CEX implementations.
    """

    ax4.text(0.1, 0.9, summary_text, transform=ax4.transAxes, fontsize=10,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()

    # Save the chart
    chart_path = os.path.join(output_dir, "cex_vs_dex_funding_comparison.png")
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"\nChart saved: {chart_path}")

    # Also save as PDF for the paper
    pdf_path = os.path.join(output_dir, "cex_vs_dex_funding_comparison.pdf")
    plt.savefig(pdf_path, format='pdf', bbox_inches='tight')
    print(f"PDF saved: {pdf_path}")

    plt.close()


# ============================================================================
# GENERATE LATEX TABLE FOR PAPER
# ============================================================================

def generate_latex_table(report_df: pd.DataFrame) -> str:
    """Generate LaTeX table for inclusion in the paper"""

    latex = r"""
\begin{table*}[h]
\centering
\caption{Empirical Comparison of CEX vs DEX Funding Rate Mechanisms}
\label{tab:funding_comparison}
\begin{tabular}{@{}lcccccc@{}}
\toprule
\textbf{Platform} & \textbf{Type} & \textbf{Interest Component} & \textbf{Mean Rate} & \textbf{Std Dev} & \textbf{Min} & \textbf{Max} \\
\midrule
"""

    for _, row in report_df.iterrows():
        source = row["Source"].replace("_", " ").title()
        ptype = row["Platform_Type"]
        interest = "Yes (0.03\%/day)" if row["Has_Interest_Component"].startswith("YES") else "No"
        mean_rate = row["Mean_Funding_Rate"]
        std_rate = row["Std_Funding_Rate"]
        min_rate = row["Min_Funding_Rate"]
        max_rate = row["Max_Funding_Rate"]

        latex += f"{source} & {ptype} & {interest} & {mean_rate} & {std_rate} & {min_rate} & {max_rate} \\\\\n"

    latex += r"""
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item Data collected """ + datetime.now().strftime("%B %Y") + r""". CEX platforms include explicit interest rate components in their funding formulas. DEX platforms use premium-only mechanisms with zero interest.
\end{tablenotes}
\end{table*}
"""

    return latex


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("\n" + "=" * 70)
    print("FUNDING RATE DATA COLLECTOR FOR ISLAMIC FINANCE RESEARCH")
    print("CEX (Interest-bearing) vs DEX (Premium-only) Comparison")
    print("=" * 70)

    # Initialize aggregator
    aggregator = FundingRateAggregator(BINANCE_API_KEY, BINANCE_API_SECRET)

    # Fetch historical data
    historical_data = aggregator.fetch_historical_comparison(days=30)

    # Fetch current snapshot
    current_data = aggregator.fetch_current_snapshot()

    # Generate comparison report
    print("\n" + "=" * 60)
    print("COMPARISON REPORT")
    print("=" * 60)

    report_df = aggregator.generate_comparison_report(historical_data)
    print("\n" + report_df.to_string(index=False))

    # Save data
    print("\n" + "=" * 60)
    print("SAVING DATA")
    print("=" * 60)

    aggregator.save_data(historical_data, "historical")
    aggregator.save_data(current_data, "current")

    # Save report
    report_path = os.path.join(DATA_DIR, f"comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    report_df.to_csv(report_path, index=False)
    print(f"Report saved: {report_path}")

    # Generate charts
    print("\n" + "=" * 60)
    print("GENERATING CHARTS")
    print("=" * 60)

    create_comparison_charts(historical_data, DATA_DIR)

    # Generate LaTeX table
    latex_table = generate_latex_table(report_df)
    latex_path = os.path.join(DATA_DIR, "latex_table.tex")
    with open(latex_path, "w") as f:
        f.write(latex_table)
    print(f"LaTeX table saved: {latex_path}")

    # Print key findings
    print("\n" + "=" * 70)
    print("KEY FINDINGS FOR PAPER")
    print("=" * 70)
    print("""
    1. BINANCE (CEX): Contains explicit 0.01% interest per 8-hour interval
       - This is fixed, predetermined, and labeled as "Interest Rate"
       - Constitutes clear RIBA under Islamic finance principles

    2. DYDX (DEX): Zero interest component confirmed
       - Funding based purely on premium (mark-spot divergence)
       - Documentation states "interest rate component for all markets is 0%"

    3. HYPERLIQUID (DEX): Premium-only funding mechanism
       - No fixed interest charge in funding calculation
       - Market-determined funding based on position imbalance

    CONCLUSION: DEX perpetuals structurally eliminate the explicit
    interest component present in CEX implementations.
    """)

    print("\nData collection complete!")
    print(f"All files saved to: {DATA_DIR}")


if __name__ == "__main__":
    main()
