"""Stage 2: parameter sweeps -> results/*.json, then the three plots drawn FROM that JSON.

    python scripts/run_sweeps.py                # sweeps + plots (about 10 min at N = 10^6)
    python scripts/run_sweeps.py --plots-only   # redraw the PNGs from the existing JSON

Every sweep point is an independent run with its own seed, drawn from one master seed and
recorded next to the point, so the error bars are independent and any point can be rerun alone.
"""

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from qkd_bot import theory  # noqa: E402
from qkd_bot.protocol import detection_rate, run_bb84  # noqa: E402
from qkd_bot.provenance import provenance  # noqa: E402

SEED = 20261013
N = 1_000_000
TEST_FRACTION = 0.1
F_VALUES = [round(float(x), 2) for x in np.linspace(0, 1, 21)]
LAM_VALUES = [round(float(x), 3) for x in np.linspace(0, 0.3, 13)]
M_VALUES = list(range(1, 31))
DETECTION_TARGET = 0.999
RESULTS = Path(__file__).resolve().parents[1] / "results"

# Data in categorical slots 1-2 (a validated pair); everything else in neutral inks.
MEASURED, THEORY = "#2a78d6", "#eb6834"
INK, INK_2, MUTED, GRID, AXIS, SURFACE = (
    "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
)


# ---------------------------------------------------------------- statistics


def sigma(q, n):
    return float(theory.binomial_sigma(q, n))


def z_score(measured, expected, n):
    """(measured - theory) in units of the theory σ. An exact prediction (σ = 0) that is
    missed gives None, which is flagged like |z| > 4."""
    s = sigma(expected, n)
    if s == 0:
        return 0.0 if measured == expected else None
    return (measured - expected) / s


def fmt_z(z):
    return "exact prediction missed" if z is None else f"{z:+.2f}"


def beyond_4sigma(points, id_key, z_keys):
    """Every check beyond 4σ, as text. Reported, never adjusted."""
    return [
        f"{id_key} = {p[id_key]}: {key} = {fmt_z(p[key])}"
        for p in points
        for key in z_keys
        if p[key] is None or abs(p[key]) > 4
    ]


# ---------------------------------------------------------------- sweeps


def qber_sweep(param, values, seeds, n):
    """One independent BB84 run per value of `param` ("f" or "lam"); the other is zero."""
    points = []
    for value, seed in zip(values, seeds):
        run = run_bb84(n, seed=seed, test_fraction=TEST_FRACTION, **{param: value})
        expected = theory.expected_qber(**{param: value})
        n_sifted, n_test = run.alice_key.size, int(run.test_mask.sum())
        point = {
            param: value,
            "seed": seed,
            "n_sifted": n_sifted,
            "sifted_fraction": run.sifted_fraction,
            "sifted_fraction_sigma": sigma(run.sifted_fraction, n),
            "sifted_fraction_z": z_score(run.sifted_fraction, 0.5, n),
            "qber": run.qber,
            "qber_sigma": sigma(run.qber, n_sifted),
            "qber_theory": expected,
            "qber_z": z_score(run.qber, expected, n_sifted),
            "n_test": n_test,
            "qber_estimate": run.qber_estimate,
            "qber_estimate_sigma": sigma(run.qber_estimate, n_test),
            "qber_estimate_z": z_score(run.qber_estimate, expected, n_test),
        }
        points.append(point)
        print(
            f"  {param} = {value:<5}  QBER {run.qber:.5f} ± {point['qber_sigma']:.5f}"
            f"  theory {expected:.5f}  z {fmt_z(point['qber_z'])}"
        )
    return points


def fit_through_origin(points, param, slope_theory):
    """Weighted least squares for QBER = k·param, then the param value where QBER = Q*,
    i.e. where the key fraction reaches zero.

    Points with σ = 0 (param = 0: no errors at all) carry no slope information and are left out.
    """
    x = np.array([p[param] for p in points])
    q = np.array([p["qber"] for p in points])
    s = np.array([p["qber_sigma"] for p in points])
    use = s > 0
    w = 1 / s[use] ** 2
    k = np.sum(w * x[use] * q[use]) / np.sum(w * x[use] ** 2)
    k_sigma = 1 / np.sqrt(np.sum(w * x[use] ** 2))
    chi2 = np.sum(w * (q[use] - k * x[use]) ** 2)
    dof = int(use.sum()) - 1
    q_star = theory.qber_threshold()
    return {
        "model": f"QBER = k * {param}; weighted least squares; points with sigma = 0 excluded",
        "k": float(k),
        "k_sigma": float(k_sigma),
        "k_theory": slope_theory,
        "k_z": float((k - slope_theory) / k_sigma),
        "chi2": float(chi2),
        "dof": dof,
        "chi2_z": float((chi2 - dof) / math.sqrt(2 * dof)),  # normal approximation to χ²
        "zero_key_at": float(q_star / k),
        "zero_key_at_sigma": float(q_star * k_sigma / k**2),
        "zero_key_at_theory": q_star / slope_theory,
    }


def key_fraction_points(points, param):
    """r(Q) from each measured QBER, with the delta-method σ: |dr/dQ| = 2·log2((1 − Q)/Q),
    and 0 where r is clamped at zero."""
    out = []
    for p in points:
        q, q_sigma = p["qber"], p["qber_sigma"]
        r = float(theory.key_fraction(q))
        r_sigma = 2 * math.log2((1 - q) / q) * q_sigma if r > 0 and q > 0 else 0.0
        out.append({
            param: p[param],
            "qber": q,
            "qber_sigma": q_sigma,
            "key_fraction": r,
            "key_fraction_sigma": r_sigma,
            "key_fraction_theory": float(theory.key_fraction(p["qber_theory"])),
        })
    return out


def detection_sweep(n, seed, shuffle_seeds):
    """Full intercept-resend run; for each m the sifted key is cut into disjoint m-bit test
    sets and the fraction of sets containing at least one error is counted."""
    run = run_bb84(n, f=1.0, seed=seed, test_fraction=TEST_FRACTION)
    k = run.errors.size
    points = []
    for m, shuffle_seed in zip(M_VALUES, shuffle_seeds):
        draws = k // m
        p = detection_rate(run, m, draws, seed=shuffle_seed)
        expected = float(theory.p_detect(m))
        points.append({
            "m": m,
            "draws": draws,
            "shuffle_seed": shuffle_seed,
            "p_detect": p,
            "p_detect_sigma": sigma(p, draws),
            "p_detect_theory": expected,
            "z": z_score(p, expected, draws),
            # Below ~10 expected undetected sets the normal approximation behind z is rough.
            "expected_undetected_sets": draws * (1 - expected),
        })

    # m needed for the target: solve (1 - q)^m = 1 - target with the measured per-bit error q.
    q, q_sigma = run.qber, sigma(run.qber, k)
    log_miss = math.log(1 - DETECTION_TARGET)
    m_theory = log_miss / math.log(0.75)
    target = {
        "target": DETECTION_TARGET,
        "n_sifted": k,
        "per_bit_error": q,
        "per_bit_error_sigma": q_sigma,
        "per_bit_error_z": z_score(q, 0.25, k),
        "m_needed": log_miss / math.log(1 - q),
        "m_needed_sigma": abs(log_miss) / ((1 - q) * math.log(1 - q) ** 2) * q_sigma,
        "m_needed_theory": m_theory,
        "smallest_integer_m_theory": math.ceil(m_theory),
        "first_m_reaching_target_empirically": next(
            (p["m"] for p in points if p["p_detect"] >= DETECTION_TARGET), None
        ),
    }
    return points, target


# ---------------------------------------------------------------- JSON


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"  wrote {path}")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def run_sweeps(n, seed, out):
    meta = provenance(seed, n)  # taken before any file is written
    rng = np.random.default_rng(seed)
    f_seeds = [int(s) for s in rng.integers(0, 2**31, len(F_VALUES))]
    lam_seeds = [int(s) for s in rng.integers(0, 2**31, len(LAM_VALUES))]
    detection_seed = int(rng.integers(0, 2**31))
    shuffle_seeds = [int(s) for s in rng.integers(0, 2**31, len(M_VALUES))]
    q_star = theory.qber_threshold()
    common = {"generated_by": "scripts/run_sweeps.py", "provenance": meta}

    for param, values, seeds, slope, description in [
        ("f", F_VALUES, f_seeds, 0.25,
         "Sifted-key QBER vs intercept-resend fraction f (lambda = 0, no loss); theory f/4."),
        ("lam", LAM_VALUES, lam_seeds, 0.5,
         "Sifted-key QBER vs depolarizing lambda (no Eve, no loss); theory lambda/2."),
    ]:
        print(f"QBER vs {param}")
        points = qber_sweep(param, values, seeds, n)
        fit = fit_through_origin(points, param, slope)
        flags = beyond_4sigma(points, param, ["qber_z", "qber_estimate_z", "sifted_fraction_z"])
        flags += [f"fit: {key} = {fit[key]:+.2f}" for key in ("k_z", "chi2_z") if abs(fit[key]) > 4]
        name = "qber_vs_f" if param == "f" else "qber_vs_lambda"
        write_json(out / f"{name}.json", {
            "name": name,
            "description": description,
            **common,
            "parameters": {
                param: values,
                "loss": 0.0,
                "test_fraction": TEST_FRACTION,
                "qber_threshold": q_star,
                "seeds": "one per point, drawn from provenance.seed; recorded in each point",
            },
            "points": points,
            "fit": fit,
            "beyond_4sigma": flags,
        })

    # Derived purely from the two QBER files on disk.
    vs_f, vs_lam = load_json(out / "qber_vs_f.json"), load_json(out / "qber_vs_lambda.json")
    write_json(out / "key_fraction.json", {
        "name": "key_fraction",
        "description": (
            "Asymptotic secret key fraction r(Q) = max(0, 1 - 2 h2(Q)) (Shor-Preskill), computed "
            "from the measured QBER in qber_vs_f.json and qber_vs_lambda.json. Not a measured "
            "key rate. sigma by the delta method."
        ),
        **common,
        "derived_from": ["qber_vs_f.json", "qber_vs_lambda.json"],
        "parameters": {"qber_threshold": q_star},
        "vs_f": {"points": key_fraction_points(vs_f["points"], "f"), "fit": vs_f["fit"]},
        "vs_lambda": {"points": key_fraction_points(vs_lam["points"], "lam"), "fit": vs_lam["fit"]},
    })

    print("Detection vs m (f = 1)")
    points, target = detection_sweep(n, detection_seed, shuffle_seeds)
    flags = beyond_4sigma(points, "m", ["z"])
    if target["per_bit_error_z"] is None or abs(target["per_bit_error_z"]) > 4:
        flags.append(f"per-bit error: z = {fmt_z(target['per_bit_error_z'])}")
    write_json(out / "detection_vs_m.json", {
        "name": "detection_vs_m",
        "description": (
            "Full intercept-resend (f = 1, lambda = 0, no loss): empirical probability that m "
            "sacrificed sifted bits contain at least one error, against 1 - (3/4)^m."
        ),
        **common,
        "parameters": {
            "f": 1.0,
            "lam": 0.0,
            "loss": 0.0,
            "m": M_VALUES,
            "run_seed": detection_seed,
            "method": "per m, the sifted key is shuffled and cut into floor(K/m) disjoint m-bit sets",
        },
        "points": points,
        "m_for_target": target,
        "beyond_4sigma": flags,
    })


# ---------------------------------------------------------------- plots (from JSON only)


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.labelcolor": INK_2,
        "axes.titlecolor": INK,
        "axes.titlesize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": AXIS,
        "ytick.color": AXIS,
        "xtick.labelcolor": INK_2,
        "ytick.labelcolor": INK_2,
        "legend.frameon": False,
        "legend.fontsize": 8.5,
        "font.size": 9.5,
    })


def measured(ax, x, y, yerr, label):
    ax.errorbar(x, y, yerr=yerr, fmt="o", ms=5, color=MEASURED, elinewidth=1, capsize=0,
                mec=SURFACE, mew=0.8, label=label, zorder=3)


def footer(fig, data, filename):
    p = data["provenance"]
    commit = (p["git_commit"] or "unknown")[:7] + ("+dirty" if p["git_dirty"] else "")
    fig.text(0.01, 0.01, f"data: {filename} · commit {commit} · master seed {p['seed']} · "
             f"N = {p['n']:,} trials per run · error bars ±1σ",
             color=MUTED, fontsize=7.5, ha="left", va="bottom")


def plot_qber_vs_f(out):
    data = load_json(out / "qber_vs_f.json")
    pts, fit = data["points"], data["fit"]
    q_star = data["parameters"]["qber_threshold"]
    f = np.array([p["f"] for p in pts])
    q = np.array([p["qber"] for p in pts])
    s = np.array([p["qber_sigma"] for p in pts])
    z = np.array([p["qber_z"] for p in pts], dtype=float)

    fig, (ax, ax_z) = plt.subplots(2, 1, figsize=(7.2, 6.4), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08})
    grid = np.linspace(0, 1, 200)
    ax.plot(grid, grid / 4, color=THEORY, lw=1.6, label="theory: QBER = f/4", zorder=2)
    measured(ax, f, q, s, "simulation (error bars smaller than markers)")
    ax.axhline(q_star, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(0.99, q_star + 0.004, f"key fraction r = 0 above Q* = {q_star:.1%}", color=INK_2,
            fontsize=8.5, ha="right", transform=ax.get_yaxis_transform())
    f0, f0_sigma = fit["zero_key_at"], fit["zero_key_at_sigma"]
    ax.vlines(f0, 0, q_star, color=MUTED, lw=1, ls=(0, (1, 2)), zorder=1)
    ax.errorbar([f0], [q_star], xerr=[f0_sigma], fmt="D", ms=7, color=INK, mec=SURFACE,
                mew=0.8, zorder=4,
                label=f"r = 0 at f = {f0:.5f} ± {f0_sigma:.5f} (theory {fit['zero_key_at_theory']:.5f})")
    ax.set_ylabel("QBER on the sifted key")
    ax.set_ylim(0, 0.27)
    ax.set_title("QBER vs intercepted fraction f (intercept-resend, λ = 0, no loss)", loc="left")
    ax.legend(loc="upper left")

    ax_z.axhspan(-4, 4, color=GRID, alpha=0.6, lw=0, zorder=0)
    ax_z.axhline(0, color=AXIS, lw=0.8)
    ax_z.plot(f, z, "o", ms=4.5, color=MEASURED, mec=SURFACE, mew=0.8, zorder=3)
    ax_z.set_ylim(-max(5, np.nanmax(np.abs(z)) + 1), max(5, np.nanmax(np.abs(z)) + 1))
    ax_z.set_ylabel("(sim − theory) / σ")
    ax_z.set_xlabel("fraction of qubits intercepted, f")
    ax_z.text(0.01, 4.3, "±4σ", color=INK_2, fontsize=8, transform=ax_z.get_yaxis_transform())
    ax_z.set_xlim(-0.02, 1.02)
    footer(fig, data, "qber_vs_f.json")
    fig.subplots_adjust(left=0.11, right=0.98, top=0.94, bottom=0.12)
    fig.savefig(out / "qber_vs_f.png", dpi=150)
    plt.close(fig)


def plot_key_fraction(out):
    data = load_json(out / "key_fraction.json")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True)
    panels = [
        (axes[0], data["vs_f"], "f", "f", 4, "fraction of qubits intercepted, f (λ = 0)"),
        (axes[1], data["vs_lambda"], "lam", "λ", 2, "depolarizing parameter λ (no Eve)"),
    ]
    for ax, section, key, symbol, divisor, xlabel in panels:
        pts, fit = section["points"], section["fit"]
        x = np.array([p[key] for p in pts])
        grid = np.linspace(0, x.max(), 300)
        ax.plot(grid, theory.key_fraction(grid / divisor), color=THEORY, lw=1.6,
                label=f"theory r(Q) with Q = {symbol}/{divisor}", zorder=2)
        measured(ax, x, [p["key_fraction"] for p in pts], [p["key_fraction_sigma"] for p in pts],
                 "from simulated QBER")
        x0, x0_sigma = fit["zero_key_at"], fit["zero_key_at_sigma"]
        ax.axvline(x0, color=MUTED, lw=1, ls=(0, (1, 2)), zorder=1)
        room_on_right = x0 < 0.6 * x.max()  # put the label where the panel is empty
        ax.text(x0 + (0.015 if room_on_right else -0.015) * x.max(), 0.5 if room_on_right else 0.78,
                f"r = 0 at {symbol} = {x0:.5f} ± {x0_sigma:.5f}\n(theory {fit['zero_key_at_theory']:.5f})",
                color=INK_2, fontsize=8.5, ha="left" if room_on_right else "right")
        ax.set_xlabel(xlabel)
        ax.set_ylim(-0.03, 1.05)
        ax.legend(loc="upper right" if room_on_right else "lower left")
    axes[0].set_ylabel("asymptotic secret key fraction r(Q)")
    fig.suptitle("Asymptotic secret key fraction (computed from measured QBER)",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.text(0.01, 0.905, "r(Q) = max(0, 1 − 2·$h_2$(Q)) (Shor–Preskill, one-way EC + PA) evaluated "
             "at each simulated QBER: a bound computed from data, not a measured key rate.",
             color=INK_2, fontsize=8.5, ha="left")
    footer(fig, data, "key_fraction.json")
    fig.subplots_adjust(left=0.07, right=0.98, top=0.85, bottom=0.17, wspace=0.06)
    fig.savefig(out / "key_fraction.png", dpi=150)
    plt.close(fig)


def plot_detection(out):
    data = load_json(out / "detection_vs_m.json")
    pts, target = data["points"], data["m_for_target"]
    m = np.array([p["m"] for p in pts])
    p_det = np.array([p["p_detect"] for p in pts])
    s = np.array([p["p_detect_sigma"] for p in pts])
    draws = np.array([p["draws"] for p in pts])
    grid = np.linspace(1, m.max(), 300)
    m_need, m_need_sigma = target["m_needed"], target["m_needed_sigma"]

    fig, (ax, ax_log) = plt.subplots(1, 2, figsize=(10, 4.6))
    ax.plot(grid, 1 - 0.75**grid, color=THEORY, lw=1.6, label="theory 1 − (3/4)$^m$", zorder=2)
    measured(ax, m, p_det, s, "simulation: disjoint m-bit test sets")
    ax.axhline(target["target"], color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(1, target["target"] - 0.035, f"{target['target']:.1%}", color=INK_2, fontsize=8.5)
    ax.set_xlabel("sacrificed sifted bits, m")
    ax.set_ylabel("P(at least one error revealed)")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="lower right")

    miss = 1 - p_det
    seen = miss > 0
    ax_log.plot(grid, 0.75**grid, color=THEORY, lw=1.6, label="theory (3/4)$^m$", zorder=2)
    measured(ax_log, m[seen], miss[seen], [np.minimum(s[seen], 0.9 * miss[seen]), s[seen]],
             "simulation")
    if (~seen).any():
        ax_log.plot(m[~seen], 1 / draws[~seen], "v", ms=6, mfc=SURFACE, mec=MEASURED,
                    label="no undetected set seen (marker at 1/sets)", zorder=3)
    ax_log.axhline(1 - target["target"], color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    ax_log.axvline(m_need, color=MUTED, lw=1, ls=(0, (1, 2)), zorder=1)
    ax_log.text(m_need - 0.4, 0.3,
                f"P(unnoticed) = {1 - target['target']:.1%} at\nm = {m_need:.2f} ± {m_need_sigma:.2f}\n"
                f"(theory {target['m_needed_theory']:.2f}: m ≥ {target['smallest_integer_m_theory']} bits)",
                color=INK_2, fontsize=8.5, ha="right")
    ax_log.set_yscale("log")
    ax_log.set_xlabel("sacrificed sifted bits, m")
    ax_log.set_ylabel("P(Eve unnoticed)")
    ax_log.legend(loc="lower left")
    fig.suptitle("Detecting full intercept-resend with m sacrificed bits",
                 x=0.01, ha="left", fontsize=11, color=INK)
    footer(fig, data, "detection_vs_m.json")
    fig.subplots_adjust(left=0.07, right=0.98, top=0.9, bottom=0.17, wspace=0.25)
    fig.savefig(out / "detection_vs_m.png", dpi=150)
    plt.close(fig)


def make_plots(out):
    style()
    for plot in (plot_qber_vs_f, plot_key_fraction, plot_detection):
        plot(out)
    print(f"  plots written to {out}")


def main():
    parser = argparse.ArgumentParser(description="BB84 parameter sweeps and plots.")
    parser.add_argument("--n", type=int, default=N, help="trials per run")
    parser.add_argument("--seed", type=int, default=SEED, help="master seed")
    parser.add_argument("--out", type=Path, default=RESULTS, help="output directory")
    parser.add_argument("--plots-only", action="store_true", help="redraw from existing JSON")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.plots_only:
        run_sweeps(args.n, args.seed, args.out)
    make_plots(args.out)


if __name__ == "__main__":
    main()
