import inspect

from app.api.router import create_report, predict, upload


def test_upload_streaming_endpoint_is_async():
    assert inspect.iscoroutinefunction(upload)


def test_cpu_and_blocking_handlers_use_fastapi_thread_pool():
    assert not inspect.iscoroutinefunction(predict)
    assert not inspect.iscoroutinefunction(create_report)
