"""Detecting a full intercept-resend attack from a small sacrificed sample."""

from qkd_bot.protocol import detection_rate, run_bb84
from qkd_bot.theory import binomial_sigma

SEED = 20261012


def test_full_eve_goes_unnoticed_in_ten_test_bits_with_prob_three_quarters_to_the_tenth():
    run = run_bb84(400_000, f=1.0, seed=SEED)
    m = 10
    draws = run.errors.size // m  # every sifted bit used once, in disjoint m-bit blocks
    p_unnoticed = 1 - detection_rate(run, m=m, draws=draws, seed=SEED)
    expected = 0.75**m  # ≈ 0.0563
    sigma = binomial_sigma(expected, draws)
    assert abs(p_unnoticed - expected) <= 4 * sigma, (
        f"measured {p_unnoticed:.5f}, theory {expected:.5f}, 4σ = {4 * sigma:.5f}"
    )
