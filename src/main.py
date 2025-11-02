import argparse
import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

from .exchanges import cg_top_coins, binance_perp_exchange_info, binance_perp_premium_index, binance_open_interest, bybit_perp_instruments, bybit_funding, bybit_mark_price, okx_perp_instruments, okx_ticker, okx_funding_rate, guess_usdt_perp_symbol
from .data import annualize_funding
from .strategy import InstrumentMetrics, select_strategies, size_legs
from .portfolio import estimate_vols, risk_parity_weights, save_recommendations

def try_fetch_perp(base: str):
    candidates = guess_usdt_perp_symbol(base)
    # Priority: Binance -> Bybit -> OKX
    for venue, sym in candidates:
        if venue == "binance":
            data = binance_perp_premium_index(sym)
            if data and "markPrice" in data:
                funding_8h = float(data.get("lastFundingRate", 0.0))
                return dict(venue="binance", symbol=sym, mark=float(data["markPrice"]), funding_8h=funding_8h, oi=binance_open_interest(sym))
        elif venue == "bybit":
            mp = bybit_mark_price(sym)
            fr = bybit_funding(sym)
            if mp is not None and fr is not None:
                return dict(venue="bybit", symbol=sym, mark=float(mp), funding_8h=float(fr), oi=None)
        elif venue == "okx":
            tk = okx_ticker(sym)
            fr = okx_funding_rate(sym)
            if tk and fr is not None:
                mark = float(tk.get("last", tk.get("askPx", 0.0)))
                return dict(venue="okx", symbol=sym, mark=mark, funding_8h=float(fr), oi=None)
    return None

def build_metrics(top: List[Dict[str, Any]]) -> List[InstrumentMetrics]:
    rows: List[InstrumentMetrics] = []
    for c in top:
        base = c.get("symbol","").upper()
        spot_price = c.get("current_price")
        perp = try_fetch_perp(c.get("symbol","").upper())
        funding_ann = None
        mark_price = None
        venue_symbol = None
        venue = None
        oi = None
        if perp:
            mark_price = perp["mark"]
            venue_symbol = perp["symbol"]
            venue = perp["venue"]
            if perp["funding_8h"] is not None:
                funding_ann = annualize_funding(perp["funding_8h"])
            oi = perp["oi"]
        rows.append(InstrumentMetrics(
            base=base,
            spot_price=spot_price,
            funding_8h=perp["funding_8h"] if perp else None,
            funding_annualized=funding_ann,
            mark_price=mark_price,
            basis_annualized=None,  # опционально: добавить квартальные
            oi_usd=oi,
            venue_symbol=venue_symbol,
            venue=venue
        ))
    return rows

def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--capital", type=float, default=10000.0)
    ap.add_argument("--n_coins", type=int, default=50)
    ap.add_argument("--funding_pos_thr", type=float, default=0.20)
    ap.add_argument("--funding_neg_thr", type=float, default=-0.20)
    ap.add_argument("--basis_thr", type=float, default=0.10)
    ap.add_argument("--max_weight", type=float, default=0.35)
    ap.add_argument("--vol_lookback", type=int, default=30)
    ap.add_argument("--trend_lookback", type=int, default=7)
    args = ap.parse_args()

    # 1) Top coins with spot
    top = cg_top_coins(args.n_coins)

    # 2) Build perp metrics
    metrics = build_metrics(top)

    # 3) Naive price history (for vol) — в этой версии опущено (можно расширить историей CoinGecko /coins/{id}/market_chart)
    # Для демонстрации назначим одинаковую волу = 0.8 на всех, чтобы показать risk parity механику
    vols = {m.base: 0.8 for m in metrics if m.spot_price}

    # 4) Отбор стратегий
    ideas = select_strategies(metrics, funding_pos_thr=args.funding_pos_thr, funding_neg_thr=args.funding_neg_thr, basis_thr=args.basis_thr)

    # 5) Риск‑паритетные веса
    weights = risk_parity_weights(vols, max_weight=args.max_weight)

    # 6) Размеры ног
    ideas = size_legs(ideas, weights, capital=args.capital)

    # 7) Вывод
    rows = []
    for idea in ideas:
        for leg in idea.legs:
            rows.append({
                "base": idea.base,
                "strategy": idea.idea,
                "venue": leg["venue"],
                "asset": leg["asset"],
                "side": leg["side"],
                "symbol": leg["symbol"],
                "size_usd": leg["size_usd"],
                "expected_yield_annualized": idea.expected_yield_annualized
            })
    df = pd.DataFrame(rows).sort_values(["strategy","base","asset"])
    if df.empty:
        print("Не найдено стратегий по текущим порогам. Попробуйте снизить пороги funding/basis или увеличить список монет.")
        return
    save_path = save_recommendations(df, save_dir="runs")
    print(df.to_string(index=False))
    print(f"\nСохранено в: {save_path}")

if __name__ == "__main__":
    main()
