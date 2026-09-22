"""Render publication diagrams of the verified NPC control boundaries.

Saved/BrainLab/venv/bin/python Docs/Articles/render_control_diagrams.py
The layouts are explanatory diagrams, not measured data or executed policies.
"""
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/mosswild-diagrams-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent / 'assets'
COLORS = {'game':'#FAEDCD', 'adapter':'#DEEBF6', 'brain':'#D1EEE5', 'future':'#F0E1F5', 'neutral':'#EEF0F2'}
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':13, 'text.color':'#24353E', 'svg.fonttype':'none'})


class Diagram:
    def __init__(self, name, title, subtitle, height=9):
        self.name, self.height, self.nodes = name, height, {}
        self.fig, self.ax = plt.subplots(figsize=(12, height))
        self.fig.subplots_adjust(left=0.015, right=0.985, top=0.99, bottom=0.015)
        self.ax.set(xlim=(0,12), ylim=(0,height))
        self.ax.axis('off')
        self.ax.text(.25,height-.36,title,fontsize=20,weight='bold',va='top')
        self.ax.text(.25,height-.93,subtitle,fontsize=11,va='top',color='#5C6B75')
        for i,(kind,label) in enumerate([('game','Игровой код C++'),('adapter','Адаптер / декодер'),('brain','Нейронная модель')]):
            x=.25+i*3.85
            self.ax.add_patch(FancyBboxPatch((x,.22),.18,.18,boxstyle='round,pad=0.01',facecolor=COLORS[kind],edgecolor='#9CA8AA'))
            self.ax.text(x+.28,.31,label,fontsize=10,va='center')
    def box(self, key, x, y, label, kind='game', w=3.35, h=1.2):
        self.nodes[key]=(x,y,w,h)
        self.ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.06,rounding_size=0.10',
                         facecolor=COLORS[kind],edgecolor='#899CA5',linewidth=1.1,zorder=3))
        self.ax.text(x,y,label,ha='center',va='center',fontsize=13,linespacing=1.35,zorder=4)
    def edge(self,a,b,side_a='right',side_b='left',label='',rad=0):
        def port(k,side):
            x,y,w,h=self.nodes[k]
            return {'left':(x-w/2-.06,y),'right':(x+w/2+.06,y),'top':(x,y+h/2+.06),'bottom':(x,y-h/2-.06)}[side]
        p,q=port(a,side_a),port(b,side_b)
        self.ax.add_patch(FancyArrowPatch(p,q,arrowstyle='-|>',mutation_scale=15,color='#516873',linewidth=1.4,
                                          connectionstyle=f'arc3,rad={rad}',zorder=2))
        if label:
            self.ax.text((p[0]+q[0])/2+.08,(p[1]+q[1])/2+.12,label,fontsize=10,color='#52626C',ha='center',
                         bbox={'facecolor':'white','edgecolor':'none','pad':1},zorder=5)
    def note(self,y,text):
        self.ax.text(.25,y,text,fontsize=11,color='#52626C',va='center')
    def save(self):
        for ext in ('png','svg'):
            path = OUT/f'controls-{self.name}.{ext}'
            self.fig.savefig(path,dpi=150,facecolor='white')
            if ext == 'svg':
                path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')
        plt.close(self.fig)


def main():
    OUT.mkdir(exist_ok=True)
    d=Diagram('overview','Кто управляет жуком','Общая граница управления; детали соответствуют версии ночного запуска',10)
    d.box('world',2,7.8,'Потребности, ресурсы,\nпамять и соседи')
    d.box('goal',6,7.8,'Выбор цели, обход,\nсоциальные поправки')
    d.box('sense',10,7.8,'Кодирование запроса\nturn / drive / threat')
    d.box('brain',10,5.25,'Входные стимулы\n→ полный коннектом\n→ активность L / R / F','brain',h=1.55)
    d.box('decode',6,5.25,'Декодер: активность\n→ поворот и ход','adapter')
    d.box('body',2,5.25,'Сглаживание, скорость\nформы тела, коллизии')
    d.box('gate',6,3.8,'ForwardHz > 4',w=3.5,h=.6)
    d.box('contact',2.6,2.2,'Контакт и игровая задача\n+ разрешение по ForwardHz\n→ кормушка, вода, укус',w=4.45,h=1.55)
    d.box('rules',8.55,2.2,'C++ меняет энергию, воду,\nресурсы и здоровье;\nанимирует тело',w=5.25,h=1.55)
    d.edge('world','goal');d.edge('goal','sense');d.edge('sense','brain','bottom','top')
    d.edge('brain','decode','left','right');d.edge('decode','body','left','right')
    d.edge('body','contact','bottom','top');d.edge('contact','rules')
    d.edge('brain','gate','bottom','right');d.edge('gate','contact','left','top')
    d.note(1.1,'Обновлённое состояние мира используется при следующем выборе цели.')
    d.save()

    d=Diagram('readout','Что изменилось при обучении декодера','Обучали внешний переводчик активности; синаптические веса оставались прежними',8.9)
    d.box('request',2,6.55,'Заранее заданные\nturn / drive','adapter')
    d.box('brain',6,6.55,'Неизменная модель\n→ активность L / R / F','brain')
    d.box('fit',10,6.55,'Подбор коэффициентов\nвнешнего декодера','adapter')
    d.edge('request','brain');d.edge('brain','fit')
    d.edge('request','fit','top','top',label='те же команды — целевые ответы',rad=-.1)
    d.box('rates',2,3.75,'В игре: измеренные\nчастоты L / R / F','brain')
    d.box('readout',6,3.75,'Было: калибровка\nСтало: полином\nс обученными весами','adapter',h=1.5)
    d.box('out',10,3.75,'turn / drive\n→ сглаживание в C++\n→ движение',h=1.5)
    d.edge('rates','readout');d.edge('readout','out');d.edge('fit','readout','bottom','top')
    d.note(2.0,'Декодер видит только частоты. Координаты, цель и потребности ему не передаются.')
    d.note(1.25,'Сглаживание: 0,35 с в проблемном цикле → 0,08 с после исправления.')
    d.save()

    d=Diagram('prediction','Где исправили задержку','Прогноз меняет следующий сенсорный запрос; актора он не перемещает',8.6)
    d.box('old',2,6.1,'Текущая поза + ранее\nполученная команда')
    d.box('predict',6,6.1,'Прогноз позы с учётом\nсглаживания и коллизий')
    d.box('target',10,6.1,'Угол к выбранной цели\nиз прогнозируемой позы')
    d.edge('old','predict');d.edge('predict','target')
    d.box('real',2,3.45,'Настоящее тело исполняет\nпоследнюю команду\nв пределах её бюджета',h=1.5)
    d.box('decode',6,3.45,'Новый ответ\n→ декодер','adapter')
    d.box('brain',10,3.45,'Следующий запрос\n→ та же модель','brain')
    d.edge('target','brain','bottom','top');d.edge('brain','decode','left','right');d.edge('decode','real','left','right')
    d.note(1.7,'Прогноз используется в асинхронной игре. В синхронном аудите он отключён.')
    d.note(1.05,'Горизонт ограничен оставшимся временем команды и оценкой задержки ответа.')
    d.save()

    d=Diagram('economy','Кто организует снабжение','Поздняя экономика, добавленная после десяти циклов; нейронный мотор тот же',10)
    d.box('demand',2.15,7.7,'Запас + груз в пути\nниже целевого уровня?',w=3.75)
    d.box('workers',6.2,7.7,'Да → назначить\nдо 2–3 снабженцев')
    d.box('goal',10,7.7,'Назначение учитывается\nпри выборе цели',w=3.35)
    d.edge('demand','workers');d.edge('workers','goal')
    d.box('unload',2.15,5.0,'Груз у гнезда\n→ разгрузить\n→ снять назначение',w=3.75,h=1.5)
    d.box('food',6.2,5.0,'У еды: поесть самому,\nзатем набрать груз\nи выбрать возврат',h=1.5)
    d.box('motor',10,5.0,'Направление к цели\n→ модель → декодер\n→ движение','brain',h=1.5)
    d.edge('goal','motor','bottom','top');d.edge('motor','food','left','right');d.edge('food','unload','left','right')
    d.box('upkeep',3.15,2.2,'Постоянные расходы и порча\nснова уменьшают запас',w=5.3)
    d.box('brood',8.85,2.2,'Отдельная проверка C++:\nродитель + запас + лимит\n→ яйцо → новый NPC',w=5.3,h=1.5)
    d.edge('unload','upkeep','bottom','top')
    d.note(.85,'При достаточных запасах пустых снабженцев освобождают; при нехватке цикл повторяется.')
    d.save()

    d=Diagram('priorities','Почему вода могла оказаться важнее бегства','Упрощённый порядок PlanBiome в версии ночного запуска; все проверки делает C++',13.4)
    rows=[
      ('water',10.9,'Сработало условие жажды?','Ближайшая вода'),
      ('wound',9.0,'Режим отхода из-за ранения,\nпотребности не критические?','Восстановление у гнезда'),
      ('load',7.1,'Пора вернуть груз?\n(объём, источник, таймер)','Возврат в гнездо'),
      ('player',5.2,'Игрок на территории, близко,\nпотребности не критические?','Защита от игрока'),
      ('rival',3.3,'Подходящий соперник рядом,\nпотребности не критические?','Слаб / врагов больше → отход\nИначе → защита'),
    ]
    for key,y,q,a in rows:
        d.box(key,3.5,y,q,w=5.5,h=1.2)
        d.box(key+'a',9.3,y,a,w=4.3,h=1.2)
        d.edge(key,key+'a',label='да')
    for (a,*_),(b,*__) in zip(rows,rows[1:]):
        d.edge(a,b,'bottom','top',label='нет')
    d.box('fallback',6,1.15,'Иначе: тревога → прежняя кормовая цель → голод / снабжение → отдых или разведка',w=11.3,h=.65)
    d.edge('rival','fallback','bottom','top',label='нет')
    d.save()

    d=Diagram('social','Откуда берётся совместное движение','Социальные правила меняют цель и входные сигналы; отдельный «роевой мозг» не добавлялся',10.3)
    d.box('knowledge',2,7.85,'Общая память о еде,\nследы и тревога')
    d.box('goal',6,7.85,'Оценка кормовых целей,\nследование лидеру')
    d.box('guide',10,7.85,'Промежуточная точка\nпо следу и обходу')
    d.edge('knowledge','goal');d.edge('goal','guide')
    d.box('brain',2,5.0,'Тот же коннектом\n→ тот же декодер','brain')
    d.box('senses',6,5.0,'Кодирование turn / drive;\nсогласование темпа')
    d.box('neighbors',10,5.0,'Отталкивание,\nвыравнивание направления,\nсближение с соседями',h=1.6)
    d.edge('guide','neighbors','bottom','top');d.edge('neighbors','senses','left','right');d.edge('senses','brain','left','right')
    d.box('body',2.8,2.3,'Движение отдельных тел\nс игровой физикой',w=4.5)
    d.box('measure',8.55,2.3,'По траекториям считаем\nгруппирование и добычу.\nЭто оценка, не награда модели',w=5.3,h=1.5)
    d.edge('brain','body','bottom','top');d.edge('body','measure')
    d.save()

    d=Diagram('baseline','Как устроить следующее сравнение','План эксперимента — обычный контроллер в этих прогонах ещё не проверялся',8.8)
    d.box('shared',6,6.35,'Одинаковые потребности, карта, экономика,\nвыбор цели и подготовка направления',w=9.5,h=1.3)
    d.box('neural',3,3.8,'Вариант A:\nнейронная модель\n+ декодер','brain',w=4.5,h=1.6)
    d.box('classic',9,3.8,'Вариант B, ещё не сделан:\nобычный моторный\nконтроллер','future',w=4.5,h=1.6)
    d.edge('shared','neural','bottom','top');d.edge('shared','classic','bottom','top')
    d.box('eval',6,1.55,'Одинаковое тело и правила → сравнить траектории,\nдобычу, потери и вычислительные затраты',w=10.5,h=1.1)
    d.edge('neural','eval','bottom','top');d.edge('classic','eval','bottom','top')
    d.save()
    print('Rendered 7 diagrams as PNG and SVG')


def render_sensory():
    d=Diagram('sensory','Управление через раздражители','Новый режим: ресурс и маршрут до запуска модели не выбираются',12.7)
    d.box('world',3,10.35,'Все источники еды и воды,\nгнездо, тела и препятствия',w=5.1)
    d.box('needs',9,10.35,'Голод, жажда, груз, травмы\nи дефицит запасов гнезда',w=5.1)
    d.box('encode',6,8.25,'C++ суммирует вклады источников и задаёт силу раздражителей:\nеда ±, вода ±, гнездо ±, возбуждение, угроза',w=11,h=1.3)
    d.edge('world','encode','bottom','top');d.edge('needs','encode','bottom','top')
    d.box('input',3,6.1,'Адаптер: восемь каналов\n→ стимуляция отдельных\nвходных групп','adapter',w=5.1,h=1.45)
    d.box('brain',9,6.1,'Полный коннектом\n→ активность выходов\nL / R / F','brain',w=4.7,h=1.45)
    d.edge('encode','input','bottom','top');d.edge('input','brain')
    d.box('body',3,3.9,'C++: сглаживание,\nдвижение тела и коллизии',w=5.1)
    d.box('decode',9,3.9,'Прежний декодер\n→ поворот и ход','adapter',w=4.7)
    d.edge('brain','decode','bottom','top');d.edge('decode','body','left','right')
    d.box('ecology',6,1.9,'C++: питание и укусы при контакте и достаточной активности;\nразгрузка и потомство — по правилам экономики',w=10.7,h=1.3)
    d.edge('body','ecology','bottom','top')
    d.edge('brain','ecology','right','right',rad=-.15)
    d.ax.text(11.88,4,'ForwardHz > 4',rotation=90,ha='center',va='center',fontsize=10,color='#52626C')
    d.note(.85,'Назначение снабженцев, построение маршрутов и внешние роевые поправки отключены.')
    d.save()
    print('Rendered sensory control diagram as PNG and SVG')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sensory-only',action='store_true')
    args=parser.parse_args()
    if not args.sensory_only:main()
    render_sensory()
