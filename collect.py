import json, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

CACHE=Path('site/data.json')
JST=timezone(timedelta(hours=9))
LAT,LON=35.7105,139.7746
def now(): return datetime.now(JST).isoformat()
def fetch(url, params=None, post=None):
    if params: url+='?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,data=post,headers={'User-Agent':'UenoDailyDashboard/1.0'})
    with urllib.request.urlopen(req,timeout=45) as f: return f.read(8*1024*1024)
def weather():
    p=dict(latitude=LAT,longitude=LON,timezone='Asia/Tokyo',forecast_days=2,current='temperature_2m,weather_code',hourly='temperature_2m,precipitation_probability,weather_code',daily='temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code')
    return json.loads(fetch('https://api.open-meteo.com/v1/forecast',p))
def food():
    q='[out:json][timeout:25];nwr["amenity"~"^(restaurant|cafe|fast_food|food_court)$"]["name"](35.702,139.768,35.718,139.780);out center;'
    errors=[]
    for endpoint in ('https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter'):
        try:
            raw=json.loads(fetch(endpoint,params={'data':q}))
            if not isinstance(raw.get('elements'),list) or raw.get('remark'):
                raise ValueError(raw.get('remark','Invalid Overpass response'))
            break
        except Exception as exc:
            errors.append(str(exc))
    else:
        raise RuntimeError('Overpass unavailable: '+'; '.join(errors))
    out=[]; seen=set()
    for e in raw['elements']:
        t=e.get('tags',{})
        if 'name' not in t or 'amenity' not in t: continue
        n=t.get('name:ja') or t['name']; loc=e.get('center',e); lat=loc.get('lat'); lon=loc.get('lon')
        if lat is None or lon is None or (n,round(lat,4),round(lon,4)) in seen: continue
        seen.add((n,round(lat,4),round(lon,4)))
        out.append(dict(name=n,cuisine=t.get('cuisine',''),category=t['amenity'],hours=t.get('opening_hours',''),lat=lat,lon=lon,url=f'https://www.openstreetmap.org/{e["type"]}/{e["id"]}'))
    out.sort(key=lambda x: (x['lat']-LAT)**2+(x['lon']-LON)**2*.66)
    return out
def news(local=False, query=None):
    p={'hl':'ja','gl':'JP','ceid':'JP:ja'}
    url='https://news.google.com/rss'
    if local or query: url+='/search';p['q']=query or '(上野 OR 御徒町 OR 台東区) when:7d'
    root=ET.fromstring(fetch(url,p));out=[]
    for i in root.findall('./channel/item')[:30]:
        title=i.findtext('title',''); link=i.findtext('link',''); source=i.findtext('source',''); date=i.findtext('pubDate','')
        if not link.startswith('https://'):continue
        try: date=parsedate_to_datetime(date).astimezone(JST).isoformat()
        except (ValueError,TypeError): pass
        if source and title.endswith(' - '+source):title=title[:-len(source)-3]
        out.append(dict(title=title,url=link,source=source,published=date))
    return out
def kev():
    errors=[]
    for endpoint in ('https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json','https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json'):
        try:
            entries=json.loads(fetch(endpoint))['vulnerabilities']
            if not isinstance(entries,list) or not entries: raise ValueError('Empty KEV catalog')
            return [dict(title=v['cveID']+' | '+v['vendorProject']+' '+v['product'],source='CISA KEV / 悪用確認済み',published=v['dateAdded'],url='https://www.cisa.gov/known-exploited-vulnerabilities-catalog',detail=v.get('requiredAction',''),ransomware=v.get('knownRansomwareCampaignUse','Unknown')) for v in sorted(entries,key=lambda v:v['dateAdded'],reverse=True)[:20]]
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError('; '.join(errors))
def jpcert():
    root=ET.fromstring(fetch('https://www.jpcert.or.jp/rss/jpcert.rdf'))
    out=[]
    for e in root.findall('.//{*}item'):
        title=e.findtext('{*}title',''); url=e.findtext('{*}link','')
        if title and url.startswith('https://'):
            out.append(dict(title=title,url=url,source='JPCERT/CC',published=e.findtext('{http://purl.org/dc/elements/1.1/}date','')))
    if not out: raise ValueError('Empty JPCERT feed')
    return out[:25]
SOURCES={'weather':weather,'food':food,'news':news,'local':lambda:news(True),'kev':kev,'jpcert':jpcert,'incident':lambda:news(query='(情報漏洩 OR 情報漏えい OR 不正アクセス OR ランサムウェア) when:7d'),'itnews':lambda:news(query='(Microsoft 365 OR AWS OR Oracle OR MySQL OR Tableau) (障害 OR 脆弱性 OR サポート終了 OR 仕様変更 OR 値上げ) when:7d')}
try: state=json.loads(CACHE.read_text(encoding='utf-8'))
except (OSError,ValueError): state={}
with ThreadPoolExecutor(max_workers=8) as pool:
    jobs={key:pool.submit(fn) for key,fn in SOURCES.items()}
    for key,job in jobs.items():
        try:
            state[key]={'data':job.result(),'updated':now(),'error':None}
            print(key,'OK')
        except Exception as e:
            state[key]={**state.get(key,{}),'error':str(e),'attempted':now()}
            print(key,'ERROR',str(e))
state['last_attempt']=now()
CACHE.parent.mkdir(parents=True,exist_ok=True)
temp=CACHE.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8');temp.replace(CACHE)
