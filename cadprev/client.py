"""Cliente HTTP da API do CADPREV.

Só biblioteca padrão. Respeita ``HTTPS_PROXY`` automaticamente, porque
``urllib`` já lê as variáveis de ambiente de proxy.

Modo offline
------------
Se ``CADPREV_FIXTURES`` apontar para um diretório, o cliente lê
``<dir>/<ENDPOINT>.json`` em vez de ir à rede. É assim que os testes rodam e é
assim que se desenvolve a interface sem depender da disponibilidade da API.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence

from . import endpoints

log = logging.getLogger("cadprev.client")

USER_AGENT = (
    "dashboard-cadprev/0.1 (+https://github.com/gilbertotulli/dashboard-cadprev)"
)


class ErroDaAPI(RuntimeError):
    """A API respondeu, mas com erro, ou respondeu algo que não é o envelope."""


class RespostaInesperada(ErroDaAPI):
    """O corpo veio sem a chave ``data``."""


class Cliente:
    """Consulta paginada aos recursos da API.

    Args:
        base_url: host da API. Ver ``endpoints.BASE_URL``.
        pausa: segundos entre requisições. A API é pública e gratuita;
            manter uma pausa é cortesia com um serviço que não cobra nada.
        tentativas: quantas vezes repetir uma falha temporária.
        timeout: segundos até desistir de uma requisição.
        fixtures: diretório de amostras para o modo offline.
    """

    def __init__(self, base_url: str = endpoints.BASE_URL, pausa: float = 1.0,
                 tentativas: int = 4, timeout: float = 60.0,
                 fixtures: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.pausa = pausa
        self.tentativas = tentativas
        self.timeout = timeout
        self.fixtures = fixtures or os.environ.get("CADPREV_FIXTURES") or None
        self.requisicoes = 0

    # -- rede -------------------------------------------------------------

    def _get(self, path: str, params: Mapping[str, Any]) -> Dict[str, Any]:
        query = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        )
        url = "{}{}?{}".format(self.base_url, path, query)
        pedido = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })

        espera = 2.0
        ultimo_erro: Optional[Exception] = None
        for tentativa in range(1, self.tentativas + 1):
            try:
                with urllib.request.urlopen(pedido, timeout=self.timeout) as resp:
                    corpo = resp.read().decode("utf-8", errors="replace")
                self.requisicoes += 1
                return json.loads(corpo)
            except urllib.error.HTTPError as erro:
                # 4xx é problema do pedido: repetir não resolve.
                if 400 <= erro.code < 500:
                    raise ErroDaAPI(
                        "{} respondeu {} {}".format(url, erro.code, erro.reason)
                    ) from erro
                ultimo_erro = erro
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erro:
                ultimo_erro = erro

            if tentativa < self.tentativas:
                log.warning("falha em %s (tentativa %d/%d): %s — repetindo em %.0fs",
                            path, tentativa, self.tentativas, ultimo_erro, espera)
                time.sleep(espera)
                espera *= 2

        raise ErroDaAPI(
            "{} falhou após {} tentativas: {}".format(url, self.tentativas, ultimo_erro)
        )

    # -- fixtures ---------------------------------------------------------

    def _do_fixture(self, nome: str) -> Dict[str, Any]:
        caminho = os.path.join(self.fixtures, nome + ".json")
        if not os.path.exists(caminho):
            raise ErroDaAPI(
                "modo offline: falta a amostra {}. Gere com "
                "`python -m cadprev inspect {} --salvar`.".format(caminho, nome)
            )
        with open(caminho, encoding="utf-8") as fh:
            dados = json.load(fh)
        if isinstance(dados, list):
            dados = {"data": dados, "count": len(dados), "limit": endpoints.PAGE_SIZE}
        return dados

    # -- API pública ------------------------------------------------------

    def pagina(self, nome: str, offset: int = 0, **filtros: Any) -> Dict[str, Any]:
        """Uma página crua, como a API devolveu."""
        alvo = endpoints.get(nome)
        if self.fixtures:
            return self._do_fixture(nome)
        return self._get(alvo.path, dict(filtros, offset=offset))

    def registros(self, nome: str, limite_paginas: Optional[int] = None,
                  **filtros: Any) -> Iterator[Dict[str, Any]]:
        """Percorre todas as páginas, devolvendo registro a registro.

        A última página é aquela em que ``count < limit`` — mesma regra do
        cliente R de referência. ``limite_paginas`` serve para explorar sem
        baixar a base inteira.
        """
        offset = 0
        pagina_num = 0
        while True:
            corpo = self.pagina(nome, offset=offset, **filtros)
            if "data" not in corpo:
                raise RespostaInesperada(
                    "{}: resposta sem a chave 'data'. Veio: {}".format(
                        nome, ", ".join(sorted(corpo))[:200])
                )
            dados: List[Dict[str, Any]] = corpo.get("data") or []
            for registro in dados:
                yield registro

            pagina_num += 1
            limite = int(corpo.get("limit") or endpoints.PAGE_SIZE)
            contagem = int(corpo.get("count") if corpo.get("count") is not None
                           else len(dados))
            if contagem < limite or not dados or self.fixtures:
                return
            if limite_paginas and pagina_num >= limite_paginas:
                log.info("%s: parando em %d páginas por limite pedido",
                         nome, pagina_num)
                return
            offset += limite
            if self.pausa:
                time.sleep(self.pausa)

    def amostra(self, nome: str, **filtros: Any) -> Sequence[Dict[str, Any]]:
        """Primeira página, para descobrir os campos reais de um endpoint."""
        corpo = self.pagina(nome, offset=0, **filtros)
        return corpo.get("data") or []
