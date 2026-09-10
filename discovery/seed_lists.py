"""
discovery/seed_lists.py - Hardcoded seed list of known companies per ATS.

Run: python -m discovery.seed_lists
Idempotent: UNIQUE(ats_type, ats_slug) handles duplicates.
"""

import logging

from sources.ats._registry import upsert_company

log = logging.getLogger(__name__)


# ── Greenhouse (confirmed working via proof-of-concept) ──────────────────────

GREENHOUSE_SEEDS = [
    # German/European companies
    ('HelloFresh', 'hellofresh', 'hellofresh.com', 'DE'),
    ('N26', 'n26', 'n26.com', 'DE'),
    ('Celonis', 'celonis', 'celonis.com', 'DE'),
    ('FlixBus', 'flix', 'flixbus.com', 'DE'),
    ('Trade Republic', 'traderepublicbank', 'traderepublic.com', 'DE'),
    ('Contentful', 'contentful', 'contentful.com', 'DE'),
    ('SumUp', 'sumup', 'sumup.com', 'DE'),
    ('Wolt', 'wolt', 'wolt.com', 'FI'),
    ('Raisin', 'raisin', 'raisin.com', 'DE'),
    ('commercetools', 'commercetools', 'commercetools.com', 'DE'),
    ('Grover', 'grover', 'grover.com', 'DE'),
    # Major global companies (jobs may include DE locations)
    ('Databricks', 'databricks', 'databricks.com', 'US'),
    ('Cloudflare', 'cloudflare', 'cloudflare.com', 'US'),
    ('Stripe', 'stripe', 'stripe.com', 'US'),
    ('Coinbase', 'coinbase', 'coinbase.com', 'US'),
    ('Airbnb', 'airbnb', 'airbnb.com', 'US'),
    ('Elastic', 'elastic', 'elastic.co', 'US'),
    ('Figma', 'figma', 'figma.com', 'US'),
    ('Lyft', 'lyft', 'lyft.com', 'US'),
    ('Dropbox', 'dropbox', 'dropbox.com', 'US'),
    ('Instacart', 'instacart', 'instacart.com', 'US'),
    ('GitLab', 'gitlab', 'gitlab.com', 'US'),
    ('Robinhood', 'robinhood', 'robinhood.com', 'US'),
    ('Pinterest', 'pinterest', 'pinterest.com', 'US'),
    ('Discord', 'discord', 'discord.com', 'US'),
    ('Twitch', 'twitch', 'twitch.tv', 'US'),
    ('Datadog', 'datadog', 'datadoghq.com', 'US'),
    ('DoorDash', 'doordash', 'doordash.com', 'US'),
    ('Brex', 'brex', 'brex.com', 'US'),
    ('Plaid', 'plaid', 'plaid.com', 'US'),
    ('Gusto', 'gusto', 'gusto.com', 'US'),
    ('Airtable', 'airtable', 'airtable.com', 'US'),
    ('Webflow', 'webflow', 'webflow.com', 'US'),
    ('Toast', 'toast', 'toasttab.com', 'US'),
    ('Duolingo', 'duolingo', 'duolingo.com', 'US'),
    ('Reddit', 'reddit', 'reddit.com', 'US'),
    ('Canva', 'canva', 'canva.com', 'AU'),
    ('Wise', 'wise', 'wise.com', 'UK'),
    ('Revolut', 'revolut', 'revolut.com', 'UK'),
    ('Delivery Hero', 'deliveryhero', 'deliveryhero.com', 'DE'),
    ('Zalando', 'zalando', 'zalando.de', 'DE'),
    ('AUTO1 Group', 'auto1-group', 'auto1-group.com', 'DE'),
    ('TeamViewer', 'teamviewer', 'teamviewer.com', 'DE'),
    ('Scout24', 'scout24', 'scout24.com', 'DE'),
    ('Trivago', 'trivago', 'trivago.com', 'DE'),
    ('About You', 'aboutyou', 'aboutyou.com', 'DE'),
    ('Personio', 'personiogmbh', 'personio.com', 'DE'),
    ('Mambu', 'mambu', 'mambu.com', 'DE'),
    ('Forto', 'forto', 'forto.com', 'DE'),
    ('Sennder', 'sennder', 'sennder.com', 'DE'),
    ('Omio', 'omio', 'omio.com', 'DE'),
    ('Ecosia', 'ecosia', 'ecosia.org', 'DE'),
]

# ── Lever (confirmed working) ────────────────────────────────────────────────

LEVER_SEEDS = [
    ('Spotify', 'spotify', 'spotify.com', 'SE'),
    ('Palantir', 'palantir', 'palantir.com', 'US'),
    ('Netflix', 'netflix', 'netflix.com', 'US'),
    ('Atlassian', 'atlassian', 'atlassian.com', 'AU'),
    ('TIER Mobility', 'tier-mobility', 'tier.app', 'DE'),
    ('GoTo', 'goto', 'goto.com', 'US'),
    ('Handshake', 'handshake', 'joinhandshake.com', 'US'),
    ('Snyk', 'snyk', 'snyk.io', 'UK'),
    ('HashiCorp', 'hashicorp', 'hashicorp.com', 'US'),
]

# ── Ashby (confirmed working) ────────────────────────────────────────────────

ASHBY_SEEDS = [
    ('Deel', 'deel', 'deel.com', 'US'),
    ('Notion', 'notion', 'notion.so', 'US'),
    ('Ramp', 'ramp', 'ramp.com', 'US'),
    ('Watershed', 'watershed', 'watershed.com', 'US'),
    ('Linear', 'linear', 'linear.app', 'US'),
    ('Vercel', 'vercel', 'vercel.com', 'US'),
    ('Retool', 'retool', 'retool.com', 'US'),
    ('Supabase', 'supabase', 'supabase.com', 'US'),
    ('Anthropic', 'anthropic', 'anthropic.com', 'US'),
    ('Anduril', 'anduril', 'anduril.com', 'US'),
]

# ── Personio (confirmed working - DACH market focus) ─────────────────────────

PERSONIO_SEEDS = [
    ('tonies', 'tonies', 'tonies.com', 'DE'),
    ('Vivid Money', 'vivid', 'vivid.money', 'DE'),
    ('LIQID', 'liqid', 'liqid.de', 'DE'),
    ('Merantix', 'merantix', 'merantix.com', 'DE'),
    ('CLARK', 'clark', 'clark.de', 'DE'),
    ('Homeday', 'homeday', 'homeday.de', 'DE'),
    ('CHECK24', 'check24', 'check24.de', 'DE'),
    ('Circula', 'circula', 'circula.com', 'DE'),
    ('Ada Health', 'ada', 'ada.com', 'DE'),
    ('Volocopter', 'volocopter', 'volocopter.com', 'DE'),
    ('Ecosia', 'ecosia', 'ecosia.org', 'DE'),
    ('smava', 'smava', 'smava.de', 'DE'),
    ('Tandem', 'tandem', 'tandem.net', 'DE'),
    ('Personio', 'personio', 'personio.com', 'DE'),
    ('Kaia Health', 'kaia-health', 'kaiahealth.com', 'DE'),
    ('Haiilo', 'haiilo', 'haiilo.com', 'DE'),
    ('bunch', 'bunch', 'bunch.ai', 'DE'),
]

# ── SmartRecruiters (to be expanded via discovery) ───────────────────────────

SMARTRECRUITERS_SEEDS = [
    ('Visa', 'visa', 'visa.com', 'US'),
    ('Bosch', 'BoschGroup', 'bosch.com', 'DE'),
    ('Continental', 'continental', 'continental.com', 'DE'),
    ('McDonald\'s', 'McDonaldsCorporation', 'mcdonalds.com', 'US'),
]


# ── Workable (widget API - to be expanded via discovery) ─────────────────────

WORKABLE_SEEDS = [
    ('CXG', 'cxg', 'cxg.com', 'FR'),
]

# ── Recruitee (strong in DACH/Benelux) ───────────────────────────────────────

RECRUITEE_SEEDS = [
    ('Wacom Europe', 'wacomeurope', 'wacom.com', 'DE'),
    ('KPMG', 'kpmg', 'kpmg.com', 'NL'),
    ('EY', 'ey', 'ey.com', 'UK'),
    ('Accenture', 'accenture', 'accenture.com', 'US'),
]

# ── d.vinci (Hamburg-based, German market) ───────────────────────────────────

DVINCI_SEEDS = [
    ('Henkell Freixenet', 'henkell-freixenet', 'henkell-freixenet.com', 'DE'),
]

# ── Pinpoint (UK/Europe focus, compensation data) ───────────────────────────

PINPOINT_SEEDS = [
    ('Pinpoint', 'workwithus', 'pinpointhq.com', 'UK'),
    ('Grant Thornton', 'grantthornton', 'grantthornton.co.uk', 'UK'),
    ('Improbable', 'improbable', 'improbable.io', 'UK'),
]


# ── Workday (paginated POST API - career_url is required per company) ─────────
# Format: (name, slug, career_url, domain, country)
# career_url is the full Workday API base: https://{co}.{wdN}.myworkdayjobs.com/wday/cxs/{co}/{site}

WORKDAY_SEEDS = [
    # German companies
    ('Deutsche Bank', 'db', 'https://db.wd3.myworkdayjobs.com/wday/cxs/db/DBWebsite', 'db.com', 'DE'),
    ('Deutsche Telekom', 'tmobile', 'https://tmobile.wd1.myworkdayjobs.com/wday/cxs/tmobile/External', 'telekom.com', 'DE'),
    ('Sartorius', 'sartorius', 'https://sartorius.wd3.myworkdayjobs.com/wday/cxs/sartorius/sartoriuscareers', 'sartorius.com', 'DE'),
    ('KION Group', 'kiongroup', 'https://kiongroup.wd3.myworkdayjobs.com/wday/cxs/kiongroup/KION_SCS', 'kiongroup.com', 'DE'),
    ('Armacell', 'armacell', 'https://armacell.wd3.myworkdayjobs.com/wday/cxs/armacell/career-armacell', 'armacell.com', 'DE'),
    ('WTS', 'wts', 'https://wts.wd3.myworkdayjobs.com/wday/cxs/wts/wts', 'wts.com', 'DE'),
    ('Berner Group', 'bernergroup', 'https://bernergroup.wd3.myworkdayjobs.com/wday/cxs/bernergroup/careers_berner_group', 'bfriendsshop.com', 'DE'),
    ('EMBL', 'embl', 'https://embl.wd103.myworkdayjobs.com/wday/cxs/embl/EMBL', 'embl.org', 'DE'),
    # European companies with DE presence
    ('Airbus', 'ag', 'https://ag.wd3.myworkdayjobs.com/wday/cxs/ag/Airbus', 'airbus.com', 'DE'),
    ('Shell', 'shell', 'https://shell.wd3.myworkdayjobs.com/wday/cxs/shell/ShellCareers', 'shell.com', 'NL'),
    ('BDR Thermea', 'bdrthermea', 'https://bdrthermea.wd103.myworkdayjobs.com/wday/cxs/bdrthermea/External', 'bdrthermea.com', 'NL'),
    ('Valmet', 'valmet', 'https://valmet.wd103.myworkdayjobs.com/wday/cxs/valmet/External', 'valmet.com', 'FI'),
    ('Roquette', 'roquette', 'https://roquette.wd3.myworkdayjobs.com/wday/cxs/roquette/External', 'roquette.com', 'FR'),
    ('CMS Law', 'cmno', 'https://cmno.wd3.myworkdayjobs.com/wday/cxs/cmno/CMS_Career_Site', 'cms.law', 'DE'),
    ('Frontier Economics', 'frontiereconomics', 'https://frontiereconomics.wd3.myworkdayjobs.com/wday/cxs/frontiereconomics/Frontier_Economics_Careers', 'frontier-economics.com', 'UK'),
    ('Inalfa Roof Systems', 'inalfa', 'https://inalfa.wd3.myworkdayjobs.com/wday/cxs/inalfa/InalfaCareers', 'inalfa.com', 'NL'),
    ('Dentsu', 'dentsuaegis', 'https://dentsuaegis.wd3.myworkdayjobs.com/wday/cxs/dentsuaegis/DAN_GLOBAL', 'dentsu.com', 'JP'),
    ('Alantra', 'alantra', 'https://alantra.wd3.myworkdayjobs.com/wday/cxs/alantra/Alantra', 'alantra.com', 'ES'),
    ('EPSA', 'epsa', 'https://epsa.wd103.myworkdayjobs.com/wday/cxs/epsa/ExternalCareerSite', 'epsa.com', 'FR'),
    # Major multinationals with German operations
    ('GE Vernova', 'gevernova', 'https://gevernova.wd5.myworkdayjobs.com/wday/cxs/gevernova/Vernova_ExternalSite', 'gevernova.com', 'US'),
    ('Accenture', 'accenture', 'https://accenture.wd103.myworkdayjobs.com/wday/cxs/accenture/AccentureCareers', 'accenture.com', 'US'),
    ('NVIDIA', 'nvidia', 'https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite', 'nvidia.com', 'US'),
    ('Skechers', 'skechers', 'https://skechers.wd5.myworkdayjobs.com/wday/cxs/skechers/One-career-site', 'skechers.com', 'US'),
    ('Danaher', 'danaher', 'https://danaher.wd1.myworkdayjobs.com/wday/cxs/danaher/DanaherJobs', 'danaher.com', 'US'),
    ('Adobe', 'adobe', 'https://adobe.wd5.myworkdayjobs.com/wday/cxs/adobe/external_experienced', 'adobe.com', 'US'),
    ('Medtronic', 'medtronic', 'https://medtronic.wd1.myworkdayjobs.com/wday/cxs/medtronic/MedtronicCareers', 'medtronic.com', 'US'),
    ('NTT', 'nttlimited', 'https://nttlimited.wd3.myworkdayjobs.com/wday/cxs/nttlimited/ntt_careers', 'ntt.com', 'JP'),
    ('Kyndryl', 'kyndryl', 'https://kyndryl.wd5.myworkdayjobs.com/wday/cxs/kyndryl/KyndrylProfessionalCareers', 'kyndryl.com', 'US'),
    ('Levi Strauss', 'levistraussandco', 'https://levistraussandco.wd5.myworkdayjobs.com/wday/cxs/levistraussandco/External', 'levistrauss.com', 'US'),
    ('Samsung', 'sec', 'https://sec.wd3.myworkdayjobs.com/wday/cxs/sec/Samsung_Careers', 'samsung.com', 'KR'),
    ('PayPal', 'paypal', 'https://paypal.wd1.myworkdayjobs.com/wday/cxs/paypal/jobs', 'paypal.com', 'US'),
    ('Wolters Kluwer', 'wk', 'https://wk.wd3.myworkdayjobs.com/wday/cxs/wk/External', 'wolterskluwer.com', 'NL'),
    ('Global Payments', 'tsys', 'https://tsys.wd1.myworkdayjobs.com/wday/cxs/tsys/TSYS', 'globalpayments.com', 'US'),
    ('MUFG', 'mufgub', 'https://mufgub.wd3.myworkdayjobs.com/wday/cxs/mufgub/MUFG-Careers', 'mufg.jp', 'JP'),
    ('Smith & Nephew', 'smithnephew', 'https://smithnephew.wd5.myworkdayjobs.com/wday/cxs/smithnephew/External', 'smith-nephew.com', 'UK'),
    ('Intel', 'intel', 'https://intel.wd1.myworkdayjobs.com/wday/cxs/intel/External', 'intel.com', 'US'),
    ('Red Hat', 'redhat', 'https://redhat.wd5.myworkdayjobs.com/wday/cxs/redhat/Jobs', 'redhat.com', 'US'),
    ('Snap', 'snapchat', 'https://snapchat.wd1.myworkdayjobs.com/wday/cxs/snapchat/snap', 'snap.com', 'US'),
    ('Nissan', 'alliance', 'https://alliance.wd3.myworkdayjobs.com/wday/cxs/alliance/nissanjobs', 'nissan.com', 'JP'),
    ('Agilent', 'agilent', 'https://agilent.wd5.myworkdayjobs.com/wday/cxs/agilent/agilent_careers', 'agilent.com', 'US'),
    ('Henry Schein', 'henryschein', 'https://henryschein.wd1.myworkdayjobs.com/wday/cxs/henryschein/External_Careers', 'henryschein.com', 'US'),
    ('Vantage Data Centers', 'vantagedc', 'https://vantagedc.wd1.myworkdayjobs.com/wday/cxs/vantagedc/Vantage', 'vantagedc.com', 'US'),
    ('BeiGene', 'beigene', 'https://beigene.wd5.myworkdayjobs.com/wday/cxs/beigene/BeiGene', 'beigene.com', 'CN'),
    ('CSL', 'csl', 'https://csl.wd1.myworkdayjobs.com/wday/cxs/csl/CSL_External', 'csl.com', 'AU'),
    ('Guidewire', 'guidewire', 'https://guidewire.wd5.myworkdayjobs.com/wday/cxs/guidewire/external', 'guidewire.com', 'US'),
    ('Blackstone', 'blackstone', 'https://blackstone.wd1.myworkdayjobs.com/wday/cxs/blackstone/Blackstone_Careers', 'blackstone.com', 'US'),
    ('AVEVA', 'aveva', 'https://aveva.wd3.myworkdayjobs.com/wday/cxs/aveva/AVEVA_careers', 'aveva.com', 'UK'),
    ('Zoetis', 'zoetis', 'https://zoetis.wd5.myworkdayjobs.com/wday/cxs/zoetis/zoetis', 'zoetis.com', 'US'),
    ('Prologis', 'prologis', 'https://prologis.wd5.myworkdayjobs.com/wday/cxs/prologis/Prologis_External_Careers', 'prologis.com', 'US'),
    ('Unilever', 'unilever', 'https://unilever.wd3.myworkdayjobs.com/wday/cxs/unilever/Unilever_Early_Careers', 'unilever.com', 'UK'),
    ('Uniqlo', 'fastretailing', 'https://fastretailing.wd3.myworkdayjobs.com/wday/cxs/fastretailing/graduates_eu_Uniqlo', 'uniqlo.com', 'JP'),
    ('Galderma', 'galderma', 'https://galderma.wd3.myworkdayjobs.com/wday/cxs/galderma/External', 'galderma.com', 'CH'),
    ('Kraft Heinz', 'heinz', 'https://heinz.wd1.myworkdayjobs.com/wday/cxs/heinz/KraftHeinz_Careers', 'kraftheinzcompany.com', 'US'),
    ('SLR Consulting', 'slrconsulting', 'https://slrconsulting.wd103.myworkdayjobs.com/wday/cxs/slrconsulting/SLRCareers', 'slrconsulting.com', 'UK'),
    ('FICO', 'fico', 'https://fico.wd1.myworkdayjobs.com/wday/cxs/fico/External', 'fico.com', 'US'),
    ('Houlihan Lokey', 'hl', 'https://hl.wd1.myworkdayjobs.com/wday/cxs/hl/Campus', 'hl.com', 'US'),
    ('Johnson Matthey', 'jm', 'https://jm.wd103.myworkdayjobs.com/wday/cxs/jm/External', 'matthey.com', 'UK'),
]


ALL_SEEDS = {
    'greenhouse': GREENHOUSE_SEEDS,
    'lever': LEVER_SEEDS,
    'ashby': ASHBY_SEEDS,
    'personio': PERSONIO_SEEDS,
    'smartrecruiters': SMARTRECRUITERS_SEEDS,
    'workable': WORKABLE_SEEDS,
    'recruitee': RECRUITEE_SEEDS,
    'dvinci': DVINCI_SEEDS,
    'pinpoint': PINPOINT_SEEDS,
    'workday': WORKDAY_SEEDS,
}


def seed_all() -> dict[str, int]:
    """Insert all seed companies into the registry. Returns counts per ATS."""
    counts = {}
    for ats_type, seeds in ALL_SEEDS.items():
        count = 0
        for seed in seeds:
            # Workday uses 5-tuple: (name, slug, career_url, domain, country)
            # All others use 4-tuple: (name, slug, domain, country)
            if len(seed) == 5:
                name, slug, career_url, domain, country = seed
            else:
                name, slug, domain, country = seed
                career_url = None
            upsert_company(
                ats_type=ats_type,
                ats_slug=slug,
                company_name=name,
                domain=domain,
                career_url=career_url,
                country=country,
                discovered_via='seed',
            )
            count += 1
        counts[ats_type] = count
        log.info(f"Seeded {count} companies for {ats_type}")
    return counts


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    print("Seeding company registry...")
    result = seed_all()
    total = sum(result.values())
    print(f"\nDone. Seeded {total} companies:")
    for ats, count in sorted(result.items()):
        print(f"  {ats}: {count}")
