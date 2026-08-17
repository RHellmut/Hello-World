#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Finanzierungsrechner Eigentumswohnung Stuttgart-Vaihingen, Waldburgstrasse 153b.

Berechnet die monatliche Annuitaet an die Bank, die laufende Gesamtbelastung
und den Tilgungsplan ueber die Zinsbindung. Erzeugt daraus ein PDF.

Alle Stellschrauben stehen im Konfigurationsblock KONFIGURATION weiter unten.
Aendert sich z. B. der Zinssatz, genuegt eine Zeile und ein erneuter Lauf:

    python3 immobilienfinanzierung.py
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# ═══════════════════════════════════════════════════════════════════════════
#  KONFIGURATION - hier alle Parameter anpassen
# ═══════════════════════════════════════════════════════════════════════════

# --- Objekt -------------------------------------------------------------
OBJEKT_ADRESSE = "Waldburgstrasse 153b, 70563 Stuttgart-Vaihingen"
OBJEKT_BESCHREIBUNG = "4 Zimmer, Erdgeschoss, Terrasse und Garten"
WOHNFLAECHE_QM = 93.0
GARTENFLAECHE_QM = 191.0
ENERGIESTANDARD = "Effizienzhaus 55 EE"

# --- Kaufpreis ----------------------------------------------------------
KAUFPREIS_WOHNUNG = 795_000.0        # inkl. Einbaukueche
KAUFPREIS_STELLPLATZ = 32_500.0      # Tiefgaragen-Stellplatz

# --- Kaufnebenkosten ----------------------------------------------------
GRUNDERWERBSTEUER_SATZ = 0.050       # Baden-Wuerttemberg
NOTAR_GRUNDBUCH_SATZ = 0.020         # Notar und Grundbuchamt
MAKLERPROVISION_SATZ = 0.000         # laut Expose keine Kaeuferprovision

# --- Finanzierung -------------------------------------------------------
EIGENKAPITAL = 400_000.0
SOLLZINS = 0.0410                    # nominaler Sollzins p. a.
ANFANGSTILGUNG = 0.0300              # anfaenglicher Tilgungssatz p. a.
ZINSBINDUNG_JAHRE = 20
SONDERTILGUNG_JAHR = 0.0             # bewusst ohne Sondertilgung gerechnet

# --- Laufende Kosten ----------------------------------------------------
HAUSGELD_MONAT = 346.0               # laut Expose
GRUNDSTEUER_JAHR = 600.0             # Schaetzung, siehe Hinweis im PDF
RUECKLAGE_SONDEREIGENTUM_QM = 1.0    # EUR je qm und Monat

# --- Haushaltsrechnung --------------------------------------------------
# Monatliches Nettohaushaltseinkommen. None => es werden nur die
# Schwellenwerte ausgewiesen, ohne konkrete Belastungsquote.
NETTOEINKOMMEN_MONAT = None

# --- Vergleichsszenarien ------------------------------------------------
TILGUNGSVARIANTEN = [0.020, 0.025, 0.030, 0.035, 0.040]

# --- Ausgabe ------------------------------------------------------------
PDF_DATEI = "Finanzierung_Waldburgstrasse_153b.pdf"
STAND = "17. August 2026"

# ═══════════════════════════════════════════════════════════════════════════
#  RECHENKERN
# ═══════════════════════════════════════════════════════════════════════════


def annuitaet_monatlich(darlehen, zins, tilgung):
    """Monatliche Rate aus Darlehenshoehe, Sollzins und Anfangstilgung."""
    return darlehen * (zins + tilgung) / 12.0


def tilgungsverlauf(darlehen, zins, rate, sondertilgung=0.0, max_monate=1200):
    """Monatsgenauer Tilgungsverlauf.

    Liefert eine Liste von Monatsdatensaetzen. Die Sondertilgung wird jeweils
    am Ende eines vollen Jahres verrechnet. Die letzte Rate wird auf die
    tatsaechliche Restschuld gekuerzt, damit keine Ueberzahlung entsteht.
    """
    monate = []
    rest = darlehen
    monatszins = zins / 12.0

    for m in range(1, max_monate + 1):
        zinsanteil = rest * monatszins
        tilgungsanteil = min(rate - zinsanteil, rest)
        zahlung = zinsanteil + tilgungsanteil
        rest -= tilgungsanteil

        sonder = 0.0
        if sondertilgung and m % 12 == 0 and rest > 0:
            sonder = min(sondertilgung, rest)
            rest -= sonder

        monate.append(
            {
                "monat": m,
                "zins": zinsanteil,
                "tilgung": tilgungsanteil,
                "sondertilgung": sonder,
                "zahlung": zahlung + sonder,
                "restschuld": rest,
            }
        )

        if rest <= 0.005:
            break

    return monate


def jahresuebersicht(monate):
    """Verdichtet den Monatsverlauf auf Jahreszeilen."""
    jahre = []
    for start in range(0, len(monate), 12):
        block = monate[start : start + 12]
        jahre.append(
            {
                "jahr": start // 12 + 1,
                "zins": sum(m["zins"] for m in block),
                "tilgung": sum(m["tilgung"] for m in block),
                "sondertilgung": sum(m["sondertilgung"] for m in block),
                "zahlung": sum(m["zahlung"] for m in block),
                "restschuld": block[-1]["restschuld"],
            }
        )
    return jahre


def kennzahlen(darlehen, zins, tilgung, bindung_jahre, sondertilgung=0.0):
    """Buendelt alle Ergebnisgroessen einer Finanzierungsvariante."""
    rate = annuitaet_monatlich(darlehen, zins, tilgung)
    verlauf = tilgungsverlauf(darlehen, zins, rate, sondertilgung)
    jahre = jahresuebersicht(verlauf)

    bindung_monate = bindung_jahre * 12
    innerhalb = verlauf[:bindung_monate]

    return {
        "rate": rate,
        "verlauf": verlauf,
        "jahre": jahre,
        "laufzeit_monate": len(verlauf),
        "laufzeit_jahre": len(verlauf) / 12.0,
        "zinsen_gesamt": sum(m["zins"] for m in verlauf),
        "zinsen_bindung": sum(m["zins"] for m in innerhalb),
        "tilgung_bindung": sum(m["tilgung"] + m["sondertilgung"] for m in innerhalb),
        "restschuld_bindung": (
            innerhalb[-1]["restschuld"] if len(verlauf) >= bindung_monate else 0.0
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  ABLEITUNG DER GRUNDGROESSEN
# ═══════════════════════════════════════════════════════════════════════════

KAUFPREIS_GESAMT = KAUFPREIS_WOHNUNG + KAUFPREIS_STELLPLATZ
GRUNDERWERBSTEUER = KAUFPREIS_GESAMT * GRUNDERWERBSTEUER_SATZ
NOTAR_GRUNDBUCH = KAUFPREIS_GESAMT * NOTAR_GRUNDBUCH_SATZ
MAKLERPROVISION = KAUFPREIS_GESAMT * MAKLERPROVISION_SATZ
NEBENKOSTEN = GRUNDERWERBSTEUER + NOTAR_GRUNDBUCH + MAKLERPROVISION
NEBENKOSTEN_QUOTE = NEBENKOSTEN / KAUFPREIS_GESAMT

GESAMTINVESTITION = KAUFPREIS_GESAMT + NEBENKOSTEN
DARLEHEN = GESAMTINVESTITION - EIGENKAPITAL
EIGENKAPITALQUOTE = EIGENKAPITAL / GESAMTINVESTITION
BELEIHUNGSAUSLAUF = DARLEHEN / KAUFPREIS_GESAMT

ERG = kennzahlen(DARLEHEN, SOLLZINS, ANFANGSTILGUNG, ZINSBINDUNG_JAHRE,
                 SONDERTILGUNG_JAHR)

RATE = ERG["rate"]
GRUNDSTEUER_MONAT = GRUNDSTEUER_JAHR / 12.0
RUECKLAGE_MONAT = RUECKLAGE_SONDEREIGENTUM_QM * WOHNFLAECHE_QM

BELASTUNG_PFLICHT = RATE + HAUSGELD_MONAT + GRUNDSTEUER_MONAT
BELASTUNG_GESAMT = BELASTUNG_PFLICHT + RUECKLAGE_MONAT

QM_PREIS_WOHNUNG = KAUFPREIS_WOHNUNG / WOHNFLAECHE_QM
QM_PREIS_GESAMT = GESAMTINVESTITION / WOHNFLAECHE_QM


# ═══════════════════════════════════════════════════════════════════════════
#  FORMATIERUNG
# ═══════════════════════════════════════════════════════════════════════════


def eur(betrag, nachkomma=0):
    """Formatiert einen Betrag im deutschen Format mit Euro-Zeichen."""
    text = f"{betrag:,.{nachkomma}f}"
    text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{text} €"


def prozent(wert, nachkomma=2):
    return f"{wert * 100:.{nachkomma}f}".replace(".", ",") + " %"


def zahl(wert, nachkomma=1):
    return f"{wert:.{nachkomma}f}".replace(".", ",")


def dauer(monate):
    jahre, rest = divmod(int(round(monate)), 12)
    teile = []
    if jahre:
        teile.append(f"{jahre} Jahr" + ("e" if jahre != 1 else ""))
    if rest:
        teile.append(f"{rest} Monat" + ("e" if rest != 1 else ""))
    return ", ".join(teile) if teile else "0 Monate"


# ═══════════════════════════════════════════════════════════════════════════
#  PDF-GESTALTUNG
# ═══════════════════════════════════════════════════════════════════════════

ANTHRAZIT = colors.HexColor("#3C3C3B")
MITTELGRAU = colors.HexColor("#77776F")
LINIE = colors.HexColor("#C9C9C2")
ZEILE = colors.HexColor("#F2F2EF")
WEISS = colors.white

_ss = getSampleStyleSheet()

S_TITEL = ParagraphStyle(
    "Titel", parent=_ss["Normal"], fontName="Helvetica", fontSize=19,
    leading=25, textColor=ANTHRAZIT, spaceAfter=2,
)
S_UNTERTITEL = ParagraphStyle(
    "Untertitel", parent=_ss["Normal"], fontName="Helvetica", fontSize=10,
    leading=15, textColor=MITTELGRAU,
)
S_H2 = ParagraphStyle(
    "H2", parent=_ss["Normal"], fontName="Helvetica-Bold", fontSize=11.5,
    leading=15, textColor=ANTHRAZIT, spaceBefore=16, spaceAfter=7,
)
S_TEXT = ParagraphStyle(
    "Text", parent=_ss["Normal"], fontName="Helvetica", fontSize=8.8,
    leading=13, textColor=ANTHRAZIT,
)
S_HINWEIS = ParagraphStyle(
    "Hinweis", parent=_ss["Normal"], fontName="Helvetica", fontSize=7.6,
    leading=11, textColor=MITTELGRAU,
)
S_ZELLE = ParagraphStyle(
    "Zelle", parent=_ss["Normal"], fontName="Helvetica", fontSize=8.5,
    leading=11.5, textColor=ANTHRAZIT,
)
S_HERO_LABEL = ParagraphStyle(
    "HeroLabel", parent=_ss["Normal"], fontName="Helvetica", fontSize=9,
    leading=12, textColor=colors.HexColor("#D8D8D2"),
)
S_HERO_WERT = ParagraphStyle(
    "HeroWert", parent=_ss["Normal"], fontName="Helvetica-Bold", fontSize=27,
    leading=31, textColor=WEISS, alignment=TA_RIGHT,
)
S_HERO_TEXT = ParagraphStyle(
    "HeroText", parent=_ss["Normal"], fontName="Helvetica", fontSize=8.4,
    leading=12, textColor=colors.HexColor("#D8D8D2"), alignment=TA_RIGHT,
)

INHALTSBREITE = A4[0] - 4 * cm


def abschnitt(titel):
    """Ueberschrift mit Unterstrich, angelehnt an die Optik des Exposes."""
    linie = Table([[""]], colWidths=[3.6 * cm], rowHeights=[1.6], hAlign="LEFT")
    linie.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ANTHRAZIT),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    kopf = Table([[Paragraph(titel, S_H2)], [linie]],
                 colWidths=[INHALTSBREITE], hAlign="LEFT")
    kopf.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (0, 0), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 3),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 10),
    ]))
    return kopf


def wertetabelle(zeilen, hervorheben=(), breiten=None):
    """Zweispaltige Tabelle: Bezeichnung links, Betrag rechts."""
    daten = [[Paragraph(a, S_ZELLE), b] for a, b in zeilen]
    breiten = breiten or [INHALTSBREITE * 0.62, INHALTSBREITE * 0.38]
    tab = Table(daten, colWidths=breiten, hAlign="LEFT")

    stil = [
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (0, 0), (-1, -1), ANTHRAZIT),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINIE),
    ]
    for i in range(0, len(daten), 2):
        stil.append(("BACKGROUND", (0, i), (-1, i), ZEILE))
    for i in hervorheben:
        stil.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
        stil.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#E4E4DE")))

    tab.setStyle(TableStyle(stil))
    return tab


def matrixtabelle(kopf, zeilen, breiten, markiere=None):
    """Mehrspaltige Tabelle mit dunkler Kopfzeile."""
    daten = [kopf] + zeilen
    tab = Table(daten, colWidths=breiten, hAlign="LEFT", repeatRows=1)

    stil = [
        ("BACKGROUND", (0, 0), (-1, 0), ANTHRAZIT),
        ("TEXTCOLOR", (0, 0), (-1, 0), WEISS),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (0, 1), (-1, -1), ANTHRAZIT),
        ("TOPPADDING", (0, 0), (-1, -1), 3.3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.3),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINIE),
    ]
    for i in range(1, len(daten)):
        if i % 2 == 1:
            stil.append(("BACKGROUND", (0, i), (-1, i), ZEILE))
    if markiere is not None:
        stil += [
            ("BACKGROUND", (0, markiere), (-1, markiere), colors.HexColor("#DEDED6")),
            ("FONTNAME", (0, markiere), (-1, markiere), "Helvetica-Bold"),
        ]

    tab.setStyle(TableStyle(stil))
    return tab


def herobox():
    """Die zentrale Aussage des Dokuments: die Rate an die Bank."""
    links = Paragraph(
        "<b>Ihre monatliche Rate an die Bank</b><br/>"
        f"Annuitätendarlehen über {eur(DARLEHEN)}<br/>"
        f"{prozent(SOLLZINS)} Sollzins, {prozent(ANFANGSTILGUNG)} Anfangstilgung",
        S_HERO_LABEL,
    )
    rechts = [
        Paragraph(eur(RATE, 2), S_HERO_WERT),
        Paragraph("pro Monat, fest über "
                  f"{ZINSBINDUNG_JAHRE} Jahre", S_HERO_TEXT),
    ]
    tab = Table([[links, rechts]],
                colWidths=[INHALTSBREITE * 0.5, INHALTSBREITE * 0.5])
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ANTHRAZIT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
    ]))
    return tab


def kopf_und_fuss(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINIE)
    canvas.setLineWidth(0.4)

    canvas.line(2 * cm, A4[1] - 1.5 * cm, A4[0] - 2 * cm, A4[1] - 1.5 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MITTELGRAU)
    canvas.drawString(2 * cm, A4[1] - 1.32 * cm,
                      "FINANZIERUNGSÜBERSICHT · WALDBURGSTRASSE 153B, "
                      "STUTTGART-VAIHINGEN")
    canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 1.32 * cm, f"Stand {STAND}")

    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.drawString(2 * cm, 1.05 * cm,
                      "Unverbindliche Modellrechnung – kein Angebot und "
                      "keine Finanzierungsberatung")
    canvas.drawRightString(A4[0] - 2 * cm, 1.05 * cm, f"Seite {doc.page}")
    canvas.restoreState()


# ═══════════════════════════════════════════════════════════════════════════
#  INHALT
# ═══════════════════════════════════════════════════════════════════════════


def teil_kopf():
    inhalt = []

    inhalt.append(Paragraph("Finanzierung Ihrer Eigentumswohnung", S_TITEL))
    inhalt.append(Paragraph(
        f"{OBJEKT_ADRESSE}<br/>{OBJEKT_BESCHREIBUNG} · "
        f"{zahl(WOHNFLAECHE_QM, 0)} m² Wohnfläche · "
        f"{zahl(GARTENFLAECHE_QM, 0)} m² Garten · {ENERGIESTANDARD}",
        S_UNTERTITEL))
    inhalt.append(Spacer(1, 18))

    inhalt.append(herobox())
    inhalt.append(Spacer(1, 20))
    return inhalt


def teil_kaufpreis():
    inhalt = []
    inhalt.append(abschnitt("1 · Kaufpreis und Erwerbsnebenkosten"))
    inhalt.append(wertetabelle(
        [
            ("Kaufpreis Wohnung inkl. Einbauküche", eur(KAUFPREIS_WOHNUNG)),
            ("Tiefgaragen-Stellplatz", eur(KAUFPREIS_STELLPLATZ)),
            ("<b>Kaufpreis gesamt</b>", eur(KAUFPREIS_GESAMT)),
            (f"Grunderwerbsteuer Baden-Württemberg "
             f"({prozent(GRUNDERWERBSTEUER_SATZ, 1)})", eur(GRUNDERWERBSTEUER)),
            (f"Notar und Grundbuchamt ({prozent(NOTAR_GRUNDBUCH_SATZ, 1)})",
             eur(NOTAR_GRUNDBUCH)),
            ("Maklerprovision (keine Käuferprovision laut Exposé)",
             eur(MAKLERPROVISION)),
            (f"<b>Erwerbsnebenkosten gesamt</b> "
             f"({prozent(NEBENKOSTEN_QUOTE, 1)} vom Kaufpreis)", eur(NEBENKOSTEN)),
            ("<b>Gesamtinvestition</b>", eur(GESAMTINVESTITION)),
        ],
        hervorheben=[2, 6, 7],
    ))
    inhalt.append(Spacer(1, 5))
    inhalt.append(Paragraph(
        "Die Einbauküche ist im Kaufpreis enthalten und wurde nicht als "
        "bewegliches Inventar herausgerechnet. Würde sie im Kaufvertrag "
        "separat ausgewiesen, entfiele darauf die Grunderwerbsteuer – bei "
        "einem Ansatz von 25.000 € wären das rund 1.250 € weniger.",
        S_HINWEIS))
    return [KeepTogether(inhalt), Spacer(1, 16)]


def teil_struktur():
    inhalt = []
    inhalt.append(abschnitt("2 · Finanzierungsstruktur"))
    inhalt.append(wertetabelle(
        [
            ("Gesamtinvestition", eur(GESAMTINVESTITION)),
            (f"abzüglich Eigenkapital "
             f"({prozent(EIGENKAPITALQUOTE, 1)} der Gesamtinvestition)",
             "– " + eur(EIGENKAPITAL)),
            ("<b>Darlehensbedarf</b>", eur(DARLEHEN)),
            ("Sollzins p. a., gebunden", prozent(SOLLZINS)),
            ("Anfängliche Tilgung p. a.", prozent(ANFANGSTILGUNG)),
            ("Zinsbindung", f"{ZINSBINDUNG_JAHRE} Jahre"),
            ("Beleihungsauslauf (Darlehen zu Kaufpreis)",
             prozent(BELEIHUNGSAUSLAUF, 1)),
        ],
        hervorheben=[2],
    ))
    inhalt.append(Spacer(1, 5))
    inhalt.append(Paragraph(
        f"Mit einem Beleihungsauslauf von {prozent(BELEIHUNGSAUSLAUF, 1)} liegen "
        "Sie unterhalb der 60-Prozent-Schwelle. Das ist die Zone, in der Banken "
        "ihre besten Konditionen vergeben – ein starkes Argument in der "
        "Zinsverhandlung. Sondertilgungen sind in dieser Rechnung bewusst nicht "
        "berücksichtigt; ein Recht auf 5 % jährlich sollten Sie sich "
        "dennoch einräumen lassen, da es üblicherweise kostenfrei ist.",
        S_HINWEIS))
    return [KeepTogether(inhalt), Spacer(1, 16)]


def teil_belastung():
    inhalt = []
    inhalt.append(abschnitt("3 · Monatliche Belastung bei Eigennutzung"))
    inhalt.append(wertetabelle(
        [
            ("Rate an die Bank (Zins und Tilgung)", eur(RATE, 2)),
            ("Hausgeld laut Exposé", eur(HAUSGELD_MONAT, 2)),
            ("Grundsteuer (geschätzt)", eur(GRUNDSTEUER_MONAT, 2)),
            ("<b>Feste monatliche Zahlungsverpflichtungen</b>",
             eur(BELASTUNG_PFLICHT, 2)),
            (f"Rücklage Sondereigentum "
             f"({zahl(RUECKLAGE_SONDEREIGENTUM_QM, 2)} € je m²)",
             eur(RUECKLAGE_MONAT, 2)),
            ("<b>Gesamtbelastung inkl. Vorsorge</b>", eur(BELASTUNG_GESAMT, 2)),
        ],
        hervorheben=[3, 5],
    ))
    inhalt.append(Spacer(1, 5))
    inhalt.append(Paragraph(
        "Nicht enthalten sind Strom, Internet, Hausrat- und "
        "Haftpflichtversicherung sowie Heiz- und Warmwasserkosten, soweit sie "
        "über das Hausgeld hinausgehen. Die Hausgeld-Rücklage der "
        "Eigentümergemeinschaft deckt nur das Gemeinschaftseigentum; für "
        "Küche, Bäder und Böden in Ihrer Wohnung sind Sie selbst "
        "zuständig. Beim Neubau fällt das die ersten Jahre kaum ins "
        "Gewicht, ab etwa dem zehnten Jahr sehr wohl.",
        S_HINWEIS))
    inhalt.append(Spacer(1, 4))
    inhalt.append(Paragraph(
        "<b>Zur Grundsteuer:</b> Baden-Württemberg besteuert seit 2025 nur "
        "den Bodenwert. Grundstücksflächenanteil mal Bodenrichtwert "
        "ergibt den Grundsteuerwert, davon 1,3 Promille Steuermesszahl abzüglich "
        "30 % Abschlag für Wohnnutzung, multipliziert mit dem Stuttgarter "
        "Hebesatz von 354 %. Der hier angesetzte Wert von "
        f"{eur(GRUNDSTEUER_JAHR)} im Jahr ist eine bewusst vorsichtige "
        "Schätzung. Den verbindlichen Betrag nennt Ihnen der Verkäufer "
        "oder die Hausverwaltung – fragen Sie danach.",
        S_HINWEIS))
    return [KeepTogether(inhalt), Spacer(1, 16)]


def teil_verlauf():
    inhalt = []
    inhalt.append(abschnitt("4 · Verlauf der gewählten Finanzierung"))
    inhalt.append(wertetabelle(
        [
            ("Darlehen", eur(DARLEHEN)),
            ("Monatliche Rate", eur(RATE, 2)),
            (f"Zinsen während der Zinsbindung ({ZINSBINDUNG_JAHRE} Jahre)",
             eur(ERG["zinsen_bindung"])),
            ("Tilgung während der Zinsbindung", eur(ERG["tilgung_bindung"])),
            (f"<b>Restschuld nach {ZINSBINDUNG_JAHRE} Jahren</b>",
             eur(ERG["restschuld_bindung"])),
            ("Gesamtlaufzeit bis zur Schuldenfreiheit",
             dauer(ERG["laufzeit_monate"])),
            ("<b>Zinsen über die gesamte Laufzeit</b>",
             eur(ERG["zinsen_gesamt"])),
            ("Kaufpreis je m² Wohnfläche",
             eur(QM_PREIS_WOHNUNG) + " / m²"),
            ("Gesamtinvestition je m² Wohnfläche",
             eur(QM_PREIS_GESAMT) + " / m²"),
        ],
        hervorheben=[4, 6],
    ))
    return [KeepTogether(inhalt), Spacer(1, 16)]


def teil_varianten():
    inhalt = []
    inhalt.append(abschnitt("5 · Was andere Tilgungssätze bedeuten"))

    zeilen, markiere = [], None
    for i, t in enumerate(TILGUNGSVARIANTEN, start=1):
        k = kennzahlen(DARLEHEN, SOLLZINS, t, ZINSBINDUNG_JAHRE)
        if abs(t - ANFANGSTILGUNG) < 1e-9:
            markiere = i
        zeilen.append([
            prozent(t, 1),
            eur(k["rate"], 2),
            eur(k["rate"] + HAUSGELD_MONAT + GRUNDSTEUER_MONAT, 2),
            dauer(k["laufzeit_monate"]),
            eur(k["restschuld_bindung"]),
            eur(k["zinsen_gesamt"]),
        ])

    breiten = [
        INHALTSBREITE * 0.11, INHALTSBREITE * 0.155, INHALTSBREITE * 0.175,
        INHALTSBREITE * 0.20, INHALTSBREITE * 0.175, INHALTSBREITE * 0.185,
    ]
    inhalt.append(matrixtabelle(
        ["Tilgung", "Bankrate", "Feste Kosten",
         "Schuldenfrei nach", f"Rest n. {ZINSBINDUNG_JAHRE} J.", "Zinsen gesamt"],
        zeilen, breiten, markiere=markiere,
    ))
    inhalt.append(Spacer(1, 5))

    ref = kennzahlen(DARLEHEN, SOLLZINS, TILGUNGSVARIANTEN[0], ZINSBINDUNG_JAHRE)
    mehr_rate = RATE - ref["rate"]
    weniger_zins = ref["zinsen_gesamt"] - ERG["zinsen_gesamt"]
    inhalt.append(Paragraph(
        f"Die markierte Zeile ist Ihre Variante. Der Vergleich zeigt den "
        f"eigentlichen Hebel: Gegenüber der marktüblichen Zwei-Prozent-Tilgung "
        f"zahlen Sie monatlich {eur(mehr_rate, 2)} mehr, sparen dafür aber "
        f"{eur(weniger_zins)} Zinsen und sind "
        f"{dauer(ref['laufzeit_monate'] - ERG['laufzeit_monate'])} früher "
        "schuldenfrei. Jeder zusätzliche Tilgungsprozentpunkt wirkt hier "
        "stärker als eine Zinsverbesserung um 0,2 Punkte.",
        S_HINWEIS))
    return [KeepTogether(inhalt), Spacer(1, 16)]


def teil_machbarkeit():
    inhalt = []
    inhalt.append(abschnitt("6 · Machbarkeit aus Sicht der Bank"))
    if NETTOEINKOMMEN_MONAT:
        q_pflicht = BELASTUNG_PFLICHT / NETTOEINKOMMEN_MONAT
        q_rate = RATE / NETTOEINKOMMEN_MONAT
        frei = NETTOEINKOMMEN_MONAT - BELASTUNG_GESAMT

        if q_pflicht <= 0.35:
            urteil = ("Die Belastungsquote liegt im komfortablen Bereich. "
                      "Banken bewerten das als solide finanzierbar.")
        elif q_pflicht <= 0.40:
            urteil = ("Die Belastungsquote liegt im oberen, aber noch "
                      "üblichen Bereich. Die meisten Banken finanzieren "
                      "das, prüfen aber genauer.")
        else:
            urteil = ("Die Belastungsquote liegt über der üblichen "
                      "40-Prozent-Grenze. Rechnen Sie mit Rückfragen, "
                      "Zinsaufschlägen oder der Forderung nach mehr "
                      "Eigenkapital.")

        inhalt.append(wertetabelle(
            [
                ("Nettohaushaltseinkommen im Monat",
                 eur(NETTOEINKOMMEN_MONAT, 2)),
                ("Rate an die Bank", eur(RATE, 2)),
                ("Feste monatliche Zahlungsverpflichtungen",
                 eur(BELASTUNG_PFLICHT, 2)),
                ("Belastungsquote nur Bankrate", prozent(q_rate, 1)),
                ("<b>Belastungsquote feste Kosten</b>", prozent(q_pflicht, 1)),
                ("Verbleibend nach Gesamtbelastung", eur(frei, 2)),
            ],
            hervorheben=[4],
        ))
        inhalt.append(Spacer(1, 5))
        inhalt.append(Paragraph(urteil, S_HINWEIS))
    else:
        inhalt.append(Paragraph(
            "Banken prüfen nicht den Kaufpreis, sondern Ihre "
            "Haushaltsrechnung. Als Faustregel sollen die festen Wohnkosten "
            "35 bis 40 % des Nettohaushaltseinkommens nicht überschreiten. "
            "Daraus ergeben sich diese Schwellen:", S_TEXT))
        inhalt.append(Spacer(1, 7))
        inhalt.append(matrixtabelle(
            ["Nettoeinkommen im Monat", "Belastungsquote", "Bewertung"],
            [
                [eur(BELASTUNG_PFLICHT / 0.30), "30 %", "sehr komfortabel"],
                [eur(BELASTUNG_PFLICHT / 0.35), "35 %", "solide"],
                [eur(BELASTUNG_PFLICHT / 0.40), "40 %", "obere Grenze"],
                [eur(BELASTUNG_PFLICHT / 0.45), "45 %", "kritisch"],
            ],
            [INHALTSBREITE * 0.36, INHALTSBREITE * 0.29, INHALTSBREITE * 0.35],
        ))
        inhalt.append(Spacer(1, 5))
        inhalt.append(Paragraph(
            f"Bezugsgröße sind die festen Zahlungsverpflichtungen von "
            f"{eur(BELASTUNG_PFLICHT, 2)} im Monat. Legen Sie zusätzlich "
            "die Rücklage fürs Sondereigentum an, sollte das Einkommen "
            "entsprechend höher liegen.", S_HINWEIS))

    return [KeepTogether(inhalt), Spacer(1, 16)]


def teil_tilgungsplan():
    inhalt = [abschnitt(
        f"7 · Tilgungsplan über die Zinsbindung von "
        f"{ZINSBINDUNG_JAHRE} Jahren")]

    zeilen = []
    for j in ERG["jahre"][:ZINSBINDUNG_JAHRE]:
        anteil = j["tilgung"] / j["zahlung"] if j["zahlung"] else 0.0
        zeilen.append([
            str(j["jahr"]),
            eur(j["zahlung"]),
            eur(j["zins"]),
            eur(j["tilgung"]),
            prozent(anteil, 1),
            eur(j["restschuld"]),
        ])

    breiten = [
        INHALTSBREITE * 0.09, INHALTSBREITE * 0.175, INHALTSBREITE * 0.175,
        INHALTSBREITE * 0.175, INHALTSBREITE * 0.16, INHALTSBREITE * 0.225,
    ]
    inhalt.append(matrixtabelle(
        ["Jahr", "Zahlung", "davon Zinsen", "davon Tilgung",
         "Tilgungsanteil", "Restschuld"],
        zeilen, breiten,
    ))
    inhalt.append(Spacer(1, 7))

    j1, jn = ERG["jahre"][0], ERG["jahre"][ZINSBINDUNG_JAHRE - 1]
    inhalt.append(Paragraph(
        f"Im ersten Jahr zahlen Sie {eur(j1['zahlung'])}, davon gehen "
        f"{eur(j1['zins'])} als Zinsen an die Bank und nur {eur(j1['tilgung'])} "
        f"in Ihr Eigentum. Im Jahr {ZINSBINDUNG_JAHRE} hat sich das Verhältnis "
        f"umgedreht: {eur(jn['tilgung'])} Tilgung stehen dann nur noch "
        f"{eur(jn['zins'])} Zinsen gegenüber. Dieser Effekt ist der Grund, "
        "warum eine höhere Anfangstilgung so stark wirkt – sie "
        "beschleunigt genau diese Umkehr.",
        S_HINWEIS))
    return inhalt + [Spacer(1, 16)]


def teil_anschluss():
    inhalt = []
    inhalt.append(abschnitt("8 · Nach Ablauf der Zinsbindung"))
    if ERG["restschuld_bindung"] > 0:
        rest_rate = annuitaet_monatlich(
            ERG["restschuld_bindung"], SOLLZINS, ANFANGSTILGUNG)
        inhalt.append(Paragraph(
            f"Nach {ZINSBINDUNG_JAHRE} Jahren verbleibt eine Restschuld von "
            f"{eur(ERG['restschuld_bindung'])}. Diese finanzieren Sie zu den dann "
            "geltenden Konditionen an. Weil der Betrag klein ist, fällt das "
            "Zinsrisiko kaum ins Gewicht: Selbst ein deutlich höherer "
            "Anschlusszins bewegt die Rate nur um wenige Euro. Bei "
            f"gleichbleibenden Konditionen läge sie bei {eur(rest_rate, 2)}, "
            f"und Sie wären nach insgesamt {dauer(ERG['laufzeit_monate'])} "
            "schuldenfrei.", S_TEXT))
    else:
        inhalt.append(Paragraph(
            "Das Darlehen ist bereits vor Ablauf der Zinsbindung vollständig "
            "getilgt. Eine Anschlussfinanzierung entfällt.", S_TEXT))

    inhalt.append(Spacer(1, 4))
    inhalt.append(Paragraph(
        "Unabhängig von der vereinbarten Zinsbindung können Sie das "
        "Darlehen nach § 489 BGB zehn Jahre nach Vollauszahlung mit einer "
        "Frist von sechs Monaten entschädigungsfrei kündigen. Eine lange "
        "Zinsbindung schränkt Sie also nicht ein: Sie sichert gegen steigende "
        "Zinsen ab, lässt Ihnen bei fallenden Zinsen aber den Ausstieg.",
        S_HINWEIS))
    return [KeepTogether(inhalt), Spacer(1, 10)]


def teil_grundlagen():
    inhalt = []
    inhalt.append(abschnitt("9 · Grundlagen und Vorbehalte"))
    inhalt.append(Paragraph(
        "Gerechnet wurde ein Annuitätendarlehen mit monatlich "
        "nachschüssiger Zahlung, konstanter Rate und monatlicher "
        "Zinsverrechnung. Der ausgewiesene Zinssatz ist ein nominaler Sollzins; "
        "der Effektivzins liegt geringfügig darüber, weil Banken "
        "Bearbeitungsentgelte und Auszahlungskurse einrechnen. Nicht "
        "berücksichtigt sind Bereitstellungszinsen, Schätzkosten, "
        "Kontoführungsgebühren und die Kosten der Grundschuldbestellung, "
        "die bereits in den Notargebühren enthalten sein können. "
        "Grunderwerbsteuer und Notarkosten sind mit marktüblichen Sätzen "
        "angesetzt, die Grundsteuer ist geschätzt.", S_TEXT))
    inhalt.append(Spacer(1, 5))
    inhalt.append(Paragraph(
        "Dieses Dokument ist eine Modellrechnung zur eigenen Orientierung. Es "
        "ersetzt weder ein verbindliches Finanzierungsangebot noch eine "
        "Beratung durch Bank, Steuerberater oder Notar.", S_HINWEIS))

    return [KeepTogether(inhalt)]


# ═══════════════════════════════════════════════════════════════════════════
#  ERZEUGUNG
# ═══════════════════════════════════════════════════════════════════════════


def erzeuge_pdf(dateiname=PDF_DATEI):
    doc = BaseDocTemplate(
        dateiname, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title="Finanzierungsübersicht Waldburgstrasse 153b",
        author="Modellrechnung", subject="Immobilienfinanzierung",
    )
    rahmen = Frame(doc.leftMargin, doc.bottomMargin,
                   doc.width, doc.height, id="haupt")
    doc.addPageTemplates(
        [PageTemplate(id="standard", frames=[rahmen], onPage=kopf_und_fuss)])

    # Kein fester Seitenumbruch: Die Abschnitte fließen und werden nur
    # gegen das Zerreißen geschuetzt. So bleibt das Layout stimmig, wenn
    # sich Parameter aendern und Abschnitte laenger oder kuerzer werden.
    story = []
    story += teil_kopf()
    story += teil_kaufpreis()
    story += teil_struktur()
    story += teil_belastung()
    story += teil_verlauf()
    story += teil_varianten()
    story += teil_machbarkeit()
    story += teil_tilgungsplan()
    story += teil_anschluss()
    story += teil_grundlagen()

    doc.build(story)
    return dateiname


def konsolenausgabe():
    print("=" * 62)
    print("FINANZIERUNG WALDBURGSTRASSE 153B, STUTTGART-VAIHINGEN")
    print("=" * 62)
    print(f"Kaufpreis gesamt          {eur(KAUFPREIS_GESAMT):>18}")
    print(f"Erwerbsnebenkosten        {eur(NEBENKOSTEN):>18}"
          f"  ({prozent(NEBENKOSTEN_QUOTE, 1)})")
    print(f"Gesamtinvestition         {eur(GESAMTINVESTITION):>18}")
    print(f"Eigenkapital              {eur(EIGENKAPITAL):>18}"
          f"  ({prozent(EIGENKAPITALQUOTE, 1)})")
    print(f"Darlehen                  {eur(DARLEHEN):>18}"
          f"  (Beleihung {prozent(BELEIHUNGSAUSLAUF, 1)})")
    print("-" * 62)
    print(f"Sollzins / Tilgung        {prozent(SOLLZINS)} / "
          f"{prozent(ANFANGSTILGUNG)}")
    print(f"RATE AN DIE BANK          {eur(RATE, 2):>18}  pro Monat")
    print(f"Gesamtbelastung           {eur(BELASTUNG_GESAMT, 2):>18}  pro Monat")
    print("-" * 62)
    print(f"Restschuld nach {ZINSBINDUNG_JAHRE} J.     "
          f"{eur(ERG['restschuld_bindung']):>18}")
    print(f"Schuldenfrei nach         {dauer(ERG['laufzeit_monate']):>18}")
    print(f"Zinsen gesamt             {eur(ERG['zinsen_gesamt']):>18}")
    print("=" * 62)


if __name__ == "__main__":
    konsolenausgabe()
    print(f"\nPDF erzeugt: {erzeuge_pdf()}")
