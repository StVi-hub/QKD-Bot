"""The one-qubit circuit for a single BB84 trial.

A trial is fully specified by (alice_bit, alice_basis, eve_basis, bob_basis), so a run of
N trials needs at most 2·2·3·2 = 24 distinct circuits.
"""

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit_aer.noise import depolarizing_error

Z, X = 0, 1  # basis labels
NO_EVE = -1  # eve_basis value for a qubit Eve does not intercept


def bb84_circuit(alice_bit, alice_basis, eve_basis, bob_basis, lam=0.0):
    """Alice prepares → [Eve measures and resends] → depolarizing channel → Bob measures.

    Both classical registers are always declared, so every circuit has the same layout;
    Eve's bit stays 0 when she does not intercept.
    """
    eve = ClassicalRegister(1, "eve")
    bob = ClassicalRegister(1, "bob")
    qc = QuantumCircuit(QuantumRegister(1, "q"), eve, bob)

    # Alice: |0>/|1> in Z, and H turns them into |+>/|-> for X.
    if alice_bit:
        qc.x(0)
    if alice_basis == X:
        qc.h(0)

    # Eve: measuring in X is H, Z-measure, H. The measurement collapses the qubit into the
    # basis state she observed, which is exactly what she would resend — no reset needed.
    if eve_basis != NO_EVE:
        if eve_basis == X:
            qc.h(0)
        qc.measure(0, eve[0])
        if eve_basis == X:
            qc.h(0)

    # Channel: ρ -> (1 - λ)ρ + λ·I/2. Aer's depolarizing_error uses this same convention.
    if lam > 0:
        qc.append(depolarizing_error(lam, 1), [0])

    if bob_basis == X:
        qc.h(0)
    qc.measure(0, bob[0])
    return qc


def read_register(memory, circuit, name):
    """Extract one named 1-bit register from Aer's per-shot memory strings.

    Aer writes registers space-separated with the last-declared register first
    (little-endian), e.g. "b e" for (eve, bob). Look the position up by name, never assume it.
    """
    column = [reg.name for reg in reversed(circuit.cregs)].index(name)
    return np.array([int(shot.split(" ")[column]) for shot in memory], dtype=np.uint8)
