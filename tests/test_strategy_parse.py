from stocksense.core.contracts import StrategySpec
from stocksense.research.strategy_parse import StrategyParseError, parse_strategy_question
import pytest


def test_hero_create():
    spec, diff, mode = parse_strategy_question(
        "Backtest a 20/50 SMA crossover on NVDA since 2020."
    )
    assert mode == "create"
    assert spec.ticker == "NVDA"
    assert spec.strategy.fast_window == 20
    assert spec.strategy.slow_window == 50
    assert spec.start == "2020-01-01"
    assert spec.commission_bps == 0


def test_mutate_costs_only():
    prior, _, _ = parse_strategy_question(
        "Backtest a 20/50 SMA crossover on NVDA since 2020."
    )
    spec, diff, mode = parse_strategy_question(
        "Add 5 bps commission and 2 bps slippage.", prior
    )
    assert mode == "mutate_costs"
    assert spec.commission_bps == 5
    assert spec.slippage_bps == 2
    assert spec.strategy.fast_window == 20
    assert "commission_bps" in diff


def test_view_metrics_no_mutation():
    prior, _, _ = parse_strategy_question(
        "Backtest a 20/50 SMA crossover on NVDA since 2020."
    )
    prior2, _, _ = parse_strategy_question(
        "Add 5 bps commission and 2 bps slippage.", prior
    )
    spec, diff, mode = parse_strategy_question(
        "Show max drawdown and hit rate.", prior2
    )
    assert mode == "view_metrics"
    assert diff == {}
    assert spec.model_dump() == prior2.model_dump()


def test_no_ticker_400():
    with pytest.raises(StrategyParseError, match="Ticker"):
        parse_strategy_question("Backtest an SMA crossover since 2020.")
