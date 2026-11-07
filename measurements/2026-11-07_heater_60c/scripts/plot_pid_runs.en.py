# English derivative: original data/calculations retained; outputs use plots/en and derived/en.
"""Offline analysis of completed live bench recordings; never controls hardware."""
import json
import math
import os
from pathlib import Path
import statistics
import sys

RUN = Path(__file__).resolve().parents[1]
ROOT = RUN.parents[1]
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 10,
    'figure.facecolor': '#0c121b', 'axes.facecolor': '#141e2b',
    'axes.edgecolor': '#344358', 'axes.labelcolor': '#e5edf7',
    'text.color': '#e5edf7', 'xtick.color': '#9eb0c7',
    'ytick.color': '#9eb0c7', 'grid.color': '#344358',
    'legend.facecolor': '#141e2b', 'legend.edgecolor': '#344358',
    'savefig.facecolor': '#0c121b', 'svg.fonttype': 'none',
})


def stats(values):
    values = [float(x) for x in values if x is not None and math.isfinite(x)]
    return dict(n=len(values), minimum=min(values), maximum=max(values),
                mean=statistics.mean(values), std=statistics.pstdev(values)) if values else None


def analyze(path):
    d = json.loads(path.read_text(encoding='utf-8'))
    s = [r for r in d['samples'] if r.get('elapsed') is not None and r['mode'] == 1]
    if not s:
        return None
    target = d.get('target_elapsed')
    hold = [r for r in s if target is not None and r['elapsed'] >= target]
    first300 = [r for r in hold if r['elapsed'] <= target + 300]
    last300 = [r for r in s if r['elapsed'] >= s[-1]['elapsed'] - 300]
    last60 = [r for r in s if r['elapsed'] >= s[-1]['elapsed'] - 60]
    cfg = d['start_config']
    result = dict(name=path.stem, start=next(e for e in d['events'] if e['event']=='AUTO_detected'),
                  parameters=dict(kp=cfg[8]/1000, ki=cfg[9]/1000, kd=cfg[10]/100,
                                  period_s=(cfg[13]+(cfg[46]<<16))/1000,
                                  cj_source=cfg[2], setpoint=cfg[0]/10),
                  duration_s=s[-1]['elapsed'], target_elapsed_s=target,
                  hold_duration_s=s[-1]['elapsed']-target if target is not None else 0,
                  five_minutes_completed=bool(d.get('hold_completed')),
                  all_temperature=stats(r['temperature'] for r in s),
                  first300_temperature=stats(r['temperature'] for r in first300),
                  last300_temperature=stats(r['temperature'] for r in last300),
                  last60_temperature=stats(r['temperature'] for r in last60),
                  last300_output=stats(r['output'] for r in last300),
                  first300_output=stats(r['output'] for r in first300),
                  fault_samples=sum(bool(r['active'] or r['latched']) for r in s),
                  stop_telemetry=d.get('stop_telemetry'), events=d['events'])
    fig, axs = plt.subplots(3, 1, figsize=(12, 9), sharex=True, layout='constrained',
                            gridspec_kw={'height_ratios': [2, 1, 1]})
    x = [r['elapsed']/60 for r in s]
    axs[0].plot(x, [r['temperature'] for r in s], color='#55d9c6', lw=2, label='Type-K thermocouple')
    axs[0].axhline(60, color='#e9b567', ls='--', label='Setpoint 60 °C')
    axs[0].axhspan(50, 70, color='#e9b567', alpha=.055, label='Relay tolerance ±10 °C')
    axs[0].set_ylabel('Temperature, °C')
    axs[0].set_title(f"CH1 · {path.stem}\nKp={cfg[8]/1000:g} · Ki={cfg[9]/1000:g} · Kd={cfg[10]/100:g} · period 2 s", loc='left', pad=14)
    axs[1].plot(x, [r['output'] for r in s], color='#e9b567', lw=1.5, label='PID command')
    axs[1].set_ylabel('Command, %')
    axs[1].set_ylim(-3, 103)
    case_stats = {}
    thermal = [t for t in d['thermal'] if t.get('elapsed') is not None]
    for marker_id, name, color in [(1, 'Корпус A', '#55d9c6'), (2, 'Корпус B', '#baaff0')]:
        tx, ty = [], []
        for t in thermal:
            m = next((m for m in t['state']['markers'] if m['id'] == marker_id), None)
            # NaN explicitly preserves unavailable palette estimates as gaps.
            v = m.get('temperature') if m else None
            tx.append(t['elapsed']/60)
            ty.append(float('nan') if v is None else v)
        axs[2].plot(tx, ty, color=color, lw=1.3, label={'Корпус A': 'Enclosure A', 'Корпус B': 'Enclosure B'}[name]+' ≈')
        case_stats[name] = dict(statistics=stats(ty), unavailable=sum(not math.isfinite(v) for v in ty))
    result['case_surface_palette_estimates'] = case_stats
    axs[2].set_ylabel('Enclosure ≈ °C')
    axs[2].set_xlabel('Time since AUTO, min')
    for ax in axs:
        ax.grid(alpha=.4)
        ax.legend(loc='upper left', fontsize=9)
        if target is not None:
            ax.axvline(target/60, color='#93a4bc', ls=':', lw=1)
            if d.get('hold_completed'):
                ax.axvspan(target/60, (target+300)/60, color='#55d9c6', alpha=.05)
    (RUN/'plots'/'en').mkdir(parents=True, exist_ok=True)
    for ext in ('png', 'svg'):
        fig.savefig(RUN/'plots'/'en'/f'{path.stem}.{ext}', dpi=160)
    plt.close(fig)
    if hold:
        fig, axes = plt.subplots(2,1,figsize=(12,6),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[2,1]})
        hx=[(r['elapsed']-target)/60 for r in hold]
        axes[0].plot(hx,[r['temperature'] for r in hold],color='#55d9c6',lw=1.6,label='Type-K thermocouple reading')
        axes[0].axhline(60,color='#e9b567',ls='--',label='Setpoint 60 °C')
        axes[0].set_ylabel('Temperature, °C')
        axes[0].set_title('Holding after reaching the setpoint · '+path.stem,loc='left',pad=12)
        axes[1].plot(hx,[r['output'] for r in hold],color='#e9b567',lw=1.3,label='PID command')
        axes[1].set_ylabel('Command, %');axes[1].set_xlabel('Time since first entry into 59.8…60.2 °C, min')
        for ax in axes:
            ax.grid(alpha=.4);ax.legend(loc='upper right',fontsize=9)
            if hx[-1]>=5:ax.axvline(5,color='#93a4bc',ls=':',lw=1)
        for ext in ('png','svg'):fig.savefig(RUN/'plots'/'en'/f'{path.stem}_hold.{ext}',dpi=160)
        plt.close(fig)
    return result


if __name__ == '__main__':
    results = [r for p in sorted((RUN/'raw').glob('pid60_hold5_??.json')) if (r := analyze(p))]
    (RUN/'derived'/'en').mkdir(parents=True, exist_ok=True)
    (RUN/'derived/en/pid_analysis.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    for r in results:
        print(json.dumps({k:v for k,v in r.items() if k not in ('stop_telemetry', 'events')}, ensure_ascii=False))
