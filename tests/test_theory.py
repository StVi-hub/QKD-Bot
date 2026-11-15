"""Closed-form values from the CLAUDE.md theory table."""

import pytest

from qkd_bot import theory


def test_binary_entropy_is_one_bit_at_one_half():
    assert theory.h2(0.5) == pytest.approx(1.0)


def test_binary_entropy_is_zero_for_a_certain_outcome():
    assert theory.h2(0.0) == 0.0
    assert theory.h2(1.0) == 0.0


def test_key_fraction_is_one_without_errors():
    assert theory.key_fraction(0.0) == pytest.approx(1.0)


def test_key_fraction_reaches_zero_at_eleven_percent():
    q = theory.qber_threshold()
    assert q == pytest.approx(0.1100, abs=1e-4)
    assert theory.h2(q) == pytest.approx(0.5)
    assert theory.key_fraction(q) == pytest.approx(0.0, abs=1e-9)


def test_max_tolerable_interception_noiseless():
    assert theory.f_max() == pytest.approx(0.44, abs=1e-3)


def test_full_eve_unnoticed_by_24_test_bits():
    assert theory.p_undetected(24) == pytest.approx(0.001, abs=1e-4)


@pytest.mark.parametrize(
    "f, lam, qber",
    [(1.0, 0.0, 0.25), (0.4, 0.0, 0.10), (0.0, 0.1, 0.05), (0.4, 0.1, 0.14)],
)
def test_expected_qber_matches_table(f, lam, qber):
    assert theory.expected_qber(f, lam) == pytest.approx(qber)
