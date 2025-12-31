import json
from pathlib import Path

from mgi.features.mistakes_untraded import run

def test_untraded_snapshot(tmp_path, monkeypatch):
    # Arrange: copy fixture into temp data folder
    root = tmp_path
    (root / "data" / "raw" / "series_1").mkdir(parents=True)
    (root / "data" / "derived" / "series_1").mkdir(parents=True)

    fixture = Path("tests/fixtures/events_small.jsonl").read_text(encoding="utf-8")
    (root / "data" / "raw" / "series_1" / "events.jsonl").write_text(fixture, encoding="utf-8")

    # optional end_state.json if you want team names
    (root / "data" / "raw" / "series_1" / "end_state.json").write_text("{}", encoding="utf-8")

    # Get original project root before monkeypatch.chdir
    orig_root = Path.cwd()

    monkeypatch.chdir(root)

    # Act
    rc = run("1", top=5, window_seconds=25)
    assert rc == 0

    got = json.loads((root / "data" / "derived" / "series_1" / "mistakes_untraded.json").read_text(encoding="utf-8"))
    expected = json.loads((orig_root / "tests/expected/mistakes_untraded_expected.json").read_text(encoding="utf-8"))

    # Assert
    assert got == expected
    
    # Invariants
    assert sum(x["isNearObjective"] for x in got) >= sum(x["isPressureObjective"] for x in got)
    assert sum(x["answeredByObjective"] for x in got) <= len(got)
