from react_foundations.metrics import exact_match, f1_score, normalize_answer


def test_normalize_and_em():
    assert exact_match("The Indian Ocean", "Indian Ocean")
    assert normalize_answer("Cupertino,") == "cupertino"


def test_f1_partial_overlap():
    assert f1_score("Indian Ocean", "the Indian Ocean") == 1.0
    assert f1_score("yes", "no") == 0.0
    assert 0 < f1_score("google inc", "google") < 1
