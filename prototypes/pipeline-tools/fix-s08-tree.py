from pathlib import Path
p=Path('ui/src/components/ScopeTree/index.tsx'); s=p.read_text().replace("import type {ReactNode} from 'react';","import {useEffect,useRef,type ReactNode} from 'react';")
s=s.replace(" const contains=", """ const root=useRef<HTMLDivElement>(null);
 useEffect(()=>{
  let branch=root.current?.querySelector('[aria-current="true"]')?.closest('details');
  while(branch){branch.open=true;branch=branch.parentElement?.closest('details')||null;}
 },[selected]);
 const contains=""",1)
s=s.replace('<div className={css.tree} role=', '<div ref={root} className={css.tree} role=',1);p.write_text(s)
p=Path('ui/src/components/ScopeTree/ScopeTree.test.tsx'); s=p.read_text()
insert="""
 it('reopens a manually collapsed ancestor when selection changes within it',async()=>{
  const user=userEvent.setup();
  const siblings:TreeNode[]=[{id:'root',label:'Repository',children:[{id:'platform',label:'Platform',children:[
   {id:'a',label:'Source A',href:'/a'},{id:'b',label:'Source B',href:'/b'}
  ]}]}];
  const {rerender}=render(<MemoryRouter><ScopeTree label="Sources" selected="a" nodes={siblings}/></MemoryRouter>);
  const summary=screen.getByText('Platform').closest('summary')!;
  const branch=summary.parentElement as HTMLDetailsElement;
  await user.click(summary);expect(branch.open).toBe(false);
  rerender(<MemoryRouter><ScopeTree label="Sources" selected="b" nodes={siblings}/></MemoryRouter>);
  expect(branch.open).toBe(true);
  expect(screen.getByRole('link',{name:'Source B'})).toHaveAttribute('aria-current','true');
  await user.click(summary);expect(branch.open).toBe(false);
 });
"""
s=s.replace(" it('renders an unavailable",insert+" it('renders an unavailable");p.write_text(s)
p=Path('docs/ui/pipeline/08-components.md'); s=p.read_text()
s=s.replace('## Granica tras i danych',"""## Kandydaci do osobnego pakietu
ActionButton, Panel, StateBadge, RouteState, Tabs, Field, DataTable i MetricRow mogą być kandydatami do wspólnego pakietu UI, gdy drugi rzeczywisty konsument potwierdzi zgodne kontrakty. Dziś pozostają w ui/; sam ponowny import nie uzasadnia publikacji pakietu.
BrandMark pozostaje przy marce. Urn, ProvenanceTrail, ScopeTree, SkillContent i SkillDiff opisują odczyt instrukcji/źródeł Guidefold; ewentualny pakiet domenowy wymaga drugiego konsumenta i jawnych zależności Router/Markdown/typy, a nie sztucznej uniwersalizacji.
Routes, fixture adapter, formularz decyzji, lifecycle, sesja i eksport nie są kandydatami do biblioteki prezentacyjnej: zależą od konkretnego workflow i przyszłego Go API.

## Granica tras i danych""")
s=s.replace('Vitest / 14 plików | 42/42 PASS','Vitest / 15 plików | 45/45 PASS')
s=s.replace('640,04 kB / 172,56 kB','około 640 kB / 173 kB')
s=s.replace('F1–F9 mają implementację',"""Audyt przed R1 poprawił komunikat kopiowania po zmianie URN i dwa bezbarwne obrysy przeniesione do tokenu; dodano regresję późnego clipboard. R1 poprawia nieznane filtry URL (wartość i błąd pozostają widoczne, brak fałszywego zera) oraz ponowne otwarcie gałęzi dla nowego wyboru; normalny render galerii jest niezmieniony.
Nowe copy sprawdzone w kontekście przez odczyt tekstu: „Unavailable: {value}”, „This filter value is unavailable in this fixture. Choose a value or clear filters.”, „Filter unavailable”, „Resolve unavailable filters before reading the result count.” i „Choose an available value or clear filters. The requested value remains in the URL.”; tekst wskazuje problem, nie obiecuje wyników.
F1–F9 mają implementację""")
p.write_text(s)
