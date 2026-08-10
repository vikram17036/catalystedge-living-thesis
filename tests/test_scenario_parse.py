from stocksense.research.scenario_parse import parse_scenario_question


def test_hero_drop_10():
    spec, _ = parse_scenario_question("What if NVDA drops 10% in one day?")
    assert spec.ticker == "NVDA"
    assert spec.shock_value == -0.10


def test_chip_make_5_refines():
    prior, _ = parse_scenario_question("What if NVDA drops 10% in one day?")
    spec, diff = parse_scenario_question("Make it a 5% drop.", prior)
    assert spec.shock_value == -0.05
    assert "shock_value" in diff
