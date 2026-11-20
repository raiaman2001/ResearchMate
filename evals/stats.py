"""Chhote-sample statistics: mean, bootstrap confidence interval, paired comparison (stdlib only)."""
import random
import statistics


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def bootstrap_ci(xs, n_boot=2000, alpha=0.05, seed=0):
    """Percentile bootstrap CI of the mean. (lo, hi) ya (None, None) agar data nahi."""
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    if len(xs) == 1:
        return xs[0], xs[0]
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(xs, k=len(xs))) for _ in range(n_boot))
    return means[int(alpha / 2 * n_boot)], means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]


def mean_ci(xs, **kw):
    xs = [x for x in xs if x is not None]
    lo, hi = bootstrap_ci(xs, **kw)
    return {"n": len(xs), "mean": mean(xs), "lo": lo, "hi": hi}


def paired(a, b, higher_is_better=None, n_min=5, **kw):
    """a, b: same length lists (None = missing: pair drop). Difference = b - a.
    verdict: improves / worsens (higher_is_better ke hisaab se) ya 'increases/decreases' (None), 'no clear difference'
    (CI 0 ko cover kare), 'too few pairs' (n < n_min)."""
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(pairs)
    out = {"n": n, "mean_a": mean([p[0] for p in pairs]), "mean_b": mean([p[1] for p in pairs]),
           "diff": None, "lo": None, "hi": None, "verdict": "no data"}
    if not n:
        return out
    diffs = [y - x for x, y in pairs]
    out["diff"] = statistics.mean(diffs)
    out["lo"], out["hi"] = bootstrap_ci(diffs, **kw)
    if n < n_min:
        out["verdict"] = "too few pairs"
    elif out["lo"] > 0:
        out["verdict"] = "increases" if higher_is_better is None else ("improves" if higher_is_better else "worsens")
    elif out["hi"] < 0:
        out["verdict"] = "decreases" if higher_is_better is None else ("worsens" if higher_is_better else "improves")
    else:
        out["verdict"] = "no clear difference"
    return out
