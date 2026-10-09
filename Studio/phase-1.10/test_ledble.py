"""Offline protocol and worker integration tests; no BLE or GUI required."""
import ast
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ledble_driver import LEDBLEDriver


class FakeLamp:
    def __init__(self):
        self.calls = []
    async def connect(self): self.calls.append('connect')
    async def disconnect(self): self.calls.append('disconnect')
    async def set_rgb(self, *rgb): self.calls.append(rgb)


class ProtocolTests(unittest.TestCase):
    def test_confirmed_packets(self):
        for rgb, expected in [((255, 0, 0), '7e070503ff000000ef'),
                              ((0, 255, 0), '7e07050300ff0000ef'),
                              ((0, 0, 255), '7e0705030000ff00ef'),
                              ((-10, 999, 12), '7e07050300ff0c00ef')]:
            self.assertEqual(LEDBLEDriver.rgb_packet(*rgb).hex(), expected)

    def test_identification_and_power_status(self):
        self.assertTrue(LEDBLEDriver.matches('LEDBLE-00-0806'))
        self.assertFalse(LEDBLEDriver.matches('MELK-OA10   7F'))
        self.assertFalse(LEDBLEDriver.matches(None))
        self.assertFalse(LEDBLEDriver.matches('unrelated-FFE1'))
        self.assertFalse(LEDBLEDriver.POWER_CONFIRMED)
        self.assertEqual(LEDBLEDriver.power_packet(True).hex(), '7e040401ffffff00ef')
        self.assertEqual(LEDBLEDriver.power_packet(False).hex(), '7e040400ffffff00ef')


def offline_async(function):
    # Mock I/O completes inline: execute without requiring a Windows event loop.
    def run(self):
        coroutine = function(self)
        try:
            coroutine.send(None)
        except StopIteration:
            return
        finally:
            coroutine.close()
        self.fail("Unexpected suspension in mocked I/O")
    return run


class AdapterTests(unittest.TestCase):
    @offline_async
    async def test_failure_stage_and_original_exception(self):
        import ledble_driver
        for failing in ['scan', 'construction', 'connect', 'services', 'FFE0', 'FFE1', 'write']:
            with self.subTest(stage=failing):
                logs = []
                error = OSError('The specified server cannot perform the requested operation')
                error.winerror = -2147024838
                def fail(stage):
                    if stage == failing: raise error
                class Service:
                    def get_characteristic(inner, uuid):
                        fail('FFE1')
                        return SimpleNamespace(properties=['write-without-response'])
                class Services:
                    def get_service(inner, uuid): fail('FFE0'); return Service()
                class Client:
                    def __init__(inner, device, **options): fail('construction'); inner.is_connected = False
                    async def connect(inner): fail('connect'); inner.is_connected = True
                    @property
                    def services(inner): fail('services'); return Services()
                    async def disconnect(inner): raise RuntimeError('cleanup failed')
                    async def write_gatt_char(inner, *args, **kwargs): fail('write')
                class Scanner:
                    @staticmethod
                    async def find_device_by_filter(predicate, timeout):
                        fail('scan')
                        device = SimpleNamespace(name='LEDBLE-00-0806', address='FRESH-WINDOWS')
                        predicate(device, SimpleNamespace(local_name=device.name))
                        return device
                with patch.object(ledble_driver, '_diagnostic_callback', logs.append), patch.dict(
                    sys.modules, bleak=SimpleNamespace(BleakClient=Client, BleakScanner=Scanner)):
                    driver = LEDBLEDriver()
                    with self.assertRaises(OSError) as raised:
                        await driver.connect()
                        await driver.set_rgb(255, 0, 0)
                    self.assertIs(raised.exception, error)
                    expected = {'scan':'scan', 'construction':'BleakClient construction',
                                'connect':'client.connect (includes automatic GATT discovery)',
                                'services':'service discovery result (client.services)',
                                'FFE0':'FFE0 lookup','FFE1':'FFE1 lookup','write':'first write'}[failing]
                    self.assertTrue(any(line.startswith('LEDBLE_ERROR,' + expected + ',') for line in logs), logs)
                    self.assertTrue(any('winerror=-2147024838' in line for line in logs))

    @offline_async
    async def test_discovery_services_write_and_cleanup(self):
        char = SimpleNamespace(properties=['read', 'write', 'write-without-response', 'notify'])
        class Service:
            def get_characteristic(inner, uuid):
                self.assertEqual(uuid, LEDBLEDriver.WRITE_UUID)
                return char
        class Services:
            def get_service(inner, uuid):
                self.assertEqual(uuid, LEDBLEDriver.SERVICE_UUID)
                return Service()
        class Client:
            def __init__(inner, device, **options):
                self.assertIs(device, scanned[0])
                self.assertEqual(options, {"services": [LEDBLEDriver.SERVICE_UUID]})
                inner.is_connected = False; inner.services = Services(); inner.writes = []
            async def connect(inner): inner.is_connected = True
            async def disconnect(inner): inner.is_connected = False
            async def write_gatt_char(inner, characteristic, packet, response):
                self.assertIs(characteristic, char)
                inner.writes.append((packet, response))
        scanned = []
        class Scanner:
            @staticmethod
            async def find_device_by_filter(predicate, timeout):
                self.assertFalse(predicate(SimpleNamespace(name='LEDBLE-other'), SimpleNamespace(local_name=None)))
                device = SimpleNamespace(name=None, address='WINDOWS-SCAN-ADDRESS')
                self.assertTrue(predicate(device, SimpleNamespace(local_name='LEDBLE-00-0806')))
                scanned.append(device)
                return device
        with patch.dict(sys.modules, bleak=SimpleNamespace(BleakClient=Client, BleakScanner=Scanner)):
            driver = LEDBLEDriver()
            await driver.connect()
            client = driver.client
            self.assertEqual(client.writes, [])  # No unconfirmed power writes.
            await driver.set_rgb(255, 0, 0)
            self.assertEqual(client.writes, [(bytes.fromhex('7e070503ff000000ef'), False)])
            await driver.disconnect()
            self.assertFalse(client.is_connected)
            self.assertIsNone(driver.client)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path(__file__).with_name('olive_rgb.py').read_text(encoding='utf-8-sig'))
        worker = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'BluetoothWorker')
        self.clock = SimpleNamespace(monotonic=lambda: 10)
        self.sleeps = []
        async def sleep(seconds): self.sleeps.append(seconds)
        ns = dict(asyncio=SimpleNamespace(sleep=sleep), time=self.clock,
                  LEDBLEDriver=FakeLamp, LIGHT_UPDATE_INTERVAL=.25)
        exec(compile(ast.Module(body=[worker], type_ignores=[]), '<worker>', 'exec'), ns)
        self.worker = ns['BluetoothWorker'].__new__(ns['BluetoothWorker'])
        w = self.worker
        w.lotus_lamp = FakeLamp(); w.lamp = w.lotus_lamp
        w.device_family = 'LotusLamp Corner Lamp'; w.connected = False; w.connecting = False
        w.rgb_lock = asyncio.Lock(); w.last_rgb = None; w.last_send_time = 0
        w._debug = lambda message: None; w.log_callback = lambda message: None; w.status_callback = lambda message: None

    @offline_async
    async def test_original_and_strip_selection(self):
        w = self.worker
        await w._connect()
        self.assertIs(w.lamp, w.lotus_lamp)
        self.assertEqual(w.lotus_lamp.calls, ['connect'])
        await w._connect('LEDBLE Strip')
        self.assertEqual(w.lotus_lamp.calls, ['connect', 'disconnect'])
        strip = w.lamp
        await w._set_rgb(1, 2, 3)
        self.assertEqual(strip.calls, ['connect', (1, 2, 3)])
        await w._connect('LotusLamp Corner Lamp')
        self.assertEqual(strip.calls[-1], 'disconnect')
        self.assertIs(w.lamp, w.lotus_lamp)
        self.assertEqual(self.sleeps, [.75, .75, .75])

    @offline_async
    async def test_rate_limit_delta_refresh_and_clamping(self):
        w = self.worker; w.connected = True
        sent = []
        def submit(coroutine): sent.append(coroutine); coroutine.close()
        w._submit = submit
        w.set_rgb(-1, 999, 50)
        self.assertEqual(w.last_rgb, (0, 255, 50))
        self.clock.monotonic = lambda: 10.1
        w.set_rgb(100, 0, 0)
        self.assertEqual(len(sent), 1)
        self.clock.monotonic = lambda: 10.3
        w.set_rgb(1, 255, 50)
        self.assertEqual(len(sent), 1)
        self.clock.monotonic = lambda: 11.6
        w.set_rgb(1, 255, 50)
        self.assertEqual(len(sent), 2)

    def test_switch_waits_for_shared_rgb_lock(self):
        class Gate:
            def __await__(self):
                yield "waiting for RGB lock"
        class Locked:
            async def __aenter__(self): await Gate()
            async def __aexit__(self, *args): pass
        w = self.worker
        w.rgb_lock = Locked()
        task = w._connect('LEDBLE Strip')
        self.assertEqual(task.send(None), "waiting for RGB lock")
        self.assertFalse(w.connected)
        self.assertIs(w.lamp, w.lotus_lamp)
        self.assertEqual(w.lotus_lamp.calls, [])
        with self.assertRaises(StopIteration): task.send(None)
        self.assertTrue(w.connected)


if __name__ == '__main__':
    unittest.main()
