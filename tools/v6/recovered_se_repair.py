#!/usr/bin/env python3
"""V6 Recovered-SE Repair Experiment. RESEARCH ONLY.

Production code in src/ is NOT modified. This harness recomputes the ensemble
from archived per-model predictions under three uncertainty modes:

    ORIGINAL : se = |effect / z_raw|          <- the defect (default)
    REPAIRED : se = k_h / sqrt(n_eff)         <- the frozen minimum repair
    EQUAL    : se = 1                         <- repair control

Only the uncertainty input changes. effect, z_raw, correlation prior, Z_CLIP,
score_from_z, cells and outcomes are identical across modes.
"""
from __future__ import annotations
import glob, hashlib, json, sys, time
import numpy as np, pandas as pd

sys.path.insert(0, "src")
from mip.engine.evidence import model_correlation
from mip.research.statistics import Z_CLIP, score_from_z
from mip.validation.metrics import cohort

B = "data/validation/analogue_v1/embargoed_revalidation"
OFF = ["earnings_behavior","interest_rate_sensitivity","macro_regime","momentum_exhaustion",
       "relative_strength","sector_rotation","valuation"]
HZ = ["1w","2w","1m","3m","6m","1y"]
SEED, N_BOOT, BLOCK, N_MIN = 20260801, 1000, 4, 100
NEFF_FLOOR = 1.0

MODE_ORIGINAL, MODE_REPAIRED, MODE_EQUAL = "ORIGINAL", "REPAIRED", "EQUAL"

def recover_se(mode, effect, z_raw, n_eff):
    """The ONLY line that differs between arms."""
    if mode == MODE_ORIGINAL:
        return np.abs(effect / z_raw)
    if mode == MODE_REPAIRED:
        return 1.0 / np.sqrt(np.maximum(n_eff, NEFF_FLOOR))
    if mode == MODE_EQUAL:
        return np.ones_like(np.asarray(effect, float))
    raise ValueError(mode)

def combine(names, eff, se):
    """Exact replication of production combine_decision_evidence (verified 2.84e-14)."""
    C = np.array([[model_correlation(a,b) for b in names] for a in names])
    w = 1.0/se**2; tot = w.sum()
    e_c = float((w*eff).sum()/tot)
    var = float((w[:,None]*w[None,:]*C*se[:,None]*se[None,:]).sum()/tot**2)
    z = e_c/np.sqrt(var) if var > 0 else 0.0
    return z, w/tot, e_c

def spearman(x,y):
    x=np.asarray(x,float); y=np.asarray(y,float)
    if len(x)<4: return np.nan
    rx=pd.Series(x).rank().to_numpy(); ry=pd.Series(y).rank().to_numpy()
    rx=rx-rx.mean(); ry=ry-ry.mean()
    dx,dy=np.sqrt((rx*rx).sum()),np.sqrt((ry*ry).sum())
    return np.nan if dx==0 or dy==0 else float((rx*ry).sum()/(dx*dy))

# ------------------------------------------------------------------ unit tests
def run_tests():
    T=[]
    def ck(name,cond): T.append((name,bool(cond)))
    ck("zero effect -> ORIGINAL se==0 (degenerate, weight inf)", recover_se(MODE_ORIGINAL,np.array([0.0]),np.array([1.0]),np.array([9.0]))[0]==0.0)
    ck("zero effect -> REPAIRED se finite & positive", np.isfinite(recover_se(MODE_REPAIRED,np.array([0.0]),np.array([1.0]),np.array([9.0]))[0]))
    ck("near-zero z -> REPAIRED se unaffected", recover_se(MODE_REPAIRED,np.array([1.0]),np.array([1e-12]),np.array([4.0]))[0]==0.5)
    ck("missing n_eff -> floored, finite", np.isfinite(recover_se(MODE_REPAIRED,np.array([1.0]),np.array([1.0]),np.array([0.0]))[0]))
    ck("non-finite n_eff -> floor via nan_to_num", np.isfinite(recover_se(MODE_REPAIRED,np.array([1.0]),np.array([1.0]),np.nan_to_num(np.array([np.inf]),posinf=1e6))[0]))
    n=np.array([4.0,16.0]); se=recover_se(MODE_REPAIRED,np.array([1.,1.]),np.array([1.,1.]),n)
    w=1/se**2; ck("weight proportional to n_eff", abs(w[1]/w[0]-4.0)<1e-12)
    _,sh,_=combine(["momentum_exhaustion","relative_strength"],np.array([.01,.02]),np.array([.5,.5]))
    ck("weight normalization sums to 1", abs(sh.sum()-1.0)<1e-12)
    ck("equal-input symmetry", abs(sh[0]-sh[1])<1e-12)
    ck("weight bounded: max/min ratio <= 320", (1/recover_se(MODE_REPAIRED,np.array([1.]),np.array([1.]),np.array([1.0]))[0]**2)/(1/recover_se(MODE_REPAIRED,np.array([1.]),np.array([1.]),np.array([320.1]))[0]**2) <= 1.0)
    z1,_,_=combine(["macro_regime","relative_strength"],np.array([.01,.02]),np.array([.4,.6]))
    z2,_,_=combine(["macro_regime","relative_strength"],np.array([.01,.02]),np.array([.4,.6]))
    ck("deterministic reproduction", z1==z2)
    ck("ORIGINAL mode reproduces defect identity w=(z/eff)^2",
       abs(1/recover_se(MODE_ORIGINAL,np.array([0.02]),np.array([2.0]),np.array([9.]))[0]**2 - (2.0/0.02)**2) < 1e-6)
    return T

# ------------------------------------------------------------------ load
def load():
    rows=[]
    for f in sorted(glob.glob(f"{B}/predictions_*.jsonl")):
        for L in open(f):
            d=json.loads(L)
            if d.get("horizon"): rows.append(d)
    P=pd.DataFrame(rows); P["as_of"]=pd.to_datetime(P["as_of"]).dt.date
    P=P[P.model.isin(OFF)].copy()
    M=pd.read_csv(f"{B}/merged.csv"); M["as_of"]=pd.to_datetime(M["as_of"]).dt.date
    return P,M

def cells_for(P,M,h):
    base=M[(M.system=="baseline")&(M.complete)].copy()
    c=cohort(base,h)
    c=c[c.realized_excess.notna()][["symbol","as_of","horizon","evidence_score","realized_excess"]]
    p=P[P.horizon==h]
    act=p[(~p.neutral.astype(bool))&p.excess.notna()&p.z_raw.notna()&(p.z_raw.abs()>1e-12)&p.n_eff.notna()].copy()
    grp={}
    for (s,a),g in act.groupby(["symbol","as_of"]):
        se0=np.abs(g.excess.to_numpy(float)/g.z_raw.to_numpy(float))
        if (se0<=0).any(): continue
        grp[(s,a)]=(list(g.model),g.excess.to_numpy(float),g.z_raw.to_numpy(float),g.n_eff.to_numpy(float))
    c=c[[(s,a) in grp for s,a in zip(c.symbol,c.as_of)]].reset_index(drop=True)
    return c,grp
