"""Direct2D bitmap interpolation; one uploaded image and fractional source bounds."""
import ctypes as C
from ctypes import wintypes as W

class GUID(C.Structure):
    _fields_=[('a',W.DWORD),('b',W.WORD),('c',W.WORD),('d',W.BYTE*8)]
class Size(C.Structure):
    _fields_=[('w',W.UINT),('h',W.UINT)]
class Pixel(C.Structure):
    _fields_=[('format',W.UINT),('alpha',W.UINT)]
class Props(C.Structure):
    _fields_=[('type',W.UINT),('pixel',Pixel),('dpiX',C.c_float),('dpiY',C.c_float),('usage',W.UINT),('level',W.UINT)]
class HwndProps(C.Structure):
    _fields_=[('hwnd',W.HWND),('size',Size),('options',W.UINT)]
class BitmapProps(C.Structure):
    _fields_=[('pixel',Pixel),('dpiX',C.c_float),('dpiY',C.c_float)]
class Rect(C.Structure):
    _fields_=[('left',C.c_float),('top',C.c_float),('right',C.c_float),('bottom',C.c_float)]

def method(pointer,index,result,*args):
    table=C.cast(pointer,C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(result,C.c_void_p,*args)(table[index])
def release(pointer):
    if pointer and pointer.value:method(pointer,2,W.ULONG)(pointer);pointer.value=None

def check(hr):
    if hr<0:raise OSError(f'Direct2D HRESULT 0x{hr&0xffffffff:08x}')

class Renderer:
    def __init__(self,hwnd,image,software=False):
        self.pulse_bitmaps=[];self.pulse_opacities=(0,0)
        self.factory=C.c_void_p();self.target=C.c_void_p();self.bitmap=C.c_void_p()
        self.width,self.height=image.size;self.software=software
        try:
            dll=C.WinDLL('d2d1')
            iid=GUID(0x06152247,0x6f50,0x465a,(W.BYTE*8)(0x92,0x45,0x11,0x8b,0xfd,0x3b,0x60,0x07))
            dll.D2D1CreateFactory.argtypes=[W.UINT,C.POINTER(GUID),C.c_void_p,C.POINTER(C.c_void_p)]
            dll.D2D1CreateFactory.restype=W.LONG
            check(dll.D2D1CreateFactory(0,C.byref(iid),None,C.byref(self.factory)))
            # Software fallback renders a smaller viewport, stretched by Direct2D.
            ratio=min(1,1280/self.width)
            self.rw,self.rh=max(1,round(self.width*ratio)),max(1,round(self.height*ratio))
            props=Props(2 if software else 1,Pixel(87,3),96,96,0,0)
            window=HwndProps(hwnd,Size(self.rw,self.rh),2)
            create=method(self.factory,14,W.LONG,C.POINTER(Props),C.POINTER(HwndProps),C.POINTER(C.c_void_p))
            check(create(self.factory,C.byref(props),C.byref(window),C.byref(self.target)))
            raw=image.convert('RGB').tobytes('raw','BGRX')
            bmp=BitmapProps(Pixel(87,3),96,96)
            create_bmp=method(self.target,4,W.LONG,Size,C.c_void_p,W.UINT,C.POINTER(BitmapProps),C.POINTER(C.c_void_p))
            check(create_bmp(self.target,Size(self.width,self.height),raw,self.width*4,C.byref(bmp),C.byref(self.bitmap)))
            self.begin=method(self.target,48,None)
            self.end=method(self.target,49,W.LONG,C.c_void_p,C.c_void_p)
            self.draw_bitmap=method(self.target,26,None,C.c_void_p,C.POINTER(Rect),C.c_float,W.UINT,C.POINTER(Rect))
        except Exception:self.close();raise

    def set_pulse_layers(self,images):
        for image in images:
            bitmap=C.c_void_p();self.pulse_bitmaps.append(bitmap)
            raw=image.convert('RGB').tobytes('raw','BGRX')
            props=BitmapProps(Pixel(87,3),96,96)
            check(method(self.target,4,W.LONG,Size,C.c_void_p,W.UINT,C.POINTER(BitmapProps),C.POINTER(C.c_void_p))(
                self.target,Size(self.width,self.height),raw,self.width*4,C.byref(props),C.byref(bitmap)))

    def draw(self,scale):
        # Linear filtering samples subpixel coordinates: no integer crop jumps.
        cw,ch=self.width/scale,self.height/scale
        x,y=(self.width-cw)/2,(self.height-ch)/2
        dx,dy=getattr(self,'offset',(0,0))
        x=max(0,min(self.width-cw,x-dx/scale))
        y=max(0,min(self.height-ch,y-dy/scale))
        src=Rect(x,y,x+cw,y+ch);dst=Rect(0,0,self.rw,self.rh)
        self.begin(self.target)
        self.draw_bitmap(self.target,self.bitmap,C.byref(dst),1.0,1,C.byref(src))
        for bitmap,opacity in zip(self.pulse_bitmaps,self.pulse_opacities):
            if opacity>0:self.draw_bitmap(self.target,bitmap,C.byref(dst),opacity,1,C.byref(src))
        check(self.end(self.target,None,None))

    def set_motion_sample(self,effect,elapsed):
        from zoom_effect import jitter_offset,chromatic_opacities
        self.offset=jitter_offset(elapsed) if effect=='pulse' else (0,0)
        self.pulse_opacities=chromatic_opacities(elapsed) if effect=='pulse' else (0,0)

    def close(self):
        for bitmap in self.pulse_bitmaps:release(bitmap)
        self.pulse_bitmaps=[]
        release(self.bitmap);release(self.target);release(self.factory)
