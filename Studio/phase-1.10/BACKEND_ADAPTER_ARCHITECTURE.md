# Phase 1.5 — adapter boundary (mock only)

No production adapter exists in this release. `studio_qt/backend_adapter.py` imports only the standard library, QtCore and the unchanged mock state model. It performs no discovery, pairing, hardware writes, audio capture, network access, disk writes, thread creation or asyncio setup. `discover_devices()` returns the two predefined simulated devices.

## Current implementation

```text
Qt widgets → StudioController → LightingAdapter intent methods
                                  └─ MockLightingAdapter → in-memory state
MockLightingAdapter.device_status → queued Qt slot → Inspector
MockLightingAdapter.audio_meters  → queued Qt slot → four reactor meters
```

`LightingAdapter` is a Protocol defining the interface. The only implementation is `MockLightingAdapter`, a QObject exposing `device_status` and `audio_meters` signals. Status and meter payloads are immutable dataclasses. Explicit queued connections target QObject slots on the main-window/inspector objects. The UI ignores late notifications after adapter closure.

The controller maintains optimistic preview state and invokes adapter methods for master, mode, power, brightness, follow, color and scene intent. Navigation, favorites, inspector tabs and preview preferences remain local UI state. The default mock shares the existing `StudioState`; an injected mock with its own model is tested too. This mock-state convenience is **not** a requirement that a future worker share mutable UI objects.

Scene interpolation changes display colors locally. It does not call adapter RGB methods every frame. There is one root-owned 34 ms timer for synthetic animation and transitions. Its synthetic band averages enter the mock-only `publish_demo_meters()` helper and return through the same queued notification path that a future analysis publisher could use. The 72 bars and waveform are still synthetic, not backend FFT data.

The mock records at most 256 command tuples for tests; this bounded audit log is not a transport queue. `close()` is idempotent, rejects subsequent commands and suppresses new meter notifications. Window close stops its timer, cancels interpolation and closes the mock adapter. There are no worker threads to join.

## Intent contract and confirmation needed before Phase 2

| Interface | Current mock meaning | Must confirm against production before implementation |
|---|---|---|
| `discover_devices()` / `request_status()` | Emits predefined `DeviceStatus` records | Which existing service owns scanning; stable IDs, discovery cancellation, saved devices and status lifecycle |
| `device_status` signal | Device ID, display name, simulated connection state | Mapping actual disconnected/connecting/connected/error states; stale-generation handling; error payload and retry ownership |
| `set_power(device_id, enabled)` | Updates channel state | Per-driver power support, ordering and failure reporting; never infer a packet |
| `set_rgb(device_id, color)` | Validated `#RRGGBB` UI color | Existing application-level RGB entry points, conversion, capabilities, coalescing and driver rate limits |
| `set_brightness(device_id, 0..1)` | Normalized local brightness | Native brightness versus RGB scaling; Follow Master multiplication and restoration rules |
| `set_follow_master(device_id, enabled)` | Updates mock follow setting | Existing router ownership, in-flight transition cancellation and independent-state restoration |
| `set_master(power, brightness)` | Updates master state | Existing routing semantics and atomicity across devices, including independent channels |
| `select_mode(mode)` | Manual/Music/Screen UI choice | Existing mode lifecycle and names, capture ownership, start/stop and failure states |
| `apply_scene(scene)` | Calls existing mock scene model | Production scene identity/schema, transition ownership and application-level routing |
| `audio_meters` signal | Immutable normalized bass/mids/treble/level | Existing MusicEngine payload, normalization, publication cadence and lifetime; no new capture session |
| `close()` | Stops accepting mock commands | Ownership of application services, asynchronous shutdown, pending commands and completion acknowledgement |

`Corner` and `Hue` are opaque demo IDs, not Bluetooth addresses. Color values and command names are application intent, not BLE packets. Discovery does not imply connection or pairing. No unsupported hardware feature is advertised by this interface.

## Intended integration architecture — documentation only

```text
Qt main thread
  → Qt signals and slots
  → future backend adapter (validate and submit; return immediately)
  → existing application routing and persistent asynchronous Bluetooth worker
  → existing device drivers, coalescing and rate limits

existing service/analysis notifications
  → immutable status/meter payloads
  → queued Qt signal
  → main-thread slot
  → widgets
```

1. Reuse the existing worker's submission boundary and event loop. Inspection confirms `BluetoothWorker` already uses `asyncio.run_coroutine_threadsafe`; this is evidence to review its public ownership contract, not permission to bypass it or create another loop. Hue service ownership must be reviewed separately rather than assuming all production services share one loop.
2. A UI slot must never perform BLE discovery, connection, synchronous waiting, `future.result()`, `asyncio.run()`, sleeps or thread joins. Submit through the existing service boundary and report completion asynchronously.
3. Worker callbacks must never call widget methods or mutate GUI-owned state. Emit copied immutable data through queued signals whose receivers belong to the Qt main thread.
4. Preserve the existing corner lamp's 4 Hz limit and each driver's existing behavior. GUI repaint cadence is unrelated to transport cadence. Keep latest-value coalescing at the existing routing/worker boundary; do not enqueue every slider or animation sample as a write.
5. Before live support, define pending/acknowledged/error state and generation IDs for reconnect, mode changes and shutdown. The current optimistic mock state must not be displayed as confirmed hardware state. Add failure tests before wiring any actual driver.
6. Audio telemetry should use a bounded latest-snapshot mechanism when connected to real producers. Queued Qt signals alone do not impose backpressure. The present 30 Hz mock publisher is on the GUI thread and does not establish a production telemetry queue policy.
7. Closing the UI must unsubscribe, stop its timer, reject stale notifications and request backend shutdown only if this UI owns those services. The application must never close someone else's event loop. Shutdown completion must remain asynchronous.

These items are preparation only. No live bridge, new packet format, retry policy, pairing path or rate limiter has been implemented. Hardware integration requires explicit approval after UI review.
