import json
from pathlib import Path
import numpy as np


def test_quality_calibrators_are_oof_provenance_and_monotone():
    root = Path(__file__).resolve().parents[2]
    data = json.loads((root / 'artifacts/models/quality_calibrators.json').read_text())
    assert data
    for name, item in data.items():
        assert item['method'] == 'platt_logit'
        assert item['n'] >= item['positive'] >= 1
        if item.get('enabled'):
            assert item['coef'] > 0
            assert item['oof_raw_auc'] >= 0.60


def test_platt_calibration_preserves_ranking_for_enabled_heads():
    root = Path(__file__).resolve().parents[2]
    data = json.loads((root / 'artifacts/models/quality_calibrators.json').read_text())
    oof = json.loads((root / 'artifacts/v68_oof/oof_predictions.json').read_text())
    for name, item in data.items():
        if not item.get('enabled'):
            continue
        p = np.clip(np.asarray(oof[name]['p'], dtype=float), 1e-6, 1-1e-6)
        z = np.log(p/(1-p))
        pc = 1/(1+np.exp(-(item['coef']*z+item['intercept'])))
        assert np.all(np.diff(pc[np.argsort(p)]) >= -1e-12)
