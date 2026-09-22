"""Extract final control results once, then render article figures from compact JSON.

--extract reads the completed comparison summary. Default rendering needs no Saved files.
"""
import argparse
import json
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/mosswild-controller-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from render_control_diagrams import Diagram

ARTICLE=Path(__file__).resolve().parent
ASSETS=ARTICLE/'assets'
DATA=ASSETS/'controller-control-data.json'
COLORS={'connectome':'#7549A4','reactive-v1':'#287A5C'}
LABELS={'connectome':'Коннектомы + декодеры','reactive-v1':'Простой контроллер'}

def control_diagram():
    d=Diagram('motor-control','Проверка с заменой моторного блока','Одинаковые раздражители, тела, контактные правила и шаг времени',10.5)
    d.box('world',6,8.0,'C++: геометрия мира и потребности\n→ те же восемь каналов раздражителей',w=10.6,h=1.2)
    d.box('brain',3,5.7,'Полный коннектом\n+ прежний декодер','brain',w=5.1,h=1.4)
    d.box('reflex',9,5.7,'Сумма левых/правых сигналов\n+ формула скорости\nбез карты, памяти и целей','adapter',w=5.1,h=1.4)
    d.edge('world','brain','bottom','top');d.edge('world','reflex','bottom','top')
    d.box('body',6,3.4,'C++: те же поворот, ход, сглаживание и коллизии\nОдин ответ → 0,4 с мира, шаг физики 0,05 с',w=10.6,h=1.2)
    d.edge('brain','body','bottom','top');d.edge('reflex','body','bottom','top')
    d.box('economy',6,1.65,'Контактная экология и размножение остаются в C++\nПорог нейронной частоты убран в ОБОИХ вариантах',w=10.6,h=1.1)
    d.edge('body','economy','bottom','top')
    d.note(.80,'Один и тот же мир запускается заново для каждого варианта и seed.')
    d.save()


def render(data):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'text.color':'#24353E'})
    seeds=sorted({r['seed'] for r in data['runs']})
    fig,axes=plt.subplots(1,2,figsize=(13.2,6.5))
    fig.subplots_adjust(left=.085,right=.97,bottom=.24,top=.73,wspace=.32)
    fig.text(.085,.94,'Нужен ли полный коннектом для снабжения колонии?',fontsize=20,weight='bold')
    fig.text(.085,.885,'Четыре seed · два контроллера · по 30 игровых минут · обе колонии вместе',fontsize=11)
    x=np.arange(len(seeds));width=.34
    for i,mode in enumerate(COLORS):
        runs=[next(r for r in data['runs'] if r['seed']==seed and r['mode']==mode) for seed in seeds]
        for ax,key in zip(axes,('food_delivered','batch_median_ms')):
            bars=ax.bar(x+(i-.5)*width,[r[key] for r in runs],width,color=COLORS[mode],label=LABELS[mode])
            ax.bar_label(bars,fmt='%.0f' if key=='food_delivered' else '%.3g',padding=4,fontsize=10)
    axes[0].set_title('Доставлено еды',loc='left',fontweight='bold',pad=14)
    axes[0].set_ylabel('Игровых единиц')
    axes[0].set_ylim(0,max(r['food_delivered'] for r in data['runs'])*1.17)
    axes[1].set_title('Медианное время моторного пакета',loc='left',fontweight='bold',pad=14)
    axes[1].set_ylabel('Миллисекунды, логарифмическая шкала')
    axes[1].set_yscale('log')
    vals=[r['batch_median_ms'] for r in data['runs']]
    axes[1].set_ylim(min(vals)/3,max(vals)*4)
    for ax in axes:
        ax.set_xticks(x,[str(s) for s in seeds]);ax.set_xlabel('Seed',labelpad=10)
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper left',bbox_to_anchor=(.079,.855),frameon=False,ncol=2)
    fig.text(.085,.10,'Доставка ограничена также расходами и целевым запасом гнёзд; это не универсальная оценка качества AI.',fontsize=10,color='#52626C')
    fig.text(.085,.06,'Время пакета — измерение сервиса без HTTP и рендера. Более быстрый расчёт не ускоряет шаг мира.',fontsize=10,color='#52626C')
    fig.savefig(ASSETS/'mosswild-controller-control.png',dpi=180,facecolor='white');plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('--extract',action='store_true');p.add_argument('--diagram-only',action='store_true');args=p.parse_args()
    if args.diagram_only:control_diagram();return
    if args.extract:
        raw=json.loads((ARTICLE.parents[1]/'Saved/BrainLab/controller-control/motor-control-v1/summary.json').read_text())
        data={'protocol':raw['protocol'],'sources_sha256':raw['sources_sha256'],'paired':raw['paired'],
              'runs':[{k:v for k,v in r.items() if k not in ('source_manifest','series')} for r in raw['runs']]}
        DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    data=json.loads(DATA.read_text());render(data);control_diagram()

if __name__=='__main__':main()
