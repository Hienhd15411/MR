import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.process_with_ai import _validate_processed, cmd_apply  # noqa: E402


def _good_row(**overrides):
    base = {
        "id": "abc123",
        "title_normalized": "OpenAI ra mắt GPT-5 với khả năng agentic",
        "summary": "• OpenAI công bố GPT-5\n• Khả năng tool-use vượt trội\n• Tác động lớn đến AI commerce",
        "category": "AI",
        "sub_category": "Big tech AI",
        "topic_lens": "Technology",
        "topic_sub": "AI/ Gen AI",
        "campaign_period": "",
        "impact_score": 5,
        "relevance_score": 4,
        "final_score": round(5 * 0.6 + 4 * 0.4, 2),
        "tags": "ai, foundation_model",
        "ai_processed_at": "2026-05-06T01:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_validate_passes_for_good_row():
    assert _validate_processed([_good_row()]) == []


def test_validate_catches_bad_final_score():
    row = _good_row(final_score=2.5)
    errs = _validate_processed([row])
    assert any("final_score" in e for e in errs)


def test_validate_catches_score_out_of_range():
    row = _good_row(impact_score=7)
    errs = _validate_processed([row])
    assert any("impact_score" in e for e in errs)


def test_validate_catches_invalid_topic_lens():
    row = _good_row(topic_lens="Marketing")  # not in {Legal, Technology, Economic}
    errs = _validate_processed([row])
    assert any("topic_lens" in e for e in errs)


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
    p.write_text(json.dumps([_good_row(final_score=1.0)]), encoding="utf-8")
    rc = cmd_apply(processed_path=p, dry_run=True)
    assert rc == 3
