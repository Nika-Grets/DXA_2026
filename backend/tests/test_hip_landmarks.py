import numpy as np
from app.ml.hip_landmarks import detect_hip_landmarks

def test_hip_landmark_output_is_bounded():
    img=np.zeros((240,280),dtype=np.float32)
    img[80:230,120:145]=1.0
    out=detect_hip_landmarks(img,'right')
    assert 0.0 <= out.confidence <= 1.0
    assert len(out.shaft_center)==2
