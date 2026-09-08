# ADR-0031: Monorepo import, reviewed skill library and harness delivery

**Status:** Proposed · 2026-09-06 · konkretna propozycja na nowe wymagania właściciela; nie deklaracja wdrożenia.
**Proposes amendments to:** [ADR-0029](ADR-0029-product-focus-hard-rules.md), [ADR-0016](ADR-0016-knowledge-lifecycle-gates-and-layers.md), [ADR-0012](ADR-0012-nothing-generated-is-committed.md).
**Architecture:** [React + Go API + worker; assessment of NestJS](../PIVOT-ARCHITECTURE.md). **Review:** [five roles](../PIVOT-REVIEW.md).
**Specification:** [PRODUCT-PIVOT](../PRODUCT-PIVOT.md) · [proposed backlog](../PIVOT-BACKLOG.md).

## Context

Właściciel po negatywnym wyniku treningu E1 chce domknąć obietnice produktu przez import monorepo, ekstrakcję/enrichment po stronie serwera, adaptację SkillPyramid, UI organizacji i piramidy, telemetrię oraz instalowalne SEARCH/USE. To jawna zmiana zakresu względem wcześniejszego zamrożenia UI i lifecycle. Wynik modelu nie przesądza o wartości tych funkcji, ale ich wartość wymaga pilota.

W kodzie istnieją CLI, mapy scope, Go BM25F SEARCH/USE, snapshoty, ledger i authoring reports. Hosted auth, organizacje i pełny cykl import → review → publikacja nie są dowiedzioną gotową funkcją.

## Proposed decision

1. Produkt ma dostarczać organizacji wersjonowaną bibliotekę skilli ze źródłami, przeglądem zmian i obserwowalnym użyciem w harnessach. Własny model nie jest warunkiem wydania.
2. Dopuścić konkretny nowy zakres: React UI, WorkOS AuthKit, podstawowe org owner/member, bezpieczny import, jeden worker CPU, ekstrakcję/enrichment, propozycje konsolidacji i eksport zmian do Git.
3. Frontend: React/Vite. Backend: modularna aplikacja Go i osobny worker; bez mikroserwisów per use case. NestJS pozostaje alternatywą przy uzasadnionej przewadze kompetencji zespołu, bez automatycznego rewrite. Zachować jeden Postgres i obecny kształt T1; GCS na paczki/zasoby. Domyślny retrieval pozostaje BM25F, bez obowiązkowego GPU. Nie dodawać osobnej bazy grafowej ani platformy kolejkowej.
4. Repo tree, scope/ownership i warstwa wiedzy pozostają osobnymi osiami. Relacje są typowane, wersjonowane i walidowane przed publikacją.
5. Git pozostaje źródłem zatwierdzonych instrukcji. Chmura przechowuje kopie, propozycje i dowody. UI akceptuje propozycję do eksportu; aktywacja wygenerowanej instrukcji następuje po review/merge w Git i sync.
6. Uściślić ADR-0012: cache, snapshoty i mechanicznie wygenerowane pliki pozostają poza Git. Treść skilla wywodząca się z propozycji, oceniona i przyjęta przez człowieka, jest recenzowanym artefaktem źródłowym i może zostać zapisana w Git. Nie ma automatycznego commitu lub merge.
7. Dla MVP uprościć pełny cykl G0–G7 do draft → review/export → Git → published oraz needs_review/archive. Zachować owner review, provenance, walidację grafu i rollback; nie używać liczby loadów jako dowodu skuteczności lub automatycznej promocji.
8. Organizacje muszą być izolowane już w MVP. Zaawansowane ACL można odłożyć tylko przy jawnym modelu wspólnego dostępu członków organizacji.
9. Instalowalny skill i skrypt API są wspólne; native plugin opakowuje je tam, gdzie harness pozwala. Dwa adaptery są odebrane w realnych sesjach. Zdarzenia ekspozycji, load, reported, observed i feedback są oddzielne.
10. Zachować done = used, limit rozszerzania badań i go/no-go z realnego pilota. Nowe historie są przekładane na jeden backlog GitHub po przyjęciu zakresu; lokalne P01–P15 nie udają numerów issue.

## Consequences

- ADR-0029 pozostaje zapisem wcześniejszej zaakceptowanej decyzji; ta propozycja wskazuje dokładnie, co ją zmienia. Bez zatwierdzenia nie przestawiamy istniejących zadań implementacyjnych.
- Generowanie może zakończyć się brakiem użytecznej propozycji; produkt nadal importuje i dostarcza istniejące skille.
- Szybkie zobaczenie draftu w UI i publikacja do agentów są różnymi etapami. Git review dodaje tarcie, które mierzymy w pilocie.
- Multi-org i pakiety z zasobami wymagają pracy poza istniejącym single-tenant operatorem. To nie jest tylko frontend do obecnego API.
- Koszt auth w wybranym bezpłatnym zakresie jest oddzielny od kosztu infrastruktury, przechowywania i LLM.
- Harmonogram i AC w PRD są celami planistycznymi. Wyniki publikacji SkillPyramid nie są wynikami Guidefolda.

## Sources

[SkillPyramid v1](https://arxiv.org/html/2606.03692v1), [WorkOS pricing](https://workos.com/pricing), [current service](../../services/search/README.md), [harness contract](../HARNESS-SERVICE-CONTRACT.md), [telemetry contract](../SEARCH-USE-TELEMETRY.md).


## Delivery amendment after review

Wczesny Pilot Core przechodzi cały wąski przepływ przed kompletną betą. Zachowujemy cele partnera 20.09 i realnych sesji 04.10. Osiem tygodni to warunkowy budżet planistyczny, nie termin potwierdzony velocity. Oddzielamy Release AC, Quality Gates i Pilot Evidence. Pakiety/closure wymagają jawnego kontraktu 1.2; multi-org wymaga tożsamości per request i izolowanego cache. Zaufany Python builder pozostaje narzędziem workera, a API obrazem Go.
