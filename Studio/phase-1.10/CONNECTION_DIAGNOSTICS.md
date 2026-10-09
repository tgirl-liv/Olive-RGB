# LEDBLE connection diagnostics — v1.4.2

Baseline: exact latest v1.4.2 ZIP supplied/delivered in this conversation.
This is a diagnostic source build, not a connection fix. RGB protocol unchanged.

Close the old app. Run install_dependencies.bat in this extracted project, then
`py olive_rgb.py`. Select LEDBLE Strip and press CONNECT. Copy the System log
from LEDBLE_SCAN_START through LEDBLE_ERROR and LEDBLE_TRACE, including cleanup
messages. If using an EXE, rebuild this project first; the old EXE has no new logs.

Changed files:
- ledble_driver.py: stage diagnostics, backend traceback frames, first-write
  markers, and cleanup error handling that preserves the original exception.
- olive_rgb.py: imports and registers the diagnostic callback with existing
  GUI log immediately before constructing the worker. Worker body unchanged.
- test_ledble.py: fresh-device identity assertion and injected failure diagnostics.
- New CONNECTION_DIAGNOSTICS.md (this report).

No changes to worker body, rate limiter, reactive engines, LotusLamp connection
behavior/UUIDs/packets, LEDBLE RGB/power builders, dependencies, or build scripts.
No second thread/loop, pairing request, automatic retry, or cache override added.
Selection remains a family name; no LEDBLE address is stored. Each disconnected
LEDBLE connection scans immediately by LEDBLE-00-0806 and passes that scan's actual
BLEDevice directly to BleakClient. A connected-client no-op remains unchanged.

Markers:
LEDBLE_SCAN_START,<target>
LEDBLE_SCAN_FOUND,<advertised-name>,<current-Windows-address>
LEDBLE_CLIENT_CREATE
LEDBLE_CONNECT_START,<current-Windows-address>
LEDBLE_CONNECTED
LEDBLE_SERVICES_READY
LEDBLE_FFE0_LOOKUP / LEDBLE_FFE0_READY
LEDBLE_FFE1_LOOKUP / LEDBLE_FFE1_READY
LEDBLE_WRITE_MODE,response=<True/False>
LEDBLE_FIRST_WRITE_START / LEDBLE_FIRST_WRITE_OK
LEDBLE_ERROR,<operation>,<exception-type>,winerror=<code>,<message>
LEDBLE_TRACE,<backend-file>,<function>,<line>,<source>

Bleak automatically discovers GATT services within client.connect(). Therefore
an error labeled client.connect can originate inside Windows service enumeration;
traceback frames identify the backend operation rather than asserting that the
radio link itself failed. LEDBLE_CONNECTED means connect() returned successfully,
not a separate low-level link-established event.
Reference: https://bleak.readthedocs.io/en/stable/api/client.html

Validation: seven offline tests passed, including seven injected failure stages
(scan, constructor, connect, services access, FFE0, FFE1, first write), signed
WinError reporting, original-error preservation when cleanup also fails, and
passing the identical freshly scanned device object to the client constructor.
Source compilation passed. AST comparisons establish unchanged entire worker,
Music/Screen engines, packet builders, name-family matcher and disconnect method.

The provided original log does NOT identify which operation throws WinError
-2147024838. Actual Windows discovery, connection, and the exact failing operation
cannot be confirmed without the user's next log. No physical testing was done.
