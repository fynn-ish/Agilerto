"""Fixed wording for non-AI replies, in English and Tagalog."""

FALLBACK_EMERGENCY_NUMBER = "911"

TEXT = {
    "en": {
        "refuse_evacuation": (
            "I can't tell you whether to evacuate. That decision should come from your local authorities. "
            "Please contact your city or municipal DRRMO and follow their announcements and PAGASA or PHIVOLCS advisories. "
            "If you are in danger, call 911. I can show the nearest evacuation centers, the current weather, and recent "
            "earthquakes from my saved data."),
        "refuse_safety": (
            "I can't judge whether a place or activity is safe. Please ask your local DRRMO or other authorities and check "
            "the official PAGASA and PHIVOLCS advisories. If you are in danger, call 911. I can show nearby facilities, "
            "current weather, and recent earthquakes from my saved data."),
        "refuse_prediction": (
            "I can't predict disasters such as earthquakes, floods, or typhoons. For official warnings, check PAGASA and "
            "PHIVOLCS. I can show the current weather, recent earthquakes, and the nearest evacuation centers from my saved data."),
        "refuse_rules": (
            "I can only answer from my saved disaster information, and I can't change how I work. You can ask about nearby "
            "help, the weather, recent earthquakes, advisories, news, hotlines, or safety tips."),
        "distress": (
            "I'm really sorry you're going through this. You don't have to face it alone. If you are in immediate danger, "
            "call 911. You can also call the NCMH Crisis Hotline, free and open 24/7: 1553 (landline) or 0917 899 8727. "
            "If someone is with you, please tell them how you feel. I'm a disaster information assistant, so I can't give "
            "you the support a person can."),
        "emergency_head": "This sounds like an emergency. Call 911 now. I cannot send help from here.",
        "emergency_numbers": "Emergency numbers:",
        "emergency_nearest": "Nearest {label}:",
        "emergency_guide": "Saved safety guide:",
        "no_sources": (
            "I don't have that information in my saved data. You can ask about the nearest hospital or evacuation center, "
            "the weather, recent earthquakes, emergency hotlines, or safety tips."),
        "ai_unavailable": "The local AI is not running right now, so here are the saved records that match your question:",
        "fallback": "I couldn't produce an answer with checked citations, so here are the saved records related to your question:",
        "busy": "The assistant is still working on another question. Please try again in a moment.",
        "note_stale": "The {what} data is {age} old. Conditions may have changed.",
        "note_offline": "Offline: live data (weather, earthquakes) is from {when}.",
        "note_unverified": "Some places are not verified yet. Call ahead or confirm with your local DRRMO before travelling.",
        "no_advisories": (
            "I have no saved advisory that answers this. Advisory data: {when}. That does not mean there is "
            "no warning. Please check PAGASA (typhoons and rain), PHIVOLCS (earthquakes and volcanoes), NDRRMC, and your "
            "local DRRMO. I can show the current weather and recent earthquakes from my saved data."),
        "never_checked": "nothing has been downloaded yet",
        "checked_at": "last checked {time}",
        "note_gdacs": "GDACS alerts are automated and are not official Philippine warnings. Check PAGASA, PHIVOLCS, NDRRMC, and your local DRRMO.",
        "note_news": "News headlines come from outside outlets and have not been verified by this system.",
        "what_weather": "weather", "what_quake": "earthquake", "what_advisory": "advisory", "what_news": "news",
        "kind_hospital": "hospital", "kind_evacuation_center": "evacuation center",
        "kind_fire_station": "fire station", "kind_police_station": "police station",
    },
    "tl": {
        "refuse_evacuation": (
            "Hindi ko masasabi kung dapat kang lumikas. Ang desisyong iyon ay dapat manggaling sa mga lokal na awtoridad. "
            "Makipag-ugnayan sa DRRMO ng inyong lungsod o bayan, at sundin ang kanilang mga anunsyo at ang mga abiso ng "
            "PAGASA o PHIVOLCS. Kung nasa panganib ka, tumawag sa 911. Maipapakita ko ang pinakamalapit na evacuation center, "
            "ang kasalukuyang panahon, at ang mga kamakailang lindol mula sa naka-save kong data."),
        "refuse_safety": (
            "Hindi ko masasabi kung ligtas ang isang lugar o gawain. Magtanong sa inyong lokal na DRRMO o sa mga awtoridad, "
            "at tingnan ang mga opisyal na abiso ng PAGASA at PHIVOLCS. Kung nasa panganib ka, tumawag sa 911. Maipapakita ko "
            "ang mga kalapit na pasilidad, ang panahon, at ang mga kamakailang lindol mula sa naka-save kong data."),
        "refuse_prediction": (
            "Hindi ako makapag-predict ng mga sakuna tulad ng lindol, baha, o bagyo. Para sa mga opisyal na babala, tingnan "
            "ang PAGASA at PHIVOLCS. Maipapakita ko ang kasalukuyang panahon, ang mga kamakailang lindol, at ang pinakamalapit "
            "na evacuation center mula sa naka-save kong data."),
        "refuse_rules": (
            "Makakasagot lang ako gamit ang naka-save kong impormasyon tungkol sa sakuna, at hindi ko mababago ang paraan ng "
            "paggana ko. Puwede kang magtanong tungkol sa kalapit na tulong, panahon, mga kamakailang lindol, advisory, balita, "
            "hotline, o safety tips."),
        "distress": (
            "Pasensya na at nararanasan mo ito. Hindi mo kailangang harapin ito nang mag-isa. Kung nasa agarang panganib ka, "
            "tumawag sa 911. Maaari ka ring tumawag sa NCMH Crisis Hotline, libre at bukas 24/7: 1553 (landline) o "
            "0917 899 8727. Kung may kasama ka, sabihin mo sa kanila ang nararamdaman mo. Isa akong assistant para sa "
            "impormasyon sa sakuna, kaya hindi ko maibibigay ang suportang maibibigay ng isang tao."),
        "emergency_head": "Mukhang emergency ito. Tumawag agad sa 911. Hindi ako makakapagpadala ng tulong mula rito.",
        "emergency_numbers": "Mga emergency number:",
        "emergency_nearest": "Pinakamalapit na {label}:",
        "emergency_guide": "Naka-save na safety guide:",
        "no_sources": (
            "Wala akong impormasyon tungkol diyan sa naka-save kong data. Puwede kang magtanong tungkol sa pinakamalapit na "
            "ospital o evacuation center, sa panahon, sa mga kamakailang lindol, sa mga hotline, o sa mga safety tip."),
        "ai_unavailable": "Hindi tumatakbo ang lokal na AI ngayon, kaya ito ang mga naka-save na record na tugma sa tanong mo:",
        "fallback": "Hindi ako nakabuo ng sagot na may na-check na citation. Narito ang mga naka-save na record na may kinalaman sa tanong mo:",
        "busy": "Abala pa ang assistant sa ibang tanong. Subukan ulit sa ilang sandali.",
        "note_stale": "Luma na ang {what} data ({age}). Maaaring nagbago na ang kondisyon.",
        "note_offline": "Offline: ang live data (panahon, lindol) ay mula pa noong {when}.",
        "note_unverified": "May mga lugar na hindi pa verified. Tumawag muna o magkumpirma sa lokal na DRRMO bago pumunta.",
        "no_advisories": (
            "Wala akong naka-save na advisory na sasagot dito. Advisory data: {when}. Hindi ibig "
            "sabihin nito na walang babala. Tingnan ang PAGASA (bagyo at ulan), PHIVOLCS (lindol at bulkan), NDRRMC, at ang "
            "inyong lokal na DRRMO. Maipapakita ko ang kasalukuyang panahon at ang mga kamakailang lindol mula sa naka-save kong data."),
        "never_checked": "wala pang na-download",
        "checked_at": "huling na-check noong {time}",
        "note_gdacs": "Awtomatiko ang mga alerto ng GDACS at hindi ito opisyal na babala ng Pilipinas. Tingnan ang PAGASA, PHIVOLCS, NDRRMC, at ang lokal na DRRMO.",
        "note_news": "Ang mga balita ay mula sa labas na news outlet at hindi pa na-verify ng sistemang ito.",
        "what_weather": "panahon", "what_quake": "lindol", "what_advisory": "advisory", "what_news": "balita",
        "kind_hospital": "ospital", "kind_evacuation_center": "evacuation center",
        "kind_fire_station": "fire station", "kind_police_station": "police station",
    },
}


def t(lang: str, key: str, **kw) -> str:
    return TEXT.get(lang, TEXT["en"])[key].format(**kw)
