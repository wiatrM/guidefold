from pathlib import Path
import re,json
base=Path('../pipeline-hifi'); css=(base/'src/tokens.css').read_text(); source=Path('../industrial-surveyor/src/styles.css').read_text()
original=dict(re.findall(r'(--[\w-]+)\s*:\s*([^;{}]+)',source)); groups=[
(('graphite','stone','steel','survey','safety','warning','signal','line'),'Paleta lub obrys istniejącego wzorca; zachowuje znaczenie stanu.'),
(('system','human','error'),'Istniejący kolor statusu przeniesiony do nazwanego tokenu tekstu/tła.'),
(('control-border',),'Steel wyraźniej oddziela aktywną kontrolkę od tła; próg 3:1.'),
(('font','weight','tracking'),'Jedna skala typograficzna nagłówków, tekstu i dokładnych identyfikatorów.'),
(('space',),'Odstępy siatki 8 px i jej połówki 4 px przy etykiecie.'),
(('border','radius'),'Geometria wzorca: obrys 1 px, promień 2 px.'),
(('focus',),'Widoczny obrys klawiatury oddzielony od granicy kontrolki.'),
(('row','control-height','touch'),'Balanced 40 px; kontrolka 44 px na telefonie dla dotyku.'),
(('icon','brand'),'Spójne rozmiary ikon regular i oryginalnego rastra znaku.'),
(('rail','shell','desktop','mobile','context','page','topbar'),'Stały rail na desktopie, kompaktowe disclosure na telefonie; kontekst org pozostaje widoczny.'),
(('two','aside','field','filter','steps','metric-columns'),'Responsywna liczba kolumn bez zmiany kolejności DOM.'),
(('table','source-disclosure'),'Minimalna czytelna szerokość tabeli i linku Source details; zamiast pojedynczych liter w kolumnie jest przewijanie poziome.'),
(('form','reading','source-width'),'Ograniczenie długości linii formularza, instrukcji i ścieżki.'),
(('text-area','body-editor','raw-max','scroll'),'Miejsce na edycję, przewijalny surowy plik i dojście do decyzji.'),
(('zero','full','viewport','min-page'),'Wspólne granice układu zamiast powtarzania rozmiarów w modułach.'),
(('gallery-width',),'Maksymalna szerokość developerskiej galerii; bez wpływu na siedem widoków U4.'),
(('grid-tile',),'Skala istniejącego rastra; nie tworzy nowej ilustracji.'),
(('duration','ease'),'Krótka zmiana stanu; reduced motion ustawia czas na zero.'),
(('disabled',),'Dodatkowy sygnał niedostępności obok disabled i opisu.'),
(('layer-skip','skip-hidden'),'Link pomijania nawigacji ponad interfejsem po focusie; ukryty wizualnie poza nim.')
]
entries=[]
for name,value in re.findall(r'(--[\w-]+)\s*:\s*([^;{}]+)',css):
 key=name[2:]; reason=next((r for keys,r in groups if any(key.startswith(k) for k in keys)),None)
 assert reason,name
 entries.append(dict(token=name,value=value.strip(),origin='copied named token' if original.get(name,'').strip()==value.strip() else 'new named token or responsive override',why=reason))
def rgb(h): return [int(h[i:i+2],16)/255 for i in (1,3,5)]
def lum(h):return sum(c*w for c,w in zip([x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb(h)],[.2126,.7152,.0722]))
def contrast(a,b):x,y=sorted([lum(a),lum(b)]);return round((y+.05)/(x+.05),2)
pairs=[('#e6e8ea','#0f1418','body',4.5),('#aeb8be','#0f1418','secondary',4.5),('#7bc6c2','#0f1418','system/link',4.5),('#ff9b6d','#0f1418','human label',4.5),('#ef8d8d','#0f1418','error',4.5),('#081014','#ff6a28','human button',4.5),('#677681','#081014','input border',3),('#677681','#0f1418','button border',3),('#ff6a28','#0f1418','focus',3)]
ratios=[dict(fg=a,bg=b,use=u,ratio=contrast(a,b),minimum=m,passed=contrast(a,b)>=m)for a,b,u,m in pairs]
out=base/'qa';out.mkdir(exist_ok=True)
(out/'token-provenance.json').write_text(json.dumps(dict(date='2026-09-06',source='../industrial-surveyor/src/styles.css',entries=entries,contrast=ratios),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(tokens=len(set(e['token'] for e in entries)),declarations=len(entries),contrast=ratios),indent=2))
