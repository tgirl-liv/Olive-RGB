"""Additive Hue/Master tab; all BLE remains on the existing worker loop."""
import asyncio
import queue
import tkinter as tk
from tkinter import ttk, colorchooser
from hue_driver import HueService
from music_coordination import MusicLightingRouter as LightingRouter


def number(value, default, low, high):
    try:
        value = float(value)
        return max(low, min(high, value)) if value == value else default
    except (ValueError, TypeError):
        return default


class HuePanel:
    def __init__(self, app, notebook):
        self.app = app
        self.root = app.root
        data = app.settings.get('hue', {})
        if not isinstance(data, dict): data = {}
        self.identity = data.get('identity', {})
        if not isinstance(self.identity, dict): self.identity = {}
        self.identity = {'name':'Tv lamp', **self.identity}
        if not isinstance(self.identity.get('name'), str): self.identity['name'] = 'Tv lamp'
        self.power = tk.BooleanVar(value=bool(data.get('power', True)))
        self.brightness = tk.DoubleVar(value=number(data.get('brightness'), 180, 1, 254))
        self.temperature = tk.DoubleVar(value=number(data.get('temperature'), 300, 153, 500))
        self.mode = tk.StringVar(value='temperature' if data.get('mode') == 'temperature' else 'color')
        color = data.get('rgb', [255,255,255])
        if not isinstance(color, (list,tuple)) or len(color)!=3: color=[255,255,255]
        self.rgb = tuple(int(number(c,255,0,255)) for c in color)
        self.follow = tk.BooleanVar(value=bool(data.get('follow_master',False)))
        master = app.settings.get('master', {})
        if not isinstance(master,dict): master={}
        self.master_power = tk.BooleanVar(value=bool(master.get('power',True)))
        self.master_brightness = tk.DoubleVar(value=number(master.get('brightness'),1,0,1))
        self.service = HueService(self.identity, self.independent(), self.follow.get())
        self.caps = {}
        self.connected = False
        self.save_job = self.master_job = None
        self.started = False
        tab = ttk.Frame(notebook, style='Paper.TFrame')
        notebook.add(tab, text='HUE / MASTER')
        left = ttk.Frame(tab, style='Paper.TFrame'); left.pack(side='left',fill='both',expand=True,padx=24,pady=20)
        right = ttk.Frame(tab, style='Paper.TFrame'); right.pack(side='left',fill='both',expand=True,padx=24,pady=20)
        ttk.Label(left,text='Philips Hue — Tv lamp',style='Section.TLabel').pack(anchor='w')
        self.status = ttk.Label(left,text='Disconnected',style='Card.TLabel'); self.status.pack(anchor='w',pady=6)
        self.identity_label = ttk.Label(left,text=self.identity['name'],style='Muted.Card.TLabel'); self.identity_label.pack(anchor='w')
        row=ttk.Frame(left,style='Paper.TFrame'); row.pack(fill='x',pady=8)
        ttk.Button(row,text='Connect / Reconnect',command=lambda:self.service.request('connect')).pack(side='left')
        ttk.Button(row,text='Disconnect',command=lambda:self.service.request('disconnect')).pack(side='left',padx=6)
        ttk.Checkbutton(left,text='Follow Master',variable=self.follow,command=self.changed).pack(anchor='w',pady=5)
        self.power_button=ttk.Checkbutton(left,text='Power on',variable=self.power,command=self.changed)
        self.power_button.pack(anchor='w',pady=5)
        ttk.Label(left,text='Brightness',style='Card.TLabel').pack(anchor='w')
        self.brightness_slider=ttk.Scale(left,from_=1,to=254,variable=self.brightness,command=self.changed)
        self.brightness_slider.pack(fill='x',pady=5)
        self.color_button=ttk.Button(left,text='Choose RGB color',command=self.choose_color)
        self.color_button.pack(fill='x',pady=5)
        self.color_radio=ttk.Radiobutton(left,text='Color',value='color',variable=self.mode,command=self.changed)
        self.color_radio.pack(anchor='w')
        self.white_radio=ttk.Radiobutton(left,text='White temperature',value='temperature',variable=self.mode,command=self.changed)
        self.white_radio.pack(anchor='w')
        self.temperature_slider=ttk.Scale(left,from_=153,to=500,variable=self.temperature,command=self.temperature_changed)
        self.temperature_slider.pack(fill='x',pady=5)
        self.features=ttk.Label(left,text='Connect to detect bulb capabilities.',style='Muted.Card.TLabel',wraplength=370)
        self.features.pack(anchor='w',pady=8)
        ttk.Label(right,text='MASTER LIGHTING',style='Section.TLabel').pack(anchor='w')
        ttk.Label(right,text='Corner lamp and Hue devices following Master.',style='Muted.Card.TLabel',wraplength=330).pack(anchor='w',pady=8)
        ttk.Checkbutton(right,text='Master power on',variable=self.master_power,command=self.master_changed).pack(anchor='w',pady=8)
        ttk.Label(right,text='Master brightness',style='Card.TLabel').pack(anchor='w')
        ttk.Scale(right,from_=0,to=1,variable=self.master_brightness,command=self.master_changed).pack(fill='x',pady=8)
        ttk.Button(right,text='Master color',command=app.choose_color).pack(fill='x',pady=8)
        ttk.Label(right,text='The existing Light presets and Music / Movie / Gaming modes also follow these Master settings. White-only Hue bulbs follow power and brightness; RGB is skipped.',style='Muted.Card.TLabel',wraplength=330).pack(anchor='w',pady=8)
        self.refresh_controls()

    def attach(self, worker):
        self.worker = worker
        self.router = LightingRouter(worker,self.service,self.master_power.get(),self.master_brightness.get())
        self.root.after(100,self.poll)
        return self.router

    def independent(self):
        return dict(power=self.power.get(),brightness=round(self.brightness.get()),
                    temperature=round(self.temperature.get()),rgb=self.rgb,mode=self.mode.get())

    def export(self):
        return {'hue':dict(self.independent(),identity=dict(self.identity),follow_master=self.follow.get()),
                'master':dict(power=self.master_power.get(),brightness=self.master_brightness.get())}

    def save_later(self):
        if self.save_job: self.root.after_cancel(self.save_job)
        self.save_job=self.root.after(400,self.app.save_settings)

    def changed(self, _=None):
        self.service.update(independent=self.independent(),follow=self.follow.get())
        self.refresh_controls()
        self.save_later()

    def temperature_changed(self, _=None):
        self.mode.set('temperature')
        self.changed()

    def choose_color(self):
        color,_=colorchooser.askcolor(color='#%02x%02x%02x'%self.rgb,parent=self.root)
        if color:
            self.rgb=tuple(round(c) for c in color)
            self.mode.set('color')
            self.changed()

    def master_changed(self, _=None):
        self.router.set_master(self.master_power.get(),self.master_brightness.get())
        # Send the final static-slider value after the existing corner limiter window.
        if self.master_job: self.root.after_cancel(self.master_job)
        self.master_job=self.root.after(300,lambda:self.router.set_master(self.master_power.get(),self.master_brightness.get()))
        self.save_later()

    def refresh_controls(self):
        independent=self.connected and not self.follow.get()
        for widget,key in ((self.power_button,'power'),(self.brightness_slider,'brightness'),
                           (self.color_button,'color'),(self.color_radio,'color'),
                           (self.white_radio,'temperature'),(self.temperature_slider,'temperature')):
            widget.configure(state='normal' if independent and self.caps.get(key) else 'disabled')

    def poll(self):
        if self.app.closing: return
        if not self.started and self.worker.ready.is_set() and self.worker.loop and self.worker.loop.is_running():
            self.service.start(self.worker.loop)
            self.started=True
        while True:
            try: kind,value=self.service.events.get_nowait()
            except queue.Empty: break
            if kind=='status':
                self.connected=value=='Connected'
                self.status.configure(text=value)
                self.refresh_controls()
            elif kind=='capabilities':
                self.caps=value
                if value.get('temperature') and not value.get('color'):
                    self.mode.set('temperature')
                    self.service.update(independent=self.independent())
                elif value.get('color') and not value.get('temperature'):
                    self.mode.set('color')
                    self.service.update(independent=self.independent())
                text=', '.join(key for key,enabled in value.items() if enabled)
                self.features.configure(text='Detected: '+text if text else 'Capabilities unavailable until connected.')
                self.refresh_controls()
            elif kind=='identity':
                self.identity=value
                self.identity_label.configure(text=value['name']+' / '+value.get('address_hint',''))
                self.save_later()
            elif kind=='log': self.app.log(value)
        self.root.after(100,self.poll)

    def shutdown(self):
        if self.save_job: self.root.after_cancel(self.save_job)
        if self.master_job: self.root.after_cancel(self.master_job)
        loop=self.worker.loop
        if not loop or not loop.is_running():
            self.root.destroy(); return
        async def finish():
            await asyncio.gather(self.service.close_async(),
                                 asyncio.wait_for(self.worker._disconnect(),5), return_exceptions=True)
            pending=[t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in pending: task.cancel()
            if pending:
                await asyncio.wait_for(asyncio.gather(*pending,return_exceptions=True),3)
        future=asyncio.run_coroutine_threadsafe(finish(),loop)
        def wait():
            if not future.done(): self.root.after(50,wait); return
            try: future.result()
            except Exception as error: self.app.log(f'Bluetooth shutdown: {error}')
            loop.call_soon_threadsafe(loop.stop)
            self.root.after(50,join)
        def join():
            if self.worker.thread.is_alive(): self.root.after(50,join); return
            if not loop.is_closed(): loop.close()
            self.root.destroy()
        self.root.after(50,wait)
