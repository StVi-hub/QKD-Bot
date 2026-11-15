"""The Qiskit Aer behaviour that the seeding in protocol.run_bb84 relies on (theory.md §6.5)."""

import numpy as np
from qiskit import transpile
from qiskit_aer import AerSimulator

from qkd_bot.circuits import X, Z, bb84_circuit, read_register


def test_aer_seeds_shot_i_with_seed_plus_i():
    # run_bb84 gives its Aer jobs disjoint seed ranges because of this behaviour. If an Aer
    # upgrade changes it, revisit the seeding in protocol.py.
    circuit = bb84_circuit(0, Z, X, Z)  # Eve in the wrong basis: Bob's bit is a fair coin
    simulator = AerSimulator(method="stabilizer")
    compiled = transpile(circuit, simulator, optimization_level=0)

    def bob_bits(seed):
        job = simulator.run(compiled, shots=1_000, memory=True, seed_simulator=seed)
        return read_register(job.result().get_memory(), circuit, "bob")

    base = 2**62
    assert np.array_equal(bob_bits(base)[1:], bob_bits(base + 1)[:-1])  # same stream, shifted
    assert not np.array_equal(bob_bits(base), bob_bits(base + 2**32))  # seeds not truncated
