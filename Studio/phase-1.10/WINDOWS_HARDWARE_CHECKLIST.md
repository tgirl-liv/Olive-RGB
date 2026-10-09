# Phase 1.10 — Windows physical test checklist

Use **[PHASE110_HARDWARE_CHECKLIST.md](PHASE110_HARDWARE_CHECKLIST.md)** for LIVE music validation. Earlier phase instructions below remain historical reference.

Use **[PHASE19_HARDWARE_CHECKLIST.md](PHASE19_HARDWARE_CHECKLIST.md)** for this release's independent Hue + Corner checks. The historical Phase 1.8 checklist follows for reference; its original copy remains in the untouched Phase 1.8 release.

Not yet performed. Record actual results; screenshots/tests in this package use fake hardware.

1. Keep the original working application. Close it and any mobile/controller app connected to the Corner Lamp. Power the lamp normally.
2. In the new copy, run Setup Qt Preview, then Setup Live Corner Preview, then Launch Qt Preview. DEMO is selected by default. Confirm DEMO still behaves as the simulated preview.
3. Restart and explicitly select LIVE. Confirm disconnected status, disabled lamp controls and no automatic connection or color change.
4. Press Connect Corner Lamp. Confirm the reported device is **MELK-OA10   7F / BE:28:87:00:08:7F**. If your physical lamp has a different identity, stop and report it rather than changing protocols. An error must remain an error, not turn into a simulated connected state.
5. Set master/local power ON and both brightness controls to 100%. Select Corner Lamp. Enter HEX `#FF0000`, `#00FF00`, `#0000FF` and confirm red, green and blue on the lamp. Exercise wheel and advanced RGB controls.
6. Set local brightness to 25%, 50%, 100%. With Follow Master ON, repeat with master brightness. With Follow Master OFF, changing master brightness/power must not affect the lamp; local controls must still work.
7. Test local and master software power. OFF should produce black; ON should restore the selected color. This verifies RGB-black behavior, not a dedicated hardware power command.
8. Drag brightness and wheel rapidly. The GUI should remain responsive and the lamp should settle to the final value. Existing rate limiting can suppress tiny changes for up to 1.5 seconds.
9. Confirm Hue physical controls, Music/Screen lighting and scenes are unavailable in LIVE. Workspace Music/Compact presets may still rearrange the UI without changing lighting mode.
10. Disconnect. Confirm disabled controls, disconnected status and no automatic reconnection. Reconnect explicitly, including a quick Disconnect → Connect cycle; a successful reconnect should not apply a color until a supported control changes.
11. Power the lamp off unexpectedly. Confirm error/lost-connection status and no false connected indicator or automatic retry. Restore power and Connect explicitly.
12. Close during a connection attempt, then repeat while dragging a color/brightness control. The window must remain responsive while cleanup completes and close without leaving a controlling process. Already transmitted writes cannot be undone. Reopening LIVE must again require Connect.
13. Check all workspace presets, splitter/collapse controls and keyboard operation. At small sizes scroll to lower controls. Verify native Windows DPI on your actual display as needed.
14. After closing LIVE, launch the original Tkinter application independently and confirm its existing lamp behavior remains intact.

Record Windows version, Python/package versions, actual device identity, each pass/fail, exact status/error text, and whether the lamp physically changed as expected. Do not report physical success until these checks have been performed by the user. If a failure occurs, do not edit packet bytes, add pairing, or introduce automatic reconnect loops as a workaround.
