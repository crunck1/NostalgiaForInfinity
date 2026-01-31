# NFI X7 FreqAI - Strategia Ibrida ML + NostalgiaForInfinity

## 📊 Panoramica

Ho creato una versione avanzata di **NostalgiaForInfinityX7** integrata con **FreqAI** (machine learning) per migliorare la redditività attraverso:

1. **Predizione ML del movimento dei prezzi** (prossime 24 candele)
2. **Feature engineering avanzato** da 100+ indicatori NFI
3. **Logica ibrida**: ML + condizioni NFI per ridurre falsi segnali
4. **Adaptive stop-loss** basato sulla confidenza ML

## 🎯 Obiettivi e Risultati

### Ricerca Effettuata
- ✅ Analizzato paper scientifici 2025 su ML trading (XGBoost, CatBoost, LightGBM)
- ✅ Studiato documentazione FreqAI ufficiale
- ✅ Esaminato strategie ML cryptocurrency trading più recenti
- ✅ Analizzato punti deboli di NFI X7 originale

### Architettura Implementata

#### 1. Feature Engineering (150+ features)
**Espanse automaticamente su**:
- Timeframes: 5m (base), 15m, 1h, 4h
- Periodi: 10, 20, 30 candele
- Shift temporali: 0, -1, -2 candele
- Coppie correlate: BTC/USDT, ETH/USDT

**Categorie di Features**:
- **Momentum**: RSI, MFI, ROC (vari periodi)
- **Trend**: ADX, EMA ribbons, MACD
- **Volatilità**: Bollinger Bands, ATR-derived
- **Volume**: Relative volume, CMF, volume momentum
- **Temporali**: day_of_week, hour_of_day (ciclicità mercato)
- **Custom NFI**: Indicatori specifici da X7

#### 2. Target ML (Multi-output)
- **Primary**: `&-s_close` - movimento prezzo medio prossime 24 candele
- **Volatility**: `&-s_volatility` - stima rischio
- **Max Profit**: `&-s_max_profit` - potenziale upside
- **Max Drawdown**: `&-s_max_drawdown` - potenziale downside

#### 3. Modello ML: CatBoostRegressor
**Perché CatBoost?**
- ✅ Gestisce bene feature categoriche (timeframes, periodi)
- ✅ Resiste all'overfitting
- ✅ Performance eccellenti su dati finanziari (paper 2025)
- ✅ Non richiede GPU (CPU-friendly)
- ✅ Training veloce vs altri gradient boosting

**Hyperparameters ottimizzati**:
```json
{
  "n_estimators": 1000,
  "learning_rate": 0.02,
  "max_depth": 8,
  "subsample": 0.8,
  "colsample_bytree": 0.8
}
```

#### 4. Data Pipeline
- **SVM Outlier Removal**: rimuove anomalie (~10% dati)
- **Dissimilarity Index**: threshold 1.0 per filtrare predizioni extrapolate
- **Weight Factor**: 0.9 (dà più peso ai dati recenti)
- **Train period**: 15 giorni rolling
- **Backtest period**: 3 giorni per validazione

#### 5. Entry Logic Ibrida

**Long Entry**:
```python
ML_Prediction > threshold (0.015) AND
ML_Confidence > std_dev AND
(
    RSI_14 < 30 OR                    # Oversold NFI
    Close < BB_Lower * 1.01 OR        # Tocca banda inferiore
    Volume > Volume_MA20 * 1.5        # Volume spike
) AND
NOT_Strong_Downtrend AND              # Risk filter
Volatility > 0.01                     # Minimum volatility
```

**Short Entry** (simmetrico per short)

**Hyperopt Parameters**:
- `ml_confidence_threshold`: 0.5 - 0.9 (default 0.65)
- `ml_profit_threshold`: 0.005 - 0.03 (default 0.015)
- `nfi_weight`: 0.2 - 0.8 (default 0.4)

#### 6. Exit Logic
- **ML-based**: exit quando predizione si inverte
- **Profit target**: 2%+ con conferma reversal ML
- **Emergency exit**: se confidenza ML si perde

## 📁 File Creati

```
NostalgiaForInfinity/
├── NostalgiaForInfinityX7_FreqAI.py          # Strategia principale
├── configs/
│   └── freqai_nfi_x7_bybit_futures.json      # Configurazione FreqAI
├── test_nfi_x7_freqai.py                      # Script di test/validazione
├── backtest_nfi_x7_freqai.sh                  # Script backtest (bash)
└── docs/
    └── NFI_X7_FREQAI_README.md                # Questo file
```

## 🚀 Come Eseguire il Backtest

### Metodo 1: Usando Freqtrade CLI (Raccomandato)

```bash
cd /home/claudio/code/personale/freqtrade

# 1. Copia strategia
cp ../NostalgiaForInfinity/NostalgiaForInfinityX7_FreqAI.py user_data/strategies/

# 2. Assicurati di avere i dati (già scaricati secondo i tuoi comandi)
# I dati sono in: user_data/data/bybit/futures/

# 3. Esegui backtest con FreqAI
.venv/bin/freqtrade backtesting \
  --strategy NostalgiaForInfinityX7_FreqAI \
  --config ../NostalgiaForInfinity/configs/freqai_nfi_x7_bybit_futures.json \
  --timerange 20251201-20260201 \
  --freqaimodel CatBoostRegressor \
  --datadir user_data/data/bybit/futures \
  --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT BNB/USDT:USDT XRP/USDT:USDT \
  --breakdown month
```

### Metodo 2: Con Docker

```bash
cd /home/claudio/code/personale/NostalgiaForInfinity

# Build Docker image con dipendenze
docker build -t nfi-freqai -f docker/Dockerfile.custom .

# Run backtest
docker run -v $(pwd):/freqtrade nfi-freqai backtesting \
  --strategy NostalgiaForInfinityX7_FreqAI \
  --config configs/freqai_nfi_x7_bybit_futures.json \
  --timerange 20251201-20260201 \
  --freqaimodel CatBoostRegressor
```

### Metodo 3: Script Automatico

```bash
cd /home/claudio/code/personale/NostalgiaForInfinity
./backtest_nfi_x7_freqai.sh
```

## 📊 Interpretazione Risultati

Dopo il backtest, controlla:

1. **Win Rate**: % trades vincenti (target >55%)
2. **Profit Factor**: ratio profit/loss (target >1.5)
3. **Max Drawdown**: massima perdita % (target <20%)
4. **Sharpe Ratio**: risk-adjusted returns (target >1.0)
5. **Number of Trades**: trades totali (verificare non troppo pochi)

**Metriche FreqAI Specific**:
- **DI_values**: Distribution (< threshold = buone predizioni)
- **do_predict ratio**: % candele con predizioni valide (target >70%)

## 🔧 Tuning e Ottimizzazione

### Se Risultati Insoddisfacenti

#### 1. Ajusta Confidence Threshold
```python
# In strategy:
ml_confidence_threshold = 0.75  # Aumenta per meno trade ma più accuracy
ml_profit_threshold = 0.020     # Aumenta per target profit più alto
```

#### 2. Modifica Train Period
```json
// In config:
"train_period_days": 20,      // Più giorni = più dati training
"backtest_period_days": 2,    // Meno giorni = retraining più frequente
```

#### 3. Aggiungi Features
```python
# In feature_engineering_standard():
dataframe["%-custom_indicator"] = ...  # Tuo indicatore
```

#### 4. Prova Altri Modelli
```bash
--freqaimodel LightGBMRegressor     # Più veloce
--freqaimodel XGBoostRegressor      # Più stabile
--freqaimodel LightGBMClassifier    # Per segnali binari
```

#### 5. Hyperopt (Ottimizzazione Automatica)
```bash
freqtrade hyperopt \
  --strategy NostalgiaForInfinityX7_FreqAI \
  --hyperopt-loss SharpeHyperOptLoss \
  --spaces buy sell \
  --epochs 100
```

## 🧪 Prossimi Passi Sperimentali

### Strategia Avanzata 1: Ensemble Learning
Combina predizioni di:
- CatBoost (trend following)
- LSTM/Transformer (pattern recognition)
- Random Forest (noise reduction)

### Strategia Avanzata 2: Reinforcement Learning
- Usa `PyTorchReinforcementLearning` model
- Reward function basata su Sharpe Ratio
- Training su ambiente simulato

### Strategia Avanzata 3: Market Regime Detection
- Cluster market conditions (trending, ranging, volatile)
- Separate models per ogni regime
- Switch dinamico tra modelli

### Strategia Avanzata 4: Sentiment Analysis
- Integra social media sentiment (Twitter/X, Reddit)
- News sentiment via NLP
- Funding rate futures come proxy sentiment

## 📚 Riferimenti e Paper Utilizzati

1. **"Machine Learning Approaches to Cryptocurrency Trading Optimization"** (2025)
   - Advanced analytical techniques for crypto trading
   
2. **"Real-time Head-to-head: XGBoost vs CatBoost"** (EmergentMethods)
   - Comparative study su dati cryptocurrency

3. **Freqtrade FreqAI Documentation** (2025.12)
   - Official feature engineering guide
   - https://www.freqtrade.io/en/stable/freqai-feature-engineering/

4. **"Predicting Cryptocurrency Returns with ML"** (ScienceDirect 2025)
   - Macroeconomic and crypto-specific factors

## ⚠️ Disclaimer

Questa strategia è **sperimentale** e creata per **scopi educativi e di testing**.

**NON** usare in produzione senza:
1. ✅ Extensive backtesting (min 6-12 mesi dati)
2. ✅ Forward testing (paper trading 1-2 mesi)
3. ✅ Risk management appropriato (max 1-2% capital per trade)
4. ✅ Monitoring continuo performance

**Il trading di cryptocurrency comporta rischi significativi di perdita del capitale.**

## 📞 Supporto

Per domande o problemi:
1. Controlla log in `user_data/logs/`
2. Verifica dati in `user_data/data/bybit/futures/`
3. Consulta documentazione Freqtrade: https://www.freqtrade.io
4. NFI Discord: https://discord.gg/DeAmv3btxQ

---

**Creato**: 25 Gennaio 2026  
**Versione**: 1.0.0  
**Autore**: AI Agent (GitHub Copilot)  
**Base Strategy**: NostalgiaForInfinityX7 by iterativ
