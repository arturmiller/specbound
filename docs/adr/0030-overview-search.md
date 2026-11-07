# ADR 0030: Übersicht und Suche über reale Daten

Die Organisationsübersicht zeigt gespeicherte Produkte, validierte Pack-
Revisionen und Findings. Die API begrenzt Produkte und Findings auf Teams,
für die der Nutzer Leserechte hat; Packs sind organisationsweit sichtbar und
werden nicht künstlich einem Team zugeordnet. Die Suche filtert die jeweils
geladenen Namen und Identifikatoren im Browser. Der Teamfilter gilt für Produkte
und Findings sowie Assessments; der Scope-Filter gilt für deren Environment-Werte.

Produkt- und Pack-Links wählen die zugehörige echte ID im vorhandenen Portal;
ein Finding führt zum Snapshot seines letzten Finding-Ereignisses und damit zum
revisionsgenauen Bericht. Die Übersicht wird beim Laden und über die Schaltfläche
„Aktualisieren“ neu abgefragt. Sie zeigt ausschließlich bereits gespeicherte
Ergebnisse und ersetzt keine automatische Freigabe oder Collector-Ausführung.
