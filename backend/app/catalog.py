"""Curated official-source fallback for /build-task.

Live search (wigolo via npx) needs network + node and can fail or return
nothing; this catalog keeps the citizen build flow working with vetted
official portals, keyword-matched against the task text. Entries must be
HTTPS + .gov.in/.nic.in (the endpoint's _validate_fetch_url enforces it).
"""

CATALOG = [
    {"keywords": ("business", "udyam", "msme", "udyog", "entrepreneur",
                  "shop", "store", "trader", "startup"),
     "urls": ["https://udyamregistration.gov.in/",
              "https://www.gst.gov.in/",
              "https://www.mca.gov.in/"]},
    {"keywords": ("gst", "tax", "income", "filing", "itr", "pan"),
     "urls": ["https://www.gst.gov.in/",
              "https://www.incometax.gov.in/"]},
    {"keywords": ("company", "roc", "incorporate", "llp", "director"),
     "urls": ["https://www.mca.gov.in/"]},
    {"keywords": ("driving", "licence", "license", "vehicle", "rto",
                  "registration certificate", "parivahan", "rc book"),
     "urls": ["https://parivahan.gov.in/"]},
    {"keywords": ("passport", "visa", "foreign"),
     "urls": ["https://www.passportindia.gov.in/"]},
    {"keywords": ("food", "fssai", "restaurant", "hotel", "eatery"),
     "urls": ["https://fssai.gov.in/"]},
    {"keywords": ("pension", "provident", "epf", "pf ", "gratuity",
                  "retirement"),
     "urls": ["https://www.epfindia.gov.in/"]},
    {"keywords": ("scholarship", "stipend", "student", "education fee"),
     "urls": ["https://scholarships.gov.in/"]},
    {"keywords": ("farmer", "agriculture", "kisan", "crop", "kharif"),
     "urls": ["https://pmkisan.gov.in/"]},
    {"keywords": ("health", "ayushman", "insurance", "hospital", "medical"),
     "urls": ["https://pmjay.gov.in/"]},
    {"keywords": ("job card", "mgnrega", "nrega", "wages", "employment"),
     "urls": ["https://nrega.nic.in/"]},
    {"keywords": ("voter", "election", "epic"),
     "urls": ["https://voters.eci.gov.in/"]},
    {"keywords": ("scheme", "welfare", "benefit", "subsidy", "grant"),
     "urls": ["https://www.myscheme.gov.in/"]},
    # --- Mumbai / Maharashtra vertical (research P0 sources, 2026-10-04) ---
    {"keywords": ("shop", "establishment", "trade licence", "trade license",
                  "hawker", "hoarding", "advertisement licence",
                  "municipal", "corporation", "local body",
                  "birth certificate", "death certificate",
                  "marriage certificate", "property tax",
                  "building permission", "completion certificate",
                  "fire licence", "signboard"),
     "urls": ["https://www.mcgm.gov.in/",
              "https://aaplesarkar.mahaonline.gov.in/en/CommonForm/ViewAllServices"]},
    {"keywords": ("mumbai", "maharashtra"),
     "urls": ["https://www.mcgm.gov.in/",
              "https://aaplesarkar.mahaonline.gov.in/en/CommonForm/ViewAllServices"]},
    {"keywords": ("aaple sarkar", "maharashtra state", "rti ",
                  "family card", "ration card"),
     "urls": ["https://aaplesarkar.mahaonline.gov.in/en/CommonForm/ViewAllServices"]},
    # --- Delhi e-District certificates ---
    {"keywords": ("delhi", "income certificate", "caste certificate",
                  "domicile certificate", "disability certificate"),
     "urls": ["https://edistrict.delhi.gov.in/in/en/Public/Services.html"]},
]


def fallback_sources(task: str, service_type: str = "", state: str = "",
                     max_urls: int = 3) -> list[str]:
    text = f"{task} {service_type} {state}".lower()
    ranked = []
    for i, entry in enumerate(CATALOG):
        hits = sum(1 for kw in entry["keywords"] if kw in text)
        if hits:
            ranked.append((-hits, i, entry["urls"]))
    urls: list[str] = []
    for _, _, entry_urls in sorted(ranked):
        for u in entry_urls:
            if u not in urls:
                urls.append(u)
    return urls[:max_urls]
