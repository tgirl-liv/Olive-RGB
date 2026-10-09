"""Use the pinned real HueBLE implementation with mocked Bleak I/O."""
import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch, AsyncMock
import hue_driver as hd


class HueApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_hueble_connect_capabilities_packets_and_no_hidden_reconnect(self):
        import HueBLE as hue
        data={hue.UUID_POWER:b'\x01',hue.UUID_BRIGHTNESS:b'\x80',
              hue.UUID_TEMPERATURE:(300).to_bytes(2,'little'),
              hue.UUID_XY_COLOUR:b'\x00\x40\x00\x40',
              hue.UUID_ZIGBEE_ADDRESS:b'\x01\x02\x03\x04\x05\x06\x07\x08'}
        writes=[]
        class Client:
            is_connected=True
            _backend=NS()
            services=NS(get_characteristic=lambda uuid: NS() if uuid in data else None)
            async def start_notify(self,uuid,callback):pass
            async def read_gatt_char(self,uuid):return data[uuid]
            async def write_gatt_char(self,uuid,value,response):writes.append((uuid,value,response))
            async def pair(self):raise AssertionError('Pairing must stay manual')
            async def disconnect(self):self.is_connected=False
        client=Client()
        scanned=NS(name='Tv lamp',address='FRESH',details=None)
        scan=AsyncMock(return_value={'fresh':(scanned,NS(local_name='Tv lamp'))})
        establish=AsyncMock(return_value=client)
        with patch('bleak.BleakScanner.discover',scan),patch.object(hue,'establish_connection',establish):
            driver=hd.HueDriver({'name':'Tv lamp'},lambda *args:None)
            await driver.connect()
            self.assertTrue(all(driver.capabilities.values()))
            self.assertIs(establish.call_args.kwargs['device'],scanned)
            self.assertEqual(establish.call_args.kwargs['max_attempts'],1)
            await driver.write('power',False)
            await driver.write('power',True)
            await driver.write('brightness',200)
            await driver.write('color',(255,0,0))
            await driver.write('temperature',300)
            self.assertEqual(writes[:3],[(hue.UUID_POWER,b'\x00',True),(hue.UUID_POWER,b'\x01',True),(hue.UUID_BRIGHTNESS,b'\xc8',True)])
            self.assertEqual(writes[3][0],hue.UUID_XY_COLOUR)
            self.assertEqual(len(writes[3][1]),4)
            client.is_connected=False
            with patch.object(asyncio,'create_task',side_effect=AssertionError('Untracked reconnect')):
                driver.light._disconnect_callback(client)
            with self.assertRaises(ConnectionError):await driver.light.connect()
            await driver.disconnect()


if __name__=='__main__':unittest.main()
