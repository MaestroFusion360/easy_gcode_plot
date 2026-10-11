"""GPU dexel removal and conservative maximum-height traversal (OpenGL 4.3)."""

REMOVE = r"""#version 430
layout(local_size_x=8, local_size_y=8) in;
layout(rg32f, binding=0) uniform image2D stock;
layout(std430, binding=0) readonly buffer Profile { vec2 profile[]; };
uniform ivec2 first, last;
uniform vec2 pitch;
uniform vec3 begin, end;
uniform int profileCount, kind, rapid, reset;
uniform float radius, ballRadius, corner, taperAngle, top, pathRadius;
uniform vec4 arc;
uniform int isArc;
const float INF = 3.402823e38;

// Closed radial disk: the first/last valid parameter on a straight sweep.
bool interval(vec2 p, vec2 d, float r, out vec2 ab) {
    float l2=dot(d,d);
    if(l2==0.0) { ab=vec2(0,1); return dot(p,p)<=r*r; }
    float q=dot(p,d)/l2;
    // A cross product avoids cancellation for long, almost collinear cuts.
    float cross=p.x*d.y-p.y*d.x;
    float perp=cross*cross/l2;
    if(perp>r*r) return false;
    float span=sqrt(max(0.0,(r*r-perp)/l2));
    ab=vec2(max(0.0,q-span), min(1.0,q+span));
    return ab.x<=ab.y;
}
float tip(float r) {
    if(kind==1) return ballRadius-sqrt(max(0.0,ballRadius*ballRadius-r*r));
    if(kind==3) {
        float transition=ballRadius*cos(taperAngle);
        if(r<=transition) return ballRadius-sqrt(max(0.0,ballRadius*ballRadius-r*r));
        return ballRadius*(1.0-sin(taperAngle))+(r-transition)/tan(taperAngle);
    }
    float rho=max(0.0,r-(radius-corner));
    return corner-sqrt(max(0.0,corner*corner-rho*rho));
}
float curved(vec2 p, vec3 d, vec2 ab) {
    float l2=dot(d.xy,d.xy);
    if(l2==0.0) return min(0.0,d.z)+tip(length(p));
    float q=dot(p,d.xy)/l2;
    float t=clamp(q,ab.x,ab.y);
    if(d.z!=0.0 && kind==1) {
        float cross=p.x*d.y-p.y*d.x;
        float perp=cross*cross/l2;
        t=clamp(q-d.z*sqrt(max(0.0,ballRadius*ballRadius-perp))/sqrt(l2*(l2+d.z*d.z)),ab.x,ab.y);
    } else if(d.z!=0.0) {
        // Bull tip is convex. Bisect its monotone derivative to float precision.
        float lo=ab.x, hi=ab.y;
        for(int i=0;i<32;i++) {
            float mid=(lo+hi)*0.5;
            if(mid==lo || mid==hi) break;
            vec2 v=mid*d.xy-p;
            float r=length(v), rho=max(0.0,r-(radius-corner));
            float slope;
            if(kind==3) slope=r<=ballRadius*cos(taperAngle)
                ?r/sqrt(max(1e-30,ballRadius*ballRadius-r*r)):1.0/tan(taperAngle);
            else slope=rho/sqrt(max(1e-30,corner*corner-rho*rho));
            float derivative=d.z+slope*dot(v,d.xy)/max(r,1e-30);
            if(derivative<0.0) lo=mid; else hi=mid;
        }
        t=(lo+hi)*0.5;
    }
    return min(d.z*t+tip(length(p-t*d.xy)),
               min(d.z*ab.x+tip(length(p-ab.x*d.xy)),d.z*ab.y+tip(length(p-ab.y*d.xy))));
}
float coneValue(vec2 p, vec3 d, float t, vec2 a, float slope) {
    return d.z*t+a.x+(length(p-t*d.xy)-a.y)*slope;
}
float envelope(vec2 p, vec3 d) {
    vec2 ab;
    if(!interval(p,d.xy,radius,ab)) return INF;
    if(kind!=0) return curved(p,d,ab);
    float result=INF, l2=dot(d.xy,d.xy);
    for(int i=0;i<profileCount;i++) {
        vec2 a=profile[i];
        // Every axial vertex also bounds its interior disk.
        if(interval(p,d.xy,a.y,ab)) result=min(result,a.x+d.z*(d.z>=0.0?ab.x:ab.y));
        if(i+1==profileCount) break;
        vec2 b=profile[i+1];
        if(b.y==a.y) continue;
        float r0=min(a.y,b.y), r1=max(a.y,b.y);
        if(!interval(p,d.xy,r1,ab)) continue;
        float slope=(b.x-a.x)/(b.y-a.y);
        if(l2==0.0) {
            float r=length(p);
            if(r>=r0) result=min(result,min(0.0,d.z)+a.x+(r-a.y)*slope);
            continue;
        }
        float q=dot(p,d.xy)/l2;
        float cross=p.x*d.y-p.y*d.x;
        float perp=cross*cross/l2;
        // The annulus has at most two parameter intervals. Evaluate its
        // boundaries plus the stationary point of each conical span.
        for(int side=0;side<2;side++) {
            vec2 range=side==0?vec2(ab.x,min(ab.y,q)):vec2(max(ab.x,q),ab.y);
            if(perp<r0*r0) {
                float gap=sqrt((r0*r0-perp)/l2);
                if(side==0) range.y=min(range.y,q-gap);
                else range.x=max(range.x,q+gap);
            }
            if(range.x>range.y) continue;
            result=min(result,coneValue(p,d,range.x,a,slope));
            result=min(result,coneValue(p,d,range.y,a,slope));
            float denom=slope*slope*l2-d.z*d.z;
            if(slope>0.0 && denom>0.0) {
                float t=clamp(q-d.z*sqrt(max(0.0,perp/(l2*denom))),range.x,range.y);
                result=min(result,coneValue(p,d,t,a,slope));
            }
        }
    }
    return result;
}
void main() {
    ivec2 cell=first+ivec2(gl_GlobalInvocationID.xy);
    if(any(greaterThanEqual(cell,last))) return;
    if(reset!=0) { imageStore(stock,cell,vec4(top,0,0,0)); return; }
    vec2 old=imageLoad(stock,cell).rg;
    vec2 point=vec2(cell)*pitch;
    float height;
    if(isArc!=0) {
        vec2 relative=point-arc.xy;
        float angle=atan(relative.y,relative.x);
        float travel=mod(sign(arc.w)*(angle-arc.z),6.283185307179586);
        float distance;
        if(travel<=abs(arc.w)) distance=abs(length(relative)-pathRadius);
        else distance=min(length(point-begin.xy),length(point-end.xy));
        height=begin.z+envelope(vec2(distance,0),vec3(0));
    } else height=begin.z+envelope(point-begin.xy,end-begin);
    height=max(0.0,height);
    if(height<old.r) imageStore(stock,cell,vec4(height,max(old.g,float(rapid)),0,0));
}
"""

REDUCE = r"""#version 430
layout(local_size_x=8, local_size_y=8) in;
layout(rg32f, binding=0) readonly uniform image2D source;
layout(rg32f, binding=1) writeonly uniform image2D target;
uniform ivec2 first, last;
void main() {
    ivec2 p=first+ivec2(gl_GlobalInvocationID.xy);
    if(any(greaterThanEqual(p,last))) return;
    ivec2 size=imageSize(source);
    float high=0.0;
    for(int y=0;y<2;y++) for(int x=0;x<2;x++) {
        ivec2 q=p*2+ivec2(x,y);
        if(all(lessThan(q,size))) high=max(high,imageLoad(source,q).r);
    }
    imageStore(target,p,vec4(high,0,0,0));
}
"""

VERTEX = r"""#version 430
void main() {
    vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);
    gl_Position=vec4(p*2.0-1.0,0,1);
}
"""

FRAGMENT = r"""#version 430
uniform sampler2D stock;
uniform mat4 mvp, inverseMvp;
uniform vec4 viewport;
uniform vec3 origin, extent;
uniform vec2 pitch;
uniform ivec2 cells;
uniform int maxLevel;
uniform vec4 stockColor, cutColor, rapidColor;
out vec4 color;

bool box(vec3 o, vec3 d, vec3 lo, vec3 hi, out float enter, out float leave, out vec3 normal) {
    enter=-3.402823e38; leave=3.402823e38; normal=vec3(0);
    for(int a=0;a<3;a++) {
        if(d[a]==0.0) { if(o[a]<lo[a] || o[a]>hi[a]) return false; }
        else {
            float u=(lo[a]-o[a])/d[a], v=(hi[a]-o[a])/d[a];
            if(min(u,v)>enter) { enter=min(u,v); normal=vec3(0); normal[a]=-sign(d[a]); }
            leave=min(leave,max(u,v));
        }
    }
    return enter<=leave;
}
vec2 sampleHeight(ivec2 p) {
    return texelFetch(stock,clamp(p,ivec2(0),cells),0).rg;
}
vec2 heightMaterial(vec2 xy) {
    vec2 grid=clamp(xy/pitch,vec2(0),vec2(cells));
    ivec2 cell=min(ivec2(floor(grid)),cells-1);
    vec2 uv=grid-vec2(cell);
    vec2 h00=sampleHeight(cell), h10=sampleHeight(cell+ivec2(1,0));
    vec2 h01=sampleHeight(cell+ivec2(0,1)), h11=sampleHeight(cell+ivec2(1,1));
    float hx=h10.r-h00.r, hy=h01.r-h00.r;
    float hxy=h11.r-h10.r-h01.r+h00.r;
    float height=h00.r+hx*uv.x+hy*uv.y+hxy*uv.x*uv.y;
    float rapid=mix(mix(h00.g,h10.g,uv.x),mix(h01.g,h11.g,uv.x),uv.y);
    return vec2(clamp(height,0.0,extent.z),rapid);
}
void shadeHit(vec3 position, vec3 normal, vec4 tint) {
    vec4 clip=mvp*vec4(position+origin,1);
    gl_FragDepth=(clip.z/clip.w)*0.5+0.5;
    float light=0.35+0.65*max(0.0,dot(normal,normalize(vec3(-0.4,-0.6,1.0))));
    color=vec4(tint.rgb*light,tint.a);
}
bool intersectHeightPatch(vec3 o, vec3 d, ivec2 cell, float start, float finish,
           inout vec3 normal, out float distance, out vec2 material) {
    vec2 h00=sampleHeight(cell), h10=sampleHeight(cell+ivec2(1,0));
    vec2 h01=sampleHeight(cell+ivec2(0,1)), h11=sampleHeight(cell+ivec2(1,1));
    float hx=h10.r-h00.r, hy=h01.r-h00.r;
    float hxy=h11.r-h10.r-h01.r+h00.r;
    vec3 p=o+start*d;
    vec2 uv=clamp(p.xy/pitch-vec2(cell),vec2(0),vec2(1));
    vec2 speed=d.xy/pitch;
    // Intersect z(t) with the bilinear height patch. Substitution produces
    // a quadratic, solved directly rather than by a ray-march step size.
    float A=-hxy*speed.x*speed.y;
    float B=d.z-hx*speed.x-hy*speed.y-hxy*(uv.x*speed.y+uv.y*speed.x);
    float C=p.z-h00.r-hx*uv.x-hy*uv.y-hxy*uv.x*uv.y;
    float s=3.402823e38;
    bool boundary=C<=0.0;
    if(boundary) s=0.0;
    else if(A==0.0) {
        if(B<0.0) s=-C/B;
    } else {
        float discriminant=B*B-4.0*A*C;
        if(discriminant>=0.0) {
            float q=-0.5*(B+(B>=0.0?1.0:-1.0)*sqrt(discriminant));
            float r0=q/A;
            float r1=q!=0.0?C/q:3.402823e38;
            if(r0>=0.0 && B+2.0*A*r0<=0.0) s=r0;
            if(r1>=0.0 && B+2.0*A*r1<=0.0) s=min(s,r1);
        }
    }
    if(s>finish-start) return false;
    distance=start+s;
    uv=clamp(uv+s*speed,vec2(0),vec2(1));
    material=mix(mix(h00,h10,uv.x),mix(h01,h11,uv.x),uv.y);
    material.r=h00.r+hx*uv.x+hy*uv.y+hxy*uv.x*uv.y;
    normal=normalize(vec3(-(hx+hxy*uv.y)/pitch.x,-(hy+hxy*uv.x)/pitch.y,1));
    return true;
}
void main() {
    vec2 ndc=(gl_FragCoord.xy-viewport.xy)/viewport.zw*2.0-1.0;
    vec4 a=inverseMvp*vec4(ndc,-1,1), b=inverseMvp*vec4(ndc,1,1);
    vec3 o=a.xyz/a.w-origin, d=b.xyz/b.w-origin-o;
    float entry, exit; vec3 normal;
    if(!box(o,d,vec3(0),extent,entry,exit,normal)) discard;
    // The stock boundary has its own exact plane normal. Do not infer a box
    // face from a reconstructed point's floating-point equality with a plane.
    // This also closes the underside wherever any material remains above it.
    if(entry>=0.0) {
        vec3 boundaryPosition=clamp(o+entry*d,vec3(0),extent);
        vec2 material=heightMaterial(boundaryPosition.xy);
        if(material.r>0.0 && boundaryPosition.z<=material.r) {
            shadeHit(boundaryPosition,normal,stockColor);
            return;
        }
    }
    float t=max(0.0,entry);
    // No step-count cap: traverse conservative height bounds until the first
    // solid dexel or the exact stock-box exit. No fixed ray-march step size.
    while(t<=exit) {
        vec3 p=o+t*d;
        ivec2 cell=clamp(ivec2(floor(p.xy/pitch)),ivec2(0),cells-1);
        // At a shared boundary select the cell in the ray's direction.
        for(int axis=0;axis<2;axis++) {
            if(d[axis]<0.0 && p[axis]<=float(cell[axis])*pitch[axis]) cell[axis]=max(0,cell[axis]-1);
        }
        float next=exit;
        bool advanced=false;
        for(int level=maxLevel;level>=0;level--) {
            ivec2 node=cell>>level;
            vec2 lo=vec2(node<<level)*pitch;
            vec2 hi=min(vec2((node+1)<<level)*pitch,extent.xy);
            // A patch uses its four corner samples. Include the neighbouring
            // mip nodes so every bound remains conservative at shared edges.
            ivec2 mipLast=textureSize(stock,level)-1;
            float high=0.0;
            for(int y=0;y<2;y++) for(int x=0;x<2;x++)
                high=max(high,texelFetch(stock,min(node+ivec2(x,y),mipLast),level).r);
            float tin,tout; vec3 n;
            bool hit=high>0.0 && box(o,d,vec3(lo,0),vec3(hi,high),tin,tout,n)
                     && tout>=t && tin<=exit;
            if(hit && level==0) {
                float distance; vec2 material;
                hit=intersectHeightPatch(o,d,cell,max(t,tin),min(exit,tout),n,distance,material);
                if(hit) {
                    vec3 position=o+distance*d;
                    vec4 tint=material.g>0.5?rapidColor:(material.r<extent.z?cutColor:stockColor);
                    shadeHit(position,n,tint);
                    return;
                }
            }
            if(!hit) {
                // Leave the XY node, even when its Z slab is missed.
                next=exit;
                for(int axis=0;axis<2;axis++) if(d[axis]!=0.0) {
                    float edge=d[axis]>0.0?hi[axis]:lo[axis];
                    next=min(next,(edge-o[axis])/d[axis]);
                }
                advanced=true;
                break;
            }
        }
        if(!advanced || next>=exit) break;
        // Advance by one representable positive float, not a physical step.
        t=uintBitsToFloat(floatBitsToUint(max(t,next))+1u);
    }
    discard;
}
"""
