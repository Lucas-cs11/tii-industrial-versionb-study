#!/usr/bin/env python3
import sys, json, time
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE)); sys.path.insert(0,str(HERE/'scripts'))
sys.path.insert(0,'/Users/lucas/Library/Mobile Documents/com~apple~CloudDocs/WorkingFiles/在投文章/TII_TPN/tpn-illustrative-case')
sys.path.insert(0,'/Users/lucas/Library/Mobile Documents/com~apple~CloudDocs/WorkingFiles/在投文章/TII_TPN/literature_tpn_case_eval/pipeline')
import model_def
from src.verifier import verify
from collections import defaultdict
import scg as lit
CONFIGS=[(14,60),(14,75),(14,90)]
def run_before(L,H):
    t=model_def.build(); st=time.time(); r=verify(t,L=L,H=H,complete_set=True); return r,round(time.time()-st,2)
def run_after(L,H):
    m=json.loads((HERE/'models'/'versionB_after.json').read_text()); t=model_def.from_canonical(m)
    st=time.time(); r=verify(t,L=L,H=H,complete_set=True); return r,round(time.time()-st,2)
def main():
    out=HERE/'results'/'sensitivity'; out.mkdir(parents=True,exist_ok=True)
    for L,H in CONFIGS:
        for name,fn in (('before',run_before),('after',run_after)):
            p=out/f'{name}_L{L}_H{H}.json'
            if p.exists():
                print('skip',name,L,H,flush=True); continue
            try:
                r,dt=fn(L,H)
                data={'L':L,'H':H,'verdict':r['result'],'enumeration_complete':r.get('enumeration_complete'),
                      'certificates':len(r['certificates']),'scg_classes':r['stats']['scg_classes'],
                      'scg_edges':r['stats']['scg_edges'],'runtime_s':dt,
                      'stats':{k:r['stats'][k] for k in ('scg_classes','scg_edges','candidate_words','candidate_words_processed','temporal_states','terminal_pairs','lp_calls')}}
                if r['certificates']:
                    c=r['certificates'][0]
                    data['first_certificate']={'phi':list(c.phi),'N':list(c.sigma_N),'F':list(c.sigma_F),
                                                'overlap':[str(c.overlap[0]),str(c.overlap[1])] if c.overlap else None,
                                                'oracle_check':'pending'}
                p.write_text(json.dumps(data,indent=1)+'\n')
                print('done',name,L,H,data['verdict'],data['certificates'],dt,flush=True)
            except Exception as e:
                p.write_text(json.dumps({'L':L,'H':H,'error':f'{type(e).__name__}: {e}'},indent=1)+'\n')
                print('error',name,L,H,e,flush=True)
if __name__=='__main__': main()
