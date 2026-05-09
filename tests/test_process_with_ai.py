import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.process_with_ai import _validate_processed, cmd_apply  # noqa: E402


def _good_row(**overrides):
    base = {
        "id": "abc123",
        "week": "W18-26",
        "topic_group": "Market Pulse",
        "sub_topic_group": "Thị trường thế giới",
        "category": "Fintech",
        "subcategory": "Agentic payments",
        "related_vertical": "E-wallet",
        "title_normalized": "Stripe Link ra mắt: ví điện tử cho AI agent",
        "summary": "• What\n• Numbers\n• Implication",
        "start_date": "30/04/2026",
        "end_date": "",
        "signal_level": "4",
        "mentioned_players": "Stripe, OpenAI",
        "ai_processed_at": "2026-05-06T01:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_validate_passes_for_good_row():
    assert _validate_processed([_good_row()]) == []


def test_validate_catches_invalid_vertical():
    row = _good_row(related_vertical="Banking")
    errs = _validate_processed([row])
    assert any("related_vertical" in e for e in errs)


def test_validate_catches_invalid_signal_level():
    row = _good_row(signal_level="9")
    errs = _validate_processed([row])
    assert any("signal_level" in e for e in errs)


def test_validate_missing_field():
    row = _good_row()
    del row["title_normalized"]
    errs = _validate_processed([row])
    assert any("title_normalized" in e for e in errs)


def test_apply_dry_run_works(tmp_path):
    p = tmp_path / "processed.json"
    p.write_text(json.dumps([_good_row()]), encoding="utf-8")
    rc = cmd_apply(processed_path=p, dry_run=True)
    assert rc == 0


def test_apply_missing_file_returns_2(tmp_path):
    rc = cmd_apply(processed_path=tmp_path / "nope.json", dry_run=True)
    assert rc == 2


def test_apply_invalid_returns_3(tmp_path):
    p = tmp_path / "processed.json"
    p.write_text(json.dumps([_good_row(signal_level="99")]), encoding="utf-8")
    rc = cmd_apply(processed_path=p, dry_run=True)
    assert rc == 3
