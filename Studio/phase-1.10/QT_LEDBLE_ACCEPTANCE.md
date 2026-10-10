# Studio LEDBLE family selection — Windows acceptance

## Connection and persistence

In LIVE, use the Bluetooth controller family selector beside Connect:
**LotusLamp Corner Lamp** or **LEDBLE Strip**. Selection disconnects the previous
controller and discards queued RGB commands. Press Connect explicitly afterward.
Restoring preferences never connects or starts Music.

There is one shared Bluetooth channel, session, worker and event loop. The internal
`Corner` channel key remains stable for existing manual settings, participation
and Music routing; its visible device label changes to LEDBLE Strip. Hue remains
independent. This sprint does not provide simultaneous LotusLamp and LEDBLE
connections or separate lighting settings for the two Bluetooth families.

The existing atomic Qt preferences store saves the selected family and its known
target identity outside the repository. LotusLamp retains name `MELK-OA10   7F`
and address `BE:28:87:00:08:7F`. LEDBLE retains exact-name discovery of
`LEDBLE-00-0806`; its discovered Windows address is reported but is not persisted
because the existing driver intentionally rediscovers the device. Arbitrary names,
addresses and unverified LEDBLE models are not enabled.

RGB, software brightness and RGB-black software power reuse existing adapters.
No unconfirmed native LEDBLE power packet is sent. The 250 ms update limiter,
connection settling delay, packets, service checks and retry policy are unchanged.
After uncertain disconnect cleanup, reconnect is disabled until LIVE is reopened.

## Windows hardware checks — pending

Linux automated checks use simulated devices. Physical LEDBLE, LotusLamp and Hue
acceptance has **not** been performed in this environment. Record Windows/Python
versions, adapter, exact advertising name, strip model and failures for each check.

- [ ] Launch `Studio/phase-1.10/studio_qt_preview.py`, choose LIVE; confirm no scan,
      connection or audio capture until explicitly requested.
- [ ] Select LEDBLE, restart Studio, confirm the selection survives and remains
      disconnected. Original Tkinter settings must remain untouched.
- [ ] Connect `LEDBLE-00-0806`; verify reported identity, FFE0/FFE1 discovery,
      and red/green/blue/HEX/HSV manual colors with the existing packet behavior.
- [ ] Verify device and Master brightness, Follow Master and software OFF/ON.
      OFF should send RGB black, not an unverified native power command.
- [ ] Connect Hue; verify Both Lights manual control, independent settings,
      capability gating and unchanged Hue behavior.
- [ ] Run LIVE Music; verify participation, coordinated/same-color controls,
      palette changes, Album fallback and manual color ownership gating. Verify
      audio capture, Virtual Light Preview and Audio Reactor continue running.
- [ ] Switch LEDBLE → LotusLamp during Music and manual updates. Confirm the strip
      disconnects, queued colors do not leak, and the new lamp needs explicit
      Connect. Repeat in reverse and through rapid selector changes.
- [ ] Disconnect/reconnect repeatedly; verify no extra connections, event loops,
      duplicate writes or unexpected automatic color restoration.
- [ ] Switch family or close the window during discovery, connection settling,
      an RGB write and disconnect. Confirm clean exit without hanging threads or
      Qt deleted-object exceptions.
- [ ] Test missing device, powered-off strip, signal loss and WinRT discovery
      failure. Confirm clear errors and only the existing bounded retry behavior.
      A failed cleanup must not start a replacement connection.
- [ ] Confirm the existing 250 ms accepted RGB cadence and settling behavior using
      diagnostic logs. Confirm LotusLamp and Hue regression behavior on hardware.
- [ ] Launch DEMO; confirm simulated lighting/audio and no hardware access.
