from typing import Dict, Any, List, Optional, Tuple
import math
import statistics
import numpy as np

def annualize_funding(eight_hour_rate: float) -> float:
    """Funding публикуется за 8ч. Переводим в годовые по геометрии."""
    # (1+r_8h)^(24/8 * 365) - 1
    periods = 3 * 365
    return (1.0 + eight_hour_rate) ** periods - 1.0

def annualize_basis(spot: float, futures: float, days_to_expiry: int) -> Optional[float]:
    if spot <= 0 or futures <= 0 or days_to_expiry <= 0:
        return None
    return (futures/spot - 1.0) * (365.0 / days_to_expiry)

def safe_float(x) -> Optional[float]:
    try:
        return float(x)
    except:
        return None

def inv_vol_weights(vols: Dict[str, float], max_weight: float = 0.35) -> Dict[str, float]:
    invs = {}
    for k,v in vols.items():
        if v is None or v <= 0:
            continue
        invs[k] = 1.0 / v
    if not invs:
        return {}
    total = sum(invs.values())
    w = {k: v/total for k,v in invs.items()}
    # cap
    # redistribute excess naively
    over = {k: max(0.0, wv - max_weight) for k,wv in w.items()}
    excess = sum(over.values())
    if excess > 0:
        # reduce proportionally others
        under_keys = [k for k in w.keys() if w[k] < max_weight]
        under_total = sum(w[k] for k in under_keys)
        for k in w.keys():
            if k in over and over[k] > 0:
                w[k] = max_weight
        if under_total > 0:
            scale = (under_total) / (under_total + excess)
            for k in under_keys:
                w[k] *= scale
    return w
