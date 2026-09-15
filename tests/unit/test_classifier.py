from kitbuilder.classifier import OTHER, classify_filename

CATEGORIES = {
    "Kick": ["kick", "kck", "bd", "bassdrum"],
    "Snare": ["snare", "snr", "sd"],
    "Hat Closed": ["hat", "hh", "chh", "closedhat"],
    "Hat Open": ["openhat", "ohh"],
}


def test_simple_match():
    category, ambiguous = classify_filename("kick_01.wav", CATEGORIES)
    assert category == "Kick"
    assert ambiguous == []


def test_case_insensitive_and_anywhere_in_name():
    category, _ = classify_filename("SUPER_KICK_tail.wav", CATEGORIES)
    assert category == "Kick"


def test_unmatched_is_other():
    category, ambiguous = classify_filename("weird_sound.wav", CATEGORIES)
    assert category == OTHER
    assert ambiguous == []


def test_ambiguous_match_logs_other_categories_but_first_priority_wins():
    # "openhat_01.wav" contains both "hat" (Hat Closed) and "openhat" (Hat Open).
    category, ambiguous = classify_filename("openhat_01.wav", CATEGORIES)
    assert category == "Hat Closed"
    assert ambiguous == ["Hat Open"]


def test_unambiguous_hat_closed():
    category, ambiguous = classify_filename("hat_closed.wav", CATEGORIES)
    assert category == "Hat Closed"
    assert ambiguous == []
