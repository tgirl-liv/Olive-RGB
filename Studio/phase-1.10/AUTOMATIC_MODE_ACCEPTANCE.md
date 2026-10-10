# Automatic LIVE mode activation — Windows acceptance

Automated validation uses simulated audio, screen capture and devices. Real Windows
loopback/MSS and physical-light acceptance remain pending. Launch remains Manual;
restoring preferences and changing pages never connect devices or start effects.

From the repository root, using the existing Studio Python environment:

```powershell
Set-Location .\Studio\phase-1.10
python .\studio_qt_preview.py
```

Choose LIVE and leave devices disconnected:

1. Play audio; select Music on the Master bus. Confirm the reactor and Album section's
   Virtual Light Preview update. Production settings remain editable. The main header
   has no Start/Stop Music buttons; advanced actions remain on the Music page.
2. Re-select Music repeatedly. Capture and visualization should continue uninterrupted.
3. Select Screen. Audio stops before Movie capture begins; the Screen page opens and
   its virtual preview updates. No Hue/Bluetooth connection is attempted.
4. Choose Gaming on the Screen page, then select Manual. Capture stops and manual
   controls become available. Restart Studio: launch is idle; selecting Screen starts
   saved Gaming settings, monitor, intensity and saturation.
5. Test Manual → Music → Screen → Music → Manual, including rapid changes and Esc.
   Confirm the selector stays Manual while opening capture and only selects Music or
   Screen after the first measured frame. Opening status must remain visible; failures
   return to Manual. Close during a transition.
6. Test unavailable audio and denied/unavailable screen capture. Confirm a visible
   error, Manual selection, no stuck capture, and successful retry after restoring access.
7. Navigate pages without selecting a mode. The active effect must not change.

With hardware (pending): verify exclusive Music/Screen output ownership and restoration
of saved manual RGB/white output, with existing Master/device brightness and power.
No transport, color conversion or rate-limit changes are part of this repair.

## Capture startup diagnostics

Music uses the Windows default **playback/output** device, matching the original app;
Studio has no separate input-device selector. Verify the desired output in Windows
Settings → System → Sound and in the playing application's volume mixer. Play audio
through that output before selecting Music. A valid WASAPI loopback is resolved by
playback endpoint ID, avoiding a microphone with a similar name. No second recorder
is created. Output changes still use the original engine's device-change loop.

- Successful startup requires a measured MusicFrame from the recorder → FFT → existing
  lighting pipeline. A worker/thread-start log alone is insufficient.
- With playback, confirm 72 FFT bars/curve and the Album section's virtual RGB change.
  Pause playback: status should say **capture running · silence**, rather than fail;
  resume playback without changing modes and confirm response returns.
- Missing default output, unavailable loopback and recorder failures show their actual
  exception text and restore Manual. No first frame after five seconds is a startup
  timeout, not silence. Native recording calls cannot be forcibly interrupted; mode
  switching waits for the existing worker to finish, without blocking Qt.
- Screen similarly requires a captured RGB frame before owning output. Show changing
  red/green/blue content on the selected monitor, select Screen, and confirm preview
  follows it. Test saved Gaming, monitor, intensity and saturation. A black captured
  desktop is valid output; protected video may remain black.

Automated tests execute the production engine loops, FFT and output routing with
controlled SoundCard/recorder and MSS input. They verify capture-context entry,
first-frame readiness, real calculated spectrum/virtual output, silence, device/open
errors, timeouts, repeat-click idempotence and clean cancellation. These are **simulated
I/O tests**, not Windows or physical-light verification. The specific Windows recording's
0% cause cannot be established remotely without the new status/error and device details.

If Music does not activate, run this in the same activated Python environment and
record its output alongside the visible Studio error (no audio recorder is opened):

```powershell
python -c "import sys, soundcard as sc; print(sys.executable); print('Default output:', sc.default_speaker()); print('Loopbacks:', sc.all_microphones(include_loopback=True))"
```

Record the Windows output endpoint name, playback app, default-output selection,
startup status/error, and whether recorded RMS rises with playback. Do not label a
silent or wrong playback endpoint as a visualizer failure solely from 0% LEVEL.

Additional cloud software verification: native PulseAudio loopback recorded a 1 kHz
playback signal (measured RMS approximately 0.141), produced 72 FFT bands and virtual
Music RGB. Native MSS/Xvfb captured changing desktop content and updated Screen RGB.
Music → Screen → Manual drained the preceding capture thread and left both physical
sessions disconnected. This verifies Linux virtual audio/display only, not Windows
WASAPI, Windows desktop capture, or physical light behavior.
