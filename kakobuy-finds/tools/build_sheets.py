import json,os,hashlib
from PIL import Image, ImageOps
P=[json.loads(l.strip().rstrip(',')) for l in open('products.jsonl') if l.strip()]
def fn(u): return 'full/'+hashlib.md5(u.encode()).hexdigest()+'.jpg'
OUT='site'; os.makedirs(OUT+'/img/c',exist_ok=True); os.makedirs(OUT+'/img/g',exist_ok=True)
CW,CH,CC,CR=400,500,3,4      # card cells
GW,GH,GC,GR=520,650,6,4      # gallery cells
BG=(20,20,19)
def load(u):
    im=Image.open(fn(u)); im=ImageOps.exif_transpose(im)
    if im.mode in ('RGBA','LA','P'):
        im=im.convert('RGBA'); b=Image.new('RGB',im.size,(255,255,255)); b.paste(im,mask=im.split()[-1]); im=b
    return im.convert('RGB')
bad=[]
for s in range(0,len(P),CC*CR):
    sh=Image.new('RGB',(CW*CC,CH*CR),BG)
    for k in range(s,min(s+CC*CR,len(P))):
        c=k-s; u=P[k]['image']
        if not u: continue
        try: sh.paste(ImageOps.fit(load(u),(CW,CH),Image.LANCZOS),((c%CC)*CW,(c//CC)*CH))
        except Exception as e: bad.append((k,str(e)))
    sh.save(f'{OUT}/img/c/{s//(CC*CR):03d}.jpg',quality=74,optimize=True,progressive=True)
for s in range(0,len(P),GR):
    sh=Image.new('RGB',(GW*GC,GH*GR),BG)
    for k in range(s,min(s+GR,len(P))):
        r=k-s
        for j,u in enumerate(P[k]['photos'][:GC]):
            try:
                im=load(u); im.thumbnail((GW,GH),Image.LANCZOS)
                sh.paste(im,(j*GW+(GW-im.width)//2, r*GH+(GH-im.height)//2))
            except Exception as e: bad.append((k,j,str(e)))
    sh.save(f'{OUT}/img/g/{s//GR:03d}.jpg',quality=64,optimize=True,progressive=True)
print('bad',bad)
