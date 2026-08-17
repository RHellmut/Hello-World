# Hello-World
Just another repository

Hello Humans,
i am about to learn GitHub

## Finanzierungsrechner

`immobilienfinanzierung.py` berechnet die Finanzierung der Eigentumswohnung
Waldburgstrasse 153b in Stuttgart-Vaihingen und erzeugt daraus ein PDF.

```bash
pip install reportlab
python3 immobilienfinanzierung.py
```

Alle Parameter stehen im Block `KONFIGURATION` am Kopf der Datei: Kaufpreis,
Nebenkostensaetze, Eigenkapital, Sollzins, Tilgung, Zinsbindung, Hausgeld und
das Nettohaushaltseinkommen. Wer eine Zahl aendert und das Skript erneut
laufen laesst, bekommt ein vollstaendig neu gerechnetes PDF – Tilgungsplan,
Variantenvergleich und Haushaltsrechnung inklusive.

Das Ergebnis liegt als `Finanzierung_Waldburgstrasse_153b.pdf` bei.
