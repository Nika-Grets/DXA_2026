from pathlib import Path
import joblib
from app.ml import dexa_baseline as db

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / 'artifacts' / 'models' / 'right_posrot.joblib'
_model = joblib.load(MODEL)

def _load_only_right():
    return {'right_posrot': _model}

db._MODEL_CACHE = None
db._load_benchmark_models = _load_only_right

from app.external_ml.inference import predict_study
