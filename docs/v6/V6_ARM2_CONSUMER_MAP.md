# V6 Arm 2 — Consumer / Non-Consumer Map (R4)

**Feature:** `ret_21d`

## 1. Model population

`ALL_MODELS` contains 9 models. `src/mip/engine/evidence.py:71`:

```python
SHADOW_MODELS = frozenset({"historical_analogues", "conditional_probability"})
```

Shadow models are excluded from the combined evidence score. The scored ensemble is **7 models**, matching the `OFF` list used by Arm 1 and Arm 1.5.

## 2. Partition as produced by the frozen rule

| Set | Members | n |
|---|---|---|
| **CONSUMERS** | `earnings_behavior`, `macro_regime`, `momentum_exhaustion`, `relative_strength`, `sector_rotation`, `valuation` | **6** |
| **NON-CONSUMERS** | `interest_rate_sensitivity` | **1** |

## 3. Exhaustiveness and mutual exclusivity — PROVEN

- Union = 7 = |official model set| → **exhaustive**
- Intersection = ∅ → **mutually exclusive**

The named stop condition — *"if the partition cannot be proven exhaustive and mutually exclusive, stop"* — is **satisfied**. It is not what blocks this experiment. Two different defects do.

## 4. Verification of the single control model

`interest_rate_sensitivity` builds feature names **dynamically** (`src/mip/models/rates.py:160`, `template.format(window=window)`), so a string scan could have missed a dependency. Resolved at runtime:

```
SERIES  = {"2Y": "dgs2_chg_{window}d", "10Y": "dgs10_chg_{window}d"}
WINDOWS = (5, 21, 63, 126)
→ dgs2_chg_{5,21,63,126}d, dgs10_chg_{5,21,63,126}d
→ 'ret_21d' in names == False
```

It is a genuine non-consumer. It is also **the only one**, and it was silent until the macro ingest restored `dgs2_*`/`dgs10_*` (previously 0 non-null values).

## 5. B-02 — the control arm is degenerate

The frozen rule maximises consumer count. Over a fixed 7-model population, **maximising the treatment arm is identically minimising the control arm.** The rule that picks the feature is therefore the rule that guarantees the weakest possible specificity control. `ret_21d` attains the extreme: control n = 1.

Consequences:
- The preregistered **pooling rule is inoperative** — there is nothing to pool.
- No between-model variance is estimable in the control arm; the leakage CI is driven entirely by within-model bootstrap noise.
- A single spurious result in one model is indistinguishable from systematic leakage.

## 6. Static classification vs. measured behaviour

Measured on 90 cells at horizon 1m, ρ = 0.30 (three times the primary ρ):

| Model | Frozen class | Cells changed by injection | Verdict |
|---|---|---|---|
| `momentum_exhaustion` | CONSUMER | **13 / 90** | true consumer |
| `earnings_behavior` | CONSUMER | 0 / 90 | **not a consumer** |
| `macro_regime` | CONSUMER | 0 / 90 | **not a consumer** |
| `relative_strength` | CONSUMER | 0 / 90 | **not a consumer** |
| `sector_rotation` | CONSUMER | 0 / 90 | **not a consumer** |
| `valuation` | CONSUMER | 0 / 90 | **not a consumer** |
| `interest_rate_sensitivity` | NON-CONSUMER | 0 / 90 | correctly classified |

**The frozen partition is empirically false: 5 of 6 "consumers" are byte-identical under injection.**

The measured partition is:

| Set | Members | n |
|---|---|---|
| TRUE CONSUMERS | `momentum_exhaustion` | **1** |
| TRUE NON-CONSUMERS | the other 6 | **6** |

Of those 6, three (`valuation`, `earnings_behavior`, `sector_rotation`) emit constant output and have undefined IC (B-04), leaving **3 usable controls**.

Arm 2 was designed to measure transmission from a feature into many models against a control of few. The restored reality is the exact inverse: **one treated model, three usable controls.**
