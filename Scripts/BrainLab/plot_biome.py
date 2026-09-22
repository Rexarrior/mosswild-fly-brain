"""Standalone figures from saved Unreal traces; no synthetic observations."""
import json
import os
from pathlib import Path
from runtime import ROOT,LAB
os.environ.setdefault('MPLCONFIGDIR',str(LAB/'mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def save_svg(fig, path):
    fig.savefig(path)
    # Matplotlib emits spaces before path-data newlines; keep generated text clean.
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')

def main():
    before_path=LAB/'biome-play-before-latency-fix.json'
    after_path=LAB/'biome-play.json'
    if before_path.exists() and after_path.exists():
        before=json.loads(before_path.read_text());after=json.loads(after_path.read_text())
        if after.get('status')=='passed':
            fig,ax=plt.subplots(figsize=(11,4.5),layout='constrained')
            for data,style,condition in [(before,'--','Stale sensory pose'),(after,'-','Predicted sensory pose')]:
                for backend,color in [('siliconfly','#168b79'),('flybrain','#b47a34')]:
                    ax.plot([r['wall'] for r in data['samples']],
                            [sum(a['backend']==backend for a in r['agents']) for r in data['samples']],
                            linestyle=style,color=color,label=f'{backend} / {condition}')
            ax.set(title='Real asynchronous Unreal gameplay: two complete 600-second rendered runs',xlabel='Wall-clock seconds',ylabel='Living NPCs per colony',ylim=(-.2,6.5))
            ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False);ax.legend(fontsize=8)
            fig.savefig(ROOT/'Docs/BrainBiome-rendered.png',dpi=160);save_svg(fig,ROOT/'Docs/BrainBiome-rendered.svg');plt.close(fig)
    records=json.loads((ROOT/'Docs/BrainBiome-iterations.json').read_text())
    records=[r for r in records if r['metrics']['elapsed']>=599]
    fig,axs=plt.subplots(2,2,figsize=(13,8),layout='constrained')
    fig.suptitle('Mosswild: measured Unreal ecology / full Metal connectomes',fontsize=16)
    selected=[records[0],records[len(records)//2],records[-2],records[-1]]
    colors=['#7185a8','#b47a34','#ad5241','#168b79']
    for r,c in zip(selected,colors):
        path=LAB/'iterations'/r['name']/'trace.jsonl'
        if not path.exists():continue
        rows=[json.loads(l) for l in path.read_text().splitlines() if l]
        axs[0,0].plot([a['elapsed'] for a in rows],[a['alive'] for a in rows],color=c,label=r['name'])
    axs[0,0].set(xlabel='World seconds',ylabel='Living agents',ylim=(0,13),title='Population across the full run');axs[0,0].legend(fontsize=8)
    stages=[r['stage'] for r in records];m=[r['metrics'] for r in records]
    axs[0,1].bar(stages,[a['food_delivered'] for a in m],color='#168b79');axs[0,1].set(title='Food physically delivered to nests',xlabel='Iteration',ylabel='Food units')
    axs[1,0].plot(stages,[a['stuck_fraction']*100 for a in m],marker='o',color='#ad5241');axs[1,0].set(title='Blocked time during attempted travel',xlabel='Iteration',ylabel='% of active agent seconds',ylim=(0,None))
    axs[1,1].plot(stages,[a['observed_swarm_fraction']*100 for a in m],marker='o',color='#168b79',label='Whole run')
    axs[1,1].plot(stages,[a['late_swarm_fraction']*100 for a in m],marker='s',color='#b47a34',label='Second half only')
    axs[1,1].set(title='Observed groups: ≥3 movers / 850cm / alignment >0.65',xlabel='Iteration',ylabel='% of eligible moving samples',ylim=(0,100));axs[1,1].legend(fontsize=8)
    for ax in axs.flat:
        ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
    fig.savefig(ROOT/'Docs/BrainBiome-progress.png',dpi=160)
    save_svg(fig,ROOT/'Docs/BrainBiome-progress.svg')
    plt.close(fig)

    controls_path=ROOT/'Docs/BrainBiome-controls.json'
    if controls_path.exists():
        controls=json.loads(controls_path.read_text())
        seeds=sorted({r['config']['seed'] for r in controls})
        fig,axs=plt.subplots(1,2,figsize=(11,4.6),layout='constrained')
        fig.suptitle('Final controller: paired social-signal controls / last 300 world seconds',fontsize=13)
        for social,offset,color,label in [(True,-.18,'#168b79','Social signals ON'),(False,.18,'#b47a34','Social signals OFF')]:
            for panel in range(2):
                values=[]
                for seed in seeds:
                    r=next((r for r in controls if r['config']['seed']==seed and r['config']['swarm']==social),None)
                    if r is None:values.append(float('nan'));continue
                    m=r['metrics']
                    value=m['late_swarm_fraction'] if panel==0 else m['late_grouped_colony_seconds']/(2*(m['elapsed']-300))
                    values.append(value*100)
                bars=axs[panel].bar([i+offset for i in range(len(seeds))],values,width=.34,color=color,label=label)
                axs[panel].bar_label(bars,fmt='%.1f',padding=3,fontsize=8)
        for ax in axs:
            ax.set_xticks(range(len(seeds)),[str(s) for s in seeds])
            ax.set(xlabel='Ecology seed',ylim=(0,100));ax.grid(axis='y',alpha=.18)
            ax.spines[['top','right']].set_visible(False);ax.legend(fontsize=8)
        axs[0].set(title='Grouped movers, conditional on ≥3 moving',ylabel='% of eligible moving samples')
        axs[1].set(title='Any coherent group, including inactive time',ylabel='% of all late colony time')
        fig.savefig(ROOT/'Docs/BrainBiome-controls.png',dpi=160)
        save_svg(fig,ROOT/'Docs/BrainBiome-controls.svg');plt.close(fig)

    tracking=ROOT/'Docs/BrainMotor-tracking.json'
    if tracking.exists():
        results=json.loads(tracking.read_text())['results']
        fig,axs=plt.subplots(1,2,figsize=(13,5),layout='constrained')
        fig.suptitle('Closed-loop motor check: full brains, isolated body, no social rules',fontsize=14)
        for kind,tau,gain,color,label in [('calibrated',0,1,'#7185a8','Calibrated / no smoothing'),('trained',.35,1,'#ad5241','Learned / 0.35s smoothing'),('trained',.08,.75,'#168b79','Learned / 0.08s / gain 0.75')]:
            record=next(r for r in results if r['backend']=='siliconfly' and r['form']==2 and r['decoder']==kind and r['smoothing']==tau and r['turn_gain']==gain)
            path=LAB/'tracking-benchmark'/(record['name']+'.json')
            if path.exists():
                samples=json.loads(path.read_text())
                axs[0].plot([r['x']/100 for r in samples],[r['y']/100 for r in samples],color=color,lw=1,alpha=.8,label=label)
        axs[0].scatter([8,8,0,0],[0,8,8,0],marker='x',color='#263b39',s=60)
        axs[0].set_aspect('equal');axs[0].set(xlabel='Metres',ylabel='Metres',title='SiliconFly / fastest form / four waypoints');axs[0].legend(fontsize=8)
        cases=[('calibrated',0,1),('calibrated',.35,1),('trained',.35,1),('trained',.08,1),('trained',.08,.75)]
        for backend,offset,color in [('siliconfly',-.18,'#168b79'),('flybrain',.18,'#b47a34')]:
            values=[sum(r['completed_waypoints']==4 for r in results if r['backend']==backend and (r['decoder'],r['smoothing'],r['turn_gain'])==case) for case in cases]
            axs[1].bar([i+offset for i in range(5)],values,width=.34,color=color,label=backend)
        axs[1].set_xticks(range(5),['Calibrated\nno smoothing','Calibrated\n0.35s','Learned\n0.35s','Learned\n0.08s','Learned\n0.08s / gain .75'],fontsize=8)
        axs[1].set(ylim=(0,3.5),yticks=[0,1,2,3],ylabel='Forms completing all four waypoints',title='30 controlled trials / 120 body-second limit');axs[1].legend(fontsize=8)
        for ax in axs:ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
        fig.savefig(ROOT/'Docs/BrainMotor-tracking.png',dpi=160);save_svg(fig,ROOT/'Docs/BrainMotor-tracking.svg');plt.close(fig)

    latency_path=ROOT/'Docs/BrainMotor-latency.json'
    if latency_path.exists():
        results=json.loads(latency_path.read_text())['results']
        fig,axs=plt.subplots(1,2,figsize=(13,5),layout='constrained')
        fig.suptitle('Sensor latency: full brains / known delay imposed in the body loop',fontsize=14)
        for delay,predict,color,label in [(0.,False,'#7185a8','No delay'),(.4,False,'#ad5241','0.4s delay'),(.4,True,'#168b79','0.4s delay + pose forecast')]:
            r=next(r for r in results if r['backend']=='siliconfly' and r['form']==2 and r['delay']==delay and r['predict']==predict)
            points=json.loads((LAB/'latency-benchmark'/(r['name']+'.json')).read_text())
            axs[0].plot([p['x']/100 for p in points],[p['y']/100 for p in points],color=color,lw=1,label=label)
        axs[0].scatter([8,8,0,0],[0,8,8,0],marker='x',color='#263b39',s=60)
        axs[0].set_aspect('equal');axs[0].set(xlabel='Metres',ylabel='Metres',title='SiliconFly / fastest form / four waypoints');axs[0].legend(fontsize=8)
        cases=[(0.,False),(.2,False),(.2,True),(.4,False),(.4,True)]
        for backend,offset,color in [('siliconfly',-.18,'#168b79'),('flybrain',.18,'#b47a34')]:
            values=[sum(r['completed_waypoints']==4 for r in results if r['backend']==backend and (r['delay'],r['predict'])==case) for case in cases]
            axs[1].bar([i+offset for i in range(5)],values,width=.34,color=color,label=backend)
        axs[1].set_xticks(range(5),['No delay','0.2s delay','0.2s +\nforecast','0.4s delay','0.4s +\nforecast'],fontsize=8)
        axs[1].set(ylim=(0,3.5),yticks=[0,1,2,3],ylabel='Forms completing all four waypoints',title='30 trials / learned readout / 0.08s smoothing');axs[1].legend(fontsize=8)
        for ax in axs:ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
        fig.savefig(ROOT/'Docs/BrainMotor-latency.png',dpi=160);save_svg(fig,ROOT/'Docs/BrainMotor-latency.svg');plt.close(fig)
if __name__=='__main__':main()
