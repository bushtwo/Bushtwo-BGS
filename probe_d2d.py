import ctypes,time
from PIL import Image
from native_zoom import NativeZoom
from wallpaper_engine import WindowsWallpaperEngine
from composition_renderer import CompositionRenderer as Renderer
ctypes.windll.shcore.SetProcessDpiAwareness(1)
e=WindowsWallpaperEngine();parent=e._wallpaper_layer()
im=Image.new('RGB',(2560,1440),(0,255,255))
s=NativeZoom(parent,im)
try:
    r=Renderer(s.hwnd,im)
    try:
        costs=[]
        for i in range(10):
            t=time.monotonic();r.draw(1+i*.001);costs.append(time.monotonic()-t)
        print('Hardware Direct2D draw ms:',round(sum(costs)/len(costs)*1000,3))
    finally:r.close()
finally:s.destroy()
