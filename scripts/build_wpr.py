"""Build four weekly progress-report pages using the user's WPR PDF format."""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

import pymupdf
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'deliverables/WPR_Weeks_1_to_4.json'
TARGET=ROOT/'output/pdf/WPR_Weeks_1_to_4.pdf'
FONT=Path('C:/Windows/Fonts')
for name,file in [('WPRTimes','times.ttf'),('WPRTimes-Bold','timesbd.ttf'),('WPRTimes-Italic','timesi.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
pdfmetrics.registerFontFamily('WPRTimes',normal='WPRTimes',bold='WPRTimes-Bold',italic='WPRTimes-Italic',boldItalic='WPRTimes-Bold')
WIDTH,HEIGHT=A4
MARGIN=56
CONTENT_WIDTH=WIDTH-2*MARGIN
styles={
 'institution':ParagraphStyle('institution',fontName='WPRTimes-Bold',fontSize=12.2,leading=15,alignment=TA_CENTER),
 'header':ParagraphStyle('header',fontName='WPRTimes-Bold',fontSize=11.5,leading=14,alignment=TA_CENTER),
 'details':ParagraphStyle('details',fontName='WPRTimes-Bold',fontSize=15,leading=18,alignment=TA_CENTER),
 'body':ParagraphStyle('body',fontName='WPRTimes',fontSize=10.2,leading=13.3,spaceAfter=3.2),
 'bullet':ParagraphStyle('bullet',fontName='WPRTimes',fontSize=10.2,leading=13.3,leftIndent=10,firstLineIndent=0,bulletIndent=0,spaceAfter=3.2),
 'section':ParagraphStyle('section',fontName='WPRTimes-Bold',fontSize=11.7,leading=14,spaceBefore=8,spaceAfter=4,keepWithNext=True),
 'cell':ParagraphStyle('cell',fontName='WPRTimes-Bold',fontSize=10.4,leading=13.2),
 'label':ParagraphStyle('label',fontName='WPRTimes-Bold',fontSize=11.2,leading=13.5),
 'signature':ParagraphStyle('signature',fontName='WPRTimes',fontSize=10.2,leading=13.5),
 'footer':ParagraphStyle('footer',fontName='WPRTimes-Italic',fontSize=7.2,leading=8.5,textColor=colors.HexColor('#666666')),
}


def p(text,style='body',bold=False):
    text=html.escape(str(text))
    return Paragraph('<b>'+text+'</b>' if bold else text,styles[style])


def page_footer(canvas,doc):
    note=p(DATA['allocation_status'],'footer')
    note.wrap(CONTENT_WIDTH,30)
    note.drawOn(canvas,MARGIN,24)


def page(week):
    story=[p(DATA['institution'],'institution'),p(DATA['school'],'institution'),
           p('WEEKLY PROGRESS REPORT','header'),p(DATA['semester'],'header'),
           Spacer(1,11),p('B.Tech. Major Project Details','details'),Spacer(1,10)]
    rows=[['Project Id',DATA['project_id']],['Project Title',DATA['project_title']],
          ['Reporting period',week['reporting_date'] or '________________________'],['Week No.',str(week['number'])]]
    table=Table([[p(label,'label'),p(value,'cell')] for label,value in rows],
                colWidths=[128,CONTENT_WIDTH-128],hAlign='LEFT')
    table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.65,colors.black),
                               ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                               ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
                               ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story += [table,Spacer(1,4),p('Work Completed This Week:','section')]
    story += [Paragraph(html.escape(text),styles['bullet'],bulletText='\u2022') for text in week['completed']]
    story.append(p('Challenges/Issues:','section'))
    story += [Paragraph(html.escape(text),styles['bullet'],bulletText='\u2022') for text in week['challenges']]
    story += [Spacer(1,5),Paragraph('<b>Plan for Next Week: </b>'+html.escape(week['next_plan']),styles['body']),
              Spacer(1,5),p("Guide's Remarks:",'body',bold=True),Spacer(1,33)]
    signatures=Table([[p('Signature of Student','signature'),p('Signature of Guide','signature')],
                      [p(DATA['student'],'signature'),p('['+DATA['guide']+']','signature')]],
                     colWidths=[CONTENT_WIDTH/2,CONTENT_WIDTH/2])
    signatures.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                                    ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                                    ('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),1)]))
    story += [signatures]
    return story


def main():
    global DATA
    DATA=json.loads(SOURCE.read_text(encoding='utf-8'))
    assert [w['number'] for w in DATA['weeks']]==[1,2,3,4]
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(TARGET),pagesize=A4,leftMargin=MARGIN,rightMargin=MARGIN,
                           topMargin=53,bottomMargin=49,title='Weekly Progress Reports - Weeks 1 to 4',
                           author=DATA['student'])
    story=[]
    for i,week in enumerate(DATA['weeks']):
        if i:story.append(PageBreak())
        story += page(week)
    doc.build(story,onFirstPage=page_footer,onLaterPages=page_footer)
    pdf=pymupdf.open(TARGET)
    assert len(pdf)==4, f'Expected one page per week, got {len(pdf)}'
    out=ROOT/'report/wpr';out.mkdir(parents=True,exist_ok=True)
    checks=[]
    for i,pg in enumerate(pdf,1):
        text=pg.get_text()
        assert DATA['student'] in text and DATA['project_id'] in text
        assert all(label in text for label in ('Work Completed This Week:','Challenges/Issues:',
                                                'Plan for Next Week:',"Guide's Remarks:",
                                                'Signature of Student','Signature of Guide'))
        assert 'DQN' not in text and 'FTP-75' not in text
        for word in pg.get_text('words'):
            assert word[0]>=MARGIN-2 and word[2]<=WIDTH-MARGIN+2,(i,word)
            assert word[1]>=45 and word[3]<HEIGHT-20,(i,word)
        pg.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(out/f'week-{i}.png')
        checks.append(dict(week=i,page=i,required_sections_present=True,within_page_bounds=True,
                           reporting_date=DATA['weeks'][i-1]['reporting_date']))
    # Evidence used for content; these records do not establish calendar allocation.
    report=dict(pdf=str(TARGET),pages=len(pdf),sha256=hashlib.sha256(TARGET.read_bytes()).hexdigest(),
                allocation_status=DATA['allocation_status'],checks=checks,
                evidence_by_week={str(w['number']):w['evidence'] for w in DATA['weeks']},
                source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest())
    (out/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
