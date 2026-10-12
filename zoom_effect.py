"""Shared motion curves for the native compositor and software fallback."""
import math

def zoom_scale(elapsed, interval, effect='smooth'):
    elapsed = max(0.0, min(float(elapsed), float(interval)))
    # Effect 1 plays once (1s in, 1s out), then holds. Effect 2 uses 5s legs.
    leg = 1.0 if effect == 'pulse' else 5.0
    amplitude = 0.10 if effect == 'pulse' else 0.20
    if effect == 'pulse':
        elapsed = min(elapsed, 2.0)
        return 1.0 + amplitude * (1.0 - math.cos(math.pi * elapsed / leg)) / 2.0
    step = int(elapsed / leg)
    t = (elapsed - step * leg) / leg
    eased = t * t * (3 - 2 * t)
    return 1.0 + amplitude * (eased if step % 2 == 0 else 1 - eased)


def smooth_segments(interval, elapsed=0):
    """Five-second cubic legs, including a continuous partial leg on resume."""
    cursor = elapsed
    while cursor < interval:
        step = int(cursor / 5)
        local = cursor - step * 5
        sign = 1 if step % 2 == 0 else -1
        start = 1.0 if sign == 1 else 1.2
        # Expanded smoothstep: start + sign * (.024*t^2 - .0032*t^3).
        yield (cursor - elapsed,
               start + sign * (.024 * local**2 - .0032 * local**3),
               sign * (.048 * local - .0096 * local**2),
               sign * (.024 - .0096 * local), sign * -.0032)
        cursor = min(interval, (step + 1) * 5)


def pulse_texture(image, lens_strength=.20, chromatic_strength=.60, separation=1.0, lens_image=None):
    """Bake barrel distortion and radial color separation once per wallpaper."""
    from PIL import Image
    rgb = image.convert('RGB')
    width,height=rgb.size
    def distort(source,strength):
        if strength==0:return source.copy()
        def point(x,y):
            nx,ny=2*x/width-1,2*y/height-1
            radius2=(nx*nx+ny*ny)/2
            factor=1-strength*(1-radius2)
            return (width*(1+nx*factor)/2,height*(1+ny*factor)/2)
        mesh=[]
        for top in range(0,height,32):
            bottom=min(top+32,height)
            for left in range(0,width,32):
                right=min(left+32,width)
                quad=point(left,top)+point(left,bottom)+point(right,bottom)+point(right,top)
                mesh.append(((left,top,right,bottom),quad))
        return source.transform(source.size,Image.Transform.MESH,mesh,Image.Resampling.BILINEAR)
    warped=lens_image if lens_image is not None else distort(rgb,lens_strength)
    if chromatic_strength==0:return warped
    r,g,b=warped.split()
    # Opposing radial channel warps make the fringe visible around details;
    # all samples stay inside the image, so the screen remains fully covered.
    red=distort(rgb.getchannel('R'),max(0,lens_strength+.04*separation))
    blue=distort(rgb.getchannel('B'),max(0,lens_strength-.04*separation))
    return Image.merge('RGB',(Image.blend(r,red,chromatic_strength),g,
                              Image.blend(b,blue,chromatic_strength)))


def chromatic_opacities(elapsed):
    """Ease fringe opacity from 50% to the peak; mirror on the out-leg.

    Two opposite cached color separations gently crossfade back and forth.
    Return source-over opacities, preserving a maximum 60% channel fringe.
    """
    t=float(elapsed)
    if t<=.5 or t>=1.5:return (0.0,0.0)
    ramp=(min(t,2-t)-.5)/.5
    strength=ramp*ramp*(3-2*ramp)
    swing=(1-math.cos(2*math.pi*(t-.5)))/2
    first,second=strength*(1-swing),strength*swing
    return (first/(1-second) if second<1-1e-9 else 0.0,second)


def chromatic_segments(elapsed,channel):
    """Small native linear segments; the compositor interpolates every frame."""
    times=[elapsed]+[i/100 for i in range(50,151) if i/100>elapsed]+[2.0]
    for start,end in zip(times,times[1:]):
        if end<=start:continue
        a=chromatic_opacities(start)[channel]
        b=chromatic_opacities(end)[channel]
        yield (start-elapsed,a,(b-a)/(end-start),0.0,0.0)


def pulse_parameters(elapsed):
    """Opaque lens geometry follows zoom; only the color fringe fades."""
    t=max(0.0,min(2.0,float(elapsed)))
    lens=.20*(1-math.cos(math.pi*t))/2
    a,b=chromatic_opacities(t)
    opacity=1-(1-a)*(1-b)
    return lens,.60*opacity,.04*math.cos(2*math.pi*(t-.5)) if opacity else 0.0


def jitter_offset(elapsed):
    if elapsed>=2.0:return (0.0,0.0)
    return (.65 * math.sin(2 * math.pi * 7 * elapsed),
            .45 * math.sin(2 * math.pi * 11 * elapsed))


def zoom_frame(image, scale):
    from PIL import Image
    width, height = image.size
    crop_w, crop_h = width / scale, height / scale
    left, top = (width - crop_w) / 2, (height - crop_h) / 2
    return image.resize(image.size, Image.Resampling.BILINEAR,
                        box=(left, top, left + crop_w, top + crop_h))
