from typing import Dict, Any, List, Optional
import math
import pandas as pd
import numpy as np
from .data import inv_vol_weights

def estimate_vols(prices: Dict[str, List[float]], lookback: int = 30) -> Dict[str, float]:
    vols = {}
    for base, series in prices.items():
        if not series or len(series) < max(lookback, 5):
            continue
        arr = np.array(series[-lookback:], dtype=float)
        rets = np.diff(np.log(arr))
        if len(rets) > 1:
            vols[base] = float(np.std(rets) * (252 ** 0.5))  # годовая вола
    return vols

def risk_parity_weights(vols: Dict[str, float], max_weight: float = 0.35) -> Dict[str, float]:
    return inv_vol_weights(vols, max_weight=max_weight)

def save_recommendations(df: pd.DataFrame, save_dir: str = "runs") -> str:
    import os, time
    os.makedirs(save_dir, exist_ok=True)
    path = f"{save_dir}/latest_recommendations.csv"
    df.to_csv(path, index=False)
    return path
