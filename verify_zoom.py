import math
from unittest.mock import Mock
from PIL import Image
from zoom_effect import zoom_scale, zoom_frame
from wallpaper_engine import WindowsWallpaperEngine
for interval in (5,15,30):
    for t in range(interval*100+1):
        s=zoom_scale(t/100,interval)
        assert 1<=s<=1.200001
    for t in range(5,interval,5):
        left=(zoom_scale(t,interval)-zoom_scale(t-.001,interval))/.001
        right=(zoom_scale(t+.001,interval)-zoom_scale(t,interval))/.001
        assert abs(left)<.0001 and abs(right)<.0001
assert zoom_scale(5,5)==zoom_scale(15,15)==1.2
assert zoom_scale(30,30)==1.0
im=Image.new('RGB',(100,100))
for x in range(100):
    for y in range(100):im.putpixel((x,y),(x*2,y*2,0))
out=zoom_frame(im,1.1)
assert out.size==im.size and abs(out.getpixel((50,50))[0]-im.getpixel((50,50))[0])<=2
for mode,timer,secs,expected in [('Fill','interval',5,True),('Fill','interval',15,True),('Fill','interval',30,True),('Fit','interval',5,False),('Center','interval',15,False),('Fill','day',30,False),('Fill','interval',60,False)]:
    e=WindowsWallpaperEngine.__new__(WindowsWallpaperEngine);e.stop_zoom=Mock();e.fade_transition=Mock()
    e.configure_zoom(True,mode,timer,secs,False,None)
    assert e._zoom_enabled==expected
print('Zoom range, centered crop, smooth reversals and eligibility passed')
