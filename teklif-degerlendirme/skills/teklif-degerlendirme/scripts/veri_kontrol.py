"""Source completeness, blind comparison and bounded, evidenced corrections."""
from __future__ import annotations
import copy
import datetime as dt
import hashlib
import json
from teklif_motoru import cost_summary, score_suppliers, price_line, as_decimal

CRITICAL_FIELDS = ("total", "currency", "vat", "quantity", "quote_date", "validity", "delivery", "payment", "incoterms", "warranty")
STATES = {"verified", "missing", "excluded", "unreadable", "conflicting", "assumption"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fact_map(data):
    items = data.get("facts", [])
    if not isinstance(items, list):
        raise ValueError("facts liste olmalı.")
    result = {}
    for fact in items:
        if not isinstance(fact, dict) or not isinstance(fact.get("fact_id"), str) or not fact["fact_id"].strip() or fact["fact_id"] in result:
            raise ValueError("Olgu kimliği eksik veya yinelenmiş.")
        result[fact["fact_id"]] = fact
    return result


def evidence_ok(item, sources):
    return (isinstance(item, dict) and sources.get(item.get("source_id")) == item.get("source_sha256")
            and item.get("source_id") in sources and isinstance(item.get("location"), str) and bool(item["location"].strip())
            and isinstance(item.get("quote"), str) and bool(item["quote"].strip()))


def bound_scoring(data, costs):
    scoring=copy.deepcopy(data['scoring']); facts=fact_map(data)
    suppliers={o['id']:o['supplier_id'] for o in data['offers']}
    expected={s['supplier_id'] for s in scoring['suppliers']}
    for criterion in scoring['criteria']:
        bindings=criterion.get('bindings',{})
        if set(bindings)!=expected:
            raise ValueError('Her puanlama değeri maliyet hesabına veya doğrulanmış olguya bağlanmalı.')
        cost_ids={b.get('offer_id') for b in bindings.values() if b.get('kind')=='cost'}
        if cost_ids:
            if any(b.get('kind')!='cost' for b in bindings.values()):
                raise ValueError('Bir maliyet ölçütünde sayısal olgu ve maliyet birimleri karıştırılamaz.')
            bases={(data['costs'][oid].get('base_currency'),data['costs'][oid].get('base_date')) for oid in cost_ids}
            if len(bases)!=1 or not next(iter(bases))[0]:
                raise ValueError('Maliyet puanlaması tek ortak baz para birimi ve değerleme gününde olmalı.')
            quotes, rates={},{}
            for oid in cost_ids:
                payload=data['costs'][oid]
                for currency,quote in payload.get('fx_rates',{}).items():
                    value=(as_decimal(quote.get('forex_selling'),'fx'),as_decimal(quote.get('unit'),'fx unit'))
                    if currency in quotes and quotes[currency]!=value: raise ValueError('Aynı döviz için farklı kur setiyle maliyet puanlanamaz.')
                    quotes[currency]=value
                for currency,rate in payload.get('annual_rates',{}).items():
                    value=as_decimal(rate,'annual rate')
                    if currency in rates and rates[currency]!=value: raise ValueError('Aynı döviz için farklı iskonto oranıyla maliyet puanlanamaz.')
                    rates[currency]=value
        values={}
        for supplier,binding in bindings.items():
            if binding.get('kind')=='cost':
                oid=binding.get('offer_id')
                if suppliers.get(oid)!=supplier or binding.get('metric')!='known_present_value_in_base_currency':
                    raise ValueError('Puanlama maliyet bağı yanlış firmaya/ölçüye ait.')
                value=costs.get(oid,{}).get(binding['metric'])
                if value is None: raise ValueError('Puanlamada karşılaştırılabilir ortak döviz maliyeti yok.')
                values[supplier]=str(value)
            elif binding.get('kind')=='fact':
                fact=facts.get(binding.get('fact_id'),{})
                if fact.get('evidence_status')!='verified': raise ValueError('Puanlama olgusu doğrulanmamış.')
                values[supplier]=str(as_decimal(fact.get('value'),'scoring fact'))
            else: raise ValueError('Puanlama dayanağı cost veya fact olmalı.')
        criterion['values']=values
    return scoring


def validate(data, inventory):
    failures, open_issues = [], []
    if data.get("schema") != "teklif-data/v4":
        failures.append("Merkezi veri şeması teklif-data/v4 olmalı.")
    sources = {s["source_id"]: s["sha256"] for s in inventory["entries"]}
    facts = fact_map(data)
    offers = data.get("offers", [])
    ids = [o.get("id") for o in offers]
    if not ids or any(not i for i in ids) or len(set(ids)) != len(ids):
        failures.append("Firma/teklif kimlikleri boş veya yinelenmiş.")
    requirements = data.get("requirements", [])
    reqs = {r["id"]: r for r in requirements}
    if len(reqs) != len(requirements):
        failures.append("Şartname kimlikleri yinelenmiş.")
    rfi = data.get("rfi", [])
    rfi_facts = {f for r in rfi if r.get("owner") and r.get("question") for f in r.get("fact_ids", [])}
    scope_facts = {f for s in data.get("scope_items", []) for f in s.get("fact_ids", [])}
    scope_exceptions = data.get("scope_not_applicable", {})
    scope_ids=set()
    for item in data.get('scope_items',[]):
        if not item.get('id') or item['id'] in scope_ids or not item.get('fact_ids') or not set(item['fact_ids']).issubset(facts):
            failures.append('Kapsam kimliği benzersiz ve olguya bağlı olmalı.')
        scope_ids.add(item.get('id'))
        if item.get('classification')=='5-A':
            if item.get('offer_id') not in ids: failures.append('5-A firma bazlı olmalı.')
        elif item.get('classification')=='5-B':
            allocations=item.get('allocations',[])
            if len(allocations)!=len(ids) or {r.get('offer_id') for r in allocations}!=set(ids):
                failures.append('5-B bütün firmalarda kanıtlı ortak kapsam olmalı.')
            try:
                values={(as_decimal(r.get('amount'),'5-B amount'),r.get('currency'),dt.date.fromisoformat(r['payment_date'])) for r in allocations}
                if len(values)!=1 or any(not r.get('fact_ids') or not set(r['fact_ids']).issubset(facts) for r in allocations):
                    failures.append('5-B tutar/döviz/tarih/kanıt bütün firmalarda aynı olmalı.')
            except (ValueError,TypeError,KeyError) as error: failures.append('5-B bilinmeyen gider olamaz: '+str(error))
        else: failures.append('Kapsam sınıfı 5-A veya 5-B olmalı.')
    analysis_date = dt.date.fromisoformat(data["analysis_date"])
    required_ids = {f"{offer}/field/{field}" for offer in ids for field in CRITICAL_FIELDS}
    critical_ids = required_ids | {f"requirement/{rid}" for rid,r in reqs.items() if r.get('category')=='mandatory'}
    critical_ids |= {f"{offer}/requirement/{rid}" for offer in ids for rid,r in reqs.items() if r.get('category')=='mandatory'}
    required_ids |= {f"requirement/{rid}" for rid in reqs}
    required_ids |= {f"{offer}/requirement/{rid}" for offer in ids for rid in reqs}
    if any(r.get('category') not in {'mandatory','preference','information'} for r in requirements):
        failures.append('Her şartname hükmü mandatory/preference/information olarak sınıflanmalı.')
    absent = required_ids - set(facts)
    if absent:
        failures.append("Zorunlu olgu/hüküm kaydı eksik: " + ", ".join(sorted(absent)))
    for fid, fact in facts.items():
        state = fact.get("evidence_status")
        if state=='verified' and fact.get('value') is None:
            failures.append(f'{fid}: doğrulanmış değer null olamaz; eksik veri missing olmalı.')
        if state not in STATES:
            failures.append(f"{fid}: kanıt durumu geçersiz.")
        if fid in critical_ids and fact.get("critical") is not True:
            failures.append(f"{fid}: zorunlu alanın kritikliği kaldırılamaz.")
        if state in {"verified", "excluded", "conflicting"} and not evidence_ok(fact, sources):
            failures.append(f"{fid}: özgün kaynak/sayfa/alıntı bağı geçersiz.")
        if state != "verified":
            if not fact.get("open_issue") or fid not in rfi_facts:
                failures.append(f"{fid}: açık konu ve muhataplı RFI gerekli.")
            if fact.get("critical"):
                open_issues.append(fid)
        if fact.get("kind") == "scope" and state in {"missing", "excluded"} and fid not in scope_facts and not scope_exceptions.get(fid):
            failures.append(f"{fid}: 5-A/5-B adayı veya uygulanmama gerekçesi yok.")
        if "/requirement/" in fid and fact.get("value") == "noncompliant" and fid in critical_ids:
            if not any(fid in e.get("fact_ids", []) and e.get("reason") for e in data.get("exclusions", [])):
                failures.append(f"{fid}: uygunsuzluğun eleme değerlendirmesi yok.")
    for offer in offers:
        if not offer.get("supplier_id") or not offer.get("name"):
            failures.append(f"{offer.get('id')}: bağımsız tedarikçi kimliği/adı gerekli.")
        line_ids=set()
        for line in offer.get('lines',[]):
            if not line.get('id') or line['id'] in line_ids: failures.append('Kalem kimliği eksik/yinelenmiş.')
            line_ids.add(line.get('id'))
            for field in ('quantity','unit_price','vat_rate'):
                if line.get(field) is None: continue
                fact=facts.get(line.get('bindings',{}).get(field),{})
                try:
                    if fact.get('evidence_status')!='verified' or as_decimal(line[field],field)!=as_decimal(fact.get('value'),field):
                        failures.append(f"{offer['id']}/{line.get('id')}/{field}: kalem olguya bağlı değil.")
                except ValueError as error: failures.append(str(error))
        for key in ("quote_date", "validity"):
            fact = facts.get(f"{offer['id']}/field/{key}", {})
            if fact.get("evidence_status") == "verified":
                try:
                    date = dt.date.fromisoformat(fact["value"])
                    stale = (analysis_date - date).days > 60 if key == "quote_date" else date < analysis_date
                    if key == "quote_date" and date > analysis_date:
                        stale = True
                    if stale:
                        open_issues.append(f"{offer['id']}/{key}: güncel teklif teyidi gerekli")
                except (ValueError, TypeError):
                    failures.append(f"{offer['id']}/{key}: doğrulanmış tarih ISO tarih olmalı.")
    costs = {}
    for offer in offers:
        payload = data.get("costs", {}).get(offer["id"])
        if payload is None:
            open_issues.append(f"{offer['id']}: karşılaştırılabilir maliyet girdisi yok")
            continue
        try:
            for event in payload.get('events', []):
                if event.get('known') is True:
                    for field in ('amount','currency','payment_date'):
                        fid=event.get('bindings',{}).get(field)
                        fact=facts.get(fid,{})
                        if fact.get('evidence_status')!='verified':
                            failures.append(f"{offer['id']}/{event.get('event_id')}/{field}: doğrulanmış olgu bağı yok.")
                            continue
                        expected, actual = fact.get('value'), event.get(field)
                        equal = as_decimal(expected,field)==as_decimal(actual,field) if field=='amount' else expected==actual
                        if not equal:
                            failures.append(f"{offer['id']}/{event.get('event_id')}/{field}: maliyet olguyla uyuşmuyor.")
                elif not event.get('fact_ids') or not set(event['fact_ids']).issubset(facts):
                    failures.append(f"{offer['id']}/{event.get('event_id')}: bilinmeyen maliyet kaynak olgusuna bağlı değil.")
            if not payload.get('assumption_sources'):
                failures.append(f"{offer['id']}: faiz/kur/değerleme günü dayanağı gerekli.")
            costs[offer["id"]] = cost_summary(payload)
            if costs[offer["id"]]["status"] != "complete_cost_inputs":
                open_issues.append(f"{offer['id']}: fiyatlanmamış maliyet var")
        except ValueError as error:
            failures.append(f"{offer['id']}: {error}")
    if len({o.get('supplier_id') for o in offers})>=2:
        bases={(p.get('base_currency'),p.get('base_date')) for p in data.get('costs',{}).values()}
        if len(bases)>1: failures.append('Karşılaştırılan maliyetlerde baz döviz/değerleme günü aynı olmalı.')
        if any(not currency for currency,_ in bases): open_issues.append('Ortak baz dövizli maliyet hesabı eksik.')
    if data.get('adjudication'):
        open_issues.extend('Çözülemeyen fark: '+d['difference_id'] for d in data['adjudication'].get('decisions',[]) if d.get('decision')=='open')
    scoring = None
    sensitivity=[]
    if data.get("scoring"):
        if len({o["supplier_id"] for o in offers}) < 2:
            failures.append("Tek bağımsız tedarikçi/alternatifleri puanlanamaz.")
        elif open_issues:
            failures.append("Maliyet/kritik bilgi açıkken kesin puan sıralaması üretilemez.")
        else:
            try:
                scoring_ids={s['supplier_id'] for s in data['scoring'].get('suppliers',[])}
                if scoring_ids!={o['supplier_id'] for o in offers}:
                    raise ValueError('Puanlama tüm ve yalnız mevcut bağımsız tedarikçileri kapsamalı.')
                rebound=bound_scoring(data,costs)
                for raw,bound in zip(data['scoring']['criteria'],rebound['criteria']):
                    if set(raw.get('values',{}))!=set(bound['values']) or any(as_decimal(raw['values'][s],'score')!=as_decimal(v,'bound score') for s,v in bound['values'].items()):
                        raise ValueError('Puanlama değerleri güncel kaynak/maliyetle uyuşmuyor.')
                for supplier in data['scoring']['suppliers']:
                    offer_ids={o['id'] for o in offers if o['supplier_id']==supplier['supplier_id']}
                    mandatory_fail=any(facts.get(f'{oid}/requirement/{rid}',{}).get('value')=='noncompliant' for oid in offer_ids for rid,r in reqs.items() if r.get('category')=='mandatory')
                    if mandatory_fail and supplier['eligible']:
                        raise ValueError('Zorunlu teknik uygunsuzluk puanlamadan önce eleme kapısına yansıtılmalı.')
                scoring = score_suppliers(data["scoring"])
                criteria=data['scoring']['criteria']
                if len(criteria)>=2:
                    scenarios=data['scoring'].get('sensitivity',[])
                    if not isinstance(scenarios,list) or len(scenarios)<2:
                        raise ValueError('Çok ölçütlü puanlamada bazın yanında en az iki açık ağırlık duyarlılık senaryosu gerekli.')
                    ids={c['criterion_id'] for c in criteria}; signatures={tuple(sorted((c['criterion_id'],as_decimal(c['weight'],'weight')) for c in criteria))}; names=set()
                    for scenario in scenarios:
                        if not scenario.get('id') or scenario['id'] in names or not scenario.get('label') or set(scenario.get('weights',{}))!=ids:
                            raise ValueError('Duyarlılık kimliği/adı/ağırlık kapsamı geçersiz.')
                        names.add(scenario['id']); signature=tuple(sorted((k,as_decimal(v,'sensitivity weight')) for k,v in scenario['weights'].items()))
                        if signature in signatures: raise ValueError('Duyarlılık senaryoları bazdan ve birbirinden farklı olmalı.')
                        signatures.add(signature); request=copy.deepcopy(data['scoring'])
                        for c in request['criteria']: c['weight']=scenario['weights'][c['criterion_id']]
                        sensitivity.append({'id':scenario['id'],'label':scenario['label'],'result':score_suppliers(request)})
            except ValueError as error:
                failures.append(str(error))
    return {"status": "FAIL" if failures else "PASS", "failures": failures, "open_issues": sorted(set(open_issues)),
            "costs": costs, "scoring": scoring, "sensitivity":sensitivity, "data_sha256": digest(data), "critical_fact_ids": sorted(f for f, v in facts.items() if v.get("critical"))}


def compare(data, blind):
    left, right = fact_map(data), fact_map(blind)
    diffs = []
    for fid in sorted(set(left) | set(right)):
        a, b = left.get(fid), right.get(fid)
        # Differing source excerpts remain visible; no model judgement is guessed by code.
        compare_fields = ("value", "evidence_status", "source_id", "location")
        if a is None or b is None or any(a.get(k) != b.get(k) for k in compare_fields):
            diffs.append({"difference_id": fid, "main": a, "independent": b})
    for index, note in enumerate(blind.get("free_notes", [])):
        diffs.append({"difference_id": f"free/{index}", "independent": note, "main": None})
    return {"schema": "teklif-diff/v4", "data_sha256": digest(data), "blind_sha256": digest(blind), "differences": diffs}


def apply_corrections(data, verdict, diff, sources):
    if verdict.get("data_sha256") != digest(data) or verdict.get("diff_sha256") != digest(diff):
        raise ValueError("Hakem kararı güncel veri/fark listesine bağlı değil.")
    decisions = verdict.get("decisions", [])
    expected = {d["difference_id"] for d in diff["differences"]}
    if len(decisions) != len(expected) or {d.get("difference_id") for d in decisions} != expected:
        raise ValueError("Her farka bir karar gerekli.")
    result = copy.deepcopy(data)
    mapped = fact_map(result)
    for d in decisions:
        if d.get("decision") not in {"main", "independent", "open"} or not d.get("reason"):
            raise ValueError("Hakem kararı/gerekçesi eksik.")
        if d["decision"] == "open":
            continue
        fact = d.get("replacement")
        difference=next(row for row in diff['differences'] if row['difference_id']==d['difference_id'])
        if d['decision']=='independent' and fact is None and not d['difference_id'].startswith('free/'):
            raise ValueError('Bağımsız bulgu seçildiğinde açık replacement olgusu gerekli.')
        if d['decision']=='main' and fact is None and difference.get('main') is None and not d['difference_id'].startswith('free/'):
            raise ValueError('Ana veride olmayan olgu düzeltmesiz kabul edilemez.')
        if fact is not None:
            if fact.get("fact_id") != d["difference_id"] or not evidence_ok(fact, sources):
                raise ValueError("Düzeltme özgün kaynağa bağlı değil.")
            mapped[fact["fact_id"]] = fact
    result["facts"] = list(mapped.values())
    # Rebuild each typed cost field from its canonical fact binding. No stale amount
    # can survive a sourced correction; the full engine and workbook rerun afterwards.
    for payload in result.get('costs',{}).values():
        for event in payload.get('events',[]):
            for field,fid in event.get('bindings',{}).items():
                if field not in {'amount','currency','payment_date'} or fid not in mapped:
                    raise ValueError('Maliyet düzeltme bağı geçersiz.')
                if mapped[fid].get('evidence_status')=='verified':
                    event[field]=copy.deepcopy(mapped[fid]['value'])
                else:
                    event['known']=False
                    event.setdefault('fact_ids',[]).append(fid)
    for offer in result.get('offers',[]):
        for line in offer.get('lines',[]):
            for field,fid in line.get('bindings',{}).items():
                if field not in {'quantity','unit_price','vat_rate','price_unit','price_includes_vat','discounts'} or fid not in mapped:
                    raise ValueError('Kalem düzeltme bağı geçersiz.')
                line[field]=copy.deepcopy(mapped[fid].get('value')) if mapped[fid].get('evidence_status')=='verified' else None
    if result.get('scoring'):
        computed={oid:cost_summary(payload) for oid,payload in result.get('costs',{}).items()}
        result['scoring']=bound_scoring(result,computed)
        mandatory={r['id'] for r in result.get('requirements',[]) if r.get('category')=='mandatory'}
        for supplier in result['scoring']['suppliers']:
            oids={o['id'] for o in result['offers'] if o['supplier_id']==supplier['supplier_id']}
            if any(mapped.get(f'{oid}/requirement/{rid}',{}).get('value')=='noncompliant' for oid in oids for rid in mandatory):
                supplier['eligible']=False
    result["adjudication"] = copy.deepcopy(verdict)
    # Fact corrections do not silently rewrite cost/offer structures. Derived records
    # must be revalidated and explicitly revised when a changed fact affects them.
    return result
