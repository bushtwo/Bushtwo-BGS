"""Reusable native wallpaper surface: two DIBs, no Tk image uploads per frame."""
import ctypes
from ctypes import wintypes as W

class Header(ctypes.Structure):
    _fields_ = [('size',W.DWORD),('width',W.LONG),('height',W.LONG),
                ('planes',W.WORD),('bits',W.WORD),('compression',W.DWORD),
                ('bytes',W.DWORD),('xppm',W.LONG),('yppm',W.LONG),
                ('used',W.DWORD),('important',W.DWORD)]
def bind(dll,name,args,result):
    fn=getattr(dll,name);fn.argtypes=args;fn.restype=result;return fn

class Paint(ctypes.Structure):
    _fields_=[('dc',W.HDC),('erase',W.BOOL),('rect',W.RECT),('restore',W.BOOL),('update',W.BOOL),('reserved',W.BYTE*32)]

class NativeZoom:
    def __init__(self,parent,image,x=0,y=0,owner=None,widget=None,opacity=1.0):
        self.u=ctypes.WinDLL('user32',use_last_error=True)
        self.g=ctypes.WinDLL('gdi32',use_last_error=True)
        self.owner=owner;self.widget=widget;self.buffers=[];self.draw_count=0;self.old_proc=None
        self.width,self.height=image.size
        self.backend=None;self.current_scale=1.0;self._drawing=False;self._opacity=opacity
        self.hwnd=None
        self.parent_hwnd=parent
        bind(self.g,'CreateCompatibleDC',[W.HDC],W.HDC)
        bind(self.g,'CreateDIBSection',[W.HDC,ctypes.POINTER(Header),W.UINT,ctypes.POINTER(ctypes.c_void_p),W.HANDLE,W.DWORD],W.HBITMAP)
        bind(self.g,'SelectObject',[W.HDC,W.HANDLE],W.HANDLE)
        bind(self.g,'DeleteObject',[W.HANDLE],W.BOOL)
        bind(self.g,'DeleteDC',[W.HDC],W.BOOL)
        bind(self.g,'StretchBlt',[W.HDC,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.HDC,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.DWORD],W.BOOL)
        bind(self.g,'BitBlt',[W.HDC,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.HDC,ctypes.c_int,ctypes.c_int,W.DWORD],W.BOOL)
        bind(self.g,'SetStretchBltMode',[W.HDC,ctypes.c_int],ctypes.c_int)
        bind(self.u,'CreateWindowExW',[W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.HWND,W.HMENU,W.HINSTANCE,ctypes.c_void_p],W.HWND)
        bind(self.u,'DestroyWindow',[W.HWND],W.BOOL)
        bind(self.u,'IsWindow',[W.HWND],W.BOOL)
        bind(self.u,'SetLayeredWindowAttributes',[W.HWND,W.DWORD,W.BYTE,W.DWORD],W.BOOL)
        bind(self.u,'SetWindowPos',[W.HWND,W.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.UINT],W.BOOL)
        bind(self.u,'FindWindowExW',[W.HWND,W.HWND,W.LPCWSTR,W.LPCWSTR],W.HWND)
        bind(self.u,'GetWindowLongW',[W.HWND,ctypes.c_int],ctypes.c_long)
        bind(self.u,'SetWindowLongW',[W.HWND,ctypes.c_int,ctypes.c_long],ctypes.c_long)
        bind(self.u,'SetWindowLongPtrW',[W.HWND,ctypes.c_int,ctypes.c_ssize_t],ctypes.c_ssize_t)
        bind(self.u,'CallWindowProcW',[ctypes.c_void_p,W.HWND,W.UINT,W.WPARAM,W.LPARAM],ctypes.c_ssize_t)
        bind(self.u,'BeginPaint',[W.HWND,ctypes.POINTER(Paint)],W.HDC)
        bind(self.u,'EndPaint',[W.HWND,ctypes.POINTER(Paint)],W.BOOL)
        bind(self.u,'InvalidateRect',[W.HWND,ctypes.c_void_p,W.BOOL],W.BOOL)
        bind(self.u,'UpdateWindow',[W.HWND],W.BOOL)
        try:
            for _ in range(2):
                dc=self.g.CreateCompatibleDC(None)
                if not dc:raise ctypes.WinError(ctypes.get_last_error())
                header=Header(ctypes.sizeof(Header),self.width,-self.height,1,32,0,0,0,0,0,0)
                bits=ctypes.c_void_p()
                bitmap=self.g.CreateDIBSection(dc,ctypes.byref(header),0,ctypes.byref(bits),None,0)
                if not bitmap:
                    self.g.DeleteDC(dc);raise ctypes.WinError(ctypes.get_last_error())
                previous=self.g.SelectObject(dc,bitmap)
                self.buffers.append((dc,bitmap,previous,bits))
            raw=image.convert('RGB').tobytes('raw','BGRX')
            ctypes.memmove(self.buffers[0][3],raw,len(raw))
            self.g.SetStretchBltMode(self.buffers[1][0],3)
            self.hwnd=self.u.CreateWindowExW(0x80000|0x20|0x80|0x08000000,'STATIC','',0x40000000,x,y,self.width,self.height,self.parent_hwnd,None,None,None)
            if not self.hwnd:raise ctypes.WinError(ctypes.get_last_error())
            proc_type=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
            @proc_type
            def paint_proc(hwnd,message,wparam,lparam):
                if message==0x14:return 1  # Avoid clearing before the buffered paint.
                if message==0x0F:
                    paint=Paint();dc=self.u.BeginPaint(hwnd,ctypes.byref(paint))
                    if self.backend is None:self.g.BitBlt(dc,0,0,self.width,self.height,self.buffers[1][0],0,0,0x00CC0020)
                    self.u.EndPaint(hwnd,ctypes.byref(paint));return 0
                return self.u.CallWindowProcW(self.old_proc,hwnd,message,wparam,lparam)
            self.paint_proc=paint_proc
            self.old_proc=self.u.SetWindowLongPtrW(self.hwnd,-4,ctypes.cast(paint_proc,ctypes.c_void_p).value)
            if not self.old_proc:raise ctypes.WinError(ctypes.get_last_error())
            self.render(1.0)
            self.attributes('-alpha',opacity)
            icons=self.u.FindWindowExW(parent,None,'SHELLDLL_DefView',None)
            self.u.SetWindowPos(self.hwnd,icons or 0,x,y,self.width,self.height,0x10|0x40)
        except Exception:
            self.destroy();raise

    def render(self,scale):
        if not self.winfo_exists():return
        self.current_scale=scale
        if self.backend is not None:
            self._drawing=True
            try:self.backend.draw(scale)
            finally:self._drawing=False
            self.draw_count+=1
            return
        crop_w=max(1,round(self.width/scale));crop_h=max(1,round(self.height/scale))
        left=(self.width-crop_w)//2;top=(self.height-crop_h)//2
        if not self.g.StretchBlt(self.buffers[1][0],0,0,self.width,self.height,self.buffers[0][0],left,top,crop_w,crop_h,0x00CC0020):
            raise ctypes.WinError(ctypes.get_last_error())
        self.u.InvalidateRect(self.hwnd,None,False);self.u.UpdateWindow(self.hwnd)
        self.draw_count+=1

    def set_backend(self,backend):
        self.backend=backend
        if hasattr(backend,'set_opacity'):
            backend.set_opacity(self._opacity)
            self.u.SetLayeredWindowAttributes(self.hwnd,0,255,2)
        for dc,bitmap,previous,_ in self.buffers:
            self.g.SelectObject(dc,previous);self.g.DeleteObject(bitmap);self.g.DeleteDC(dc)
        self.buffers.clear()
        self.render(1.0)

    def attributes(self,name,value):
        if name=='-alpha':
            self._opacity=value
            if self.backend is not None and hasattr(self.backend,'set_opacity'):
                self.backend.set_opacity(value)
                return
            if not self.u.SetLayeredWindowAttributes(self.hwnd,0,round(value*255),2):
                raise ctypes.WinError(ctypes.get_last_error())

    def winfo_exists(self):
        return bool(self.hwnd and self.u.IsWindow(self.hwnd))

    def destroy(self):
        if self.backend is not None:self.backend.close();self.backend=None
        if self.old_proc and self.hwnd:
            self.u.SetWindowLongPtrW(self.hwnd,-4,self.old_proc);self.old_proc=None
        if self.hwnd:self.u.DestroyWindow(self.hwnd)
        self.hwnd=None
        if self.owner is not None and self.owner.winfo_exists():self.owner.destroy()
        for dc,bitmap,previous,_ in self.buffers:
            self.g.SelectObject(dc,previous);self.g.DeleteObject(bitmap);self.g.DeleteDC(dc)
        self.buffers.clear()
