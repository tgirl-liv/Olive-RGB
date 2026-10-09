# Codex project instructions — Olive RGB Qt Studio

## Current baseline
- This directory is a copied Phase 1.10 development baseline. Preserve the original ZIP and the separate v1.5.1 backup.
- Treat the existing `olive_rgb.py` backend and the `studio_qt/` adapters as authoritative until inspected. Do not replace functioning hardware code with speculative implementations.
- Do not assume all buttons are wired merely because screenshots or mock tests pass.

## Safe changes
- Before editing, inspect the relevant control's signal/callback, adapter, and backend route.
- Keep DEMO simulation isolated from LIVE hardware I/O.
- Never bypass Bluetooth write throttling, connection ownership, or shutdown safeguards.
- Avoid moving Python modules, changing import paths, or relocating Windows launch scripts in an organization-only change.
- Prefer small focused patches, explicit tests, and a summary of hardware verification still needed.
- If physical lights are unavailable, clearly mark tests as simulated, not hardware-verified.

## Next task
Create a UI control functionality matrix (working/partial/broken/unimplemented) and propose fixes before implementing large changes.
