from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from .data import annualize_funding, annualize_basis, safe_float

@dataclass
class InstrumentMetrics:
    base: str
    spot_price: Optional[float]
    funding_8h: Optional[float]        # 8h funding (perp)
    funding_annualized: Optional[float]
    mark_price: Optional[float]
    basis_annualized: Optional[float]  # for quarterly, if available (best-effort)
    oi_usd: Optional[float]
    venue_symbol: Optional[str]
    venue: Optional[str]

@dataclass
class TradeIdea:
    base: str
    idea: str           # 'cash_and_carry', 'reverse_cnc', 'quarterly_basis', 'trend_hedge'
    rationale: str
    legs: List[Dict[str, Any]]  # each: {'venue': 'binance', 'side': 'buy/sell', 'asset': 'spot/perp/quarterly', 'symbol': 'BTCUSDT', 'size_usd': float}
    expected_yield_annualized: Optional[float]

def select_strategies(metrics: List[InstrumentMetrics],
                      funding_pos_thr: float = 0.20,
                      funding_neg_thr: float = -0.20,
                      basis_thr: float = 0.10) -> List[TradeIdea]:
    ideas: List[TradeIdea] = []
    for m in metrics:
        if m.spot_price is None:
            continue

        # Cash & Carry: L spot + S perp при положительном funding
        if m.funding_annualized is not None and m.funding_annualized >= funding_pos_thr and m.venue_symbol:
            ideas.append(TradeIdea(
                base=m.base,
                idea="cash_and_carry",
                rationale=f"Funding годовых ≈ {m.funding_annualized:.1%} ≥ {funding_pos_thr:.0%}. Захватываем funding, delta ~ 0.",
                legs=[
                    {"venue": m.venue, "side": "buy", "asset": "spot", "symbol": f"{m.base}/USDT", "size_usd": None},
                    {"venue": m.venue, "side": "sell", "asset": "perp", "symbol": m.venue_symbol, "size_usd": None},
                ],
                expected_yield_annualized=m.funding_annualized
            ))

        # Reverse CnC: S spot + L perp при отрицательном funding
        if m.funding_annualized is not None and m.funding_annualized <= funding_neg_thr and m.venue_symbol:
            ideas.append(TradeIdea(
                base=m.base,
                idea="reverse_cnc",
                rationale=f"Funding годовых ≈ {m.funding_annualized:.1%} ≤ {funding_neg_thr:.0%}. Играем реверсный funding.",
                legs=[
                    {"venue": m.venue, "side": "sell", "asset": "spot", "symbol": f"{m.base}/USDT", "size_usd": None},
                    {"venue": m.venue, "side": "buy", "asset": "perp", "symbol": m.venue_symbol, "size_usd": None},
                ],
                expected_yield_annualized=abs(m.funding_annualized)
            ))

        # Quarterly basis: L spot + S quarterly при высокой базе (если бы была)
        if m.basis_annualized is not None and m.basis_annualized >= basis_thr and m.venue_symbol:
            ideas.append(TradeIdea(
                base=m.base,
                idea="quarterly_basis",
                rationale=f"Годовая база квартального фьючерса ≈ {m.basis_annualized:.1%} ≥ {basis_thr:.0%}.",
                legs=[
                    {"venue": m.venue, "side": "buy", "asset": "spot", "symbol": f"{m.base}/USDT", "size_usd": None},
                    {"venue": m.venue, "side": "sell", "asset": "quarterly", "symbol": m.venue_symbol.replace('USDT','USDQ'), "size_usd": None},
                ],
                expected_yield_annualized=m.basis_annualized
            ))

        # Trend hedge (упрощённо): если funding около нуля (low-cost hedge) и есть 7d ап-тренд — но 7d ретёрн считаем вне этого файла
        # Сама фильтрация делается в main, тут каркас остаётся.
    return ideas

def size_legs(ideas: List[TradeIdea], weights: Dict[str, float], capital: float) -> List[TradeIdea]:
    """Заполняем size_usd пропорционально риск-весам (одинаковый USD на long и short ногу для дельта-нейтрали)."""
    out: List[TradeIdea] = []
    for idea in ideas:
        w = weights.get(idea.base, 0.0)
        alloc = capital * w
        for leg in idea.legs:
            leg["size_usd"] = round(alloc, 2)
        out.append(idea)
    return out
