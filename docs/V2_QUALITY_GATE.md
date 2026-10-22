# V2 QUALITY CONTROL GATE SPECIFICATION & STANDARDS

## 1. Automated Verification Gates

Every video produced by AI Avatar NextGen V2 must pass through the automated `QualityControlGate` (`quality/qc_gate.py`) prior to final user presentation:

```
[Render Output] ──► [Container Integrity] ──► [Duration Alignment] ──► [Temporal Jitter] ──► [PASS / FAIL]
```

### Verification Criteria & Thresholds:

| Metric | Verification Standard | Failure Condition | Target Threshold |
| :--- | :--- | :--- | :--- |
| **Container & Decodability** | Video is valid MP4 with valid SPS/PPS headers | Corrupted frames, moov atom missing | 0 corrupted frames |
| **Resolution Integrity** | Vertical Full HD (1080×1920) or Native 720p+ | Wrong aspect ratio, pixel squashing | Exactly 1080×1920 (Broadcast) |
| **Frame Rate** | Constant frame rate (CFR) | Variable frame rate (VFR), dropped frames | 25.0 FPS $\pm 0.1$ or 60.0 FPS $\pm 0.1$ |
| **A/V Sync & Duration** | Duration difference between audio & video | Audio cut off, video lingering | $\Delta t \le 0.15\text{s}$ |
| **Temporal Stability** | Frame-to-frame pixel difference variance | High-frequency oral flickering / jitter | Jitter Score $\le 0.85$ (V2 target $<0.40$) |
| **Lip Closure on Bilabials** | Inter-lip gap on silent or /b, m, p/ frames | Open mouth during silence ("rubber mouth") | 100% complete seal |

---

## 2. Blind Human Acceptance Protocol

Before promoting any model checkpoint or pipeline configuration to Production Truth:
1. **Blind Side-by-Side Review:**
   Reviewers evaluate Condition A vs. Condition B without knowledge of the underlying engine names.
2. **Scoring Dimensions (1–5 scale):**
   - Naturalness of mouth & jaw motion (no synthetic elasticity).
   - Realism of teeth and tongue visibility.
   - Appropriateness of head tilt & eye movement to speech emotion.
   - Lack of visible mask compositing seams around the chin/cheeks.
   - Overall perceived human realism.
3. **Threshold for Promotion:**
   The candidate engine must score at least **+0.8 points higher** than the baseline average before any transition is authorized.

**GATE P7 STATUS: PASS**
