"""Effect 1: continuously warp one cached GPU texture, with opaque output."""
import ctypes as C
from ctypes import wintypes as W
from functools import lru_cache
from d2d_renderer import GUID,method,check,release
from zoom_effect import pulse_parameters

SOURCE=b'''
Texture2D wallpaper : register(t0);
SamplerState filtering : register(s0);
cbuffer Settings : register(b0) { float lens; float fringe; float separation; float unused; };
struct Vertex { float4 position : SV_POSITION; float2 uv : TEXCOORD0; };
Vertex vertexMain(uint id : SV_VertexID) {
    Vertex v;
    v.uv=float2((id<<1)&2,id&2);
    v.position=float4(v.uv*float2(2,-2)+float2(-1,1),0,1);
    return v;
}
float2 warp(float2 uv,float strength) {
    float2 n=uv*2-1;
    float radius2=dot(n,n)*0.5;
    return (1+n*(1-strength*(1-radius2)))*0.5;
}
float4 pixelMain(Vertex v) : SV_TARGET {
    float3 color=wallpaper.Sample(filtering,warp(v.uv,lens)).rgb;
    if (fringe>0) {
        float red=wallpaper.Sample(filtering,warp(v.uv,max(0,lens+separation))).r;
        float blue=wallpaper.Sample(filtering,warp(v.uv,max(0,lens-separation))).b;
        color.r=lerp(color.r,red,fringe);
        color.b=lerp(color.b,blue,fringe);
    }
    return float4(color,1);
}
'''

class TextureDesc(C.Structure):
    _fields_=[(n,W.UINT) for n in ('width','height','mips','array','format','samples','quality','usage','bind','cpu','misc')]
class Data(C.Structure):
    _fields_=[('data',C.c_void_p),('pitch',W.UINT),('slice',W.UINT)]
class BufferDesc(C.Structure):
    _fields_=[(n,W.UINT) for n in ('size','usage','bind','cpu','misc','stride')]
class SamplerDesc(C.Structure):
    _fields_=[('filter',W.UINT),('u',W.UINT),('v',W.UINT),('w',W.UINT),
              ('bias',C.c_float),('anisotropy',W.UINT),('comparison',W.UINT),
              ('border',C.c_float*4),('min_lod',C.c_float),('max_lod',C.c_float)]
class Viewport(C.Structure):
    _fields_=[(n,C.c_float) for n in ('x','y','width','height','near','far')]

@lru_cache(maxsize=2)
def compile_shader(entry,target):
    compiler=C.WinDLL('d3dcompiler_47')
    compiler.D3DCompile.argtypes=[C.c_void_p,C.c_size_t,C.c_char_p,C.c_void_p,C.c_void_p,C.c_char_p,C.c_char_p,W.UINT,W.UINT,C.POINTER(C.c_void_p),C.POINTER(C.c_void_p)]
    compiler.D3DCompile.restype=W.LONG
    code=C.c_void_p();error=C.c_void_p()
    try:
        result=compiler.D3DCompile(SOURCE,len(SOURCE),None,None,None,entry,target,0x8000,0,C.byref(code),C.byref(error))
        if result<0 and error.value:
            message=method(error,3,C.c_void_p)(error)
            raise RuntimeError(C.string_at(message).decode('utf-8','replace'))
        check(result)
        return C.string_at(method(code,3,C.c_void_p)(code),method(code,4,C.c_size_t)(code))
    finally:release(code);release(error)

class PulseShader:
    def __init__(self,renderer,image):
        self.renderer=renderer;self.objects=[];self.sample=None;self.last_sample=None
        def obj():
            p=C.c_void_p();self.objects.append(p);return p
        self.texture=obj();self.view=obj();self.vertex=obj();self.pixel=obj();self.sampler=obj();self.constants=obj()
        device=renderer.device
        try:
            raw=C.create_string_buffer(image.convert('RGB').tobytes('raw','BGRX'))
            desc=TextureDesc(image.width,image.height,1,1,87,1,0,1,8,0,0)
            data=Data(C.cast(raw,C.c_void_p),image.width*4,0)
            check(method(device,5,W.LONG,C.POINTER(TextureDesc),C.POINTER(Data),C.POINTER(C.c_void_p))(device,C.byref(desc),C.byref(data),C.byref(self.texture)))
            check(method(device,7,W.LONG,C.c_void_p,C.c_void_p,C.POINTER(C.c_void_p))(device,self.texture,None,C.byref(self.view)))
            for index,entry,target,out in ((12,b'vertexMain',b'vs_4_0',self.vertex),(15,b'pixelMain',b'ps_4_0',self.pixel)):
                code=compile_shader(entry,target)
                check(method(device,index,W.LONG,C.c_void_p,C.c_size_t,C.c_void_p,C.POINTER(C.c_void_p))(device,code,len(code),None,C.byref(out)))
            sampler=SamplerDesc(0x15,3,3,3,0,1,1,(C.c_float*4)(0,0,0,0),0,3.402823e38)
            check(method(device,23,W.LONG,C.POINTER(SamplerDesc),C.POINTER(C.c_void_p))(device,C.byref(sampler),C.byref(self.sampler)))
            buf=BufferDesc(16,0,4,0,0,0)
            check(method(device,3,W.LONG,C.POINTER(BufferDesc),C.c_void_p,C.POINTER(C.c_void_p))(device,C.byref(buf),None,C.byref(self.constants)))
        except Exception:self.close();raise

    def set_sample(self,effect,elapsed):
        self.sample=pulse_parameters(elapsed) if effect=='pulse' else (0,0,0)

    def draw(self):
        if self.sample is None or self.sample==self.last_sample:return
        from composition_renderer import guid,query
        r=self.renderer;ctx=r.context3d
        surface=C.c_void_p();texture=C.c_void_p();target=C.c_void_p();drawing=False
        try:
            offset=W.POINT();iid=guid('cafcb56c-6ac3-4889-bf47-9e23bbd260ec')
            check(method(r.surface,3,W.LONG,C.c_void_p,C.POINTER(GUID),C.POINTER(C.c_void_p),C.POINTER(W.POINT))(r.surface,None,C.byref(iid),C.byref(surface),C.byref(offset)));drawing=True
            query(surface,guid('6f15aaf2-d208-4e89-9ab4-489535d34f9c'),texture)
            check(method(r.device,9,W.LONG,C.c_void_p,C.c_void_p,C.POINTER(C.c_void_p))(r.device,texture,None,C.byref(target)))
            values=(C.c_float*4)(*self.sample,0)
            method(ctx,48,None,C.c_void_p,W.UINT,C.c_void_p,C.c_void_p,W.UINT,W.UINT)(ctx,self.constants,0,None,values,0,0)
            method(ctx,17,None,C.c_void_p)(ctx,None)
            method(ctx,24,None,W.UINT)(ctx,4)
            method(ctx,11,None,C.c_void_p,C.c_void_p,W.UINT)(ctx,self.vertex,None,0)
            method(ctx,9,None,C.c_void_p,C.c_void_p,W.UINT)(ctx,self.pixel,None,0)
            method(ctx,23,None,C.c_void_p,C.c_void_p,W.UINT)(ctx,None,None,0)
            for index,pointer in ((8,self.view),(10,self.sampler),(16,self.constants)):
                method(ctx,index,None,W.UINT,W.UINT,C.POINTER(C.c_void_p))(ctx,0,1,C.byref(pointer))
            method(ctx,33,None,W.UINT,C.POINTER(C.c_void_p),C.c_void_p)(ctx,1,C.byref(target),None)
            method(ctx,35,None,C.c_void_p,C.c_void_p,W.UINT)(ctx,None,None,0xffffffff)
            method(ctx,43,None,C.c_void_p)(ctx,None)
            viewport=Viewport(offset.x,offset.y,r.width,r.height,0,1)
            method(ctx,44,None,W.UINT,C.POINTER(Viewport))(ctx,1,C.byref(viewport))
            method(ctx,13,None,W.UINT,W.UINT)(ctx,3,0)
            method(ctx,33,None,W.UINT,C.c_void_p,C.c_void_p)(ctx,0,None,None)
            check(method(r.surface,4,W.LONG)(r.surface));drawing=False
            self.last_sample=self.sample
        finally:
            if drawing:method(r.surface,4,W.LONG)(r.surface)
            release(target);release(texture);release(surface)

    def close(self):
        for p in reversed(self.objects):release(p)
