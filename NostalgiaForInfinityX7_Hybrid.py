"""
NostalgiaForInfinityX7_Hybrid - ML-Filtered Strategy
FreqAI-enabled strategy that uses X7 signals with ML filtering
"""

import logging
import numpy as np
import pandas as pd
from pandas import DataFrame
from typing import Optional, Dict

from freqtrade.strategy import IStrategy, DecimalParameter
from NostalgiaForInfinityX7 import NostalgiaForInfinityX7

log = logging.getLogger(__name__)


class NostalgiaForInfinityX7_Hybrid(IStrategy):
    """Hybrid: X7 signals + ML filter"""
    
    INTERFACE_VERSION = 3
    _x7_instance = None
    
    minimal_roi = {"0": 10}
    stoploss = -0.99
    trailing_stop = False
    use_custom_stoploss = False
    
    timeframe = '5m'
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True
    startup_candle_count: int = 800
    can_short = True
    
    ml_confidence_long = DecimalParameter(0.50, 0.85, default=0.60, space='buy', optimize=True, load=True)
    ml_confidence_short = DecimalParameter(0.50, 0.85, default=0.60, space='sell', optimize=True, load=True)
    ml_exit_on_confidence_loss = True
    ml_exit_confidence_threshold = DecimalParameter(0.40, 0.60, default=0.45, space='sell', optimize=True, load=True)
    
    def _get_x7_instance(self):
        if self._x7_instance is None:
            self._x7_instance = NostalgiaForInfinityX7(self.config)
            self._x7_instance.dp = self.dp
            self._x7_instance.wallets = self.wallets
        return self._x7_instance
    
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: dict, **kwargs) -> DataFrame:
        if 'rsi_14' in dataframe.columns:
            dataframe["%-rsi"] = dataframe["rsi_14"]
        if 'rsi_slow' in dataframe.columns:
            dataframe["%-rsi_slow"] = dataframe["rsi_slow"]
        
        for ema in ['ema_12', 'ema_26', 'ema_50', 'ema_100', 'ema_200']:
            if ema in dataframe.columns:
                dataframe[f"%-{ema}"] = dataframe[ema]
                dataframe[f"%-pct_close_{ema}"] = (dataframe["close"] - dataframe[ema]) / dataframe[ema]
        
        for bb in ['bb_lowerband', 'bb_middleband', 'bb_upperband', 'bb_width']:
            if bb in dataframe.columns:
                dataframe[f"%-{bb}"] = dataframe[bb]
        
        dataframe["%-volume"] = dataframe["volume"]
        dataframe["%-volume_mean_12"] = dataframe["volume"].rolling(12).mean()
        dataframe["%-close_pct_change"] = dataframe["close"].pct_change()
        dataframe["%-high_low_pct"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]
        
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        if 'ema_12' in dataframe.columns:
            dataframe["%-pct_close_ema12"] = (dataframe["close"] - dataframe["ema_12"]) / dataframe["ema_12"]
        if 'ema_26' in dataframe.columns:
            dataframe["%-pct_close_ema26"] = (dataframe["close"] - dataframe["ema_26"]) / dataframe["ema_26"]
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        if 'rsi_14' in dataframe.columns:
            dataframe["%-rsi_normalized"] = dataframe["rsi_14"] / 100.0
        
        if 'ema_12' in dataframe.columns and 'ema_26' in dataframe.columns:
            dataframe["%-ema12_ema26_cross"] = (dataframe["ema_12"] > dataframe["ema_26"]).astype(int)
        
        dataframe["%-atr"] = dataframe.get("atr", dataframe["high"] - dataframe["low"])
        dataframe["%-atr_pct"] = dataframe["%-atr"] / dataframe["close"]
        
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["&-s_close"] = dataframe["close"].shift(-24).rolling(5).mean()
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        x7 = self._get_x7_instance()
        dataframe = x7.populate_indicators(dataframe, metadata)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        x7 = self._get_x7_instance()
        dataframe = x7.populate_entry_trend(dataframe, metadata)
        
        if '&-s_close' in dataframe.columns and 'do_predict' in dataframe.columns:
            dataframe['ml_upside'] = (dataframe['&-s_close'] - dataframe['close']) / dataframe['close']
            
            conditions_ml_long = (
                (dataframe['do_predict'] == 1) &
                (dataframe['ml_upside'] > self.ml_confidence_long.value / 100.0)
            )
            
            if 'enter_long' in dataframe.columns and dataframe['enter_long'].sum() > 0:
                original_signals = dataframe['enter_long'].sum()
                dataframe.loc[~conditions_ml_long, 'enter_long'] = 0
                filtered_signals = dataframe['enter_long'].sum()
                
                if original_signals > filtered_signals:
                    log.info(
                        f"{metadata['pair']}: ML filtered {original_signals - filtered_signals} "
                        f"X7 signals ({filtered_signals}/{original_signals} kept)"
                    )
            
            if self.can_short and 'enter_short' in dataframe.columns:
                conditions_ml_short = (
                    (dataframe['do_predict'] == 1) &
                    (dataframe['ml_upside'] < -self.ml_confidence_short.value / 100.0)
                )
                if dataframe['enter_short'].sum() > 0:
                    dataframe.loc[~conditions_ml_short, 'enter_short'] = 0
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        x7 = self._get_x7_instance()
        dataframe = x7.populate_exit_trend(dataframe, metadata)
        
        if self.ml_exit_on_confidence_loss and '&-s_close' in dataframe.columns:
            if 'ml_upside' not in dataframe.columns:
                dataframe['ml_upside'] = (dataframe['&-s_close'] - dataframe['close']) / dataframe['close']
            
            conditions_ml_exit_long = (
                (dataframe['do_predict'] == 1) &
                (dataframe['ml_upside'] < self.ml_exit_confidence_threshold.value / 100.0)
            )
            
            if 'exit_long' in dataframe.columns:
                dataframe.loc[conditions_ml_exit_long, 'exit_long'] = 1
                dataframe.loc[conditions_ml_exit_long, 'exit_tag'] = 'ml_confidence_lost'
            
            if self.can_short and 'exit_short' in dataframe.columns:
                conditions_ml_exit_short = (
                    (dataframe['do_predict'] == 1) &
                    (dataframe['ml_upside'] > -self.ml_exit_confidence_threshold.value / 100.0)
                )
                dataframe.loc[conditions_ml_exit_short, 'exit_short'] = 1
                dataframe.loc[conditions_ml_exit_short, 'exit_tag'] = 'ml_confidence_lost_short'
        
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time, entry_tag, side: str, **kwargs) -> bool:
        x7 = self._get_x7_instance()
        return x7.confirm_trade_entry(pair, order_type, amount, rate, time_in_force,
                                     current_time, entry_tag, side, **kwargs)

    def version(self) -> str:
        return "v17.X7-Hybrid-ML-Filter"
