# QKD-Bot — Quantum-Secured Robotic Commands

> **MVP landing September 2026.** Development begins mid-late August 2026.

Classical cryptography rests on mathematical hardness: we believe factoring large numbers is
too slow to break RSA. Quantum key distribution rests on physical law instead — measuring a
quantum system unavoidably disturbs it, so an eavesdropper cannot listen without leaving
evidence.

QKD-Bot applies that to robotics. A ground station and a robot establish a shared key using the
BB84 protocol; an active eavesdropper is not merely *suspected* but **provably detected** by the
error rate she is forced to introduce — and the robot refuses to act on commands it can no
longer trust.

## Part of a three-project system

| Project | Role |
|---|---|
| [Neural-Edge](https://github.com/StVi-Hub/Neural-Edge) | Adaptive perception under power and thermal limits |
| [Aether-Link](https://github.com/StVi-Hub/Aether-Link) | Deterministic telemetry transport |
| **QKD-Bot** (this repo) | Quantum-secured command channel |

This project secures the command path for the perception and telemetry stack: a rescue robot
that cannot be hijacked mid-mission.

## Core technologies

- **Quantum simulation:** Qiskit
- **Language:** Python
- **Orchestration:** Docker Compose — Alice, Bob, and Eve as separate containers
- **Channels:** WebSocket (simulated quantum channel with configurable loss and noise),
  UDP (classical reconciliation channel)
- **Symmetric crypto:** AES-GCM, keyed from the sifted quantum key

## Roadmap to MVP

### Phase 1 — BB84 core
- [ ] Single-process BB84: random bit and basis preparation, random-basis measurement, sifting
      on matching bases, QBER estimation over a sacrificed subset
- [ ] **Target tests:** with no eavesdropper, QBER approximates channel noise; under
      intercept-resend, QBER approaches 25 percent — the signature the no-cloning theorem
      forces on any attacker who must guess a measurement basis

### Phase 2 — Networked nodes
- [ ] Alice and Bob split into containers communicating over the two channels
- [ ] Simulated lossy quantum channel modelling fibre decoherence with configurable parameters
- [ ] Key-sifting engine as its own module: basis reconciliation, parity-block error estimation,
      and an explicit key accept/discard policy

### Phase 3 — Adversary and fail-safe
- [ ] Eve container performing intercept-resend, toggled by a Compose profile
- [ ] QBER above threshold triggers key rejection and puts the robot into a logged fail-safe
- [ ] Mock actuator commands authenticated with AES-GCM under the derived key — QKD distributes
      the key, symmetric crypto does the work, as in real deployments
- [ ] **Target plots:** QBER versus channel loss, and QBER with and without an active
      eavesdropper

## Definition of done

`docker compose up` exchanges and verifies a key between the two nodes. Running with
`--profile eve` spikes the QBER, logs the detection, and trips the fail-safe. Tests pass in CI.

## Current status

Theory and design phase. Implementation begins mid-late August 2026.

## Planned extensions (winter 2026–27)

Cascade error correction, privacy amplification via universal hashing, the E91 entanglement-based
protocol, ROS2 Humble integration with a key-manager lifecycle node signing actuator packets, and
a latency-overhead benchmark against an OpenSSL baseline.
