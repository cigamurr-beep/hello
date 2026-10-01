import json,os,subprocess,hashlib
from concurrent.futures import ThreadPoolExecutor
P=[json.loads(l.strip().rstrip(',')) for l in open('products.jsonl') if l.strip()]
os.makedirs('full',exist_ok=True)
urls=set()
for p in P:
    for u in p['photos'][:6]: urls.add(u)
def fn(u): return 'full/'+hashlib.md5(u.encode()).hexdigest()+'.jpg'
def dl(u):
    f=fn(u)
    if os.path.exists(f) and os.path.getsize(f)>1000: return 1
    for t in range(3):
        r=subprocess.run(["curl","-sS","-m","40","-o",f,u+"?w=800"],capture_output=True)
        if r.returncode==0 and os.path.getsize(f)>1000: return 1
    return 0
with ThreadPoolExecutor(16) as ex: r=list(ex.map(dl,sorted(urls)))
print(len(urls),sum(r))
