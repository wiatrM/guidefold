# Przegląd pivotu przez agentów: decyzje i poprawki

Reguły odczytu i aktualizacji: [DOCUMENTATION-RULES](DOCUMENTATION-RULES.md). Ten dokument zachowuje uzasadnienia i oceny agentów. Aktualny zakres odczytuj z PRD, a stan wykonania z kodu i dowodów QA.

**2026-09-06.** Pięć perspektyw agentowych na prośbę właściciela: CTO, CEO, Business/Product Manager, marketing i research. To recenzje dokumentów, kodu i źródeł; nie opinie rzeczywistych klientów ani zastępstwo badania popytu. Implementacji produktu nie uruchomiono.

## Werdykt

Warunkowe GO dla kierunku. Pierwszy etap ma pokazać pełny wąski przepływ u użytkownika, przed inwestycją w kompletną betę. React jest decyzją właściciela; rekomendacja backendu to Go z osobnym workerem, bez mikroserwisów na każdy use case.

| Perspektywa | Najważniejszy problem | Przyjęta poprawka |
|---|---|---|
| CEO | Osiem tygodni budowy przed dowodem powrotów/buyera | Wczesny Pilot Core, cele 20.09/04.10, finansowanie etapami, rozmowa zakupowa przed końcem pilota |
| CTO | Multi-org, pakiety i closure wymagają przebudowy kontraktów | Wczesne bramki izolacji/cache, wersjonowany kontrakt 1.2, manifest zasobów, kanoniczny builder w workerze |
| Business/Product Manager | Mapa nie oznacza aktywacji; AC mieszają kod z wartością | Aktywacja ownera/zespołu, R/Q/P, prostszy roundtrip przez Git, osobne Core i beta |
| Marketing | Katalog i statystyki istnieją u vendorów | Obietnica zatwierdzonych instrukcji z repo, rzeczywiste dostarczenie i decyzja ownera; demo onboarding → drift → CI |
| Research | Mała próbka, leakage i graf mogą dać fałszywy sukces | Rubryki per operacja, holdout, abstention, typy relacji, osobny eksperyment ludzi/agentów i retencja dowodów |

## Rozstrzygnięcia

- Pełny kierunek użytkownika zostaje: scan, cloud extraction/enrichment, piramida, org UI/auth, telemetria i instalowalne SEARCH/USE. Pilot ogranicza wolumen oraz liczbę wariantów, nie usuwa tych obietnic.
- Jeden harness uruchamia pierwszą pełną ścieżkę; drugi jest wcześnie sprawdzany technicznie i wymagany do kompletnej bety. Nie odkładamy ryzyka integracji na tygodnie 5–6.
- Istniejące zatwierdzone skille nie czekają na generowanie ani nowy workflow propozycji. Marketing sugerował odsunięcie konsolidacji; zachowujemy mały przykład w Core z uwagi na wyraźne wymaganie właściciela, a wolumen rozszerzamy po ocenie.
- Git pozostaje kanoniczny. UI przygotowuje propozycję; nie wymagamy dwóch pełnych review identycznej treści. Bez integracji hosta Git jawnie zapisujemy deklarację uprawnionego operatora zamiast udawać weryfikację merge.
- Publikacja i review to oddzielne stany. Akceptacja propozycji nie jest dowodem poprawy zadania. Liczba krawędzi, skilli albo loadów nie jest sukcesem produktu.
- Wszystkie pięć dodatkowych zastosowań jest opisanych z wymaganiami/AC, lecz używają wspólnych modułów i mają różne role w pilocie.
- Statystyka helped zachowuje mianownik z istniejącego kontraktu; mixed pokazujemy osobno.
- 24/30 zostaje wskaźnikiem diagnostycznym, nie obietnicą 80% jakości; rozszerzenie generowania wymaga niezależnej oceny.
- Zamiana backendu na NestJS jest możliwa, ale nie ma obecnie dowodu przewagi nad rozbudową Go. TypeScript może uzasadnić wybór przy rzeczywistej przewadze kompetencji zespołu; na dziś nie robimy rewrite ani dodatkowego BFF.
- Mikroserwisy wydzielamy według obciążenia i odpowiedzialności danych. API oraz worker mają osobne procesy; onboarding, piramida i drift nie dostają osobnych usług.
- Zaawansowane ACL/SSO są później. Izolacja organizacji i jawny model wspólnego dostępu członków są wymagane od pierwszego pilota.

## Poprawki w dokumentach

- [PRD](PRODUCT-PIVOT.md): wszystkie funkcje i AC, aktywacja, kwalifikacja partnera, publikacja, budżety, retencja, wczesne bramki, plan ewaluacji.
- [Architektura](PIVOT-ARCHITECTURE.md): React/Go/NestJS, moduły, procesy, API–worker i warunki wydzielania usług.
- [Backlog](PIVOT-BACKLOG.md): zależności dla istniejących i nowych skilli, etap Core i rozszerzenia, mapowanie do historycznych epiców.
- [ADR-0031](adr/ADR-0031-monorepo-to-managed-skill-library.md): proponowana zmiana wcześniejszego freeze i uproszczenie lifecycle.
- Wcześniejsze plany otrzymują widoczne odsyłacze. Błędne porównanie SkillPyramid z płaską biblioteką w ADR-0016 jest korygowane jako korekta źródła, bez zmiany historycznego statusu decyzji.

## Co nadal wymaga danych, a nie kolejnego agenta

Partner i dopuszczony zakres danych, owner z czasem na review, osoba decyzyjna zakupowo, dostępność inżynierów Go/TS, realne koszty LLM/obsługi oraz wynik używania. Nie wymyślamy tych odpowiedzi. Brak danych nie blokuje przygotowania specyfikacji, ale ogranicza obietnice terminu, ceny i wartości.

