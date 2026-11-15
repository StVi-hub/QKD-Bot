"""Simulated BB84 against theory. Statistical checks use a 4σ tolerance, σ = √(q(1−q)/n)."""

from functools import cache

import numpy as np
import pytest

from qkd_bot.circuits import X, Z
from qkd_bot.protocol import run_bb84
from qkd_bot.theory import binomial_sigma

N = 200_000
SEED = 20261012


@cache
def _cached_run(f, lam, loss):
    return run_bb84(N, f=f, lam=lam, loss=loss, seed=SEED)


def run(f=0.0, lam=0.0, loss=0.0):
    """One shared run per parameter set. Positional, normalised arguments make run(f=1.0) and
    run(f=1.0, lam=0.0) hit the same cache entry."""
    return _cached_run(float(f), float(lam), float(loss))


def assert_within_4sigma(measured, expected, n):
    sigma = binomial_sigma(expected, n)
    assert abs(measured - expected) <= 4 * sigma, (
        f"measured {measured:.5f}, theory {expected:.5f}, 4σ = {4 * sigma:.5f} (n = {n})"
    )


def test_noiseless_qber_is_exactly_zero():
    # Any bit-order (register) mix-up would give a QBER near 1/2 here, not a small number.
    r = run()
    assert r.qber == 0.0
    assert np.array_equal(r.alice_key, r.bob_key)


def test_sifted_fraction_is_one_half():
    assert_within_4sigma(run().sifted_fraction, 0.5, N)


@pytest.mark.parametrize(
    "f, lam, expected",
    [(1.0, 0.0, 0.25), (0.4, 0.0, 0.10), (0.0, 0.1, 0.05), (0.4, 0.1, 0.14)],
)
def test_qber_matches_theory(f, lam, expected):
    r = run(f=f, lam=lam)
    assert_within_4sigma(r.qber, expected, r.alice_key.size)


@pytest.mark.parametrize("basis", [Z, X])
def test_depolarizing_qber_is_lambda_over_two_in_each_basis(basis):
    r = run(lam=0.1)
    errors = r.errors[r.key_bases == basis]
    assert_within_4sigma(errors.mean(), 0.05, errors.size)


def test_sacrificed_subset_estimates_the_qber():
    r = run(f=1.0)
    assert_within_4sigma(r.qber_estimate, 0.25, int(r.test_mask.sum()))


def test_loss_lowers_the_sifted_fraction_not_the_qber():
    r = run(loss=0.5)
    assert_within_4sigma(r.sifted_fraction, 0.25, N)
    assert r.qber == 0.0


def test_same_seed_gives_identical_output():
    a = run_bb84(20_000, f=0.4, lam=0.1, loss=0.2, seed=7)
    b = run_bb84(20_000, f=0.4, lam=0.1, loss=0.2, seed=7)
    assert np.array_equal(a.alice_key, b.alice_key)
    assert np.array_equal(a.bob_key, b.bob_key)
    assert np.array_equal(a.test_mask, b.test_mask)


def test_different_seed_gives_different_output():
    a = run_bb84(20_000, f=0.4, lam=0.1, seed=7)
    b = run_bb84(20_000, f=0.4, lam=0.1, seed=8)
    assert not np.array_equal(a.bob_key, b.bob_key)
