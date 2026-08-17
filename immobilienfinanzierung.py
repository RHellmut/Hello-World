#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Finanzierungsrechner Eigentumswohnung Stuttgart-Vaihingen, Waldburgstrasse 153b.

Berechnet die monatliche Annuitaet an die Bank, die laufende Gesamtbelastung
und den Tilgungsplan ueber die Zinsbindung. Erzeugt daraus ein PDF im
Querformat.

Grundsatz der Rechnung: Alle unsicheren Groessen werden bewusst am oberen
Rand der plausiblen Spanne angesetzt. Wird es guenstiger, entsteht Puffer.
Abschnitt 10 des PDF weist offen aus, wo dieser Puffer steckt.

Alle Stellschrauben stehen im Konfigurationsblock KONFIGURATION weiter unten.
Aendert sich z. B. der Zinssatz, genuegt eine Zeile und ein erneuter Lauf:

    python3 immobilienfinanzierung.py
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
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

# --- Erwerbsnebenkosten -------------------------------------------------
GRUNDERWERBSTEUER_SATZ = 0.050       # Baden-Wuerttemberg
NOTAR_GRUNDBUCH_SATZ = 0.020         # oberer Rand der Spanne 1,5 bis 2,0 %
MAKLERPROVISION_SATZ = 0.000         # laut Expose keine Kaeuferprovision

# --- Finanzierungsnebenkosten -------------------------------------------
# Diese Posten fallen zusaetzlich zum Kaufpreis an und erhoehen den
# Darlehensbedarf. Grundschuldkosten und Bereitstellungszinsen bemessen
# sich am Darlehen, das sie selbst vergroessern - siehe darlehensbedarf().
SCHAETZKOSTEN = 1_500.0              # Wertermittlung, oberer Rand
GRUNDSCHULD_SATZ = 0.010             # Bestellung und Eintragung, vom Darlehen
BEREITSTELLUNGSZINS_MONAT = 0.0025   # 0,25 % je Monat, marktueblich
BEREITSTELLUNGSZINS_MONATE = 3       # konservativ unterstellte Abrufverzoegerung

# --- Finanzierung -------------------------------------------------------
EIGENKAPITAL = 400_000.0
SOLLZINS = 0.0410                    # nominaler Sollzins p. a.
ANFANGSTILGUNG = 0.0300              # anfaenglicher Tilgungssatz p. a.
ZINSBINDUNG_JAHRE = 20
SONDERTILGUNG_JAHR = 0.0             # bewusst ohne Sondertilgung gerechnet

# --- Laufende Kosten ----------------------------------------------------
HAUSGELD_MONAT = 346.0               # laut Expose
GRUNDSTEUER_JAHR = 900.0             # konservativ, Herleitung ergibt ca. 500
KONTOFUEHRUNG_MONAT = 3.0            # laut BGH unzulaessig, vorsorglich angesetzt
RUECKLAGE_SONDEREIGENTUM_QM = 1.0    # EUR je qm und Monat

# --- Haushaltsrechnung --------------------------------------------------
# Monatliches Nettohaushaltseinkommen. None => es werden nur die
# Schwellenwerte ausgewiesen, ohne konkrete Belastungsquote.
NETTOEINKOMMEN_MONAT = 7_900.0

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


def darlehensbedarf(basis, quotenkosten, genauigkeit=1e-9, max_schritte=200):
    """Loest die Rueckkopplung zwischen Darlehen und darlehensabhaengigen Kosten.

    Grundschuldkosten und Bereitstellungszinsen bemessen sich am Darlehen,
    erhoehen es aber zugleich. Gesucht ist der Fixpunkt

        D = basis + quotenkosten * D

    der sich hier als Iteration ergibt. Die geschlossene Loesung waere
    basis / (1 - quotenkosten); die Iteration bleibt auch dann korrekt,
    wenn spaeter nicht lineare Posten hinzukommen.
    """
    if quotenkosten >= 1.0:
        raise ValueError(
            "Darlehensabhaengige Kosten erreichen 100 % - keine Loesung.")

    d = basis
    for _ in range(max_schritte):
        neu = basis + quotenkosten * d
        if abs(neu - d) < genauigkeit:
            return neu
        d = neu
    return d


# ═══════════════════════════════════════════════════════════════════════════
#  ABLEITUNG DER GRUNDGROESSEN
# ═══════════════════════════════════════════════════════════════════════════

KAUFPREIS_GESAMT = KAUFPREIS_WOHNUNG + KAUFPREIS_STELLPLATZ
GRUNDERWERBSTEUER = KAUFPREIS_GESAMT * GRUNDERWERBSTEUER_SATZ
NOTAR_GRUNDBUCH = KAUFPREIS_GESAMT * NOTAR_GRUNDBUCH_SATZ
MAKLERPROVISION = KAUFPREIS_GESAMT * MAKLERPROVISION_SATZ
ERWERBSNEBENKOSTEN = GRUNDERWERBSTEUER + NOTAR_GRUNDBUCH + MAKLERPROVISION
ERWERBSNEBENKOSTEN_QUOTE = ERWERBSNEBENKOSTEN / KAUFPREIS_GESAMT

# Darlehensabhaengige Finanzierungsnebenkosten als Quote vom Darlehen
_QUOTENKOSTEN = (
    GRUNDSCHULD_SATZ
    + BEREITSTELLUNGSZINS_MONAT * BEREITSTELLUNGSZINS_MONATE
)
DARLEHEN = darlehensbedarf(
    basis=KAUFPREIS_GESAMT + ERWERBSNEBENKOSTEN + SCHAETZKOSTEN - EIGENKAPITAL,
    quotenkosten=_QUOTENKOSTEN,
)

GRUNDSCHULDKOSTEN = DARLEHEN * GRUNDSCHULD_SATZ
BEREITSTELLUNGSZINSEN = (
    DARLEHEN * BEREITSTELLUNGSZINS_MONAT * BEREITSTELLUNGSZINS_MONATE)
FINANZIERUNGSNEBENKOSTEN = (
    SCHAETZKOSTEN + GRUNDSCHULDKOSTEN + BEREITSTELLUNGSZINSEN)

NEBENKOSTEN_GESAMT = ERWERBSNEBENKOSTEN + FINANZIERUNGSNEBENKOSTEN
NEBENKOSTEN_QUOTE = NEBENKOSTEN_GESAMT / KAUFPREIS_GESAMT
GESAMTINVESTITION = KAUFPREIS_GESAMT + NEBENKOSTEN_GESAMT

EIGENKAPITALQUOTE = EIGENKAPITAL / GESAMTINVESTITION
BELEIHUNGSAUSLAUF = DARLEHEN / KAUFPREIS_GESAMT

ERG = kennzahlen(DARLEHEN, SOLLZINS, ANFANGSTILGUNG, ZINSBINDUNG_JAHRE,
                 SONDERTILGUNG_JAHR)

RATE = ERG["rate"]
GRUNDSTEUER_MONAT = GRUNDSTEUER_JAHR / 12.0
RUECKLAGE_MONAT = RUECKLAGE_SONDEREIGENTUM_QM * WOHNFLAECHE_QM

BELASTUNG_PFLICHT = (
    RATE + HAUSGELD_MONAT + GRUNDSTEUER_MONAT + KONTOFUEHRUNG_MONAT)
BELASTUNG_GESAMT = BELASTUNG_PFLICHT + RUECKLAGE_MONAT

QM_PREIS_WOHNUNG = KAUFPREIS_WOHNUNG / WOHNFLAECHE_QM
QM_PREIS_GESAMT = GESAMTINVESTITION / WOHNFLAECHE_QM


def feste_kosten(rate):
    """Feste monatliche Zahlungsverpflichtungen zu einer gegebenen Rate."""
    return rate + HAUSGELD_MONAT + GRUNDSTEUER_MONAT + KONTOFUEHRUNG_MONAT


# ═══════════════════════════════════════════════════════════════════════════
#  FORMATIERUNG
# ═══════════════════════════════════════════════════════════════════════════


# Geschuetztes Leerzeichen: verhindert, dass im Fließtext zwischen Zahl
# und Einheit umgebrochen wird ("59,9" am Zeilenende, "%" in der naechsten).
NBSP = " "


def eur(betrag, nachkomma=0):
    """Formatiert einen Betrag im deutschen Format mit Euro-Zeichen."""
    text = f"{betrag:,.{nachkomma}f}"
    text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{text}{NBSP}€"


def prozent(wert, nachkomma=2):
    return f"{wert * 100:.{nachkomma}f}".replace(".", ",") + NBSP + "%"


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
#  PDF-GESTALTUNG - Querformat, zweispaltig
# ═══════════════════════════════════════════════════════════════════════════

SEITE = landscape(A4)
RAND_SEITLICH = 1.7 * cm
RAND_OBEN = 1.6 * cm
RAND_UNTEN = 1.4 * cm

INHALTSBREITE = SEITE[0] - 2 * RAND_SEITLICH
SPALTENABSTAND = 26.0

ANTHRAZIT = colors.HexColor("#3C3C3B")
MITTELGRAU = colors.HexColor("#77776F")
LINIE = colors.HexColor("#C9C9C2")
ZEILE = colors.HexColor("#F2F2EF")
HERVOR = colors.HexColor("#E4E4DE")
WEISS = colors.white

_ss = getSampleStyleSheet()

S_TITEL = ParagraphStyle(
    "Titel", parent=_ss["Normal"], fontName="Helvetica", fontSize=20,
    leading=25, textColor=ANTHRAZIT, spaceAfter=2,
)
S_UNTERTITEL = ParagraphStyle(
    "Untertitel", parent=_ss["Normal"], fontName="Helvetica", fontSize=9.5,
    leading=14, textColor=MITTELGRAU,
)
S_H2 = ParagraphStyle(
    "H2", parent=_ss["Normal"], fontName="Helvetica-Bold", fontSize=11,
    leading=14, textColor=ANTHRAZIT,
)
S_TEXT = ParagraphStyle(
    "Text", parent=_ss["Normal"], fontName="Helvetica", fontSize=8.5,
    leading=12.5, textColor=ANTHRAZIT,
)
S_HINWEIS = ParagraphStyle(
    "Hinweis", parent=_ss["Normal"], fontName="Helvetica", fontSize=7.7,
    leading=11, textColor=MITTELGRAU,
)
S_ZELLE = ParagraphStyle(
    "Zelle", parent=_ss["Normal"], fontName="Helvetica", fontSize=8.3,
    leading=11, textColor=ANTHRAZIT,
)
S_HERO_LABEL = ParagraphStyle(
    "HeroLabel", parent=_ss["Normal"], fontName="Helvetica", fontSize=9,
    leading=13, textColor=colors.HexColor("#D8D8D2"),
)
S_HERO_WERT = ParagraphStyle(
    "HeroWert", parent=_ss["Normal"], fontName="Helvetica-Bold", fontSize=26,
    leading=30, textColor=WEISS,
)
S_HERO_KLEIN = ParagraphStyle(
    "HeroKlein", parent=_ss["Normal"], fontName="Helvetica", fontSize=8.2,
    leading=11.5, textColor=colors.HexColor("#D8D8D2"),
)


def spaltenbreiten(anteil_links=0.60):
    """Breiten der beiden Inhaltsspalten inklusive Zwischenraum."""
    netto = INHALTSBREITE - SPALTENABSTAND
    return netto * anteil_links, netto * (1.0 - anteil_links)


def nebeneinander(links, rechts, anteil_links=0.60):
    """Stellt zwei Flowable-Gruppen nebeneinander - nutzt das Querformat."""
    lb, rb = spaltenbreiten(anteil_links)
    tab = Table([[links, rechts]], colWidths=[lb, rb + SPALTENABSTAND],
                hAlign="LEFT")
    tab.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), SPALTENABSTAND),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tab


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
        ("BOTTOMPADDING", (0, 1), (0, 1), 9),
    ]))
    return kopf


def wertetabelle(zeilen, breite, hervorheben=()):
    """Zweispaltige Tabelle: Bezeichnung links, Betrag rechts."""
    daten = [[Paragraph(a, S_ZELLE), b] for a, b in zeilen]
    tab = Table(daten, colWidths=[breite * 0.62, breite * 0.38], hAlign="LEFT")

    stil = [
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (0, 0), (-1, -1), ANTHRAZIT),
        ("TOPPADDING", (0, 0), (-1, -1), 4.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINIE),
    ]
    for i in range(0, len(daten), 2):
        stil.append(("BACKGROUND", (0, i), (-1, i), ZEILE))
    for i in hervorheben:
        stil.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
        stil.append(("BACKGROUND", (0, i), (-1, i), HERVOR))

    tab.setStyle(TableStyle(stil))
    return tab


def matrixtabelle(kopf, zeilen, breiten, markiere=None, schrift=8.0):
    """Mehrspaltige Tabelle mit dunkler Kopfzeile."""
    daten = [kopf] + zeilen
    tab = Table(daten, colWidths=breiten, hAlign="LEFT", repeatRows=1)

    stil = [
        ("BACKGROUND", (0, 0), (-1, 0), ANTHRAZIT),
        ("TEXTCOLOR", (0, 0), (-1, 0), WEISS),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), schrift),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (0, 1), (-1, -1), ANTHRAZIT),
        ("TOPPADDING", (0, 0), (-1, -1), 3.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINIE),
    ]
    for i in range(1, len(daten)):
        if i % 2 == 1:
            stil.append(("BACKGROUND", (0, i), (-1, i), ZEILE))
    if markiere is not None:
        stil += [
            ("BACKGROUND", (0, markiere), (-1, markiere), HERVOR),
            ("FONTNAME", (0, markiere), (-1, markiere), "Helvetica-Bold"),
        ]

    tab.setStyle(TableStyle(stil))
    return tab


def herobox():
    """Die zentrale Aussage des Dokuments: die Rate an die Bank."""
    lb, rb = spaltenbreiten(0.46)

    links = [
        Paragraph("Ihre monatliche Rate an die Bank", S_HERO_LABEL),
        Paragraph(eur(RATE, 2), S_HERO_WERT),
        Paragraph(
            f"Annuitätendarlehen über {eur(DARLEHEN)} · {prozent(SOLLZINS)} "
            f"Sollzins · {prozent(ANFANGSTILGUNG)} Anfangstilgung · fest über "
            f"{ZINSBINDUNG_JAHRE} Jahre", S_HERO_KLEIN),
    ]
    rechts = [
        Paragraph(
            f"<b>Gesamtbelastung {eur(BELASTUNG_GESAMT, 2)} im Monat</b><br/>"
            f"Feste Zahlungsverpflichtungen {eur(BELASTUNG_PFLICHT, 2)}, "
            f"zusätzlich {eur(RUECKLAGE_MONAT, 2)} Rücklage für das "
            "Sondereigentum.", S_HERO_KLEIN),
        Spacer(1, 6),
        Paragraph(
            f"<b>Schuldenfrei nach {dauer(ERG['laufzeit_monate'])}</b><br/>"
            f"Restschuld nach {ZINSBINDUNG_JAHRE} Jahren "
            f"{eur(ERG['restschuld_bindung'])} · Zinsen über die "
            f"Gesamtlaufzeit {eur(ERG['zinsen_gesamt'])}.", S_HERO_KLEIN),
    ]

    tab = Table([[links, rechts]], colWidths=[lb, rb + SPALTENABSTAND])
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ANTHRAZIT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 13),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 13),
        ("LEFTPADDING", (0, 0), (0, 0), 16),
        ("LEFTPADDING", (1, 0), (1, 0), SPALTENABSTAND),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
    ]))
    return tab


def kopf_und_fuss(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINIE)
    canvas.setLineWidth(0.4)

    oben = SEITE[1] - 1.15 * cm
    canvas.line(RAND_SEITLICH, oben, SEITE[0] - RAND_SEITLICH, oben)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MITTELGRAU)
    canvas.drawString(RAND_SEITLICH, oben + 5,
                      "FINANZIERUNGSÜBERSICHT · WALDBURGSTRASSE 153B, "
                      "STUTTGART-VAIHINGEN")
    canvas.drawRightString(SEITE[0] - RAND_SEITLICH, oben + 5,
                           f"Stand {STAND}")

    unten = 1.0 * cm
    canvas.line(RAND_SEITLICH, unten, SEITE[0] - RAND_SEITLICH, unten)
    canvas.drawString(RAND_SEITLICH, unten - 9,
                      "Unverbindliche Modellrechnung – kein Angebot und "
                      "keine Finanzierungsberatung · konservativ gerechnet")
    canvas.drawRightString(SEITE[0] - RAND_SEITLICH, unten - 9,
                           f"Seite {doc.page}")
    canvas.restoreState()


# ═══════════════════════════════════════════════════════════════════════════
#  INHALT
# ═══════════════════════════════════════════════════════════════════════════


def teil_kopf():
    return [
        Paragraph("Finanzierung Ihrer Eigentumswohnung", S_TITEL),
        Paragraph(
            f"{OBJEKT_ADRESSE} · {OBJEKT_BESCHREIBUNG} · "
            f"{zahl(WOHNFLAECHE_QM, 0)} m² Wohnfläche · "
            f"{zahl(GARTENFLAECHE_QM, 0)} m² Garten · {ENERGIESTANDARD}",
            S_UNTERTITEL),
        Spacer(1, 14),
        herobox(),
        Spacer(1, 20),
    ]


def teil_kaufpreis():
    lb, _ = spaltenbreiten(0.60)
    tabelle = wertetabelle(
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
            (f"<b>Erwerbsnebenkosten</b> "
             f"({prozent(ERWERBSNEBENKOSTEN_QUOTE, 1)} vom Kaufpreis)",
             eur(ERWERBSNEBENKOSTEN)),
        ],
        lb, hervorheben=[2, 6],
    )
    text = [
        Paragraph(
            "Die Grunderwerbsteuer liegt in Baden-Württemberg bei 5,0 % und "
            "ist nicht verhandelbar. Für Notar und Grundbuchamt ist mit "
            "2,0 % der obere Rand der üblichen Spanne von 1,5 bis 2,0 % "
            "angesetzt – fällt die Rechnung niedriger aus, entsteht Puffer.",
            S_TEXT),
        Spacer(1, 7),
        Paragraph(
            "Die Einbauküche ist im Kaufpreis enthalten und wurde nicht als "
            "bewegliches Inventar herausgerechnet. Würde sie im Kaufvertrag "
            "separat ausgewiesen, entfiele darauf die Grunderwerbsteuer – bei "
            "einem Ansatz von 25.000 € wären das rund 1.250 € weniger. Das "
            "ist zulässig, solange der Wert realistisch bleibt.",
            S_HINWEIS),
    ]
    return [KeepTogether([
        abschnitt("1 · Kaufpreis und Erwerbsnebenkosten"),
        nebeneinander(tabelle, text, 0.60),
    ]), Spacer(1, 16)]


def teil_finanzierungskosten():
    lb, _ = spaltenbreiten(0.60)
    tabelle = wertetabelle(
        [
            ("Wertermittlung / Schätzkosten", eur(SCHAETZKOSTEN)),
            (f"Grundschuldbestellung und -eintragung "
             f"({prozent(GRUNDSCHULD_SATZ, 1)} der Grundschuld)",
             eur(GRUNDSCHULDKOSTEN)),
            (f"Bereitstellungszinsen "
             f"({prozent(BEREITSTELLUNGSZINS_MONAT, 2)} × "
             f"{BEREITSTELLUNGSZINS_MONATE} Monate)",
             eur(BEREITSTELLUNGSZINSEN)),
            ("<b>Finanzierungsnebenkosten</b>", eur(FINANZIERUNGSNEBENKOSTEN)),
            ("Erwerbsnebenkosten (Abschnitt 1)", eur(ERWERBSNEBENKOSTEN)),
            (f"<b>Nebenkosten gesamt</b> "
             f"({prozent(NEBENKOSTEN_QUOTE, 1)} vom Kaufpreis)",
             eur(NEBENKOSTEN_GESAMT)),
            ("<b>Gesamtinvestition</b>", eur(GESAMTINVESTITION)),
        ],
        lb, hervorheben=[3, 5, 6],
    )
    text = [
        Paragraph(
            "<b>Grundschuld:</b> Der Notar bestellt sie, das Grundbuchamt "
            "trägt sie ein. Nach GNotKG ergibt sich für diese Darlehenshöhe "
            "eine Gebühr von etwa 0,45 %; angesetzt ist mit 1,0 % der obere "
            "Rand der gängigen Faustregel.", S_TEXT),
        Spacer(1, 6),
        Paragraph(
            "<b>Bereitstellungszinsen:</b> Sie fallen an, sobald die Bank das "
            "Geld bereithält, es aber noch nicht abgerufen ist. Weil die "
            "Wohnung bezugsfertig ist und in einer Summe gezahlt wird, sind "
            "sie realistisch kaum zu erwarten – drei Monate sind bewusst "
            "vorsichtig unterstellt.", S_TEXT),
        Spacer(1, 6),
        Paragraph(
            "Diese Posten erhöhen den Darlehensbedarf, und die Grundschuld "
            "bemisst sich wiederum am Darlehen. Die Rechnung löst diese "
            "Rückkopplung als Fixpunkt auf, statt sie zu ignorieren.",
            S_HINWEIS),
    ]
    return [KeepTogether([
        abschnitt("2 · Finanzierungsnebenkosten"),
        nebeneinander(tabelle, text, 0.60),
    ]), Spacer(1, 16)]


def teil_struktur():
    lb, _ = spaltenbreiten(0.60)
    tabelle = wertetabelle(
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
        lb, hervorheben=[2],
    )

    abstand = 0.60 - BELEIHUNGSAUSLAUF
    if abstand > 0:
        beleihung = Paragraph(
            f"<b>Achten Sie auf die 60-Prozent-Marke.</b> Der "
            f"Beleihungsauslauf liegt bei {prozent(BELEIHUNGSAUSLAUF, 1)} und "
            f"damit nur {prozent(abstand, 1)} unter der Schwelle, ab der "
            f"Banken ihre besten Konditionen vergeben. Das entspricht rund "
            f"{eur(abstand * KAUFPREIS_GESAMT)}. Steigen die Nebenkosten "
            "stärker als hier unterstellt, kippen Sie in die nächste "
            "Beleihungsklasse und zahlen auf die gesamte Summe einen "
            "Zinsaufschlag.", S_TEXT)
    else:
        beleihung = Paragraph(
            f"Der Beleihungsauslauf liegt mit {prozent(BELEIHUNGSAUSLAUF, 1)} "
            "über der 60-Prozent-Schwelle. Mehr Eigenkapital oder niedrigere "
            "Nebenkosten würden Sie in die günstigere Klasse zurückholen.",
            S_TEXT)

    text = [
        beleihung,
        Spacer(1, 6),
        Paragraph(
            "Sondertilgungen sind bewusst nicht eingerechnet. Ein Recht auf "
            "5 % jährlich sollten Sie sich dennoch einräumen lassen: Es ist "
            "üblicherweise kostenfrei und verschafft Ihnen Spielraum, ohne "
            "die vereinbarte Rate zu erhöhen.", S_HINWEIS),
    ]
    return [KeepTogether([
        abschnitt("3 · Finanzierungsstruktur"),
        nebeneinander(tabelle, text, 0.60),
    ]), Spacer(1, 16)]


def teil_belastung():
    lb, _ = spaltenbreiten(0.60)
    tabelle = wertetabelle(
        [
            ("Rate an die Bank (Zins und Tilgung)", eur(RATE, 2)),
            ("Hausgeld laut Exposé", eur(HAUSGELD_MONAT, 2)),
            ("Grundsteuer (konservativ geschätzt)", eur(GRUNDSTEUER_MONAT, 2)),
            ("Kontoführung Darlehenskonto", eur(KONTOFUEHRUNG_MONAT, 2)),
            ("<b>Feste monatliche Zahlungsverpflichtungen</b>",
             eur(BELASTUNG_PFLICHT, 2)),
            (f"Rücklage Sondereigentum "
             f"({zahl(RUECKLAGE_SONDEREIGENTUM_QM, 2)} € je m²)",
             eur(RUECKLAGE_MONAT, 2)),
            ("<b>Gesamtbelastung inkl. Vorsorge</b>", eur(BELASTUNG_GESAMT, 2)),
        ],
        lb, hervorheben=[4, 6],
    )
    text = [
        Paragraph(
            "<b>Kontoführung:</b> Der BGH hat Kontoführungsgebühren für "
            "Darlehenskonten bei Verbraucherkrediten für unwirksam erklärt "
            "(XI ZR 168/21). Der Posten ist hier nur vorsorglich enthalten – "
            "verlangt Ihre Bank ihn, können Sie widersprechen.", S_TEXT),
        Spacer(1, 6),
        Paragraph(
            "<b>Grundsteuer:</b> Baden-Württemberg besteuert seit 2025 nur "
            "den Bodenwert. Grundstücksflächenanteil mal Bodenrichtwert ergibt "
            "den Grundsteuerwert, davon 1,3 Promille Steuermesszahl abzüglich "
            "30 % Abschlag für Wohnnutzung, multipliziert mit dem Stuttgarter "
            f"Hebesatz von 354 %. Für Ihren Anteil ergibt das überschlägig "
            f"500 bis 600 € im Jahr; angesetzt sind "
            f"{eur(GRUNDSTEUER_JAHR)}. Den verbindlichen Betrag nennt Ihnen "
            "die Hausverwaltung.", S_TEXT),
        Spacer(1, 6),
        Paragraph(
            "Nicht enthalten sind Strom, Internet, Hausrat- und "
            "Haftpflichtversicherung sowie Heiz- und Warmwasserkosten, soweit "
            "sie über das Hausgeld hinausgehen. Die Rücklage der "
            "Eigentümergemeinschaft deckt nur das Gemeinschaftseigentum; für "
            "Küche, Bäder und Böden in Ihrer Wohnung sind Sie selbst "
            "zuständig.", S_HINWEIS),
    ]
    return [KeepTogether([
        abschnitt("4 · Monatliche Belastung bei Eigennutzung"),
        nebeneinander(tabelle, text, 0.60),
    ]), Spacer(1, 16)]


def teil_verlauf():
    lb, _ = spaltenbreiten(0.60)
    tabelle = wertetabelle(
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
            ("Kaufpreis je m² Wohnfläche", eur(QM_PREIS_WOHNUNG) + " / m²"),
            ("Gesamtinvestition je m² Wohnfläche",
             eur(QM_PREIS_GESAMT) + " / m²"),
        ],
        lb, hervorheben=[4, 6],
    )
    anteil_zins = ERG["zinsen_gesamt"] / (ERG["zinsen_gesamt"] + DARLEHEN)
    text = [
        Paragraph(
            f"Über die gesamte Laufzeit zahlen Sie {eur(DARLEHEN)} zurück und "
            f"zusätzlich {eur(ERG['zinsen_gesamt'])} an Zinsen. Von jedem Euro, "
            f"den Sie an die Bank überweisen, sind damit "
            f"{prozent(anteil_zins, 0)} reine Zinskosten.", S_TEXT),
        Spacer(1, 6),
        Paragraph(
            f"Der Quadratmeterpreis von {eur(QM_PREIS_WOHNUNG)} bezieht sich "
            "auf die reine Wohnung. Rechnet man Stellplatz und sämtliche "
            f"Nebenkosten hinzu, kostet Sie der Quadratmeter tatsächlich "
            f"{eur(QM_PREIS_GESAMT)} – das ist die Zahl, an der sich ein "
            "späterer Verkauf messen lassen muss.", S_HINWEIS),
    ]
    return [KeepTogether([
        abschnitt("5 · Verlauf der gewählten Finanzierung"),
        nebeneinander(tabelle, text, 0.60),
    ]), Spacer(1, 16)]


def teil_varianten():
    mit_quote = bool(NETTOEINKOMMEN_MONAT)

    zeilen, markiere = [], None
    for i, t in enumerate(TILGUNGSVARIANTEN, start=1):
        k = kennzahlen(DARLEHEN, SOLLZINS, t, ZINSBINDUNG_JAHRE)
        if abs(t - ANFANGSTILGUNG) < 1e-9:
            markiere = i
        fest = feste_kosten(k["rate"])
        zeile = [prozent(t, 1), eur(k["rate"], 2), eur(fest, 2)]
        if mit_quote:
            zeile.append(prozent(fest / NETTOEINKOMMEN_MONAT, 1))
        zeile += [
            dauer(k["laufzeit_monate"]),
            eur(k["restschuld_bindung"]),
            eur(k["zinsen_gesamt"]),
        ]
        zeilen.append(zeile)

    kopf = ["Anfangstilgung", "Rate an die Bank", "Feste Kosten"]
    anteile = [0.13, 0.15, 0.15]
    if mit_quote:
        kopf.append("Belastungsquote")
        anteile.append(0.14)
    kopf += ["Schuldenfrei nach", f"Restschuld nach {ZINSBINDUNG_JAHRE} J.",
             "Zinsen gesamt"]
    anteile += ([0.16, 0.14, 0.13] if mit_quote else [0.21, 0.18, 0.18])

    ref = kennzahlen(DARLEHEN, SOLLZINS, TILGUNGSVARIANTEN[0],
                     ZINSBINDUNG_JAHRE)
    hinweis = Paragraph(
        f"Die markierte Zeile ist Ihre Variante. Gegenüber der marktüblichen "
        f"Zwei-Prozent-Tilgung zahlen Sie monatlich "
        f"{eur(RATE - ref['rate'], 2)} mehr, sparen dafür "
        f"{eur(ref['zinsen_gesamt'] - ERG['zinsen_gesamt'])} Zinsen und sind "
        f"{dauer(ref['laufzeit_monate'] - ERG['laufzeit_monate'])} früher "
        "schuldenfrei. Jeder zusätzliche Tilgungsprozentpunkt wirkt hier "
        "stärker als eine Zinsverbesserung um 0,2 Punkte.", S_HINWEIS)

    return [KeepTogether([
        abschnitt("6 · Was andere Tilgungssätze bedeuten"),
        matrixtabelle(kopf, zeilen, [INHALTSBREITE * a for a in anteile],
                      markiere=markiere),
        Spacer(1, 6),
        hinweis,
    ]), Spacer(1, 16)]


def teil_machbarkeit():
    lb, _ = spaltenbreiten(0.52)

    if NETTOEINKOMMEN_MONAT:
        q_pflicht = BELASTUNG_PFLICHT / NETTOEINKOMMEN_MONAT
        q_rate = RATE / NETTOEINKOMMEN_MONAT

        tabelle = wertetabelle(
            [
                ("Nettohaushaltseinkommen im Monat",
                 eur(NETTOEINKOMMEN_MONAT, 2)),
                ("Rate an die Bank", eur(RATE, 2)),
                ("Feste monatliche Zahlungsverpflichtungen",
                 eur(BELASTUNG_PFLICHT, 2)),
                ("Belastungsquote nur Bankrate", prozent(q_rate, 1)),
                ("<b>Belastungsquote feste Kosten</b>", prozent(q_pflicht, 1)),
                ("Verbleibend nach Gesamtbelastung",
                 eur(NETTOEINKOMMEN_MONAT - BELASTUNG_GESAMT, 2)),
            ],
            lb, hervorheben=[4],
        )

        if q_pflicht <= 0.35:
            kern = ("Die Belastungsquote liegt im komfortablen Bereich. "
                    "Banken bewerten das als solide finanzierbar.")
        elif q_pflicht <= 0.40:
            kern = ("Die Belastungsquote liegt im oberen, aber noch üblichen "
                    "Bereich. Die meisten Banken finanzieren das, prüfen "
                    "aber genauer.")
        else:
            kern = ("Die Belastungsquote liegt über der üblichen "
                    "40-Prozent-Grenze. Rechnen Sie mit Rückfragen, "
                    "Zinsaufschlägen oder der Forderung nach mehr "
                    "Eigenkapital.")

        text = [Paragraph(f"<b>{kern}</b>", S_TEXT)]

        # Welche geringere Tilgung bringt die Quote unter 40 %?
        if q_pflicht > 0.40:
            entlastung = [
                t for t in sorted(TILGUNGSVARIANTEN, reverse=True)
                if t < ANFANGSTILGUNG
                and feste_kosten(annuitaet_monatlich(DARLEHEN, SOLLZINS, t))
                / NETTOEINKOMMEN_MONAT <= 0.40
            ]
            if entlastung:
                t = entlastung[0]
                k = kennzahlen(DARLEHEN, SOLLZINS, t, ZINSBINDUNG_JAHRE)
                fest = feste_kosten(k["rate"])
                text += [
                    Spacer(1, 6),
                    Paragraph(
                        f"Der kürzeste Weg darunter ist eine Anfangstilgung "
                        f"von {prozent(t, 1)}: Die Rate sinkt auf "
                        f"{eur(k['rate'], 2)}, die Quote auf "
                        f"{prozent(fest / NETTOEINKOMMEN_MONAT, 1)}. Sie "
                        f"zahlen dafür {dauer(k['laufzeit_monate'])} statt "
                        f"{dauer(ERG['laufzeit_monate'])} und insgesamt "
                        f"{eur(k['zinsen_gesamt'] - ERG['zinsen_gesamt'])} "
                        "mehr Zinsen. Mit einem Sondertilgungsrecht holen Sie "
                        "einen Teil davon zurück, ohne die vereinbarte Rate "
                        "zu erhöhen – taktisch oft die stärkere Variante.",
                        S_TEXT),
                ]

        text += [
            Spacer(1, 6),
            Paragraph(
                "Die Quote bezieht sich allein auf die Wohnkosten. Laufende "
                "Kredite, Leasingraten oder Unterhaltsverpflichtungen rechnet "
                "die Bank zusätzlich an. Umgekehrt ist diese Rechnung "
                "durchgehend konservativ: Fallen Grundsteuer, Notar- und "
                "Finanzierungsnebenkosten niedriger aus, sinkt die Quote.",
                S_HINWEIS),
        ]
    else:
        tabelle = matrixtabelle(
            ["Nettoeinkommen im Monat", "Belastungsquote", "Bewertung"],
            [
                [eur(BELASTUNG_PFLICHT / 0.30), "30 %", "sehr komfortabel"],
                [eur(BELASTUNG_PFLICHT / 0.35), "35 %", "solide"],
                [eur(BELASTUNG_PFLICHT / 0.40), "40 %", "obere Grenze"],
                [eur(BELASTUNG_PFLICHT / 0.45), "45 %", "kritisch"],
            ],
            [lb * 0.38, lb * 0.28, lb * 0.34],
        )
        text = [Paragraph(
            "Banken prüfen nicht den Kaufpreis, sondern Ihre "
            "Haushaltsrechnung. Als Faustregel sollen die festen Wohnkosten "
            "35 bis 40 % des Nettohaushaltseinkommens nicht überschreiten. "
            f"Bezugsgröße sind die {eur(BELASTUNG_PFLICHT, 2)} festen "
            "Zahlungsverpflichtungen im Monat.", S_TEXT)]

    return [KeepTogether([
        abschnitt("7 · Machbarkeit aus Sicht der Bank"),
        nebeneinander(tabelle, text, 0.52),
    ]), Spacer(1, 16)]


def teil_tilgungsplan():
    """Tilgungsplan, im Querformat als zwei Hälften nebeneinander."""
    jahre = ERG["jahre"][:ZINSBINDUNG_JAHRE]
    haelfte = (len(jahre) + 1) // 2
    lb, rb = spaltenbreiten(0.50)

    def block(teil, breite):
        zeilen = [[
            str(j["jahr"]),
            eur(j["zins"]),
            eur(j["tilgung"]),
            prozent(j["tilgung"] / j["zahlung"] if j["zahlung"] else 0, 1),
            eur(j["restschuld"]),
        ] for j in teil]
        return matrixtabelle(
            ["Jahr", "Zinsen", "Tilgung", "Tilgungsanteil", "Restschuld"],
            zeilen,
            [breite * 0.11, breite * 0.21, breite * 0.21,
             breite * 0.23, breite * 0.24],
            schrift=7.8,
        )

    j1, jn = jahre[0], jahre[-1]
    return [KeepTogether([
        abschnitt(f"8 · Tilgungsplan über die Zinsbindung von "
                  f"{ZINSBINDUNG_JAHRE} Jahren"),
        nebeneinander(block(jahre[:haelfte], lb),
                      block(jahre[haelfte:], rb), 0.50),
        Spacer(1, 7),
        Paragraph(
            f"Die jährliche Zahlung beträgt konstant {eur(j1['zahlung'])}. Im "
            f"ersten Jahr gehen davon {eur(j1['zins'])} als Zinsen an die Bank "
            f"und nur {eur(j1['tilgung'])} in Ihr Eigentum. Im Jahr "
            f"{ZINSBINDUNG_JAHRE} hat sich das Verhältnis umgedreht: "
            f"{eur(jn['tilgung'])} Tilgung stehen dann nur noch "
            f"{eur(jn['zins'])} Zinsen gegenüber. Dieser Effekt ist der Grund, "
            "warum eine höhere Anfangstilgung so stark wirkt – sie "
            "beschleunigt genau diese Umkehr.", S_HINWEIS),
    ]), Spacer(1, 16)]


def teil_puffer():
    """Legt offen, wo die konservativen Ansaetze Spielraum lassen."""
    posten = [
        ("Notar und Grundbuchamt", "1,5 % statt 2,0 %",
         KAUFPREIS_GESAMT * 0.005),
        ("Grundschuldbestellung", "GNotKG-Gebühr statt 1,0 %",
         GRUNDSCHULDKOSTEN - DARLEHEN * 0.0045),
        ("Bereitstellungszinsen", "sofortiger Abruf, 0 Monate",
         BEREITSTELLUNGSZINSEN),
        ("Schätzkosten", "Bank verzichtet oder pauschaliert",
         SCHAETZKOSTEN - 500.0),
        ("Einbauküche herausrechnen", "25.000 € ohne Grunderwerbsteuer",
         25_000.0 * GRUNDERWERBSTEUER_SATZ),
    ]
    # Auf ganze Euro runden, bevor summiert wird: Sonst weicht die
    # Summenzeile von der Summe der angezeigten Einzelwerte ab.
    posten = [(a, b, round(c)) for a, b, c in posten]
    summe = sum(p[2] for p in posten)

    lb, _ = spaltenbreiten(0.60)
    zeilen = [[a, b, eur(c)] for a, b, c in posten]
    zeilen.append(["Summe", "", eur(summe)])
    tabelle = matrixtabelle(
        ["Position", "Günstigerer Fall", "Ersparnis einmalig"],
        zeilen, [lb * 0.36, lb * 0.38, lb * 0.26],
        markiere=len(zeilen),
    )

    # Wirkung auf Rate und Quote, wenn saemtliche Puffer aufgehen
    d_guenstig = DARLEHEN - summe
    r_guenstig = annuitaet_monatlich(d_guenstig, SOLLZINS, ANFANGSTILGUNG)
    fest_guenstig = (r_guenstig + HAUSGELD_MONAT + 500.0 / 12.0)

    text = [
        Paragraph(
            "Jede unsichere Größe ist am oberen Rand der plausiblen Spanne "
            "angesetzt. Fällt sie günstiger aus, sinkt der Darlehensbedarf – "
            "die Rechnung kann sich also nur zu Ihren Gunsten irren.", S_TEXT),
        Spacer(1, 6),
        Paragraph(
            f"Gehen sämtliche Puffer auf, sinkt das Darlehen auf "
            f"{eur(d_guenstig)} und die Rate auf {eur(r_guenstig, 2)}. "
            "Zusammen mit einer Grundsteuer von 500 € im Jahr und ohne "
            "Kontoführungsgebühr lägen die festen Kosten dann bei "
            f"{eur(fest_guenstig, 2)}"
            + (f" – eine Belastungsquote von "
               f"{prozent(fest_guenstig / NETTOEINKOMMEN_MONAT, 1)}."
               if NETTOEINKOMMEN_MONAT else ".")
            + " Das ist das optimistische Ende der Spanne, nicht die "
              "Planungsgrundlage.", S_TEXT),
        Spacer(1, 6),
        Paragraph(
            "Nach oben abgesichert ist die Rechnung damit nicht vollständig: "
            "Ein höherer Sollzins, eine unerwartet hohe Grundsteuer oder eine "
            "Sonderumlage der Eigentümergemeinschaft liegen außerhalb dieser "
            "Betrachtung.", S_HINWEIS),
    ]
    return [KeepTogether([
        abschnitt("9 · Wo diese Rechnung Puffer enthält"),
        nebeneinander(tabelle, text, 0.60),
    ]), Spacer(1, 16)]


def teil_anschluss():
    lb, rb = spaltenbreiten(0.50)

    if ERG["restschuld_bindung"] > 0:
        rest_rate = annuitaet_monatlich(
            ERG["restschuld_bindung"], SOLLZINS, ANFANGSTILGUNG)
        links = Paragraph(
            f"Nach {ZINSBINDUNG_JAHRE} Jahren verbleibt eine Restschuld von "
            f"{eur(ERG['restschuld_bindung'])}. Diese finanzieren Sie zu den "
            "dann geltenden Konditionen an. Weil der Betrag klein ist, fällt "
            "das Zinsrisiko kaum ins Gewicht: Selbst ein deutlich höherer "
            "Anschlusszins bewegt die Rate nur um wenige Euro. Bei "
            f"gleichbleibenden Konditionen läge sie bei {eur(rest_rate, 2)}, "
            f"und Sie wären nach insgesamt {dauer(ERG['laufzeit_monate'])} "
            "schuldenfrei.", S_TEXT)
    else:
        links = Paragraph(
            "Das Darlehen ist bereits vor Ablauf der Zinsbindung vollständig "
            "getilgt. Eine Anschlussfinanzierung entfällt.", S_TEXT)

    rechts = Paragraph(
        "Unabhängig von der vereinbarten Zinsbindung können Sie das Darlehen "
        "nach § 489 BGB zehn Jahre nach Vollauszahlung mit einer Frist von "
        "sechs Monaten entschädigungsfrei kündigen. Eine lange Zinsbindung "
        "schränkt Sie also nicht ein: Sie sichert gegen steigende Zinsen ab, "
        "lässt Ihnen bei fallenden Zinsen aber den Ausstieg.", S_HINWEIS)

    return [KeepTogether([
        abschnitt("10 · Nach Ablauf der Zinsbindung"),
        nebeneinander(links, rechts, 0.50),
    ]), Spacer(1, 16)]


def teil_grundlagen():
    links = Paragraph(
        "Gerechnet wurde ein Annuitätendarlehen mit monatlich nachschüssiger "
        "Zahlung, konstanter Rate und monatlicher Zinsverrechnung. Der "
        "ausgewiesene Zinssatz ist ein nominaler Sollzins; der Effektivzins "
        "liegt geringfügig darüber, weil Banken Bearbeitungsentgelte und "
        "Auszahlungskurse einrechnen. Grunderwerbsteuer, Notarkosten und "
        "Finanzierungsnebenkosten sind mit marktüblichen Sätzen am oberen "
        "Rand angesetzt, die Grundsteuer ist geschätzt.", S_TEXT)
    rechts = Paragraph(
        "Nicht berücksichtigt sind Sonderumlagen der Eigentümergemeinschaft, "
        "Umzugs- und Einrichtungskosten sowie Zinsänderungen nach Ablauf der "
        "Zinsbindung. Dieses Dokument ist eine Modellrechnung zur eigenen "
        "Orientierung. Es ersetzt weder ein verbindliches "
        "Finanzierungsangebot noch eine Beratung durch Bank, Steuerberater "
        "oder Notar.", S_HINWEIS)

    return [KeepTogether([
        abschnitt("11 · Grundlagen und Vorbehalte"),
        nebeneinander(links, rechts, 0.50),
    ])]


# ═══════════════════════════════════════════════════════════════════════════
#  ERZEUGUNG
# ═══════════════════════════════════════════════════════════════════════════


def erzeuge_pdf(dateiname=PDF_DATEI):
    doc = BaseDocTemplate(
        dateiname, pagesize=SEITE,
        leftMargin=RAND_SEITLICH, rightMargin=RAND_SEITLICH,
        topMargin=RAND_OBEN, bottomMargin=RAND_UNTEN,
        title="Finanzierungsübersicht Waldburgstrasse 153b",
        author="Modellrechnung", subject="Immobilienfinanzierung",
    )
    rahmen = Frame(doc.leftMargin, doc.bottomMargin,
                   doc.width, doc.height, id="haupt")
    doc.addPageTemplates(
        [PageTemplate(id="standard", frames=[rahmen], onPage=kopf_und_fuss)])

    # Kein fester Seitenumbruch: Die Abschnitte fliessen und werden nur
    # gegen das Zerreissen geschuetzt. So bleibt das Layout stimmig, wenn
    # sich Parameter aendern und Abschnitte laenger oder kuerzer werden.
    story = []
    for teil in (teil_kopf, teil_kaufpreis, teil_finanzierungskosten,
                 teil_struktur, teil_belastung, teil_verlauf, teil_varianten,
                 teil_machbarkeit, teil_tilgungsplan, teil_puffer,
                 teil_anschluss, teil_grundlagen):
        story += teil()

    doc.build(story)
    return dateiname


def konsolenausgabe():
    print("=" * 64)
    print("FINANZIERUNG WALDBURGSTRASSE 153B, STUTTGART-VAIHINGEN")
    print("konservativ gerechnet")
    print("=" * 64)
    print(f"Kaufpreis gesamt           {eur(KAUFPREIS_GESAMT):>18}")
    print(f"Erwerbsnebenkosten         {eur(ERWERBSNEBENKOSTEN):>18}"
          f"  ({prozent(ERWERBSNEBENKOSTEN_QUOTE, 1)})")
    print(f"Finanzierungsnebenkosten   {eur(FINANZIERUNGSNEBENKOSTEN):>18}")
    print(f"  davon Schaetzkosten      {eur(SCHAETZKOSTEN):>18}")
    print(f"  davon Grundschuld        {eur(GRUNDSCHULDKOSTEN):>18}")
    print(f"  davon Bereitstellung     {eur(BEREITSTELLUNGSZINSEN):>18}")
    print(f"Gesamtinvestition          {eur(GESAMTINVESTITION):>18}")
    print(f"Eigenkapital               {eur(EIGENKAPITAL):>18}"
          f"  ({prozent(EIGENKAPITALQUOTE, 1)})")
    print(f"Darlehen                   {eur(DARLEHEN):>18}"
          f"  (Beleihung {prozent(BELEIHUNGSAUSLAUF, 1)})")
    print("-" * 64)
    print(f"Sollzins / Tilgung         {prozent(SOLLZINS)} / "
          f"{prozent(ANFANGSTILGUNG)}")
    print(f"RATE AN DIE BANK           {eur(RATE, 2):>18}  pro Monat")
    print(f"Feste Kosten               {eur(BELASTUNG_PFLICHT, 2):>18}"
          "  pro Monat")
    print(f"Gesamtbelastung            {eur(BELASTUNG_GESAMT, 2):>18}"
          "  pro Monat")
    if NETTOEINKOMMEN_MONAT:
        print(f"Belastungsquote            "
              f"{prozent(BELASTUNG_PFLICHT / NETTOEINKOMMEN_MONAT, 1):>18}")
    print("-" * 64)
    print(f"Restschuld nach {ZINSBINDUNG_JAHRE} J.      "
          f"{eur(ERG['restschuld_bindung']):>18}")
    print(f"Schuldenfrei nach          {dauer(ERG['laufzeit_monate']):>18}")
    print(f"Zinsen gesamt              {eur(ERG['zinsen_gesamt']):>18}")
    print("=" * 64)


if __name__ == "__main__":
    konsolenausgabe()
    print(f"\nPDF erzeugt: {erzeuge_pdf()}")
