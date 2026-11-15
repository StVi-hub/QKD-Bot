"""Closed-form BB84 predictions that the simulation is validated against.

Nothing here touches Qiskit: these are the independent theory values.
"""

import numpy as np


def h2(q):
    """Binary entropy in bits, with 0·log 0 = 0 so that h2(0) = h2(1) = 0."""
    q = np.asarray(q, dtype=float)
    total = np.zeros_like(q)
    for p in (q, 1 - q):
        total -= p * np.log2(p, where=p > 0, out=np.zeros_like(p))
    return total


def key_fraction(q):
    """Asymptotic secret key fraction r(Q) = max(0, 1 - 2·h2(Q)) (Shor–Preskill).

    One h2(Q) pays for error correction, the other for privacy amplification.
    Meaningful for 0 <= Q <= 1/2.
    """
    return np.maximum(0.0, 1 - 2 * h2(q))


def qber_threshold(tol=1e-12):
    """The QBER at which r(Q) reaches 0, i.e. the root of h2(Q) = 1/2 in (0, 1/2). ≈ 0.1100."""
    lo, hi = 0.0, 0.5  # 1 - 2·h2 is +1 at Q = 0 and -1 at Q = 1/2, decreasing in between
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if 1 - 2 * h2(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def expected_qber(f=0.0, lam=0.0):
    """QBER on the sifted key with intercept-resend on a fraction f and depolarizing λ.

    f/4 from Eve, λ/2 from the channel, minus f·λ/4: when Eve picked the wrong basis the bit
    is already random, so the noise cannot make it any worse.
    """
    return f / 4 + lam / 2 - f * lam / 4


def f_max(lam=0.0):
    """Largest interception fraction f that still leaves a positive key fraction.

    Solves expected_qber(f, lam) = qber_threshold() for f. Noiseless: 4 × 0.1100 ≈ 0.44.
    """
    f = (4 * qber_threshold() - 2 * lam) / (1 - lam)
    return float(np.clip(f, 0.0, 1.0))


def expected_sifted_fraction(loss=0.0):
    """Fraction of sent qubits kept after sifting: detected (1 - L) and bases match (1/2)."""
    return (1 - loss) / 2


def p_undetected(m, q=0.25):
    """Probability that m sacrificed bits show no error when each is wrong w.p. q.

    q = 1/4 is full intercept-resend: (3/4)^m.
    """
    return (1 - q) ** m


def p_detect(m, q=0.25):
    """Probability that at least one of m sacrificed bits reveals an error."""
    return 1 - p_undetected(m, q)


def binomial_sigma(q, n):
    """Standard deviation of an estimated proportion q from n independent samples."""
    return np.sqrt(q * (1 - q) / n)
