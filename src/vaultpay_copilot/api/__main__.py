"""Sobe a API com as opções seguras do uvicorn: python -m vaultpay_copilot.api"""

import uvicorn

HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    uvicorn.run(
        "vaultpay_copilot.api.app:create_app",
        factory=True,
        host=HOST,
        port=PORT,
        # Por padrão o uvicorn confia no X-Forwarded-For de quem chega por 127.0.0.1: qualquer
        # cliente local escolheria o próprio "IP" e furaria o limite por IP.
        proxy_headers=False,
        # O log de acesso do uvicorn grava o endereço digitado e o IP; o nosso não.
        access_log=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
