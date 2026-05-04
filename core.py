"""
Sell Put v5.0 核心模組
P0 修正：IVR→IV/HV，DTE 多到期日選擇
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class StockData:
    ticker: str
    sector: str
    price: float
    mkt_cap: float
    beta: float
    fwd_pe: float
    ttm_pe: float
    fcf: float
    revenue_growth: float
    low_52w: float
    high_52w: float
    rsi: float
    hv: float
    earnings_date: Optional[datetime]

@dataclass
class OptionData:
    exp: str
    dte: int
    strike: float
    iv: float
    bid: float
    ask: float
    oi: int
    spread: float
    delta: float
    theta: float = 0.0   # Daily theta (decay in $)
    vega: float = 0.0   # Vega ($ per 1% IV change)
    gamma: float = 0.0   # Gamma: dDelta/dS per $1 move in underlying
    strike_deviation: float = 0.0  # (actual_strike - target_strike) / target_strike; positive=ITM, negative=OTM
    tier: str = 'unknown'

@dataclass
class ScoreResult:
    ticker: str
    sector: str
    grade: str
    adj_total: float
    raw_total: float
    scores: Dict[str, int]
    stock: StockData
    option: Optional[OptionData] = None
    metrics: Optional[Dict[str, float]] = None
    is_forbidden: bool = False
    warnings: Optional[List[str]] = None
    suggested_strike: Optional[float] = None  # 建議履約價（8-10% OTM）


class SellPutV5Skill:
    """Sell Put v5.0 Skill 核心類"""
    
    SECTORS = {
        'MU': 'Semiconductor', 'TSM': 'Semiconductor', 'AVGO': 'Semiconductor',
        'AMD': 'Semiconductor', 'NVDA': 'Semiconductor', 'MRVL': 'Semiconductor',
        'ALAB': 'Biotech', 'GOOGL': 'Cloud/AI', 'VST': 'Utilities',
        'AAPL': 'Consumer', 'AMZN': 'Cloud/AI', 'ARM': 'Semiconductor',
        'MSFT': 'Cloud/AI', 'INTC': 'Semiconductor', 'TSLA': 'EV',
        'QQQ': 'ETF', 'VRT': 'Infrastructure/Datacenter'
    }
    
    def __init__(self, tickers: List[str], today: Optional[datetime] = None):
        self.tickers = tickers
        self.today = today or datetime.now()
        self.vix = 20.0
        self.vix_reg = 2
        self.vix_adj = 0.0
        self.pos_scale = 1.0
        self.vix_label = '正常中性'

    # ------------------------------------------------------------------
    # BSM Implied Volatility Calculator (bisection method)
    # ------------------------------------------------------------------
    def _bsm_put_price(self, S, K, T, r, sigma):
        """Black-Scholes-Merton put price."""
        if T <= 0 or sigma <= 0:
            return max(K - S, 0)
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    def _bsm_vega(self, S, K, T, r, sigma):
        """Vega (derivative of put price w.r.t. sigma)."""
        if T <= 0 or sigma <= 0:
            return 0
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        return S * np.sqrt(T) * norm.pdf(d1)

    def _calc_implied_vol(self, S, K, T, r, market_price, is_call=False, tol=1e-6, max_iter=100):
        """
        Back-calculate implied volatility from market price using bisection.
        Returns IV as a decimal (e.g. 0.72 for 72%), or None if cannot converge.
        """
        if T <= 0 or market_price <= 0:
            return None
        
        # Intrinsic value bounds
        if is_call:
            intrinsic = max(S - K, 0)
        else:
            intrinsic = max(K - S, 0)
        
        if market_price < intrinsic:
            return None
        
        # Search range: 1% to 500% IV
        sigma_low, sigma_high = 0.01, 5.0
        
        # Initial bounds check
        p_low = self._bsm_put_price(S, K, T, r, sigma_low)
        p_high = self._bsm_put_price(S, K, T, r, sigma_high)
        
        if not (p_low <= market_price <= p_high):
            # Widen range
            sigma_low = 0.001
            sigma_high = 10.0
        
        for _ in range(max_iter):
            sigma_mid = (sigma_low + sigma_high) / 2
            price_mid = self._bsm_put_price(S, K, T, r, sigma_mid)
            if abs(price_mid - market_price) < tol:
                return sigma_mid
            if price_mid < market_price:
                sigma_low = sigma_mid
            else:
                sigma_high = sigma_mid
            if sigma_high - sigma_low < 1e-8:
                break
        
        return (sigma_low + sigma_high) / 2
        
    def fetch_stock_data(self, ticker: str) -> StockData:
        """抓取股票基礎數據"""
        tk = yf.Ticker(ticker)
        info = tk.info
        
        # Price: use currentPrice or regularMarketPrice, handle None values
        price = info.get('currentPrice') or info.get('regularMarketPrice') or 0
        mkt_cap = info.get('marketCap', 0)
        beta = info.get('beta', 1.0)
        fwd_pe_raw = info.get('forwardPE', 0)
        ttm_pe = info.get('trailingPE', 0) or 0
        fwd_pe = fwd_pe_raw if (fwd_pe_raw and fwd_pe_raw > 0) else (ttm_pe if ttm_pe > 0 else 0)
        fcf = info.get('freeCashflow', 0)
        revenue_growth = info.get('revenueGrowth', 0)
        low_52w = info.get('fiftyTwoWeekLow', 0)
        high_52w = info.get('fiftyTwoWeekHigh', 0)
        
        # RSI & HV
        hist = tk.history(period='3mo')
        if len(hist) >= 60:
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
            
            log_returns = np.log(hist['Close'] / hist['Close'].shift(1))
            hv_30 = log_returns.rolling(window=30).std() * np.sqrt(252) * 100
            current_hv = hv_30.iloc[-1] if not pd.isna(hv_30.iloc[-1]) else 30
        else:
            current_rsi = 50
            current_hv = 30
        
        # 財報日期 - 多層次抓取策略
        earnings_date = None
        try:
            # 策略1: calendar 屬性 (可能是 dict 或 DataFrame)
            calendar = tk.calendar
            if calendar is not None:
                if isinstance(calendar, dict):
                    # dict 格式
                    if 'Earnings Date' in calendar:
                        date_val = calendar['Earnings Date']
                        if isinstance(date_val, list) and len(date_val) > 0:
                            earnings_date = pd.to_datetime(date_val[0])
                        elif date_val is not None:
                            earnings_date = pd.to_datetime(date_val)
                elif hasattr(calendar, 'empty') and not calendar.empty:
                    # DataFrame 格式
                    if 'Earnings Date' in calendar.columns:
                        date_val = calendar['Earnings Date'].iloc[0]
                        if pd.notna(date_val):
                            earnings_date = pd.to_datetime(date_val)
                    elif 'Earnings Date Low' in calendar.columns:
                        date_val = calendar['Earnings Date Low'].iloc[0]
                        if pd.notna(date_val):
                            earnings_date = pd.to_datetime(date_val)
        except Exception:
            pass
        
        # 策略2: info 中的 nextEarningsDate
        if earnings_date is None:
            try:
                next_earnings = info.get('nextEarningsDate')
                if next_earnings:
                    earnings_date = pd.to_datetime(next_earnings)
            except Exception:
                pass
        
        # 策略3: info 中的 earningsDate
        if earnings_date is None:
            try:
                earnings_date_str = info.get('earningsDate')
                if earnings_date_str:
                    if isinstance(earnings_date_str, list) and len(earnings_date_str) > 0:
                        earnings_date = pd.to_datetime(earnings_date_str[0])
                    else:
                        earnings_date = pd.to_datetime(earnings_date_str)
            except Exception:
                pass
        
        return StockData(
            ticker=ticker,
            sector=self.SECTORS.get(ticker, 'Unknown'),
            price=price,
            mkt_cap=mkt_cap,
            beta=beta,
            fwd_pe=fwd_pe,
            ttm_pe=ttm_pe,
            fcf=fcf,
            revenue_growth=revenue_growth,
            low_52w=low_52w,
            high_52w=high_52w,
            rsi=current_rsi,
            hv=current_hv,
            earnings_date=earnings_date
        )
    
    def fetch_vix(self) -> Tuple[float, int, float, float, str]:
        """抓取 VIX 並確定體制"""
        try:
            vix = yf.Ticker('^VIX')
            vix_info = vix.info
            self.vix = vix_info.get('regularMarketPrice', vix_info.get('currentPrice', 20))
        except:
            self.vix = 20
        
        if self.vix < 15:
            self.vix_reg, self.vix_adj, self.pos_scale, self.vix_label = 1, 0.05, 1.0, '極度貪婪'
        elif self.vix < 20:
            self.vix_reg, self.vix_adj, self.pos_scale, self.vix_label = 2, 0, 1.0, '正常中性'
        elif self.vix < 25:
            self.vix_reg, self.vix_adj, self.pos_scale, self.vix_label = 3, -0.03, 0.85, '輕微焦慮'
        elif self.vix < 35:
            self.vix_reg, self.vix_adj, self.pos_scale, self.vix_label = 4, -0.05, 0.70, '恐慌'
        else:
            self.vix_reg, self.vix_adj, self.pos_scale, self.vix_label = 5, 0, 0, '崩潰'
        
        return self.vix, self.vix_reg, self.vix_adj, self.pos_scale, self.vix_label
    
    def fetch_option_data(self, stock: StockData) -> OptionData:
        """抓取期權數據（多到期日選擇 + 動態 DTE 窗口 + 重試保護）"""
        ticker = stock.ticker
        price = stock.price

        # 計算距財報天數（用於動態 DTE 窗口）
        days_to_earnings = 999
        if stock.earnings_date:
            days_to_earnings = (stock.earnings_date - self.today).days

        def covers_earnings(exp_str):
            """判斷到期日是否涵蓋財報（到期日在財報日之後 7 天內，即 earnings 落在期權有效期內）"""
            if not stock.earnings_date:
                return False
            exp_date = datetime.strptime(exp_str, '%Y-%m-%d')
            # 到期日在財報後 7 天內 = 到期日 - 財報日 < 7
            # 到期日必須在財報日之後（earnings 還沒發生）才有意義
            return exp_date > stock.earnings_date and (exp_date - stock.earnings_date).days < 7

        # 根據距財報天數，動態設定 DTE 窗口
        #   1. 距財報 >30天 → 正常選 30-45 DTE
        #   2. 距財報 7-30天 → 擴展到 14-60，強制不涵蓋財報
        #   3. 距財報 ≤7天  → 允許 DTE<20，強制不涵蓋
        #   4. 財報已過（days_to_earnings < 0）→ 正常窗口（30-45）
        if days_to_earnings < 0 or days_to_earnings > 30:
            dte_window = (30, 45)
        elif days_to_earnings > 7:
            dte_window = (14, 60)
        else:
            dte_window = (5, 60)

        # 特別檢查：即使 DTE 在窗口內，若 earnings 落在窗口內（5/15-5/29 for NVDA），
        # 也視為「涵蓋」，退而求次選更早到期日
        def earnings_in_window():
            """判斷 earnings 日期是否落在 [today+DTE窗口下界, today+45] 區間內"""
            if not stock.earnings_date:
                return False
            win_end = self.today + timedelta(days=45)
            return self.today <= stock.earnings_date <= win_end

        force_early_window = earnings_in_window()

        for attempt in range(3):
            try:
                tk = yf.Ticker(ticker)
                exps = tk.options
                if not exps:
                    if attempt < 2:
                        import time; time.sleep(1.5)
                        continue
                    return OptionData(exp=None, dte=30, strike=price*0.95, iv=30, bid=0, ask=0, oi=0, spread=5, delta=-0.5, tier='t3')

                # 篩選 20-60 DTE
                valid_exps = []
                for exp in exps:
                    exp_date = datetime.strptime(exp, '%Y-%m-%d')
                    dte = (exp_date - self.today).days
                    if 20 <= dte <= 60:
                        valid_exps.append((exp, dte))

                # 從有效到期日中，選「不涵蓋財報 + 在動態窗口內」的
                # 若 earnings 落在 [today+DTE窗口下界, today+45] 區間，額外排除臨界到期日
                if force_early_window and days_to_earnings > 7:
                    # 強制只選 DTE <= (earnings - today) - 7 的到期日（即 earnings 後至少7天）
                    hard_deadline_dte = days_to_earnings - 7
                    safe_and_valid = [
                        (e, d) for e, d in valid_exps
                        if d <= hard_deadline_dte and not covers_earnings(e)
                    ]
                else:
                    safe_and_valid = [
                        (e, d) for e, d in valid_exps
                        if not covers_earnings(e) and dte_window[0] <= d <= dte_window[1]
                    ]

                if safe_and_valid:
                    selected_exp, selected_dte = min(safe_and_valid, key=lambda x: abs(x[1] - 37))
                elif valid_exps:
                    # 沒有安全到期日 → 全都涵蓋財報（財報太近），退而求次
                    fallback_exps = [(e, d) for e, d in valid_exps if dte_window[0] <= d <= dte_window[1]]
                    if fallback_exps:
                        selected_exp, selected_dte = min(fallback_exps, key=lambda x: x[1])
                    else:
                        return OptionData(exp=None, dte=0, strike=price*0.95, iv=0, bid=0, ask=0, oi=0, spread=5, delta=-0.5, tier='t3')
                else:
                    return OptionData(exp=None, dte=30, strike=price*0.95, iv=30, bid=0, ask=0, oi=0, spread=5, delta=-0.5, tier='t3')

                # 抓 Put 數據：優先使用有真實報價的最近 ATM Put，IV 無效時用 BSM 回算
                opt = tk.option_chain(selected_exp)
                puts = opt.puts
                puts['dist_from_atm'] = abs(puts['strike'] - price)

                iv = 0.0
                bid = 0.0
                ask = 0.0
                strike = price * 0.95
                oi = 0
                spread = 5.0

                # ----------------------------------------------------------------
                # Step 1: 找有 bid/ask 的 puts（流動性最好）
                # ----------------------------------------------------------------
                active = puts[puts['bid'] > 0].copy()

                if not active.empty:
                    tier = 't1'  # t1: real bid/ask prices
                    # 選 dist_from_atm 最小的活躍 put
                    best = active.loc[active['dist_from_atm'].idxmin()]
                    strike = float(best['strike'])
                    bid = float(best['bid'])
                    ask = float(best['ask'])
                    oi = int(best['openInterest']) if not pd.isna(best['openInterest']) else 0
                    spread = (ask - bid) / ((ask + bid) / 2) * 100 if (ask + bid) > 0 else 5

                    # IV：優先用 yfinance 原生 IV（通常為 raw decimal，如 0.72）
                    raw_iv = best.get('impliedVolatility')
                    if raw_iv is not None and not pd.isna(raw_iv) and raw_iv > 0.001:
                        # yfinance 給的是小數 (0.72) 或少見的 (72)，取合理範圍內的值
                        # 如果 raw_iv > 1，認為它已經是百分比形式（如 72）
                        iv = raw_iv * 100 if raw_iv < 1.0 else raw_iv
                    else:
                        iv = 0.0

                    # 如果 yfinance IV 為 0 或不合理（ATM put 不該是 0），用 BSM 回算
                    if iv == 0 and bid > 0:
                        T_frac = selected_dte / 365.0
                        mp = (bid + ask) / 2  # midpoint
                        if mp > 0:
                            calc_iv = self._calc_implied_vol(
                                S=price, K=strike, T=T_frac,
                                r=0.045, market_price=mp
                            )
                            if calc_iv is not None:
                                iv = calc_iv * 100  # convert to %

                else:
                    # ----------------------------------------------------------------
                    # Step 2: 沒有 bid/ask → 用 lastPrice > 0 的最近 ATM put 做 BSM 回算
                    # ----------------------------------------------------------------
                    traded = puts[puts['lastPrice'] > 0].copy()
                    if not traded.empty:
                        tier = 't2'  # t2: lastPrice BSM back-calculation
                        near_atm = traded[traded['dist_from_atm'] < price * 0.05]  # 5% ATM range
                        if near_atm.empty:
                            near_atm = traded
                        best = near_atm.loc[near_atm['dist_from_atm'].idxmin()]
                        strike = float(best['strike'])
                        last_px = float(best['lastPrice'])
                        oi = int(best['openInterest']) if not pd.isna(best['openInterest']) else 0

                        # BSM IV 回算
                        T_frac = selected_dte / 365.0
                        calc_iv = self._calc_implied_vol(
                            S=price, K=strike, T=T_frac,
                            r=0.045, market_price=last_px
                        )
                        if calc_iv is not None:
                            iv = calc_iv * 100  # convert to %

                        # 參考性報價
                        bid = ask = last_px
                        spread = 0
                    else:
                        # ----------------------------------------------------------------
                        # Step 3: 完全沒有交易數據 → fallback：HV × 1.3 估算
                        # ----------------------------------------------------------------
                        atm_put = puts.loc[puts['dist_from_atm'].idxmin()]
                        strike = float(atm_put['strike'])
                        tier = 't3'  # t3: HV × 1.3 estimate
                        iv = stock.hv * 1.3  # IV ≈ HV × 1.3 是常見經驗值
                        spread = 10

                # ----------------------------------------------------------------
                # Black-Scholes Delta (for reference, even if IV is estimated)
                # ----------------------------------------------------------------
                # ── Black-Scholes Greeks (Delta, Theta, Vega) ──────────────────
                try:
                    S2, K2, T2, r2, sigma2 = price, strike, selected_dte/365, 0.045, max(iv, 1)/100
                    d1 = (np.log(S2/K2) + (r2 + 0.5*sigma2**2)*T2) / (sigma2*np.sqrt(T2))
                    d2 = d1 - sigma2*np.sqrt(T2)
                    delta = norm.cdf(d1) - 1
                    # Theta (daily, $): -S*sigma*pdf(d1)/(2*sqrt(T)) * exp(-r*T) / 365
                    theta = -0.5 * S2 * sigma2 * norm.pdf(d1) / np.sqrt(T2) * np.exp(-r2*T2) / 365
                    # Vega ($ per 1% IV change): S*sqrt(T)*pdf(d1)*0.01
                    vega = S2 * np.sqrt(T2) * norm.pdf(d1) * 0.01
                    # Gamma: dDelta/dS per $1 = S*sigma*sqrt(T)*pdf(d1) / (K^2 * sigma^2 * T)
                    gamma = norm.pdf(d1) / (S2 * K2 * sigma2 * sigma2 * T2) if T2 > 0 and sigma2 > 0 and K2 > 0 else 0.0
                except:
                    delta = -0.5
                    theta = 0.0
                    vega = 0.0
                    gamma = 0.0

                # Strike deviation: (actual - 8% OTM target) / target; positive=ITM, negative=deep OTM
                target_8pct = price * 0.92
                strike_deviation = (strike - target_8pct) / target_8pct if target_8pct > 0 else 0.0

                return OptionData(
                    exp=selected_exp, dte=selected_dte, strike=strike,
                    iv=iv, bid=bid, ask=ask, oi=oi, spread=spread, delta=delta,
                    theta=theta, vega=vega, gamma=gamma, strike_deviation=strike_deviation,
                    tier=tier
                )
            except Exception:
                if attempt < 2:
                    import time; time.sleep(1.5)
                    continue
                return OptionData(exp=None, dte=30, strike=price*0.95, iv=30, bid=0, ask=0, oi=0, spread=5, delta=-0.5, theta=0.0, vega=0.0, strike_deviation=0.0, tier='t3')

    
    def calculate_scores(self, stock: StockData, option: OptionData) -> Tuple[Dict[str, int], Dict[str, float]]:
        """計算十維度評分"""
        scores = {}
        metrics = {}
        
        price = stock.price
        hv = stock.hv
        iv = option.iv
        
        # ① 距52週低點
        dist_low = (price / stock.low_52w - 1) * 100 if stock.low_52w > 0 else 100
        if dist_low >= 200: scores['s1'] = 23
        elif dist_low >= 150: scores['s1'] = 20
        elif dist_low >= 100: scores['s1'] = 17
        elif dist_low >= 50: scores['s1'] = 13
        elif dist_low >= 30: scores['s1'] = 9
        elif dist_low >= 15: scores['s1'] = 5
        else: scores['s1'] = 3
        metrics['dist_low'] = dist_low
        
        # ② IV/HV 比率（P0修正）
        iv_hv_ratio = iv / hv if hv > 0 else 1.0
        if iv_hv_ratio > 1.5: scores['s2'] = 18
        elif iv_hv_ratio > 1.3: scores['s2'] = 15
        elif iv_hv_ratio > 1.1: scores['s2'] = 12
        elif iv_hv_ratio > 0.9: scores['s2'] = 9
        elif iv_hv_ratio > 0.7: scores['s2'] = 6
        else: scores['s2'] = 3
        metrics['iv_hv_ratio'] = iv_hv_ratio
        
        # ③ 基本面
        if stock.ticker == 'QQQ':
            # P0修正④：QQQ 直接設 s3=0，無需計算
            scores['s3'] = 0
        else:
            # P0修正②：FCF<0 或 PE>100 → 硬上限 s3≤5
            if stock.fwd_pe <= 0 or stock.fwd_pe > 100:
                pe_score = 0
            elif stock.fwd_pe <= 20: pe_score = 9
            elif stock.fwd_pe < 30: pe_score = 7   # 20-30（不含30），與文檔一致
            elif stock.fwd_pe <= 50: pe_score = 5   # 30-50（含30）
            else: pe_score = 2

            if stock.fcf > 10e9: fcf_score = 10
            elif stock.fcf >= 1e9: fcf_score = 7  # 含$1B
            elif stock.fcf > 0: fcf_score = 3
            else: fcf_score = 0

            if stock.revenue_growth >= 0.20: growth_score = 9
            elif stock.revenue_growth >= 0.10: growth_score = 6
            elif stock.revenue_growth >= 0: growth_score = 3
            else: growth_score = 1

            raw_s3 = pe_score + fcf_score + growth_score
            # FCF 為負時，硬上限 5 分
            if stock.fcf < 0:
                scores['s3'] = min(raw_s3, 5)
            else:
                scores['s3'] = raw_s3
        
        # ④ RSI
        rsi = stock.rsi
        if 40 <= rsi <= 60: scores['s4'] = 9
        elif 30 <= rsi < 40 or 60 < rsi <= 70: scores['s4'] = 6
        elif 20 <= rsi < 30 or 70 < rsi <= 80: scores['s4'] = 3
        else: scores['s4'] = 1
        
        # ⑤ 市值+Beta
        mkt_score = 3 if stock.mkt_cap > 500e9 else 2 if stock.mkt_cap > 100e9 else 1 if stock.mkt_cap > 50e9 else 0
        beta_score = 5 if stock.beta <= 1.5 else 4
        scores['s5'] = mkt_score + beta_score
        
        # ⑥ 期權流動性
        spread = option.spread
        oi = option.oi
        spread_score = 5 if spread < 2 else 4 if spread < 5 else 2 if spread < 10 else 0
        oi_score = 4 if oi > 10000 else 3 if oi > 5000 else 1 if oi > 1000 else 0
        scores['s6'] = spread_score + oi_score
        
        # ⑦ 事件風險
        if stock.earnings_date:
            days_to_earnings = (stock.earnings_date - self.today).days
        else:
            days_to_earnings = 999 if stock.ticker == 'QQQ' else 20  # 無財報預設 20天→s7=3（保守），不觸發forbidden
        
        if days_to_earnings > 30: scores['s7'] = 5
        elif days_to_earnings >= 15: scores['s7'] = 3  # 15-30（含15）
        elif days_to_earnings >= 7: scores['s7'] = 1   # 7-14（含7）
        elif days_to_earnings < 0: scores['s7'] = 5      # 已過財報：下次財報約90天後，事件風險極低 → s7=5（與>30天同級）
        else: scores['s7'] = 0
        metrics['days_to_earnings'] = days_to_earnings
        
        # ⑧ PoP×ROCC（P0修正①：DTE可能為0時保護）
        dte = max(option.dte, 1)  # 防止除零
        bid = option.bid
        margin = price * 0.20

        if 30 <= dte <= 45: dte_factor = 1.10
        elif 20 <= dte <= 29: dte_factor = 1.00   # 含 DTE=20（動態窗口擴展）
        elif 45 < dte <= 60: dte_factor = 0.95    # P2修正：45<dte（不含45，否則被上面吃掉）
        else: dte_factor = 0.85

        rocc_raw = (bid / margin) * (365 / dte) * 100 if margin > 0 else 0
        rocc_adj = rocc_raw * dte_factor
        pop = 1 - abs(option.delta)
        efficiency = rocc_adj * pop

        if option.dte == 0:
            scores['s8'] = 0  # 無法計算
        elif efficiency > 400: scores['s8'] = 9
        elif efficiency > 250: scores['s8'] = 7
        elif efficiency > 150: scores['s8'] = 5
        elif efficiency > 80: scores['s8'] = 3
        else: scores['s8'] = 1
        
        metrics['rocc_raw'] = rocc_raw
        metrics['rocc_adj'] = rocc_adj
        metrics['pop'] = pop
        metrics['efficiency'] = efficiency
        # R-D: Margin efficiency (annual return relative to 20% cash-secured margin)
        # Net premium after spread: bid * (1 - spread%/100)
        net_premium = bid * (1 - spread / 100) if bid > 0 else 0
        margin_used = price * 0.20
        margin_efficiency = (net_premium / margin_used) * (365 / dte) * 100 if margin_used > 0 else 0
        metrics['margin_efficiency'] = round(margin_efficiency, 1)
        
        # ── 年化收益率與時機（用於 report_formatter.py 顯示）
        # P0修正④：年化% DTE口徑與表格DTE一致（均用 days_to_earnings）
        # R-C: 扣除 Spread 摩擦成本
        import math
        stock_dte = days_to_earnings if 0 < days_to_earnings < 999 else dte
        gross_return = iv * 0.05 * math.sqrt(stock_dte / 365) * 100
        # 實際權利金 =理論最大值 × (1 - spread%/100)
        spread_factor = max(1 - spread / 100, 0.5)  # 至少留50%
        metrics['annual_return'] = round(gross_return * spread_factor, 1) if stock_dte > 0 else 0.0
        if option.dte < 14 and stock.rsi > 60:
            metrics['timing'] = '短線'
        elif option.dte <= 45:
            metrics['timing'] = '波段'
        else:
            metrics['timing'] = '長期'
        
        # ⑨ 52W位置
        if stock.high_52w > stock.low_52w:
            pos_52w = (price - stock.low_52w) / (stock.high_52w - stock.low_52w) * 100
        else:
            pos_52w = 50
        
        if pos_52w < 30: scores['s9'] = 4
        elif pos_52w < 50: scores['s9'] = 3
        elif pos_52w < 70: scores['s9'] = 2
        else: scores['s9'] = 1
        metrics['pos_52w'] = pos_52w
        
        # ⑩ Skew
        skew_z = (iv - hv) / hv if hv > 0 else 0
        if skew_z > 2.0: scores['s10'] = 4
        elif skew_z > 1.0: scores['s10'] = 3
        elif skew_z > -1.0: scores['s10'] = 2
        else: scores['s10'] = 1
        
        return scores, metrics
    
    def run(self) -> List[ScoreResult]:
        """執行完整評分流程"""
        results = []
        
        # VIX
        self.fetch_vix()
        
        for ticker in self.tickers:
            try:
                stock = self.fetch_stock_data(ticker)
                option = self.fetch_option_data(stock)
                scores, metrics = self.calculate_scores(stock, option)
                
                raw_total = sum(scores.values())
                adj_total = raw_total * 0.8 if scores['s3'] < 10 else raw_total
                
                if adj_total >= 80: grade = 'A'
                elif adj_total >= 65: grade = 'B'
                elif adj_total >= 50: grade = 'C'
                else: grade = 'D'
                
                # 🚫 禁止新規：僅在「財報在未來 7 天內」時才禁止（已過財報不算）
                days_to_earnings = metrics.get('days_to_earnings', 999)
                is_forbidden = 0 <= days_to_earnings <= 7

                # P0修正③：生成完整警告（共9項）
                warnings = []
                dist_low = metrics.get('dist_low', 100)
                iv_hv_ratio = metrics.get('iv_hv_ratio', 1.0)
                hv = stock.hv
                iv = option.iv

                # ① 近52W低點
                if dist_low < 15:
                    warnings.append(f"⚠️ 近52W低點（距低點{dist_low:.1f}%)")

                # ② 過熱 RSI>70
                if stock.rsi > 70:
                    warnings.append(f"⚠️ 過熱 RSI={stock.rsi:.0f}")

                # ④ IV/HV 異常：同時檢查被高估(>1.5)與被低估(<0.2)，用 elif 鏈避免重複
                if iv_hv_ratio > 1.5:
                    warnings.append(f"⚠️ IV被高估 IV/HV={iv_hv_ratio:.2f}")
                elif iv_hv_ratio < 0.2 and hv > 30:
                    warnings.append(f"⚠️ IV低估 IV/HV={iv_hv_ratio:.2f}")

                # ⑤ IV異常（IV/HV<0.1，IV低估的子集）
                if iv_hv_ratio < 0.1:
                    warnings.append(f"⚠️ IV異常 IV/HV={iv_hv_ratio:.2f}")

                # ⑦ 數據不穩（tier=t3）
                if option.tier == 't3':
                    warnings.append(f"⚠️ 數據不穩tier=t3")

                # ⑦' IV數據可疑（t2 + IV<10%）
                if option.tier == 't2' and iv < 10:
                    warnings.append(f"⚠️ IV數據可疑 IV={iv:.1f}%(t2)")

                # ⑧ 高IV低流動（IV>80% 且市值<$100B）
                if iv > 80 and stock.mkt_cap < 100e9:
                    warnings.append(f"⚠️ 高IV低流動 IV={iv:.0f}%")

                # ⑨ 基本面<10分
                s3_score = scores.get('s3', 0)
                if s3_score < 10:
                    warnings.append(f"⚠️ 基本面不足 s3={s3_score}")

                # ⑩ Put到期涵蓋財報（到期日在財報後 7 天內，且財報尚未發生）
                if option.exp and stock.earnings_date:
                    exp_date = datetime.strptime(option.exp, '%Y-%m-%d')
                    if exp_date > stock.earnings_date and (exp_date - stock.earnings_date).days < 7:
                        warnings.append(f"⚠️ Put到期間涵蓋財報（{stock.earnings_date.strftime('%m/%d')}）")

                # 計算建議履約價（距離現價 8% 的 OTM Put）
                suggested_strike = stock.price * 0.92  # 8% OTM
                
                results.append(ScoreResult(
                    ticker=ticker,
                    sector=stock.sector,
                    grade=grade,
                    adj_total=adj_total,
                    raw_total=raw_total,
                    scores=scores,
                    stock=stock,
                    option=option,
                    metrics=metrics,
                    is_forbidden=is_forbidden,
                    warnings=warnings,
                    suggested_strike=suggested_strike
                ))
            except Exception as e:
                print(f"Error processing {ticker}: {e}")

        # ── P1 新增：S5 板塊集中度懲罰 ──────────────────────────────
        from collections import Counter
        sector_counts = Counter(r.sector for r in results)
        max_count = max(sector_counts.values()) if sector_counts else 1
        for r in results:
            if sector_counts[r.sector] >= 3 and max_count >= 3:
                # 該板塊有 ≥3 檔 → s5 扣 2 分
                r.scores['s5'] = max(r.scores.get('s5', 0) - 2, 0)
                r.warnings.append(f"⚠️板塊集中({sector_counts[r.sector]}檔)S5-2")  # P1修正：放warnings欄（非s7），與文檔一致
                # 重新計算總分
                r.raw_total = sum(r.scores.values())
                r.adj_total = r.raw_total * 0.8 if r.scores.get('s3', 0) < 10 else r.raw_total
                # 重新評級
                if r.adj_total >= 80: r.grade = 'A'
                elif r.adj_total >= 65: r.grade = 'B'
                elif r.adj_total >= 50: r.grade = 'C'
                else: r.grade = 'D'

        results.sort(key=lambda x: x.adj_total, reverse=True)
        return results
