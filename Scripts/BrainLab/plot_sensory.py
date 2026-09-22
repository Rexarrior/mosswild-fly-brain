"""Export measured ecology and paths; reads recorded runs, never reruns the model."""
import argparse
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from runtime import LAB

def read_rows(folder):
    rows=[json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
    final=json.loads((folder/'complete.json').read_text())
    if final['elapsed']>rows[-1]['elapsed']:rows.append(final)
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='sensory-visible-v1');args=p.parse_args()
    results=json.loads((LAB/'sensory'/f'{args.prefix}-results.json').read_text())
    assert results, 'No completed runs to plot'
    fig,axes=plt.subplots(3,2,figsize=(12,10),layout='constrained')
    colors={'sensory-populations-v1':'#166c9b','planner':'#b85f26'}
    seeds=list(dict.fromkeys(run['config']['seed'] for run in results))
    styles=['-','--','-.',':']
    for n,run in enumerate(results):
        cfg=run['config'];folder=LAB/'iterations'/cfg['name']
        rows=read_rows(folder)
        mode=rows[-1]['controller'];label=f'{"Sensory" if cfg["sensory_competition"] else "Planner"} / {cfg["seed"]}'
        x=[r['elapsed']/60 for r in rows];style=styles[seeds.index(cfg['seed'])%len(styles)]
        values=[[r['alive'] for r in rows],[r['food_delivered'] for r in rows],
                [min((a['energy'] for a in r['agents']),default=float('nan')) for r in rows],
                [min((a['hydration'] for a in r['agents']),default=float('nan')) for r in rows],
                [min(c['store']/max(c['target'],1) for c in r['colonies']) for r in rows],
                [r['fights'] for r in rows]]
        for ax,y in zip(axes.flat,values):ax.plot(x,y,color=colors[mode],linestyle=style,label=label,lw=1.5)
    for ax,title in zip(axes.flat,('Living adults (initial 6, cap 12)','Delivered food (cumulative)',
                                  'Lowest energy among living agents','Lowest hydration among living agents',
                                  'Lower colony reserve / current target','Contact strikes (cumulative)')):
        ax.set_title(title,loc='left',fontsize=11);ax.set_xlabel('Biome minutes');ax.grid(alpha=.2)
    axes[0,0].set_ylim(0,13);axes[0,0].legend(fontsize=8,ncol=2)
    for ax in axes[1]:ax.axhline(25,color='#aa3643',ls=':',lw=1)
    axes[2,0].axhline(1,color='#555555',ls=':',lw=1)
    fig.suptitle('Mosswild: simultaneous sensory populations versus goal planner\nSame contact economy; flocking/recruitment off; frozen motor readout',fontsize=14)
    target=LAB/'sensory'/f'{args.prefix}-comparison.png';fig.savefig(target,dpi=180);plt.close(fig)
    columns=min(2,len(results));row_count=(len(results)+columns-1)//columns
    fig,axes=plt.subplots(row_count,columns,figsize=(6*columns,5.4*row_count),layout='constrained',squeeze=False)
    display_runs=sorted(results,key=lambda r:(r['config']['seed'],not r['config']['sensory_competition']))
    for ax,run in zip(axes.flat,display_runs):
        cfg=run['config'];folder=LAB/'iterations'/cfg['name'];rows=read_rows(folder)
        geometry=json.loads((folder/'source/Config/BrainBiome.json').read_text())
        tracks={}
        for r in rows:
            for a in r['agents']:tracks.setdefault((a['backend'],a['id']),[]).append((a['x']/100,a['y']/100))
        for (b,_),points in tracks.items():
            ax.plot(*zip(*points),color='#169c9b' if b=='siliconfly' else '#d48522',lw=.6,alpha=.6)
        for q in geometry['points']:
            ax.scatter(q['x']/100,q['y']/100,c='#2d6aab' if q['kind']==1 else '#549849',marker='s',s=24,zorder=4)
        for h in geometry['homes']:
            ax.scatter(h[0]/100,h[1]/100,c='#333333',edgecolors='white',linewidths=.6,marker='*',s=160,zorder=5)
        for obstacle in geometry['obstacles']:
            ax.add_patch(plt.Circle((obstacle['x']/100,obstacle['y']/100),obstacle['radius']/100,
                                   facecolor='#dddddd',edgecolor='#aaaaaa',lw=.5,zorder=0))
        width=geometry['half_width']/100;height=geometry['half_height']/100
        ax.set(xlim=(-width,width),ylim=(-height,height),aspect='equal',xlabel='X, metres',ylabel='Y, metres',
               title=f'{"Sensory" if cfg["sensory_competition"] else "Planner"} / {cfg["seed"]}')
        ax.grid(alpha=.15)
    for ax in list(axes.flat)[len(results):]:ax.set_visible(False)
    fig.suptitle('Observed paths: cyan SiliconFly / amber FlyBrainEngine\nSquares: food or water; stars: nests; circles: obstacles')
    fig.savefig(LAB/'sensory'/f'{args.prefix}-paths.png',dpi=160)
    print(target)

if __name__=='__main__':main()
