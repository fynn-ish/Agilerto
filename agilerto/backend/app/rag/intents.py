"""Understands what a question is about (English, Tagalog, Taglish) so retrieval can pick the right records.
Pure keyword matching: fast, works offline, needs no model."""
import re
from dataclasses import dataclass, field


def normalize(text: str) -> str:
    text = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", text).strip()


def _rx(words):
    alt = "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))
    return re.compile(rf"(?<![a-z])(?:{alt})(?![a-z])")


FACILITY_RX = {
    "hospital": _rx(["hospital", "hospitals", "ospital", "clinic", "klinika", "medical center", "doctor", "doktor",
                     "emergency room", "rhu", "health center"]),
    "evacuation_center": _rx(["evacuation center", "evacuation centers", "evacuation centre", "evacuation", "evac",
                              "shelter", "lilikasan", "kanlungan", "evacuation site"]),
    "fire_station": _rx(["fire station", "fire stations", "firefighter", "firefighters", "fire truck", "bfp",
                         "bumbero", "bombero"]),
    "police_station": _rx(["police station", "police", "pulis", "pnp"]),
}

HAZARD_RX = {
    "earthquake": _rx(["earthquake", "earthquakes", "quake", "quakes", "lindol", "lumilindol", "lumindol", "aftershock"]),
    "typhoon": _rx(["typhoon", "typhoons", "bagyo", "storm", "hurricane", "signal no"]),
    "flood": _rx(["flood", "floods", "flooding", "baha", "binabaha", "bumabaha"]),
    "fire": _rx(["fire", "fires", "sunog", "nasusunog"]),
    "landslide": _rx(["landslide", "landslides", "guho", "pagguho", "mudslide"]),
    "volcanic": _rx(["volcano", "volcanic", "bulkan", "ashfall", "ash fall", "taal", "eruption"]),
}

WEATHER_RX = _rx(["weather", "panahon", "rain", "raining", "ulan", "umuulan", "temperature", "temp", "init", "lamig",
                  "wind", "windy", "hangin", "forecast", "humidity", "cloudy", "mainit", "malamig"])
QUAKE_RX = _rx(["earthquake", "earthquakes", "quake", "quakes", "lindol", "lumilindol", "lumindol", "magnitude",
                "aftershock", "phivolcs", "tremor", "yanig"])
HOTLINE_RX = _rx(["hotline", "hotlines", "emergency number", "emergency numbers", "phone number", "contact number",
                  "numero", "telepono", "call", "tawag", "tumawag", "911", "red cross", "ndrrmc", "mdrrmo", "drrmo"])
HOWTO_RX = _rx(["what should i do", "what do i do", "what to do", "how do i", "how to", "ano ang gagawin",
                "anong gagawin", "ano gagawin", "paano", "safety", "tips", "precaution", "precautions", "prepare",
                "preparation", "paghahanda", "handa", "guide", "steps"])
NEARBY_RX = _rx(["near me", "nearby", "nearest", "closest", "near", "malapit", "pinakamalapit", "around me",
                 "sa paligid", "where", "saan", "nasaan"])
PHASE_RX = {
    "before": _rx(["before", "prepare", "preparation", "paghahanda", "bago", "handa"]),
    "after": _rx(["after", "afterwards", "pagkatapos", "matapos", "pagkatapos ng"]),
}


@dataclass
class Intents:
    facility_types: list = field(default_factory=list)
    weather: bool = False
    quake: bool = False
    hotline: bool = False
    hazards: list = field(default_factory=list)
    phase: str | None = None
    nearby: bool = False
    howto: bool = False

    @property
    def matched_other(self) -> bool:
        return bool(self.weather or self.quake or self.hazards or self.hotline)

    @property
    def matched(self) -> bool:
        return bool(self.facility_types or self.weather or self.quake or self.hotline or self.hazards or self.nearby)


def detect(question: str) -> Intents:
    q = normalize(question)
    types = [t for t, rx in FACILITY_RX.items() if rx.search(q)]

    # "fire station" must not also count as the hazard "fire"
    stripped = q
    for rx in FACILITY_RX.values():
        stripped = rx.sub(" ", stripped)
    hazards = [h for h, rx in HAZARD_RX.items() if rx.search(stripped)]

    howto = bool(HOWTO_RX.search(q))
    phase = next((p for p, rx in PHASE_RX.items() if rx.search(q)), None)

    weather = bool(WEATHER_RX.search(q))
    quake = bool(QUAKE_RX.search(stripped)) and not howto          # "what to do in an earthquake" wants the guide, not the quake list
    if not howto and ("typhoon" in hazards or "flood" in hazards):
        weather = True                                              # rain and wind data are relevant to these

    return Intents(
        facility_types=types, weather=weather, quake=quake, hotline=bool(HOTLINE_RX.search(q)),
        hazards=hazards, phase=phase, nearby=bool(NEARBY_RX.search(q)), howto=howto,
    )


# ---------- full-text search query ----------
STOPWORDS = set("""
a an the is are was were be been am do does did can could would should will shall may might must of in on at to for from
by with and or but if so as it its this that these those there here what which who whom whose when where why how i me my
we us our you your he she they them their please tell show give need want know any some about near nearest nearby closest
help now today currently current right just also very more most than then too not no yes ok okay hi hello po ba ang ng sa
na ay mga yung ung ko ako namin natin kami kayo ikaw mo niyo nyo ano anong paano saan nasaan may meron mayroon dito doon
ngayon para lang naman kung at o ito iyan yan pa din rin bang nang kay kanino sino
pinakamalapit malapit kanina during habang kapag pag gagawin gawin bad
""".split())

SYNONYMS = {
    "ospital": ["hospital"], "klinika": ["clinic"], "lindol": ["earthquake"], "lumilindol": ["earthquake"],
    "lumindol": ["earthquake"], "yanig": ["earthquake"], "sunog": ["fire"], "bagyo": ["typhoon"], "baha": ["flood"],
    "binabaha": ["flood"], "guho": ["landslide"], "pagguho": ["landslide"], "bulkan": ["volcanic", "volcano"],
    "pulis": ["police"], "bumbero": ["fire"], "bombero": ["fire"], "ulan": ["rain"], "umuulan": ["rain"],
    "panahon": ["weather"], "hangin": ["wind"], "init": ["temperature"], "evac": ["evacuation"],
    "lilikasan": ["evacuation"], "kanlungan": ["evacuation", "shelter"], "telepono": ["phone"],
    "numero": ["number", "hotline"], "tawag": ["call"], "paghahanda": ["prepare"], "pagkatapos": ["after"],
}


def fts_query(question: str) -> str | None:
    """Turn a question into an FTS5 OR-query: stopwords removed, Tagalog terms mapped to the English words
    our records use, long words matched as prefixes (hospital/hospitals)."""
    terms: list[str] = []
    for tok in re.findall(r"[a-z0-9]+", normalize(question)):
        if tok in STOPWORDS:
            continue
        if len(tok) < 3 and not tok.isdigit():
            continue
        for t in [tok, *SYNONYMS.get(tok, [])]:
            if t not in terms:
                terms.append(t)
    if not terms:
        return None
    return " OR ".join(f'"{t}"*' if len(t) >= 4 else f'"{t}"' for t in terms)
