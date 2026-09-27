from uuid import UUID

import numpy as np

from app.ml.dexa_baseline import DexaBaselineAdapter


class MockMLAdapter(DexaBaselineAdapter):
    """Backward-compatible name for integrations that imported the old mock."""
