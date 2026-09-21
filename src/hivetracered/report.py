# Fix the f-string issue by building the attribute string separately and re-writing the file.

import os, json, argparse, hashlib, math, re
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from hivetracered.statistics import error_mask, boolean_values, _mapping, _present, _evaluation_failed
from hivetracered.pipeline.framework_mapping import (
    FRAMEWORKS,
    get_framework_mappings,
)
from hivetracered.pipeline.mitigations import get_prioritized_mitigations

SUCCESS_RATE = "Success Rate"
ATTACK_TYPE = "Attack Type"
TOTAL_TESTS = "Total Tests"
BLOCK_RATE = "Block Rate"

def get_chart_style():
    return {
        "paper_bgcolor": "#161a23",
        "plot_bgcolor": "#161a23",
        "font": dict(color="#e8e8e8"),
        "xaxis": dict(gridcolor="#2a2f3a", color="#e8e8e8"),
        "yaxis": dict(gridcolor="#2a2f3a", color="#e8e8e8")
    }

def _read_dataframe(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.parquet':
        return pd.read_parquet(file_path)
    if ext in ('.xlsx', '.xls'):
        return pd.read_excel(file_path)
    return pd.read_csv(file_path)


def _safe_get(d, key, default="unknown"):
    if isinstance(d, dict):
        return d.get(key, default)
    try:
        dd = json.loads(d)
    except Exception:
        return default
    if isinstance(dd, dict):
        return dd.get(key, default)
    return default


def _expand_evaluation(df):
    for key in ("is_harmful", "did_answer", "should_block"):
        df[key] = df["evaluation"].apply(lambda x, k=key: _safe_get(x, k))


def _betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b) (Numerical Recipes betacf, Lentz)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _betainc(b, a, 1.0 - x)
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((a + m2 - 1) * (a + m2)),
                   -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1.0) < 1e-12:
            break
    return front * h / a


def clopper_pearson_upper(successes, total, confidence=0.95):
    """One-sided Clopper-Pearson (exact binomial) upper bound on a proportion, in
    percent: the largest p at which observing <= ``successes`` of ``total`` still
    has probability >= 1 - confidence. Exact rather than Wilson: ASR often sits
    near 0, and a one-sided bound is the honest "at most this bad" figure.

    Statistical model with repeats: ``total`` is the number of distinct examples
    and ``successes`` the sum of per-example success fractions (mean over K and
    N), so it may be non-integer; the beta form handles that. Treating a fraction
    as if it were a single binary trial over-states its variance, so the bound is
    conservative; the alternative (n = K*N*examples raw trials) would ignore that
    repeats of one example are correlated and be anti-conservative."""
    if total <= 0:
        return 0.0
    if successes >= total:
        return 100.0
    # Upper bound = quantile(confidence) of Beta(x + 1, n - x); bisection on I_p.
    a, b = successes + 1, total - successes
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if _betainc(a, b, mid) < confidence:
            lo = mid
        else:
            hi = mid
    return hi * 100


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value from the discordant counts: b = baseline
    failed but attack succeeded, c = baseline succeeded but attack failed.
    Under H0 the discordant pairs split 50/50, so this is a two-sided binomial
    test on min(b, c) of b + c. Exact rather than chi-square: discordant counts
    are small at typical dataset sizes."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def bh_adjust(pvalues):
    """Benjamini-Hochberg adjusted p-values, in the original input order.

    Compare to the FDR level directly. FDR control assumes independent tests
    or positive regression dependency on the true null hypotheses.
    """
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted, running = [0.0] * m, 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        running = min(running, m * pvalues[i] / (rank + 1))
        adjusted[i] = running
    return adjusted


# Percentile bootstrap over examples. Used wherever an example's observation is
# a success *fraction* (K or N repeats collapsed) rather than a single 0/1 trial:
# the exact binomial bound assumes Bernoulli trials, so feeding it fractions is
# only conservative, and a plug-in estimator like the per-type risk below has no
# closed-form binomial bound at all.
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260909
# Bootstrap draws are rounded before being compared with zero: the per-example
# differences are multiples of 1/(K*N), so an exactly-zero mean can come back as
# -1e-17 and be miscounted as evidence against H0.
_ZERO_TOL = 12


def _bootstrap_means(values, n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED, batch=500):
    """Bootstrap distribution of the mean, resampling *examples* (whole rows),
    not individual repeats: repeats of one example are correlated, examples are
    the independent unit. Batched to keep the index matrix small on big runs.
    Deterministic: same input, same seed, same report."""
    v = np.asarray(values, dtype=float)
    n = v.size
    if n == 0:
        return np.zeros(0)
    rng = np.random.default_rng(seed)
    out = np.empty(n_resamples)
    for start in range(0, n_resamples, batch):
        size = min(batch, n_resamples - start)
        out[start:start + size] = v[rng.integers(0, n, size=(size, n))].mean(axis=1)
    return out


def bootstrap_upper(values, confidence=0.95, seed=BOOTSTRAP_SEED):
    """One-sided percentile bootstrap upper bound [0, U] on the mean, in percent."""
    draws = _bootstrap_means(values, seed=seed)
    if draws.size == 0:
        return 0.0
    return float(np.percentile(draws, 100 * confidence) * 100)


def bootstrap_lower_and_p(values, confidence=0.95, seed=BOOTSTRAP_SEED):
    """One-sided [L, 1] bound on the mean and the bootstrap p-value for
    H0: mean <= 0 against H1: mean > 0 (the attack raises ASR).

    Returns (L in percent, p). p is the share of bootstrap means at or below
    zero, so it is discrete with step 1/B: p = 0 means "no resample reached
    zero", not "p is exactly zero"; it is reported as < 1/B."""
    draws = _bootstrap_means(values, seed=seed)
    if draws.size == 0:
        return 0.0, 1.0
    low = float(np.percentile(draws, 100 * (1 - confidence)) * 100)
    p = float(np.mean(np.round(draws, _ZERO_TOL) <= 0))
    return low, p


def _is_binary(values):
    """True when every example is a plain 0/1 trial, i.e. K = N = 1 (or every
    repeat of every example agreed)."""
    v = np.asarray(values, dtype=float)
    return bool(v.size) and bool(np.all((v == 0) | (v == 1)))


def asr_upper(values, seed=BOOTSTRAP_SEED):
    """One-sided 95% upper bound on the mean of per-example success fractions,
    in percent, plus the name of the method used.

    Plain 0/1 observations get the exact binomial (Clopper-Pearson) bound.
    Fractions get the percentile bootstrap, except when every example carries
    the *same* fraction: the bootstrap is then degenerate (every resample has
    the same mean, so U = the estimate itself, and an all-zero attack would be
    reported as "at most 0%"). That case falls back to the conservative exact
    bound."""
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return 0.0, "Clopper-Pearson"
    if _is_binary(v) or float(np.ptp(v)) == 0.0:
        return clopper_pearson_upper(float(v.sum()), int(v.size)), "Clopper-Pearson"
    return bootstrap_upper(v, seed=seed), "bootstrap"


def _seed_for(name, offset=0):
    """Per-attack bootstrap seed, stable across runs and independent of the
    order attacks happen to appear in."""
    return (BOOTSTRAP_SEED + offset + int(hashlib.sha1(str(name).encode()).hexdigest()[:8], 16)) % (2 ** 32)


def _example_col(df):
    """Column that identifies an example. The pipeline's ``base_prompt_id`` when
    every row has one: two examples with the same text stay two observations.
    Older result files carry only the text."""
    if "base_prompt_id" in df.columns and df["base_prompt_id"].notna().all():
        return "base_prompt_id"
    return "base_prompt"


def _count_examples(df):
    """Number of distinct examples in ``df`` (per dataset, by example id)."""
    keys = [c for c in ("dataset", _example_col(df)) if c in df.columns]
    return int(len(df[keys].drop_duplicates())) if keys else 0


def _per_example_success(df, keys):
    """Success fraction per (keys) unit: mean over the K and N repeat rows."""
    return df.groupby(keys, sort=False, dropna=False)["success"].mean()


def _paired_fractions(df, baseline="NoneAttack"):
    """Examples x attacks table of per-example success fractions, or None when
    the frame cannot support a paired comparison. Rows are examples, so every
    column is aligned on the same example and the pairing is exact."""
    if not {"attack_name", "base_prompt", "success"}.issubset(df.columns):
        return None
    df = _answered(df)  # errored requests are not trials
    if baseline not in set(df["attack_name"]):
        return None
    keys = [c for c in ("dataset", _example_col(df)) if c in df.columns]
    return _per_example_success(df, keys + ["attack_name"]).unstack("attack_name")


def mcnemar_vs_baseline(df, baseline="NoneAttack", alpha=0.05):
    """Pair every attack with the baseline on the same example and test whether
    the attack changes the outcome (exact McNemar). One row per attack:
    n pairs, discordant counts b/c, ASR delta in pp, raw and BH-adjusted
    p-value; ``significant`` uses the adjusted one (one family = all attacks).

    Fractional success (mean over K) is binarised at > 0.5 per example, after
    averaging any N repeats: McNemar needs one verdict per (example, attack)."""
    fractions = _paired_fractions(df, baseline)
    if fractions is None:
        return pd.DataFrame()
    # Keep a missing observation missing: NaN > 0.5 is False, which would turn
    # an errored example into a failed attack and pair it anyway.
    verdict = (fractions > 0.5).where(fractions.notna())
    base = verdict[baseline]
    rows = []
    for name in verdict.columns:
        if name == baseline:
            continue
        both = verdict[name].notna() & base.notna()
        a, x = verdict.loc[both, name].astype(bool), base[both].astype(bool)
        b, c = int((a & ~x).sum()), int((~a & x).sum())
        p = mcnemar_exact(b, c)
        rows.append({
            "attack_name": name, "n pairs": int(both.sum()),
            "baseline ASR": float(x.mean() * 100) if both.any() else 0.0,
            "attack ASR": float(a.mean() * 100) if both.any() else 0.0,
            "Δ (pp)": float((a.mean() - x.mean()) * 100) if both.any() else 0.0,
            "b (0→1)": b, "c (1→0)": c, "p-value": p,
        })
    table = pd.DataFrame(rows)
    if not table.empty:
        table["p (BH)"] = bh_adjust(table["p-value"].tolist())
        table["significant"] = table["p (BH)"] < alpha
    return table


def paired_bootstrap_vs_baseline(df, baseline="NoneAttack", alpha=0.05):
    """Paired bootstrap of every attack against the baseline, for runs with
    repeats (K*N > 1). Per example, d = attack fraction - baseline fraction;
    resampling examples keeps the pairing, so d absorbs how hard the example is
    and only the attack's effect is left.

    One-sided by design: H0: E[d] <= 0 against H1: E[d] > 0 (the attack raises
    ASR). An attack that *lowers* ASR is therefore never flagged significant -
    that is the question being asked, not a bug. Columns: n pairs, both ASRs,
    Delta, its one-sided 95% lower bound, bootstrap p and its BH-adjusted
    twin.

    Preferred over McNemar here because McNemar needs one 0/1 verdict per
    example: with K repeats that means thresholding the fraction, which throws
    away the difference between 3/5 and 5/5."""
    fractions = _paired_fractions(df, baseline)
    if fractions is None:
        return pd.DataFrame()
    base = fractions[baseline]
    rows = []
    for name in fractions.columns:
        if name == baseline:
            continue
        both = fractions[name].notna() & base.notna()
        attack_p, base_p = fractions.loc[both, name].to_numpy(float), base[both].to_numpy(float)
        d = attack_p - base_p
        low, p = bootstrap_lower_and_p(d, seed=_seed_for(name))
        rows.append({
            "attack_name": name, "n pairs": int(both.sum()),
            "baseline ASR": float(base_p.mean() * 100) if d.size else 0.0,
            "attack ASR": float(attack_p.mean() * 100) if d.size else 0.0,
            "Δ (pp)": float(d.mean() * 100) if d.size else 0.0,
            "Δ 95% lower (pp)": low, "p-value": p,
        })
    table = pd.DataFrame(rows)
    if not table.empty:
        table["p (BH)"] = bh_adjust(table["p-value"].tolist())
        table["significant"] = table["p (BH)"] < alpha
    return table


def paired_test_vs_baseline(df, baseline="NoneAttack", alpha=0.05):
    """Compare every attack with the baseline and say which test was used.

    Plain 0/1 outcomes (K = N = 1) -> exact McNemar on the discordant pairs.
    Success fractions -> paired bootstrap, which uses the fractions as they are.
    Returns (table, method)."""
    fractions = _paired_fractions(df, baseline)
    if fractions is None:
        return pd.DataFrame(), "exact McNemar"
    values = fractions.to_numpy(float)
    if _is_binary(values[~np.isnan(values)]):
        return mcnemar_vs_baseline(df, baseline, alpha), "exact McNemar"
    return paired_bootstrap_vs_baseline(df, baseline, alpha), "paired bootstrap"


_MCNEMAR_NOTE = (
    "b = examples the attack broke that {baseline} did not; c = the reverse. "
    "Two-sided exact binomial test on the discordant pairs."
)
_BOOTSTRAP_NOTE = (
    "Δ = mean per-example difference in success fraction against {baseline}, "
    "with its one-sided 95% lower bound from {b:,} paired bootstrap resamples of "
    "the examples. One-sided: an attack that lowers ASR is never flagged."
)


def _fmt_p(v, floor):
    return f"<{floor:g}" if v < floor else f"{v:.{max(0, -math.floor(math.log10(floor)))}f}"


def _paired_test_html(df, baseline="NoneAttack"):
    """(html, title, note) for the attack-vs-baseline table."""
    table, method = paired_test_vs_baseline(df, baseline)
    bootstrap = method == "paired bootstrap"
    note = (_BOOTSTRAP_NOTE if bootstrap else _MCNEMAR_NOTE).format(
        baseline=baseline, b=BOOTSTRAP_RESAMPLES
    )
    title = f"Attack vs {baseline} ({method}, paired by example)"
    if table.empty:
        return "", title, note
    out = table.copy()
    out["Excluded examples"] = _count_examples(df) - out["n pairs"]
    out = out.rename(columns={"n pairs": "Paired examples"})
    for col in ("baseline ASR", "attack ASR"):
        out[col] = out[col].round(1).astype(str) + "%"
    for col in ("Δ (pp)", "Δ 95% lower (pp)"):
        if col in out.columns:
            out[col] = out[col].map("{:+.1f}".format)
    # McNemar p is exact, so 0.001 is a fair floor; the bootstrap p is a share
    # of B resamples and cannot resolve below 1/B.
    floor = 1 / BOOTSTRAP_RESAMPLES if bootstrap else 0.001
    for col in ("p-value", "p (BH)"):
        out[col] = out[col].map(lambda v: _fmt_p(v, floor))
    out["significant"] = out["significant"].map(lambda v: "✅ yes" if v else "— no")
    return out.to_html(index=False, classes="dataframe compact", border=0), title, note


def _example_success(df):
    """Per-example success fraction (mean over all K and N repeats), so that a
    repeated example is one observation, not K*N. Returns (successes, examples)."""
    keys = [c for c in ("dataset", "attack_name", _example_col(df)) if c in df.columns]
    per_example = df.groupby(keys, sort=False, dropna=False)["success"].mean()
    return float(per_example.sum()), int(len(per_example))


def _per_attack_asr(df):
    """ASR (%) and one-sided 95% Clopper-Pearson upper bound per attack, over
    distinct examples (mean of K/N repeats), not over repeat rows."""
    df = _answered(df)  # errored requests are not trials
    if not {"attack_name", "success"}.issubset(df.columns) or df.empty:
        return pd.DataFrame(
            columns=["attack_name", "successes", "examples", SUCCESS_RATE, "upper"]
        )
    if "base_prompt" in df.columns:
        keys = [c for c in ("dataset", _example_col(df)) if c in df.columns]
        per_example = _per_example_success(df, ["attack_name"] + keys)
    else:  # no example key: every row is its own observation
        per_example = df.set_index("attack_name")["success"]
    stats = per_example.groupby(level="attack_name", sort=False).agg(["sum", "count", "mean"])
    stats = stats.rename(
        columns={"sum": "successes", "count": "examples", "mean": SUCCESS_RATE}
    )
    stats[SUCCESS_RATE] = stats[SUCCESS_RATE] * 100
    bounds = {
        name: asr_upper(group.to_numpy(float), seed=_seed_for(name))
        for name, group in per_example.groupby(level="attack_name", sort=False)
    }
    stats["upper"] = [bounds[name][0] for name in stats.index]
    stats["upper method"] = [bounds[name][1] for name in stats.index]
    return stats.reset_index()


def asr_bound_method(df):
    """Which upper-bound method this frame gets: exact when every example is a
    plain 0/1 trial, bootstrap once repeats make the observations fractional."""
    if "success" not in df.columns or df.empty:
        return "Clopper-Pearson"
    return "Clopper-Pearson" if _is_binary(_answered(df)["success"].to_numpy(float)) else "bootstrap"


def _bound_caption(df):
    method = asr_bound_method(df)
    if method == "bootstrap":
        return (f"faint bar is the one-sided 95% upper bound "
                f"({BOOTSTRAP_RESAMPLES:,}-resample percentile bootstrap over examples)")
    return "faint bar is the one-sided 95% Clopper-Pearson upper bound"


def attack_type_risk(df):
    """Per attack type: the chance an example falls to at least one attack of
    that type, given **one attempt with each attack**.

    Plug-in estimator q_i = 1 - prod_a (1 - p[i,a]) over the attacks of the
    type, averaged over examples, with a one-sided 95% upper bound. Unlike the
    "share of prompts broken at least once" figure on the charts, this does not
    grow just because K or N was raised: it always prices a single attempt per
    attack.

    Assumes the attacks of a type succeed independently on a fixed example. They
    are run independently, but correlated failure modes (one hardened refusal
    that blocks the whole family) would make this an over-estimate."""
    need = {"attack_type", "attack_name", "base_prompt", "success"}
    if not need.issubset(df.columns) or df.empty:
        return pd.DataFrame()
    df = _answered(df)  # errored requests are not trials
    keys = [c for c in ("dataset", _example_col(df)) if c in df.columns]
    rows = []
    for attack_type, sub in df.groupby("attack_type", sort=False, dropna=False):
        fractions = _per_example_success(sub, keys + ["attack_name"]).unstack("attack_name")
        if fractions.empty:
            continue
        # prod() skips attacks that were not run on an example (factor 1).
        q = (1 - (1 - fractions).prod(axis=1)).to_numpy(float)
        upper, method = asr_upper(q, seed=_seed_for(attack_type, 7))
        rows.append({
            "attack_type": attack_type,
            "Attacks": int(fractions.shape[1]),
            "Examples": int(fractions.shape[0]),
            "One-attempt Risk": float(q.mean() * 100),
            "upper": upper,
            "upper method": method,
        })
    table = pd.DataFrame(rows)
    return table.sort_values("One-attempt Risk", ascending=False).reset_index(drop=True) if not table.empty else table


def _attack_type_risk_html(df):
    table = attack_type_risk(df)
    if table.empty:
        return ""
    out = table.drop(columns=["upper method"]).copy()
    out["One-attempt Risk"] = out["One-attempt Risk"].round(1).astype(str) + "%"
    out["95% Upper"] = table["upper"].map("≤{:.1f}%".format)
    out = out.drop(columns=["upper"])
    return out.to_html(index=False, classes="dataframe compact", border=0)


def _asr_upper_figure(stats, orientation="v"):
    """Solid ASR bar over a faint bar to the Clopper-Pearson upper bound."""
    names = stats["attack_name"].tolist()
    rates = stats[SUCCESS_RATE].tolist()
    uppers = stats["upper"].tolist()
    custom = np.column_stack([rates, uppers])
    hover = (
        "%{y}<br>ASR=%{customdata[0]:.1f}%<br>95% upper ≤%{customdata[1]:.1f}%<extra></extra>"
        if orientation == "h" else
        "%{x}<br>ASR=%{customdata[0]:.1f}%<br>95% upper ≤%{customdata[1]:.1f}%<extra></extra>"
    )
    bar = dict(customdata=custom, hovertemplate=hover, width=0.6)
    bg = dict(
        name="95% upper", marker=dict(color="rgba(99,110,250,0.28)", line=dict(width=0)),
        text=[f"≤{u:.1f}%" for u in uppers], textposition="outside",
        textfont=dict(color="#b0b8c3", size=11), cliponaxis=False, **bar,
    )
    fg = dict(
        name="ASR", marker=dict(color="#636efa", line=dict(width=0)),
        text=[f"{r:.1f}%" for r in rates], textposition="inside",
        insidetextanchor="middle", textfont=dict(color="#e8e8e8", size=12), **bar,
    )
    if orientation == "h":
        traces = [
            go.Bar(x=uppers, y=names, orientation="h", **bg),
            go.Bar(x=rates, y=names, orientation="h", **fg),
        ]
    else:
        traces = [
            go.Bar(x=names, y=uppers, **bg),
            go.Bar(x=names, y=rates, **fg),
        ]
    hi = max(uppers) if uppers else 0.0
    fig = go.Figure(traces)
    fig.update_layout(
        barmode="overlay", bargap=0.28, showlegend=True,
        legend=dict(
            orientation="h", y=1.08, x=1, xanchor="right",
            font=dict(color="#b0b8c3"), bgcolor="rgba(0,0,0,0)",
        ),
    )
    if orientation == "h":
        fig.update_layout(xaxis_range=[0, min(108, hi + 12)])
    else:
        fig.update_layout(yaxis_range=[0, min(108, hi + 10)])
    return fig


def collapse_k_repeats(df):
    """Reduce the K rows of one (dataset x attack x example x attempt) unit to one:
    ``success`` becomes the fraction of that unit's runs that succeeded (at K=1:
    0.0 or 1.0, that run's verdict). Other columns (response, error, is_blocked, ...) are taken as a
    whole row: the first repeat without an error, or repeat 0 if all failed.
    Adds a ``K`` column: the configured K, i.e. the largest number of repeats
    seen (units with a stage-1 error have fewer rows)."""
    if "k_index" not in df.columns or "success" not in df.columns or df.empty:
        return df
    # 'dataset' is absent in single-dataset CSVs. Two examples with the same text
    # are told apart by their position among rows with the same keys and k_index.
    keys = [c for c in ("dataset", "attack_name", _example_col(df), "n_index") if c in df.columns]
    df = df.assign(_unit=df.groupby(keys + ["k_index"], sort=False, dropna=False).cumcount())
    keys.append("_unit")
    groups = df.groupby(keys, sort=False, dropna=False)
    # One whole row per unit (pandas "first" would mix columns from different
    # repeats): the first repeat without an error, else repeat 0.
    failed = df["_invalid"].astype(bool) if "_invalid" in df.columns else error_mask(df)
    by_health = df.assign(_failed=failed).sort_values("_failed", kind="stable")
    pick = sorted(by_health.groupby(keys, sort=False, dropna=False).head(1).index)
    # Success fraction over the healthy repeats only: an errored repeat is not
    # a trial. Units where every repeat errored keep 0.0 (their picked row
    # carries the error, so downstream _answered() drops them from rates).
    # transform() keeps the row index, so each picked row takes its own unit's
    # fraction whatever order the rows came in.
    healthy_success = df["success"].astype(float).where(~failed)
    fraction = healthy_success.groupby([df[k] for k in keys], sort=False, dropna=False).transform("mean")
    collapsed = df.loc[pick].copy()
    collapsed["success"] = fraction.loc[pick].fillna(0.0).astype(float)
    collapsed["K"] = int(groups.size().max())
    return collapsed.drop(columns=["_unit", "k_index"]).reset_index(drop=True)


def _prepare_frame(df):
    if "evaluation" in df.columns:
        _expand_evaluation(df)
    # Rows without a verdict (request error, judge error, or no 'success' at
    # all) are missing observations, not failed attacks. Mark them before the
    # booleans are coerced; _answered() keeps them out of every rate.
    invalid = error_mask(df)
    if "success" in df.columns:
        invalid |= df["success"].isna()
    df["_invalid"] = invalid
    for col in ("success", "is_blocked"):
        if col in df.columns:
            df[col] = boolean_values(df[col])
    if "response" in df.columns:
        df["response_length"] = df["response"].fillna("").astype(str).str.len()
    return df


def load_data(file_path="df.csv", *, collapse=True):
    try:
        df = _read_dataframe(file_path)
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

    df = _prepare_frame(df)
    return collapse_k_repeats(df) if collapse else df

def _answered(df):
    """Rows that actually got a model response (no transport/provider error).

    ASR denominators use these rows only: an errored request says nothing
    about the model's safety, so counting it as "not attacked successfully"
    understates ASR. Errors stay visible via error_rate over the full df.
    """
    if not len(df):
        return df
    invalid = df.get("_invalid", pd.Series(False, index=df.index)).astype(bool) | error_mask(df)
    invalid |= df["success"].isna() if "success" in df else True
    return df[~invalid]


def _fmt_rate(value):
    return "n/a" if pd.isna(value) else f"{value:.1f}%"


def _observation_status(row):
    if _present(row.get("error")):
        return "request_error"
    evaluation = _mapping(row.get("evaluation"))
    if (_present(row.get("evaluation_error")) or _evaluation_failed(evaluation)):
        return "judge_error"
    if bool(row.get("_invalid", False)) or pd.isna(row.get("success")):
        return "unscored"
    if bool(row.get("is_blocked", False)):
        return "blocked"
    return "success" if bool(row.get("success", False)) else "failure"


def _request_counts(raw):
    # Vectorized masks also understand legacy errors nested in evaluation JSON.
    invalid = raw.get("_invalid", error_mask(raw)).astype(bool) | error_mask(raw)
    if "success" in raw:
        invalid |= raw.success.isna()
    else:
        invalid |= True
    request_errors = raw.get("error", pd.Series("", index=raw.index)).map(_present)
    judge_errors = (error_mask(raw) & ~request_errors)
    unscored = invalid & ~request_errors & ~judge_errors
    blocked = boolean_values(raw.get("is_blocked", pd.Series(False, index=raw.index))) & ~request_errors
    return dict(request_count=len(raw), valid_tests=int((~invalid).sum()),
                error_count=int(invalid.sum()), request_errors=int(request_errors.sum()),
                judge_errors=int(judge_errors.sum()), unscored=int(unscored.sum()),
                blocked_count=int(blocked.sum()),
                blocked_rate=float(blocked.sum() / (~request_errors).sum() * 100)
                if (~request_errors).any() else float("nan"),
                error_rate=float(invalid.mean() * 100) if len(raw) else 0.0)


def _basic_rates(df):
    has_rows = len(df) > 0
    total_tests = len(df) if has_rows else 0
    answered = _answered(df)
    has_answered = len(answered) > 0
    # No answered rows -> the rate is unknown (NaN, shown as "n/a"), not 0%:
    # a run where every request failed must not read as "model is safe".
    success_rate = float(answered["success"].mean() * 100) if "success" in df.columns and has_answered else float("nan")
    blocked_rate = float(answered["is_blocked"].mean() * 100) if "is_blocked" in df.columns and has_answered else float("nan")
    error_count = total_tests - len(answered)
    error_rate = float(error_count / total_tests * 100) if has_rows else 0.0
    return total_tests, success_rate, blocked_rate, error_rate


def _best_attack(df):
    if not ("attack_name" in df.columns and "success" in df.columns and len(df)):
        return "-", 0.0
    keys = [c for c in ("dataset", "attack_name", _example_col(df)) if c in df]
    g = df.groupby(keys, dropna=False).success.mean().groupby("attack_name").agg(["count", "sum", "mean"]).reset_index()
    if not len(g):
        return "-", 0.0
    idx = g["mean"].idxmax()
    return str(g.loc[idx, "attack_name"]), float(g.loc[idx, "mean"] * 100)


def _vulnerable_prompts(df):
    if not ("base_prompt" in df.columns and "success" in df.columns and len(df)):
        return 0, 0, 0.0
    vulnerable = _count_examples(df[df["success"] > 0])
    total = _count_examples(df)
    rate = float(vulnerable / total * 100) if total > 0 else 0.0
    return vulnerable, total, rate


def _merge_mappings(df, base_category, subcategories):
    if "attack_type" in df.columns and "attack_name" in df.columns and len(df):
        merged: dict = {}
        pairs = df[["attack_type", "attack_name"]].drop_duplicates()
        for _, row in pairs.iterrows():
            m = get_framework_mappings(
                attack_type=row["attack_type"],
                attack_name=row["attack_name"],
                base_category=base_category,
                subcategories=subcategories,
            )
            for fw, cats in m.items():
                merged.setdefault(fw, set()).update(cats)
        return merged
    return get_framework_mappings(base_category=base_category, subcategories=subcategories)


def _framework_categories(merged_mappings):
    framework_categories: dict = {}
    for fw_key, cat_ids in merged_mappings.items():
        fw_defs = FRAMEWORKS.get(fw_key, {}).get("categories", {})
        framework_categories[fw_key] = sorted(
            f"{cid}: {fw_defs[cid]['name']}" for cid in cat_ids if cid in fw_defs
        )
    return framework_categories


def _asr_none_attack(df):
    if not ("attack_name" in df.columns and "success" in df.columns and len(df)):
        return 0.0
    none_attack_df = df[df["attack_name"] == "NoneAttack"]
    if len(none_attack_df) == 0:
        return 0.0
    successes, examples = _example_success(none_attack_df)
    return successes / examples * 100


def _asr_max_injection(df):
    if not ("attack_name" in df.columns and "success" in df.columns and len(df)):
        return 0.0, "-"
    injection_df = df[df["attack_name"] != "NoneAttack"]
    if len(injection_df) == 0:
        return 0.0, "-"
    keys = [c for c in ("dataset", "attack_name", _example_col(df)) if c in injection_df]
    attack_stats = injection_df.groupby(keys, dropna=False).success.mean().groupby("attack_name").mean()
    if len(attack_stats) == 0:
        return 0.0, "-"
    return float(attack_stats.max() * 100), str(attack_stats.idxmax())


def _vulnerable_attack_types(df):
    if not ("attack_type" in df.columns and "success" in df.columns and len(df)):
        return []
    type_asr = df.groupby("attack_type")["success"].mean()
    return sorted(type_asr[type_asr > 0].index.tolist())


def calculate_metrics(df, per_request=None):
    total_tests, success_rate, blocked_rate, error_rate = _basic_rates(df)
    # ASR-style rates count answered rows only; error rows are reported
    # separately via error_rate. Metadata still comes from the full df.
    answered_df = _answered(df)

    has_rows = len(df) > 0
    # No pooled Clopper-Pearson: the same example under different attacks is
    # not an independent trial. The per-attack bound lives in the detail table.
    k_repeats = int(df["K"].iloc[0]) if "K" in df.columns and has_rows else 1
    model_name = df["model"].iloc[0] if "model" in df.columns and has_rows else "Unknown"
    n_attack_types = df["attack_type"].nunique() if "attack_type" in df.columns else 0
    n_attacks = df["attack_name"].nunique() if "attack_name" in df.columns else 0

    best_attack_name, best_attack_rate = _best_attack(answered_df)
    vulnerable_prompts, total_prompts, vulnerable_prompts_rate = _vulnerable_prompts(answered_df)

    base_category = df["category"].iloc[0] if "category" in df.columns and has_rows else "Unknown"
    subcategories = df["subcategory"].unique().tolist() if "subcategory" in df.columns else None

    merged_mappings = _merge_mappings(df, base_category, subcategories)
    framework_categories = _framework_categories(merged_mappings)

    asr_none_attack = _asr_none_attack(answered_df)
    asr_max_attack, best_attack_name_detailed = _asr_max_injection(answered_df)

    vulnerable_attack_types = _vulnerable_attack_types(answered_df)
    prioritized_mitigations = get_prioritized_mitigations(vulnerable_attack_types)

    raw = per_request if per_request is not None else df
    operational = _request_counts(raw)
    return {
        "example_count": _count_examples(df), "variant_count": len(df),
        "error_count": total_tests - len(answered_df), "valid_tests": len(answered_df),
        "total_tests": total_tests, "success_rate": success_rate, "blocked_rate": blocked_rate,
        "error_rate": error_rate, "k_repeats": k_repeats,
        "model_name": model_name, "n_attack_types": n_attack_types,
        "n_attacks": n_attacks, "best_attack_name": best_attack_name, "best_attack_rate": best_attack_rate,
        "vulnerable_prompts": vulnerable_prompts, "total_prompts": total_prompts,
        "vulnerable_prompts_rate": vulnerable_prompts_rate,
        "base_category": base_category,
        "framework_categories": framework_categories,
        "framework_mappings": {k: sorted(v) for k, v in merged_mappings.items()},
        "asr_none_attack": asr_none_attack, "asr_max_attack": asr_max_attack,
        "best_attack_name_detailed": best_attack_name_detailed,
        "vulnerable_attack_types": vulnerable_attack_types,
        "prioritized_mitigations": prioritized_mitigations,
        **operational,
    }

def _per_type_stats(df, include_block_rate=False):
    df = _answered(df)  # errored requests are not trials
    type_stats = []
    for attack_type in df["attack_type"].unique():
        type_df = df[df["attack_type"] == attack_type]
        total_unique_prompts = _count_examples(type_df)
        successful_prompts = _count_examples(type_df[type_df["success"] > 0])
        success_rate = successful_prompts / total_unique_prompts if total_unique_prompts > 0 else 0.0
        entry = {
            "attack_type": attack_type,
            SUCCESS_RATE: success_rate * 100 if include_block_rate else success_rate,
            "Total Unique Prompts": total_unique_prompts,
            "Successful Prompts": successful_prompts,
        }
        if include_block_rate:
            entry[BLOCK_RATE] = type_df["is_blocked"].mean() * 100
        type_stats.append(entry)
    return type_stats


def _build_top_types_html(df, include_plotlyjs=True):
    if not {"attack_type", "success", "attack_name", "base_prompt"}.issubset(df.columns):
        return ""
    top_types = pd.DataFrame(_per_type_stats(df))
    top_types[SUCCESS_RATE] = top_types[SUCCESS_RATE] * 100
    top_types = top_types.sort_values(SUCCESS_RATE, ascending=False).head(3).reset_index(drop=True)
    fig_top_types = px.bar(
        top_types, x=SUCCESS_RATE, y="attack_type", orientation="h",
        text=SUCCESS_RATE
    )
    fig_top_types.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_top_types.update_layout(
        xaxis_title="Successful Unique Prompts (% of unique prompts)", yaxis_title=ATTACK_TYPE, height=350, margin={"l": 10, "r": 10, "t": 30, "b": 10},
        **get_chart_style()
    )
    return pio.to_html(fig_top_types, include_plotlyjs=include_plotlyjs, full_html=False)


def _build_top_attacks_html(df, include_plotlyjs):
    if not {"attack_name", "success"}.issubset(df.columns):
        return ""
    top_attacks = _per_attack_asr(df).sort_values(SUCCESS_RATE, ascending=False).head(3)
    if top_attacks.empty:
        return ""
    fig_top_attacks = _asr_upper_figure(top_attacks, orientation="h")
    fig_top_attacks.update_layout(
        xaxis_title="Attack Success Rate (%)", yaxis_title="Attack Name", height=350, margin=dict(l=10,r=10,t=40,b=10),
        **get_chart_style()
    )
    return pio.to_html(fig_top_attacks, include_plotlyjs=include_plotlyjs, full_html=False)


def _build_attack_type_html(df):
    if not {"attack_type","success","is_blocked","attack_name","base_prompt"}.issubset(df.columns):
        return ""
    attack_type_stats = pd.DataFrame(_per_type_stats(df, include_block_rate=True))
    attack_type_stats = attack_type_stats[attack_type_stats[SUCCESS_RATE] > 3]
    if len(attack_type_stats) == 0:
        return "<p style='color: var(--muted); text-align: center; padding: 40px;'>No attack types with successful unique prompts > 3%</p>"
    fig_attack_type = px.bar(attack_type_stats, x="attack_type", y=SUCCESS_RATE)
    fig_attack_type.update_layout(
        xaxis_title=ATTACK_TYPE, yaxis_title="Successful Unique Prompts (% of unique prompts)", height=400, margin={"l": 10, "r": 10, "t": 30, "b": 10},
        **get_chart_style()
    )
    return pio.to_html(fig_attack_type, include_plotlyjs=False, full_html=False)


def _build_attacks_html(df):
    if not {"attack_name","success","is_blocked"}.issubset(df.columns):
        return ""
    attack_stats = _per_attack_asr(df)
    attack_stats = attack_stats[attack_stats[SUCCESS_RATE] > 3]
    if len(attack_stats) == 0:
        return "<p style='color: var(--muted); text-align: center; padding: 40px;'>No individual attacks with Attack Success Rate > 3%</p>"
    fig_attacks = _asr_upper_figure(attack_stats, orientation="v")
    fig_attacks.update_layout(
        xaxis_title="Attack Name", yaxis_title="Attack Success Rate (%)", xaxis_tickangle=45, height=500, margin=dict(l=10,r=10,t=40,b=50),
        **get_chart_style()
    )
    return pio.to_html(fig_attacks, include_plotlyjs=False, full_html=False)


def _label_bool_success(df):
    """Map per-request True/False to Fail/Success. Leave K-mean fractions alone."""
    if "success" not in df.columns or df.empty:
        return df
    uniques = set(df["success"].dropna().unique())
    if uniques <= {0, 1, True, False, 0.0, 1.0}:
        out = df.copy()
        out["success"] = np.where(out["success"].astype(bool), "Success", "Fail")
        return out
    return df


def _build_length_charts_html(df):
    if not {"response_length","success","attack_type"}.issubset(df.columns):
        return "", ""
    df = _answered(df)  # an errored request has no response to measure
    if df.empty:
        return "", ""
    df = _label_bool_success(df)
    fig_length = px.box(df, x="success", y="response_length", color="success")
    fig_length.update_layout(
        xaxis_title="Attack Success", yaxis_title="Response Length (chars)", height=400, margin=dict(l=10,r=10,t=30,b=10),
        **get_chart_style()
    )
    length_html = pio.to_html(fig_length, include_plotlyjs=False, full_html=False)

    avg_length = df.groupby("attack_type")["response_length"].mean().reset_index()
    fig_avg_length = px.bar(avg_length, x="attack_type", y="response_length")
    fig_avg_length.update_layout(
        xaxis_title=ATTACK_TYPE, yaxis_title="Avg Response Length (chars)", xaxis_tickangle=45, height=400, margin={"l": 10, "r": 10, "t": 30, "b": 50},
        **get_chart_style()
    )
    avg_length_html = pio.to_html(fig_avg_length, include_plotlyjs=False, full_html=False)
    return length_html, avg_length_html


def _build_answer_html(df):
    if not ({"did_answer","success"}.issubset(df.columns) and len(df)):
        return ""
    df = _answered(df)  # errored requests are not trials
    if df.empty:
        return ""
    df = _label_bool_success(df)
    answer_analysis = pd.crosstab(df["did_answer"], df["success"], normalize="index") * 100
    answer_long = answer_analysis.reset_index().melt(id_vars="did_answer", var_name="success", value_name="pct")
    fig_answer = px.bar(answer_long, x="did_answer", y="pct", color="success", barmode="stack")
    fig_answer.update_layout(
        xaxis_title="Did Answer", yaxis_title="Percentage", height=400, margin=dict(l=10,r=10,t=30,b=10),
        **get_chart_style()
    )
    return pio.to_html(fig_answer, include_plotlyjs=False, full_html=False)


def _lazy_chart_html(html):
    def defer(match):
        code = match.group(1)
        plot = re.search(r'Plotly\.newPlot\(\s*"([^"]+)"', code)
        if not plot:
            return match.group(0)
        key = json.dumps(plot.group(1))
        return f'<script>window.REPORT_PLOTS = window.REPORT_PLOTS || {{}}; window.REPORT_PLOTS[{key}] = function() {{{code}}};</script>'
    return re.sub(r'<script type="text/javascript">(.*?)</script>', defer, html, flags=re.S)


def create_charts(df, include_plotlyjs=True, per_request=None):
    fig_top_types_html = _build_top_types_html(df, include_plotlyjs=include_plotlyjs)
    fig_top_attacks_html = _build_top_attacks_html(
        df, include_plotlyjs=include_plotlyjs and not fig_top_types_html
    )
    fig_attack_type_html = _build_attack_type_html(df)
    fig_attacks_html = _build_attacks_html(df)
    content = per_request if per_request is not None else df
    fig_length_html, fig_avg_length_html = _build_length_charts_html(content)
    fig_answer_html = _build_answer_html(content)

    return {key: _lazy_chart_html(value) for key, value in {
        "fig_top_types_html": fig_top_types_html,
        "fig_top_attacks_html": fig_top_attacks_html,
        "fig_attack_type_html": fig_attack_type_html,
        "fig_attacks_html": fig_attacks_html,
        "fig_length_html": fig_length_html,
        "fig_avg_length_html": fig_avg_length_html,
        "fig_answer_html": fig_answer_html
    }.items()}

def _attack_detailed_html(df, per_request=None):
    if not {"attack_type", "attack_name", "success", "is_blocked"}.issubset(df.columns):
        return ""
    raw = per_request if per_request is not None else df
    stats = _per_attack_asr(df).set_index("attack_name")
    rows = []
    for (kind, name), group in raw.groupby(["attack_type", "attack_name"], sort=False):
        counts = _request_counts(group)
        units = df[df.attack_name == name]
        per_example = units.groupby(_example_col(units)).size() if len(units) else pd.Series(dtype=int)
        lo, hi = (int(per_example.min()), int(per_example.max())) if len(per_example) else (0, 0)
        rows.append({
            "Attack": name, "Type": kind, "Examples": _count_examples(group),
            "Assessed examples": int(stats.loc[name, "examples"]) if name in stats.index else 0,
            "Variants per example": str(lo) if lo == hi else f"{lo}–{hi}",
            "Requests": counts["request_count"], "Valid observations": counts["valid_tests"],
            "Request errors": counts["request_errors"], "Judge errors": counts["judge_errors"],
            "Unscored": counts["unscored"], "Blocked": counts["blocked_count"],
            SUCCESS_RATE: _fmt_rate(stats.loc[name, SUCCESS_RATE]) if name in stats.index else "No assessment",
            "95% Upper": f"≤{stats.loc[name, 'upper']:.1f}%" if name in stats.index else "—",
        })
    return '<div class="table-container">' + pd.DataFrame(rows).to_html(index=False, classes="dataframe compact", border=0) + '</div>'


def _bfmt(x, col=None):
    if isinstance(x, (bool, np.bool_)):
        return "✅" if x else "❌"
    if col == "success" and isinstance(x, (float, np.floating)):  # fraction over K
        return "✅" if x == 1 else "❌" if x == 0 else f"{x:.0%}"
    return str(x)


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clip(s, n=100):
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


_EXPLORER_COLUMNS = (
    ("attack_name", "Attack"),
    ("attack_type", "Type"),
    ("n_index", "Attack variant"),
    ("k_index", "Requests"),
    ("base_prompt", "Base prompt"),
    ("success", "Success"),
    ("is_blocked", "Blocked"),
)


def _explorer_columns(df):
    cols = []
    for c, _ in _EXPLORER_COLUMNS:
        if c not in df.columns:
            continue
        if c == "n_index" and df["n_index"].nunique() <= 1:
            continue
        cols.append(c)
    return cols


def _explorer_groups(df):
    """One unit per (example × attack × N); K repeats stay together for expand."""
    if df.empty:
        return []
    work = df.copy()
    if "k_index" not in work.columns:
        return [(row, work.iloc[[i]]) for i, (_, row) in enumerate(work.iterrows())]
    keys = [c for c in ("dataset", "attack_name", _example_col(work), "n_index") if c in work.columns]
    work = work.assign(
        _unit=work.groupby(keys + ["k_index"], sort=False, dropna=False).cumcount()
    )
    keys = keys + ["_unit"]
    groups = []
    for _, g in work.groupby(keys, sort=False, dropna=False):
        summary = g.iloc[0].copy()
        if "success" in g.columns:
            valid = _answered(g)
            summary["success"] = float(valid["success"].mean()) if len(valid) else float("nan")
        if "is_blocked" in g.columns:
            summary["is_blocked"] = bool(g["is_blocked"].fillna(False).astype(bool).any())
        summary["k_index"] = int(len(g))
        groups.append((summary, g.sort_values("k_index", kind="stable") if "k_index" in g.columns else g))
    return groups


def _explorer_payload(df):
    texts, lookup, rows = [], {}, []
    def intern(value):
        value = "" if value is None or (not isinstance(value, (dict, list)) and pd.isna(value)) else str(value)
        if value not in lookup:
            lookup[value] = len(texts)
            texts.append(value)
        return lookup[value]
    variant_counts = {}
    groups = _explorer_groups(df)
    for summary, _ in groups:
        key = (str(summary.get("attack_name", "")), str(summary.get(_example_col(df), "")))
        variant_counts[key] = variant_counts.get(key, 0) + 1
    for summary, repeats in groups:
        attack = str(summary.get("attack_name", ""))
        example = str(summary.get(_example_col(df), ""))
        responses = []
        for _, row in repeats.iterrows():
            status = _observation_status(row)
            evaluation = _mapping(row.get("evaluation"))
            error = (row.get("error") if _present(row.get("error")) else
                     row.get("evaluation_error") if _present(row.get("evaluation_error")) else
                     evaluation.get("evaluation_error") or evaluation.get("error") or
                     _mapping(evaluation.get("raw_evaluation")).get("error") or
                     ("Missing or invalid judge verdict" if status in ("judge_error", "unscored") else ""))
            # Store concise verdict fields, not the judge's repeated input template.
            verdict = {k: evaluation[k] for k in ("reason", "should_answer", "did_answer", "is_harmful") if k in evaluation}
            responses.append([status, intern(row.get("response", "")), intern(error),
                              intern(json.dumps(verdict, ensure_ascii=False) if verdict else "")])
        valid = sum(r[0] in ("success", "failure", "blocked") for r in responses)
        rows.append(dict(attack=attack, type=str(summary.get("attack_type", "")), example=example,
                         variant=int(summary.get("n_index", 0)) + 1,
                         variants=variant_counts[(attack, example)],
                         base=intern(summary.get("base_prompt", "")),
                         prompt=intern(summary.get("prompt", "")), responses=responses,
                         valid=valid, successes=sum(r[0] == "success" for r in responses),
                         blocked=any(r[0] == "blocked" for r in responses), errors=len(responses)-valid))
    return dict(texts=texts, rows=rows)


def _explorer_table_html(df, display_columns, ns=""):
    sfx = f"_{ns}" if ns else ""
    payload = _explorer_payload(df) if display_columns else {"texts": [], "rows": []}
    # Escape script terminators even though this is non-executable JSON.
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    return f"""
    <script type="application/json" id="log-data{sfx}">{data}</script>
    <div class="table-container">
      <table id="explorer-table{sfx}" class="dataframe compact">
        <thead><tr><th>Attack</th><th>Type</th><th>Example</th><th>Attack variant</th>
        <th>Base prompt</th><th>Requests / valid</th><th>Success</th><th>Errors</th><th>Blocked</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <div class="pager">
      <button id="page-prev{sfx}" type="button">Previous</button>
      <span id="page-label{sfx}"></span>
      <button id="page-next{sfx}" type="button">Next</button>
      <label>Rows per page <select id="page-size{sfx}"><option>25</option><option selected>50</option><option>100</option></select></label>
    </div>
    """


def generate_data_tables(df, ns="", per_request=None):
    attack_detailed_html = _attack_detailed_html(df, per_request)
    explorer_df = per_request if per_request is not None else df
    display_columns = _explorer_columns(explorer_df)
    explorer_table_html = _explorer_table_html(explorer_df, display_columns, ns=ns)

    paired_html, paired_title, paired_note = _paired_test_html(df)

    return {
        "attack_detailed_html": attack_detailed_html,
        "attack_type_risk_html": _attack_type_risk_html(df),
        "paired_test_html": paired_html,
        "paired_test_title": paired_title,
        "paired_test_note": paired_note,
        "explorer_table_html": explorer_table_html,
        "samples_html": "",
        "display_columns": display_columns
    }


def _sanitize_ns(name):
    """Turn a dataset name into a safe HTML id / JS identifier fragment."""
    return re.sub(r"\W+", "_", str(name))


_REPORT_STYLES = """
    <style>
    :root{
      --bg: #0e1117;
      --card: #161a23;
      --text: #e8e8e8;
      --muted: #b0b8c3;
      --accent: #ff4b4b;
      --accent2: #ffa14b;
      --border: #2a2f3a;
      --good: #22c55e;
      --warn: #f59e0b;
    }
    * { box-sizing: border-box; }
    body{
      margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
      background: var(--bg); color: var(--text);
    }
    .wrapper{ max-width: 1200px; margin: 0 auto; padding: 24px; }
    h1{ font-size: 28px; margin: 0 0 8px; }
    h2{ font-size: 22px; margin: 24px 0 8px; }
    h3{ font-size: 18px; margin: 16px 0 8px; color: var(--muted); }
    .section{ background: var(--card); border: 1px solid var(--border); padding: 16px; border-radius: 16px; margin-bottom: 16px; }
    .metric-link{ background:none; border:0; color:var(--warn); cursor:pointer; padding:0; }
    .pager{ display:flex; gap:12px; align-items:center; margin:12px 0; flex-wrap:wrap; }
    .pager button,.pager select{ background:var(--card); color:var(--text); border:1px solid var(--border); padding:8px; }
    .pager button:disabled{ opacity:.4; }
    .table-container{ overflow-x:auto; }
    pre{ overflow-wrap:anywhere; }
    @media(max-width:700px){ .grid-4,.grid-2,.controls{ grid-template-columns:1fr!important; } }
    .grid-4{ display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; }
    .grid-2{ display:grid; grid-template-columns: repeat(2, 1fr); gap:12px; }
    .metric{
      background: #121620; border: 1px solid var(--border);
      padding:16px; border-radius: 12px;
    }
    .metric .label{ color: var(--muted); font-size: 13px; }
    .metric .value{ font-size: 24px; font-weight:600; margin-top:4px; }
    .metric .delta{ color: var(--muted); font-size: 12px; margin-top:2px; }
    .kf{ display:flex; gap:12px; flex-wrap: wrap;}
    .kf .badge{ padding: 10px 12px; background:#102116; border:1px solid #1b3a26; color:#9be3b4; border-radius:10px; }
    .kf .warn{ background:#211d10; border-color:#3a2f1b; color:#ffd29b; }
    hr{ border: none; border-top: 1px solid var(--border); margin: 20px 0; }

    .tabs{ display:flex; gap:6px; margin: 12px 0 16px; flex-wrap: wrap;}
    .tablink{
      background: transparent; color: var(--text); border:1px solid var(--border);
      padding:8px 12px; border-radius:999px; cursor:pointer;
    }
    .tablink.active{ background: var(--accent); border-color: var(--accent); }

    table.dataframe{ width:100%; border-collapse: collapse; }
    table.dataframe th, table.dataframe td{ border-bottom:1px solid var(--border); padding:8px; text-align:left; }
    table.dataframe tr:hover{ background: #0f1420; }
    .compact th, .compact td{ font-size: 13px; }

    .table-container{ max-height: 600px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; }
    .table-container table{ margin: 0; border-radius: 0; }

    .sample-block{ margin: 8px 0; }
    .sample-block summary{ cursor:pointer; list-style: none; border:1px solid var(--border); background:#0f1420; padding:10px 12px; border-radius:10px; }
    .sample-block summary::-webkit-details-marker{ display:none; }
    .sample-inner{ padding:10px 2px; }
    tr.explorer-row { cursor: pointer; }
    tr.explorer-row td:first-child::before { content: "▸ "; color: var(--muted); }
    tr.explorer-row.open td:first-child::before { content: "▾ "; }
    tr.explorer-row.open { background: #0f1420; }
    tr.explorer-expand td { background: #0b0f19; }
    pre{ white-space: pre-wrap; background:#0b0f19; padding:10px; border: 1px solid var(--border); border-radius: 8px; }

    .controls{ display:grid; grid-template-columns: 1fr 1fr 1fr; gap:12px; margin-bottom: 10px; }
    .control{ background:#0f1420; border:1px solid var(--border); padding:10px; border-radius:10px; }
    .checkbox-group{ display:flex; flex-wrap: wrap; gap:8px; max-height: 120px; overflow:auto; }
    .checkbox-group label{ background:#0b0f19; border:1px solid var(--border); padding:6px 8px; border-radius:8px; display:flex; align-items:center; gap:6px; }
    .select{ width:100%; padding:8px; background:#0b0f19; border:1px solid var(--border); color:var(--text); border-radius:8px; }

    .footer{ color: var(--muted); font-size: 12px; text-align:center; margin-top: 28px; }

    .plot-container{ width: 100%; display: flex; justify-content: center; margin: 16px 0; }
    .plot-container > div{ width: 100%; max-width: 100%; }

    .mitigation-item{
      background: #0f1420; border: 1px solid var(--border); padding: 14px 16px;
      border-radius: 12px; margin-bottom: 10px; display: flex; align-items: center; gap: 16px;
    }
    .mitigation-item .mit-name{ flex: 1; font-weight: 500; }
    .mitigation-item .mit-coverage{ color: var(--muted); font-size: 13px; white-space: nowrap; }
    .progress-bar{
      width: 120px; height: 8px; background: #1a1f2e; border-radius: 4px; overflow: hidden; flex-shrink: 0;
    }
    .progress-bar .fill{ height: 100%; border-radius: 4px; background: var(--good); transition: width 0.3s; }
    .mitigation-badge{
      display: inline-block; padding: 4px 10px; margin: 3px 4px 3px 0; font-size: 12px;
      background: #102116; border: 1px solid #1b3a26; color: #9be3b4; border-radius: 8px;
    }

.dataset-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:20px 0 18px;padding:5px;background:#121620;border:1px solid var(--border);border-radius:10px;width:fit-content;max-width:100%}
.dataset-tablink{appearance:none;font:inherit;font-size:14px;line-height:1.4;font-weight:500;padding:9px 15px;border:1px solid transparent;border-radius:7px;background:transparent;color:var(--muted);cursor:pointer;overflow-wrap:anywhere;transition:background .15s,color .15s,border-color .15s}
.dataset-tablink:hover{background:#1c2330;color:var(--text)}
.dataset-tablink.active{background:#273347;border-color:#465b79;color:#f0f4fb;box-shadow:0 1px 3px #0003}
.dataset-tablink:focus-visible{outline:2px solid #91b0ff;outline-offset:2px}
@media(prefers-reduced-motion:reduce){.dataset-tablink{transition:none}}
.summary-results{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:20px 0 18px}
.summary-results .metric{padding:16px 18px}.summary-results .value{font-size:28px;line-height:1.25;letter-spacing:-.4px;margin:7px 0 5px;font-variant-numeric:tabular-nums}.summary-results .delta{font-size:13px;line-height:1.45}.summary-results .attack-value{color:var(--accent2)}
.summary-volume{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;font-size:14px;margin:18px 0 8px}.summary-volume strong{font-size:18px;font-variant-numeric:tabular-nums}.summary-arrow{color:var(--muted)}
.summary-quality{display:flex;align-items:center;gap:10px 22px;flex-wrap:wrap;border-top:1px solid var(--border);padding:14px 0;margin-top:14px;font-size:14px}.summary-quality button{font:inherit;color:var(--text)}.summary-help{color:var(--muted);font-size:13px;margin:8px 0 18px}.summary-help summary{cursor:pointer;width:fit-content}.summary-help p{line-height:1.6;max-width:850px}.summary-help ul{line-height:1.8;padding-left:20px}.summary-observed{font-size:13px;color:var(--muted);margin-top:18px}
@media(max-width:700px){.summary-results{grid-template-columns:1fr}.summary-results .value{font-size:26px}.summary-volume{gap:8px}.summary-quality{gap:12px}}
    </style>
    """

def _build_report_js(namespaces, attack_types_by_ns, multi):
    config = json.dumps(dict(namespaces=namespaces, types=attack_types_by_ns, multi=multi), ensure_ascii=False).replace("<", "\\u003c")
    code = Path(__file__).with_name("report_ui.js").read_text(encoding="utf-8")
    return f"<script>const REPORT_CONFIG = {config};\n{code}</script>"


def _build_body_html(df, metrics, charts, data_tables, ns, generated_at):
    """Build one report body — the five tabs plus the footer — for a single
    dataset (or the whole df in single-dataset mode).

    All element ids are suffixed with ``_<ns>`` when ``ns`` is non-empty, so
    multiple bodies can coexist in one document without id collisions.
    """
    sfx = f"_{ns}" if ns else ""
    k_repeats = metrics.get("k_repeats", 1)

    assessed = _answered(df) if "success" in df.columns else pd.DataFrame()
    names = set(assessed["attack_name"]) if "attack_name" in assessed else set()
    control = f"{metrics.get('asr_none_attack', 0):.1f}%" if "NoneAttack" in names else "Not measured"
    attack = f"{metrics.get('asr_max_attack', 0):.1f}%" if names - {"NoneAttack"} else "Not measured"
    best = metrics.get("best_attack_name_detailed", "-")
    comparisons, method = paired_test_vs_baseline(df)
    comparisons = comparisons[comparisons["n pairs"] > 0] if not comparisons.empty else comparisons
    compared = len(comparisons)
    significant = int(((comparisons["significant"]) & (comparisons["Δ (pp)"] > 0)).sum()) if compared else 0
    significance_value = f'{significant}<span style="font-size:18px;color:var(--muted);letter-spacing:0"> / {compared}</span>' if compared else "Not measured"
    significance_note = "One-sided test for ASR increase" if method == "paired bootstrap" else "Two-sided test · higher ASR only"
    if not compared:
        significance_note = "No assessed pairs with the control"
    examples = metrics.get("example_count", metrics["total_prompts"])
    variants = metrics.get("variant_count", metrics["total_tests"])
    requests = metrics.get("request_count", metrics["total_tests"])
    valid = metrics.get("valid_tests", 0)
    blocked = metrics.get("blocked_count", 0)
    req, judge, unscored = (metrics.get(k, 0) for k in ("request_errors", "judge_errors", "unscored"))
    repeats = k_repeats
    error_label = " · ".join(f"{v} {label}" for v, label in [(req, "request errors"), (judge, "judge errors"), (unscored, "unscored")] if v) or "0 errors"

    fw_short = {
        "OWASP_LLM_TOP_10": "OWASP LLM Top 10",
        "MITRE_ATLAS": "MITRE ATLAS",
        "FSTEK_117": "ФСТЭК 117",
    }
    fw_badge_colors = {
        "OWASP_LLM_TOP_10": ("#9bb4e3", "#1a1e3a", "#2a3a5a"),
        "MITRE_ATLAS": ("#9be3b4", "#102116", "#1b3a26"),
        "FSTEK_117": ("#ffd29b", "#211d10", "#3a2f1b"),
    }
    framework_categories = metrics.get("framework_categories", {})
    framework_badges_html = ""
    for fw_key in ["OWASP_LLM_TOP_10", "MITRE_ATLAS", "FSTEK_117"]:
        cats = framework_categories.get(fw_key, [])
        if not cats:
            continue
        fw_name = fw_short.get(fw_key, fw_key)
        color, bg, border = fw_badge_colors.get(fw_key, ("#e8e8e8", "#1a1e3a", "#2a3a5a"))
        fw_defs = FRAMEWORKS.get(fw_key, {}).get("categories", {})
        badges = []
        for cat in cats:
            cat_id = cat.split(":")[0].strip()
            desc = fw_defs.get(cat_id, {}).get("description", "")
            badges.append(
                f'<div class="badge" style="background:{bg}; border-color:{border}; color:{color};" title="{desc}">{cat}</div>'
            )
        framework_badges_html += f"""
          <div style="margin-bottom:8px;"><strong>{fw_name}:</strong></div>
          <div class="kf" style="margin-bottom:12px;">
            {chr(10).join(badges)}
          </div>
"""

    mitigations_html = ""
    prioritized = metrics.get("prioritized_mitigations", [])
    if prioritized:
        items = []
        for m in prioritized:
            items.append(
                f'<div class="mitigation-item">'
                f'<div class="mit-name">{m["mitigation"]}</div>'
                f'</div>'
            )
        mitigations_html += "<h3>Prioritized Mitigations</h3>\n" + "\n".join(items)
    else:
        mitigations_html += '<p style="color:var(--muted);padding:20px;">No vulnerable attack types detected — no mitigations to recommend.</p>'

    controls_html = f"""
    <div class="controls">
      <div class="control">
        <div style="font-size:12px; color: var(--muted); margin-bottom:6px;">Filter by Attack Type</div>
        <div id="attack-type-box{sfx}" class="checkbox-group"></div>
      </div>
      <div class="control">
        <div style="font-size:12px; color: var(--muted); margin-bottom:6px;">Filter by Success</div>
        <select id="filter-success{sfx}" class="select">
          <option value="all">All</option>
          <option value="success">At least one successful response</option>
          <option value="fail">No successful valid responses</option>
          <option value="unknown">No assessment</option>
        </select>
      </div>
      <div class="control">
        <div style="font-size:12px; color: var(--muted); margin-bottom:6px;">Filter by Blocked Status</div>
        <select id="filter-blocked{sfx}" class="select">
          <option value="all">All</option>
          <option value="blocked">Blocked Only</option>
          <option value="not_blocked">Not Blocked Only</option>
        </select>
      </div>
      <div class="control"><label>Search all records
        <input id="log-search{sfx}" class="select" type="search" placeholder="Attack, prompt, response or error"></label></div>
      <div class="control"><label>Errors
        <select id="filter-errors{sfx}" class="select">
          <option value="all">All records</option><option value="any">With errors</option>
          <option value="request_error">Request errors</option><option value="judge_error">Judge errors</option>
          <option value="unscored">Unscored responses</option><option value="no_valid">No valid assessment</option>
        </select></label></div>
    </div>
    """

    return f"""
      <div class="tabs">
        <button class="tablink active" data-target="tab1{sfx}" onclick="showTab('{ns}',1)">📋 Executive Summary</button>
        <button class="tablink" data-target="tab2{sfx}" onclick="showTab('{ns}',2)">⚔️ Attack Analysis</button>
        <button class="tablink" data-target="tab3{sfx}" onclick="showTab('{ns}',3)">📝 Content Analysis</button>
        <button class="tablink" data-target="tab4{sfx}" onclick="showTab('{ns}',4)">🔍 Run log</button>
        <button class="tablink" data-target="tab5{sfx}" onclick="showTab('{ns}',5)">🛡️ Mitigations</button>
      </div>

      <!-- Executive Summary -->
      <div id="tab1{sfx}" class="section">
        <h2>🎯 Executive Summary</h2>
        <div class="summary-results">
          <div class="metric"><div class="label">ASR without transformation</div><div class="value">{control}</div><div class="delta">Original request · NoneAttack control</div></div>
          <div class="metric"><div class="label">Highest attack ASR</div><div class="value attack-value">{attack}</div><div class="delta">{best}</div></div>
          <div class="metric"><div class="label">Attacks significantly above baseline</div><div class="value">{significance_value}</div><div class="delta">{significance_note}</div></div>
        </div>
        <div class="summary-volume"><span><strong>{examples}</strong> original examples</span><span class="summary-arrow">→</span><span><strong>{variants}</strong> attack variants</span><span class="summary-arrow">→</span><span><strong>{requests}</strong> model requests</span></div>
        <div class="summary-help">Up to {repeats} requests per variant. Repeats do not increase the number of independent examples.</div>
        <div class="summary-quality"><span><strong>{valid} / {requests}</strong> requests assessed</span><button class="metric-link" onclick="showErrors('{ns}','any')">{error_label}</button><span>{blocked} blocked requests</span></div>
        <details class="summary-help"><summary>How this run is counted</summary><p>Each original example is transformed into attack variants, then each variant is sent repeatedly. ASR averages valid responses within each variant, variants within each original example, and then examples equally. Errors are excluded. A blocked request is an unsuccessful attack, not an error.</p><ul><li>Request errors: {req}</li><li>Judge errors: {judge}</li><li>Unscored responses: {unscored}</li></ul><p>Upper confidence bounds are shown in the attack charts. Paired differences and significance are available in Attack Analysis.</p></details>
        <h3>Top 3 Attack Types</h3>
        <div style="color:var(--muted); font-size:13px; margin-bottom:8px;">Share of unique prompts with success &gt; 0 in at least one attack of this type</div>
        {charts['fig_top_types_html']}

        <h3>Top 3 Attacks</h3>
        <div style="color:var(--muted); font-size:13px; margin-bottom:8px;">Attack success rate: average valid responses within each variant, then variants within each original example, then examples equally; {_bound_caption(df)}</div>
        {charts['fig_top_attacks_html']}
        <p class="summary-observed">{metrics['vulnerable_prompts']}/{metrics['total_prompts']} original examples had at least one successful response across the tested attacks and repeats. This is not a per-request success rate.</p>
        <h3>📊 Security Framework Coverage</h3>
        <div style="background:#0f1420; border:1px solid var(--border); padding:16px; border-radius:12px; margin-bottom:16px;">
          <div style="margin-bottom:12px;"><strong>Category:</strong> <span style="color:var(--accent2);">{metrics.get('base_category', 'Unknown')}</span></div>
          {framework_badges_html if framework_badges_html else '<div style="color:var(--muted);">No framework categories mapped</div>'}
        </div>



      </div>

      <!-- Attack Analysis -->
      <div id="tab2{sfx}" class="section" style="display:none;">
        <h2>⚔️ Attack Analysis</h2>

        <h3>Successful Unique Prompts, by Attack Type</h3>
        <div style="color:var(--muted); font-size:13px; margin-bottom:8px;">Share of unique prompts with success &gt; 0 in at least one attack of this type</div>
        <div class="plot-container">
          {charts['fig_attack_type_html']}
        </div>

        <h3>Attack Success Rate by Attack Name</h3>
        <div style="color:var(--muted); font-size:13px; margin-bottom:8px;">Attack success rate: average valid responses within each variant, then variants within each original example, then examples equally; {_bound_caption(df)}</div>
        <div class="plot-container">
          {charts['fig_attacks_html']}
        </div>

        <h3>📊 Detailed Attack Statistics</h3>
        {data_tables['attack_detailed_html']}

        <h3>🎯 Risk by Attack Type (one attempt per attack)</h3>
        <div style="color:var(--muted); font-size:13px; margin-bottom:8px;">Chance an example falls to at least one attack of the type, priced at a single attempt each: 1 − ∏(1 − per-attack success). Assumes the attacks of a type fail independently on a fixed example.</div>
        {data_tables.get('attack_type_risk_html', '')}

        <h3>🔬 {data_tables.get('paired_test_title', '')}</h3>
        <p style="color: var(--muted);">{data_tables.get('paired_test_note', '')} Significant at α = 0.05 after Benjamini-Hochberg correction across all attacks (FDR level 0.05).</p>
        {data_tables.get('paired_test_html', '')}
      </div>

      <!-- Content Analysis -->
      <div id="tab3{sfx}" class="section" style="display:none;">
        <h2>📝 Content Analysis</h2>
        <div style="color:var(--muted); font-size:13px; margin-bottom:8px;">Each valid model response is one observation here, including repeated requests for the same attack variant.</div>

        <h3>Response Length Distribution by Attack Success</h3>
        <div class="plot-container">
          {charts['fig_length_html']}
        </div>

        <h3>Average Response Length by Attack Type</h3>
        <div class="plot-container">
          {charts['fig_avg_length_html']}
        </div>

        <h3>Response Quality Analysis</h3>
        <div class="plot-container">
          {charts['fig_answer_html']}
        </div>
      </div>

      <!-- Data Explorer -->
      <div id="tab4{sfx}" class="section" style="display:none;">
        <h2>🔍 Run log</h2>
        <div style="color:var(--muted); font-size:13px; margin-bottom:8px;">One row per attack variant of an original example. Repeated requests are grouped. Search and filters cover all records, including other pages. Click a row to read every response.</div>
        {controls_html}
        <div style="margin-bottom:8px; color: var(--muted);"><span id="filtered-count{sfx}"></span></div>
        {data_tables['explorer_table_html']}
      </div>

      <!-- Mitigations -->
      <div id="tab5{sfx}" class="section" style="display:none;">
        <h2>🛡️ Mitigation Recommendations</h2>
        <div style="background:#1a1a10; border:1px solid #3a351b; padding:14px 18px; border-radius:10px; margin-bottom:16px; color:#ffd29b; font-size:14px;">
          The mitigations listed below are general recommendations based on detected attack categories. A professional security audit is needed to determine the concrete mitigations applicable to your specific use case and environment.
        </div>
        {mitigations_html}
      </div>

      <div class="footer">
        <hr/>
        <div>✅ Loaded {len(df)} records • <strong>Model:</strong> {metrics['model_name']} • <strong>Attack Types:</strong> {metrics['n_attack_types']} • <strong>Total Attacks:</strong> {metrics['n_attacks']}</div>
        <div><strong>Report Generated:</strong> {generated_at}</div>
      </div>
    """


def build_html_report(df, metrics, charts, data_tables):
    """
    Build complete HTML report from processed data.

    Multi-dataset mode is used when ``metrics is None`` or ``df`` carries more
    than one distinct ``dataset`` value. It renders a dataset selector at the
    top; selecting a dataset shows that dataset's full report — the same five
    tabs as the single-dataset report (Executive Summary, Attack Analysis,
    Content Analysis, Data Explorer, Mitigations). ``charts`` and
    ``data_tables`` are recomputed per dataset, so both may be ``None``. No
    cross-dataset aggregate is shown.

    Args:
        df: DataFrame with evaluation results
        metrics: Dictionary of calculated metrics, or ``None`` for multi-dataset
        charts: Dictionary of chart HTML strings, or ``None`` for multi-dataset
        data_tables: Dictionary of data table HTML strings, or ``None`` for multi-dataset

    Returns:
        Complete HTML string for the report
    """
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    multi = (
        "dataset" in df.columns
        and not df.empty
        and (metrics is None or df["dataset"].nunique() > 1)
    )

    if multi:
        namespaces = []
        attack_types_by_ns = {}
        selector = []
        panels = []
        first = True
        for ds_name, sub_raw in df.groupby("dataset", sort=False):
            ns = _sanitize_ns(ds_name)
            namespaces.append(ns)
            sub_df = collapse_k_repeats(sub_raw.copy())
            ds_metrics = calculate_metrics(sub_df, per_request=sub_raw)
            ds_charts = create_charts(sub_df, include_plotlyjs=first, per_request=sub_raw)
            ds_tables = generate_data_tables(sub_df, ns=ns, per_request=sub_raw)
            attack_types_by_ns[ns] = (
                sorted(sub_df["attack_type"].dropna().unique().tolist())
                if "attack_type" in sub_df.columns else []
            )
            body = _build_body_html(sub_df, ds_metrics, ds_charts, ds_tables, ns, generated_at)
            hidden = "" if first else ' style="display:none;"'
            panels.append(f'<div id="dataset-panel-{ns}" class="dataset-panel"{hidden}>{body}</div>')
            selector.append(
                f'<button class="dataset-tablink{" active" if first else ""}" '
                f'data-ds="{ns}" onclick="showDataset(\'{ns}\')">{ds_name}</button>'
            )
            first = False
        js = _build_report_js(namespaces, attack_types_by_ns, multi=True)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Multi-Dataset Report</title>
{_REPORT_STYLES}
</head>
<body>
<div class="wrapper">
  <h1>🔍 Automated Report — Multi-Dataset</h1>
  <div style="color:var(--muted);">Per-dataset red teaming results — select a dataset to view its full report</div>
  <div class="dataset-tabs">
    {''.join(selector)}
  </div>
  {''.join(panels)}
</div>
{js}
</body>
</html>"""

    # Single-dataset mode. Compute any artifacts the caller did not supply.
    if metrics is None:
        metrics = calculate_metrics(df)
    if charts is None:
        charts = create_charts(df)
    if data_tables is None:
        data_tables = generate_data_tables(df)

    attack_types = (
        sorted(df["attack_type"].dropna().unique().tolist())
        if "attack_type" in df.columns else []
    )
    body = _build_body_html(df, metrics, charts, data_tables, "", generated_at)
    js = _build_report_js([""], {"": attack_types}, multi=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Static Report</title>
{_REPORT_STYLES}
</head>
<body>
<div class="wrapper">
  <h1>🔍 Automated Report</h1>
  <div style="color:var(--muted);">Comprehensive analysis of red teaming results</div>
  {body}
</div>
{js}
</body>
</html>"""

def main():
    parser = argparse.ArgumentParser(description="Generate static HTML report for framework results")
    parser.add_argument("--data-file", type=str, default="df.csv", help="Path to data file (default: df.csv)")
    parser.add_argument("--output", "-o", type=str, default="Static_report.html", help="Output HTML file path (default: Static_report.html)")
    args = parser.parse_args()

    try:
        df = load_data(args.data_file, collapse=False)
        if df.empty:
            print("Warning: No data loaded. Generating empty report.")

        per_request = df
        df = collapse_k_repeats(per_request.copy())
        metrics = calculate_metrics(df, per_request=per_request)
        charts = create_charts(df, per_request=per_request)
        data_tables = generate_data_tables(df, per_request=per_request)

        # Use the shared HTML builder
        report_df = per_request if "dataset" in per_request and per_request["dataset"].nunique() > 1 else df
        html = build_html_report(report_df, metrics, charts, data_tables)

        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"Report generated: {args.output}")

    except Exception as e:
        print(f"Error processing data: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()