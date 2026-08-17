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
Erwerbs- und Finanzierungsnebenkosten, Eigenkapital, Sollzins, Tilgung,
Zinsbindung, laufende Kosten und das Nettohaushaltseinkommen. Wer eine Zahl
aendert und das Skript erneut laufen laesst, bekommt ein vollstaendig neu
gerechnetes PDF – Tilgungsplan, Variantenvergleich und Haushaltsrechnung
inklusive.

Zwei Eigenheiten der Rechnung:

* **Konservativer Ansatz.** Unsichere Groessen sind am oberen Rand der
  plausiblen Spanne angesetzt. Abschnitt 9 des PDF weist offen aus, wo
  dadurch Puffer entsteht und wie stark die Rate faellt, wenn er aufgeht.
* **Fixpunkt beim Darlehen.** Grundschuldkosten und Bereitstellungszinsen
  bemessen sich am Darlehen, erhoehen es aber zugleich. `darlehensbedarf()`
  loest diese Rueckkopplung iterativ auf, statt sie zu ignorieren.

Das Ergebnis liegt als `Finanzierung_Waldburgstrasse_153b.pdf` bei – sechs
Seiten im Querformat, auf Tablet-Lektuere ausgelegt.
