"""Upload once, then let the Windows compositor transform the cached wallpaper."""
import ctypes as C
from ctypes import wintypes as W
import uuid
import math
from zoom_effect import zoom_scale, smooth_segments, jitter_offset, chromatic_opacities, chromatic_segments
from d2d_renderer import GUID,Pixel,BitmapProps,Rect,Size,method,release,check

class BitmapProps1(C.Structure):
    _fields_=[('pixel',Pixel),('dpiX',C.c_float),('dpiY',C.c_float),('options',W.UINT),('color',C.c_void_p)]
class Matrix(C.Structure):
    _fields_=[('m11',C.c_float),('m12',C.c_float),('m21',C.c_float),('m22',C.c_float),('dx',C.c_float),('dy',C.c_float)]

def guid(text):return GUID.from_buffer_copy(uuid.UUID(text).bytes_le)
def query(pointer,iid,out):
    check(method(pointer,0,W.LONG,C.POINTER(GUID),C.POINTER(C.c_void_p))(pointer,C.byref(iid),C.byref(out)))

# MSVC stores each group of virtual overloads in reverse declaration order.
class CompositionRenderer:
    def __init__(self,hwnd,image):
        self.width,self.height=image.size;self.software=False;self.hwnd=hwnd
        self.objects=[];self.old_style=None;self.jitter_animations=[]
        self.pulse_effects=[];self.pulse_animations=[];self.pulse_shader=None
        def obj():
            p=C.c_void_p();self.objects.append(p);return p
        self.device=obj();self.context3d=obj();self.dxgi=obj();self.d2d=obj();self.ctx=obj()
        self.comp=obj();self.target=obj();self.visual=obj();self.effect=obj();self.surface=obj();self.scale_transform=obj();self.animation=C.c_void_p()
        try:
            d3d=C.WinDLL('d3d11');d3d.D3D11CreateDevice.argtypes=[C.c_void_p,W.UINT,W.HMODULE,W.UINT,C.c_void_p,W.UINT,W.UINT,C.POINTER(C.c_void_p),C.c_void_p,C.POINTER(C.c_void_p)]
            d3d.D3D11CreateDevice.restype=W.LONG
            hr=d3d.D3D11CreateDevice(None,1,None,0x20,None,0,7,C.byref(self.device),None,C.byref(self.context3d))
            if hr<0:
                self.software=True
                check(d3d.D3D11CreateDevice(None,5,None,0x20,None,0,7,C.byref(self.device),None,C.byref(self.context3d)))
            query(self.device,guid('54ec77fa-1377-44e6-8c32-88fd5f44c84c'),self.dxgi)
            d2d=C.WinDLL('d2d1');d2d.D2D1CreateDevice.argtypes=[C.c_void_p,C.c_void_p,C.POINTER(C.c_void_p)];d2d.D2D1CreateDevice.restype=W.LONG
            check(d2d.D2D1CreateDevice(self.dxgi,None,C.byref(self.d2d)))
            check(method(self.d2d,4,W.LONG,W.UINT,C.POINTER(C.c_void_p))(self.d2d,0,C.byref(self.ctx)))
            dc=C.WinDLL('dcomp');dc.DCompositionCreateDevice.argtypes=[C.c_void_p,C.POINTER(GUID),C.POINTER(C.c_void_p)];dc.DCompositionCreateDevice.restype=W.LONG
            iid=guid('c37ea93a-e7aa-450d-b16f-9746cb0407f3')
            check(dc.DCompositionCreateDevice(self.dxgi,C.byref(iid),C.byref(self.comp)))
            self.u=C.WinDLL('user32');self.u.GetWindowLongW.argtypes=[W.HWND,C.c_int];self.u.SetWindowLongW.argtypes=[W.HWND,C.c_int,C.c_long]
            self.old_style=self.u.GetWindowLongW(hwnd,-20)
            self.u.SetWindowLongW(hwnd,-20,self.old_style|0x00200000)  # No CPU redirection bitmap.
            check(method(self.comp,6,W.LONG,W.HWND,W.BOOL,C.POINTER(C.c_void_p))(self.comp,hwnd,True,C.byref(self.target)))
            check(method(self.comp,7,W.LONG,C.POINTER(C.c_void_p))(self.comp,C.byref(self.visual)))
            check(method(self.comp,23,W.LONG,C.POINTER(C.c_void_p))(self.comp,C.byref(self.effect)))
            check(method(self.visual,10,W.LONG,C.c_void_p)(self.visual,self.effect))
            check(method(self.effect,4,W.LONG,C.c_float)(self.effect,0.0))
            check(method(self.comp,8,W.LONG,W.UINT,W.UINT,W.UINT,W.UINT,C.POINTER(C.c_void_p))(self.comp,self.width,self.height,87,1,C.byref(self.surface)))
            check(method(self.visual,15,W.LONG,C.c_void_p)(self.visual,self.surface))
            check(method(self.visual,11,W.LONG,W.UINT)(self.visual,1))  # Linear interpolation.
            check(method(self.target,3,W.LONG,C.c_void_p)(self.target,self.visual))
            self.commit=method(self.comp,3,W.LONG)
            self.set_matrix=method(self.visual,8,W.LONG,C.POINTER(Matrix))
            self.set_alpha=method(self.effect,4,W.LONG,C.c_float)
            check(method(self.comp,13,W.LONG,C.POINTER(C.c_void_p))(self.comp,C.byref(self.scale_transform)))
            check(method(self.scale_transform,8,W.LONG,C.c_float)(self.scale_transform,self.width/2))
            check(method(self.scale_transform,10,W.LONG,C.c_float)(self.scale_transform,self.height/2))
            check(method(self.visual,7,W.LONG,C.c_void_p)(self.visual,self.scale_transform))
            self._upload(image)
            check(self.commit(self.comp))
        except Exception:self.close();raise

    def _upload(self,image,surface=None):
        surface=self.surface if surface is None else surface
        src=C.c_void_p();texture=C.c_void_p();target=C.c_void_p();drawing=False
        try:
            raw=image.convert('RGB').tobytes('raw','BGRX');props=BitmapProps(Pixel(87,3),96,96)
            check(method(self.ctx,4,W.LONG,Size,C.c_void_p,W.UINT,C.POINTER(BitmapProps),C.POINTER(C.c_void_p))(self.ctx,Size(self.width,self.height),raw,self.width*4,C.byref(props),C.byref(src)))
            iid=guid('cafcb56c-6ac3-4889-bf47-9e23bbd260ec');offset=W.POINT()
            check(method(surface,3,W.LONG,C.c_void_p,C.POINTER(GUID),C.POINTER(C.c_void_p),C.POINTER(W.POINT))(surface,None,C.byref(iid),C.byref(texture),C.byref(offset)));drawing=True
            props1=BitmapProps1(Pixel(87,1),96,96,3,None)
            check(method(self.ctx,62,W.LONG,C.c_void_p,C.POINTER(BitmapProps1),C.POINTER(C.c_void_p))(self.ctx,texture,C.byref(props1),C.byref(target)))
            method(self.ctx,74,None,C.c_void_p)(self.ctx,target)
            method(self.ctx,48,None)(self.ctx)
            dst=Rect(offset.x,offset.y,offset.x+self.width,offset.y+self.height)
            method(self.ctx,26,None,C.c_void_p,C.POINTER(Rect),C.c_float,W.UINT,C.c_void_p)(self.ctx,src,C.byref(dst),1.0,1,None)
            check(method(self.ctx,49,W.LONG,C.c_void_p,C.c_void_p)(self.ctx,None,None))
            method(self.ctx,74,None,C.c_void_p)(self.ctx,None)
            check(method(surface,4,W.LONG)(surface));drawing=False
        finally:
            if drawing:method(surface,4,W.LONG)(surface)
            release(target);release(texture);release(src)

    def set_pulse_layers(self,images):
        for image in images:
            visual=C.c_void_p();effect=C.c_void_p();surface=C.c_void_p()
            self.objects.extend((visual,effect,surface))
            check(method(self.comp,7,W.LONG,C.POINTER(C.c_void_p))(self.comp,C.byref(visual)))
            check(method(self.comp,23,W.LONG,C.POINTER(C.c_void_p))(self.comp,C.byref(effect)))
            check(method(self.comp,8,W.LONG,W.UINT,W.UINT,W.UINT,W.UINT,C.POINTER(C.c_void_p))(self.comp,self.width,self.height,87,1,C.byref(surface)))
            self._upload(image,surface)
            check(method(visual,15,W.LONG,C.c_void_p)(visual,surface))
            check(method(visual,10,W.LONG,C.c_void_p)(visual,effect))
            check(method(effect,4,W.LONG,C.c_float)(effect,0.0))
            check(method(self.visual,16,W.LONG,C.c_void_p,W.BOOL,C.c_void_p)(self.visual,visual,True,None))
            self.pulse_effects.append(effect)
        check(self.commit(self.comp))

    def draw(self,scale):
        if self.pulse_shader is not None:self.pulse_shader.draw()
        check(method(self.scale_transform,4,W.LONG,C.c_float)(self.scale_transform,scale))
        check(method(self.scale_transform,6,W.LONG,C.c_float)(self.scale_transform,scale))
        check(self.commit(self.comp))

    def enable_pulse(self,image):
        from pulse_shader import PulseShader
        self.pulse_shader=PulseShader(self,image)

    def start_animation(self,interval,effect,elapsed=0):
        if effect=='pulse':interval=min(interval,2.0)
        remaining=interval-elapsed
        if remaining<=0:
            if effect=='pulse':self.set_motion_sample(effect,2.0)
            self.draw(zoom_scale(interval,interval,effect)+(.002 if effect=='pulse' else 0));return
        release(self.animation)
        check(method(self.comp,25,W.LONG,C.POINTER(C.c_void_p))(self.comp,C.byref(self.animation)))
        # Explicit five-second cubic segments avoid a final correction to a
        # separately calculated endpoint. Pause/resume uses the identical curve.
        if effect=='pulse':
            check(method(self.animation,6,W.LONG,C.c_double,C.c_float,C.c_float,C.c_float,C.c_float)(self.animation,0.0,1.052,.05,.5,elapsed*180-90))
        else:
            for segment in smooth_segments(interval,elapsed):
                check(method(self.animation,5,W.LONG,C.c_double,C.c_float,C.c_float,C.c_float,C.c_float)(self.animation,*segment))
        check(method(self.animation,8,W.LONG,C.c_double,C.c_float)(self.animation,remaining,zoom_scale(interval,interval,effect)+(.002 if effect=='pulse' else 0)))
        begin=C.c_longlong();C.windll.kernel32.QueryPerformanceCounter(C.byref(begin))
        check(method(self.animation,4,W.LONG,C.c_longlong)(self.animation,begin))
        check(method(self.scale_transform,3,W.LONG,C.c_void_p)(self.scale_transform,self.animation))
        check(method(self.scale_transform,5,W.LONG,C.c_void_p)(self.scale_transform,self.animation))
        for p in self.jitter_animations:release(p)
        self.jitter_animations=[]
        for index,amplitude,frequency in ((3,.65,7),(5,.45,11)):
            if effect=='pulse':
                p=C.c_void_p();self.jitter_animations.append(p)
                check(method(self.comp,25,W.LONG,C.POINTER(C.c_void_p))(self.comp,C.byref(p)))
                check(method(p,6,W.LONG,C.c_double,C.c_float,C.c_float,C.c_float,C.c_float)(p,0,0,amplitude,frequency,elapsed*frequency*360))
                final=jitter_offset(interval)[0 if index==3 else 1]
                check(method(p,8,W.LONG,C.c_double,C.c_float)(p,remaining,final))
                check(method(p,4,W.LONG,C.c_longlong)(p,begin))
                check(method(self.visual,index,W.LONG,C.c_void_p)(self.visual,p))
            else:
                check(method(self.visual,index+1,W.LONG,C.c_float)(self.visual,0))
        for p in self.pulse_animations:release(p)
        self.pulse_animations=[]
        for channel,layer in enumerate(self.pulse_effects):
            if effect=='pulse':
                p=C.c_void_p();self.pulse_animations.append(p)
                check(method(self.comp,25,W.LONG,C.POINTER(C.c_void_p))(self.comp,C.byref(p)))
                for segment in chromatic_segments(elapsed,channel):
                    check(method(p,5,W.LONG,C.c_double,C.c_float,C.c_float,C.c_float,C.c_float)(p,*segment))
                check(method(p,8,W.LONG,C.c_double,C.c_float)(p,remaining,0.0))
                check(method(p,4,W.LONG,C.c_longlong)(p,begin))
                check(method(layer,3,W.LONG,C.c_void_p)(layer,p))
            else:check(method(layer,4,W.LONG,C.c_float)(layer,0.0))
        check(self.commit(self.comp))

    def set_motion_sample(self,effect,elapsed):
        if self.pulse_shader is not None:self.pulse_shader.set_sample(effect,elapsed)
        x,y=jitter_offset(elapsed) if effect=='pulse' else (0,0)
        check(method(self.visual,4,W.LONG,C.c_float)(self.visual,x))
        check(method(self.visual,6,W.LONG,C.c_float)(self.visual,y))
        values=chromatic_opacities(elapsed) if effect=='pulse' else (0,0)
        for layer,value in zip(self.pulse_effects,values):
            check(method(layer,4,W.LONG,C.c_float)(layer,value))

    def set_opacity(self,value):
        check(self.set_alpha(self.effect,value));check(self.commit(self.comp))

    def close(self):
        if self.pulse_shader is not None:self.pulse_shader.close();self.pulse_shader=None
        for p in self.pulse_animations:release(p)
        self.pulse_animations=[]
        for p in self.jitter_animations:release(p)
        self.jitter_animations=[]
        release(self.animation)
        for pointer in reversed(self.objects):release(pointer)
        if self.old_style is not None:
            self.u.SetWindowLongW(self.hwnd,-20,self.old_style);self.old_style=None
