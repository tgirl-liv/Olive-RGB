# LEDBLE FFE0 / WinRT cache compatibility update

Baseline: exact Olive RGB v1.4.2 LEDBLE Diagnostics.zip from this conversation.
This report supersedes the connection-strategy statements in the earlier
CONNECTION_DIAGNOSTICS.md. This remains a v1.4.2 diagnostic build.

The user's physical log locates WinError -2147024838 in Bleak WinRT
_get_services(), awaiting service.get_characteristics_async(), inside
client.connect(). Scanning and client construction succeeded; no RGB write
had yet occurred. Physical success with this update is not claimed.

## Connection change
Before:
    BleakClient(device)

After, attempt 1:
    BleakClient(device, services=[self.SERVICE_UUID])
Attempt 2, only following the specific discovery failure:
    BleakClient(device, services=[self.SERVICE_UUID],
                winrt={"use_cached_services": True})
Attempt 3, only if the same discovery failure recurs:
    BleakClient(device, services=[self.SERVICE_UUID],
                winrt={"use_cached_services": False})

SERVICE_UUID = 0000ffe0-0000-1000-8000-00805f9b34fb.
The default attempt omits winrt entirely, preserving normal cache behavior.
Each attempt constructs a new client with the identical fresh BLEDevice from
the immediately preceding name-matched Windows scan. No hard-coded strip
address, pairing request, new event loop or Bluetooth thread is introduced.

Retry requires ALL of: error during client.connect(), OSError with winerror
-2147024838, and a traceback frame in bleak/backends/winrt at _get_services
or get_services. Constructor, scan, missing-service/characteristic, property,
write, cancellation and other failures do not trigger cache retries.
At most one attempt per mode, in default/cached/uncached order. Success stops.
Failed clients are awaited through disconnect() before any retry. If cleanup
throws, its error is logged and retries stop while preserving the original
connection exception. No overlapping clients or unbounded retries are added.

The API options are documented by Bleak:
https://bleak.readthedocs.io/en/stable/api/client.html
https://bleak.readthedocs.io/en/stable/backends/windows.html

## Validation
Eight offline tests passed, including eight retry scenarios: immediate success,
cached success, uncached success, exhaustion at three attempts, same WinError
outside discovery, different WinError, cleanup failure, and cancellation.
Tests assert the same scanned BLEDevice object, exact constructor options,
cleanup-before-retry order, mode logs, and unchanged RGB packet results.
All Python source compiles. Byte comparisons confirm olive_rgb.py is entirely
unchanged, including the worker, LotusLamp setup/UUIDs, limiter, UI, and all
reactive modes. Driver packet builders, channel order, matching, RGB write
method and disconnect method are structurally unchanged.
No live GUI, physical BLE connection, or executable build was performed.

Run checks: py -B -m unittest discover -s . -p "test_ledble*.py" -v

## Exact files changed
- ledble_driver.py: LEDBLE-only service filter, bounded cache retry, diagnostics.
- test_ledble.py: fake constructors accept/assert the service filter.
- New test_ledble_retry.py: retry and cleanup tests.
- New COMPATIBILITY_UPDATE.md: this report.
All other baseline files are byte-for-byte unchanged, including dependencies
and build scripts. No dependency upgrades are needed for this change.

## Run on Windows
Close the prior Olive RGB process, extract this folder and run py olive_rgb.py.
Choose LEDBLE Strip and CONNECT. Look for LEDBLE_SERVICE_FILTER,FFE0 and
LEDBLE_CONNECT_ATTEMPT,default (then cached/uncached only if necessary).
On success: LEDBLE_CONNECTED, LEDBLE_SERVICES_READY, LEDBLE_FFE0_FOUND,
LEDBLE_FFE1_FOUND. On failure: LEDBLE_CONNECT_FAIL,<mode>,<exception>, followed
by the existing detailed error/trace lines. Share that log for diagnosis.
If using an EXE, rebuild it from this folder before testing; an older EXE does
not load the changed source driver. RGB remains 7E 07 05 03 RR GG BB 00 EF.
