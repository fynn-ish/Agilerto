"""Checks an AI answer BEFORE the user sees it. Small models sometimes cite sources that do not exist
or invent phone numbers; both are caught here in plain code."""
import re

CITE_RX = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
NO_INFO_RX = re.compile(
    r"(don'?t have (that|this|any) information|do not have (that|this|any) information|wala akong impormasyon|"
    r"not (found )?in (my )?(the )?saved data|no information (in|on|about))", re.I)
_NUM_RX = re.compile(r"\d[\d\-\s()]*\d|\d")
_UNIT_AFTER = re.compile(r"^\s*(km|kilomet|m\b|mm|kph|km/h|°|%|min|mins|minute|h\b|hr|hour|people|persons|katao|meter|metro)", re.I)


def cited_numbers(answer: str) -> list[int]:
    """Source numbers cited in the answer, in order, without repeats. Understands [1], [1][2] and [1, 2]."""
    seen: list[int] = []
    for group in CITE_RX.findall(answer):
        for n in (int(x) for x in re.split(r"\s*,\s*", group)):
            if n not in seen:
                seen.append(n)
    return seen


def phone_like_numbers(answer: str) -> list[str]:
    """Number strings that look like phone numbers or codes (3+ digits). Measurements, years and citations are ignored."""
    text = CITE_RX.sub(" ", answer)
    found = []
    for m in _NUM_RX.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) < 3:
            continue
        if re.fullmatch(r"(19|20)\d\d", digits):
            continue                                        # a year
        if _UNIT_AFTER.match(text[m.end(): m.end() + 14]):
            continue                                        # "300 people", "12 km", "85%"
        if m.start() > 0 and text[m.start() - 1] == ".":
            continue                                        # decimals such as 0.45
        found.append(digits)
    return found


def check(answer: str, n_sources: int, allowed_texts: list[str]) -> tuple[str | None, list[int]]:
    """(problem, cited). problem is None when the answer passes every check."""
    if not answer or not answer.strip():
        return "the answer is empty", []
    cited = cited_numbers(answer)
    bad = [n for n in cited if not 1 <= n <= n_sources]
    if bad:
        return f"it cites source numbers that do not exist: {bad}. Valid numbers are 1 to {n_sources}", cited
    if not cited and not NO_INFO_RX.search(answer):
        return "it has no citations like [1]", cited
    allowed_digits = [re.sub(r"\D", "", a) for a in allowed_texts]
    unsupported = [d for d in phone_like_numbers(answer) if not any(d in a for a in allowed_digits)]
    if unsupported:
        return f"it contains numbers that are not in the sources: {sorted(set(unsupported))}", cited
    return None, cited
