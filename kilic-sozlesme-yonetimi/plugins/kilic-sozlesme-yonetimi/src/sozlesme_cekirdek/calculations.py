"""Exact user-supplied inputs. Arithmetic/date output is not source or legal verification."""
from datetime import date,timedelta
from decimal import Decimal,localcontext,ROUND_HALF_UP,ROUND_HALF_EVEN,ROUND_DOWN
import calendar
import re
from .errors import CoreError
from .safety import hash_value

ROUNDINGS={'HALF_UP':ROUND_HALF_UP,'HALF_EVEN':ROUND_HALF_EVEN,'DOWN':ROUND_DOWN}


def decimal_text(value):
    if type(value) is not str or not re.fullmatch(r'(0|[1-9][0-9]{0,23})(\.[0-9]{1,12})?',value):
        raise CoreError('HESAP_GIRDISI','Ondalık string, nokta ayracı ve negatif olmayan sınırlı değer gerekli')
    return Decimal(value)


def money(spec):
    expected={'kind','base','rate','periods','currency','places','rounding','cap'}
    if set(spec)!=expected or spec['kind']!='MONEY' or spec['currency'] not in {'TRY','USD','EUR','GBP'}:
        raise CoreError('HESAP_GIRDISI','Tam para hesabı parametreleri gerekli')
    if type(spec['periods']) is not int or not 0<=spec['periods']<=1000000 or type(spec['places']) is not int or not 0<=spec['places']<=4 or spec['rounding'] not in ROUNDINGS:
        raise CoreError('HESAP_GIRDISI','Dönem/yuvarlama aralığı farklı')
    base,rate=decimal_text(spec['base']),decimal_text(spec['rate'])
    if rate>1:raise CoreError('HESAP_GIRDISI','Oran kesir olarak 0–1 aralığında olmalı')
    cap=None if spec['cap'] is None else decimal_text(spec['cap'])
    with localcontext() as context:
        context.prec=64
        raw=base*rate*spec['periods'];bounded=min(raw,cap) if cap is not None else raw
        amount=bounded.quantize(Decimal(1).scaleb(-spec['places']),rounding=ROUNDINGS[spec['rounding']])
    return {'kind':'MONEY','amount':format(amount,'f'),'currency':spec['currency'],'raw_amount':format(raw,'f'),
        'cap_applied':cap is not None and raw>cap,'input_digest':hash_value(spec),'input_verification':'USER_INPUT_NOT_VERIFIED',
        'business_approval':'NOT_GRANTED','legal_enforceability':'NOT_EVALUATED'}


def due_date(spec):
    expected={'kind','start','count','unit','day_type','include_start','month_end','weekend','holidays','holiday_calendar_complete'}
    if set(spec)!=expected or spec['kind']!='DATE' or type(spec['count']) is not int or not 1<=spec['count']<=3660 or type(spec['include_start']) is not bool:
        raise CoreError('TARIH_KURALI','Başlangıç, süre ve açık tarih kuralı gerekli')
    try:start=date.fromisoformat(spec['start'])
    except (TypeError,ValueError) as exc:raise CoreError('TARIH_KURALI','YYYY-MM-DD tarihi gerekli') from exc
    if spec['start']!=start.isoformat():raise CoreError('TARIH_KURALI','Kanonik başlangıç tarihi gerekli')
    try:
        if spec['unit']=='MONTHS':
            if spec['day_type']!='CALENDAR' or spec['include_start'] or spec['month_end'] not in {'CLAMP','ERROR'} or spec['weekend'] or spec['holidays'] or spec['holiday_calendar_complete'] is not None:
                raise CoreError('TARIH_KURALI','Ay için takvim ve açık ay sonu politikası gerekli')
            index=start.year*12+start.month-1+spec['count'];year,zero=divmod(index,12);month=zero+1
            last=calendar.monthrange(year,month)[1]
            if start.day>last and spec['month_end']=='ERROR':raise CoreError('TARIH_KURALI','Hedef ayda bu gün yok; açık karar gerekli')
            result=date(year,month,min(start.day,last))
        elif spec['unit']=='DAYS':
            if spec['month_end'] is not None:raise CoreError('TARIH_KURALI','Gün hesabında ay sonu alanı boş olmalı')
            if spec['day_type']=='CALENDAR':
                if spec['weekend'] or spec['holidays'] or spec['holiday_calendar_complete'] is not None:raise CoreError('TARIH_KURALI','Takvim günü hesabına iş günü takvimi eklenemez')
                result=start+timedelta(days=spec['count']-int(spec['include_start']))
            elif spec['day_type']=='BUSINESS':
                weekend=spec['weekend'];holidays=spec['holidays']
                if (type(weekend) is not list or not 1<=len(set(weekend))<=6 or len(set(weekend))!=len(weekend)
                    or any(type(day) is not int or not 0<=day<=6 for day in weekend) or type(holidays) is not list
                    or len(set(holidays))!=len(holidays) or spec['holiday_calendar_complete'] is not True):
                    raise CoreError('TARIH_KURALI','Açık hafta tatili ve tamam olduğu beyan edilen tatil takvimi gerekli')
                excluded={date.fromisoformat(d) for d in holidays}
                if any(d.isoformat()!=raw for d,raw in zip([date.fromisoformat(v) for v in holidays],holidays)):raise CoreError('TARIH_KURALI','Kanonik tatil tarihi gerekli')
                result=start if spec['include_start'] else start+timedelta(days=1);remaining=spec['count']
                while True:
                    if result.weekday() not in weekend and result not in excluded:remaining-=1
                    if remaining==0:break
                    result+=timedelta(days=1)
            else:raise CoreError('TARIH_KURALI','İş veya takvim günü açık seçilmeli')
        else:raise CoreError('TARIH_KURALI','DAYS veya MONTHS gerekli')
    except (ValueError,TypeError,OverflowError) as exc:raise CoreError('TARIH_KURALI','Tarih/takvim değeri veya aralığı geçersiz') from exc
    return {'kind':'DATE','date':result.isoformat(),'input_digest':hash_value(spec),'input_verification':'USER_INPUT_NOT_VERIFIED',
        'business_approval':'NOT_GRANTED','legal_deadline':'NOT_EVALUATED'}


def calculate(spec):
    if type(spec) is not dict:raise CoreError('HESAP_GIRDISI','Tipli hesap nesnesi gerekli')
    if spec.get('kind')=='MONEY':return money(spec)
    if spec.get('kind')=='DATE':return due_date(spec)
    raise CoreError('HESAP_GIRDISI','İzinli para/tarih hesabı gerekli')
