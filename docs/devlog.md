# Development log

Engineering record for QKD-Bot: what was built, the decisions behind it, and every problem found,
with its cause and how it was resolved. Oldest entry first. Derivations and the full analysis are
in [theory.md](theory.md) (cited below as §); results and limits are in the [README](../README.md).

---

## 2026-10-12 — Core simulation and tests

**Work**
- `theory.py` holds the closed forms: binary entropy, the Shor–Preskill key fraction, the 11.00 %
  threshold (by bisection), the expected QBER with Eve and noise, *f*_max, the detection
  probability and the binomial σ.
- `circuits.py` builds the one-qubit circuit for a single trial: Alice → optional intercept-resend
  Eve → depolarizing channel → Bob.
- `protocol.py` simulates each of the ≤ 24 distinct trial configurations once, with one shot per
  trial, then applies loss, sifting, and a sacrificed test subset for the QBER estimate.
- Tests use 4σ tolerances, with σ computed from the theoretical value. Exact checks cover the
  noiseless QBER (exactly zero, with and without loss).

**Decisions**
- **Qiskit Aer's stabilizer simulator.** Every state, gate, measurement and noise process in BB84 is
  a stabilizer operation (§4.5).
- **Trials grouped by configuration**, rather than simulated one at a time. This is exact for
  i.i.d. trials and fast at 10⁶ trials (§4.1).
- **Depolarizing noise as Aer's `depolarizing_error` instruction**, used only after reading its
  source to confirm the parameter convention.
- **Eve's classical register declared in every circuit**, so a bit-order mix-up makes the noiseless
  QBER ≈ 1/2 instead of passing silently.

**Issues**
- *Bit order (§6.1).* Aer lists the last-declared register first, so reading "the last character"
  would return Eve's bit as Bob's. Results are read by register name.
- *Depolarizing convention (§6.2).* Two parameterisations are in use, and mixing them up shifts the
  QBER by a factor of 3/4 or 4/3. Aer's matches ρ → (1 − λ)ρ + λ·I/2, so no rescaling is needed.
- *Transpile cost (§6.3).* 24 separate `transpile` calls took 70 % of the run time. A single call is
  3.4× faster, with bit-identical output.
- *A 2.6σ deviation (§6.4).* Rerunning at 10⁶ trials with three seeds showed no bias. It was treated
  as a fluctuation, and nothing was changed.

**Environment:** Python 3.11.9, Qiskit 2.5.2, Qiskit Aer 0.17.2 and NumPy 2.4.6, in a repo-local
virtual environment.

## 2026-10-13 — Parameter sweeps, provenance and plots

**Work**
- `provenance.py` stamps every result file with:
  - the git commit, and a dirty flag for uncommitted changes to `src/`, `scripts/` or
    `pyproject.toml`
  - the Python, Qiskit, Aer and NumPy versions, and the platform
  - a UTC timestamp, the seed and N
- `scripts/run_sweeps.py` produces 64 sweep points, each evaluated on 10⁶ trials, from 35 runs:
  - QBER vs *f*: 21 points, one independent run each
  - QBER vs λ: 13 points, one independent run each
  - detection probability vs *m*, *m* = 1 … 30: all on one full-intercept-resend run

  Each point records its measured value, σ and z against theory. Anything beyond 4σ is written
  to a `beyond_4sigma` list. The plots are drawn from the JSON files only.
- theory.md gains a Results section (§7), and each theory row now links to the plot that validates
  it.

**Decisions**
- **An independent, recorded seed for every QBER sweep point**, all derived from one master seed. A
  shared seed would make the curves smoother, but it correlates the points and invalidates the σ
  and χ² of any fit across them.
- **The f at zero key fraction comes from a weighted fit** of QBER = k·f over the 20 points with
  errors, not from interpolating between two points. χ² tests the linear model.
- **The m for 99.9 % detection comes from the measured per-bit error rate** (500 247 sifted bits).
  The empirical detection curve alone cannot separate *m* = 24 from *m* = 25: they differ by about
  1σ.
- **Detection is estimated over disjoint test sets**, so the sets are independent and the binomial
  σ is valid.

**Issue: Aer's per-shot seeding made sweep points share random numbers (§6.5)**
- *Symptom.* The fit across the f sweep gave χ² = 8.0 for 19 degrees of freedom (lower tail
  ≈ 1 %). No single point was off; the points scattered too little.
- *Cause.* Aer seeds shot *i* of a job with `seed_simulator + i`. Per-circuit seeds were drawn from
  [0, 2³¹), so 9 pairs of jobs in different sweep points had overlapping seed ranges, sharing up to
  77 014 shots.
- *Ruled out.* Shots within one job are independent: variance ratios and autocorrelations over
  10⁶ shots stayed within |z| ≤ 2.2.
- *Fix.* Each run now gives its jobs consecutive, disjoint seed ranges from one random 62-bit base.
  A regression test pins down the Aer behaviour this relies on.
- *Verification.* The full sweep was regenerated, and a replay of all 35 runs' seed ranges finds no
  overlap. The same fit now gives χ² = 15.0 for 19 degrees of freedom. No result was adjusted.

**Outcome:** no check beyond 4σ. Across the 64 sweep points, the largest deviation of the measured
quantity (QBER or detection probability) is 2.0σ (|z| = 2.04, QBER at λ = 0.15). Including the
secondary checks, the largest is 2.7σ (|z| = 2.74, sifted fraction at λ = 0.2).

## 2026-10-14 — README rewritten; results reproduced on a clean commit

**Work**
- README rewritten to the MVP scope. It now has a Results section (the three plots, and headline
  numbers with uncertainties, each with its source JSON), Limits, Core technologies and a completed
  roadmap. Networking, containers, AES-GCM and fail-safe logic moved to Planned extensions.
- theory.md: the sifting row now also cites the sifted fractions recorded at every sweep point.

**Reproducibility check.** With the sweep code committed and the tree clean,
`scripts/run_sweeps.py` was run again. All four JSON files matched the previous run except for
three provenance lines per file (`git_commit`, `git_dirty`, `created_utc`), confirmed with
`git diff`. Same seeds, same numbers.

## 2026-10-25 — Documentation complete

- Added this development log, covering the work since 2026-10-12.
- README: the Results section no longer hard-codes a commit hash. The `provenance` block of each
  `results/*.json` names the commit that produced it, and that block is the authoritative record.
- Checked all 34 numbers quoted in the README against the JSON fields they come from: value,
  uncertainty and rounding. All match.
- Tests: the check that pins Aer's per-shot seeding moved from `test_protocol.py` to its own file,
  `tests/test_aer_seeding.py`. This separates the 23 checks against theory from the one check of
  simulator behaviour. The test code itself is unchanged.

**Status:** the MVP scope is complete. Planned extensions are listed in the README; none has been
started.

## 2026-11-15 — Results descriptions made precise

- The README, theory.md and this log now describe the 64 sweep points exactly. They are 34
  independent QBER runs, plus the detection probability at 30 values of *m* evaluated on one run.
  The earlier text said "each sweep point is an independent run", which was not true of the
  detection points.
- The largest deviation is reported in two parts:
  - **2.0σ** for the measured quantity at the 64 points, the QBER or the detection probability
  - **2.7σ** including the secondary checks, the sifted fraction and the sacrificed-subset estimate

  Earlier text gave only the second figure.
- No code and no result changed.
