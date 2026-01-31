#!/usr/bin/env python3
"""
Simple backtest runner for NFI X7 FreqAI Strategy
December 2025 - January 2026, Bybit Futures
"""

import sys
import os
import json
from pathlib import Path

# Add paths
NFI_PATH = Path("/home/claudio/code/personale/NostalgiaForInfinity")
sys.path.insert(0, str(NFI_PATH))

print("="*70)
print("NFI X7 FreqAI Backtest - Dec 2025 to Jan 2026")
print("="*70)

# Test imports
try:
    import pandas as pd
    import numpy as np
    import talib
    print("✓ Dependencies OK (pandas, numpy, talib)")
except ImportError as e:
    print(f"✗ Missing dependency: {e}")
    print("Install with: pip install pandas numpy ta-lib")
    sys.exit(1)

# Load config
config_path = NFI_PATH / "configs" / "freqai_nfi_x7_bybit_futures.json"
try:
    with open(config_path) as f:
        config = json.load(f)
    print(f"✓ Config loaded: {config_path.name}")
except Exception as e:
    print(f"✗ Error loading config: {e}")
    sys.exit(1)

# Load strategy with config
try:
    from NostalgiaForInfinityX7_FreqAI import NostalgiaForInfinityX7_FreqAI
    strategy = NostalgiaForInfinityX7_FreqAI(config)
    print(f"✓ Strategy loaded: {strategy.__class__.__name__}")
except Exception as e:
    print(f"✗ Error loading strategy: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Check data availability
data_dir = Path("/home/claudio/code/personale/freqtrade/user_data/data/bybit/futures")
test_pairs = ['BTC_USDT_USDT', 'ETH_USDT_USDT', 'SOL_USDT_USDT']
missing_data = []

for pair in test_pairs:
    data_file = data_dir / f"{pair}-5m-futures.feather"
    if not data_file.exists():
        missing_data.append(pair)

if missing_data:
    print(f"✗ Missing data for pairs: {', '.join(missing_data)}")
    print(f"  Data directory: {data_dir}")
    print("\n  Download data with:")
    print(f"  freqtrade download-data --exchange bybit --trading-mode futures \\")
    print(f"    --timeframes 5m 15m 1h 4h 1d --timerange 20251201-20260201 \\")
    print(f"    --pairs {' '.join(missing_data)}")
    sys.exit(1)
else:
    print(f"✓ Data available for {len(test_pairs)} pairs")

# Simple indicator test
print("\n" + "="*70)
print("Testing strategy indicators...")
print("="*70)

try:
    # Load sample data
    sample_file = data_dir / "BTC_USDT_USDT-5m-futures.feather"
    df = pd.read_feather(sample_file)
    print(f"✓ Loaded {len(df)} candles from {df['date'].min()} to {df['date'].max()}")

    # Filter to test period
    df = df[df['date'] >= '2025-12-01'].copy()
    df = df[df['date'] <= '2026-02-01'].copy()
    print(f"✓ Filtered to test period: {len(df)} candles")

    if len(df) < strategy.startup_candle_count:
        print(f"✗ Not enough data. Need {strategy.startup_candle_count}, have {len(df)}")
        sys.exit(1)

    # Test populate_indicators (without FreqAI for now)
    print("\nTesting indicator calculation...")

    # Mock freqai object for testing
    class MockFreqAI:
        def start(self, dataframe, metadata, strategy):
            # Add mock predictions
            dataframe['do_predict'] = 1
            dataframe['&-s_close'] = 0.0
            dataframe['&-s_close_mean'] = 0.0
            dataframe['&-s_close_std'] = 0.01
            dataframe['&-s_volatility'] = 0.02
            dataframe['&-s_max_profit'] = 0.03
            dataframe['&-s_max_drawdown'] = -0.02
            return dataframe

    strategy.freqai = MockFreqAI()
    metadata = {'pair': 'BTC/USDT:USDT'}

    df_with_indicators = strategy.populate_indicators(df.copy(), metadata)
    print(f"✓ Indicators calculated, dataframe shape: {df_with_indicators.shape}")

    # Check key indicators
    required_indicators = ['RSI_14', 'RSI_3', 'MFI_14', 'EMA_12', 'EMA_26', 'bb_lower', 'bb_upper']
    missing_indicators = [ind for ind in required_indicators if ind not in df_with_indicators.columns]

    if missing_indicators:
        print(f"✗ Missing indicators: {', '.join(missing_indicators)}")
        sys.exit(1)
    else:
        print(f"✓ All required indicators present ({len(required_indicators)} checked)")

    # Test entry/exit signals
    print("\nTesting entry/exit signals...")
    df_with_signals = strategy.populate_entry_trend(df_with_indicators.copy(), metadata)
    df_with_signals = strategy.populate_exit_trend(df_with_signals, metadata)

    long_entries = df_with_signals['enter_long'].sum() if 'enter_long' in df_with_signals.columns else 0
    short_entries = df_with_signals['enter_short'].sum() if 'enter_short' in df_with_signals.columns else 0
    long_exits = df_with_signals['exit_long'].sum() if 'exit_long' in df_with_signals.columns else 0
    short_exits = df_with_signals['exit_short'].sum() if 'exit_short' in df_with_signals.columns else 0

    print(f"✓ Signals generated:")
    print(f"  - Long entries: {long_entries}")
    print(f"  - Short entries: {short_entries}")
    print(f"  - Long exits: {long_exits}")
    print(f"  - Short exits: {short_exits}")

    if long_entries == 0 and short_entries == 0:
        print("⚠  Warning: No entry signals generated. Check strategy conditions.")

    print("\n" + "="*70)
    print("✓ Strategy validation complete!")
    print("="*70)
    print("\nNext steps:")
    print("1. For full FreqAI backtest, install freqtrade:")
    print("   docker-compose -f docker-compose.yml up")
    print("")
    print("2. Or run via command line:")
    print("   freqtrade backtesting \\")
    print("     --strategy NostalgiaForInfinityX7_FreqAI \\")
    print("     --config configs/freqai_nfi_x7_bybit_futures.json \\")
    print("     --timerange 20251201-20260201 \\")
    print("     --freqaimodel CatBoostRegressor")
    print("="*70)

except Exception as e:
    print(f"\n✗ Error during testing: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
