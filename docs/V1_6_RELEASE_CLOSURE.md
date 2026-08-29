# AI Avatar Studio V1.6.0 — Release Closure

**Release tag:** `ai-avatar-studio-ui-v1.6.0` (annotated)
**Release commit:** see tag `ai-avatar-studio-ui-v1.6.0`
**Target repository:** `https://github.com/thangngny/AI_Avatar.git`
**Date:** 2026-08-29

> This report deliberately does not embed the release commit's own SHA, to avoid a
> self-referential second commit. The annotated tag points at the single V1.6
> release commit.

---

## Release Status

`V1_6_RELEASED_TO_GITHUB` (see the final classification in the release task).

This is the final V1.6.0 release closure. It builds on the V1.5.0 release commit
(`788cbf5`, tag `ai-avatar-studio-ui-v1.5.0`) and adds the V1.6 work as one release
commit plus an annotated tag, then pushes the existing local history to the user's
GitHub repository.

---

## Human Review

- **Human UI Review:** `PASS` (user-confirmed; screenshots reviewed by the human).
- **Evidence label:** `HUMAN_REVIEW_REQUIRED` portions (visual screenshots) were
  reviewed by the human, not by the coding model. The model cannot view images on
  this session and did not claim to.

---

## Runtime Hardening

- **Status:** `HARDENED_AND_REAL_ACCEPTED`
- **Evidence:** `PROVEN_REAL` for code-drift detection, restart-required detection,
  browser restart warning, unknown-port-owner protection, active-job restart block,
  contract mismatch (backend + browser), controlled restart, and boot-id rotation.
- **Details:** `docs/V1_6_RUNTIME_DEPLOYMENT_HARDENING.md`,
  `docs/V1_6_RUNTIME_HARDENING_REAL_ACCEPTANCE.md`.
- **Single instance, canonical-runtime enforcement, safe restart orchestrator, and
  post-start smoke** are all in place and verified against the live server.

---

## Voice / Preview Workflow

- Vietnamese voice profiles and ElevenLabs matching (`eleven_v3`), Edge TTS fallback,
  two-voice lock, language resolver, and script voice preview are implemented and
  tested.
- Static voice sample playback and download were fixed (root cause documented in
  `docs/V1_6_STATIC_VOICE_SAMPLE_PLAYBACK_ROOT_CAUSE.md`).
- **No voice profile, TTS model, or sample was regenerated for this release.** Voice
  / TTS settings are unchanged from the committed V1.6 candidate.

---

## Management Safety

Management Safety Core controls are implemented and tested (see
`docs/V1_6_MANAGEMENT_SAFETY_CORE_IMPLEMENTATION.md` and
`docs/V1_6_PRE_MANAGEMENT_FEATURE_AUDIT.md`). Activity logging and owner-direct
gating are in place.

---

## Testing

- **Full regression:** `173 OK, 1 skipped` (no failures, no errors). The single
  skip is a documented/environmental skip, not a regression.
- **Preserved suites:** runtime hardening, Two-Voice Lock, Language Resolver,
  Management Safety, Script Voice Preview, audio download, Studio runtime, and
  Production Truth.
- No ElevenLabs quota and no GPU render were consumed for this release validation.

---

## Production Truth

- **SHA1:** `a5a0e55f46c29c1722efc5cc3f8fec3d902260f0`
- **Status:** `VALID` — unchanged across the entire release. Not modified by any
  release-cleanup step.

---

## Security / Secret Scan

- `.env` (containing the real ElevenLabs key) is gitignored, untracked, and never in
  history — it is **not** pushed.
- Working-tree and staged secret scans found no real secret values in the push set.
  (A `dist/` `sk_` match is a false positive — a torch header filename — and `dist/`
  is gitignored anyway.)
- No model weights, production database, avatar latents, renders, audio previews,
  or runtime instance manifests are tracked.
- See `docs/V1_6_PRE_GITHUB_PUSH_AUDIT.md`.

---

## Git Repository

- **Existing local repository** (42 commits before this release) — history preserved,
  not re-initialized.
- **No large files:** largest blob in history is ~3.4 MB; zero blobs >50 MB.
- **No secrets in history.**
- **Release manifest:** V1.6 source / tests / config / permanent tools / docs were
  staged explicitly (no `git add -A`). Internal acceptance/audit scripts
  (`tools/_*.py`), redundant archives (`docs/*.zip`/`*.7z`), internal handover
  packages (`handover/`), and a private test script (`input4_9/`) were intentionally
  excluded via narrow `.gitignore` rules.
- **`data/avatar_sources.json`** (machine-specific avatar lineage with absolute local
  paths) was intentionally **not** committed (kept local under the `data/` ignore).

---

## Origin / Upstream

- **origin:** `https://github.com/thangngny/AI_Avatar.git` (the user's repository)
- **upstream:** `https://github.com/NeolabAI/avatar_livestream.git` (preserved)
- The target was confirmed `ORIGIN_ACCESSIBLE_AND_EMPTY` immediately before push.
- No force push was used; no history was rewritten.

---

## Release Commit

One V1.6.0 release commit on `main`, with annotated tag
`ai-avatar-studio-ui-v1.6.0` pointing at it. See the tag (not this file) for the
commit SHA, to keep a single, clean release commit.

Historical release tag `ai-avatar-studio-ui-v1.5.0` is preserved and pushed; it is
not moved or replaced.