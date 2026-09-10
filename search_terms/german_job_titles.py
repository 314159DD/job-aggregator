"""
search_terms/german_job_titles.py - Shared German job title intelligence.

Comprehensive, sector-diverse job title list for Germany.
Organized by sector (loosely based on KldB 2010 categories) and tiered by volume.

Tier 1: High-volume titles - run every crawl (~80 terms)
Tier 2: Medium-volume titles - run weekly or on rotation (~120 terms)
Tier 3: Niche/specialist titles - run monthly or on rotation (~100 terms)

Data sources for this list:
- KldB 2010 (Klassifikation der Berufe) - official German occupation classification
- BIBB Ausbildungsberufe - 300+ recognized apprenticeship titles
- Common postings from major German job boards
- BA labor market statistics (Mangelberufe / shortage occupations)

All search-term sources should import from here instead of maintaining
their own _DEFAULT_TERMS.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# SECTOR DEFINITIONS - each sector has tier 1/2/3 titles
# ---------------------------------------------------------------------------

SECTORS: dict[str, dict[int, list[str]]] = {

    # ── IT & Software ──────────────────────────────────────────────────
    "it": {
        1: [
            "Software Engineer", "Softwareentwickler", "Backend Developer",
            "Frontend Developer", "Full Stack Developer", "DevOps Engineer",
            "Data Engineer", "Data Scientist", "Cloud Engineer",
            "IT Consultant", "SAP Berater", "Scrum Master",
            "Product Owner", "IT Projektleiter", "Systemadministrator",
        ],
        2: [
            "Python Developer", "Java Developer", ".NET Developer",
            "Machine Learning Engineer", "IT Security Engineer",
            "Netzwerkadministrator", "Datenbankadministrator",
            "Mobile Developer", "QA Engineer", "Testmanager",
            "Solutions Architect", "Enterprise Architect",
            "Site Reliability Engineer", "Platform Engineer",
            "IT Support Specialist", "Webentwickler",
        ],
        3: [
            "Embedded Software Engineer", "ABAP Entwickler",
            "Salesforce Developer", "SharePoint Administrator",
            "Blockchain Developer", "Game Developer",
            "Mainframe Entwickler", "ERP Berater",
            "IT Forensiker", "Penetration Tester",
        ],
    },

    # ── Engineering & Technical ────────────────────────────────────────
    "engineering": {
        1: [
            "Maschinenbauingenieur", "Elektroingenieur", "Bauingenieur",
            "Wirtschaftsingenieur", "Verfahrensingenieur", "Konstrukteur",
            "Techniker", "Mechatroniker", "Projektingenieur",
            "Automatisierungstechniker", "Prozessingenieur",
        ],
        2: [
            "Entwicklungsingenieur", "Fertigungsingenieur",
            "Qualitätsingenieur", "Inbetriebnahme Ingenieur",
            "Technischer Zeichner", "CAD Konstrukteur",
            "Versuchsingenieur", "Produktionsingenieur",
            "Umweltingenieur", "Energieingenieur",
            "Fahrzeugtechniker", "Werkstoffingenieur",
        ],
        3: [
            "Akustikingenieur", "Strömungsingenieur",
            "Halbleiteringenieur", "Optikingenieur",
            "Messtechniker", "Kältetechniker",
            "Brandschutzingenieur", "Geotechniker",
        ],
    },

    # ── Business & Management ──────────────────────────────────────────
    "business": {
        1: [
            "Projektmanager", "Project Manager", "Product Manager",
            "Business Analyst", "Unternehmensberater", "Management Consultant",
            "Key Account Manager", "Vertriebsleiter", "Marketing Manager",
            "Geschäftsführer", "Betriebsleiter",
        ],
        2: [
            "Business Development Manager", "Strategieberater",
            "Change Manager", "Prozessmanager", "Portfoliomanager",
            "Innovation Manager", "Programmmanager", "Lean Manager",
            "Transformation Manager", "Abteilungsleiter",
        ],
        3: [
            "Interim Manager", "Restrukturierungsberater",
            "Franchise Manager", "M&A Berater",
        ],
    },

    # ── Finance & Accounting ───────────────────────────────────────────
    "finance": {
        1: [
            "Controller", "Buchhalter", "Finanzbuchhalter",
            "Steuerberater", "Wirtschaftsprüfer", "Bilanzbuchhalter",
            "Finanzanalyst", "Risikomanager", "Treasurer",
        ],
        2: [
            "Lohnbuchhalter", "Kreditorenbuchhalter", "Debitorenbuchhalter",
            "Compliance Manager", "Auditor", "Steuerfachangestellter",
            "Investmentbanker", "Versicherungsmathematiker",
            "Vermögensberater", "Fondsmanager",
        ],
        3: [
            "Kreditanalyst", "Revisor", "Aktuar",
            "Finanzplaner", "Insolvenzverwalter",
        ],
    },

    # ── Sales & Customer Service ───────────────────────────────────────
    "sales": {
        1: [
            "Vertriebsmitarbeiter", "Außendienstmitarbeiter",
            "Kundenberater", "Verkäufer", "Einzelhandelskaufmann",
            "Sachbearbeiter", "Account Manager",
        ],
        2: [
            "Inside Sales Manager", "Technical Sales Manager",
            "Sales Engineer", "Solutions Engineer",
            "Kundendienstmitarbeiter", "Call Center Agent",
            "E-Commerce Manager", "Customer Success Manager",
            "Exportmanager", "Handelsvertreter",
        ],
        3: [
            "Mediaberater", "Werbekaufmann",
            "Messehostess", "Promoter",
        ],
    },

    # ── Human Resources ────────────────────────────────────────────────
    "hr": {
        1: [
            "HR Manager", "Personalreferent", "Recruiter",
            "Personalleiter", "HR Business Partner",
        ],
        2: [
            "Personalberater", "Talent Acquisition Manager",
            "Personalentwickler", "Compensation Manager",
            "HR Controller", "Personaldienstleistungskaufmann",
            "Employer Branding Manager", "People Operations Manager",
        ],
        3: [
            "Headhunter", "Outplacement Berater",
            "Betrieblicher Gesundheitsmanager",
        ],
    },

    # ── Healthcare & Medical ───────────────────────────────────────────
    "healthcare": {
        1: [
            "Arzt", "Facharzt", "Assistenzarzt",
            "Krankenpfleger", "Pflegefachkraft", "Altenpfleger",
            "Physiotherapeut", "Medizinische Fachangestellte",
            "Apotheker", "Zahnarzt",
        ],
        2: [
            "Oberarzt", "Chefarzt", "Stationsleitung",
            "Ergotherapeut", "Logopäde", "Hebamme",
            "Rettungssanitäter", "Notfallsanitäter",
            "Psychotherapeut", "Medizintechniker",
            "Pharmazeutisch-technischer Assistent",
            "Operationstechnischer Assistent",
        ],
        3: [
            "Pathologe", "Radiologe", "Anästhesist",
            "Augenoptiker", "Hörakustiker", "Orthopädietechniker",
            "Tierheilpraktiker", "Podologe",
        ],
    },

    # ── Trades & Craft (Handwerk) ──────────────────────────────────────
    "trades": {
        1: [
            "Elektriker", "Elektroniker", "Industriemechaniker",
            "Anlagenmechaniker", "KFZ-Mechatroniker", "Schlosser",
            "Schweißer", "Tischler", "Maler", "Dachdecker",
        ],
        2: [
            "Klempner", "Installateur", "Heizungsbauer",
            "Zimmermann", "Maurer", "Fliesenleger",
            "Metallbauer", "Werkzeugmacher", "Feinmechaniker",
            "CNC-Fräser", "Dreher", "Zerspanungsmechaniker",
            "Gebäudereiniger", "Glasreiniger",
        ],
        3: [
            "Goldschmied", "Uhrmacher", "Orgelbauer",
            "Steinmetz", "Kürschner", "Sattler",
            "Glaser", "Stuckateur",
        ],
    },

    # ── Logistics & Transport ──────────────────────────────────────────
    "logistics": {
        1: [
            "LKW-Fahrer", "Lagerist", "Speditionskaufmann",
            "Logistikplaner", "Disponent", "Staplerfahrer",
            "Supply Chain Manager", "Einkäufer",
        ],
        2: [
            "Fuhrparkmanager", "Zolldeklarant",
            "Hafenlogistiker", "Kurier", "Paketzusteller",
            "Berufskraftfahrer", "Busfahrer", "Lokführer",
            "Schifffahrtskaufmann", "Luftverkehrskaufmann",
        ],
        3: [
            "Fluglotse", "Binnenschiffer",
            "Eisenbahner", "Rangierer",
        ],
    },

    # ── Education & Social ─────────────────────────────────────────────
    "education": {
        1: [
            "Erzieher", "Lehrer", "Sozialarbeiter",
            "Sozialpädagoge", "Pädagogische Fachkraft",
        ],
        2: [
            "Dozent", "Schulleiter", "Sonderpädagoge",
            "Integrationshelfer", "Kitaleitung",
            "Nachhilfelehrer", "Bildungsreferent",
            "Schulsozialarbeiter", "Jugendbetreuer",
        ],
        3: [
            "Museumspädagoge", "Waldorflehrer",
            "Sprachlehrer", "Musikpädagoge",
        ],
    },

    # ── Legal ──────────────────────────────────────────────────────────
    "legal": {
        1: [
            "Rechtsanwalt", "Jurist", "Notar",
            "Rechtsanwaltsfachangestellter",
        ],
        2: [
            "Syndikusrechtsanwalt", "Rechtsfachwirt",
            "Patentanwalt", "Datenschutzbeauftragter",
            "Compliance Officer", "Vertragsmanager",
        ],
        3: [
            "Gerichtsvollzieher", "Mediator",
            "Insolvenzverwalter",
        ],
    },

    # ── Science & Research ─────────────────────────────────────────────
    "science": {
        1: [
            "Chemiker", "Biologe", "Physiker",
            "Laborant", "Chemielaborant",
        ],
        2: [
            "Biochemiker", "Biotechnologe", "Pharmazeut",
            "Materialwissenschaftler", "Geologe",
            "Lebensmitteltechnologe", "Forschungsingenieur",
            "Laborleiter", "Studienassistent",
        ],
        3: [
            "Astrophysiker", "Meeresbiologe",
            "Meteorologe", "Archäologe",
        ],
    },

    # ── Public Administration ──────────────────────────────────────────
    "public_sector": {
        1: [
            "Verwaltungsfachangestellter", "Sachbearbeiter Öffentlicher Dienst",
            "Beamter", "Stadtplaner",
        ],
        2: [
            "Verwaltungswirt", "Finanzbeamter",
            "Polizist", "Feuerwehrmann",
            "Zollbeamter", "Standesbeamter",
            "Bauamtsmitarbeiter", "Ordnungsamt",
        ],
        3: [
            "Diplomat", "Entwicklungshelfer",
            "Richter",
        ],
    },

    # ── Hospitality, Food & Tourism ────────────────────────────────────
    "hospitality": {
        1: [
            "Koch", "Hotelfachmann", "Restaurantfachmann",
            "Bäcker", "Konditor",
        ],
        2: [
            "Küchenchef", "Hoteldirektor", "Barkeeper",
            "Sommelier", "Touristikkaufmann",
            "Reiseleiter", "Eventmanager",
            "Fleischer", "Fachkraft Systemgastronomie",
        ],
        3: [
            "Braumeister", "Winzer", "Diätkoch",
            "Kreuzfahrtdirektor",
        ],
    },

    # ── Creative & Media ───────────────────────────────────────────────
    "creative": {
        1: [
            "Grafikdesigner", "UX Designer", "UI Designer",
            "Mediengestalter", "Redakteur",
        ],
        2: [
            "Art Director", "Texter", "Content Manager",
            "Fotograf", "Videograf", "Motion Designer",
            "Social Media Manager", "PR Manager",
            "Kommunikationsdesigner", "Webdesigner",
        ],
        3: [
            "Illustrator", "Typograf", "Bühnenbildner",
            "Maskenbildner", "Kostümbildner",
        ],
    },

    # ── Agriculture & Environment ──────────────────────────────────────
    "agriculture": {
        1: [
            "Landwirt", "Gärtner", "Forstwirt",
            "Tierpfleger",
        ],
        2: [
            "Agrarwissenschaftler", "Winzer", "Fischwirt",
            "Umweltschutztechniker", "Landschaftsarchitekt",
            "Schädlingsbekämpfer", "Pferdewirt",
        ],
        3: [
            "Imker", "Revierjäger", "Müller",
        ],
    },

    # ── Insurance & Banking ────────────────────────────────────────────
    "insurance_banking": {
        1: [
            "Bankkaufmann", "Versicherungskaufmann",
            "Finanzberater", "Kreditberater",
        ],
        2: [
            "Schadensregulierer", "Versicherungsmakler",
            "Anlageberater", "Baufinanzierungsberater",
            "Filialleiter Bank", "Privatkundenberater",
        ],
        3: [
            "Hypothekenberater", "Bausparkassenberater",
        ],
    },

    # ── Real Estate & Construction ─────────────────────────────────────
    "real_estate": {
        1: [
            "Immobilienmakler", "Immobilienverwalter",
            "Bauleiter", "Architekt",
        ],
        2: [
            "Projektentwickler Immobilien", "Facility Manager",
            "Bauzeichner", "Vermessungsingenieur",
            "Gebäudetechniker", "Property Manager",
        ],
        3: [
            "Gutachter Immobilien", "Denkmalpfleger",
        ],
    },

    # ── Automotive (strong German sector) ──────────────────────────────
    "automotive": {
        1: [
            "KFZ-Mechaniker", "Fahrzeugingenieur",
            "Automobilkaufmann", "Fahrzeuglackierer",
        ],
        2: [
            "Fahrzeugentwickler", "Motorenentwickler",
            "Karosseriebauer", "Fahrzeugelektriker",
            "Technischer Prüfer", "Homologationsingenieur",
            "Testfahrer", "Serviceberater KFZ",
        ],
        3: [
            "Sachverständiger KFZ", "Kfz-Prüfingenieur",
        ],
    },

    # ── Energy & Utilities ─────────────────────────────────────────────
    "energy": {
        1: [
            "Energieberater", "Elektrotechniker",
            "Anlagenmechaniker SHK", "Solartechniker",
        ],
        2: [
            "Windkrafttechniker", "Netzingenieur",
            "Kraftwerksingenieur", "Energiemanager",
            "Smart Grid Ingenieur", "Wasserwirtschaftler",
        ],
        3: [
            "Kernkrafttechniker", "Geothermie-Ingenieur",
        ],
    },
}

SECTOR_NAMES: list[str] = list(SECTORS.keys())

# ---------------------------------------------------------------------------
# GERMAN CITIES - organized by population tier
# ---------------------------------------------------------------------------

# Tier 1: Top 15 (500K+ or major economic centers)
_CITIES_TIER_1: list[tuple[str, int]] = [
    ("Berlin", 100), ("Hamburg", 100), ("München", 100),
    ("Köln", 100), ("Frankfurt am Main", 100), ("Stuttgart", 100),
    ("Düsseldorf", 100), ("Leipzig", 100), ("Dortmund", 100),
    ("Essen", 100), ("Bremen", 100), ("Dresden", 100),
    ("Hannover", 100), ("Nürnberg", 100), ("Remote", 200),
]

# Tier 2: Major cities (200K-500K)
_CITIES_TIER_2: list[tuple[str, int]] = [
    ("Duisburg", 75), ("Bochum", 75), ("Wuppertal", 75),
    ("Bielefeld", 75), ("Bonn", 75), ("Münster", 75),
    ("Mannheim", 75), ("Karlsruhe", 75), ("Augsburg", 75),
    ("Wiesbaden", 75), ("Mönchengladbach", 75), ("Gelsenkirchen", 75),
    ("Aachen", 75), ("Braunschweig", 75), ("Kiel", 75),
    ("Chemnitz", 75), ("Halle", 75), ("Magdeburg", 75),
    ("Freiburg", 75), ("Krefeld", 75), ("Mainz", 75),
    ("Lübeck", 75), ("Erfurt", 75), ("Rostock", 75),
]

# Tier 3: Smaller cities & important economic hubs (100K-200K)
_CITIES_TIER_3: list[tuple[str, int]] = [
    ("Oberhausen", 50), ("Hagen", 50), ("Kassel", 50),
    ("Saarbrücken", 50), ("Hamm", 50), ("Mülheim", 50),
    ("Ludwigshafen", 50), ("Potsdam", 50), ("Oldenburg", 50),
    ("Osnabrück", 50), ("Leverkusen", 50), ("Heidelberg", 50),
    ("Solingen", 50), ("Darmstadt", 50), ("Paderborn", 50),
    ("Regensburg", 50), ("Ingolstadt", 50), ("Würzburg", 50),
    ("Wolfsburg", 50), ("Göttingen", 50), ("Ulm", 50),
    ("Heilbronn", 50), ("Offenbach", 50), ("Pforzheim", 50),
    ("Reutlingen", 50), ("Bottrop", 50), ("Trier", 50),
    ("Recklinghausen", 50), ("Bremerhaven", 50), ("Jena", 50),
    ("Erlangen", 50), ("Bergisch Gladbach", 50), ("Remscheid", 50),
    ("Moers", 50), ("Siegen", 50), ("Salzgitter", 50),
    ("Cottbus", 50), ("Hildesheim", 50),
]


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def get_terms(
    tier: int = 1,
    sectors: list[str] | None = None,
    language: str | None = None,
) -> list[str]:
    """Return deduplicated job title list filtered by tier and sector.

    Args:
        tier: Maximum tier to include (1=high-volume only, 2=+medium, 3=all).
        sectors: Optional list of sector keys to filter by. None = all sectors.
        language: Optional 'de' or 'en' to filter by language. None = both.

    Returns:
        Flat deduplicated list of job title search terms.
    """
    target_sectors = sectors or SECTOR_NAMES
    seen = set()
    result = []

    for sector_key in target_sectors:
        sector = SECTORS.get(sector_key, {})
        for t in range(1, tier + 1):
            for term in sector.get(t, []):
                if language == "de" and _is_english(term):
                    continue
                if language == "en" and not _is_english(term):
                    continue
                lower = term.lower()
                if lower not in seen:
                    seen.add(lower)
                    result.append(term)

    return result


def get_terms_for_source(source_name: str) -> list[str]:
    """Return appropriate term list based on source characteristics.

    - German-focused sources (arbeitsamt): tier 2, all sectors
    - International sources (adzuna, reed): tier 1, mixed language
    - Paid/limited sources (serpapi, oxylabs, indeed): tier 1 only
    """
    if source_name == "arbeitsamt":
        # German government API - use German terms, broad coverage
        return get_terms(tier=2, language="de")
    elif source_name in ("adzuna", "reed"):
        # International APIs - English-friendly, moderate breadth
        return get_terms(tier=1)
    elif source_name in ("serpapi", "oxylabs", "indeed"):
        # Paid/limited APIs - keep lean, tier 1 only
        return get_terms(tier=1)
    else:
        # Default: tier 1 all sectors
        return get_terms(tier=1)


def get_german_cities(tier: int = 1) -> list[tuple[str, int]]:
    """Return German cities as (name, radius_km) tuples.

    Args:
        tier: Maximum tier to include (1=top 15, 2=+major, 3=+all 100K+ cities).
    """
    cities = list(_CITIES_TIER_1)
    if tier >= 2:
        cities.extend(_CITIES_TIER_2)
    if tier >= 3:
        cities.extend(_CITIES_TIER_3)
    return cities


def _is_english(term: str) -> bool:
    """Heuristic: if a term contains common English job words, treat it as English."""
    english_markers = {
        "engineer", "developer", "manager", "consultant", "analyst",
        "architect", "designer", "lead", "owner", "specialist",
        "officer", "master", "agent", "success",
    }
    words = {w.lower() for w in term.split()}
    return bool(words & english_markers)
