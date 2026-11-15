"""One BB84 run: sample trials, simulate each distinct circuit once, sift, estimate the QBER."""

import itertools
from dataclasses import dataclass

import numpy as np
from qiskit import transpile
from qiskit_aer import AerSimulator

from .circuits import NO_EVE, X, Z, bb84_circuit, read_register

# Every possible (alice_bit, alice_basis, eve_basis, bob_basis): 2·2·3·2 = 24.
CONFIGURATIONS = list(itertools.product((0, 1), (Z, X), (NO_EVE, Z, X), (Z, X)))


@dataclass(frozen=True)
class BB84Run:
    n: int
    f: float
    lam: float
    loss: float
    seed: int
    alice_key: np.ndarray  # sifted key, Alice's copy
    bob_key: np.ndarray  # sifted key, Bob's copy
    key_bases: np.ndarray  # basis of each sifted bit (announced publicly during sifting)
    test_mask: np.ndarray  # True at sifted positions sacrificed to estimate the QBER

    @property
    def sifted_fraction(self):
        return self.alice_key.size / self.n

    @property
    def errors(self):
        return self.alice_key != self.bob_key

    @property
    def qber(self):
        """Error rate over the whole sifted key — knowable only because this is a simulation."""
        return float(self.errors.mean())

    @property
    def qber_estimate(self):
        """Error rate over the sacrificed test bits — what Alice and Bob can actually observe."""
        return float(self.errors[self.test_mask].mean())


def run_bb84(n, f=0.0, lam=0.0, loss=0.0, seed=0, test_fraction=0.1):
    """Simulate n BB84 trials with intercept-resend on a fraction f, depolarizing λ and loss L."""
    rng = np.random.default_rng(seed)

    # 1. Sample every trial's configuration. All draws happen regardless of f and loss, so the
    #    same seed gives the same Alice bits and bases across a parameter sweep.
    alice_bits = rng.integers(0, 2, n)
    alice_bases = rng.integers(0, 2, n)
    bob_bases = rng.integers(0, 2, n)
    eve_bases = np.where(rng.random(n) < f, rng.integers(0, 2, n), NO_EVE)
    lost = rng.random(n) < loss
    configs = np.column_stack([alice_bits, alice_bases, eve_bases, bob_bases])

    # 2–4. Group trials by configuration, run each circuit once with one shot per trial, and
    #      scatter Bob's outcomes back.
    simulator = AerSimulator(method="stabilizer")
    circuits = [bb84_circuit(*config, lam=lam) for config in CONFIGURATIONS]
    # One transpile call for all circuits: Aer rebuilds its target on every call (~0.5 s).
    # optimization_level=0 keeps the explicit noise instruction in place.
    compiled = transpile(circuits, simulator, optimization_level=0)
    # Aer seeds shot i of a job with seed_simulator + i, so two jobs whose ranges
    # [seed, seed + shots) overlap replay the same random numbers. The jobs therefore get
    # consecutive, disjoint ranges from one random 62-bit base: no two shots of a run share a
    # seed, and two runs collide with probability ~ 2n / 2^62.
    next_seed = int(rng.integers(0, 2**62))
    bob_bits = np.zeros(n, dtype=np.uint8)
    for config, circuit, compiled_circuit in zip(CONFIGURATIONS, circuits, compiled):
        trials = np.flatnonzero((configs == config).all(axis=1) & ~lost)  # lost: never reaches Bob
        if trials.size == 0:
            continue
        job = simulator.run(
            compiled_circuit, shots=trials.size, memory=True, seed_simulator=next_seed
        )
        next_seed += trials.size
        bob_bits[trials] = read_register(job.result().get_memory(), circuit, "bob")

    # Sifting: keep the detected trials where Bob happened to measure in Alice's basis.
    sifted = ~lost & (alice_bases == bob_bases)
    alice_key = alice_bits[sifted].astype(np.uint8)
    bob_key = bob_bits[sifted]

    # Each sifted bit is independently sacrificed (publicly compared) w.p. test_fraction.
    test_mask = rng.random(alice_key.size) < test_fraction

    return BB84Run(n, f, lam, loss, seed, alice_key, bob_key, alice_bases[sifted], test_mask)


def detection_rate(run, m, draws, seed=0):
    """Empirical P(at least one error among m sacrificed bits).

    The sifted key is shuffled and cut into `draws` disjoint blocks of m bits. Disjoint blocks
    are independent, so the binomial σ for `draws` samples is the honest uncertainty.
    """
    if draws * m > run.errors.size:
        raise ValueError(f"need {draws * m} sifted bits, have {run.errors.size}")
    rng = np.random.default_rng(seed)
    blocks = rng.permutation(run.errors)[: draws * m].reshape(draws, m)
    return float(blocks.any(axis=1).mean())
