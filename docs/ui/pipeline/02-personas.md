# Persony zadaniowe
Data: 2026-09-06. Wejścia: [research §1](01-research.md), [brief](00-brief.md), [IA §2](../IA.md), [pivot §1 i §7](../../PRODUCT-PIVOT.md).
Wszystkie persony i zachowania poniżej są [założeniami], nie respondentami. Jedna osoba może wykonywać zadania kilku person; stanowisk autorów publicznych zgłoszeń nie znamy.
## 1. Dwa odkrycia
Uruchomiono niezależnie persona-miner A (od obserwacji R1–R7 do zadań) i persona-miner B (od awarii do odpowiedzialności za decyzję), oba ze świeżym kontekstem i tymi samymi wejściami.
| Różnica | Miner A | Miner B | Rozstrzygnięcie |
|---|---|---|---|
| Owner | Utrzymujący wspólne instrukcje | Rozstrzygający zakres zmiany | P1: owner instrukcji; utrzymanie to kontekst, decyzja o zmianie to zadanie UI. |
| Dev | Dobierający instrukcję do bieżącego zadania | Odszukujący brakującą instrukcję | P2: developer przy zadaniu; wejście nie wymaga wcześniejszej awarii. |
| Platform | Sprawdzający dostarczenie rewizji | Potwierdzający dostarczenie rewizji | P3: operator dostarczania; osobne zadanie, bez nowej roli uprawnień lub osobnej sekcji. |
| Sposób segmentacji | Utrzymanie kolekcji i użycie | Moment niepewności i decyzja | Zachowujemy oba: kontekst nie zastępuje pytania, które UI ma rozwiązać. |
## 2. Profile
| ID / rola [założenie] | Zadanie kluczowe | Narzędzia [założenie] | Moment wejścia [założenie] | Zniechęcenie w 5 minut [założenie] |
|---|---|---|---|---|
| P1 — Owner instrukcji; podstawowy użytkownik | Porównać źródło, proponowaną treść, zakres i dowód problemu; przyjąć do eksportu, poprawić lub odrzucić. | Git, pliki instrukcji; konkretny harness ustala pilot. | Proposals z linku lub po zmianie źródła; Usage & quality po negatywnym feedbacku → Skill/Proposals; Import przy pierwszym podłączeniu. | Brak źródła obok diffu, niejasne skutki, przymus akceptacji, eksport udający publikację. |
| P2 — Developer przy zadaniu; drugi użytkownik | Znaleźć instrukcję i sprawdzić jej zastosowanie w bieżącym module. | Terminal, repo, Copilot CLI lub Cursor jako odrębne obserwacje R3/R4, nie potwierdzony wspólny zestaw. | Skill z zachowanym repo/scope albo Library, gdy zna cel, ale nie nazwę. | Utrata filtrów, nieczytelny zakres, konieczność rozumienia kategorii agentów przed odczytem instrukcji. |
| P3 — Operator dostarczania; zadanie platformowe ownera | Sprawdzić, jaka rewizja jest opublikowana, a jaka ma dowód załadowania. | CLI, adapter/harness, źródło rewizji; Google Registry z R6 to przykład problemu, nie wymagana integracja. | Organization → Integrations przy instalacji; Skill/Usage przy weryfikacji. | Zielony status bez dowodu; Unknown zastąpione zerem; brak repo i scope połączenia. |
## 3. Dowody i obalenie
| Persona | Odwołania do research §1 | Co ją obali |
|---|---|---|
| P1 | R1, R2, R5 opisują utrzymanie/duplikaty; R7 jest wymaganiem produktu, nie dowodem konfliktu zakresu. | Przy dostępnych rzeczywistych zmianach lub negatywnym feedbacku nie występuje zadanie decyzji o treści/zakresie przypisane ownerowi. Brak zdarzeń jest nierozstrzygnięty. Czas UI → Git testuje osobno wartość interfejsu, nie istnienie roli. |
| P2 | R3 to pytanie o zastosowanie; R4 opisuje root/podfolder. Nie znamy częstości potrzeby UI. | Przy rzeczywistych zadaniach uczestnicy znajdują wystarczającą odpowiedź w harnessie; źródło/scope w UI nie wspiera decyzji. |
| P3 | R6 to prośba o rozróżnienie rewizji; R4/R7 uzupełniają kontekst i wymagania. | Istniejący proces dostarcza wystarczający dowód, a dodatkowe rozróżnienie w UI nie zmienia diagnozy lub działania przy realnej rozbieżności. |
## 4. Role IA
P1 mapuje się na owner, P2 na dev, P3 na platform jako zadanie ownera. Usuwamy personę ML z zakresu U4 zgodnie z briefem, nie jako wniosek z badania.
Persona nie nadaje uprawnień: API rozstrzyga owner/member. Developer będący member może czytać i zgłaszać feedback; import, decyzje publikacji i zarządzanie org wymagają ownera (pivot §6).
[założenie] Trzy profile wystarczają do pierwszej iteracji. Obali to pilot, jeśli ujawni odrębne zadanie U4 z innymi dowodami lub kryterium decyzji, którego profile nie obejmują.
## Przegląd
R1: Owner + Badacz UX; P1=0/P2=1/P3=0 (unikalne). Dodano powrót ownera po feedbacku i dowód problemu.
R2: Owner + Badacz UX; otwarte P1=0/P2=0/P3=0. Oddzielono rolę od wartości UI; etap zamknięty, 2026-09-06.
