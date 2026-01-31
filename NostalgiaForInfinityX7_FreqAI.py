# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Dict
import talib.abstract as ta
from freqtrade.strategy import (IStrategy, merge_informative_pair, stoploss_from_open,
                                 DecimalParameter, IntParameter, CategoricalParameter)
import freqtrade.vendor.qtpylib.indicators as qtpylib
import logging
import warnings
from functools import reduce

warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)

logger = logging.getLogger(__name__)

class NostalgiaForInfinityX7_FreqAI(IStrategy):
    """
    Experimental FreqAI-powered version of NostalgiaForInfinityX7

    This strategy combines the proven indicator logic of NFI X7 with machine learning predictions
    to improve entry/exit timing and reduce false signals.

    Key Features:
    - ML predictions for price movement (next 24 candles)
    - Advanced feature engineering from NFI X7 indicators
    - Hybrid entry logic: ML + NFI conditions
    - Adaptive stop-loss based on ML confidence
    - Multi-timeframe feature engineering (5m, 15m, 1h, 4h, 1d)

    Optimized for: Bybit Futures, 5m timeframe
    """

    INTERFACE_VERSION = 3

    # ROI table - realistic profit targets (safety exit)
    minimal_roi = {
        "0": 0.025,     # 2.5% max profit
        "30": 0.02,     # 2% after 30min
        "60": 0.015,    # 1.5% after 1h
        "120": 0.01,    # 1% after 2h
        "240": 0.005    # 0.5% after 4h
    }

    # Stoploss - tighter to limit losses
    stoploss = -0.03  # -3% hard stop

    # Trailing stop (not used)
    trailing_stop = False
    trailing_only_offset_is_reached = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.03

    use_custom_stoploss = False

    # Timeframe
    timeframe = '5m'

    # Run "populate_indicators()" only for new candle
    process_only_new_candles = True

    # These values can be overridden in the config
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 800

    # FreqAI config
    can_short = True

    # Hyperoptable parameters
    # Lowered thresholds to allow more trades during initial testing
    ml_confidence_threshold = DecimalParameter(0.5, 0.9, default=0.55, space='buy', optimize=True)
    ml_profit_threshold = DecimalParameter(0.005, 0.03, default=0.010, space='sell', optimize=True)
    nfi_weight = DecimalParameter(0.2, 0.8, default=0.3, space='buy', optimize=True)

    # Plot configuration
    plot_config = {
        'main_plot': {
            'close': {'color': 'cornflowerblue'},
        },
        'subplots': {
            "Prediction": {
                '&-s_close': {'color': 'blue', 'type': 'line'},
                '&-s_close_mean': {'color': 'green', 'type': 'line'},
                '&-s_close_std': {'color': 'red', 'type': 'line'},
            },
            "do_predict": {
                'do_predict': {'color': 'brown', 'type': 'line'},
            },
            "RSI": {
                'RSI_14': {'color': 'red'},
            }
        }
    }

    def feature_engineering_expand_all(self, dataframe: DataFrame, period, metadata, **kwargs) -> DataFrame:
        """
        This function will automatically expand the defined features on the config defined
        `indicator_periods_candles`, `include_timeframes`, `include_shifted_candles`, and
        `include_corr_pairs`.

        Features from NFI X7 adapted for ML:
        - RSI (multiple periods)
        - MFI
        - ADX
        - Bollinger Bands
        - EMA/SMA
        - ROC
        - Relative Volume
        """
        # RSI variations
        dataframe[f"%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)

        # MFI
        dataframe[f"%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)

        # ADX
        dataframe[f"%-adx-period"] = ta.ADX(dataframe, timeperiod=period)

        # Moving averages
        dataframe[f"%-sma-period"] = ta.EMA(dataframe, timeperiod=period)
        dataframe[f"%-ema-period"] = ta.EMA(dataframe, timeperiod=period)

        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=period, stds=2.2
        )
        dataframe[f"bb_lowerband-period"] = bollinger["lower"]
        dataframe[f"bb_middleband-period"] = bollinger["mid"]
        dataframe[f"bb_upperband-period"] = bollinger["upper"]

        dataframe[f"%-bb_width-period"] = (
            dataframe[f"bb_upperband-period"] - dataframe[f"bb_lowerband-period"]
        ) / dataframe[f"bb_middleband-period"]

        dataframe[f"%-close-bb_lower-period"] = (
            dataframe["close"] / dataframe[f"bb_lowerband-period"]
        )

        # Rate of Change
        dataframe[f"%-roc-period"] = ta.ROC(dataframe, timeperiod=period)

        # Relative Volume
        dataframe[f"%-relative_volume-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean()
        )

        # Stochastic RSI
        stochrsi = ta.STOCHRSI(dataframe, timeperiod=14, fastk_period=period, fastd_period=3)
        dataframe[f"%-stochrsi_k-period"] = stochrsi['fastk']
        dataframe[f"%-stochrsi_d-period"] = stochrsi['fastd']

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata, **kwargs) -> DataFrame:
        """
        Features that don't need period expansion but benefit from timeframe/shift expansion
        """
        # Price change
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-pct-change-2"] = dataframe["close"].pct_change(periods=2)
        dataframe["%-pct-change-3"] = dataframe["close"].pct_change(periods=3)

        # Raw values
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]
        dataframe["%-raw_high"] = dataframe["high"]
        dataframe["%-raw_low"] = dataframe["low"]

        # NFI-specific indicators
        dataframe["%-ema_12"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["%-ema_26"] = ta.EMA(dataframe, timeperiod=26)
        dataframe["%-ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["%-ema_200"] = ta.EMA(dataframe, timeperiod=200)

        # MACD
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["%-macd"] = macd['macd']
        dataframe["%-macdsignal"] = macd['macdsignal']
        dataframe["%-macdhist"] = macd['macdhist']

        # CMF (Chaikin Money Flow)
        dataframe["%-cmf"] = (
            (((dataframe["close"] - dataframe["low"]) - (dataframe["high"] - dataframe["close"])) /
             (dataframe["high"] - dataframe["low"])) * dataframe["volume"]
        ).rolling(20).sum() / dataframe["volume"].rolling(20).sum()

        # Williams %R
        dataframe["%-williams_r"] = ta.WILLR(dataframe, timeperiod=14)

        # CCI (Commodity Channel Index)
        dataframe["%-cci"] = ta.CCI(dataframe, timeperiod=20)

        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata, **kwargs) -> DataFrame:
        """
        Custom features that should not be auto-expanded
        """
        # Time-based features
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        dataframe["%-day_of_month"] = dataframe["date"].dt.day

        # Volatility features
        dataframe["%-volatility_20"] = dataframe["close"].pct_change().rolling(20).std()
        dataframe["%-volatility_50"] = dataframe["close"].pct_change().rolling(50).std()

        # High-Low range
        dataframe["%-hl_ratio"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]

        # Volume momentum
        dataframe["%-volume_momentum"] = dataframe["volume"] / dataframe["volume"].rolling(10).mean()

        # Price momentum (multiple periods)
        for period in [5, 10, 20, 30]:
            dataframe[f"%-momentum_{period}"] = (
                dataframe["close"] / dataframe["close"].shift(period) - 1
            )

        # Trend strength (ADX derivative)
        dataframe["%-adx_14"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["%-adx_slope"] = dataframe["%-adx_14"].diff()

        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata, **kwargs) -> DataFrame:
        """
        Define ML targets - predict future price movement
        NOTE: CatboostRegressor (single target) only supports one target.
        Using CatboostRegressorMultiTarget would support multiple targets.
        For now, focusing on primary target: future price movement.
        """
        # Primary target: future price movement (next 24 candles mean)
        label_period = self.freqai_info["feature_parameters"]["label_period_candles"]

        dataframe["&-s_close"] = (
            dataframe["close"]
            .shift(-label_period)
            .rolling(label_period)
            .mean()
            / dataframe["close"]
            - 1
        )

        # NOTE: Commenting out secondary targets - CatboostRegressor supports only 1 target
        # To use multiple targets, switch to CatboostRegressorMultiTarget in config

        # # Secondary target: volatility (for confidence estimation)
        # dataframe["&-s_volatility"] = (
        #     dataframe["close"]
        #     .shift(-label_period)
        #     .rolling(label_period)
        #     .std()
        #     / dataframe["close"]
        # )

        # # Tertiary target: max profit potential
        # dataframe["&-s_max_profit"] = (
        #     dataframe["high"]
        #     .shift(-label_period)
        #     .rolling(label_period)
        #     .max()
        #     / dataframe["close"]
        #     - 1
        # )

        # # Quaternary target: max drawdown risk
        # dataframe["&-s_max_drawdown"] = (
        #     dataframe["low"]
        #     .shift(-label_period)
        #     .rolling(label_period)
        #     .min()
        #     / dataframe["close"]
        #     - 1
        # )

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate indicators - FreqAI will handle feature engineering
        """
        # Basic NFI indicators for fallback logic
        dataframe['RSI_14'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['RSI_3'] = ta.RSI(dataframe, timeperiod=3)
        dataframe['MFI_14'] = ta.MFI(dataframe, timeperiod=14)
        dataframe['ADX_14'] = ta.ADX(dataframe, timeperiod=14)

        # EMA ribbons
        for ema_period in [12, 26, 50, 100, 200]:
            dataframe[f'EMA_{ema_period}'] = ta.EMA(dataframe, timeperiod=ema_period)

        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lower'] = bollinger["lower"]
        dataframe['bb_mid'] = bollinger["mid"]
        dataframe['bb_upper'] = bollinger["upper"]
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_mid']

        # Volume
        dataframe['volume_mean_20'] = dataframe['volume'].rolling(20).mean()

        # Start FreqAI - this will populate all the ML features and predictions
        dataframe = self.freqai.start(dataframe, metadata, self)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry logic combining ML predictions with NFI conditions
        """
        # Long entry conditions - LONG ONLY with relaxed filters
        enter_long_conditions = [
            # ML prediction must be active
            (dataframe['do_predict'] == 1),
            # Require positive prediction (relaxed for more opportunities)
            (dataframe['&-s_close'] > 0.0001),  # 0.01% minimum

            # Add trend confirmation - only enter long in uptrend or oversold
            (
                (dataframe['EMA_12'] > dataframe['EMA_26']) |  # Uptrend
                (dataframe['RSI_14'] < 35)  # Or oversold
            ),

            # Avoid choppy/low volatility markets (relaxed)
            (dataframe['bb_width'] > 0.015),  # Minimum 1.5% BB width

            # Volume confirmation
            (dataframe['volume'] > 0)
        ]

        if enter_long_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, enter_long_conditions),
                ['enter_long', 'enter_tag']
            ] = (1, 'ml_long')

        # Short entry conditions - DISABLED (long only strategy)
        # User requested no shorts, focusing on long positions only
        # enter_short_conditions = []
        # Shorts are disabled

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit logic - IMPROVED: hold winners longer, exit on strong reversals
        """
        # Long exit conditions - only strong reversals
        exit_long_conditions = [
            (dataframe['do_predict'] == 1),
            # Exit on strong negative prediction or extreme overbought
            (
                (dataframe['&-s_close'] < -0.005) |  # Strong reversal: -0.5%
                (dataframe['RSI_14'] > 80)  # Extreme overbought
            )
        ]

        if exit_long_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, exit_long_conditions),
                'exit_long'
            ] = 1

        # Short exit conditions - hold winners longer
        exit_short_conditions = [
            (dataframe['do_predict'] == 1),
            # Exit on strong positive prediction or extreme oversold
            (
                (dataframe['&-s_close'] > 0.005) |  # Strong reversal: +0.5%
                (dataframe['RSI_14'] < 20)  # Extreme oversold
            )
        ]

        if exit_short_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, exit_short_conditions),
                'exit_short'
            ] = 1

        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time, entry_tag, side: str, **kwargs) -> bool:
        """
        Confirm trade entry with price checks
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) < 1:
            return False

        last_candle = dataframe.iloc[-1].squeeze()

        # Price slippage protection
        if side == "long":
            if rate > (last_candle["close"] * 1.0025):
                return False
        else:
            if rate < (last_candle["close"] * 0.9975):
                return False

        return True

    def custom_exit(self, pair: str, trade, current_time, current_rate,
                   current_profit, **kwargs) -> Optional[str]:
        """
        Custom exit logic based on ML confidence
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) < 1:
            return None

        last_candle = dataframe.iloc[-1].squeeze()

        # Emergency exit if ML confidence is lost
        if last_candle['do_predict'] != 1:
            return 'ml_confidence_lost'

        # Take profit if prediction confidence is high and profit target met
        if current_profit > 0.02:
            if trade.is_short:
                if last_candle['&-s_close'] > 0:
                    return 'ml_reversal_short'
            else:
                if last_candle['&-s_close'] < 0:
                    return 'ml_reversal_long'

        return None
