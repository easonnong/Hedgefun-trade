#!/usr/bin/env python3
"""How often would a listing's deviation gate be open? Pool vs Chainlink, over whatever the pool's observation ring spans.

    python3 tools/gate_uptime.py <v3Pool> <stockFeed> <usdgFeed> <stock> <out.json>

Every 300 s back through the ring: the pool's 60-second mean against the feed round in force at that moment (stock
feed / USDG feed). Prints the |gap| distribution and the share of samples inside 30 and 50 bps. Approximates
`HedgeFunTreasury.health` (which uses spot, and also checks spot against the 600 s mean). Read-only, writes only
<out.json>. Used for the +/-1% rule question, 2026-09-24 (test/TightRuleFork.t.sol).
"""
import bisect, json, re, subprocess, sys, time

R="https://rpc.mainnet.chain.robinhood.com"
def c(to,sig,*a):
    for i in range(5):
        r=subprocess.run(["cast","call",to,sig,*a,"--rpc-url",R],capture_output=True,text=True)
        if r.returncode==0: return r.stdout.strip().split("\n")
        time.sleep(1.5)
    raise RuntimeError(r.stderr)
n=lambda x:int(x.split()[0])
POOL,FEED,UF,STOCK=sys.argv[1:5]; USDG="0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168"
usdg0=int(USDG,16)<int(STOCK,16)
s0=c(POOL,"slot0()(uint160,int24,uint16,uint16,uint16,uint8,bool)"); idx=n(s0[2]); card=n(s0[3])
now=int(time.time())
oldest=c(POOL,"observations(uint256)(uint32,int56,uint160,bool)",str((idx+1)%card))
if oldest[3]!="true": oldest=c(POOL,"observations(uint256)(uint32,int56,uint160,bool)","0")
span=now-n(oldest[0]); print("ring span hours",round(span/3600,1))
# feed history
def rounds(feed,since):
    out=[]; rid=n(c(feed,"latestRoundData()(uint80,int256,uint256,uint256,uint80)")[0])
    while True:
        r=c(feed,"getRoundData(uint80)(uint80,int256,uint256,uint256,uint80)",str(rid))
        out.append((n(r[3]),n(r[1]))); 
        if n(r[3])<since: break
        rid-=1
    return sorted(out)
fr=rounds(FEED,now-span); ur=rounds(UF,now-span-86400)
print("feed rounds in window",len(fr))
step=300; agos=list(range(0,span-60,step))
res=[]
# batch observe: [a+60, a] pairs -> 60s mean tick
for a in agos:
    try: o=c(POOL,"observe(uint32[])(int56[],uint160[])",f"[{a+60},{a}]")
    except Exception: continue
    tc=[int(x) for x in re.findall(r"-?\d+(?=\s*\[|\s*,|\s*\]$)", re.sub(r"\[[0-9.e+-]+\]","",o[0]))]
    tick=(tc[1]-tc[0])/60; r=1.0001**tick
    spot=(1e12/r) if usdg0 else r*1e12
    ts=now-a
    fi=bisect.bisect_right([x[0] for x in fr],ts)-1; ui=bisect.bisect_right([x[0] for x in ur],ts)-1
    if fi<0 or ui<0: continue
    feed=fr[fi][1]/ur[ui][1]
    res.append((ts,(spot/feed-1)*1e4, (ts-fr[fi][0])/3600))
json.dump(res,open(sys.argv[5],"w"))
g=[abs(x[1]) for x in res]; g.sort()
q=lambda p:g[min(len(g)-1,int(p*len(g)))]
print(f"samples {len(g)} (every {step}s, 60s-mean vs feed)  median {q(.5):.0f}bp p90 {q(.9):.0f} p99 {q(.99):.0f} max {g[-1]:.0f}")
for d in (30,50): print(f"  within {d}bp: {sum(1 for x in g if x<=d)/len(g):.0%}")
