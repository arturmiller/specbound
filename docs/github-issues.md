# Designboard auf GitHub

Die vorhandene Hierarchie wurde unverändert übertragen: 10 Epics, 17 Features, 49 Tasks.

Quelle: [Roadmap](https://github.com/arturmiller/specbound/blob/1727aabf895e8a91ada7a5e00258b479c6fdaddb/designboard/data/roadmap.json).

Elternbeziehungen und Task-Abhängigkeiten sind als native GitHub-Verknüpfungen sowie im Beschreibungstext hinterlegt. Die JSON-Zuordnung in `github-issues.json` enthält die stabilen Board-IDs. Die GitHub-Issues enthalten den aktuellen lokalen Docker-Compose-Umfang; das ursprüngliche Designboard bleibt ein historischer Plan. T046 und T047 sind zurückgestellt. Dies ist ein Veröffentlichungsstand, keine laufende Synchronisierung von Status oder Browser-Markierungen.

| Board-ID | GitHub-Issue | Ebene | Parent |
| --- | --- | --- | --- |
| E01 | [#1 Lauffähiger Kern](https://github.com/arturmiller/specbound/issues/1) | epic | — |
| F01 | [#11 Repository und Startumgebung](https://github.com/arturmiller/specbound/issues/11) | feature | E01 |
| T001 | [#28 Projektstruktur anlegen](https://github.com/arturmiller/specbound/issues/28) | task | F01 |
| T002 | [#29 PostgreSQL-Migrationen einführen](https://github.com/arturmiller/specbound/issues/29) | task | F01 |
| T003 | [#30 CI-Grundchecks](https://github.com/arturmiller/specbound/issues/30) | task | F01 |
| F02 | [#12 Stabile Kernverträge](https://github.com/arturmiller/specbound/issues/12) | feature | E01 |
| T004 | [#31 Schema für Subject/Fact/Evidence](https://github.com/arturmiller/specbound/issues/31) | task | F02 |
| T005 | [#32 Assessment-Zustände definieren](https://github.com/arturmiller/specbound/issues/32) | task | F02 |
| E02 | [#2 Organisation, Teams und Identitäten](https://github.com/arturmiller/specbound/issues/2) | epic | — |
| F03 | [#13 Organisation und Teams](https://github.com/arturmiller/specbound/issues/13) | feature | E02 |
| T006 | [#33 Organisationen und Teams persistieren](https://github.com/arturmiller/specbound/issues/33) | task | F03 |
| T007 | [#34 Team-Rollen prüfen](https://github.com/arturmiller/specbound/issues/34) | task | F03 |
| T008 | [#35 Teamoberflächen integrieren](https://github.com/arturmiller/specbound/issues/35) | task | F03 |
| F04 | [#14 Menschliche und nichtmenschliche Accounts](https://github.com/arturmiller/specbound/issues/14) | feature | E02 |
| T009 | [#36 OIDC-Login und Principal-Modell](https://github.com/arturmiller/specbound/issues/36) | task | F04 |
| T010 | [#37 Agent-Identitäten und Mitgliedschaft](https://github.com/arturmiller/specbound/issues/37) | task | F04 |
| T011 | [#38 Rechtebegrenzung für Agenten](https://github.com/arturmiller/specbound/issues/38) | task | F04 |
| E03 | [#3 Git-Anbindung und Pack Releases](https://github.com/arturmiller/specbound/issues/3) | epic | — |
| F05 | [#15 Git-Quellen](https://github.com/arturmiller/specbound/issues/15) | feature | E03 |
| T012 | [#39 Git-Source-Port definieren](https://github.com/arturmiller/specbound/issues/39) | task | F05 |
| T013 | [#40 GitHub App read-only anschließen](https://github.com/arturmiller/specbound/issues/40) | task | F05 |
| T014 | [#41 Git-Tag auf Commit pinnen](https://github.com/arturmiller/specbound/issues/41) | task | F05 |
| F06 | [#16 Pack importieren](https://github.com/arturmiller/specbound/issues/16) | feature | E03 |
| T015 | [#42 Governance Pack Manifest validieren](https://github.com/arturmiller/specbound/issues/42) | task | F06 |
| T016 | [#43 Evidence Pack Manifest validieren](https://github.com/arturmiller/specbound/issues/43) | task | F06 |
| T017 | [#44 Pack-Katalog-API und UI](https://github.com/arturmiller/specbound/issues/44) | task | F06 |
| E04 | [#4 Produkte und Discovery](https://github.com/arturmiller/specbound/issues/4) | epic | — |
| F07 | [#17 Produktinventar](https://github.com/arturmiller/specbound/issues/17) | feature | E04 |
| T018 | [#45 Produkt-Datenmodell und CRUD](https://github.com/arturmiller/specbound/issues/45) | task | F07 |
| T019 | [#46 Produkt-Anlage UI](https://github.com/arturmiller/specbound/issues/46) | task | F07 |
| F08 | [#18 Erste technische Fakten](https://github.com/arturmiller/specbound/issues/18) | feature | E04 |
| T020 | [#47 OpenAPI Scanner](https://github.com/arturmiller/specbound/issues/47) | task | F08 |
| T021 | [#48 Discovery-Vollständigkeit erfassen](https://github.com/arturmiller/specbound/issues/48) | task | F08 |
| E05 | [#5 Evidence-Laufzeit und Vertrauen](https://github.com/arturmiller/specbound/issues/5) | epic | — |
| F09 | [#19 Ausführungsprotokoll](https://github.com/arturmiller/specbound/issues/19) | feature | E05 |
| T022 | [#49 Collector Request/Response definieren](https://github.com/arturmiller/specbound/issues/49) | task | F09 |
| T023 | [#50 Einen kontrollierten Collector ausführen](https://github.com/arturmiller/specbound/issues/50) | task | F09 |
| T024 | [#51 Credentials und Zugriffsgrenzen](https://github.com/arturmiller/specbound/issues/51) | task | F09 |
| T025 | [#52 Evidence Records speichern](https://github.com/arturmiller/specbound/issues/52) | task | F09 |
| F10 | [#20 Beispielprovider als eigenes Repo](https://github.com/arturmiller/specbound/issues/20) | feature | E05 |
| T026 | [#53 Minimalen Beispielprovider veröffentlichen](https://github.com/arturmiller/specbound/issues/53) | task | F10 |
| T027 | [#54 Infrastrukturabfrage als Provider-Beispiel dokumentieren](https://github.com/arturmiller/specbound/issues/54) | task | F10 |
| E06 | [#6 Deterministische Kontrolle und Evidence](https://github.com/arturmiller/specbound/issues/6) | epic | — |
| F11 | [#21 Matching & Evaluation](https://github.com/arturmiller/specbound/issues/21) | feature | E06 |
| T028 | [#55 Geltungsbereich ermitteln](https://github.com/arturmiller/specbound/issues/55) | task | F11 |
| T029 | [#56 Kontrollen regelbasiert bewerten](https://github.com/arturmiller/specbound/issues/56) | task | F11 |
| T030 | [#57 Nachweise deduplizieren](https://github.com/arturmiller/specbound/issues/57) | task | F11 |
| F12 | [#22 Findings und Revisionen](https://github.com/arturmiller/specbound/issues/22) | feature | E06 |
| T031 | [#58 Assessment-Snapshot modellieren](https://github.com/arturmiller/specbound/issues/58) | task | F12 |
| T032 | [#59 Finding-Upsert und Lifecycle](https://github.com/arturmiller/specbound/issues/59) | task | F12 |
| E07 | [#7 PR-Feedback ohne Agentensteuerung](https://github.com/arturmiller/specbound/issues/7) | epic | — |
| F13 | [#23 Webhook-Lifecycle](https://github.com/arturmiller/specbound/issues/23) | feature | E07 |
| T033 | [#60 PR-Events aufnehmen](https://github.com/arturmiller/specbound/issues/60) | task | F13 |
| T034 | [#61 Worker-Queue auf PostgreSQL](https://github.com/arturmiller/specbound/issues/61) | task | F13 |
| F14 | [#24 GitHub Kommentar und Statuscheck](https://github.com/arturmiller/specbound/issues/24) | feature | E07 |
| T035 | [#62 Einzelnen PR-Kommentar upserten](https://github.com/arturmiller/specbound/issues/62) | task | F14 |
| T036 | [#63 Commit-genauen Check setzen](https://github.com/arturmiller/specbound/issues/63) | task | F14 |
| T037 | [#64 PR-Bericht im Portal anzeigen](https://github.com/arturmiller/specbound/issues/64) | task | F14 |
| E08 | [#8 Bestandsfindings & Regeländerungen](https://github.com/arturmiller/specbound/issues/8) | epic | — |
| F15 | [#25 Baseline-Kontrollen](https://github.com/arturmiller/specbound/issues/25) | feature | E08 |
| T038 | [#65 Deployment-Identität speichern](https://github.com/arturmiller/specbound/issues/65) | task | F15 |
| T039 | [#66 Baseline per API und Zeitplan anstoßen](https://github.com/arturmiller/specbound/issues/66) | task | F15 |
| T040 | [#67 Geänderte Packs simulieren](https://github.com/arturmiller/specbound/issues/67) | task | F15 |
| T041 | [#68 Aktivierung & Reassessment](https://github.com/arturmiller/specbound/issues/68) | task | F15 |
| E09 | [#9 Portal & Dokumentation](https://github.com/arturmiller/specbound/issues/9) | epic | — |
| F16 | [#26 UX über reale APIs](https://github.com/arturmiller/specbound/issues/26) | feature | E09 |
| T042 | [#69 Übersicht und Suche](https://github.com/arturmiller/specbound/issues/69) | task | F16 |
| T043 | [#70 Docs-Informationsarchitektur](https://github.com/arturmiller/specbound/issues/70) | task | F16 |
| T044 | [#71 Unbekannte Zustände sichtbar machen](https://github.com/arturmiller/specbound/issues/71) | task | F16 |
| E10 | [#10 Lokaler Betrieb mit Docker Compose](https://github.com/arturmiller/specbound/issues/10) | epic | — |
| F17 | [#27 Lokale Auslieferung mit Docker Compose](https://github.com/arturmiller/specbound/issues/27) | feature | E10 |
| T045 | [#72 Images für den lokalen Compose-Betrieb bauen](https://github.com/arturmiller/specbound/issues/72) | task | F17 |
| T046 | [#73 Helm-Chart für Kubernetes](https://github.com/arturmiller/specbound/issues/73) | task | F17 |
| T047 | [#74 AWS ECS-Deployment als Adapter](https://github.com/arturmiller/specbound/issues/74) | task | F17 |
| T048 | [#75 Storage-Port und lokales Objektbackend](https://github.com/arturmiller/specbound/issues/75) | task | F17 |
| T049 | [#76 Operatives Monitoring und Recovery](https://github.com/arturmiller/specbound/issues/76) | task | F17 |
