# 0014: Produktanlage und Git-Verifikation

Die Produktoberfläche nutzt die vorhandene organisationsbezogene Produkt- und
Team-API. Ein Produkt wird zuerst mit einem Owner-Team gespeichert. Anschließend
kann ein GitHub-Repository zugeordnet und über die konfigurierte GitHub-App
gelesen werden. Die Produkt-ID bleibt in der URL, sodass die Detailansicht nach
einem Reload wieder geöffnet wird.

Die Repository-Verknüpfung wird vor der GitHub-Abfrage gespeichert. Scheitert
die Verifikation, zeigt die Oberfläche den Fehler und behält Produkt und
Verknüpfung für einen späteren erneuten Versuch. Eine erfolgreiche Prüfung
bestätigt den aktuellen Lesezugriff; ihr Ergebnis wird nicht dauerhaft als
Vertrauens- oder Freigabestatus gespeichert. Das Testsystem speist einen
Fixture-Git-Adapter nur innerhalb des isolierten E2E-Servers ein.
