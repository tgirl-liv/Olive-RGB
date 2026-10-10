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
   Confirm highlighting matches the requested mode while stopping, then the active
   mode; Manual is selected after activation failure. Close during a transition.
6. Test unavailable audio and denied/unavailable screen capture. Confirm a visible
   error, Manual selection, no stuck capture, and successful retry after restoring access.
7. Navigate pages without selecting a mode. The active effect must not change.

With hardware (pending): verify exclusive Music/Screen output ownership and restoration
of saved manual RGB/white output, with existing Master/device brightness and power.
No transport, color conversion or rate-limit changes are part of this repair.
