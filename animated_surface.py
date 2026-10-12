"""Independent desktop animation thread with cached Direct2D resources."""
import ctypes as C
from ctypes import wintypes as W
import os
import threading
import time
from native_zoom import NativeZoom,bind
from d2d_renderer import Renderer
from composition_renderer import CompositionRenderer
from zoom_effect import zoom_scale, pulse_texture

class Message(C.Structure):
    _fields_=[('hwnd',W.HWND),('message',W.UINT),('wparam',W.WPARAM),('lparam',W.LPARAM),('time',W.DWORD),('point',W.POINT),('private',W.DWORD)]
class Power(C.Structure):
    _fields_=[('ac',W.BYTE),('flags',W.BYTE),('percent',W.BYTE),('reserved',W.BYTE),('remaining',W.DWORD),('full',W.DWORD)]

class AnimatedSurface:
    def __init__(self,parent,image,x=0,y=0,opacity=1.0,effect=None):
        self.width,self.height=image.size
        self.hwnd=None;self.error=None;self.draw_count=0
        self.backend_name='initializing';self.fps=60;self.last_scale=1.0
        self._lock=threading.Lock();self._wake=threading.Event();self._stop=threading.Event();self._ready=threading.Event();self._alpha_event=threading.Event()
        self._alpha=opacity;self._alpha_dirty=False;self._manual=None
        self._motion=False;self._paused=False;self._elapsed=0;self._started=0
        self._interval=5;self._effect='smooth';self._command=None;self._frame_times=[];self.render_cpu_seconds=0
        self._thread=threading.Thread(target=self._run,args=(parent,image,x,y,opacity,effect),daemon=True,name='Bushtwo wallpaper animation')
        self._thread.start()
        if not self._ready.wait(10):
            self.destroy();raise RuntimeError('Wallpaper renderer initialization timed out')
        if self.error:raise RuntimeError(self.error)

    def _run(self,parent,image,x,y,opacity,effect):
        surface=None
        try:
            ole=C.windll.ole32;initialized=ole.CoInitializeEx(None,0) in (0,1)
            surface=NativeZoom(parent,image,x,y,opacity=0.0)
            backend=None
            try:
                backend=CompositionRenderer(surface.hwnd,image)
                if effect=='pulse':backend.enable_pulse(image)
            except Exception:
                if backend is not None:backend.close()
                backend=Renderer(surface.hwnd,image,software=True)
                if effect=='pulse':
                    lens=pulse_texture(image,chromatic_strength=0)
                    backend.set_pulse_layers([pulse_texture(image,separation=d,lens_image=lens) for d in (1,-1)])
            surface.set_backend(backend)
            cached=hasattr(backend,'set_opacity')
            dynamic_pulse=getattr(backend,'pulse_shader',None) is not None
            self.backend_name=('GPU lens compositor' if not backend.software else 'CPU lens compositor') if dynamic_pulse else ('cached compositor' if cached else 'software interpolation')
            power=Power();C.windll.kernel32.GetSystemPowerStatus(C.byref(power))
            self.fps=(30 if (os.cpu_count() or 2)<=2 or power.ac==0 else 60) if cached else 24
            if dynamic_pulse and backend.software:self.fps=24
            # A cached native timeline costs less CPU than a Python 30fps loop,
            # including on battery and older processors.
            native_timeline=cached and not dynamic_pulse
            self.native_timeline=native_timeline
            self.hwnd=surface.hwnd;self._is_window=surface.u.IsWindow
            surface.attributes('-alpha',opacity)
            u=surface.u
            bind(u,'PeekMessageW',[C.POINTER(Message),W.HWND,W.UINT,W.UINT,W.UINT],W.BOOL)
            bind(u,'TranslateMessage',[C.POINTER(Message)],W.BOOL)
            bind(u,'DispatchMessageW',[C.POINTER(Message)],C.c_ssize_t)
            kernel=C.WinDLL('kernel32',use_last_error=True)
            bind(kernel,'CreateWaitableTimerExW',[C.c_void_p,W.LPCWSTR,W.DWORD,W.DWORD],W.HANDLE)
            bind(kernel,'SetWaitableTimer',[W.HANDLE,C.POINTER(C.c_longlong),W.LONG,C.c_void_p,C.c_void_p,W.BOOL],W.BOOL)
            bind(kernel,'WaitForSingleObject',[W.HANDLE,W.DWORD],W.DWORD)
            bind(kernel,'CloseHandle',[W.HANDLE],W.BOOL)
            timer=kernel.CreateWaitableTimerExW(None,None,2,0x1f0003)
            msg=Message();self._ready.set();next_frame=time.monotonic()
            while not self._stop.is_set():
                if not surface.winfo_exists():
                    self.error='Desktop surface was replaced';break
                for _ in range(8):
                    if not u.PeekMessageW(C.byref(msg),None,0,0,1):break
                    u.TranslateMessage(C.byref(msg));u.DispatchMessageW(C.byref(msg))
                now=time.monotonic()
                with self._lock:
                    alpha=self._alpha if self._alpha_dirty else None;self._alpha_dirty=False
                    scale=self._manual;self._manual=None
                    moving=self._motion and not self._paused
                    command=self._command;self._command=None
                    interval,effect,elapsed=self._interval,self._effect,self._elapsed
                    if moving and now>=next_frame:
                        motion_end=min(self._interval,2.0) if self._effect=='pulse' else self._interval
                        self._elapsed=min(motion_end,max(0,now-self._started))
                        self.last_scale=zoom_scale(self._elapsed,self._interval,self._effect)
                        if not native_timeline:scale=self.last_scale
                        if self._elapsed>=motion_end:self._motion=False
                if command is not None and native_timeline:
                    if command=='start' and moving:backend.start_animation(interval,effect,elapsed)
                    else:
                        backend.set_motion_sample(effect,elapsed)
                        backend.draw(zoom_scale(elapsed,interval,effect)+(.002 if effect=='pulse' else 0))
                elif command is not None:
                    scale=zoom_scale(self._elapsed,interval,effect)
                if alpha is not None:
                    surface.attributes('-alpha',alpha);self._alpha_event.set()
                if scale is not None:
                    if hasattr(backend,'set_motion_sample'):backend.set_motion_sample(effect,self._elapsed)
                    if effect=='pulse':scale+=.002
                    began=time.monotonic();cpu_began=time.thread_time();surface.render(scale)
                    self.render_cpu_seconds+=time.thread_time()-cpu_began
                    self.last_scale=scale;self.draw_count+=1
                    self._frame_times.append(time.monotonic()-began)
                    if len(self._frame_times)>120:self._frame_times.pop(0)
                    # Sustained slow presents reduce cadence without changing time.
                    # Fallback cadence is bounded; compositor timelines require no redraws.
                    next_frame=time.monotonic()+max(0,1/self.fps-(time.monotonic()-began))
                if native_timeline:next_frame=time.monotonic()+.05
                wait=max(.001,min(.05,next_frame-time.monotonic())) if moving else .05
                if moving and timer and not native_timeline:
                    due=C.c_longlong(-max(1,int(wait*10_000_000)))
                    kernel.SetWaitableTimer(timer,C.byref(due),0,None,None,False)
                    kernel.WaitForSingleObject(timer,100)
                else:self._wake.wait(wait)
                self._wake.clear()
        except Exception as error:
            self.error=str(error);self._ready.set()
        finally:
            if 'timer' in locals() and timer:kernel.CloseHandle(timer)
            if surface is not None:surface.destroy()
            self.hwnd=None
            if 'initialized' in locals() and initialized:C.windll.ole32.CoUninitialize()

    def attributes(self,name,value):
        if name=='-alpha':
            with self._lock:self._alpha=value;self._alpha_dirty=True;self._alpha_event.clear()
            self._wake.set()

    def wait_alpha(self):
        return self._alpha_event.wait(1) and not self.error

    def render(self,scale):
        with self._lock:self._manual=scale
        self._wake.set()

    def start_zoom(self,interval,effect='smooth',paused=False):
        with self._lock:
            self._interval=interval;self._effect=effect;self._elapsed=0
            self._started=time.monotonic();self._motion=True;self._paused=paused;self._command='start'
            self._manual=None if getattr(self,'native_timeline',False) else 1.0
        self._wake.set()

    def pause(self):
        with self._lock:
            if not self._paused and self._motion:self._elapsed=min(self._interval,time.monotonic()-self._started)
            self._paused=True;self._command='pause'
        self._wake.set()

    def resume(self):
        with self._lock:self._started=time.monotonic()-self._elapsed;self._paused=False;self._command='start'
        self._wake.set()

    @property
    def elapsed(self):
        with self._lock:return min(self._interval,time.monotonic()-self._started) if self._motion and not self._paused else self._elapsed

    def winfo_exists(self):
        return bool(self.hwnd and self._thread.is_alive() and not self.error and self._is_window(self.hwnd))

    def destroy(self):
        self._stop.set();self._wake.set()
        if self._thread is not threading.current_thread():self._thread.join(.25)
