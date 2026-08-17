# Hello-World
Just another repository

Hello Humans,
i am about to learn GitHub

## Finanzierungsrechner

`immobilienfinanzierung.py` berechnet die Finanzierung einer Eigentumswohnung
und erzeugt daraus ein PDF. Hinterlegt sind zwei Objekte in
Stuttgart-Vaihingen:

```bash
pip install reportlab
python3 immobilienfinanzierung.py waldburgstrasse   # Neubau, 795.000 EUR
python3 immobilienfinanzierung.py viereichenweg     # Bestand, 370.000 EUR
```

Weitere Objekte kommen als zusaetzlicher Eintrag in das Dictionary `OBJEKTE`
am Kopf der Datei. Dort steht alles Objektspezifische: Kaufpreis, Provision,
Hausgeld, Grundsteuer und der Ansatz fuer die Instandhaltungsruecklage.

Die uebrigen Parameter im Block `KONFIGURATION` gelten fuer alle Objekte:
Nebenkostensaetze, Eigenkapital, Sollzins, Tilgung, Zinsbindung und das
Nettohaushaltseinkommen. Wer eine Zahl aendert und das Skript erneut laufen
laesst, bekommt ein vollstaendig neu gerechnetes PDF – Tilgungsplan,
Variantenvergleich und Haushaltsrechnung inklusive.

Zwei Eigenheiten der Rechnung:

* **Konservativer Ansatz.** Unsichere Groessen sind am oberen Rand der
  plausiblen Spanne angesetzt. Abschnitt 9 des PDF weist offen aus, wo
  dadurch Puffer entsteht und wie stark die Rate faellt, wenn er aufgeht.
* **Fixpunkt beim Darlehen.** Grundschuldkosten und Bereitstellungszinsen
  bemessen sich am Darlehen, erhoehen es aber zugleich. `darlehensbedarf()`
  loest diese Rueckkopplung iterativ auf, statt sie zu ignorieren.

Die Ergebnisse liegen als `Finanzierung_Waldburgstrasse_153b.pdf` und
`Finanzierung_Viereichenweg_31.pdf` bei – je sechs Seiten im Querformat,
auf Tablet-Lektuere ausgelegt.
