# Rollenreview des Portalentwurfs

Stand: 15.11.2026. Unabhängiger Agent mit frischem Kontext ohne Gesprächshistorie.
Gegenstand: `http://127.0.0.1:5173/prototype-oscal.html` und die zugehörige Ressourcenregistrierung.
Geprüft mit Chromium auf Desktop (1440 px) und Mobilgeräten (390 und 320 px).
Die beobachteten Befunde betreffen den UI-Entwurf und seine Modellierung, nicht die Sicherheit eines produktiven Systems.

## Wichtigste Befunde

### 1. Hoch – Einzelbewertungen sind nicht vollständig zugänglich

Rollen: Produktentwicklung, Auditor, Control Owner.

Die Prüfung nennt 14 Pakete. „Ergebnisse öffnen“ führt zu Anforderungen, wo das Lizenz-Control nur drei Paketbeobachtungen zeigt. Es fehlt eine Kennzeichnung als Auszug sowie ein Weg zu den weiteren Fällen, einschließlich des zweiten nicht freigegebenen Pakets.

Empfehlung: Unter dem aufgeklappten Control eine vollständige, filterbare Liste der Einzelbewertungen der gewählten Prüfung anbieten. Die Zusammenfassung muss zwischen Control-Ergebnis und Paketbewertungen unterscheiden. Dafür ist kein zusätzlicher Ergebnisse-Tab nötig.

Evidenz: [Prüfung, Bewertungen und Navigation](../../services/web/prototype-oscal.html:31).

### 2. Hoch – Der konkrete Bewertungs- und Nachweisstand ist noch nicht vollständig dargestellt

Rollen: Auditor, Security Engineer, Plattformbetrieb.

Produktcommit, Regelcommit und Lockfile sind verlinkt. Eine PyPI-Paketversionsseite ersetzt aber nicht den tatsächlich erhobenen und für die Bewertung verwendeten Evidenzinhalt. In diesem Zusammenhang fehlen Erhebungszeitpunkt, Integritätsmerkmale und die Auflösung der geltenden Profil-/Katalogquellen sowie des tatsächlichen Nachweiserzeugers.

Empfehlung: Beim Control einen zusammenhängenden Bewertungsstand zeigen: Prüfung, Produktrevision, Regel-/Profil-/Katalogrevisionen, referenzierte Nachweise und deren Erhebungszeit/Herkunft. Die Erzeugerversion benennen, soweit sie tatsächlich existiert; für den öffentlichen Lizenzscan keine Collector- oder Evidence-Pack-Herkunft erfinden.

Evidenz: [Technische Herkunft](../../services/web/prototype-oscal.html:8).

### 3. Mittel – Das geltende Profil ist im Produkt nicht nachvollziehbar verbunden

Rollen: Governance-/Control-Verantwortliche, Produktentwicklung, Datenschutz.

„Geltungsbereich“ zeigt vier zugeordnete Controls. Der Produktverweis auf `application-baseline@1.0.0` ist nur im Manifest sichtbar, dessen Katalogreferenz wiederum im Profilmanifest. Diese Quellen bilden im Portal noch keinen verbundenen fachlichen Weg.

Empfehlung: Im Produkt das geltende Profil mit Version und Herkunft anzeigen. Vom Profil zum Katalog und den ausgewählten Controls verlinken. Festlegen, ob „Zuordnung bearbeiten“ ein anderes Profil auswählt, das Profil verändert oder eine ausdrücklich modellierte Produktabweichung erzeugt. Bei As-Code-Konfiguration muss der Änderungsweg ins Repository erkennbar sein.

Evidenz: [Produkt- und Profilreferenzen](../../services/web/prototype-registry.js:3), [Geltungsbereich](../../services/web/prototype-oscal.html:28).

### 4. Mittel – Prüfungsauswahl verliert Tastaturfokus und offenen Zustand

Rollen: UX/Barrierefreiheit, alle Nutzerrollen.

Bei Änderung der Prüfung mit einer Pfeiltaste wird die Ansicht neu aufgebaut. Der Fokus fällt auf BODY, das nächste Tab beginnt wieder bei „Produkte“. Aufgeklappte Controls schließen sich.

Empfehlung: Fokus auf der Auswahl und geöffnete Control-Details erhalten; die Ergebnisänderung zugänglich ankündigen.

Evidenz: Browserbeobachtung und [Neurendern](../../services/web/prototype-oscal.html:32).

### 5. Mittel – Mobile Navigation und Manifestformular sind unvollständig lesbar

Rollen: UX/Barrierefreiheit.

Bei 390 px werden „Anforderungen“ und „Geltungsbereich“ abgeschnitten. Die Schema-URN in der Registrierung erzeugt horizontales Überlaufen: 415 px Dokumentbreite bei 390 px Viewport, 412 px bei 320 px.

Empfehlung: Vollständige Navigationsbezeichnungen ermöglichen und lange technische Kennungen umbrechen. Die Formulare bis 320 px prüfen.

Evidenz: [CSS](../../services/web/prototype-oscal.html:3), [Registrierungsformular](../../services/web/prototype-registry.js:59).

### 6. Niedrig – Statusfilter erzeugen einen unerklärten Leerzustand

Rollen: Produktentwicklung, Control Owner.

„Erfüllt“ und „Unklar“ entfernen alle Controls ohne Erklärung.

Empfehlung: „Keine Controls mit diesem Status in der ausgewählten Prüfung“ anzeigen und eine Filterzurücksetzung anbieten.

Evidenz: [Control-Filter](../../services/web/prototype-oscal.html:34).

## Einordnung nach Rollen

| Rolle | Entscheidende Frage | Aktueller Befund |
|---|---|---|
| Produktentwicklung | Was ist an meinem Produkt zu ändern? | Einzelbewertungen vollständig erschließen; produktbezogene Änderung und Regeländerung unterscheidbar machen. |
| Governance-/Control-Verantwortliche | Warum gelten diese Controls? | Profil, Version, Katalogherkunft und Änderungsweg sichtbar verbinden. |
| Auditor | Woraus folgt genau dieses Ergebnis? | Unverwechselbaren Bewertungsstand und konkrete Nachweise benötigen die Screens noch. |
| Security Engineer | Welche Prüfung läuft mit welchen Zugriffen? | Registrierung, Strukturprüfung und Ausführungsfreigabe als getrennte Zustände entwerfen. |
| Datenschutzbeauftragte | Welche Daten entstehen und wer kann sie sehen? | Vor tatsächlicher Erhebung Datenumfang, Zugriff und Aufbewahrung entscheiden; kein konkreter Compliance-Mangel am Beispiel nachgewiesen. |
| Plattformbetrieb | Welche Versionen werden tatsächlich verwendet? | Gewünschte Refs, aufgelöste Commits und Referenzauflösung im Ausführungsstand sichtbar machen. |
| UX/Barrierefreiheit | Kann ich den Ablauf zuverlässig bedienen? | Fokusverlust, abgeschnittene Navigation, horizontales Überlaufen und unklare Leerzustände beobachtet. |
| Evidence-Pack-Autor/-Maintainer | Passt mein Pack zu den Controls? | Benötigte und angebotene Capabilities sowie Ein-/Ausgabeverträge sollten nachvollziehbar verknüpft werden. |

Der Evidence-Pack-Maintainer ist eine sinnvolle zusätzliche Rolle neben Governance-Verantwortlichen, Plattformbetrieb und UX. Weitere allgemeine Compliance-Rollen würden für diesen Entwurfsstand wenig neue Einsichten liefern.

## Offene Ausführungsentscheidungen

Das Packmanifest zeigt Capability, Runtime und Schemapfade. Vor einer tatsächlichen Ausführung sollte der Startablauf die gelesenen Quellen, den Erhebungsumfang und die erforderlichen Berechtigungen erklären. Für personenbezogene Nachweise sind Zugriff, notwendiger Umfang und Aufbewahrung zu entscheiden. Diese Punkte sind offene Designentscheidungen, keine im Review belegten Sicherheitslücken oder Rechtsverstöße.

Die lokale Vorschauprüfung kennzeichnet ihre Grenzen bereits verständlich. Sie darf später nicht mit fachlicher Referenzprüfung oder einer Ausführungsfreigabe gleichgesetzt werden.

## Was funktioniert

- Produktquellen und Governance-Quellen sind getrennt dargestellt.
- Produkte und Profile haben explizite Referenzen im Manifest.
- Herkunftslinks sind an konkrete Revisionen gebunden.
- „Nicht erfüllt“ und „nicht bewertet“ sind unterscheidbar.
- Beispieldaten und die fehlende Speicherung werden offen benannt.
- Die Registrierung meldet ungültiges JSON und unzulässige relative Pfade verständlich.

## Empfohlene Reihenfolge

1. Vollständige Einzelbewertungen am Control zugänglich machen.
2. Den zusammenhängenden Bewertungs- und Nachweisstand entwerfen.
3. Profilherkunft und As-Code-Änderungsweg im Produkt integrieren.
4. Fokus und Interaktionszustand erhalten.
5. Mobile Navigation, Formularumbruch und Leerzustände korrigieren.

Der unabhängige Review hat keine Änderungen am Prototyp vorgenommen. Die Quellzeilen in der Befundaufnahme beziehen sich auf den damaligen Stand, vor der folgenden Überarbeitung.

## Umsetzung im Entwurf nach dem Review

Auf Wunsch des Nutzers wurde der Entwurf anschließend überarbeitet:

- Die Control-Ansicht zeigt sämtliche 14 Paketbewertungen des gespeicherten Scans mit Filter für 2 nicht freigegebene, 3 erfüllte und 9 unklare Fälle.
- Fünf gespeicherte Evidence-Datensätze wurden als lokale, statische Kopie aus dem vorhandenen Assessment übernommen. Die Ansicht zeigt Inhalt, Erhebungs- und Ablaufzeit, Metadatenquelle und Artefakt-/Metadaten-Hashes.
- Der Bewertungsstand zeigt die tatsächlichen Quellrevisionen. Nicht aufgezeichnete Profil-/Katalogstände und Erzeugerversionen bleiben ausdrücklich unbekannt; das heutige Entwurfsprofil wird nicht rückwirkend dem historischen Scan zugeschrieben.
- Produkt, aktuelles Entwurfsprofil und Katalog sind gegenseitig erreichbar. Der As-Code-Änderungsweg unterscheidet die Produktzuordnung von der gemeinsamen Profildefinition.
- Die Prüfungsauswahl erhält Tastaturfokus und geöffnete Control-Details. Filter ohne Treffer haben einen erklärten Leerzustand und eine Rücksetzfunktion.
- Die mobile Navigation zeigt vollständige Bezeichnungen. Formular und technische Kennungen passen in 390 und 320 Pixel Breite.

Die browserbasierte Überprüfung umfasste Paketanzahlen und Filter, sichtbare Nachweise, Fokus und offenen Zustand, Filterrücksetzung, Profil-/Katalognavigation und Direktlink-Reload sowie mobile Breiten. Die Änderungen betreffen den Prototyp; eine Repository-Registrierung oder Prüfung wird dadurch nicht tatsächlich ausgeführt.
