import ctypes,time,threading,tkinter as tk,winreg
from ctypes import wintypes
from pathlib import Path
from PIL import Image,ImageGrab
from wallpaper_engine import WindowsWallpaperEngine,SCALING_STYLES,SPI_SETDESKWALLPAPER,SPIF_UPDATEINIFILE
ctypes.windll.shcore.SetProcessDpiAwareness(1)
e=WindowsWallpaperEngine();e.root=tk.Tk();e.root.withdraw()
original=e.get_current_system_wallpaper()
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Control Panel\Desktop') as key:
    style=winreg.QueryValueEx(key,'WallpaperStyle')[0];tile=winreg.QueryValueEx(key,'TileWallpaper')[0]
mode=next((m for m,v in SCALING_STYLES.items() if v==(style,tile)),'Fill')
p=Path(e.cache_dir)/'fade_visibility_check.bmp'
Image.new('RGB',(32,32),(0,255,255)).save(p)
samples=[];stop=threading.Event();ready=threading.Event()
u=ctypes.windll.user32;g=ctypes.windll.gdi32
u.GetDC.argtypes=[wintypes.HWND];u.GetDC.restype=wintypes.HDC
u.ReleaseDC.argtypes=[wintypes.HWND,wintypes.HDC]
g.GetPixel.argtypes=[wintypes.HDC,ctypes.c_int,ctypes.c_int];g.GetPixel.restype=wintypes.DWORD
started=time.monotonic()
def capture():
    dc=u.GetDC(None)
    try:
        while not stop.is_set():
            pixel=ImageGrab.grab(bbox=(1000,300,1001,301)).getpixel((0,0))
            samples.append((time.monotonic()-started,pixel))
            ready.set();stop.wait(0.008)
    finally:u.ReleaseDC(None,dc)
thread=threading.Thread(target=capture);thread.start();ready.wait()
finished=[]
try:
    time.sleep(0.15)
    e.fade_transition(original,str(p),mode,0.5,lambda:finished.append(time.monotonic()))
    assert e._active_overlay is not None,'Fade fallback occurred'
    deadline=time.monotonic()+3
    while not finished and time.monotonic()<deadline:e.root.update()
    assert finished,'Fade did not finish'
    time.sleep(0.8)
finally:
    stop.set();thread.join();e._cancel_fade()
    e._apply_scaling_registry(mode)
    u.SystemParametersInfoW(SPI_SETDESKWALLPAPER,0,original,SPIF_UPDATEINIFILE)
    e.root.destroy();p.unlink(missing_ok=True)
baseline=samples[0][1];target=(0,255,255)
def blend(pixel):
    channel=max(range(3),key=lambda c:abs(target[c]-baseline[c]))
    return (pixel[channel]-baseline[channel])/(target[channel]-baseline[channel])
values=[blend(pixel) for _,pixel in samples]
print('Captured:',len(samples),'last:',samples[-5:])
print('Distinct visible colors:',list(dict.fromkeys(pixel for _,pixel in samples))[:30])
assert any(0.1<v<0.9 for v in values),'No visible intermediate blend'
assert max(values)>0.99,'Next wallpaper not reached'
peak=0;regressions=[]
for (when,pixel),value in zip(samples,values):
    if peak-value>0.08:regressions.append((round(when,3),round(peak,3),round(value,3)))
    peak=max(peak,value)
print('Samples:',len(samples),'baseline:',baseline,'largest backwards jump:',round(max(max(values[:i+1])-v for i,v in enumerate(values)),3))
print('Regressions:',regressions[:12])
assert not regressions,'Next wallpaper flashed or reverted during the actual handoff'
assert values[-1]>0.99,'Final desktop does not retain next wallpaper'
print('Actual visible fade and native handoff passed; original wallpaper restored')
