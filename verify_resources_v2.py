import ctypes,time
from PIL import Image
from animated_surface import AnimatedSurface
from wallpaper_engine import WindowsWallpaperEngine
ctypes.windll.shcore.SetProcessDpiAwareness(1)
e=WindowsWallpaperEngine();parent=e._wallpaper_layer()
u=ctypes.windll.user32;u.GetGuiResources.argtypes=[ctypes.c_void_p,ctypes.c_uint]
process=ctypes.c_void_p(-1)
im=Image.new('RGB',(64,64),(20,80,100))
# Warm up Windows graphics before comparing per-surface allocations.
for effect in ('smooth','pulse'):
    s=AnimatedSurface(parent,im,opacity=0,effect=effect);s.start_zoom(5,effect);time.sleep(.06);s.destroy()
before=(u.GetGuiResources(process,0),u.GetGuiResources(process,1))
for effect in ('smooth','pulse')*3:
    s=AnimatedSurface(parent,im,opacity=0,effect=effect);s.start_zoom(5,effect);time.sleep(.06);s.destroy()
time.sleep(.1)
after=(u.GetGuiResources(process,0),u.GetGuiResources(process,1))
print('Repeated surface cleanup GDI/USER handles:',before,after)
assert after[0]<=before[0]+2 and after[1]<=before[1]+2
