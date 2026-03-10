from app.engine.formula_parser import evaluate


def test_simple_addition():
    assert evaluate("10 + 20", {}) == 30


def test_variable_lookup():
    assert evaluate("str + mag", {"str": 100, "mag": 50}) == 150


def test_multiplication():
    assert evaluate("str * 2", {"str": 50}) == 100


def test_parentheses():
    assert evaluate("(str + job_level) * 3", {"str": 100, "job_level": 10}) == 330


def test_rand_with_fixed_rng():
    # rand(N) 使用固定 RNG 回傳 5
    result = evaluate("rand(100)", {}, rng=lambda n: 5)
    assert result == 5


def test_complex_formula():
    result = evaluate(
        "(str + job_level) * rand(50)",
        {"str": 100, "job_level": 10},
        rng=lambda n: 10,
    )
    # (100 + 10) * 10 = 1100
    assert result == 1100


def test_nested_rand():
    result = evaluate("rand(10) + rand(20)", {}, rng=lambda n: n - 1)
    # rand(10)=9, rand(20)=19 → 28
    assert result == 28


def test_empty_formula():
    assert evaluate("", {}) == 0


def test_division():
    assert evaluate("100 / 3", {}) == 33


def test_division_by_zero():
    assert evaluate("100 / 0", {}) == 0
