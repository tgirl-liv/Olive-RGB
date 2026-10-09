# Windows physical validation — Phase 1.9

Pending user testing. Automated connected/error screenshots use fake transports.

1. Keep the working Phase 1.8 copy. Extract Phase 1.9 separately and install its optional LIVE dependencies using the setup steps in `PHASE_1_9.md`. Close other lamp-control applications. Retain the existing working Windows pairing; this release never pairs, resets or unpairs Hue automatically.
2. Launch DEMO first. Confirm the approved layout, workspace controls and mock behavior remain available. Restart, explicitly choose LIVE, and verify both devices remain disconnected until their own Connect button is pressed.
3. **Hue only:** leave Corner disconnected. Connect Hue. Confirm the displayed name/address identifies your bulb and power/brightness readback is plausible. If saved identity verification or authentication fails, record the exact error; do not change pairing or protocols as a guess.
4. With Hue Follow Master OFF, test native OFF/ON, local brightness 25/50/100%, and red/green/blue through HEX, wheel and advanced RGB. Use only enabled capabilities. RGB controls show requested colors, not readback. Verify Corner remains disconnected and unaffected.
5. **Corner only:** disconnect Hue, connect Corner. Confirm the same Phase 1.8 red/green/blue, brightness and RGB-black power behavior. Correct Corner identity is `MELK-OA10   7F / BE:28:87:00:08:7F`.
6. **Both:** connect both. Give each a distinct color. Change one device's local color, power and brightness; the other must retain its state. Confirm statuses are independent.
7. Enable Follow Master for both and test Master brightness and OFF/ON. Local brightness multiplies Master brightness once. Hue also honors the selected RGB value/intensity once. Turn Follow Master OFF on one device and confirm subsequent Master changes do not affect it. Its local settings should remain intact.
8. Drag each brightness/color control rapidly, separately and together. Confirm the UI stays responsive and each lamp settles to its own final requested state. Existing Corner small-change suppression may delay tiny updates by up to 1.5 seconds.
9. Disconnect/reconnect Hue while Corner is active, then reverse the roles. Also try a quick Disconnect → Connect. No initial color is pushed merely by reconnecting; edit a supported control to apply requested state. Neither device should automatically reconnect after a failure.
10. Remove power from Hue and confirm a meaningful error while Corner remains controllable. Restore power and reconnect explicitly. Repeat with Corner power removed while Hue remains controllable. A cleanup failure should leave an error rather than simulated success; reopen LIVE before retrying a terminal Hue cleanup failure.
11. Close while connecting to either/both devices. Repeat while dragging controls. The window should stay responsive during cleanup, then exit. Reopen LIVE and confirm no automatic connections. Already transmitted commands cannot be undone by closing.
12. Confirm Music, Screen, scene playback and song/timeline features do not control hardware. Workspace presets may rearrange the UI without changing lighting mode. Test all presets, collapse/restore, splitter movement and keyboard controls at your usual Windows DPI.
13. Close Phase 1.9. Relaunch Phase 1.8 and then, separately, the original Tkinter application to confirm recoverability. Do not run them concurrently against the same lamp.

Record Windows version, package versions, actual device identities, reported capabilities, pass/fail per step, visible physical results and exact error text. Physical success is established only after the user confirms the lamps respond correctly.
