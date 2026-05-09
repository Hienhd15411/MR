import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.process_with_ai import _validate_processed, cmd_apply  # noqa: E402
from src.storage.schema import compute_signal_score, signal_level_for  # noqa: E402


def _good_row(**overrides):
    base = {
        "id": "358",
        "week": "W18-26",
        "source_name": "Tech in Asia",
        "title_raw": "GoTo review to comply with Prabowo's 8% platform fee cap",
        "publish_date": "01/05/2026",
        "topic_group": "Market Pulse",
        "sub_topic_group": "SEA",
        "category": "Legal",
        "subcategory": "eCommerce regulation",
        "merged_category": "Legal | eCommerce regulation",
        "related_vertical": "Ride/ Food Delivery",
        "title_normalized": "Indonesia Prabowo ký sắc lệnh cắt hoa hồng ride-hailing xuống 8%",
        "summary": "• What\n• Numbers\n• Implication",
        "start_date": "01/05/2026",
        "end_date": "",
        "tags": "indonesia, regulation",
        "R1": 5, "R2": 5, "R3": 5, "R4": 4,
        "signal_score": compute_signal_score(5, 5, 5, 4),
        "signal_level": "5 - Industry disruption",
        "ai_processed_at": "2026-05-09T01:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_compute_signal_score_matches_excel_formula():
    # Excel formula: R1*0.4 + R2*0.25 + R3*0.2 + R4*0.15
    assert compute_signal_score(5, 5, 5, 5) == 5.0
    assert compute_signal_score(1, 1, 1, 1) == 1.0
    assert compute_signal_score(5, 4, 4, 3) == round(5*0.4 + 4*0.25 + 4*0.2 + 3*0.15, 2)


def test_signal_level_band_lookup():
    assert signal_level_for(4.85) == "5 - Industry disruption"
    assert signal_level_for(4.21) == "5 - Industry disruption"
    assert signal_level_for(3.85) == "4 - Strategic shift"
    assert signal_level_for(3.0)  == "3 - Market signal"
    assert signal_level_for(2.0)  == "2 - Minor signal"
    assert signal_level_for(1.0)  == "1 - Noise"


def test_validate_passes_for_good_row():
    assert _validate_processed([_good_row()]) == []


def test_validate_catches_invalid_vertical():
    row = _good_row(related_vertical="Banking")
    errs = _validate_processed([row])
    assert any("related_vertical" in e for e in errs)


def test_validate_catches_invalid_topic_group():
    row = _good_row(topic_group="Other Group")
    errs = _validate_processed([row])
    assert any("topic_group" in e for e in errs)


def test_validate_catches_score_mismatch():
    row = _good_row(R1=5, R2=5, R3=5, R4=4, signal_score=2.0)
    errs = _validate_processed([row])
    assert any("signal_score" in e for e in errs)


def test_validate_catches_signal_level_mismatch():
    # signal_score = 4.85 → "5 - Industry disruption"; mark wrong level
    row = _good_row(signal_level="3 - Market signal")
    errs = _validate_processed([row])
    assert any("signal_level" in e for e in errs)


def test_validate_catches_R_out_of_range():
    row = _good_row(R1=7)
    errs = _validate_processed([row])
    assert any("R1" in e for e in errs)


def test_apply_dry_run_works(tmp_path):
    p = tmp_path / "processed.json"
    p.write_text(json.dumps([_good_row()]), encoding="utf-8")
    rc = cmd_apply(processed_path=p, dry_run=True)
    assert rc == 0


def test_apply_invalid_returns_3(tmp_path):
    p = tmp_path / "processed.json"
    p.write_text(json.dumps([_good_row(R1=99)]), encoding="utf-8")
    rc = cmd_apply(processed_path=p, dry_run=True)
    assert rc == 3
