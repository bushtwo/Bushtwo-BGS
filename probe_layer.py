import ctypes, time, tkinter as tk
from ctypes import wintypes
from PIL import ImageGrab
u=ctypes.windll.user32
ctypes.windll.shcore.SetProcessDpiAwareness(1)
u.FindWindowExW.argtypes=[wintypes.HWND,wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR]
u.FindWindowExW.restype=wintypes.HWND
u.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR]
u.FindWindowW.restype=wintypes.HWND
progman=u.FindWindowW('Progman',None)
u.SendMessageTimeoutW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM,wintypes.UINT,wintypes.UINT,ctypes.POINTER(ctypes.c_size_t)]
result=ctypes.c_size_t()
u.SendMessageTimeoutW(progman,0x052c,0,0,2,1000,ctypes.byref(result))
hosts=[]
ET=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
@ET
def visit(h,p):
    v=u.FindWindowExW(h,None,'SHELLDLL_DefView',None)
    if v:
        hosts.append((h,v,u.FindWindowExW(v,None,'SysListView32',None)))
    return True
u.EnumWindows(visit,0)
print('Hosts:',hosts)
worker=u.FindWindowExW(None,hosts[0][0],'WorkerW',None) or u.FindWindowExW(progman,None,'WorkerW',None)
print('Wallpaper worker:',worker)
r=tk.Tk(); r.withdraw()
t=tk.Toplevel(r); t.withdraw(); t.overrideredirect(True)
t.geometry('400x400+0+0')
l=tk.Label(t,bg='#00ffff');l.pack(fill='both',expand=True)
t.update_idletasks()
h=int(t.wm_frame(),16)
u.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int]
u.SetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_long]
u.SetWindowLongW(h,-16,(u.GetWindowLongW(h,-16)&~0x80000000)|0x40000000)
u.SetWindowLongW(h,-20,u.GetWindowLongW(h,-20)|0x80000|0x20|0x08000000)
sp=ctypes.WinDLL('user32',use_last_error=True).SetParent
sp.argtypes=[wintypes.HWND,wintypes.HWND];sp.restype=wintypes.HWND
u.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
u.SetLayeredWindowAttributes.argtypes=[wintypes.HWND,wintypes.DWORD,wintypes.BYTE,wintypes.DWORD]
try:
    for parent, after in [(worker,1)] if worker else []:
        if not sp(h,parent) and ctypes.get_last_error(): raise ctypes.WinError(ctypes.get_last_error())
        t.deiconify()
        u.SetWindowPos(h,after,0,0,400,400,0x10|0x40|0x20)
        u.SetLayeredWindowAttributes(h,0,255,2)
        for _ in range(15):
            r.update(); time.sleep(0.02)
        shot=ImageGrab.grab()
        count=sum(1 for color in shot.crop((0,0,400,400)).getdata() if color[:3]==(0,255,255))
        print('Parent:',parent,'visible cyan pixels:',count,'sample:',shot.getpixel((200,200)))
finally:
    t.destroy();r.destroy()
