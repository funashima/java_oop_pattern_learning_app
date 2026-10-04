"""Reproducible bounded-corpus evaluation; no participant data."""
import argparse
import csv
import hashlib
import json
import platform
import statistics
import time
import tracemalloc
from pathlib import Path
from pattern_lab.core import ROOT, LESSONS, load_trace, save_trace, summary, replay
from pattern_lab.runner import run_java, source_hash

def main():
    p=argparse.ArgumentParser();p.add_argument('--live',action='store_true',help='Javaで境界入力も実行（JDK必須）')
    p.add_argument('--out',type=Path,default=ROOT/'results'/'latest');args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True);rows=[]
    if args.live:(args.out/'traces').mkdir(exist_ok=True)
    for lesson in LESSONS:
        inputs=([0,1,100,10000] if lesson!='state' else [100]) if args.live else [100]
        for value in inputs:
            for variant in ('normal','broken'):
                started=time.perf_counter()
                events=run_java(lesson,variant,value) if args.live else load_trace(ROOT/'traces'/f'{lesson}_{variant}.jsonl')
                java_ms=(time.perf_counter()-started)*1000 if args.live else None
                result=summary(events)
                # Warm up; benchmark small-model reconstruction only, not GUI or Java.
                replay(events); samples=[]
                for _ in range(30):
                    t=time.perf_counter_ns();replay(events);samples.append((time.perf_counter_ns()-t)/1e6)
                tracemalloc.start();replay(events);_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                row={'lesson':lesson,'variant':variant,'input':value,'events':len(events),
                     'checkpoints':sum(e['kind']=='checkpoint' for e in events),
                     'integrity':result['integrity'],'contract':result['contract'],
                     'expected_contract':'PASS' if variant=='normal' else 'FAIL',
                     'replay_median_ms':round(statistics.median(samples),4),'replay_peak_bytes':peak,
                     'java_wall_ms':round(java_ms,2) if java_ms is not None else ''}
                row['matched']=row['contract']==row['expected_contract'] and row['integrity']=='PASS'
                rows.append(row)
                if args.live:save_trace(events,args.out/'traces'/f'{lesson}_{variant}_{value}.jsonl')
                print(f"{lesson:12} {variant:6} input={value:5} integrity={row['integrity']} contract={row['contract']}")
    with (args.out/'scenarios.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    report={'mode':'live Java' if args.live else 'bundled replay','python':platform.python_version(),
            'platform':platform.platform(),'source_sha256':source_hash(),
            'scenario_count':len(rows),'matched_count':sum(r['matched'] for r in rows),
            'integrity_checks':sum(r['checkpoints'] for r in rows),'rows':rows,
            'limits':['自作4教材・各1誤実装。独立な未知実装への一般化は未評価。',
                      '再生時間は短い記録のコアのみ。GUI性能・教育効果を示さない。',
                      '反射スナップショットとイベントは同じ値変換器を共有する。完全独立な検証ではない。']}
    (args.out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(r['matched'] for r in rows):raise SystemExit(1)

if __name__=='__main__':main()
