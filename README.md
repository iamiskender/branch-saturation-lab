# Branch Saturation Lab

An independent mechanism experiment on [The Standard Reserve](https://www.standardreserve.xyz/app/protocol/), built from whitepaper v0.1 while the protocol is pre-launch.

Not affiliated with the protocol. There is no token, no NFT, and no chain data to check any of this against yet.

## The question

The whitepaper calls the expansion license auction the protocol's largest supply sink. This asks three things about it that the paper does not answer:

1. Where does the $STANDARD that pays for a license come from?
2. How long does the sink run?
3. Does it matter which day you buy?

## Findings

**1. No charter can buy its second branch with what it earns.**

Every one of the 1,000 Founding Charters opens with exactly one branch (s7). Tokens mint only at a withdrawal (s3), so every wallet is empty at genesis. Retiring one branch out of one liquidates the whole balance and burns the charter (s9). Both internal funding routes are closed. The second branch must be paid for with $STANDARD bought on the open market.

This is arithmetic, not simulation. What simulation adds is the size: across 900 runs the resting branch count tracks `1,000 + 9,000 × participation`, maximum deviation 2.3%. The deviation never comes from a charter escaping one branch, only from charters already holding two or more.

**2. The burn engine has a computable expiry date.**

9,000 expandable slots against 100 licenses a day is a 90 day ceiling. Burn peaks near 3.35× daily issuance in the first week, then decays as each new branch dilutes the yield that sets the license floor. It reaches exactly zero at saturation in 900 runs out of 900. Total burned over the whole expansion phase: about 72 days' worth of issuance.

Saturation is linear in participation: 11 days at 10%, 23 at 25%, 47 at 50%, 90 at 100%. Charter auctions restart the engine faintly, near a tenth of daily issuance at 25 charters/day, against a peak above three times.

**3. Entry timing changes the cost of an identical branch by two orders of magnitude.**

Section 8 lets each day open at 2× the previous close, and describes the result as roughly 100× in a week. A license bought on day 3 to 5 takes over 200 days of branch yield to repay. The same license bought near saturation repays in 2. At full participation the spread runs from about 51× at a ten day buyer horizon to about 226× at sixty.

## Where the findings weaken

| Finding | Held | Weakened | Where |
|---|---|---|---|
| Bootstrap is closed | 900/900 | 225/900 | Deviation above 1% at participation of 50% and under, never above 2.3% |
| Burn reaches zero | 900/900 | 0/900 | No run kept a non-zero burn after saturation |
| Timing spread above 10× | 882/900 | 18/900 | All 18 in one corner: a ten day horizon at 10% participation |

## Why the redacted launch parameters do not matter

Whitepaper v0.1 redacts the base issuance rate, the policy multiplier, the epoch length, the resolution fee bounds and the whole of section 14.

The license floor is defined in s7 as about two days of one branch's yield, and one branch's yield is daily issuance divided by branch count `N`. Both sides carry the same `base × m` term, so it cancels:

```
daily license burn / daily issuance  =  100 × k × 2 × (base·m/N) / (base·m)  =  200k / N
```

where `k` is how far above the floor the auction clears. Findings 1 and 2 are stated entirely in that ratio. No redacted value enters them. Finding 3's magnitude does depend on assumed buyer behaviour; its existence does not.

## Assumptions

All in `DEFAULTS` in `model.py`, all swept.

- Resolution fee floor 5%, ceiling 50%, saturating at 20% weekly exit pressure. Ceiling swept 30% to 70% with no change to any finding.
- Buyer willingness to pay is a payback horizon drawn from a normal distribution. Mean swept 10 to 60 days, standard deviation swept 5 to 25.
- The continuous Dutch descent is approximated by uniform clearing at the price where cumulative demand meets daily supply. The real auction is continuous and first come first served.

## Not modelled

- Any price for $STANDARD. Everything is in tokens and days of yield.
- The contraction vault, net flow regimes, and the policy multiplier. Findings 1 and 2 are invariant to the multiplier by construction; finding 3 would move with it.
- Secondary charter transfers (s12, left for later by the protocol).
- Dormancy revocation (s10), which returns branches to the living and would slightly extend saturation.

## Reproduce

```bash
python3 model.py     # baseline trace
python3 sweep.py     # the 900 run sweep, writes sweep.csv
```

`index.html` is a self-contained port of the same model to JavaScript. It runs client side with no build step and no dependencies. Its day-by-day output matches `model.py` to within the difference in random draws (total burn 71.2 in Python, 71.5 in JS).

## Deploy

Any static host. For Vercel, the repo root works as-is with no configuration.

## Licence

MIT. Take the model, change the assumptions, and show me where it breaks.
