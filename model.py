"""
Branch Saturation Lab -- core model.

Units: daily issuance (base * m) is normalised to 1.0 token/day.
Every output is a RATIO, so the redacted launch parameters (base rate,
multiplier, epoch length) cancel out and never enter the result.

y(t) = one branch's daily yield = 1 / N(t)
license floor = 2 * y(t)   [whitepaper s7: "about two days of one branch's yield"]
"""

import numpy as np

# ---------------------------------------------------------------- assumptions
# Values redacted in whitepaper v0.1 are flagged ASSUMPTION and swept later.
DEFAULTS = dict(
    charters0        = 1000,   # whitepaper: 1,000 Founding Charters
    branches_max     = 10,     # whitepaper: 10 branches per charter
    licenses_per_day = 100,    # whitepaper: initially 100/day
    per_charter_cap  = 3,      # whitepaper: max 3 licenses per charter per day
    open_multiple    = 2.0,    # whitepaper: license auction opens at 2x last close
    floor_days       = 2.0,    # whitepaper: floor ~= 2 days of one branch's yield

    # --- ASSUMPTIONS (redacted in whitepaper) ---
    fee_floor        = 0.05,   # ASSUMPTION resolution fee floor
    fee_ceiling      = 0.50,   # ASSUMPTION resolution fee ceiling
    fee_saturation   = 0.20,   # ASSUMPTION exit pressure at which fee saturates

    # --- BEHAVIOURAL PARAMETERS (swept) ---
    horizon_mean     = 30.0,   # mean payback horizon in days -> willingness to pay
    horizon_sd       = 12.0,
    external_share   = 0.0,    # fraction of charters that can fund from the pool
    external_cap     = 3,      # licenses/day such a charter can fund externally
    charters_per_day = 0,      # charter auction cadence (starts at 0, policy-set)
    days             = 400,
    seed             = 7,
)


def resolution_fee(w7, held, p):
    """Quadratic congestion fee on the exit door (whitepaper s9)."""
    denom = max(held + w7, 1e-12)
    pressure = w7 / denom
    x = min(1.0, pressure / p["fee_saturation"])
    return p["fee_floor"] + (p["fee_ceiling"] - p["fee_floor"]) * x * x


def run(**kw):
    p = dict(DEFAULTS); p.update(kw)
    rng = np.random.default_rng(p["seed"])

    C = p["charters0"]
    cap_total = C * p["branches_max"]

    j = np.ones(C, dtype=np.int64)          # branches per charter
    B = np.zeros(C)                         # ledger balance (unminted)
    wallet = np.zeros(C)                    # realised tokens

    # payback horizon -> a charter pays at most horizon * y for a license
    H = np.clip(rng.normal(p["horizon_mean"], p["horizon_sd"], C), 2.0, None)
    is_ext = rng.random(C) < p["external_share"]

    p_last = None
    w_hist = []
    out = []

    for day in range(p["days"]):
        N = j.sum()
        y = 1.0 / N                          # one branch's daily yield
        floor = p["floor_days"] * y

        # 1. issuance accrues pro rata to the ledger
        B += j * y

        # 2. exit pressure and current resolution fee
        w7 = sum(w_hist[-7:])
        fee = resolution_fee(w7, B.sum(), p)

        # 3. license auction -- uniform clearing approximation of the Dutch descent
        p_start = p["open_multiple"] * (p_last if p_last else floor)
        val = H * y                          # willingness to pay
        room = np.minimum(p["branches_max"] - j, p["per_charter_cap"])
        eligible = room > 0

        def demand_at(price):
            """How many licenses clear at this price, given funding routes."""
            want = eligible & (val >= price)
            if not want.any():
                return 0.0, None
            # funding route A: cash already in wallet
            afford = np.floor(wallet / price)
            # funding route B: external purchase from the pool
            afford = np.where(is_ext, np.minimum(afford + p["external_cap"], 99), afford)
            # funding route C: retire one branch, spend the proceeds
            # proceeds = B/j (pro rata rule), net of the resolution fee
            can_retire = want & (j >= 2)
            proceeds = np.where(can_retire, (B / np.maximum(j, 1)) * (1 - fee), 0.0)
            gained = np.floor(proceeds / price)
            # only retire if it is net branch-positive
            worth_it = gained >= 2
            afford = np.where(can_retire & worth_it, np.maximum(afford, gained), afford)
            take = np.where(want, np.minimum(room, afford), 0)
            return take.sum(), take

        # bisect for the highest price that still clears the daily supply
        lo, hi = floor, max(p_start, floor * 1.000001)
        if demand_at(hi)[0] >= p["licenses_per_day"]:
            clear = hi
        elif demand_at(lo)[0] <= p["licenses_per_day"]:
            clear = lo
        else:
            for _ in range(48):
                mid = 0.5 * (lo + hi)
                if demand_at(mid)[0] >= p["licenses_per_day"]:
                    lo = mid
                else:
                    hi = mid
            clear = lo

        sold_total, take = demand_at(clear)
        if take is None:
            take = np.zeros(C, dtype=np.int64)

        # ration down to the daily supply, highest willingness first
        take = take.astype(np.int64)
        if take.sum() > p["licenses_per_day"]:
            order = np.argsort(-val)
            budget = p["licenses_per_day"]
            new = np.zeros_like(take)
            for i in order:
                if budget <= 0:
                    break
                g = min(take[i], budget)
                new[i] = g
                budget -= g
            take = new

        # 4. settle purchases
        burned_today = 0.0
        minted_today = 0.0
        retired_today = 0
        redistribute = 0.0
        for i in np.nonzero(take)[0]:
            cost = take[i] * clear
            # external buyers source the shortfall from the pool and never retire
            if wallet[i] < cost and not is_ext[i] and j[i] >= 2:
                gross = B[i] / j[i]
                net = gross * (1 - fee)
                B[i] -= gross
                j[i] -= 1
                wallet[i] += net
                minted_today += net
                burned_today += 0.5 * (gross - net)   # half the fee burns
                redistribute += 0.5 * (gross - net)   # half pays those who stayed
                retired_today += 1
            if wallet[i] >= cost:
                wallet[i] -= cost
            elif is_ext[i]:
                pass                              # bought the shortfall from the pool
            else:
                take[i] = 0
                continue
            j[i] += take[i]
            burned_today += cost                  # 100% of license spend burns

        # the redistributed half of every resolution fee accrues to remaining branches
        if redistribute > 0 and j.sum() > 0:
            B += redistribute * (j / j.sum())

        j = np.minimum(j, p["branches_max"])
        w_hist.append(minted_today)

        # 5. charter auction expands the ceiling
        if p["charters_per_day"] > 0:
            add = p["charters_per_day"]
            j = np.concatenate([j, np.ones(add, dtype=np.int64)])
            B = np.concatenate([B, np.zeros(add)])
            wallet = np.concatenate([wallet, np.zeros(add)])
            H = np.concatenate([H, np.clip(rng.normal(p["horizon_mean"], p["horizon_sd"], add), 2.0, None)])
            is_ext = np.concatenate([is_ext, rng.random(add) < p["external_share"]])
            C += add
            cap_total = C * p["branches_max"]

        p_last = clear if take.sum() > 0 else p_last
        out.append(dict(
            day=day, N=int(j.sum()), cap=int(cap_total),
            fill=j.sum() / cap_total,
            clear=clear, k=clear / floor,
            licenses_sold=int(take.sum()),
            retirements=retired_today,
            burn_ratio=burned_today,          # daily issuance is normalised to 1.0
            mint_ratio=minted_today,
            fee=fee,
        ))

    return out


if __name__ == "__main__":
    import json
    r = run()
    for d in (0, 1, 5, 10, 30, 60, 90, 150, 250, 399):
        row = r[d]
        print(f"day {row['day']:>3}  N={row['N']:>5}  fill={row['fill']:.1%}  "
              f"k={row['k']:>7.2f}  sold={row['licenses_sold']:>3}  "
              f"retire={row['retirements']:>3}  burn/iss={row['burn_ratio']:.3f}")
