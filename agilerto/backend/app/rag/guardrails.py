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
        r"\bevacuation (?:is )?(?:really )?(?:necessary|needed)\b",
        r"\blilikas\b.{0,20}\bba\b",
    ]),
    ("safety", [
        r"\b(is|are|am)\s+(it|this|that|we|i|the [a-z ]{2,25}|[a-z]{3,20})\s+(still\s+)?safe\b",
        r"\bis it (ok|okay|alright) to (go|stay|travel|return|drive|swim|go back)\b",
        r"\b(safe|ligtas)\s+ba\b",
        r"\bligtas ba\b",
        r"\b(?:pwede|puwede|maaari)(?: na)? ba (?:kaming|akong|na)? ?(?:umuwi|bumalik|lumabas|bumiyahe|pumasok)\b",
        r"\bcan (?:i|we) (?:go|return|get)\b.{0,12}\b(?:back|home)\b",
    ]),
    ("prediction", [
        r"\bwill (there|it|the|another|a|an)\b.{0,40}\b(earthquake|quake|aftershock|flood|flooding|typhoon|storm|landslide|eruption|erupt|hit|strike|happen)\b",
        r"\bwhen (will|is|does)\b.{0,30}\b(next|another|coming)\b.{0,30}\b(earthquake|quake|typhoon|flood|storm|eruption)\b",
        r"\bis (a|an|the)\s+(earthquake|typhoon|flood|landslide|eruption|storm)\b.{0,25}\b(coming|going to|expected|about to)\b",
        r"\b(predict|prediction|predicting)\b",
        r"\bis there (?:going to|gonna) be\b",
        r"\bwill\b[^.?!]{0,40}\b(?:erupt|flood|make landfall|landfall)\b",
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
# A question that only MENTIONS a danger word is not an emergency ("What are the signs of a heart attack?").
# Cues that a message is hypothetical, educational, or about the news cancel the match, unless it has an "!".
_DANGER = re.compile(
    r"(?<![a-z])(trapped|naipit|nakulong|na-?trap|can'?t breathe|cannot breathe|(?:hindi|di)(?: po)? makahinga|dumudugo|"
    r"bleeding|nalulunod|drowning|heart attack|inatake|nawalan ng (?:malay|ulirat)|unconscious|nasusunog|on fire)(?![a-z])")
_SITUATION = re.compile(
    r"(?<![a-z])(may sunog|sunog sa|sunog dito|(?:sunog|fire)\s*!|there'?s a fire|there is a fire|fire in my|"
    r"lumilindol ngayon|lumilindol na|lumilindol!|earthquake (?:right now|is happening)|binabaha na|may baha na|"
    r"(?:water|tubig) (?:is )?(?:rising|tumataas)|tumataas ang tubig|may gumuho|nagkaroon ng landslide)")
_HELP = re.compile(r"(?<![a-z])(tulong|saklolo|tulungan|help me|help us|please help|help)(?![a-z])")
_QUESTIONY = re.compile(
    r"(?<![a-z])(saan|paano|ano|anong|kailan|sino|where|how|what|when|who|which|can you|could you|would you|is there|are there|"
    r"pwede|puwede|maaari|makakahingi|makakakuha|find|finding|locate|looking for|understand|explain|check|tell me|show me)(?![a-z])")
_NOT_A_CALL_FOR_HELP = re.compile(
    r"(?<![a-z])(pinansyal|financial|relief|ayuda|assistance|donation|donate|salamat|thank|thanks|volunteer)(?![a-z])")
_NOT_NOW = re.compile(
    r"(?<![a-z])(if|when|whenever|kung|kapag|pag|during|habang|before|bago|tips|safety|prepare|paghahanda|signs? of|"
    r"symptoms? of|sintomas|first aid|how to use|news|balita|ayon sa|according to|reported|iniulat|noong|kahapon|"
    r"yesterday|last (?:week|year|month))(?![a-z])")
_MEDICAL = re.compile(r"(can'?t breathe|cannot breathe|makahinga|dumudugo|bleeding|heart attack|inatake|unconscious|malay|ulirat|nalulunod|drowning)")
_FIRE = re.compile(r"(sunog|fire|nasusunog|burning)")


def detect_emergency(question: str) -> dict | None:
    """Returns {'kind': 'fire'|'medical'|'general'} when the message sounds like danger right now."""
    q = normalize(question)
    shouting = "!" in question
    if _NOT_NOW.search(q) and not shouting:
        return None
    asks_for_help = bool(_HELP.search(q)) and (
        shouting or not (_QUESTIONY.search(q) or _NOT_A_CALL_FOR_HELP.search(q)))
    if not (_DANGER.search(q) or _SITUATION.search(q) or asks_for_help):
        return None
    if _MEDICAL.search(q):
        kind = "medical"
    elif _FIRE.search(q):
        kind = "fire"
    else:
        kind = "general"
    return {"kind": kind}


# ---------- someone who may be thinking about hurting themselves ----------
_DISTRESS = re.compile(
    r"(?<![a-z])(kill(?:ing)? (?:my ?self|him ?self|her ?self|them ?selves)|end(?:ing)? my (?:own )?life|take my (?:own )?life|"
    r"suicid(?:e|al)|want(?:ed)? to die|wanna die|(?:don'?t|do not) want to (?:live|be alive)|no reason to live|"
    r"better off (?:dead|without me)|(?:hurt|harm|cut) (?:my ?self|him ?self|her ?self)|self[- ]?harm|end it all|"
    r"magpakamatay|magpapakamatay|papatayin ko (?:na )?(?:ang )?sarili ko|gusto ko (?:nang |ng )?mamatay|"
    r"ayoko (?:nang |ng )?mabuhay|ayaw ko (?:nang |ng )?mabuhay|wala (?:na )?(?:akong|nang) dahilan (?:para |upang )?mabuhay|"
    r"saktan ang sarili ko|wakasan ang buhay ko|tapusin ang buhay ko)(?![a-z])")
_FEARS_DEATH = re.compile(r"(?:don'?t|do not|dont) want to die")        # fear in a disaster, not a wish to die


def detect_distress(question: str) -> bool:
    return bool(_DISTRESS.search(_FEARS_DEATH.sub(" ", normalize(question))))


# ---------- attempts to change the assistant's rules ----------
_INJECTION = [re.compile(p) for p in [
    r"\bignore\b.{0,25}\b(?:instructions|rules|prompts?|guidelines|programming)\b",
    r"\bdisregard\b.{0,25}\b(?:instructions|rules|above|previous)\b",
    r"\b(?:reveal|show|print|repeat|display|tell me|give me)\b.{0,20}\b(?:system prompt|your prompt|your instructions|your rules|initial prompt)\b",
    r"\byou are now\b", r"\bpretend (?:to be|you are|you're)\b", r"\b(?:developer|dev|god|dan) mode\b", r"\bjailbreak\b",
    r"\boverride\b.{0,25}\b(?:rules|safety|instructions|guardrails)\b", r"\bact as (?:an? )?(?:unrestricted|unfiltered|different)\b",
    r"(?:huwag|wag) mong (?:sundin|pansinin)\b.{0,30}\b(?:patakaran|utos|rules)",
    r"\b(?:kalimutan|balewalain) mo\b.{0,30}\b(?:patakaran|utos|instructions|rules)",
]]


def detect_injection(question: str) -> bool:
    q = normalize(question)
    return any(rx.search(q) for rx in _INJECTION)


# ---------- one decision, used by the assistant and by the tests ----------
def classify(question: str) -> tuple[str, str | None]:
    """('distress'|'emergency'|'injection'|'refusal'|'normal', detail).
    Order matters: people in danger or distress come first, so nothing below can get in their way."""
    if detect_distress(question):
        return "distress", None
    if (em := detect_emergency(question)):
        return "emergency", em["kind"]
    if detect_injection(question):
        return "injection", None
    if (code := detect_refusal(question)):
        return "refusal", code
    return "normal", None
