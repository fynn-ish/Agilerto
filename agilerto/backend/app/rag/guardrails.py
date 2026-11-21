"""Safety checks that run BEFORE any AI is involved. They are plain code, so they behave the same
whichever model is installed. The system informs; it never predicts disasters or decides evacuations."""
import re

from .intents import normalize


# ---------- language ----------
_TAGALOG_MARKERS = re.compile(
    r"(?<![a-z])(ba|po|opo|ang|mga|ng|sa|saan|nasaan|ano|anong|paano|malapit|pinakamalapit|yung|ung|ko|namin|natin|"
    r"naman|lang|pwede|puwede|kung|kapag|may|meron|mayroon|dito|ngayon|kanina|bukas|ospital|lindol|bagyo|baha|sunog|"
    r"pulis|tulong|lumikas|ligtas|gagawin|tayo|kami|ako|niyo|nyo|na|ay)(?![a-z])"
)
_STRONG_TAGALOG = re.compile(
    r"(?<![a-z])(ba|po|opo|ang|mga|saan|nasaan|ano|anong|paano|malapit|pinakamalapit|yung|ung|ko|namin|natin|naman|"
    r"ospital|lindol|bagyo|baha|sunog|pulis|tulong|lumikas|gagawin|kanina|bukas|kapag|kami|ako|niyo)(?![a-z])"
)


def language_of(question: str) -> str:
    """'tl' for Tagalog or Taglish, otherwise 'en'."""
    return "tl" if _STRONG_TAGALOG.search(normalize(question)) else "en"


# ---------- refusals: evacuation decisions, safety judgments, predictions ----------
_REFUSALS = [
    ("evacuation", [
        r"\b(should|must|do|shall)\s+(i|we)\b.{0,40}\b(evacuate|leave|go home|stay home|stay put|flee|go back)\b",
        r"\b(need|have|got) to evacuate\b",
        r"\b(is it|are we) time to (evacuate|leave)\b",
        r"\b(dapat|kailangan|kelangan|dapat ba|kailangan ba)\b.{0,30}\b(lumikas|umalis|mag-?evacuate|evacuate)\b",
        r"\b(lumikas|mag-?evacuate|umalis|evacuate)\s+(na\s+)?ba\b",
        r"\bevacuate na\b",
    ]),
    ("safety", [
        r"\b(is|are|am)\s+(it|this|that|we|i|the [a-z ]{2,25}|[a-z]{3,20})\s+(still\s+)?safe\b",
        r"\bis it (ok|okay|alright) to (go|stay|travel|return|drive|swim|go back)\b",
        r"\b(safe|ligtas)\s+ba\b",
        r"\bligtas ba\b",
        r"\bpuwede ba (kaming|akong)? ?(umuwi|bumalik|lumabas|bumiyahe)\b",
    ]),
    ("prediction", [
        r"\bwill (there|it|the|another|a|an)\b.{0,40}\b(earthquake|quake|aftershock|flood|flooding|typhoon|storm|landslide|eruption|erupt|hit|strike|happen)\b",
        r"\bwhen (will|is|does)\b.{0,30}\b(next|another|coming)\b.{0,30}\b(earthquake|quake|typhoon|flood|storm|eruption)\b",
        r"\bis (a|an|the)\s+(earthquake|typhoon|flood|landslide|eruption|storm)\b.{0,25}\b(coming|going to|expected|about to)\b",
        r"\b(predict|prediction|predicting)\b",
        r"\b(lilindol|babaha|bahain|tatama|sasabog|magkakaroon)\b",
        r"\bmag-?aftershock ba\b",
        r"\bkailan (ang )?(susunod|next)\b.{0,25}\b(lindol|bagyo|baha)\b",
    ]),
]
_REFUSAL_RX = [(code, [re.compile(p) for p in pats]) for code, pats in _REFUSALS]


def detect_refusal(question: str) -> str | None:
    """'evacuation' | 'safety' | 'prediction' when the question asks for a decision or a prediction."""
    q = normalize(question)
    for code, rxs in _REFUSAL_RX:
        if any(rx.search(q) for rx in rxs):
            return code
    return None


# ---------- emergencies in progress ----------
_STRONG_EMERGENCY = re.compile(
    r"(?<![a-z])(tulong|saklolo|tulungan|help me|help us|please help|trapped|naipit|nakulong|na-trap|natrap|"
    r"can'?t breathe|cannot breathe|hindi (po )?makahinga|di (po )?makahinga|dumudugo|bleeding|nalulunod|drowning|"
    r"heart attack|inatake|nawalan ng malay|unconscious|nawalan ng ulirat)(?![a-z])"
)
_WEAK_EMERGENCY = re.compile(
    r"(?<![a-z])(may sunog|nasusunog|sunog sa|sunog dito|there'?s a fire|there is a fire|on fire|house is burning|"
    r"lumilindol ngayon|lumilindol na|earthquake right now|earthquake is happening|binabaha na|may baha na|"
    r"rising (flood )?water|may gumuho|nagkaroon ng landslide)(?![a-z])"
)
# Wording that shows the person is asking about a situation, not living one
_INFORMATIONAL = re.compile(
    r"(?<![a-z])(kung|kapag|pag|paano|ano ang gagawin|anong gagawin|ano gagawin|what should i do|what do i do|what to do|"
    r"how (do|to|can)|if there|if a|when there|tips|safety|prepare|during|habang)(?![a-z])"
)

_MEDICAL = re.compile(r"(can'?t breathe|cannot breathe|makahinga|dumudugo|bleeding|heart attack|inatake|unconscious|malay|ulirat|nalulunod|drowning)")
_FIRE = re.compile(r"(sunog|fire|nasusunog|burning)")


def detect_emergency(question: str) -> dict | None:
    """Returns {'kind': 'fire'|'medical'|'general'} when the message sounds like danger right now."""
    q = normalize(question)
    strong = bool(_STRONG_EMERGENCY.search(q))
    weak = bool(_WEAK_EMERGENCY.search(q)) and not _INFORMATIONAL.search(q)
    if not (strong or weak):
        return None
    if _MEDICAL.search(q):
        kind = "medical"
    elif _FIRE.search(q):
        kind = "fire"
    else:
        kind = "general"
    return {"kind": kind}
