"""Robustness sweep. Reports where each finding holds and where it vanishes."""
import itertools, json
import numpy as np
from model import run

HORIZON  = [10, 20, 30, 45, 60]
SD       = [5, 12, 25]
EXTERNAL = [0.10, 0.25, 0.50, 1.00]
FEE_CEIL = [0.30, 0.50, 0.70]
SEEDS    = [1, 2, 3, 4, 5]

rows = []
for hm, sd, ext, fc, sd_seed in itertools.product(HORIZON, SD, EXTERNAL, FEE_CEIL, SEEDS):
    r = run(days=200, horizon_mean=hm, horizon_sd=sd, external_share=ext,
            fee_ceiling=fc, seed=sd_seed)
    N = [x["N"] for x in r]
    ks = [x["k"] for x in r]
    sold = [x["licenses_sold"] for x in r]

    # --- finding 1: does any charter reach branch 2 without external funding?
    #     measured as final N vs the linear prediction 1000 + 9000*ext
    predicted = 1000 + 9000 * ext
    f1_gap = (N[-1] - predicted) / 9000.0

    # --- finding 2: does the burn engine terminate?
    burn = [x["burn_ratio"] for x in r]
    last_active = max([i for i, s in enumerate(sold) if s > 0], default=0)
    peak_burn = max(burn)
    tail_burn = float(np.mean(burn[-30:]))
    f2_decay = peak_burn / max(tail_burn, 1e-9)

    # --- finding 3: payback spread between worst and best entry day
    # past saturation the branch count is at rest, so the tail is exact rather
    # than censored by the simulation horizon. Same rule as the JS port.
    N_end = N[-1]
    def payback(d):
        price, acc = r[d]["clear"], 0.0
        for t in range(d, len(N)):
            acc += 1.0 / N[t]
            if acc >= price:
                return t - d
        return (len(N) - d) + int(np.ceil((price - acc) * N_end))
    active_days = [i for i, s in enumerate(sold) if s > 0]
    pbs = [payback(d) for d in active_days] or [0]
    f3_spread = max(pbs) / max(min(pbs), 1)

    rows.append(dict(horizon_mean=hm, horizon_sd=sd, external=ext, fee_ceiling=fc,
                     seed=sd_seed, N_final=N[-1], predicted=predicted, f1_gap=f1_gap,
                     sat_day=last_active, peak_burn=peak_burn, tail_burn=tail_burn,
                     f2_decay=f2_decay, worst_pb=max(pbs), best_pb=min(pbs),
                     f3_spread=f3_spread, peak_k=max(ks)))

import pandas as pd
df = pd.DataFrame(rows)
df.to_csv("sweep.csv", index=False)
print(f"runs: {len(df)}\n")

print("FINDING 1 -- no charter bootstraps past 1 branch on earned yield alone")
print("  |final N - (1000 + 9000*ext)| as a fraction of the 9000 expandable slots")
print(f"  max deviation across all runs: {df.f1_gap.abs().max():.4f}")
print(f"  runs where deviation > 1%:     {(df.f1_gap.abs() > 0.01).sum()} / {len(df)}\n")

print("FINDING 2 -- the burn engine decays and terminates")
print(f"  peak burn / tail burn, median:  {df.f2_decay.median():.1f}x")
print(f"  runs with decay > 10x:          {(df.f2_decay > 10).sum()} / {len(df)}")
print(f"  runs with decay < 2x (no decay):{(df.f2_decay < 2).sum()} / {len(df)}")
print(f"  saturation day, median:         {df.sat_day.median():.0f}\n")

print("FINDING 3 -- entry timing changes the payback period")
print(f"  worst/best payback ratio, median: {df.f3_spread.median():.1f}x")
print(f"  runs with spread > 10x:           {(df.f3_spread > 10).sum()} / {len(df)}")
print(f"  runs with spread > 3x:            {(df.f3_spread > 3).sum()} / {len(df)}")
print(f"  runs with spread < 2x (no effect):{(df.f3_spread < 2).sum()} / {len(df)}\n")

print("where finding 3 weakens (spread < 3x), by horizon_mean:")
print(df.assign(weak=df.f3_spread < 3).groupby("horizon_mean").weak.agg(["sum", "count"]))
