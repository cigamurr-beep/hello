# usage: python3 align2.py vo.mp3 lines.json > seg.js
# Aligns each script line to faster-whisper word timings by cumulative letter count.
import sys,json,re
from faster_whisper import WhisperModel
LINES=json.load(open(sys.argv[2]))
L=lambda s:len(re.sub(r'[^a-zčćšđž0-9]','',s.lower()))
m=WhisperModel("small",device="cpu",compute_type="int8")
segs,info=m.transcribe(sys.argv[1],language="sr",word_timestamps=True)
W=[w for s in segs for w in s.words]
cum=[];c=0
for w in W: c+=L(w.word); cum.append(c)
scale=c/sum(L(t) for _,t in LINES)
out=[];acc=0;wi=0
for k,(sid,text) in enumerate(LINES):
    acc+=L(text)
    we=len(W)-1 if k==len(LINES)-1 else min(range(wi,len(W)),key=lambda j:abs(cum[j]-acc*scale))
    out.append(dict(id=sid,text=text,va=round(W[wi].start,2),vb=round(W[we].end,2)))
    wi=we+1
for k,o in enumerate(out): o['a']=0.0 if k==0 else round((out[k-1]['vb']+o['va'])/2,2)
for k,o in enumerate(out): o['b']=out[k+1]['a'] if k<len(out)-1 else round(max(info.duration,o['vb'])+1.0,2)
print('window.SEG='+json.dumps(out,ensure_ascii=False)+';\nwindow.TOTAL='+str(out[-1]['b'])+';')
