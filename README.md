# QKD-Bot — A Simulation Study of BB84 and Intercept-Resend Detection

> **MVP landing September 2026.** Development begins mid-late August 2026.

Classical key exchange rests on computational hardness — we assume factoring large numbers is
too slow to break RSA. Quantum key distribution rests on a different assumption: that measuring
a quantum system disturbs it, so an eavesdropper on the quantum channel is forced to introduce
errors the legitimate parties can detect statistically.

This project implements and studies that mechanism in simulation. Alice and Bob run the BB84
protocol over a modelled lossy channel; an intercept-resend attacker drives the quantum bit
error rate toward its predicted 25% signature, which the parties detect and respond to by
discarding the key.

## Scope — what this is and is not

**This is a simulation study.** There is no optical hardware and no physical quantum channel.
The channel is a software model: qubit states, a configurable loss and noise model, and a
simulated measurement. The no-cloning theorem is therefore **modelled, not demonstrated** — the
project studies the protocol's error statistics and detection behaviour, not the physics itself.

Real QKD deployments require dedicated optical hardware and a fibre or line-of-sight link.
Nothing here claims otherwise, and no application to mobile or field systems is implied.

What the project does offer: a working implementation of basis reconciliation and QBER
estimation, a reproducible attacker model, and measured error statistics compared against
theoretical predictions.

## Core technologies

- **Quantum simulation:** Qiskit
- **Language:** Python
- **Orchestration:** Docker Compose — Alice, Bob and Eve as separate containers
- **Channels:** WebSocket carrying the simulated quantum states (configurable loss and noise),
  UDP for classical reconciliation
- **Symmetric crypto:** AES-GCM, keyed from the sifted key

## Roadmap to MVP

### Phase 1 — BB84 core
- [ ] Single-process BB84: random bit and basis preparation, random-basis measurement, sifting
      on matching bases, QBER estimation over a sacrificed subset
- [ ] **Target tests:** with no attacker, measured QBER matches the configured channel noise;
      under intercept-resend, QBER approaches the theoretical 25% — Eve guesses the wrong basis
      half the time, and half of those corrupt the bit

### Phase 2 — Distributed nodes
- [ ] Alice and Bob split into containers communicating over the two channels
- [ ] Configurable loss and noise model on the simulated quantum channel
- [ ] Key-sifting engine as its own module: basis reconciliation, parity-block error estimation,
      and an explicit key accept/discard policy

### Phase 3 — Attacker and evaluation
- [ ] Eve container performing intercept-resend, toggled by a Compose profile
- [ ] QBER above threshold triggers key rejection, logged
- [ ] AES-GCM keyed from the sifted key, demonstrating the standard pairing — QKD distributes a
      symmetric key, symmetric crypto does the encryption
- [ ] **Target plots:** QBER versus channel loss, and QBER with and without an active attacker,
      measured against theoretical predictions

## Definition of done

`docker compose up` exchanges and verifies a key between the two nodes. Running with
`--profile eve` raises the QBER above threshold, logs the detection, and rejects the key.
Measured QBER curves are compared against theory. Tests pass in CI.

## Current status

Theory and design phase. Implementation begins mid-late August 2026.

## Planned extensions (winter 2026–27)

Cascade error correction, privacy amplification via universal hashing, the E91
entanglement-based protocol, and a comparison of measured key rates against published
theoretical bounds.
