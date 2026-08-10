# CatalystEdge regression suite (Phase 8)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

& $py -m pytest `
  tests/test_research_agent_eval.py `
  tests/test_research_agent_memory.py `
  tests/test_scenario_lab.py `
  tests/test_scenario_parse.py `
  tests/test_analog_search.py `
  tests/test_analog_search_parse.py `
  tests/test_thesis_attach.py `
  tests/test_thesis_loop.py `
  tests/test_event_study.py `
  tests/test_strategy_lab.py `
  tests/test_contracts.py `
  -q
exit $LASTEXITCODE
