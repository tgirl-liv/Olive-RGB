"""Software-only Hue integration tests. No hardware or pairing operations."""
import asyncio
import sys
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import hue_driver as hd

STATE = dict(power=True, brightness=120, rgb=(255,0,0), mode='color', temperature=300)


class RouterTests(unittest.TestCase):
    def test_independent_state_survives_master_updates(self):
        hue=hd.HueService({'name':'Tv lamp'}, STATE)
        calls=[]
        router=hd.LightingRouter(NS(set_rgb=lambda *args,**kw:calls.append((args,kw))),hue)
        router.set_rgb(3,4,5,force=True)
        self.assertEqual(calls[-1],((3,4,5),{'force':True}))
        self.assertEqual(hue.desired()['color'],(255,0,0))
        hue.update(follow=True)
        router.set_master(False,.5)
        self.assertFalse(hue.desired()['power'])
        self.assertEqual(calls[-1][0],(0,0,0))
        router.set_master(True,.5)
        router.set_rgb(255,100,0)
        self.assertEqual(hue.desired()['brightness'],127)
        hue.update(follow=False)
        self.assertEqual(hue.desired(),dict(power=True,brightness=120,color=(255,0,0)))

    def test_black_and_rgb_conversion(self):
        for rgb in [(0,0,0),(255,0,0),(0,255,0),(0,0,255),(255,255,255)]:
            xy=hd.rgb_to_xy(rgb)
            self.assertTrue(all(0<=v<=1 for v in xy))
        service=hd.HueService({},STATE,True)
        service.update(master=dict(power=True,brightness=1,rgb=(0,0,0)))
        self.assertFalse(service.desired()['power'])


class DriverTests(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_capabilities_identity_and_supported_writes(self):
        scanned=NS(name='Tv lamp',address='FRESH',details=None)
        class Scanner:
            @staticmethod
            async def discover(**kwargs):
                return {'a':(scanned,NS(local_name='Tv lamp'))}
        class Light:
            supports_on_off=True; supports_brightness=True
            supports_colour_xy=False; supports_colour_temp=True
            minimum_mireds=153; maximum_mireds=500
            def __init__(inner, device): self.assertIs(device,scanned); inner.connected=False; inner.calls=[]
            async def connect(inner): inner.connected=True
            async def disconnect(inner): inner.connected=False
            async def poll_zigbee_address(inner): return 'stable-id'
            async def poll_power_state(inner): return True
            async def poll_brightness(inner): return 100
            async def poll_colour_xy(inner): raise AssertionError('White bulb has no color')
            async def poll_colour_temp(inner): return 300
            async def set_power(inner,value): inner.calls.append(('power',value))
            async def set_brightness(inner,value): inner.calls.append(('brightness',value))
            async def set_colour_temp(inner,value): inner.calls.append(('temperature',value))
            async def set_colour_xy(inner,*value): raise AssertionError('Unsupported RGB sent')
        with patch.dict(sys.modules,bleak=NS(BleakScanner=Scanner)),patch.object(hd,'managed_light_class',lambda:Light):
            driver=hd.HueDriver({'name':'Tv lamp'},lambda *args:None)
            await driver.connect()
            self.assertEqual(driver.identity['address_hint'],'FRESH')
            self.assertEqual(driver.identity['zigbee_address'],'stable-id')
            self.assertFalse(driver.capabilities['color'])
            await driver.write('power',False); await driver.write('power',True)
            await driver.write('brightness',999); await driver.write('color',(255,0,0))
            await driver.write('temperature',900)
            self.assertEqual(driver.light.calls,[('power',False),('power',True),('brightness',254),('temperature',500)])
            await driver.disconnect()
            driver=hd.HueDriver({'name':'Tv lamp','zigbee_address':'wrong'},lambda *args:None)
            with self.assertRaises(RuntimeError): await driver.connect()
            await driver.disconnect()


class ActorTests(unittest.IsolatedAsyncioTestCase):
    async def wait_until(self, condition, timeout=3):
        async with asyncio.timeout(timeout):
            while not condition(): await asyncio.sleep(.005)

    def actor(self, factory):
        service=hd.HueService({'name':'Tv lamp'},STATE,driver_factory=factory)
        service.RETRY_DELAY=.01; service.POLL_INTERVAL=.002
        service.start(asyncio.get_running_loop())
        service.request('connect')
        return service

    async def test_coalescing_serialization_fairness_and_cleanup(self):
        writes=[]; drivers=[]
        class Driver:
            def __init__(inner,identity,emit):
                inner.identity=identity;inner.connected=False;inner.busy=False
                inner.capabilities=dict(power=True,brightness=True,color=True,temperature=False)
                drivers.append(inner)
            async def connect(inner): inner.connected=True
            async def write(inner,key,value):
                self.assertFalse(inner.busy);inner.busy=True
                writes.append((key,value,time.monotonic()))
                await asyncio.sleep(.002);inner.busy=False
            async def disconnect(inner): inner.connected=False
        service=self.actor(Driver)
        try:
            await self.wait_until(lambda: service.connected)
            for value in range(1,201): service.update(independent=dict(STATE,brightness=value))
            await self.wait_until(lambda:any(k=='brightness' and v==200 for k,v,t in writes))
            await self.wait_until(lambda:any(k=='color' for k,v,t in writes))
            self.assertLessEqual(len(writes),4)
            self.assertTrue(all(b[2]-a[2]>=.249 for a,b in zip(writes,writes[1:])))
            # Repeated brightness changes must not starve color updates.
            for value in range(20):
                service.update(independent=dict(STATE,brightness=value+100,rgb=(0,0,255)))
                await asyncio.sleep(.02)
            await self.wait_until(lambda:any(k=='color' and v==(0,0,255) for k,v,t in writes))
        finally: await service.close_async()
        self.assertFalse(drivers[-1].connected)
        self.assertTrue(service._async_task.done())

    async def test_three_attempt_bound_and_corner_independence(self):
        attempts=[]
        class Driver:
            connected=False
            def __init__(inner,identity,emit): inner.identity=identity
            async def connect(inner): attempts.append(1); await asyncio.sleep(.01); raise RuntimeError('offline')
            async def disconnect(inner): pass
        service=self.actor(Driver)
        corner=[]
        router=hd.LightingRouter(NS(set_rgb=lambda *args,**kwargs:corner.append(args)),service)
        try:
            for i in range(50): router.set_rgb(i,0,0)
            await self.wait_until(lambda:len(attempts)==3)
            await asyncio.sleep(.06)
            self.assertEqual(len(attempts),3)
            self.assertEqual(len(corner),50)
        finally: await service.close_async()

    async def test_shutdown_cancels_connection_and_closes(self):
        started=asyncio.Event();closed=[]
        class Driver:
            connected=False
            def __init__(inner,identity,emit): inner.identity=identity
            async def connect(inner): started.set(); await asyncio.Event().wait()
            async def disconnect(inner): closed.append(True)
        service=self.actor(Driver)
        await started.wait()
        await asyncio.wait_for(service.close_async(),1)
        self.assertEqual(closed,[True])
        self.assertTrue(service._async_task.done())

    async def test_disconnect_loss_retry_cycle_stops(self):
        drivers=[]
        class Driver:
            capabilities={}
            def __init__(inner,identity,emit): inner.identity=identity;inner.connected=False;drivers.append(inner)
            async def connect(inner): inner.connected=True
            async def disconnect(inner): inner.connected=False
        service=self.actor(Driver)
        try:
            for count in range(1,4):
                await self.wait_until(lambda:len(drivers)==count and service.connected)
                drivers[-1].connected=False
            await asyncio.sleep(.08)
            self.assertEqual(len(drivers),3)
        finally: await service.close_async()


if __name__=='__main__': unittest.main()
