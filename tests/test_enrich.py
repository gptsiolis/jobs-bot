import enrich


def test_extract_json_plain():
    assert enrich._extract_json('{"fit_score": 80}') == {"fit_score": 80}


def test_extract_json_with_fences_and_trailing_prose():
    # The two real failure modes seen in prod: code fences and a trailing sentence.
    fenced = '```json\n{"fit_score": 42, "summary": "x"}\n```'
    assert enrich._extract_json(fenced)["fit_score"] == 42
    trailing = '{"fit_score": 15, "summary": "y"}\nThis role is senior.'
    assert enrich._extract_json(trailing)["summary"] == "y"


def test_int0100_clamps_and_handles_junk():
    assert enrich._int0100(150) == 100
    assert enrich._int0100(-5) == 0
    assert enrich._int0100(73) == 73
    assert enrich._int0100("nope") is None
    assert enrich._int0100(None) is None
