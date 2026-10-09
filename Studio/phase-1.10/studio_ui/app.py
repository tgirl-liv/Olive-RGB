"""Dark-neon mock dashboard. Imports only standard-library preview modules."""
import math
import time
import tkinter as tk
from tkinter import ttk
from .state import StudioState, NAVIGATION, SCENES
from .theme import (SPACE, TYPE, RADIUS, FRAME_MS, FONT_FAMILY, SIDEBAR, WELL,
                    SELECTED, HOVER, FOCUS, font, COMPACT_NAV_BREAKPOINT, SCENE_COLUMNS_BREAKPOINT)
from .widgets import BG, PANEL, RAISED, LINE, TEXT, MUTED, PINK, PURPLE, CYAN
from .widgets import ScrollArea, Reactor, ColorWheel, ScenePad, NeonSlider, NeonButton, blend


def label(parent,text,size=10,color=TEXT,bold=False,bg=None):
    return tk.Label(parent,text=text,bg=bg or parent.cget('bg'),fg=color,
                    font=font(size,bold),anchor='w')


class StudioPreview:
    FRAME_MS=FRAME_MS  # One root-owned scheduler, shared theme timing.

    def __init__(self,root,state=None):
        self.root=root;self.state=state or StudioState()
        self.closed=False;self.after_id=None;self.started=time.monotonic()
        self.phase=0.;self.last_tick=self.started;self.transition=None
        self.display_colors={k:v.color for k,v in self.state.channels.items()}
        self.refreshing=False;self.scene_pads={};self.nav_buttons={}
        root.title('Olive RGB Studio 1.3 · DEMO preview')
        root.geometry('1440x900');root.minsize(800,600);root.configure(bg=BG)
        root.protocol('WM_DELETE_WINDOW',self.close)
        self._styles()
        root.columnconfigure(1,weight=1);root.rowconfigure(1,weight=1)
        self._sidebar()
        header=tk.Frame(root,bg=BG);header.grid(row=0,column=1,columnspan=2,sticky='ew',padx=20,pady=(12,8))
        self.heading=label(header,'Music Studio',22,bold=True);self.heading.pack(side='left')
        NeonButton(header,text='▦  Scenes',width=88,height=28,command=lambda:self.navigate('Scenes')).pack(side='left',padx=SPACE['lg'])
        label(header,'DEMO  /  MOCK DEVICES',9,CYAN,True).pack(side='right')
        self.center=ScrollArea(root);self.center.grid(row=1,column=1,sticky='nsew',padx=(18,10))
        self.inspector_shell=tk.Frame(root,bg=PANEL,width=350)
        self.inspector_shell.grid(row=1,column=2,sticky='nsew',padx=(4,16),pady=(0,8))
        self.inspector_shell.grid_propagate(False)
        self.inspector_shell.columnconfigure(0,weight=1);self.inspector_shell.rowconfigure(2,weight=1)
        self._inspector()
        self._build_center()
        footer=tk.Frame(root,bg=BG);footer.grid(row=2,column=1,columnspan=2,sticky='ew',padx=20,pady=(5,10))
        self.notice=label(footer,'Preview only · no Bluetooth, audio capture, or saved settings',9,MUTED)
        self.notice.pack(side='left')
        self.nav_tooltip=label(root,'',9,TEXT,bg=RAISED)
        self.nav_tooltip.configure(padx=SPACE['sm'],pady=SPACE['xs'],highlightbackground=FOCUS,highlightthickness=1)
        self._refresh()
        root.bind('<Configure>',self._resize)
        root.bind('<MouseWheel>',self._scroll_wheel)
        root.bind('<FocusIn>',self._reveal_focus)
        for index,page in enumerate(NAVIGATION,1):root.bind(f'<Alt-Key-{index}>',lambda _,name=page:self.navigate(name))
        self.after_id=root.after(self.FRAME_MS,self._tick)

    def _styles(self):
        style=ttk.Style(self.root);style.theme_use('clam')
        style.configure('.',background=PANEL,foreground=TEXT,font=TYPE['body'],borderwidth=0)
        style.configure('TButton',background=RAISED,foreground=TEXT,padding=(SPACE['md'],SPACE['sm']),borderwidth=0,lightcolor=LINE,darkcolor=LINE,bordercolor=LINE)
        style.map('TButton',background=[('active',HOVER)])
        style.configure('Accent.TButton',background='#6544A3',foreground='white')
        style.configure('TCheckbutton',background=PANEL,foreground=MUTED)
        style.map('TCheckbutton',background=[('active',PANEL)])
        style.configure('TCombobox',fieldbackground=RAISED,background=RAISED,foreground=TEXT,arrowcolor=MUTED,padding=5)
        style.map('TCombobox',fieldbackground=[('readonly',RAISED)],foreground=[('readonly',TEXT)])
        style.configure('TEntry',fieldbackground=RAISED,foreground=TEXT,insertcolor=TEXT,padding=6,bordercolor=LINE,lightcolor=LINE,darkcolor=LINE)
        style.configure('Horizontal.TScale',background=PANEL,troughcolor=RAISED,sliderlength=14)
        style.configure('Vertical.TScrollbar',background=LINE,troughcolor=BG,arrowcolor=MUTED,width=9,bordercolor=BG,lightcolor=LINE,darkcolor=LINE,arrowsize=9)
        self.root.option_add('*TCombobox*Listbox.background',RAISED)
        self.root.option_add('*TCombobox*Listbox.foreground',TEXT)

    def _resize(self,event):
        if event.widget is not self.root:return
        width=event.width
        self.inspector_shell.configure(width=350 if width>=1400 else 320 if width>=1200 else 300 if width>=1000 else 264)
        compact=width<COMPACT_NAV_BREAKPOINT
        self.sidebar.configure(width=72 if compact else 144)
        self.brand.itemconfigure('brand-sub',text='RGB' if compact else 'RGB / MUSIC STUDIO')
        self.brand.itemconfigure('brand-name',state='hidden' if compact else 'normal')
        for name,button in self.nav_buttons.items():button.configure(text=self.nav_icons[name] if compact else f'{self.nav_icons[name]}   {name}',anchor='center' if compact else 'w')
        for text in self.sidebar_status:
            if compact:text.pack_forget()
            elif not text.winfo_manager():text.pack(side='bottom',anchor='w',padx=12,pady=5)
        if self.reactor:self.reactor.configure(height=190 if event.height>=850 else 170)

    def _reveal_focus(self,event):
        widget=event.widget
        for area in (self.center,self.inspect_scroll):
            parent=widget
            while parent is not None and parent is not area.body:parent=getattr(parent,'master',None)
            if parent is None:continue
            y=widget.winfo_rooty()-area.body.winfo_rooty();bottom=y+widget.winfo_height()
            top=area.canvas.canvasy(0);height=area.canvas.winfo_height();total=max(1,area.body.winfo_height())
            if y<top:area.canvas.yview_moveto(max(0,y-8)/total)
            elif bottom>top+height:area.canvas.yview_moveto((bottom-height+8)/total)

    def _scroll_wheel(self,event):
        widget=self.root.winfo_containing(event.x_root,event.y_root)
        while widget:
            if widget is self.center.canvas or widget is self.inspect_scroll.canvas:
                widget.yview_scroll(-1 if event.delta>0 else 1,'units');return 'break'
            widget=widget.master

    def _sidebar(self):
        side=tk.Frame(self.root,bg=SIDEBAR,width=152);self.sidebar=side
        side.grid(row=0,column=0,rowspan=3,sticky='ns');side.pack_propagate(False)
        brand=tk.Canvas(side,height=74,bg=SIDEBAR,highlightthickness=0);self.brand=brand
        brand.pack(fill='x',pady=(14,4))
        brand.create_rectangle(16,9,46,39,fill='#7935DB',outline=PURPLE)
        for i in range(5):brand.create_line(22+i*4,24-(i%3+1)*3,22+i*4,24+(i%3+1)*3,fill=TEXT,width=2)
        brand.create_text(55,24,text='OLIVE',tags='brand-name',anchor='w',fill=TEXT,font=('Segoe UI',15,'bold'))
        brand.create_text(18,58,text='RGB  /  MUSIC STUDIO',tags='brand-sub',anchor='w',fill=PINK,font=('Segoe UI',8,'bold'))
        icons={'Studio':'⌂','Music':'♫','Devices':'◉','Scenes':'▦','Screen':'▣','Settings':'⚙'};self.nav_icons=icons
        for name in NAVIGATION:
            button=tk.Button(side,text=f'{icons[name]}   {name}',anchor='w',bg=SIDEBAR,fg=MUTED,activebackground=RAISED,
                             activeforeground=TEXT,relief='flat',bd=0,padx=12,pady=14,
                             font=('Segoe UI',11),cursor='hand2',command=lambda n=name:self.navigate(n))
            button.pack(fill='x',padx=8,pady=3);self.nav_buttons[name]=button
            button.bind('<Enter>',lambda _,n=name:self._nav_hint(n))
            button.bind('<Leave>',lambda _:self._nav_hint(None))
            button.bind('<FocusIn>',lambda _,n=name:self._nav_hint(n))
            button.bind('<FocusOut>',lambda _:self._nav_hint(None))
        self.sidebar_status=[]
        for text in ('DEMO ONLY','●  Hue · simulated','●  Corner · simulated'):
            item=label(side,text,8,CYAN if text=='DEMO ONLY' else MUTED);item.pack(side='bottom',anchor='w',padx=12,pady=5);self.sidebar_status.append(item)

    def _nav_hint(self,name):
        if not hasattr(self,'nav_tooltip'):return
        if name is None or self.sidebar.winfo_width()>100:self.nav_tooltip.place_forget();return
        button=self.nav_buttons[name]
        self.nav_tooltip.configure(text=f'{name} · Alt+{NAVIGATION.index(name)+1}')
        self.nav_tooltip.place(x=self.sidebar.winfo_width()+8,y=button.winfo_rooty()-self.root.winfo_rooty()+8)
        self.nav_tooltip.lift()

    def _card(self,title,kicker=None):
        box=tk.Frame(self.center.body,bg=PANEL,highlightbackground=LINE,highlightthickness=1)
        box.pack(fill='x',pady=(0,8))
        top=tk.Frame(box,bg=PANEL);top.pack(fill='x',padx=SPACE['lg'],pady=(SPACE['sm'],SPACE['xs']))
        label(top,title,11,bold=True).pack(side='left')
        if kicker:
            caption=label(top,kicker,8,MUTED);caption.pack(side='right')
            def adapt(event):
                if event.width<650:caption.pack_forget()
                elif not caption.winfo_manager():caption.pack(side='right')
            top.bind('<Configure>',adapt)
        body=tk.Frame(box,bg=PANEL);body.pack(fill='both',expand=True,padx=SPACE['lg'],pady=(0,SPACE['sm']))
        return body

    def _combo(self,parent,variable,values,command):
        widget=ttk.Combobox(parent,textvariable=variable,values=values,state='readonly',width=16)
        widget.bind('<<ComboboxSelected>>',lambda _:command(variable.get()))
        return widget

    def _scale(self,parent,value,command,low=0,high=1):
        return NeonSlider(parent,value=value,command=command,low=low,high=high)

    def _build_center(self):
        for child in self.center.body.winfo_children():child.destroy()
        self.scene_pads={};self.channel_labels={};self.reactor=None
        self.master_value=None;self.play_button=None;self.screen_preview=None;self.transition_button=None
        page=self.state.page
        self.heading.configure(text={'Studio':'Music Studio','Music':'Audio & motion','Devices':'Device channels',
                                     'Screen':'Screen lab','Scenes':'Scene library','Settings':'Preview settings'}[page])
        self._master()
        if page in ('Studio','Music'):self._audio()
        if page in ('Studio','Scenes'):self._scenes()
        if page in ('Studio','Devices'):self._channels()
        if page=='Music':self._music_settings()
        if page=='Screen':self._screen()
        if page=='Settings':self._settings()
        self._refresh()

    def _master(self):
        body=tk.Frame(self.center.body,bg=PANEL,highlightbackground=LINE,highlightthickness=1)
        body.pack(fill='x',pady=(0,10))
        row=tk.Frame(body,bg=PANEL);row.pack(fill='x',padx=10,pady=10)
        self.master_button=NeonButton(row,text='⏻',command=self.toggle_master,width=40,height=40,accent=True)
        self.master_button.pack(side='left',padx=(0,10))
        label(row,'MASTER BUS',10,bold=True).pack(side='left')
        brightness=tk.Frame(row,bg=PANEL);brightness.pack(side='left',fill='x',expand=True,padx=12)
        self.master_value=label(brightness,f'{self.state.master_brightness:.0%}',9,MUTED)
        self.master_value.pack(side='right',padx=(6,0))
        self.master_slider=self._scale(brightness,self.state.master_brightness,self.set_brightness)
        self.master_slider.pack(side='left',fill='x',expand=True)
        modes=tk.Frame(body,bg=PANEL);self.mode_buttons={}
        for name in ('Manual','Music','Screen'):
            button=NeonButton(modes,text=name,width=59,height=30,accent=self.state.mode==name,command=lambda n=name:self.set_mode(n))
            button.pack(side='left',padx=1);self.mode_buttons[name]=button
        self.master_swatch=label(row,'●',19,self.state.channels['Corner'].color)
        self.master_swatch.pack(side='right',padx=2)
        previous=[None]
        def resize(event):
            wide=event.width>=680
            if previous[0]==wide:return
            previous[0]=wide;modes.pack_forget()
            if wide:modes.pack(in_=row,side='right',padx=5,before=self.master_swatch)
            else:modes.pack(anchor='e',padx=12,pady=(0,8))
        body.bind('<Configure>',resize)
        modes.pack(anchor='e',padx=12,pady=(0,8))

    def _audio(self):
        body=self._card('♫  AUDIO REACTOR','SPECTRUM + WAVEFORM · DEMO')
        self.reactor=Reactor(body);self.reactor.configure(height=190 if self.root.winfo_height()>=850 else 170);self.reactor.pack(fill='x')
        levels=tk.Frame(body,bg=PANEL);levels.pack(fill='x',pady=(7,0));self.level_labels=[];self.level_bars=[]
        for i,(name,color) in enumerate((('BASS',PURPLE),('MIDS',PINK),('TREBLE',CYAN),('OVERALL','#CEC4FF'))):
            cell=tk.Frame(levels,bg=PANEL);cell.grid(row=0,column=i,sticky='ew',padx=4);levels.columnconfigure(i,weight=1,uniform='levels')
            text=label(cell,name+'  0%',8,color);text.pack(anchor='w');self.level_labels.append((text,name))
            bar=tk.Canvas(cell,height=9,width=50,bg=RAISED,highlightthickness=0);bar.pack(fill='x',pady=(3,0));self.level_bars.append((bar,color))
        top=body.master.winfo_children()[0]
        # Playback lives in the reactor header to keep the workspace compact.
        self.play_button=NeonButton(top,command=self.toggle_play,width=85,height=24)
        self.play_button.pack(side='right',padx=5)

    def _scenes(self):
        body=self._card('▦  SCENE LAUNCH PADS','LOCAL CANVAS ART')
        tools=tk.Frame(body.master,bg=PANEL);tools.pack(in_=body,fill='x',pady=(0,7))
        top=body.master.winfo_children()[0]
        location=[None]
        def place_tools(event):
            wide=event.width>=650
            if location[0]==wide:return
            location[0]=wide;tools.pack_forget()
            if wide:tools.pack(in_=top,side='right',padx=5)
            else:tools.pack(in_=body,fill='x',pady=(0,7),before=grid)
        top.bind('<Configure>',place_tools,add='+')
        NeonButton(tools,text='All Scenes' if self.state.favorites_only else '★ Favorites',command=self.toggle_filter,width=94,height=26).pack(side='left')
        self.transition_button=NeonButton(tools,text=f'Transition · {self.state.transition_seconds:.1f}s',command=lambda:self.show_inspector('Setup'),width=140,height=26)
        self.transition_button.pack(side='right')
        grid=tk.Frame(body,bg=PANEL);grid.pack(fill='x');grid.columnconfigure((0,1),weight=1,uniform='pads')
        names=[n for n in SCENES if not self.state.favorites_only or n in self.state.favorites]
        if not names:label(grid,'No favorites yet. Select All Scenes to add one.',9,MUTED).pack(pady=14)
        for i,name in enumerate(names):
            pad=ScenePad(grid,name,SCENES[name],self.select_scene,self.toggle_favorite)
            pad.configure(height=104)
            pad.grid(row=i//2,column=i%2,sticky='ew',padx=(0,6),pady=(0,6));self.scene_pads[name]=pad
        def reflow(event):
            columns=4 if event.width>=SCENE_COLUMNS_BREAKPOINT else 2
            for col in range(4):grid.columnconfigure(col,weight=1 if col<columns else 0,uniform='pads' if col<columns else '')
            for i,pad in enumerate(self.scene_pads.values()):pad.grid(row=i//columns,column=i%columns,sticky='ew',padx=(0,6) if i%columns<columns-1 else 0,pady=(0,6))
        grid.bind('<Configure>',reflow)
        self.transition_choices=tk.Frame(body,bg=PANEL);self.transition_choices.pack(fill='x',pady=(3,0))
        label(self.transition_choices,'FADE',8,MUTED).pack(side='left',padx=(0,5))
        self.transition_options=[]
        for seconds in (0,.5,1,2,5):
            button=NeonButton(self.transition_choices,text='Instant' if seconds==0 else f'{seconds:g}s',width=50,height=25,
                              command=lambda v=seconds:self.transition_preset(v))
            button.pack(side='left',fill='x',expand=True,padx=2);self.transition_options.append((seconds,button))
        self._transition_text()

    def _channels(self):
        body=self._card('▱  DEVICE CHANNELS','MOCK OUTPUTS');self.channel_rows={};self.channel_follow={};self.channel_sliders={}
        for key,channel in self.state.channels.items():
            row=tk.Frame(body,bg=WELL,highlightbackground=PURPLE if key==self.state.selected_channel else LINE,highlightthickness=1)
            row.pack(fill='x',pady=(0,5));self.channel_rows[key]=row
            head=tk.Frame(row,bg=WELL);head.pack(fill='x',padx=8,pady=(5,2))
            dot=label(head,'◉' if key=='Hue' else '⊥',19,channel.color);dot.pack(side='left',padx=(0,8))
            NeonButton(head,text=channel.name,command=lambda k=key:self.choose_channel(k),width=110,height=27).pack(side='left')
            status=label(head,'RGB · simulated',8,MUTED);status.pack(side='left',padx=10)
            power=NeonButton(head,text='On' if channel.power else 'Off',width=38,height=26,command=lambda k=key:self.toggle_channel(k));power.pack(side='right')
            lower=tk.Frame(row,bg=WELL)
            follow=tk.BooleanVar(value=channel.follow);self.channel_follow[key]=follow
            ttk.Checkbutton(lower,text='Follow Master',variable=follow,command=lambda k=key,v=follow:self.set_follow(k,v.get())).pack(side='left')
            slider=self._scale(lower,channel.brightness,lambda v,k=key:self.set_channel_brightness(k,v));slider.pack(side='left',fill='x',expand=True,padx=(12,2));self.channel_sliders[key]=slider
            self.channel_labels[key]=(dot,status,power)
            def reflow(event,container=row,heading=head,detail=lower,power_button=power):
                wide=event.width>=650
                if getattr(container,'wide',None)==wide:return
                container.wide=wide;detail.pack_forget()
                if wide:detail.pack(in_=heading,side='right',fill='x',expand=True,padx=(8,6),before=power_button)
                else:detail.pack(fill='x',padx=8,pady=(0,5))
            row.bind('<Configure>',reflow)
            lower.pack(fill='x',padx=8,pady=(0,4))

    def _music_settings(self):
        body=self._card('MUSIC CHARACTER','MOCK PARAMETERS')
        for name,attr in (('Sensitivity','sensitivity'),('Smoothing','smoothing')):
            label(body,name,10,MUTED).pack(anchor='w',pady=(7,0))
            self._scale(body,getattr(self.state,attr),lambda v,a=attr:self.set_parameter(a,v)).pack(fill='x')
        ttk.Button(body,text='Edit color relationship →',command=lambda:self.show_inspector('Music')).pack(anchor='w',pady=(12,0))

    def _screen(self):
        body=self._card('SCREEN PREVIEW','GENERATED COLOR FIELD')
        self.screen_preview=tk.Canvas(body,height=200,bg=RAISED,highlightthickness=0)
        self.screen_preview.pack(fill='x')
        label(body,'Synthetic display only. Nothing on your screen is captured.',9,MUTED).pack(anchor='w',pady=10)
        self.screen_var=tk.StringVar(value=self.state.screen_source)
        self._combo(body,self.screen_var,('Demo display 1','Demo display 2'),lambda v:self.set_parameter('screen_source',v)).pack(fill='x')
        label(body,'Intensity',10,MUTED).pack(anchor='w',pady=(12,0))
        self._scale(body,self.state.screen_intensity,lambda v:self.set_parameter('screen_intensity',v)).pack(fill='x')

    def _settings(self):
        body=self._card('DESIGN SANDBOX','PHASE 1')
        label(body,'Everything here resets when the preview closes.',10,MUTED).pack(anchor='w',pady=6)
        motion=tk.BooleanVar(value=self.state.motion)
        ttk.Checkbutton(body,text='Animate the synthetic signal',variable=motion,
                        command=lambda:self.set_parameter('motion',motion.get())).pack(anchor='w',pady=10)
        ttk.Button(body,text='Reset demo state',command=self.reset).pack(anchor='w',pady=10)
        label(body,'No devices paired. No inputs opened. No settings written.',9,MUTED).pack(anchor='w',pady=10)

    def _inspector(self):
        top=tk.Frame(self.inspector_shell,bg=PANEL);top.grid(row=0,column=0,sticky='ew',padx=16,pady=(16,12))
        label(top,'◉  DEVICE INSPECTOR',10,TEXT,True).pack(anchor='w')
        self.target_var=tk.StringVar(value=self.state.selected_channel)
        self._combo(top,self.target_var,tuple(self.state.channels),self.choose_channel).pack(fill='x',pady=(8,0))
        self.selected_name=label(top,'',13,TEXT,True);self.selected_name.pack(anchor='w',pady=(10,3))
        label(top,'●  Simulated RGB device · DEMO',8,CYAN).pack(anchor='w')
        tabs=tk.Frame(self.inspector_shell,bg=PANEL);tabs.grid(row=1,column=0,sticky='ew',padx=10)
        self.tab_buttons={}
        for name in ('Color','Music','Setup'):
            b=ttk.Button(tabs,text=name,width=6,command=lambda n=name:self.show_inspector(n))
            b.pack(side='left',expand=True,fill='x',padx=2);self.tab_buttons[name]=b
        self.inspect_scroll=ScrollArea(self.inspector_shell,PANEL)
        self.inspect_scroll.grid(row=2,column=0,sticky='nsew',padx=10,pady=12)
        self._inspector_body()

    def _inspector_body(self):
        body=self.inspect_scroll.body
        for w in body.winfo_children():w.destroy()
        self.wheel=None;self.color_error=None;self.transition_label=None;self.inspect_power=None;self.mixer_sliders=[]
        self.selected_name.configure(text=('◉  ' if self.state.selected_channel=='Hue' else '⊥  ')+self.state.channels[self.state.selected_channel].name)
        for n,b in self.tab_buttons.items():b.configure(style='Accent.TButton' if n==self.state.inspector else 'TButton')
        if self.state.inspector=='Color':
            label(body,'COLOR LAB',10,bold=True).pack(anchor='w',padx=6,pady=(4,0))
            lab=tk.Frame(body,bg=PANEL);lab.pack(fill='x')
            self.value_var=tk.DoubleVar(value=self.state.get_hsv()[2])
            NeonSlider(lab,variable=self.value_var,vertical=True,command=lambda v:self.set_hsv(*self.state.get_hsv()[:2],v)).pack(side='right',fill='y',padx=(4,4),pady=15)
            self.wheel=ColorWheel(lab,self.set_hsv);self.wheel.pack(side='left',fill='x',expand=True)
            modes=tk.Frame(body,bg=PANEL);modes.pack(fill='x',padx=6,pady=(4,8))
            self.color_mode_buttons={};self.color_frames={}
            for name in ('HSV','RGB','HEX'):
                button=NeonButton(modes,text=name,width=60,height=27,command=lambda n=name:self.set_color_mode(n))
                button.pack(side='left',fill='x',expand=True);self.color_mode_buttons[name]=button
            editors=tk.Frame(body,bg=PANEL);editors.pack(fill='x',padx=6)
            self.hsv_vars=[];self.hsv_labels=[]
            hsv=tk.Frame(editors,bg=PANEL);self.color_frames['HSV']=hsv
            for name,value,high in zip(('Hue','Saturation','Value'),self.state.get_hsv(),(360,100,100)):
                row=tk.Frame(hsv,bg=PANEL);row.pack(fill='x',pady=2)
                label(row,name,9,MUTED).pack(side='left')
                text=label(row,'',9,TEXT);text.configure(width=5,anchor='e',font=TYPE['numeric']);text.pack(side='right',padx=(SPACE['sm'],0))
                var=tk.DoubleVar(value=value*high);self.hsv_vars.append(var);self.hsv_labels.append(text)
                NeonSlider(row,low=0,high=high,variable=var,command=lambda _:self.hsv_changed()).pack(side='left',fill='x',expand=True)
            rgb=tk.Frame(editors,bg=PANEL);self.color_frames['RGB']=rgb;self.rgb_vars=[]
            for name in ('Red','Green','Blue'):
                row=tk.Frame(rgb,bg=PANEL);row.pack(fill='x',pady=2)
                label(row,name,9,MUTED).pack(side='left');var=tk.StringVar();self.rgb_vars.append(var)
                entry=ttk.Entry(row,textvariable=var,width=8);entry.pack(side='right');entry.bind('<Return>',lambda _:self.apply_rgb())
            NeonButton(rgb,text='Apply RGB',command=self.apply_rgb,width=100,height=27).pack(anchor='e',pady=4)
            hex_frame=tk.Frame(editors,bg=PANEL);self.color_frames['HEX']=hex_frame
            label(hex_frame,'HEX COLOR',8,MUTED,True).pack(anchor='w')
            self.hex_var=tk.StringVar(value=self.state.channels[self.state.selected_channel].color)
            row=tk.Frame(hex_frame,bg=PANEL);row.pack(fill='x',pady=6)
            entry=ttk.Entry(row,textvariable=self.hex_var,width=10);entry.pack(side='left',fill='x',expand=True)
            entry.bind('<Return>',lambda _:self.apply_hex())
            NeonButton(row,text='Apply',width=60,height=28,command=self.apply_hex).pack(side='right',padx=(5,0))
            self.color_error=label(body,'',8,PINK);self.color_error.pack(anchor='w',padx=6)
            self.set_color_mode(getattr(self,'color_mode','HSV'))
            label(body,'Quick Swatches',9,TEXT).pack(anchor='w',padx=6,pady=(2,6))
            row=tk.Frame(body,bg=PANEL);row.pack(fill='x',padx=6)
            for c in ('#F521D8','#BD68FF','#2C58FF','#35DDEA','#34ECC5','#FFBA29','#FF416F','#F5F0FF'):
                button=tk.Button(row,bg=c,activebackground=c,width=2,relief='flat',bd=0,takefocus=True,command=lambda color=c:self.swatch(color))
                button.pack(side='left',expand=True,padx=2)
            self.mixer_button=NeonButton(body,text='Advanced Mixer  +',command=self.toggle_mixer,width=210,height=30)
            self.mixer_button.pack(fill='x',padx=SPACE['sm'],pady=(SPACE['md'],0))
            self.mixer=tk.Frame(body,bg=RAISED);self.mixer_open=False
            for index,name in enumerate(('Red','Green','Blue')):
                label(self.mixer,name,8,MUTED).pack(anchor='w',padx=8)
                slider=self._scale(self.mixer,int(self.state.channels[self.state.selected_channel].color[1+index*2:3+index*2],16),lambda v,i=index:self.mix_component(i,v),0,255);slider.pack(fill='x',padx=8);self.mixer_sliders.append(slider)
            self._sync_color()
        elif self.state.inspector=='Music':
            label(body,'Color relationship',12,bold=True).pack(anchor='w',padx=6,pady=(6,12))
            relationship=tk.StringVar(value=self.state.relationship)
            self._combo(body,relationship,('Same Color','Coordinated Colors','Independent Devices'),lambda v:self.set_parameter('relationship',v)).pack(fill='x',padx=6)
            label(body,'Color separation',10,MUTED).pack(anchor='w',padx=6,pady=(18,4))
            self._scale(body,self.state.separation,lambda v:self.set_parameter('separation',v)).pack(fill='x',padx=6)
            label(body,'Analogous  ← →  Complementary',8,MUTED).pack(anchor='w',padx=6,pady=4)
            for name,attr in (('Sensitivity','sensitivity'),('Smoothing','smoothing')):
                label(body,name,10,MUTED).pack(anchor='w',padx=6,pady=(18,4))
                self._scale(body,getattr(self.state,attr),lambda v,a=attr:self.set_parameter(a,v)).pack(fill='x',padx=6)
            tk.Label(body,text='Shared synthetic signal. These controls store demo values only.',wraplength=220,justify='left',bg=PANEL,fg=MUTED,font=('Segoe UI',9)).pack(padx=6,pady=22,anchor='w')
        else:
            label(body,'SCENE TRANSITION',10,bold=True).pack(anchor='w',padx=6,pady=8)
            self.transition_label=label(body,'',10,MUTED);self.transition_label.pack(anchor='w',padx=6,pady=(8,4))
            self._scale(body,self.state.transition_seconds,self.set_transition_seconds,0,5).pack(fill='x',padx=6)
            for value in (0,.5,1,2,5):
                NeonButton(body,text='Instant' if value==0 else f'Fade {value:g} seconds',width=200,height=30,
                           command=lambda v=value:self.transition_preset(v)).pack(fill='x',padx=6,pady=2)
            curve=tk.StringVar(value=self.state.transition_curve)
            self._combo(body,curve,('Smooth','Linear','Instant'),self.set_curve).pack(fill='x',padx=6,pady=12)
            motion=tk.BooleanVar(value=not self.state.motion)
            ttk.Checkbutton(body,text='Reduced Motion',variable=motion,command=lambda:self.set_parameter('motion',not motion.get())).pack(anchor='w',padx=6,pady=12)
            label(body,'●  MOCK CONNECTIONS ONLY',8,CYAN,True).pack(anchor='w',padx=6,pady=(8,12))
            self._transition_text()
        self._selected_controls(body)

    def _selected_controls(self,body):
        self.controls=tk.Frame(body,bg=PANEL,highlightbackground=LINE,highlightthickness=1)
        self.controls.pack(fill='x',padx=SPACE['sm'],pady=(SPACE['lg'],SPACE['sm']))
        self.device_toggle=NeonButton(self.controls,text='Device Controls  −',command=self.toggle_device_controls,height=30)
        self.device_toggle.pack(fill='x',padx=SPACE['xs'],pady=SPACE['xs'])
        self.control_body=tk.Frame(self.controls,bg=PANEL)
        self.control_body.pack(fill='x')
        row=tk.Frame(self.control_body,bg=PANEL);row.pack(fill='x',padx=SPACE['sm'])
        self.inspect_power=NeonButton(row,text='Power On',command=lambda:self.toggle_channel(self.state.selected_channel),width=83,height=28)
        self.inspect_power.pack(side='left')
        self.inspect_follow=tk.BooleanVar(value=self.state.channels[self.state.selected_channel].follow)
        ttk.Checkbutton(row,text='Follow Master',variable=self.inspect_follow,command=lambda:self.set_follow(self.state.selected_channel,self.inspect_follow.get())).pack(side='right')
        self.local_brightness_label=label(self.control_body,'',9,MUTED)
        self.local_brightness_label.pack(anchor='w',padx=SPACE['sm'],pady=(SPACE['sm'],0))
        self.inspect_brightness=self._scale(self.control_body,self.state.channels[self.state.selected_channel].brightness,
                                            lambda v:self.set_channel_brightness(self.state.selected_channel,v))
        self.inspect_brightness.pack(fill='x',padx=SPACE['sm'],pady=(0,SPACE['sm']))
        self.local_brightness_label.configure(text=f'Local brightness · {self.state.channels[self.state.selected_channel].brightness:.0%}')
        self.inspect_power.configure(text='Power On' if self.state.channels[self.state.selected_channel].power else 'Power Off')
        if not getattr(self,'device_expanded',True):
            self.control_body.pack_forget();self.device_toggle.configure(text='Device Controls  +')

    def toggle_device_controls(self):
        self.device_expanded=not getattr(self,'device_expanded',True)
        if self.device_expanded:self.control_body.pack(fill='x')
        else:self.control_body.pack_forget()
        self.device_toggle.configure(text='Device Controls  −' if self.device_expanded else 'Device Controls  +')

    def set_color_mode(self,name):
        self.color_mode=name
        for key,frame in self.color_frames.items():
            frame.pack_forget()
            if key==name:frame.pack(fill='x')
            self.color_mode_buttons[key].configure(accent=key==name)

    def toggle_mixer(self):
        self.mixer_open=not self.mixer_open
        self.mixer_button.configure(text='Advanced Mixer  −' if self.mixer_open else 'Advanced Mixer  +')
        if self.mixer_open:self.mixer.pack(fill='x',padx=6,pady=(4,6),before=self.controls)
        else:self.mixer.pack_forget()

    def mix_component(self,index,value):
        color=self.state.channels[self.state.selected_channel].color
        rgb=[int(color[i:i+2],16) for i in (1,3,5)];rgb[index]=round(value)
        self.swatch('#'+''.join(f'{v:02X}' for v in rgb))

    def apply_rgb(self):
        try:
            rgb=[int(v.get()) for v in self.rgb_vars]
            if any(v<0 or v>255 for v in rgb):raise ValueError()
            self.swatch('#'+''.join(f'{v:02X}' for v in rgb))
        except ValueError:self.color_error.configure(text='RGB values must be whole numbers 0–255.')

    def navigate(self,name):
        self.state.navigate(name);self._build_center();self.center.canvas.yview_moveto(0)

    def show_inspector(self,name):
        self.state.select_inspector(name);self._inspector_body();self.inspect_scroll.canvas.yview_moveto(0)

    def choose_channel(self,name):
        self.state.select_channel(name);self.target_var.set(name);self._inspector_body();self._refresh()

    def toggle_master(self):
        self.state.master_power=not self.state.master_power;self._refresh()

    def set_brightness(self,value):
        self.state.master_brightness=value
        if self.master_value:self.master_value.configure(text=f'{value:.0%}')

    def set_mode(self,value):
        self.state.mode=value
        for name,button in self.mode_buttons.items():button.configure(accent=name==value)

    def toggle_play(self):
        self.state.playing=not self.state.playing;self._refresh()

    def set_parameter(self,name,value):
        setattr(self.state,name,value)

    def toggle_channel(self,key):
        self.state.channels[key].power=not self.state.channels[key].power;self._refresh()

    def set_follow(self,key,value):
        self.state.channels[key].follow=value
        var=getattr(self,'channel_follow',{}).get(key)
        if var is not None:var.set(value)
        if key==self.state.selected_channel and getattr(self,'inspect_follow',None):self.inspect_follow.set(value)

    def set_channel_brightness(self,key,value):
        self.state.channels[key].brightness=value
        slider=getattr(self,'channel_sliders',{}).get(key)
        if slider is not None and slider.winfo_exists():slider._value.set(value)
        if key==self.state.selected_channel and getattr(self,'inspect_brightness',None):
            self.inspect_brightness._value.set(value)
            self.local_brightness_label.configure(text=f'Local brightness · {value:.0%}')

    def select_scene(self,name):
        start=dict(self.display_colors);self.state.select_scene(name)
        targets={k:v.color for k,v in self.state.channels.items()}
        duration=self.state.transition_seconds if self.state.motion else 0
        self.transition=(time.monotonic(),start,targets,duration,self.state.transition_curve)
        self._refresh();self._sync_color()

    def toggle_favorite(self,name):
        self.state.toggle_favorite(name)
        if self.state.favorites_only:self._build_center()
        else:self._refresh()

    def toggle_filter(self):
        self.state.favorites_only=not self.state.favorites_only;self._build_center()

    def set_transition_seconds(self,value):
        self.state.set_transition(value,self.state.transition_curve);self._transition_text()

    def set_curve(self,value):
        self.state.set_transition(self.state.transition_seconds,value);self._transition_text()

    def transition_preset(self,value):
        self.state.set_transition(value,'Instant' if value==0 else 'Smooth');self._transition_text()

    def _transition_text(self):
        for seconds,button in getattr(self,'transition_options',[]):
            if button.winfo_exists():button.configure(accent=seconds==self.state.transition_seconds)
        for pad in self.scene_pads.values():pad.duration=self.state.transition_seconds;pad.draw()
        if getattr(self,'transition_button',None):self.transition_button.configure(text=f'Transition · {self.state.transition_seconds:.1f}s')
        if self.transition_label:self.transition_label.configure(text=f'Duration  {self.state.transition_seconds:.1f} seconds')

    def set_hsv(self,h,s,v):
        self.state.set_hsv(h,s,v);self.transition=None;self._sync_color()

    def hsv_changed(self):
        if not self.refreshing:
            self.set_hsv(self.hsv_vars[0].get()/360,self.hsv_vars[1].get()/100,self.hsv_vars[2].get()/100)

    def swatch(self,color):
        self.state.set_hex(color);self.transition=None;self._sync_color()

    def apply_hex(self):
        try:self.swatch(self.hex_var.get())
        except ValueError:self.color_error.configure(text='Enter six HEX digits, e.g. F32E83')

    def _sync_color(self):
        if not self.wheel:return
        self.refreshing=True
        try:
            self.wheel.hsv=self.state.get_hsv();self.wheel.draw()
            color=self.state.channels[self.state.selected_channel].color
            self.hex_var.set(color)
            self.value_var.set(self.wheel.hsv[2])
            for var,index in zip(self.rgb_vars,(1,3,5)):var.set(str(int(color[index:index+2],16)))
            for slider,index in zip(self.mixer_sliders,(1,3,5)):slider._value.set(int(color[index:index+2],16))
            for name,var,text,value,maximum in zip(('Hue','Saturation','Value'),self.hsv_vars,self.hsv_labels,self.wheel.hsv,(360,100,100)):
                var.set(value*maximum);text.configure(text=f'{value*maximum:.0f}'+('°' if maximum==360 else '%'))
            self.color_error.configure(text='')
        finally:self.refreshing=False

    def _refresh(self):
        if getattr(self,'inspect_power',None):self.inspect_power.configure(text='Power On' if self.state.channels[self.state.selected_channel].power else 'Power Off')
        for n,b in self.nav_buttons.items():b.configure(bg=SELECTED if n==self.state.page else SIDEBAR,fg=TEXT if n==self.state.page else MUTED)
        if hasattr(self,'master_button'):self.master_button.configure(text='⏻',accent=self.state.master_power)
        if self.play_button:self.play_button.configure(text='Ⅱ  Pause' if self.state.playing else '▶  Play')
        for n,pad in self.scene_pads.items():
            pad.active=n==self.state.scene;pad.favorite=n in self.state.favorites;pad.duration=self.state.transition_seconds;pad.draw()
        for k,(_,_,power) in self.channel_labels.items():
            power.configure(text='On' if self.state.channels[k].power else 'Off')
            self.channel_rows[k].configure(highlightbackground=PURPLE if k==self.state.selected_channel else LINE)

    def _tick(self):
        self.after_id=None
        if self.closed:return
        now=time.monotonic();dt=min(.1,now-self.last_tick);self.last_tick=now
        if self.state.playing and self.state.motion:self.phase+=dt
        if self.transition:
            started,start,target,duration,curve=self.transition
            t=1. if not self.state.motion or duration<=0 or curve=='Instant' else min(1.,(now-started)/duration)
            alpha=t*t*(3-2*t) if curve=='Smooth' else t
            self.display_colors={k:blend(start[k],target[k],alpha) for k in target}
            if t>=1:self.transition=None
            if self.transition_button and self.transition_button.winfo_exists():
                message=f'Fading · {t:.0%}' if t<1 else f'Transition · {self.state.transition_seconds:g}s'
                if self.transition_button.text!=message:self.transition_button.configure(text=message)
        else:self.display_colors={k:v.color for k,v in self.state.channels.items()}
        active=self.state.playing and self.state.master_power and self.state.mode=='Music'
        if self.reactor:
            self.reactor.draw(self.phase,active,self.state.master_brightness*(.4+self.state.sensitivity*.6))
            for (text,name),(bar,color),value in zip(self.level_labels,self.level_bars,self.reactor.summary):
                text.configure(text=f'{name}  {value:.0%}');bar.delete('all');bar.create_rectangle(0,0,value*bar.winfo_width(),9,fill=color,outline='')
        for k,(dot,status,_) in self.channel_labels.items():
            c=self.state.channels[k];power=c.power and (self.state.master_power or not c.follow)
            brightness=c.brightness*(self.state.master_brightness if c.follow else 1.)
            color=blend('#000000',self.display_colors[k],brightness) if power else '#494250'
            dot.configure(fg=color)
            status.configure(text=f'OUT {brightness:.0%} · DEMO' if power else 'OFF · DEMO')
        if self.screen_preview:
            canvas=self.screen_preview;canvas.delete('all');w=max(100,canvas.winfo_width())
            a,b=SCENES['Ocean Breeze' if self.state.screen_source.endswith('1') else 'Sunset Chill'][:2]
            for x in range(0,w,5):canvas.create_rectangle(x,0,x+5,200,fill=blend('#000000',blend(a,b,x/w),self.state.screen_intensity),outline='')
            canvas.create_text(w/2,100,text=self.state.screen_source.upper(),fill=TEXT,font=('Segoe UI',12,'bold'))
        self.master_swatch.configure(fg=self.display_colors['Corner'] if self.state.master_power else MUTED)
        self.after_id=self.root.after(self.FRAME_MS,self._tick)

    def reset(self):
        self.state=StudioState();self.transition=None;self.display_colors={k:v.color for k,v in self.state.channels.items()}
        self.target_var.set(self.state.selected_channel);self._inspector_body();self._build_center()

    def close(self):
        if self.closed:return
        self.closed=True
        if self.after_id is not None:
            self.root.after_cancel(self.after_id);self.after_id=None
        self.root.destroy()
