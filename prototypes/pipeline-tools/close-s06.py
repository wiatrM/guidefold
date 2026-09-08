from pathlib import Path
p=Path('../../docs/ui/pipeline/06-ux-ui.md');s=p.read_text().replace('Status: implementacja i audyt ukończone, 2026-09-06; formalne rundy w toku.','Status: zamknięty, 2026-09-06; 0 otwartych P1/P2 po R3.')
s=s[:s.index('## Przegląd')]+"""## Przegląd
R1 — Owner: 0/0/0; Designer: P1=0/P2=1/P3=2. Naprawiono tabele, mobilny commit i pierwszy wynik poniżej folda.
R2 — Owner i Designer: P1=0/P2=1/P3=0 każdy; jedno wspólne znalezisko: test mierzył Panel zamiast kontenera przewijania.
R3 — obaj: 0/0/0; poprawiony selektor potwierdza 7/7 potrzebnych przewinięć klawiaturą, 2 przypadki bez potrzeby scrolla.
Wyjście: 0 otwartych P1/P2/P3; trzy rundy z powodu P2 w R2. Przeglądy syntetyczne, bez zaliczenia U4 AC5.
"""
p.write_text(s)
p=Path('../pipeline-hifi/design-qa.md');s=p.read_text().replace('Status: audyt ukończony; formalna runda 2 w toku, 2026-09-06.','Status: audyt i przeglądy ukończone, 2026-09-06; brak otwartych znalezisk.')
s=s.replace('R2 Owner i Designer: oczekuje na końcową weryfikację.','R2 Owner i Designer: wspólne P2 — test wybierał nazwany Panel zamiast kontenera DataTable.\nR3: poprawiony selector i raport potwierdzają 7 realnych przewinięć ArrowRight, 2 przypadki bez potrzeby scrolla; obaj recenzenci P1=0/P2=0/P3=0.')
s=s.replace('Final result: blocked','Final result: passed');p.write_text(s)
p=Path('../../docs/ui/UI.md');s=p.read_text().replace('build, screenshoty, kontrast i axe potwierdzone; dwa formalne przeglądy etapu 6 w toku.','build, screenshoty, kontrast i axe potwierdzone; etap 6 zamknięty po trzech rundach z 0 otwartych P1/P2.').replace('Formalne przeglądy pozostają otwarte;','Formalne przeglądy zamknięte;');p.write_text(s)
p=Path('../../docs/ui/UX.md');s=p.read_text().replace('Hi-fi etapu 6 ma potwierdzony build i audyt przeglądarkowy; formalne przeglądy w toku.','Hi-fi etapu 6 ma potwierdzony build i audyt przeglądarkowy; formalne przeglądy zamknięte z 0 otwartych P1/P2.');p.write_text(s)
