from qwen_agentic_ft.extract.parser import code_hash, normalize_code


def test_normalize_code_collapses_whitespace():
    code = "x = 1\n\ny = 2  # comment"
    normalized = normalize_code(code, strip_comments=True)
    assert "  " not in normalized
    assert "# comment" not in normalized


def test_code_hash_is_stable():
    a = code_hash("def foo():\n    return 1")
    b = code_hash("def foo():\n    return 1")
    assert a == b
