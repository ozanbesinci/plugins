"""Build readable print bands without changing any canonical workbook values."""
from pathlib import Path
from copy import copy
import math,re,textwrap
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Alignment,Font,PatternFill,Border,Side
from openpyxl.worksheet.pagebreak import Break
from display_values import label
MAX_WIDTH=145
COMPARISON_MAX_WIDTH=110
MAX_LINES=20
NUMBER=re.compile(r'([^\d-]*)(-?\d+)(\.\d+)?(\D*)')

def _chunks(text,width):
    return [text[i:i+width] for i in range(0,len(text),width)]

def _split_long(token,width):
    # A long token always starts its own line, so a number's integer digits stay
    # together on that line; only fraction digits may continue below.
    m=NUMBER.fullmatch(token)
    if m and m[1] and len(m[1])+len(m[2])>width and len(m[2])<=width:
        return _chunks(m[1],width)+_chunks(token[len(m[1]):],width)
    return _chunks(token,width)

def wrap_text(part,width,hard=None):
    # break_long_words=False keeps a long number off the end of a label line
    # (the old "Alım bugünkü değeri: 10 / 3367.74" split). `width` is the conservative
    # wrap estimate; a single word is cut only when it exceeds `hard`, the characters
    # the column really holds (so "Belirtilmedi" is not printed as "Belirtilme" / "di").
    hard=max(width,hard or width)
    lines=[]
    for line in textwrap.wrap(part,width=width,break_long_words=False,break_on_hyphens=False) or ['']:
        lines.extend(_split_long(line,width) if len(line)>hard else [line])
    return lines

def pack_groups(groups):
    """Pack wrapped logical lines into chunks of at most MAX_LINES without splitting a group,
    unless the group alone is longer than MAX_LINES."""
    chunks=[];cur=[]
    for g in groups:
        for i in range(0,len(g),MAX_LINES):
            piece=g[i:i+MAX_LINES]
            if cur and len(cur)+len(piece)>MAX_LINES:chunks.append(cur);cur=[]
            cur=cur+piece
    if cur or not chunks:chunks.append(cur)
    return chunks

def paragraph_groups(text,width,hard=None):
    """Wrapped lines grouped per paragraph; a blank separator line stays with the paragraph above.
    A paragraph longer than MAX_LINES falls back to one group per logical line."""
    groups=[];cur=[]
    def close(sep):
        if not cur:return
        lines=[l for g in cur for l in g]
        parts=[lines] if len(lines)<=MAX_LINES else [list(g) for g in cur]
        if sep:parts[-1]=parts[-1]+['']
        groups.extend(parts)
    for part in text.splitlines() or ['']:
        if part.strip()=='':
            close(True);cur=[]
        else:
            cur.append(wrap_text(part,width,hard))
    close(False)
    return groups or [['']]

def _empty_record_notice(values):
    """Recognize the report's explicit no-record row without treating blanks as data."""
    populated=[str(v).strip() for v in values if v is not None and str(v).strip()]
    if len(populated)!=1:
        return None
    text=populated[0].casefold()
    if 'bulunmuyor' in text and any(token in text for token in ('kayıt','kayit','kaydı','kaydi')):
        return 'Kayıt bulunmuyor'
    return None

def build_print_workbook(xlsx:Path,target:Path):
    source=load_workbook(xlsx,data_only=True)
    out=Workbook();out.remove(out.active);mapping=[]
    try:
        for ws in source.worksheets:
            # Excel COM coalesces equal-width adjacent columns into one dimension.
            # Resolve min/max spans before reading width, instead of creating defaults.
            widths={}
            for c in range(1,ws.max_column+1):
                span=next((d for d in ws.column_dimensions.values() if (d.min or 0)<=c<=(d.max or 0)),None)
                width=span.width if span is not None else ws.sheet_format.defaultColWidth or 13
                widths[c]=max(16,min(40,float(width)))
            if ws.title=='Ozet':widths={1:28,2:90}
            keys=list(range(1,min(2,ws.max_column)+1)) if ws.max_column>2 else []
            band_width=COMPARISON_MAX_WIDTH if ws.title=='Teklif Karsilastirma' else MAX_WIDTH
            if ws.max_column>2 and sum(widths.values())>band_width:
                groups=[];g=[];used=sum(widths[k] for k in keys)
                for c in range(3,ws.max_column+1):
                    if g and used+widths[c]>band_width:groups.append(keys+g);g=[];used=sum(widths[k] for k in keys)
                    g.append(c);used+=widths[c]
                if g:groups.append(keys+g)
            else:groups=[list(range(1,ws.max_column+1))]
            for band,cols in enumerate(groups,1):
                title=f'{ws.title[:24]} {band}' if len(groups)>1 else ws.title
                dest=out.create_sheet(title[:31]);dest.sheet_view.showGridLines=False
                for j,c in enumerate(cols,1):
                    cell=dest.cell(1,j,ws.cell(1,c).value);cell.font=Font(name='Calibri',size=11,bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='1F4E78');cell.alignment=Alignment(wrap_text=True,vertical='center',indent=1)
                    dest.column_dimensions[cell.column_letter].width=widths[c]
                dest.row_dimensions[1].height=34
                for r in range(2,ws.max_row+1):
                    empty_notice=_empty_record_notice([ws.cell(r,c).value for c in range(1,ws.max_column+1)])
                    prepared={};nchunks=1
                    for c in cols:
                        val=ws.cell(r,c).value
                        if isinstance(val,str):
                            # One group per paragraph (blank-line separated record, e.g. one
                            # assertion), so a label, its value and its source never land in
                            # different continuation rows or pages.
                            line_groups=paragraph_groups(val,max(8,int(widths[c]*.8)-2),int(widths[c])-3)
                            prepared[c]=pack_groups(line_groups);nchunks=max(nchunks,len(prepared[c]))
                        else:prepared[c]=val
                    for chunk in range(nchunks):
                        nr=dest.max_row+1;linecount=1
                        if empty_notice:
                            if len(cols)>1:
                                dest.merge_cells(start_row=nr,start_column=1,end_row=nr,end_column=len(cols))
                            notice=dest.cell(nr,1,empty_notice)
                            notice.font=Font(name='Calibri',size=18,bold=True,color='17365D')
                            notice.fill=PatternFill('solid',fgColor='FFF2CC')
                            notice.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
                            notice.border=Border(left=Side(style='medium',color='C9A227'),right=Side(style='medium',color='C9A227'),top=Side(style='medium',color='C9A227'),bottom=Side(style='medium',color='C9A227'))
                            dest.row_dimensions[nr].height=54
                            mapping.append({'source_sheet':ws.title,'source_row':r,'source_columns':cols,'print_sheet':dest.title,'print_row':nr,'continuation':chunk,'empty_notice':True})
                            continue
                        for j,c in enumerate(cols,1):
                            val=prepared[c]
                            if isinstance(val,list):
                                # Repeat short values (row identity) on every continuation chunk.
                                segment=list(val[0] if len(val)==1 else (val[chunk] if chunk<len(val) else []))
                                if chunk and j==1 and len(segment)<MAX_LINES:segment.append('(devam)')
                                val='\n'.join(segment) if segment else None;linecount=max(linecount,len(segment))
                            cell=dest.cell(nr,j,val);cell.font=Font(name='Calibri',size=11);cell.alignment=Alignment(vertical='top',wrap_text=True,indent=1);cell.number_format=ws.cell(r,c).number_format
                            cell.border=Border(right=Side(style='thin',color='D9D9D9'))
                        section_title = ws.title == 'Kapsam ve Riskler' and ws.cell(r,1).value == 'Elemeler'
                        section_header = ws.title == 'Kapsam ve Riskler' and r > 1 and ws.cell(r-1,1).value == 'Elemeler'
                        if section_title or section_header:
                            for cell in dest[nr]:
                                cell.font=Font(name='Calibri',size=11,bold=True,color='FFFFFF' if section_header else '1F4E78')
                                cell.alignment=Alignment(vertical='center',wrap_text=True,indent=1)
                                cell.border=Border()
                                if section_header:cell.fill=PatternFill('solid',fgColor='1F4E78')
                        elif all(ws.cell(r,c).value is None for c in cols):
                            for cell in dest[nr]:cell.border=Border()
                        dest.row_dimensions[nr].height=max(34 if section_header else 18,15*linecount+5)
                        mapping.append({'source_sheet':ws.title,'source_row':r,'source_columns':cols,'print_sheet':dest.title,'print_row':nr,'continuation':chunk})
                dest.page_setup.orientation='landscape';dest.page_setup.paperSize=dest.PAPERSIZE_A3
                dest.sheet_properties.pageSetUpPr.fitToPage=True;dest.page_setup.fitToWidth=1;dest.page_setup.fitToHeight=0
                dest.print_title_rows='1:1';dest.print_area=dest.dimensions
                dest.page_margins.left=dest.page_margins.right=.25;dest.page_margins.top=dest.page_margins.bottom=.6
                dest.page_margins.header=.2
                dest.oddHeader.center.text=f'{label(ws.title)} · Sütun grubu {band}/{len(groups)}';dest.oddHeader.center.size=11
                dest.oddFooter.right.text='Sayfa &P / &N';dest.oddFooter.right.size=10
        target.parent.mkdir(parents=True,exist_ok=True);out.save(target)
        return {'path':str(target),'sheets':len(out.worksheets),'mapping':mapping,'minimum_font_points':11,'maximum_band_width':MAX_WIDTH,'all_columns_retained':True}
    finally:source.close();out.close()
