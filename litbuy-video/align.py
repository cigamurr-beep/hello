# usage: python3 align.py vo.mp3 > seg.js  -- aligns script lines to whisper word timings
import sys,json,re,unicodedata
from faster_whisper import WhisperModel
LINES=[('s1','Hoćeš da naručiš iz Kine, a nemaš pojma odakle da kreneš?',{}),
('s2','Evo kako ide preko LitBuy-a. Samo pet koraka.',{}),
('s3','Prvo, klikni na bio link.',{'step':1,'title':'Otvori bio link'}),
('s4','Otvori spreadsheet i izaberi šta ti se sviđa.',{'step':2,'title':'Izaberi iz spreadsheet-a'}),
('s5','Registruj se na LitBuy i ubaci link proizvoda.',{'step':3,'title':'Registracija + link'}),
('s6','Plati order, i to je to.',{'step':4,'title':'Plati order'}),
('s7','Sad samo čekaš da ti paket stigne.',{'step':5,'title':'Paket stiže'}),
('s8','Klikni na bio link i kreni sa svojim prvim haulom!',{})]
L=lambda s:len(re.sub(r'[^a-zčćšđž]','',s.lower()))
m=WhisperModel("small",device="cpu",compute_type="int8")
segs,info=m.transcribe(sys.argv[1],language="sr",word_timestamps=True)
W=[w for s in segs for w in s.words]
dur=info.duration
cum=[];c=0
for w in W: c+=L(w.word); cum.append(c)
tot_s=sum(L(t) for _,t,_ in LINES); scale=c/tot_s
out=[];acc=0;wi=0
for k,(sid,text,extra) in enumerate(LINES):
    acc+=L(text); target=acc*scale
    if k==len(LINES)-1: we=len(W)-1
    else:
        we=min(range(wi,len(W)),key=lambda j:abs(cum[j]-target))
    out.append(dict(id=sid,text=text,va=round(W[wi].start,2),vb=round(W[we].end,2),**extra))
    wi=we+1
for k,o in enumerate(out):
    o['a']=0.0 if k==0 else round((out[k-1]['vb']+o['va'])/2,2)
for k,o in enumerate(out):
    o['b']=out[k+1]['a'] if k<len(out)-1 else round(max(dur,o['vb'])+1.2,2)
print('window.SEG='+json.dumps(out,ensure_ascii=False)+';\nwindow.TOTAL='+str(out[-1]['b'])+';')
