"""Build a source-checked simulation and viva guide from retained study artifacts."""
from pathlib import Path
import csv
import hashlib
import html
import json
import zipfile

import pymupdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'output/pdf/BTMS_Simulation_and_Viva_Guide.pdf'
QA = ROOT / 'report/simulation_guide'
W, H = A4
CW = W - 100
TEAL = colors.HexColor('#126D65')
INK = colors.HexColor('#20343B')
GRAY = colors.HexColor('#526168')
for name, filename in [('Guide','arial.ttf'), ('Guide-Bold','arialbd.ttf'), ('Guide-Italic','ariali.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(Path('C:/Windows/Fonts') / filename)))
pdfmetrics.registerFontFamily('Guide',normal='Guide',bold='Guide-Bold',italic='Guide-Italic',boldItalic='Guide-Bold')
S = {
    'title': ParagraphStyle('title', fontName='Guide-Bold', fontSize=23, leading=28, textColor=INK, spaceAfter=12),
    'subtitle': ParagraphStyle('subtitle', fontName='Guide', fontSize=11.5, leading=16, textColor=GRAY, spaceAfter=14),
    'h': ParagraphStyle('h', fontName='Guide-Bold', fontSize=12, leading=16, textColor=TEAL, spaceBefore=11, spaceAfter=6, keepWithNext=True),
    'body': ParagraphStyle('body', fontName='Guide', fontSize=10.1, leading=14.4, textColor=INK, spaceAfter=7),
    'small': ParagraphStyle('small', fontName='Guide', fontSize=8.5, leading=11.6, textColor=GRAY, spaceAfter=5),
    'cell': ParagraphStyle('cell', fontName='Guide', fontSize=9, leading=12.2, textColor=INK),
    'th': ParagraphStyle('th', fontName='Guide-Bold', fontSize=9, leading=12.2, textColor=colors.white),
    'bullet': ParagraphStyle('bullet', fontName='Guide', fontSize=10.1, leading=14.4, leftIndent=11, bulletIndent=0, spaceAfter=5, textColor=INK),
}

def p(text, style='body'):
    return Paragraph(text, S[style])

def heading(text):
    return p(text,'h')

def bullets(items):
    return [Paragraph(t,S['bullet'],bulletText='\u2022') for t in items]

def table(headers, rows, widths):
    t = Table([[p(html.escape(str(x)), 'th') for x in headers]] +
              [[p(str(x),'cell') for x in row] for row in rows], colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),TEAL), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#F0F5F4'),colors.white]),
        ('LINEBELOW',(0,0),(-1,0),.6,TEAL), ('LINEBELOW',(0,1),(-1,-1),.35,colors.HexColor('#D6DFDF')),
        ('LEFTPADDING',(0,0),(-1,-1),7), ('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),7), ('BOTTOMPADDING',(0,0),(-1,-1),7),
    ]))
    return t

def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor('#D6DFDF'))
    canvas.line(50, H-39, W-50, H-39)
    canvas.setFont('Guide-Bold',8)
    canvas.setFillColor(TEAL)
    canvas.drawString(50,H-29,'RL-BTMS / SIMULATION & VIVA GUIDE')
    canvas.setFont('Guide',8)
    canvas.setFillColor(GRAY)
    canvas.drawString(50,29,'Harshit Singh Parmar | Evidence reviewed 27 October 2026')
    canvas.drawRightString(W-50,29,f'{doc.page} / 8')

def read(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8-sig'))

def collect():
    with (ROOT/'report/results/controller_comparison.csv').open(newline='') as f:
        rows=list(csv.DictReader(f))
    runs=[]
    for mpath in sorted((ROOT/'outputs/study_20000').glob('*/*/metadata.json')):
        m=json.loads(mpath.read_text())
        models=list(mpath.parent.glob('checkpoints/*/model.zip'))
        final=mpath.parent/'checkpoints'/f"step_{m['completed_steps']}"/'model.zip'
        with zipfile.ZipFile(final) as z:
            saved=json.loads(z.read('data'))
        points={}
        for event in mpath.parent.glob('tensorboard/*/*tfevents*'):
            acc=EventAccumulator(str(event),size_guidance={'scalars':0}); acc.Reload()
            for v in acc.Scalars('eval/return'):
                points[v.step]=v.value
        counts={mode:len(json.loads((mpath.parent/f'evaluation_{mode}.json').read_text())) for mode in ['raw','shielded']}
        runs.append(dict(algo=m['algo'],seed=m['seed'],steps=m['completed_steps'],n_envs=m['n_envs'],
                         snapshots=len(models),episode_counter=saved.get('_episode_num'),curve_points=len(points),evaluations=counts))
    episodes=read('data/evaluation_episodes.json')
    learned=read('report/results/policy_evaluations.json')
    baseline_count=sum(len(read(f'report/results/{algo}_{mode}_evaluation.json'))
                       for algo in ['pid','mpc','null','bangbang'] for mode in ['raw','shielded'])
    reproduction=read('report/dashboard/reproduction.json')
    assert len(runs)==15 and len(episodes)==8 and len(learned)==240 and baseline_count==64
    assert sum(r['steps'] for r in runs)==302400 and sum(r['snapshots'] for r in runs)==30
    assert sum(r['curve_points'] for r in runs)==50
    assert all(r['n_envs']==8 and set(r['evaluations'].values())=={8} for r in runs)
    assert len(reproduction['runs'])==288 and reproduction['all_match']
    for algo in ['sac','td3']:
        assert [r['episode_counter'] for r in runs if r['algo']==algo]==[63]*5
    return rows,runs

def results_table(rows, supervised):
    selected=sorted([r for r in rows if (r['shield']=='True')==supervised], key=lambda r:float(r['cost_mean']))
    names={'mpc':'Sampling MPC','pid':'Tuned PID','null':'No cooling','bangbang':'Bang-bang','ppo':'PPO','sac':'SAC','td3':'TD3'}
    data=[[names[r['algo']]]+[f'{float(r[k]):,.2f}' for k in ['cost_mean','aux_wh_mean','violation_percent_mean','shield_firing_percent_mean']] for r in selected]
    t=table(['Controller','Mean cost','Aux. Wh','Violation %','Override %'],data,[120,104,85,92,CW-401])
    t.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    return t

def build():
    rows,runs=collect()
    pages=[]
    pages.append([
        p('Explain the project<br/>with evidence','title'),
        p('Battery thermal-management simulation, controller comparison and viva preparation','subtitle'),
        p('<b>Prepared for Harshit Singh Parmar</b><br/>Reinforcement Learning-Based Dynamic Battery Thermal Management for Software Defined Electric Vehicles'),
        heading('What problem does this project address?'),
        p('Driving and fast charging generate battery heat. Cooling must manage temperature limits and differences between modules while consuming as little auxiliary electricity as practical. This project compares learned and conventional cooling controllers under identical simulated conditions.'),
        heading('A 45-second opening explanation'),
        p('"Our project implements a coupled electrical and thermal battery simulator with four thermal regions and a finite coolant loop. Controllers independently command a pump, fan and chiller every five seconds. We trained PPO, SAC and TD3 across five seeds each, then compared them with PID, bang-bang, no cooling and sampling MPC on eight fixed cases, with and without a separate safety supervisor. The dashboard runs saved controllers through fresh Python simulations and exposes the resulting trajectories and evidence. At the current budget, RL did not outperform tuned PID; supervision accounts for the learned policies\' recorded safety."'),
        heading('What the project actually contains'),
        *bullets([
            '<b>Plant:</b> road-load demand, an electrical equivalent circuit, state of charge, four thermal nodes and serial coolant warming.',
            '<b>Control:</b> three continuous commands; 1-second physics updates and 5-second controller decisions.',
            '<b>Study:</b> 15 trained policies, retained checkpoints and logs, and 304 final evaluation outcomes.',
            '<b>Demonstration:</b> a local dashboard for fresh rollouts, comparisons, playback and JSON/CSV export.',
        ]),
        heading('The evidence boundary'),
        p('Retained EPA driving speed traces are source inputs. Battery temperatures, cooling energy and actions are calculated model outputs. The study does not demonstrate physical battery tests or automotive-ECU certification.'),
        p('Reading rule: comparison COST lower is better; training RETURN higher is better. Return is negative accumulated cost.','small'),
    ])
    pages.append([
        p('What the simulation shows','title'),
        p('A fresh calculation of the battery response under one selected episode and controller.','subtitle'),
        table(['Dashboard item','How to explain it'],[
            ['Four module temperatures','Four modeled thermal regions, not four physical temperature sensors. They show both peak temperature and uneven heating.'],
            ['Coolant temperature','The finite coolant inventory warms as it absorbs battery heat and cools through heat rejection.'],
            ['State of charge (SoC)','Remaining modeled battery charge, shown as a percentage.'],
            ['Pump / fan / chiller','Independent normalized actuator commands from 0% to 100%. These are commands, not measured hardware speeds.'],
            ['Policy request / applied command','What the controller asks for versus what is applied after possible safety supervision.'],
            ['Cooling energy / violations','Accumulated cooling electricity in Wh and seconds outside the 15-45 C band.'],
            ['Temperature chart','Four lines for the primary controller. The comparison line is the other controller\'s maximum module temperature.'],
            ['Recorded-result match','Whether the fresh calculation agrees with the corresponding saved metrics within the documented numeric tolerance.'],
        ],[147,CW-147]),
        heading('What happens after Run fresh simulation?'),
        p('Python loads the selected fixed episode and existing controller. For RL it loads the saved neural policy for the selected training seed. It calculates the rollout and compares it with the recorded result. It does not train a policy or rewrite the study table.'),
        heading('What does playback do?'),
        p('Playback animates the calculated trajectory at an accelerated rate. It does not create new measurements. JSON export contains the run evidence and comparisons; CSV export contains trajectory samples and actuator requests/applied commands.'),
        p('The local Python backend supports fresh simulation. A static evidence snapshot supports recorded results/replays only. Source: btms/dashboard/simulation.py and btms/dashboard/web/.','small'),
    ])
    pages.append([
        p('The seven controllers','title'),
        p('Three learned methods and four conventional or reference controllers.','subtitle'),
        table(['Controller','Meaning and behavior in this implementation'],[
            ['Sampling MPC','Model Predictive Control. Predicts future outcomes for sampled cooling commands and chooses the lowest-cost candidate. No RL training.'],
            ['Tuned PID','Proportional-Integral-Derivative feedback. Tuning selected a 39 C set-point, Kp=0.6 and Ki=Kd=0, so this chosen setting uses proportional feedback. Actuator routing considers ambient/coolant conditions.'],
            ['TD3','Twin Delayed Deep Deterministic Policy Gradient. Learns continuous commands using two value estimators, delayed policy updates and target-policy smoothing.'],
            ['SAC','Soft Actor-Critic. Learns continuous commands by balancing expected reward and policy entropy during training.'],
            ['PPO','Proximal Policy Optimization. Learns a policy using updates that limit abrupt changes, through clipping.'],
            ['No cooling','The null controller requests zero pump, fan and chiller command. Supervision can still force cooling if enabled.'],
            ['Bang-bang','Thermostat-style hysteresis: all cooling on at maximum module temperature >=39 C; stays on until maximum temperature <=35 C.'],
        ],[105,CW-105]),
        heading('Sampling MPC: exactly what it samples'),
        p('At each decision it tests 10 command combinations: zero cooling, full cooling, its previous command and seven randomly sampled combinations. Each candidate is held constant in a copied simulator for up to 12 decisions, or 60 simulated seconds. It selects the lowest predicted cost, applies that command for the next interval and repeats.'),
        p('This is a limited sampling comparator, not a certified global optimum. It uses the nominal simulator state and future demand, which gives it an information advantage over a policy observing the defined observation vector.'),
        heading('What the learned policies observe and output'),
        p('The 12-value observation includes four temperatures, SoC, C-rate, ambient temperature, charging flag, coolant temperature, current power demand and two future-demand summaries. The neural policy outputs three bounded actuator commands. Saved evaluations use deterministic policy predictions.'),
        p('Sources: btms/controllers/; btms/envs/btms_env.py; Stable-Baselines3 official PPO, SAC and TD3 documentation (links on page 8).','small'),
    ])
    pages.append([
        p('Safety and metric meanings','title'),
        heading('Supervisor enabled versus disabled'),
        p('<b>Enabled:</b> when the hottest module is >=42 C, a separate heuristic rule applies 100% pump, fan and chiller. Below the threshold, the controller\'s requested action is applied. <b>Disabled:</b> only the controller\'s own commands are applied. The safety band used for violation measurement is 15-45 C.'),
        p('"Supervised" here refers to safety intervention. It does not mean supervised machine learning or training from labeled examples.'),
        table(['Metric','Meaning','Better direction'],[
            ['MEAN COST','Average accumulated normalized objective: temperature-limit penalties, spatial temperature spread, cooling electricity and relative aging exposure. Not money or Wh.','Lower'],
            ['AUX. Wh','Average electrical energy consumed by the cooling equipment. Not total driving energy.','Lower, while safe'],
            ['VIOLATION %','Time with any module below 15 C or above 45 C, divided by episode duration, times 100.','Lower; ideally 0%'],
            ['OVERRIDE %','Time that the safety rule is active, divided by episode duration, times 100. It can activate even if the raw command already equals full cooling.','Generally lower, while safe'],
            ['SEEDS x EPISODES','How many training-seed variants and fixed episode cases contributed to that row.','Evidence count; no performance direction'],
        ],[98,288,CW-386]),
        heading('How the score is constructed'),
        p('Each 1-second update adds a weighted cost: 20 times the normalized squared temperature-band exceedance, plus normalized module spread, cooling power and relative aging exposure. Reward is the negative increment. Lower total cost therefore gives a higher, less negative return.'),
        heading('Interpret the numbers together'),
        *bullets([
            'Zero violations with supervision does not establish that the learned controller is independently safe.',
            'Zero override when supervision is disabled is automatic; it is not a safety achievement.',
            'Low energy caused by inadequate cooling is not good performance.',
            'A full-cooling rule cannot guarantee safety under every possible thermal load.',
        ]),
        p('Percentages are equal-episode-weight averages, not pooled time-weighted rates. For RL, episode means are averaged across the five training seeds. Source: btms/dashboard/evidence.py.','small'),
    ])
    pages.append([
        p('What the saved results say','title'),
        p('Original final-evaluation means, rounded to two decimals. Lower mean cost is better.','subtitle'),
        heading('Supervisor enabled'),results_table(rows,True),
        heading('Supervisor disabled'),results_table(rows,False),
        heading('The interpretation to present'),
        *bullets([
            '<b>Sampling MPC</b> has the lowest supervised mean cost, with substantially more computation and model/future-demand access.',
            '<b>Tuned PID</b> has the lowest unsupervised mean cost and zero recorded violations on these eight cases.',
            '<b>TD3</b> has the lowest supervised mean cost among the three learned methods.',
            'All three learned methods have higher supervised mean cost than tuned PID. Without supervision they violate the band for more than 41% of time on average.',
        ]),
        p('The supported conclusion is a comparative simulation study with measured supervisory dependence. These results do not demonstrate an RL advantage over tuned PID at the saved training budget.'),
        p('Source: report/results/controller_comparison.csv, checked against the individual retained evaluation records. Comparisons apply to the tested model, cases, tuning and training budget.','small'),
    ])
    pages.append([
        p('Runs, policies and episodes','title'),
        p('Training, checkpoint storage and final evaluation are different counts.','subtitle'),
        table(['Term','Meaning'],[
            ['Algorithm / run','The learning method / one execution of training with one algorithm and seed.'],
            ['Training seed / policy','A setting controlling training randomness / the learned controller produced by a run. Seeds are 0, 1, 2, 3 and 4 per RL algorithm.'],
            ['Episode / checkpoint','A complete driving or charging rollout / a saved model snapshot. A new snapshot is not an independent training run.'],
        ],[126,CW-126]),
        Spacer(1,10),
        table(['Method','Training runs / final policies','Steps per run','Results per mode','Both modes'],[
            ['PPO','5 / 5','20,480','5 x 8 = 40','80'],
            ['SAC','5 / 5','20,000','5 x 8 = 40','80'],
            ['TD3','5 / 5','20,000','5 x 8 = 40','80'],
            ['Tuned PID','0 / no learned policy','-','8','16'],
            ['Sampling MPC','0 / no learned policy','-','8','16'],
            ['Bang-bang','0 / no learned policy','-','8','16'],
            ['No cooling','0 / no learned policy','-','8','16'],
            ['TOTAL','15 / 15','302,400 total','152','304'],
        ],[91,127,94,99,CW-411]),
        heading('The important counting details'),
        *bullets([
            'PPO finished its rollout batch at 20,480 steps rather than the requested 20,000. Steps are environment transitions, not episodes or gradient updates.',
            'Each run used 8 parallel simulator environments. These workers do not produce 8 separate learned policies; recorded steps already count across the workers.',
            'There are 30 model.zip snapshots: 15 intermediate and 15 final. Resume pointers and exported formats do not create additional independent policies.',
            'A baseline\'s displayed 1 x 8 means one configuration on eight cases, not one RL training seed.',
        ]),
        heading('Completed training episodes: what can be verified'),
        p('SAC and TD3 final checkpoints each record an episode counter of 63 per run, or 315 per algorithm. PPO\'s stored counter is not usable for this count; its zero does not mean no episodes occurred. A verified completed-training-episode total across all three algorithms is therefore unavailable.'),
    ])
    pages.append([
        p('Test cases and evidence','title'),
        heading('Eight fixed evaluation cases'),
        table(['Conditions','Cases','Episode identifiers'],[
            ['Mild UDDS driving','2','mild_s701, mild_s702'],
            ['Hot US06 driving','2','hot_s701, hot_s702'],
            ['Fast charging','2','fastcharge_s701, fastcharge_s702'],
            ['Held-out NEDC driving','1','heldout_nedc'],
            ['HWFET driving','1','evaluation_hwfet'],
        ],[155,49,CW-204]),
        p('The paired cases differ in fixed initial temperature and SoC. Every policy sees the same manifest. Forty outcomes for one RL method in one mode means five policies tested on eight cases, not forty different scenarios. Episode seeds 701-704 are separate from training seeds 0-4.'),
        heading('Training curves and tuning'),
        p('The 15 curves contain 50 distinct recorded tuning-evaluation return points. A point summarizes evaluation on the separate tuning split; it is not one training episode. Connecting lines are a plotting aid, not extra observations. Higher return is better. NEDC is held out from training; UDDS, HWFET and US06 are training cycles.'),
        heading('What was verified previously'),
        table(['Record','What it establishes'],[
            ['15 Python tests passed','Recorded tests cover plant/normalizer behavior and dashboard/evidence boundaries. This guide creation did not retrain the models or rerun that test suite.'],
            ['288 matching reproduced outcomes','Fresh replay of all saved non-MPC final evaluations: 240 RL outcomes plus 48 PID/null/bang-bang outcomes. Numeric tolerance was used; duration, violation and supervisor seconds had to match exactly.'],
            ['MPC reproduction spot-check','One separate HWFET replay matched. The full 16-outcome MPC evaluation suite was not freshly rerun in that reproduction audit.'],
            ['302,400 recorded training steps','Saved run metadata, checkpoints and training scalar events support the experiment counts. Additional dashboard runs do not increase this training total.'],
        ],[147,CW-147]),
        heading('Limits to state openly'),
        p('Thermal/cooling parameters include engineering assumptions. Aging is a dimensionless relative exposure proxy, not measured capacity loss. Laptop inference timings do not certify an automotive ECU. Public evaluator-facing repository/data/demo links and the submission venue remain undecided.'),
        p('Repeated evaluations and reproduction runs are checks, not additional independent trained policies or new scenario samples.','small'),
    ])
    pages.append([
        p('Present it confidently','title'),
        heading('A practical five-minute demonstration'),
        *bullets([
            '<b>1. Explain the objective:</b> keep module temperatures within the study band while managing uneven heating and cooling electricity.',
            '<b>2. Select hot_s701 and tuned PID, supervisor disabled:</b> run it and explain temperature feedback, the 39 C set-point and the cost/violation metrics.',
            '<b>3. Compare SAC with PID, supervisor disabled:</b> show the freshly calculated difference on the same case; explain the saved study\'s raw-policy limitation.',
            '<b>4. Repeat with supervision enabled:</b> point out the 42 C trigger and distinguish requested commands from applied full cooling.',
            '<b>5. Open study results and training evidence:</b> explain 5 seeds x 8 cases, show a checkpoint/configuration and export a run JSON or trace CSV.',
        ]),
        heading('Likely viva questions: short answers'),
        p('<b>What is the contribution?</b> The implemented coupled simulation, comparison protocol, saved multi-seed experiments, safety-intervention analysis and inspectable demonstration. These use existing RL algorithms; do not claim a new RL algorithm. Describe your personal work separately from team work.'),
        p('<b>Why can PID beat RL?</b> PID was tuned for this objective and model. The recorded short-budget RL policies underperform it. Longer training or design changes need new experiments; improvement is not guaranteed.'),
        p('<b>Why is this still useful?</b> It establishes a reproducible comparison and exposes dependence on a safety supervisor. An honest negative result is a research finding; its value depends on the method and evidence.'),
        p('<b>What would you improve?</b> Run longer-training and reward/controller-design experiments, then repeat matched safety and robustness tests. Validate uncertain model parameters with independent data or hardware when available.'),
        heading('Where to point an evaluator'),
        p('Local project root: D:/Coding/RL BATTERY SYSTEM/. Paths below are evidence locations, not public-access links. Evaluator sharing still needs to be arranged.','small'),
        p('Simulation: btms/dashboard/simulation.py; btms/envs/btms_env.py<br/>Controllers: btms/controllers/; btms/envs/shield.py<br/>Results: report/results/controller_comparison.csv; policy_evaluations.json<br/>Cases: data/evaluation_episodes.json<br/>Runs/checkpoints/configs/events: outputs/study_20000/<br/>Tests/reproduction: report/dashboard/test_report.json; reproduction.json; mpc_spotcheck.json','small'),
        p('Official algorithm references: <link href="https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html" color="#126D65">PPO documentation</link>; <link href="https://stable-baselines3.readthedocs.io/en/master/modules/sac.html" color="#126D65">SAC documentation</link>; <link href="https://stable-baselines3.readthedocs.io/en/master/modules/td3.html" color="#126D65">TD3 documentation</link>. Project-specific behavior and numbers come from the local code and saved artifacts.','small'),
    ])
    story=[]
    for i,page in enumerate(pages):
        if i:story.append(PageBreak())
        story.extend(page)
    TARGET.parent.mkdir(parents=True,exist_ok=True); QA.mkdir(parents=True,exist_ok=True)
    SimpleDocTemplate(str(TARGET),pagesize=A4,leftMargin=50,rightMargin=50,topMargin=58,bottomMargin=49,
                      title='BTMS Simulation and Viva Guide',author='Harshit Singh Parmar',
                      subject='Controller meanings, verified experiment counts, results and presentation guide').build(story,onFirstPage=footer,onLaterPages=footer)
    pdf=pymupdf.open(TARGET)
    assert len(pdf)==8,f'Expected 8 pages, got {len(pdf)}'
    bounds=[]
    for i,page in enumerate(pdf):
        words=page.get_text('words')
        ok=all(w[0]>=48 and w[2]<=W-48 and w[1]>=16 and w[3]<=H-20 for w in words)
        assert ok,f'Out-of-bounds text on page {i+1}'
        page.get_pixmap(matrix=pymupdf.Matrix(1.3,1.3),alpha=False).save(QA/f'page-{i+1:02}.png')
        bounds.append({'page':i+1,'words':len(words),'within_bounds':ok})
    validation=dict(pdf=str(TARGET),pages=len(pdf),sha256=hashlib.sha256(TARGET.read_bytes()).hexdigest(),
                    training_runs=len(runs),final_policies=len(runs),steps=sum(r['steps'] for r in runs),
                    snapshots=sum(r['snapshots'] for r in runs),distinct_curve_points=sum(r['curve_points'] for r in runs),
                    final_evaluation_outcomes=304,source_counts_checked=True,page_checks=bounds,runs=runs)
    (QA/'validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in validation.items() if k!='runs'},indent=2))

if __name__=='__main__':
    build()
