import csv
import io
import zipfile


def _archive(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return output.getvalue()


def _rows(payload: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))


def test_batch_endpoint_deduplicates_and_returns_required_columns(client, dicom_bytes):
    archive = _archive(
        {
            "dataset/study-a/image-1.dcm": dicom_bytes,
            "dataset/study-a/image-1-copy.dcm": dicom_bytes,
        }
    )

    response = client.post("/api/v1/batch", files={"file": ("dataset.zip", archive)})

    assert response.status_code == 200, response.text
    rows = _rows(response.content)
    assert len(rows) == 1
    assert list(rows[0]) == [
        "path_to_study",
        "study_uid",
        "image_uid",
        "anatomical_region",
        "quality_class",
        "violation_type",
        "processing_status",
        "time_of_processing",
        "confidence",
        "quality_prob",
        "findings",
    ]
    assert rows[0]["processing_status"] == "Success"
    assert rows[0]["anatomical_region"] == "lumbar_spine"


def test_study_failure_and_bad_dicom_do_not_stop_other_studies(client):
    from tests.conftest import make_dicom_bytes

    good = make_dicom_bytes()
    failing = make_dicom_bytes()
    archive = _archive(
        {
            "ok-study/good.dcm": good,
            "ml-failure/failure.dcm": failing,
            "broken-study/broken.dcm": b"not a dicom",
        }
    )

    response = client.post("/api/v1/batch", files={"file": ("dataset.zip", archive)})

    assert response.status_code == 200, response.text
    rows = _rows(response.content)
    assert len(rows) == 3
    assert sorted(row["processing_status"] for row in rows) == ["Failure", "Failure", "Success"]


def test_batch_timeout_becomes_failure_row(client):
    from tests.conftest import make_dicom_bytes

    client.app.state.batch_service.timeout_seconds = 0.05
    archive = _archive({"slow-study/image.dcm": make_dicom_bytes()})

    response = client.post("/api/v1/batch", files={"file": ("dataset.zip", archive)})

    assert response.status_code == 200, response.text
    row = _rows(response.content)[0]
    assert row["processing_status"] == "Failure"
    assert "TimeoutError" in row["violation_type"]


def test_batch_can_return_report_with_optional_visualizations(client, dicom_bytes):
    archive = _archive({"study/image.dcm": dicom_bytes})

    response = client.post(
        "/api/v1/batch?include_visualizations=true",
        files={"file": ("dataset.zip", archive)},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as result:
        names = result.namelist()
        assert "batch_report.csv" in names
        assert any(name.startswith("visualizations/") and name.endswith(".png") for name in names)


def test_batch_rejects_zip_slip(client, dicom_bytes):
    archive = _archive({"../escape.dcm": dicom_bytes})
    response = client.post("/api/v1/batch", files={"file": ("dataset.zip", archive)})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ZIP_PATH_TRAVERSAL"


def test_batch_service_accepts_directory_path(client, tmp_path, dicom_bytes):
    source = tmp_path / "dataset" / "nested" / "study"
    source.mkdir(parents=True)
    (source / "image.dcm").write_bytes(dicom_bytes)

    artifact = client.app.state.batch_service.process_path(tmp_path / "dataset")

    rows = _rows(artifact.content)
    assert len(rows) == 1
    assert rows[0]["processing_status"] == "Success"
    assert rows[0]["path_to_study"] == "nested/study"
