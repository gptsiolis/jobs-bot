import enrich


def test_extract_json_plain():
    assert enrich._extract_json('{"fit_score": 80}') == {"fit_score": 80}


def test_extract_json_with_fences_and_trailing_prose():
    # The two real failure modes seen in prod: code fences and a trailing sentence.
    fenced = '```json\n{"fit_score": 42, "summary": "x"}\n```'
    assert enrich._extract_json(fenced)["fit_score"] == 42
    trailing = '{"fit_score": 15, "summary": "y"}\nThis role is senior.'
    assert enrich._extract_json(trailing)["summary"] == "y"


def test_sanitize_strips_control_chars_but_keeps_text():
    # NUL and other C0 controls crash the Supabase text write (error 22P05).
    assert enrich._sanitize("Ops\x00 role\x07 here") == "Ops role here"
    # Tabs and newlines are preserved.
    assert enrich._sanitize("line1\nline2\tend") == "line1\nline2\tend"
    assert enrich._sanitize(None) == ""


def test_int0100_clamps_and_handles_junk():
    assert enrich._int0100(150) == 100
    assert enrich._int0100(-5) == 0
    assert enrich._int0100(73) == 73
    assert enrich._int0100("nope") is None
    assert enrich._int0100(None) is None
