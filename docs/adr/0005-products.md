# 0005: Produktzuordnung und Repository-Metadaten

Jedes Produkt gehört genau einem Team. Seine Organisation wird ausschließlich
aus diesem Team abgeleitet; der Datenbankschlüssel verlangt ein existierendes
Owner-Team. Ein Teamwechsel ist nur innerhalb derselben Organisation erlaubt und
erfordert Bearbeitungsrechte auf beiden Teams. Der Organisationseigentümer darf
alle Produkte seiner Organisation verwalten; Teammitglieder sehen nur Produkte
ihrer Teams. Viewer lesen, Maintainer und Admins dürfen schreiben. Ein Team oder
eine Organisation mit Produkten kann erst nach deren Löschung oder Teamwechsel
entfernt werden.

Repository-Zuordnungen speichern pro Produkt einen Provider-Namen und einen
Repository-Bezeichner. Sie sind Metadaten, keine überprüfte Verbindung und keine
Credentials; Geheimnisse dürfen nicht als Bezeichner eingetragen werden. Die
Prüfung des Zugriffs und die echte Git-Anbindung folgen in #40. Ein Produkt kann
mehrere unterschiedliche Zuordnungen besitzen; gleiche Zuordnungen zu demselben
Produkt sind ausgeschlossen. Gelöschte Produkte verlieren ihre Zuordnungen.
