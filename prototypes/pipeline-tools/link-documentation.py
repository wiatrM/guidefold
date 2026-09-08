from pathlib import Path
roles={
"PRODUCT-PIVOT.md":"Ten dokument określa wymagania i AC. Decyzje ekranów rozwija pipeline UI; nie zmienia on zakresu bez jawnej aktualizacji PRD.",
"PIVOT-ARCHITECTURE.md":"Ten dokument określa granice systemu. Plan frontendowy rozwija pipeline UI, a prototyp nie potwierdza wdrożenia API ani izolacji organizacji.",
"PIVOT-BACKLOG.md":"Ten dokument porządkuje zadania i zależności. Szczegółowe kryteria pozostają w PRD; ukończenie makiety nie oznacza ukończenia historii backendowej.",
"PIVOT-REVIEW.md":"Ten dokument zachowuje uzasadnienia i oceny agentów. Aktualny zakres odczytuj z PRD, a stan wykonania z kodu i dowodów QA."
}
for name,role in roles.items():
 p=Path("docs")/name;s=p.read_text()
 line="Reguły odczytu i aktualizacji: [DOCUMENTATION-RULES](DOCUMENTATION-RULES.md). "+role
 if line not in s:
  title,rest=s.split("\n",1);p.write_text(title+"\n\n"+line+"\n"+rest)
p=Path("docs/DOCUMENTATION-RULES.md");s=p.read_text().replace("| Kontekst sprzed pivotu |", "| Architektura informacji, UX i system wizualny |").replace("Zachowane zasady i jawnie oznaczone zastąpienia; nie odtwarzaj starych czterech sekcji.", "Dokumenty aktualizowane pod pivot; status na początku wskazuje zakres przeglądu. Historyczne różnice zapisuje brief; nie odtwarzaj starych czterech sekcji.").replace("maks.120 linii (brief40); README30", "maks. 120 linii (brief 40); README 30")
p.write_text(s)
