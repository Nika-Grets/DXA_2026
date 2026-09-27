from uuid import uuid4


def test_full_dicom_workflow(client, dicom_bytes):
    upload = client.post("/api/v1/upload", files={"file": ("scan", dicom_bytes, "application/octet-stream")})
    assert upload.status_code == 201, upload.text
    study = upload.json()
    assert study["status"] == "parsed"
    assert study["images_count"] == 1
    assert "PatientName" not in study["images"][0]["metadata"]

    study_id = study["study_id"]
    image_id = study["images"][0]["image_id"]
    preview = client.get(f"/api/v1/studies/{study_id}/preview/{image_id}")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"

    prediction = client.post(f"/api/v1/studies/{study_id}/predict")
    assert prediction.status_code == 200, prediction.text
    assert prediction.json()["status"] == "predicted"

    generated = client.post(f"/api/v1/studies/{study_id}/report")
    assert generated.status_code == 200, generated.text
    report = client.get(f"/api/v1/studies/{study_id}/report")
    assert report.status_code == 200
    assert report.content.startswith(b"%PDF")
    assert "attachment" in report.headers["content-disposition"]


def test_report_requires_prediction(client, dicom_bytes):
    study_id = client.post("/api/v1/upload", files={"file": ("scan.dcm", dicom_bytes)}).json()["study_id"]
    response = client.post(f"/api/v1/studies/{study_id}/report")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STUDY_STATE"


def test_invalid_upload_and_unknown_study_have_stable_errors(client):
    invalid = client.post("/api/v1/upload", files={"file": ("bad.bin", b"not dicom")})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "DICOM_INVALID"
    missing = client.get(f"/api/v1/studies/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "STUDY_NOT_FOUND"


def test_health_openapi_and_cors(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert "/api/v1/upload" in client.get("/openapi.json").json()["paths"]
    allowed = client.options(
        "/api/v1/upload",
        headers={"Origin": "http://frontend.test", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers["access-control-allow-origin"] == "http://frontend.test"
    denied = client.options(
        "/api/v1/upload",
        headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in denied.headers
