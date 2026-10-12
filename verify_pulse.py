from PIL import Image,ImageDraw,ImageChops
from zoom_effect import zoom_scale,pulse_texture,jitter_offset,chromatic_opacities,chromatic_segments,pulse_parameters

for t in (0,.3,.5,1.5,2,5,30):assert chromatic_opacities(t)==(0,0)
reveal=[]
for i in range(50,101):
    a,b=chromatic_opacities(i/100)
    reveal.append(1-(1-a)*(1-b))
assert reveal[0]==0 and reveal[-1]==1
assert all(a<=b+1e-9 for a,b in zip(reveal,reveal[1:]))
assert reveal[1]<.002 and max(b-a for a,b in zip(reveal,reveal[1:]))<.031
assert pulse_parameters(0)==pulse_parameters(2)==(0,0,0)
assert abs(pulse_parameters(.5)[0]-.1)<1e-8 and pulse_parameters(.5)[1]==0
assert abs(pulse_parameters(1)[0]-.2)<1e-8 and pulse_parameters(1)[1]==.6
assert chromatic_opacities(1)==(0,1)
for t in (.7,.8,.9,1.1,1.2,1.3):
    a,b=chromatic_opacities(t)
    assert 0<=a<=1 and 0<=b<=1
    mirror=chromatic_opacities(2-t)
    assert abs(a-mirror[0])<1e-8 and abs(b-mirror[1])<1e-8
assert chromatic_opacities(.7)[0]>chromatic_opacities(.7)[1]
assert chromatic_opacities(.9)[0]<chromatic_opacities(.9)[1]
for elapsed in (0,.65,1,1.5):
    for channel in (0,1):
        segments=list(chromatic_segments(elapsed,channel))
        assert segments[0][0]==0
        assert segments[-1][1]==0 and segments[-1][2]==0

for interval in (5,15,30):
    values=[zoom_scale(i/100,interval,'pulse') for i in range(interval*100+1)]
    assert abs(values[100]-1.1)<1e-8
    assert all(a<=b for a,b in zip(values[:100],values[1:101]))
    assert all(a>=b for a,b in zip(values[100:200],values[101:201]))
    assert all(v==1.0 for v in values[200:]),'The pulse must not repeat'
    assert jitter_offset(interval)==(0,0),'Jitter must stop with the pulse'

grid=Image.new('RGB',(640,360),'black');draw=ImageDraw.Draw(grid)
for x in range(0,640,32):draw.line((x,0,x,359),fill='white',width=6)
for y in range(0,360,32):draw.line((0,y,639,y),fill='white',width=6)
lens=pulse_texture(grid,chromatic_strength=0)
fringe=pulse_texture(grid)
assert ImageChops.difference(grid,lens).getbbox(),'Lens distortion missing'
red,green,blue=fringe.split()
assert ImageChops.difference(red,green).getextrema()[1]>20,'Red fringe too faint'
assert ImageChops.difference(blue,green).getextrema()[1]>20,'Blue fringe too faint'
assert 145<=max(hi for lo,hi in ImageChops.difference(lens,fringe).getextrema())<=154
white=pulse_texture(Image.new('RGB',(640,360),'white'))
assert white.getextrema()==((255,255),)*3,'Lens introduced uncovered borders'
print('Single 2s pulse, lens strength follows zoom, 50%-to-peak aberration and neutral rest passed')
