# docs/reports/deploy

Przygotowania wydań produkcyjnych. **Żaden dokument w tym katalogu nie jest zgodą na wdrożenie
i żaden nie opisuje wykonanego kroku.** Zapis tego, co naprawdę zostało wdrożone, ma jedno
miejsce: [deploy/k8s/environments/cloudfloo-io/README.md](../../../deploy/k8s/environments/cloudfloo-io/README.md).
Produkcja jest zmieniana wyłącznie po jawnej zgodzie właściciela w bieżącej rozmowie
([CLAUDE.md](../../../CLAUDE.md), „Production is sacred").

| Dokument | Czego dotyczy | Status |
|---|---|---|
| [2026-09-15-release-prep](2026-09-15-release-prep.md) | Wydanie `main` @ `6d8e521` (PR #174, #176–#180): cztery digesty, DDL wobec działającego obrazu, Job migracji, patch digestów, smoke test, punkt rollbacku | PRZYGOTOWANE, NIEWYKONANE |
