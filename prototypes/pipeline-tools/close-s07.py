from pathlib import Path
p=Path('../../docs/ui/pipeline/07-frontend.md');s=p.read_text().replace('Status: projekt implementacyjny, 2026-09-06; rundy Owner/Principal/Architekt w toku.','Status: plan po dwóch rundach, 2026-09-06; 0 otwartych P1/P2.')
s=s.replace('R2 — w toku; etap 8 nie rozpoczyna się przed 0 otwartych P1/P2.','R2 — Owner, Principal i Architekt: każdy 0/0/0; pięć P2 zamkniętych.\nWyjście: 0 otwartych P1/P2/P3; kompletność planu nie jest dowodem implementacji ani estymacji.')
p.write_text(s)
p=Path('../../docs/ui/UI.md');s=p.read_text().replace('§5 odsyła do planu etapu 7, obecnie w przeglądzie.','§5 odsyła do planu etapu 7 zamkniętego po dwóch rundach z 0 otwartych P1/P2.').replace('2026-09-06; formalne przeglądy w toku.','2026-09-06; dwie rundy Owner/Principal/Architekt zakończone, 0 otwartych P1/P2.');p.write_text(s)
