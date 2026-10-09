"""Mock-only Tk smoke check. Does not connect hardware or save real settings."""
import sys, asyncio, threading, time, queue
from pathlib import Path
project=Path(__file__).resolve().parent
sys.path.insert(0,str(project))
import olive_rgb as app_module
import tkinter as tk
from tkinter import ttk

class Worker:
    def __init__(self,*args):
        self.connected=False; self.calls=[];self.ready=threading.Event()
        self.loop=asyncio.new_event_loop()
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        asyncio.set_event_loop(self.loop);self.ready.set();self.loop.run_forever()
    def set_rgb(self,*args,**kwargs):self.calls.append((args,kwargs))
    async def _disconnect(self):self.connected=False
    def connect(self,*args):pass

class Artwork:
    def __init__(self):self.messages=queue.SimpleQueue()
    def set_enabled(self,value):pass
    def close(self):pass

class Driver:
    def __init__(self,identity,emit):
        self.identity=identity; self.emit=emit;self.connected=False
        self.capabilities=dict(power=True,brightness=True,color=False,temperature=True)
    async def connect(self):
        self.connected=True; self.emit('capabilities',self.capabilities)
    async def write(self,*args):pass
    async def disconnect(self):self.connected=False

saved=[]
app_module.load_app_settings=lambda:{}
app_module.save_app_settings=lambda value:saved.append(value)
app_module.BluetoothWorker=Worker
app_module.AlbumArtworkWorker=Artwork
app_module.LampGUI.get_monitors=lambda self:['1']
root=tk.Tk();root.attributes("-alpha",0)
app=app_module.LampGUI(root)
panel=app.hue_panel
panel.service.driver_factory=Driver
def pump(seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        root.update();time.sleep(.005)
pump(.2)
panel.service.request('connect');pump(.3)
assert panel.connected
assert str(panel.color_button.cget('state'))=='disabled'
assert str(panel.temperature_slider.cget('state'))=='normal'
panel.follow.set(True);panel.changed();pump(.1)
assert str(panel.power_button.cget('state'))=='disabled'
app.music.start=lambda:None
app.toggle_music();assert app.active_mode=='Music'
app.stop_modes()
panel.follow.set(False);panel.changed()
app.set_manual_color((25,75,150))
assert app.bluetooth.calls[-1][0]==(25,75,150)
app.music_relationship.set('Same Color')
app.music_separation.set(.7)
app.update_music_relationship()
app.save_settings()
assert saved[-1]['music_relationship']=='Same Color'
assert saved[-1]['music_separation']==.7
assert saved[-1]['hue']['identity']['name']=='Tv lamp'
assert not saved[-1]['hue']['follow_master']
nb=next(w for w in root.winfo_children() if isinstance(w,ttk.Notebook))
nb.select(nb.tabs()[1]);root.geometry('920x680');root.update()
# Geometry check without showing a window.
def descendants(w):
    for c in w.winfo_children():
        yield c
        yield from descendants(c)
for w in descendants(root):
    if isinstance(w,ttk.Combobox) and tuple(w.cget('values'))==app_module.RELATIONSHIPS:
        print('Relationship control geometry:',w.winfo_y(),w.winfo_height(),'parent height:',w.master.winfo_height()); assert w.winfo_height()>1; assert w.winfo_y()+w.winfo_height() <= w.master.winfo_height()

app.close()
until=time.monotonic()+5
while time.monotonic()<until:
    try:root.update()
    except tk.TclError:break
    if not app.bluetooth.thread.is_alive():break
    time.sleep(.01)
assert not app.bluetooth.thread.is_alive()
assert panel.service._async_task.done()
print('GUI creation, capability gating, Follow Master, Hue-only mode, settings export and shared-loop shutdown passed with mock Bluetooth.')

app_module.load_app_settings=lambda: saved[-1]
root=tk.Tk();root.withdraw()
app=app_module.LampGUI(root)
assert app.music_relationship.get()=='Same Color'
assert app.music_separation.get()==.7
assert app.lighting.relationship=='Same Color'
assert app.lighting.separation==.7
app.close()
until=time.monotonic()+5
while app.bluetooth.thread.is_alive() and time.monotonic()<until:
    root.update();time.sleep(.01)
assert not app.bluetooth.thread.is_alive()
print('Settings persisted through GUI reconstruction.')
