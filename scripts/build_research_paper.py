"""Reflow the verified research-paper text into a consistent IEEE-style PDF."""
from __future__ import annotations

import html
import re
import csv
import json
import hashlib
import statistics
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pymupdf
from PIL import Image as PILImage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.mathtext import math_to_image
from matplotlib.font_manager import FontProperties
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle, Flowable,
)

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "deliverables/IEEE_BTMS_Manuscript.json"
TARGET = ROOT / "output/pdf/IEEE_BTMS_Research_Paper_Formatted.pdf"
TEMP = ROOT / "tmp/pdfs/paper-build"
TEMP.mkdir(parents=True, exist_ok=True)
RESULTS = ROOT / "report/results"
sys.path.insert(0, str(ROOT))

FONT_DIR = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("TimesNew", str(FONT_DIR / "times.ttf")))
pdfmetrics.registerFont(TTFont("TimesNew-Bold", str(FONT_DIR / "timesbd.ttf")))
pdfmetrics.registerFont(TTFont("TimesNew-Italic", str(FONT_DIR / "timesi.ttf")))
pdfmetrics.registerFontFamily("TimesNew", normal="TimesNew", bold="TimesNew-Bold", italic="TimesNew-Italic", boldItalic="TimesNew-Bold")

PAGE_W, PAGE_H = 612, 792
MARGIN_X, GAP, BOTTOM, TOP = 50, 18, 51, 45
COL_W = (PAGE_W - 2 * MARGIN_X - GAP) / 2
styles = {
    "body": ParagraphStyle("body", fontName="TimesNew", fontSize=9.0, leading=10.25,
                           alignment=TA_JUSTIFY, firstLineIndent=9, spaceAfter=3.4,
                           splitLongWords=False, allowWidows=0, allowOrphans=0),
    "abstract": ParagraphStyle("abstract", fontName="TimesNew", fontSize=8.8, leading=10.0,
                               alignment=TA_JUSTIFY, spaceAfter=5),
    "section": ParagraphStyle("section", fontName="TimesNew-Bold", fontSize=10, leading=11.5,
                              alignment=TA_CENTER, spaceBefore=7, spaceAfter=3, keepWithNext=True),
    "sub": ParagraphStyle("sub", fontName="TimesNew-Bold", fontSize=9.2, leading=10.8,
                          spaceBefore=5.5, spaceAfter=2, keepWithNext=True),
    "caption": ParagraphStyle("caption", fontName="TimesNew", fontSize=8, leading=9.1,
                              spaceBefore=3, spaceAfter=5, keepWithNext=True),
    "tablecap": ParagraphStyle("tablecap", fontName="TimesNew-Bold", fontSize=7.8,
                               leading=8.8, spaceBefore=4, spaceAfter=2, keepWithNext=True),
    "ref": ParagraphStyle("ref", fontName="TimesNew", fontSize=7.7, leading=8.7,
                          leftIndent=12, firstLineIndent=-12, spaceAfter=2.3),
    "eqno": ParagraphStyle("eqno", fontName="TimesNew", fontSize=8.3,
                           leading=9, alignment=TA_CENTER),
}




def para(s: str, kind="body"):
    return Paragraph(html.escape(clean(s)), styles[kind])

def table_flow(num: str):
    caption, *rows = TABLES[num]
    cap = para(f"TABLE {num}. {caption}", "tablecap")
    coln = len(rows[0])
    widths = ([COL_W * .47, COL_W * .53] if coln == 2 else
              [COL_W * .43, COL_W * .18, COL_W * .39] if coln == 3 else
              [COL_W * .37, COL_W * .21, COL_W * .21, COL_W * .21])
    if num == "XI": widths = [COL_W * .37, COL_W * .63]
    if num == "VIII": widths = [COL_W * .46, COL_W * .27, COL_W * .27]
    if num == "IX": widths = [COL_W * .30, COL_W * .25, COL_W * .24, COL_W * .21]
    data = [[para(str(cell), "ref") for cell in row] for row in rows]
    tab = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1)
    tab.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ("LINEABOVE", (0, 0), (-1, 0), .55, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), .35, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), .55, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return KeepTogether([cap, tab, Spacer(1, 5)])



# Figures are generated from recorded data by build().


def first_page(canvas, doc):
    canvas.saveState()
    title = "A Reproducible Simulation Benchmark of Reinforcement Learning and Classical Control for Electric Vehicle Battery Thermal Management"
    title_style = ParagraphStyle("title", fontName="TimesNew-Bold", fontSize=17,
                                 leading=19.5, alignment=TA_CENTER)
    author_style = ParagraphStyle("authors", fontName="TimesNew", fontSize=10,
                                  leading=12.2, alignment=TA_CENTER)
    title_p = Paragraph(html.escape(title), title_style)
    _, h = title_p.wrap(PAGE_W - 120, 110)
    title_p.drawOn(canvas, 60, PAGE_H - 45 - h)
    author = Paragraph("Rishuraj Singh, Nihaal Sansanwal, Harshit Singh Parmar, and Chaitanya Sharma", author_style)
    _, ah = author.wrap(500, 30)
    author.drawOn(canvas, 56, PAGE_H - 45 - h - 17 - ah)
    aff = Paragraph("<i>IILM University, Greater Noida, India</i>", author_style)
    _, fh = aff.wrap(500, 30)
    aff.drawOn(canvas, 56, PAGE_H - 45 - h - 17 - ah - 3 - fh)
    canvas.restoreState()

class Paper(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=(PAGE_W, PAGE_H),
                         leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                         topMargin=TOP, bottomMargin=BOTTOM,
                         title="A Reproducible Simulation Benchmark of Reinforcement Learning and Classical Control for Electric Vehicle Battery Thermal Management",
                         author="Rishuraj Singh, Nihaal Sansanwal, Harshit Singh Parmar, Chaitanya Sharma")
        left = Frame(MARGIN_X, BOTTOM, COL_W, PAGE_H - BOTTOM - TOP,
                     leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="L")
        right = Frame(MARGIN_X + COL_W + GAP, BOTTOM, COL_W, PAGE_H - BOTTOM - TOP,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="R")
        first_left = Frame(MARGIN_X, BOTTOM, COL_W, PAGE_H - BOTTOM - 170,
                           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="FL")
        first_right = Frame(MARGIN_X + COL_W + GAP, BOTTOM, COL_W, PAGE_H - BOTTOM - 170,
                            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="FR")
        self.addPageTemplates([
            PageTemplate(id="first", frames=[first_left, first_right], onPage=first_page,
                         autoNextPageTemplate="normal"),
            PageTemplate(id="normal", frames=[left, right]),
        ])


# The editable text is canonical. All result tables and plots read recorded data.
EQUATIONS = {
    1: [r"F_t=m\dot v+mgC_r\cos\theta+mg\sin\theta",
        r"\quad+\frac{1}{2}\rho C_d A v^2,\qquad\theta=\arctan g_r"],
    2: r"V_t=V_{\mathrm{oc}}(z)-IR_0(z,T)-v_{\mathrm{RC}}",
    3: r"c_t=20(d_t/5)^2+\Delta T_t/5+E_{\mathrm{aux},t}/3000+A_t/5",
    4: r"v_{\mathrm{RC}}(t+\Delta t)=IR_1+[v_{\mathrm{RC}}(t)-IR_1]e^{-\Delta t/\tau}",
    5: r"\epsilon=1-e^{-UA/(\dot m c_p)}",
    6: r"P_{\mathrm{aux}}=150u_p^3+300u_f^3+\dot Q_{\mathrm{chiller}}/2.5",
    7: r"r_k=-\sum_{j=1}^{5}c_{5k+j},\quad J_{\mathrm{episode}}=-\sum_k r_k",
    8: r"L_{\mathrm{SAC}}=\mathbb{E}_{D}[\alpha\log\pi(a|s)-\min_i Q_i(s,a)]",
    9: [r"\widetilde a=\mathrm{clip}(\pi'(s')+\epsilon,a_{\min},a_{\max})",
        r"y=r+\gamma(1-d)\min_i Q_i'(s',\widetilde a)"],
    10: r"L_{\mathrm{PPO}}=\mathbb{E}[\min(rA,\mathrm{clip}(r,1-\epsilon,1+\epsilon)A)]",
    11: [r"R_E=\Delta E_b+\Delta E_c-Q_{\mathrm{gen}}-Q_{\mathrm{pump}}",
         r"\quad+Q_{\mathrm{ambient}}+Q_{\mathrm{radiator}}+Q_{\mathrm{chiller}}"],
}


def clean(text):
    text = ' '.join(str(text).split())
    for bad, good in {'\u2013': '-', '\u2014': '-', '\u2019': "'", '\u2018': "'",
                      '\u201c': '"', '\u201d': '"', '\u00a0': ' '}.items():
        text = text.replace(bad, good)
    return text


def pdf_reference(reference):
    text = html.escape(clean(reference['text']))
    match = re.search(r'doi:\s*(10\.\S+?)(?:\.$|$)', reference['text'])
    doi = reference.get('doi') or (match[1] if match else None)
    if doi:
        text = text.replace(html.escape(doi), f'<link href="https://doi.org/{html.escape(doi)}">{html.escape(doi)}</link>')
    elif reference.get('url'):
        text += f' <link href="{html.escape(reference["url"], quote=True)}">[Online record]</link>'
    return Paragraph(f'<a name="ref{reference["id"]}"/>[{reference["id"]}] {text}', styles['ref'])


def equation_flow(number):
    equations = EQUATIONS[number]
    if isinstance(equations, str):
        equations = [equations]
    images = []
    for line, expression in enumerate(equations):
        path = TEMP / f'eq-{number:02}-{line}.png'
        math_to_image('$' + expression + '$', path, dpi=360,
                      prop=FontProperties(size=10), color='black')
        with PILImage.open(path) as image:
            width = min(COL_W - 26, image.width * 72 / 360)
            height = width * image.height / image.width
        images.append(Image(str(path), width=width, height=height))
        if line < len(equations)-1:
            images.append(Spacer(1, 4))
    if number == 2:
        path = TEMP / 'eq-02-soc.png'
        math_to_image(r'$\dot z=-I/(3600Q_{\mathrm{Ah}})$', path, dpi=360,
                      prop=FontProperties(size=10), color='black')
        with PILImage.open(path) as image:
            width = min(COL_W - 26, image.width * 72 / 360)
            height = width * image.height / image.width
        images += [Spacer(1, 4), Image(str(path), width=width, height=height)]
    row = Table([[images, para(f'({number})', 'eqno')]], colWidths=[COL_W - 24, 24])
    row.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 0),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                            ('TOPPADDING', (0, 0), (-1, -1), 5),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
    return KeepTogether([row])


class FigureBlock(Flowable):
    """A figure and its caption move between columns as one indivisible block."""
    def __init__(self,path,caption):
        super().__init__()
        with PILImage.open(path) as image:
            self.width=COL_W-2
            self.image_height=self.width*image.height/image.width
        self.image=Image(str(path),width=self.width,height=self.image_height)
        self.caption=para(caption,'caption')
        self.caption_height=self.caption.wrap(self.width,1000)[1]
        self.height=self.image_height+self.caption_height+10

    def wrap(self,available_width,available_height):
        return self.width,self.height

    def split(self,available_width,available_height):
        return []

    def draw(self):
        self.image.drawOn(self.canv,0,self.caption_height+7)
        self.caption.drawOn(self.canv,0,0)


def figure_flow(number, caption):
    path = FIGURES[number]
    return FigureBlock(path,caption)


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def json_file(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def printed(value,places):
    """Round the recorded decimal value, avoiding binary tie drift (42.275)."""
    return format(Decimal(str(value)).quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP),'f')


def recorded_tables(content):
    tables = json.loads(json.dumps(content['table_definitions']))
    next(r for r in tables['VIII'][2:] if r[0]=='Batch size')[2]='256'
    data = csv_rows(RESULTS / 'controller_comparison.csv')
    def row(algo, shield):
        return next(r for r in data if r['algo'] == algo and r['shield'].lower() == str(shield).lower())
    order = [('mpc', 'Sampling MPC'), ('pid', 'Tuned PID'), ('td3', 'TD3'), ('sac', 'SAC'),
             ('ppo', 'PPO'), ('null', 'Null with shield'), ('bangbang', 'Bang-bang')]
    tables['III'] = ['Held-out shielded means; percentages average episodes equally.',
                     ['Controller', 'Cost', 'Aux. Wh', 'Fire %']]
    tables['III'] += [[name, f"{float(row(a, True)['cost_mean']):.1f}",
                       f"{float(row(a, True)['aux_wh_mean']):.1f}",
                       f"{float(row(a, True)['shield_firing_percent_mean']):.2f}"] for a, name in order]
    raw_order = [('pid','Tuned PID'),('bangbang','Bang-bang'),('mpc','Sampling MPC'),
                 ('sac','SAC'),('td3','TD3'),('ppo','PPO'),('null','Null')]
    tables['IV'] = ['Raw held-out control; violation percentages average episodes equally.',
                    ['Controller', 'Cost', 'Viol. %']]
    tables['IV'] += [[name, f"{float(row(a, False)['cost_mean']):.1f}",
                      printed(row(a,False)['violation_percent_mean'],2)] for a, name in raw_order]
    tables['IX'] = ['Shielded thermal metrics; values average episode-level metrics.',
                    ['Control','Mean max °C','Spread °C','Aging s']]
    tables['IX'] += [[name, f"{float(row(a, True)['max_temperature_c_mean']):.2f}",
                      f"{float(row(a, True)['spatial_delta_c_mean']):.2f}",
                      f"{float(row(a, True)['aging_exposure_s_mean']):.1f}"] for a, name in order]
    tables['X'] = ['Across-seed variation in learned-policy cost (descriptive).',
                   ['Policy','Shielded J','Seed SD','Raw J']]
    tables['X'] += [[a.upper(), f"{float(row(a, True)['cost_mean']):.1f}",
                     f"{float(row(a, True)['cost_std']):.1f}",
                     f"{float(row(a, False)['cost_mean']):.0f}"] for a in ('td3','sac','ppo')]
    cycles = json_file(RESULTS / 'cycle_report.json')
    tables['VI'] = ['Source speed data and modeled demand, including drivetrain assumptions.',
                    ['Cycle','s','km','kWh/100 km']]
    tables['VI'] += [[r['cycle'].upper(),f"{r['duration_s']:.0f}",f"{r['distance_km']:.2f}",
                      f"{r['kwh_per_100km']:.2f}"] for r in cycles]
    bench = json_file(RESULTS / 'deployment_benchmark_sac_seed0.json')
    tables['V'] = ['Recorded warmed fixed-observation laptop timing.', ['Runtime','Median ms','P99 ms','Calls']]
    labels={'pytorch':'PyTorch','onnx':'ONNX','int8':'INT8','sampling_mpc':'MPC'}
    for r in bench['rows']:
        precision = 2 if r['runtime'] == 'sampling_mpc' else 4
        tables['V'].append([labels[r['runtime']], f"{r['median_ms']:.{precision}f}",
                            f"{r['p99_ms']:.{precision}f}",str(r['repeats'])])
    return tables


def renumber(content):
    blocks = json.loads(json.dumps(content['blocks']))
    order=[]
    pattern=r'\[(\d+)\](?:-\[(\d+)\])?'
    for block in blocks:
        for match in re.finditer(pattern, block.get('text','')):
            numbers=range(int(match[1]),int(match[2])+1) if match[2] else [int(match[1])]
            for n in numbers:
                if n not in order:order.append(n)
    defined={r['id'] for r in content['references']}
    assert set(order)==defined, ('Uncited or missing reference',set(order)^defined)
    mapping={old:new for new,old in enumerate(order,1)}
    def replace(match):
        numbers=range(int(match[1]),int(match[2])+1) if match[2] else [int(match[1])]
        return ','.join(f'[{mapping[n]}]' for n in numbers)
    for block in blocks:
        if 'text' in block:block['text']=re.sub(pattern,replace,clean(block['text']))
    references=[]
    for old in order:
        r=dict(next(r for r in content['references'] if r['id']==old))
        r.update(source_id=old,id=mapping[old])
        references.append(r)
    return blocks,references


def generate_figures():
    import numpy as np
    from btms.dashboard.evidence import get_runs
    from btms.envs.shield import apply_shield
    import inspect
    folder=ROOT/'report/paper_revision/figures'
    folder.mkdir(parents=True,exist_ok=True)
    figures={n:folder/f'figure_{n}.png' for n in range(1,7)}
    rows=csv_rows(RESULTS/'controller_comparison.csv')
    def get(a,shield):return next(r for r in rows if r['algo']==a and (r['shield'].lower()=='true')==shield)
    palette={'sac':'#168674','td3':'#4575a1','ppo':'#ce7d3c'}
    plt.rcParams.update({'font.size':9,'axes.titlesize':10})
    fig,ax=plt.subplots(figsize=(6,3.6))
    runs=get_runs()
    for algo in ('ppo','sac','td3'):
        chosen=[r for r in runs if r['algorithm']==algo]
        assert len(chosen)==5 and all(r['curve'] for r in chosen)
        steps=sorted(set.intersection(*[{v['step'] for v in r['curve']} for r in chosen]))
        values=np.array([[next(v['value'] for v in r['curve'] if v['step']==step) for step in steps] for r in chosen])
        mean,sd=values.mean(axis=0),values.std(axis=0,ddof=1)
        ax.plot(steps,mean,marker='o',markersize=3,label=f'{algo.upper()} (5 seeds)',color=palette[algo])
        ax.fill_between(steps,mean-sd,mean+sd,color=palette[algo],alpha=.13)
    ax.set(xlabel='Actual environment steps',ylabel='Tuning evaluation return',title='Recorded training-time evaluation')
    ax.grid(alpha=.2);ax.legend(fontsize=8);fig.tight_layout();fig.savefig(figures[1],dpi=230);plt.close(fig)
    labels=['PID','PPO','SAC','TD3'];algos=['pid','ppo','sac','td3']
    fig,axes=plt.subplots(3,1,figsize=(4.4,7.8))
    for ax,key,title,unit in zip(axes,['cost','aux_wh','shield_firing_percent'],
                                ['Shielded integrated cost','Auxiliary electricity','Supervisor firing'],
                                ['Mean episode cost','Mean episode Wh','Mean episode %']):
        ax.bar(labels,[float(get(a,True)[key+'_mean']) for a in algos],
               yerr=[float(get(a,True)[key+'_std']) for a in algos],
               color=['#303a42',palette['ppo'],palette['sac'],palette['td3']],capsize=3)
        ax.set(title=title,ylabel=unit);ax.grid(axis='y',alpha=.2)
    fig.tight_layout(h_pad=1.5);fig.savefig(figures[2],dpi=240);plt.close(fig)
    fig,ax=plt.subplots(figsize=(5.8,3.6))
    for a,label,color,offset in [('mpc','MPC','#7150a0',(-6,8)),('pid','PID','#222222',(0,9)),
                                ('td3','TD3','#4575a1',(-12,10)),('sac','SAC','#168674',(0,-15)),
                                ('ppo','PPO','#ce7d3c',(8,9)),('null','Null','#879389',(17,-15)),
                                ('bangbang','Bang-bang','#8a6040',(-22,9))]:
        x,y=float(get(a,True)['cost_mean']),float(get(a,False)['violation_percent_mean'])
        ax.scatter([x],[y],c=[color],s=42,zorder=3)
        ax.annotate(label,(x,y),xytext=offset,textcoords='offset points',fontsize=8,color=color,ha='center')
    ax.set(xlim=(1570,2040),ylim=(-4,49),xlabel='Mean shielded episode cost',ylabel='Mean raw episode violation (%)')
    ax.grid(alpha=.2);fig.tight_layout();fig.savefig(figures[3],dpi=240);plt.close(fig)
    fig,ax=plt.subplots(figsize=(5.8,3.6));xx=np.arange(3)
    ax.bar(xx-.19,[float(get(a,False)['violation_percent_mean']) for a in ('ppo','sac','td3')],.38,label='Raw violation',color='#ba4040')
    ax.bar(xx+.19,[float(get(a,True)['shield_firing_percent_mean']) for a in ('ppo','sac','td3')],.38,label='Shield firing',color='#d08a3a')
    ax.set_xticks(xx,['PPO','SAC','TD3']);ax.set(ylabel='Mean episode fraction (%)');ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(figures[4],dpi=240);plt.close(fig)
    fig,ax=plt.subplots(figsize=(6,3.6))
    for a,label,color in [('sac','SAC seed 0',palette['sac']),('pid','Tuned PID','#527aa7')]:
        record=json_file(ROOT/f'report/dashboard/replays/{a}_hot_s701_shielded.json')['results'][0]
        assert record['reproduces_recorded_metrics'] and record['episode']['id']=='hot_s701'
        trace=record['trace'];ax.plot([r['time_s'] for r in trace],[max(r['temperatures_c']) for r in trace],label=label,color=color)
    threshold=inspect.signature(apply_shield).parameters['threshold_c'].default
    assert threshold==42.0
    ax.axhspan(15,45,color='#dbe9d5',alpha=.45,label='Study band')
    ax.axhline(threshold,color='#b13c35',linestyle='--',label='Supervisor at 42°C')
    ax.set(ylim=(15,47),xlabel='Simulation time (s)',ylabel='Maximum module temperature (°C)',title='Fixed hot US06 episode')
    ax.legend(fontsize=8,ncol=2);ax.grid(alpha=.2);fig.tight_layout();fig.savefig(figures[5],dpi=240);plt.close(fig)
    bench=json_file(RESULTS/'deployment_benchmark_sac_seed0.json')
    fig,ax=plt.subplots(figsize=(5.8,3.6))
    ax.bar(['PyTorch','ONNX','INT8','MPC'],[r['median_ms'] for r in bench['rows']],color=['#4575a1','#168674','#83a35b','#b45c49'])
    ax.set_yscale('log');ax.axhline(100,color='#777',linestyle='--',label='Illustrative 100 ms reference')
    ax.set(ylabel='Recorded median call time (ms)',title='Laptop benchmark: fixed observation')
    ax.legend(fontsize=7);ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(figures[6],dpi=240);plt.close(fig)
    return figures


def tex_text(text):
    citations=[]
    def take(match):
        citations.append('\\cite{r'+match[1]+'}')
        return f'ZZCITATION{len(citations)-1}ZZ'
    text=re.sub(r'\[(\d+)\]',take,clean(text))
    replacements={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#',
                  '_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    text=''.join(replacements.get(c,c) for c in text)
    text=text.replace('°',r'$^{\circ}$').replace('×',r'$\times$')
    for i,value in enumerate(citations):text=text.replace(f'ZZCITATION{i}ZZ',value)
    return text


def write_tex(content,blocks,references):
    lines=[r'\documentclass[conference]{IEEEtran}',r'\usepackage{amsmath,amssymb,graphicx,booktabs,url}',
           r'\usepackage[hidelinks]{hyperref}',r'\title{'+tex_text(content['title'])+'}',
           r'\author{\IEEEauthorblockN{'+tex_text(', '.join(content['authors']))+'}',
           r'\IEEEauthorblockA{'+tex_text(content['affiliation'])+'}}',r'\begin{document}',r'\maketitle']
    appendix=False
    for block in blocks:
        kind=block['type'];text=block.get('text','')
        if kind=='sub' and text=='Abstract':continue
        if kind=='abstract':
            if text.startswith('Index Terms'):
                lines += [r'\begin{IEEEkeywords}'+tex_text(text.split('--',1)[-1])+r'\end{IEEEkeywords}']
            else:lines += [r'\begin{abstract}'+tex_text(text)+r'\end{abstract}']
        elif kind=='body':lines += [tex_text(text),'']
        elif kind=='section':
            if text=='REFERENCES':continue
            if text.startswith('APPENDIX') and not appendix:
                lines.append(r'\appendices');appendix=True
            heading=re.sub(r'^(?:[IVX]+\.|APPENDIX [AB]\.)\s*','',text)
            lines.append(r'\section{'+tex_text(heading.title())+'}')
        elif kind=='sub':lines.append(r'\subsection{'+tex_text(re.sub(r'^[A-D]\.\s*','',text))+'}')
        elif kind=='table':
            caption,*rows=TABLES[block['id']]
            label={'III':'shielded','IV':'raw'}.get(block['id'],block['id'])
            lines += [r'\begin{table}[t]',r'\caption{'+tex_text(caption)+'}',r'\label{tab:'+label+'}',
                      r'\centering\footnotesize',r'\begin{tabular}{l'+'r'*(len(rows[0])-1)+'}',r'\toprule']
            for i,row in enumerate(rows):
                lines.append(' & '.join(tex_text(cell) for cell in row)+r'\\')
                if i==0:lines.append(r'\midrule')
            lines += [r'\bottomrule',r'\end{tabular}',r'\end{table}']
        elif kind=='figure':
            path='../'+FIGURES[block['id']].relative_to(ROOT).as_posix()
            caption=re.sub(r'^Fig\. \d+\.\s*','',text)
            lines += [r'\begin{figure}[t]',r'\centering',r'\includegraphics[width=\columnwidth]{'+path+'}',
                      r'\caption{'+tex_text(caption)+'}',r'\label{fig:'+str(block['id'])+'}',r'\end{figure}']
        elif kind=='equation':
            n=block['id'];eq=EQUATIONS[n]
            if isinstance(eq,list):expression=r'\begin{gathered}' + r'\\'.join(eq)+r'\end{gathered}'
            else:expression=eq
            if n==2:expression=r'\begin{gathered}'+expression+r'\\\dot z=-I/(3600Q_{\mathrm{Ah}})\end{gathered}'
            lines += [r'\begin{equation}',expression,r'\label{eq:'+str(n)+'}',r'\end{equation}']
    lines.append(r'\begin{thebibliography}{99}')
    for r in references:
        lines.append(r'\bibitem{r'+str(r['id'])+'} '+tex_text(r['text'])+
                     (r' \url{'+r['url']+'}.' if r.get('url') else ''))
    lines += [r'\end{thebibliography}',r'\end{document}']
    (ROOT/'deliverables/IEEE_BTMS_Manuscript.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def build():
    global TABLES,FIGURES
    content=json_file(CONTENT)
    TABLES=recorded_tables(content)
    FIGURES=generate_figures()
    blocks,references=renumber(content)
    story=[]
    for block in blocks:
        kind=block['type']
        if kind=='table':story.append(table_flow(block['id']))
        elif kind=='equation':story.append(equation_flow(block['id']))
        elif kind=='figure':story.append(figure_flow(block['id'],block['text']))
        elif kind=='section' and block.get('text')=='REFERENCES':
            continue
        else:story.append(para(block['text'],kind))
    story.append(para('REFERENCES','section'))
    story += [pdf_reference(r) for r in references]
    Paper(TARGET).build(story)
    write_tex(content,blocks,references)
    registry=dict(checked_on=content['literature_checked'],scope='Targeted primary-source update; not an exhaustive systematic review',references=references)
    (ROOT/'deliverables/IEEE_BTMS_References.json').write_text(json.dumps(registry,indent=2,ensure_ascii=False),encoding='utf-8')
    out=ROOT/'report/paper_revision';out.mkdir(exist_ok=True)
    inputs=[CONTENT,RESULTS/'controller_comparison.csv',RESULTS/'cycle_report.json',RESULTS/'deployment_benchmark_sac_seed0.json']
    inputs += list((ROOT/'report/dashboard/replays').glob('*hot_s701_shielded.json'))
    inputs += [ROOT/'scripts/build_research_paper.py']
    manifest=dict(pdf=str(TARGET.relative_to(ROOT)),pdf_sha256=hashlib.sha256(TARGET.read_bytes()).hexdigest(),
                  pages=len(pymupdf.open(TARGET)),references=len(references),equations=len(EQUATIONS),
                  figures=len(FIGURES),tables=len(TABLES),
                  input_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                  figure_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in FIGURES.values()},
                  remaining_external_requirements=['Venue-specific template/page limits not specified','No verified public repository/data/demo URLs supplied'])
    (out/'build_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':
    build()

