"""Plot recorded long-run telemetry; also works on an in-progress run."""
import argparse
import json
import os
from runtime import LAB
os.environ.setdefault('MPLCONFIGDIR',str(LAB/'mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('name');args=p.parse_args()
    assert args.name and all(c.isalnum() or c in '-_' for c in args.name)
    folder=LAB/'economy'/args.name
    rows=[]
    for line in (folder/'trace.jsonl').read_text().splitlines():
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: break
    assert len(rows)>2
    t=[r['elapsed']/60 for r in rows]
    fig,axs=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    fig.suptitle('Mosswild: continuous nest economy / '+args.name)
    for c,backend,color in [(0,'siliconfly','#168b79'),(1,'flybrain','#b47a34')]:
        axs[0,0].plot(t,[sum(a['backend']==backend for a in r['agents']) for r in rows],color=color,label=backend)
        axs[0,1].plot(t,[r['colonies'][c]['store'] for r in rows],color=color,label=backend)
        axs[0,1].plot(t,[r['colonies'][c]['target'] for r in rows],color=color,ls=':',alpha=.5)
        xs=[];amounts=[]
        for end in range(300,int(rows[-1]['elapsed'])+1,300):
            a=min(rows,key=lambda r:abs(r['elapsed']-(end-300)))
            b=min(rows,key=lambda r:abs(r['elapsed']-end))
            xs.append(end/60-2.5+(c-.5)*1.7)
            amounts.append(b['colonies'][c]['delivered']-a['colonies'][c]['delivered'])
        axs[1,0].bar(xs,amounts,width=1.5,color=color,label=backend)
    axs[1,1].plot(t,[min(a['energy'] for a in r['agents']) if r['agents'] else 0 for r in rows],color='#ad5241',label='Lowest energy')
    axs[1,1].plot(t,[min(a['hydration'] for a in r['agents']) if r['agents'] else 0 for r in rows],color='#547da1',label='Lowest hydration')
    axs[1,1].axhline(25,color='#777',ls=':',lw=1)
    axs[0,0].set(title='Living population per colony',ylim=(0,7),ylabel='NPCs')
    axs[0,1].set(title='Nest reserves (dotted: target)',ylabel='Food units',ylim=(0,None))
    axs[1,0].set(title='Food delivered in each full five-minute window',ylabel='Food units',ylim=(0,None))
    axs[1,1].set(title='Needs of the most depleted individual',ylabel='Reserve units',ylim=(0,125))
    for ax in axs.flat:
        ax.set_xlabel('World minutes');ax.grid(alpha=.18);ax.legend(fontsize=8)
        ax.spines[['top','right']].set_visible(False)
    output=folder/'overview.png';fig.savefig(output,dpi=150);plt.close(fig)
    print(output)


if __name__=='__main__':main()
