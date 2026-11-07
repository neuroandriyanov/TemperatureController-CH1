"""Reproduce TC / current-loop / Pt100 summary figures; no instrument access."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
    'figure.facecolor': '#09121e', 'axes.facecolor': '#101e2c',
    'axes.edgecolor': '#344358', 'text.color': '#e9f0f6', 'axes.labelcolor': '#e9f0f6',
    'xtick.color': '#a2b3c4', 'ytick.color': '#a2b3c4', 'grid.color': '#344358',
    'legend.facecolor': '#101e2c', 'legend.edgecolor': '#344358', 'svg.fonttype': 'none'})


def load(folder, name):
    return json.loads((folder / name).read_text(encoding='utf-8'))


def save(fig, folder, name):
    target = folder / 'plots'
    target.mkdir(exist_ok=True)
    for suffix in ['png', 'svg']:
        fig.savefig(target / f'{name}.{suffix}', dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    tc = ROOT / '2026-11-06_thermocouple_input'
    points = load(tc, 'temperature_points.json')
    fig, ax = plt.subplots(figsize=(11, 6), layout='constrained')
    for typ in sorted({p['type'] for p in points}):
        rows = sorted((p for p in points if p['type'] == typ), key=lambda p: p['setpoint_C'])
        ax.plot([p['setpoint_C'] for p in rows], [p['deviation_C'] for p in rows], marker='o', label=typ)
    ax.axhline(0, color='#a2b3c4', ls='--', lw=1)
    ax.set(title='Термопары · 35 точек · внутренняя компенсация',
           xlabel='Задание калибратора, °C', ylabel='Среднее отклонение CH1, °C')
    ax.grid(alpha=.45);ax.legend(ncol=4)
    save(fig, tc, 'thermocouples')
    loop = ROOT / '2026-11-06_pt100_npt_loop'
    rows = load(loop, 'loop_calibration_validation.json')['points'][:5]
    fig, ax = plt.subplots(figsize=(10, 5), layout='constrained')
    ax.errorbar([p['source_ma'] for p in rows], [p['mean_error_ma'] for p in rows],
                yerr=[[p['mean_ma']-p['min_ma'] for p in rows], [p['max_ma']-p['mean_ma'] for p in rows]],
                color='#4ddbe7', marker='o', capsize=5, label='Среднее и min…max отсчётов')
    ax.axhline(0, color='#e9b567', ls='--')
    ax.set(title='Прямой вход 4–20 мА после калибровки', xlabel='Источник, мА', ylabel='CH1 − источник, мА')
    ax.grid(alpha=.45);ax.legend();save(fig, loop, 'current_loop')
    rows = load(loop, 'npt_chain_result.json')['points']
    fig, ax = plt.subplots(figsize=(11, 5), layout='constrained')
    positions = range(len(rows))
    ax.plot(positions, [p['mean_error_c'] for p in rows], 'o-', color='#4ddbe7', label='CH1, среднее')
    ax.plot(positions, [p['npt_ui']['temperature_c']-p['source_setpoint_c'] for p in rows], 's--', color='#e9b567', label='НПТ, экран')
    ax.set_xticks(list(positions), [str(p['source_setpoint_c']) for p in rows])
    ax.set(title='Pt100 → НПТ → CH1 · порядок реальной серии', xlabel='Задание Pt100, °C (последняя точка — повтор)', ylabel='Отклонение от задания, °C')
    ax.axhline(0,color='#a2b3c4',lw=1);ax.grid(alpha=.45);ax.legend();save(fig,loop,'pt100_chain')
    summary = {'tc_points': len(points), 'tc_samples': sum(p['n'] for p in points),
               'direct_current_max_abs_mean_error_ma': max(abs(p['mean_error_ma']) for p in load(loop,'loop_calibration_validation.json')['points'][:5]),
               'pt100_max_abs_mean_error_c': max(abs(p['mean_error_c']) for p in rows),
               'pt100_zero_repeat_change_c': rows[-1]['temperature_c']['mean']-rows[0]['temperature_c']['mean']}
    target=ROOT/'derived';target.mkdir(exist_ok=True)
    (target/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
