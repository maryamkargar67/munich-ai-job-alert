import re

def requires_advanced_german(text):
    text = " ".join(text.lower().split())

    blocked_terms = [
        "german speaking",
        "german-speaking",
        "fluent german",
        "advanced german",
        "native german",
        "native-level german",
        "good command of german",
        "good command of written and spoken german",
        "good command of spoken and written german",
        "german required",
        "german is required",
        "german mandatory",
        "german is mandatory",
        "german language required",
        "german language is required",

        "b2 german",
        "german b2",
        "at least b2 german",
        "at least german b2",
        "deutsch b2",
        "b2 deutsch",
        "deutschkenntnisse b2",
        "deutschkenntnisse mindestens b2",
        "deutschkenntnisse mindestens niveau b2",
        "deutschkenntnisse auf b2-niveau",
        "deutschkenntnisse niveau b2",
        "mindestens b2 deutsch",
        "mind. b2 deutsch",
        "deutsch- und englischkenntnisse mindestens niveau b2",
        "deutsch und englisch mindestens niveau b2",

        "c1 german",
        "german c1",
        "at least c1 german",
        "at least c1",
        "c2 german",
        "german c2",

        "verhandlungssichere deutschkenntnisse",
        "verhandlungssicher deutsch",
        "sehr gute deutschkenntnisse",
        "ausgezeichnete deutschkenntnisse",
        "fließende deutschkenntnisse",
        "fliessende deutschkenntnisse",
        "fließend deutsch",
        "fliessend deutsch",

        "deutschkenntnisse auf c1-niveau",
        "deutschkenntnisse auf c2-niveau",
        "deutschkenntnisse niveau c1",
        "deutschkenntnisse niveau c2",

        "mind. c1",
        "mindestens c1",
        "mind. c2",
        "mindestens c2",

        "deutsch als muttersprache",
        "deutsch muttersprache"
    ]

    if any(
        term in text
        for term in blocked_terms
    ):
        return True

    # Catch combined requirements such as:
    # "Sehr gute Deutsch- und Englischkenntnisse"
    # "Gute Deutsch- und Englischkenntnisse"
    # "Fließende Deutsch- und Englischkenntnisse"
    german_patterns = [
        r"\b(?:sehr\s+)?gute\s+deutsch[-\s]*(?:und|&)\s*englischkenntnisse\b",
        r"\bfließende\s+deutsch[-\s]*(?:und|&)\s*englischkenntnisse\b",
        r"\bfliessende\s+deutsch[-\s]*(?:und|&)\s*englischkenntnisse\b",
        r"\bverhandlungssichere\s+deutsch[-\s]*(?:und|&)\s*englischkenntnisse\b",
        r"\b(?:sehr\s+)?gute\s+kenntnisse\s+in\s+deutsch\b",
        r"\bsehr\s+gut\s+deutsch\b",
        r"\bsehr\s+gutes\s+deutsch\b",
        r"\bdeutsch\s+sehr\s+gut\b",
        r"\bsprich(?:st|en)?\s+sehr\s+gut\s+deutsch\b",
        r"\bbeherrsch(?:st|en)?\s+deutsch\s+sehr\s+gut\b",
        r"\bverhandlungssicher\s+auf\s+deutsch\b",
        r"\bverhandlungssicher(?:e|er|es)?\s+kenntnisse\s+in\s+deutsch\b",
        r"\bdeutsch\s+verhandlungssicher\b",
        r"\b(?:very\s+)?good\s+german\s+(?:skills|language\s+skills|proficiency)\b",
        r"\bproficient\s+in\s+german\b",
        r"\bstrong\s+communication\s+skills\s+in\s+(?:both\s+)?german\s+and\s+english\b",
        r"\bexcellent\s+communication\s+skills\s+in\s+(?:both\s+)?german\s+and\s+english\b",
        r"\bvery\s+good\s+communication\s+skills\s+in\s+(?:both\s+)?german\s+and\s+english\b",

        # German CEFR requirements in flexible English wording
        r"\bgerman\b.{0,40}\b(?:at\s+least|minimum|min\.?|required|mandatory)\b.{0,30}\b(?:b2|c1|c2)\b",
        r"\b(?:at\s+least|minimum|min\.?)\b.{0,30}\b(?:b2|c1|c2)\b.{0,40}\bgerman\b",
        r"\bgerman\b.{0,30}\b(?:b2|c1|c2)\s*(?:level|niveau)?\b",
        r"\b(?:b2|c1|c2)\s*(?:level|niveau)?\b.{0,30}\bgerman\b",
        r"\bgerman\s+proficiency\b.{0,30}\b(?:b2|c1|c2)\b",
    ]

    return any(
        re.search(pattern, text)
        for pattern in german_patterns
    )
