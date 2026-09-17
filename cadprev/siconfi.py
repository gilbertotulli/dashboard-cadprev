"""Cliente do SICONFI, a base contábil do Tesouro Nacional.

Segunda fonte do projeto, e a única coisa que ela precisa provar para servir é
que casa com a primeira. Casa: das 5.596 entidades que o CADPREV conhece, 5.594
existem no SICONFI com o mesmo CNPJ. Não há correspondência aproximada nem
normalização de nome — é igualdade de chave.

A API é outra criatura. Envelope diferente (``items`` e ``hasMore``, em vez de
``data`` e ``count``), paginação por ``offset``, e nenhum limite declarado de
requisições por segundo. Mesmo assim o cliente respeita uma pausa: um serviço
público que não pede calma não é um serviço público que a dispensa.

O que ela entrega e o CADPREV não tem, por ordem de utilidade:

* ``/entes`` — população, código IBGE e marca de capital, todos autoritativos.
  Este projeto vinha deduzindo esfera e capital por expressão regular sobre o
  nome do ente, e já errou: São Paulo e Rio de Janeiro, cujo município tem o
  mesmo nome do estado, foram classificados como estaduais.
* ``/rreo`` Anexo 04 — o demonstrativo previdenciário, com os investimentos
  separados entre fundo em capitalização, fundo em repartição e taxa de
  administração. É a decomposição que o CADPREV não expõe.
* ``/dca`` Anexo I-AB — o balanço, com as provisões matemáticas
  previdenciárias reconhecidas na contabilidade.
"""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterator, List, Mapping, Optional

log = logging.getLogger(__name__)

BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"

#: Quantos itens a API devolve por página.
PAGE_SIZE = 500

#: Identificação enviada no cabeçalho. Um serviço público tem direito de saber
#: quem o está consultando.
AGENTE = "painel-cadprev (github.com/gilbertotulli/dashboard-cadprev)"


class ErroDoSiconfi(RuntimeError):
    """A API não respondeu, ou respondeu o que não dá para usar."""


class Cliente:
    """GET paginado, com repetição e pausa entre páginas."""

    def __init__(self, base_url: str = BASE_URL, pausa: float = 0.5,
                 tentativas: int = 4, timeout: float = 90.0,
                 fixtures: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.pausa = pausa
        self.tentativas = tentativas
        self.timeout = timeout
        self.fixtures = fixtures
        self._ultima = 0.0

    # -- transporte -------------------------------------------------------

    def _esperar(self) -> None:
        agora = time.monotonic()
        falta = self.pausa - (agora - self._ultima)
        if falta > 0:
            time.sleep(falta)
        self._ultima = time.monotonic()

    def _get(self, caminho: str, params: Mapping[str, Any]) -> Dict[str, Any]:
        limpos = {k: v for k, v in params.items() if v is not None and v != ""}
        url = "{}/{}?{}".format(self.base_url, caminho.strip("/"),
                                urllib.parse.urlencode(limpos))
        espera, ultimo = 2.0, None
        for tentativa in range(1, self.tentativas + 1):
            self._esperar()
            try:
                pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
                with urllib.request.urlopen(pedido, timeout=self.timeout) as resposta:
                    return json.load(resposta)
            except urllib.error.HTTPError as erro:
                if 400 <= erro.code < 500 and erro.code not in (429, 503):
                    raise ErroDoSiconfi("{} respondeu {}".format(url, erro.code))
                ultimo = erro
            except Exception as erro:  # rede, timeout, JSON truncado
                ultimo = erro
            if tentativa < self.tentativas:
                log.warning("falha em /%s (tentativa %d/%d): %s — repetindo em %gs",
                            caminho, tentativa, self.tentativas, ultimo, espera)
                time.sleep(espera)
                espera *= 2
        raise ErroDoSiconfi("{} falhou após {} tentativas: {}".format(
            url, self.tentativas, ultimo))

    # -- API pública ------------------------------------------------------

    def pagina(self, caminho: str, offset: int = 0, **filtros: Any) -> Dict[str, Any]:
        if self.fixtures:
            import os
            arquivo = os.path.join(self.fixtures, caminho.strip("/") + ".json")
            if not os.path.exists(arquivo):
                raise ErroDoSiconfi("modo offline: falta a amostra " + arquivo)
            with open(arquivo, encoding="utf-8") as fh:
                dados = json.load(fh)
            return dados if isinstance(dados, dict) else {"items": dados,
                                                          "hasMore": False}
        return self._get(caminho, dict(filtros, offset=offset))

    def registros(self, caminho: str, **filtros: Any) -> Iterator[Dict[str, Any]]:
        """Todos os itens, seguindo ``hasMore`` até o fim."""
        offset = 0
        while True:
            pagina = self.pagina(caminho, offset=offset, **filtros)
            itens = pagina.get("items") or []
            for item in itens:
                yield item
            if self.fixtures or not pagina.get("hasMore") or not itens:
                return
            offset += len(itens)

    def entes(self) -> List[Dict[str, Any]]:
        """A tabela de entes da federação: uma requisição, o país inteiro."""
        return list(self.registros("entes"))
