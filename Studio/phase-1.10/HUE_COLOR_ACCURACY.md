# Hue color accuracy: trace, correction and acceptance

## Confirmed software defect and evidence

Manual HEX/color picker RGB is sRGB. The shared helper in `hue_driver.py` decoded
sRGB gamma correctly, then used wide-gamut RGB primaries (`.664511` etc.). CIE xy
is device-independent: it needs XYZ derived from the **input** color space, not
from assumed lamp primaries. Red was `(0.700606, 0.299301)` instead of standard
sRGB `(0.640000, 0.330000)`; neutral white also missed D65's x coordinate.
Pink `#FF69B4` was `(0.469102635680, 0.246854013029)`.

The correction changes only `rgb_to_xy()`'s RGB→XYZ matrix to sRGB/D65. The existing
piecewise sRGB decoding, R/G/B ordering, input clamping and black fallback remain.
No hue offsets, per-palette corrections, new commands, transport changes or
additional gamma/saturation processing are introduced. This shared helper serves
both original Tkinter and Studio in `Studio/phase-1.10`; its corrected conversion
therefore applies to both. Neither `olive_rgb.py` nor the older main checkout was
modified.

Seven new tests in `test_hue_color.py` use independent standard chromaticities,
inverse sRGB reconstruction, pinned HueBLE with mocked GATT and mocked responses.
The old matrix fails the reference/API/payload tests, including pink. Tests pass
after correction. Mock readback verifies packing/decoding only; it is not bulb
acceptance or physical color measurement.

The user-reported pink→purple hardware behavior is an acceptance failure, not a
placeholder UI issue. The conversion defect is established, but software tests
cannot prove it is the sole cause of that observed shift. The bulb model, mode
used for the recording and original-app comparison have not been established.

## Complete output trace

| Path | RGB processing before shared driver |
|---|---|
| Tkinter independent Hue | `HuePanel.choose_color()` → `independent()` → `HueService.update()` → `desired()` retains R/G/B in color mode. Brightness is native, separate. |
| Tkinter Master/Screen | `LightingRouter.set_rgb()` → Hue master state → `HueService.desired()` retains RGB and scales native brightness using peak RGB × Master brightness. |
| Qt Manual HEX/HSV/color | `StudioController.set_hex()` / `set_hsv()` → `apply_manual()` → `DualLightingAdapter.set_rgb()` → `_queue_hue()` → `HueSession.update()`. RGB is unscaled; intensity, local/Follow Master brightness and power are native, separate commands. HSV editing intentionally constructs new RGB. |
| Music in either app | Existing `MusicLightingRouter` → Same Color retains measured RGB; **Coordinated Colors intentionally changes Hue RGB** through `AccentGenerator` (20–180° coordination, saturation/envelope). This is an effect, not a transport conversion. Music output brightness/saturation intentionally modify a copied frame before coordination. |
| Qt Screen | `ScreenLightingAdapter.apply_screen()` → `_queue_hue()` sends measured RGB to a connected Hue following Master; brightness/power remain separate. |
| Final color call | Actor → `HueDriver.write('color', rgb)` → `rgb_to_xy(rgb)` → `HueBLE.set_colour_xy(x,y)` → existing XY GATT characteristic. No HS/HSV API calls. |
| White mode | `HueDriver.write('temperature', mired)` → existing `set_colour_temp()` and bulb limit clamping; separate from XY. New Studio mailbox removes pending temperature when RGB arrives and vice versa; actor invalidates the counterpart's sent cache to allow identical-color restoration. |

The original and Qt Manual routes are tested with identical RGB values before
conversion. Existing ownership/capability tests verify that unsupported RGB is
skipped and Music/Screen ownership gates manual editing. White-only bulbs cannot
render the reference RGB colors; support must be probed, not assumed.

## Expected API requests and unchanged encoding

Reference: IEC sRGB primaries and D65; gamma decoded exactly once, XYZ normalized
as `x=X/(X+Y+Z)`, `y=Y/(X+Y+Z)`. The input is 8-bit sRGB, not already-linear RGB.
The inverse-matrix tests include values on both sides of the sRGB gamma threshold.

The pinned HueBLE 2.2.3 call is `set_colour_xy(x,y)`. Its existing encoding is
`struct.pack('<HH', int(x*65535), int(y*65535))`; truncation is unchanged. Writes
remain to `HueBLE.UUID_XY_COLOUR`, UUID
`932c32bd-0005-47a2-835a-a8d455b859dd`. No packet layout/service UUID was changed.

| Color | HEX / RGB | x | y | Existing encoder's 4-byte payload (hex) |
|---|---|---:|---:|---|
| Pink | `#FF69B4` / 255,105,180 | 0.400424102011 | 0.254533185504 | `81 66 28 41` |
| Red | `#FF0000` / 255,0,0 | 0.639999925519 | 0.330000068274 | `d6 a3 7a 54` |
| Green | `#00FF00` / 0,255,0 | 0.300000008390 | 0.600000016780 | `cc 4c 99 99` |
| Blue | `#0000FF` / 0,0,255 | 0.150000008313 | 0.060000003325 | `66 26 5c 0f` |
| Cyan | `#00FFFF` / 0,255,255 | 0.224655633125 | 0.328760259206 | `82 39 29 54` |
| Magenta | `#FF00FF` / 255,0,255 | 0.320937741119 | 0.154190221199 | `28 52 78 27` |
| Yellow | `#FFFF00` / 255,255,0 | 0.419320092998 | 0.505245826920 | `58 6b 57 81` |
| White | `#FFFFFF` / 255,255,255 | 0.312726604392 | 0.329023152403 | `0e 50 3a 54` |

For example native brightness 128 is the separate existing brightness command,
not part of those XY bytes. Changing native brightness does not recompute XY.
Black retains the existing neutral fallback `(0.3127,0.3290)` for the standalone
converter; output power/zero-intensity handling stays in the existing router.

## Gamut and remaining physical verification

Neither existing driver nor HueBLE exposes a calibrated bulb gamut triangle to
the conversion helper. No application gamut clipping is performed, and the code
must not select gamut A/B/C from a generic “Philips Hue” name. Firmware gamut
mapping, calibration, actual accepted XY and physical output remain unverified.
Correct CIE input cannot make a bulb reproduce colors outside its physical gamut.

Physical acceptance, explicitly **pending**:

1. Record exact bulb model/firmware, selected stable identity, app version and
   which original/Studio path shows the shift. Confirm an RGB-capable bulb.
2. Stop Music and Screen; select Philips Hue only, Manual mode, Follow Master OFF,
   power ON and a fixed local brightness. Connect explicitly. Use HEX input.
3. Test the eight reference colors above, especially pink. Do not compare a
   coordinated Music accent to the primary Music/virtual Corner color.
4. Verify emitted XY against the table, then obtain actual
   `HueBLE.poll_colour_xy()` readback from the connected bulb (within 1/65535 when
   firmware retains the request). A matching readback still does not measure
   physical color. Compare with a trusted controller at the same brightness;
   camera white balance/exposure must not be mistaken for light chromaticity.
5. RGB→white temperature→same RGB; stop/opt out of Music/Screen and confirm manual
   RGB or white restores without competing writes. Check power/brightness scaling.
6. If pink remains purple with the correct XY call/readback, investigate that bulb's
   model-specific gamut/calibration and firmware/API behavior. Do not compensate
   with arbitrary hue offsets or change BLE encoding without measured evidence.

## Repeat software checks (no physical lights)

From `Studio/phase-1.10`, using the same dependency environment as Studio:

```powershell
& $studioPython -B -m unittest test_hue_color test_hue_api test_hue_integration test_hue_parity -v
```

See `PRE_HARDWARE_TEST_CHECKLIST.md` for environment/launch commands, the two parity
stages and all remaining hardware checks. This sprint has completed review for
the final pre-hardware commit.

## Final validation and status

Full automated suite: **362 passing tests**; actual-launcher DEMO smoke passed;
dependency compatibility check passed. No unexpected warnings, worker exceptions
or deleted-object errors appeared in final logs. The seven color tests passed a
focused recheck covering the exact gamma boundary; this is not double-counted.
Logs remain outside Git at `/workspace/olive-rgb-hue-color-validation/`.

Hue and appearance parity changes remain included and tested. Branch is
`development/qt-studio`; the reviewed commit message is
`fix(studio): correct Hue colors and complete parity`. Physical pink accuracy,
Windows software acceptance and all lamp testing remain pending. Studio is
feature-frozen pending physical hardware acceptance; no calibration or additional
feature development is included.

Final pre-commit rerun: all 362 tests and DEMO smoke passed; dependency check
passed. Logs are outside Git at
`/workspace/olive-rgb-prehardware-commit-validation/`. Windows and physical
hardware acceptance remain unverified.
