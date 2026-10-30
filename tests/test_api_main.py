import uvicorn

from vaultpay_copilot.api import __main__ as api_main


def test_sobe_so_local_e_sem_confiar_em_x_forwarded_for(monkeypatch):
    received = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **options: received.update(options, app=app))

    api_main.main()

    assert received["app"] == "vaultpay_copilot.api.app:create_app"
    assert received["factory"] is True
    assert received["host"] == "127.0.0.1"
    assert received["proxy_headers"] is False
    assert received["access_log"] is False
    assert received["server_header"] is False
