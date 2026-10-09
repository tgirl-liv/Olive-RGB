"""Offline tests for the narrowly scoped WinRT compatibility retry."""
import asyncio
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import ledble_driver
from ledble_driver import LEDBLEDriver
from test_ledble import offline_async


def discovery_error(code=-2147024838):
    error = OSError('Windows GATT discovery failure')
    error.winerror = code
    return error


# Give the raised exception the same backend location used by retry detection.
backend = {}
exec(compile('def _get_services(error):\n    raise error\n',
             'C:/python/bleak/backends/winrt/client.py', 'exec'), backend)


class RetryTests(unittest.TestCase):
    @offline_async
    async def test_attempt_order_filter_identity_cleanup_and_stop_conditions(self):
        cases = [
            ('default success', 0, None, False, 1),
            ('cached success', 1, 'discovery', False, 2),
            ('uncached success', 2, 'discovery', False, 3),
            ('bounded exhaustion', 3, 'discovery', False, 3),
            ('same code outside discovery', 3, 'other-stage', False, 1),
            ('other WinError', 3, 'other-code', False, 1),
            ('cleanup failure', 3, 'discovery', True, 1),
            ('cancelled', 3, 'cancelled', False, 1),
        ]
        for label, failures, failure_kind, cleanup_failure, expected_attempts in cases:
            with self.subTest(case=label):
                events, logs, clients = [], [], []
                device = SimpleNamespace(name='LEDBLE-00-0806', address='FRESH-WINDOWS')
                raised_errors = []
                char = SimpleNamespace(properties=['write-without-response'])
                service = SimpleNamespace(get_characteristic=lambda uuid: char)
                services = SimpleNamespace(get_service=lambda uuid: service)
                test = self
                class Scanner:
                    @staticmethod
                    async def find_device_by_filter(predicate, timeout):
                        events.append('scan')
                        test.assertTrue(predicate(device, SimpleNamespace(local_name=device.name)))
                        return device
                class Client:
                    def __init__(inner, actual_device, **options):
                        test.assertIs(actual_device, device)
                        inner.index = len(clients)
                        expected = {'services': [LEDBLEDriver.SERVICE_UUID]}
                        if inner.index:
                            expected['winrt'] = {'use_cached_services': inner.index == 1}
                        test.assertEqual(options, expected)  # No pairing or address override.
                        if inner.index:
                            test.assertEqual(events[-1], ('disconnect', inner.index - 1))
                        events.append(('construct', inner.index))
                        clients.append(inner)
                        inner.services = services
                        inner.is_connected = False
                    async def connect(inner):
                        if inner.index < failures:
                            if failure_kind == 'cancelled':
                                error = asyncio.CancelledError()
                            else:
                                error = discovery_error(-1 if failure_kind == 'other-code' else -2147024838)
                            raised_errors.append(error)
                            if failure_kind in ('discovery', 'other-code'):
                                backend['_get_services'](error)
                            raise error
                        inner.is_connected = True
                    async def disconnect(inner):
                        events.append(('disconnect', inner.index))
                        if cleanup_failure: raise RuntimeError('cleanup failed')
                        inner.is_connected = False
                with patch.object(ledble_driver, '_diagnostic_callback', logs.append), patch.dict(
                        sys.modules, bleak=SimpleNamespace(BleakClient=Client, BleakScanner=Scanner)):
                    driver = LEDBLEDriver()
                    if failures < 3:
                        await driver.connect()
                        self.assertIs(driver.client, clients[-1])
                    else:
                        with self.assertRaises(BaseException) as caught:
                            await driver.connect()
                        self.assertIs(caught.exception, raised_errors[-1])
                        self.assertIsNone(driver.client)
                    self.assertEqual(len(clients), expected_attempts)
                    self.assertEqual(events.count('scan'), 1)
                    self.assertEqual([line for line in logs if line.startswith('LEDBLE_CONNECT_ATTEMPT,')],
                                     ['LEDBLE_CONNECT_ATTEMPT,' + mode for mode in
                                      ('default', 'cached', 'uncached')[:expected_attempts]])
                    self.assertIn('LEDBLE_SERVICE_FILTER,FFE0', logs)
                    for index in range(min(failures, expected_attempts)):
                        self.assertIn(('disconnect', index), events)


if __name__ == '__main__':
    unittest.main()
