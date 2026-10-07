"""A unidade gestora de cada RPPS — quem administra os recursos.

**Não vem da API.** O CADPREV identifica tudo pelo CNPJ do *ente federativo*, e
quem administra os recursos é a unidade gestora, que na maioria dos casos é
pessoa jurídica própria: autarquia, fundo ou instituto, com CNPJ próprio. Em
2.819 das 3.976 linhas do cadastro da SPREV o CNPJ da UG difere do CNPJ do ente.

A distinção importa fora do painel. O CNPJ que aparece como cotista no extrato
do administrador do fundo é o da **unidade gestora**, não o do ente — então sem
este mapeamento não se reconcilia o que o painel mostra com o que o custodiante
manda. É por isso que esta tabela existe.

A fonte é o arquivo ``cnpj-ente-cpnj-ug`` que a SPREV publica no Portal da
Previdência, atualizado até 31/07/2025 e convertido para ``data/unidade-gestora.csv``.
Só as linhas com **CNPJ vigente** entram: o cadastro guarda o histórico, e 960
das linhas de RPPS são de CNPJ inativo — uma UG que mudou de CNPJ aparece duas
vezes. Entre as vigentes não há ambiguidade: nenhum ente tem duas.

Cinco dos 2.131 RPPS do cadastro não têm nenhuma UG com CNPJ vigente. Para eles
a consulta devolve ``None``, que é diferente de devolver a UG inativa.
"""

import csv
import os
import re
from typing import Dict, Optional

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO = os.path.join(RAIZ, "data", "unidade-gestora.csv")

#: De onde a tabela vem, para a tela poder dizer. A data é a do arquivo da
#: SPREV, não a da conversão: é ela que diz quão atual o cadastro está.
FONTE = "SPREV · cadastro CNPJ ente × CNPJ UG, atualizado até 31/07/2025"

_SO_DIGITO = re.compile(r"\D")


def _normalizar_cnpj(valor: Optional[str]) -> str:
    return _SO_DIGITO.sub("", valor or "").zfill(14)


def _carregar() -> Dict[str, Dict[str, str]]:
    if not os.path.exists(ARQUIVO):
        return {}
    with open(ARQUIVO, encoding="utf-8", newline="") as fh:
        return {
            _normalizar_cnpj(linha["cnpj_ente"]): {
                "cnpj": _normalizar_cnpj(linha["cnpj_ug"]),
                "nome": (linha.get("unidade_gestora") or "").strip() or None,
                "natureza": (linha.get("natureza_juridica") or "").strip() or None,
                "regime": (linha.get("regime") or "").strip() or None,
            }
            for linha in csv.DictReader(fh)
        }


POR_ENTE: Dict[str, Dict[str, str]] = _carregar()


def da(cnpj_ente: Optional[str]) -> Optional[Dict[str, str]]:
    """A unidade gestora de um ente, ou ``None`` se o cadastro não a traz.

    >>> da("00003848000174")["natureza"]
    'Autarquia'
    >>> da("00000000000000") is None
    True
    """
    if not cnpj_ente:
        return None
    return POR_ENTE.get(_normalizar_cnpj(cnpj_ente))


def cobertura() -> int:
    """Quantos entes o cadastro alcança — para a aba de qualidade."""
    return len(POR_ENTE)
