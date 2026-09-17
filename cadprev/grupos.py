"""Classificação dos RPPS em grupos comparáveis.

Três recortes, com origens diferentes — e a diferença importa, porque um deles
não vem da API:

============  =========================================================
Recorte       Origem
============  =========================================================
Região        derivada de ``sg_uf``, direto da API
Esfera        derivada de ``no_ente``; RPPS estaduais aparecem como
              ``Governo do Estado do …``
Capital       **não vem da API** — depende de data/capitais.csv, tabela
              auxiliar mantida neste repositório
============  =========================================================

A dependência da tabela auxiliar é declarada na interface. Uma capital que mude
de grafia na base, ou um município homônimo, erra a classificação em silêncio se
ninguém disser de onde ela veio.
"""

import csv
import os
import re
import unicodedata
from typing import Dict, Optional, Set, Tuple

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_CAPITAIS = os.path.join(RAIZ, "data", "capitais.csv")

ESTADUAL = "estadual"
CAPITAL = "capital"
MUNICIPAL = "municipal"

ROTULOS_ESFERA = {
    ESTADUAL: "Estaduais",
    CAPITAL: "Capitais",
    MUNICIPAL: "Demais municípios",
}

REGIOES: Dict[str, str] = {}
for _regiao, _ufs in {
    "Norte": "AC AP AM PA RO RR TO",
    "Nordeste": "AL BA CE MA PB PE PI RN SE",
    "Centro-Oeste": "DF GO MT MS",
    "Sudeste": "ES MG RJ SP",
    "Sul": "PR RS SC",
}.items():
    for _uf in _ufs.split():
        REGIOES[_uf] = _regiao

ORDEM_REGIOES = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")

NOMES_UF = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco",
    "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}

#: O que marca um ente como a própria unidade federativa. O nome do estado
#: sozinho não basta: "São Paulo" e "Rio de Janeiro" são também municípios, e
#: são dois dos maiores RPPS municipais do país.
_MARCA_ESTADUAL = re.compile(r"^(governo\b|estado d|distrito federal\b)")
_MARCA_MUNICIPIO = re.compile(r"\bmunicip")


def _normalizar(texto: Optional[str]) -> str:
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def _carregar_capitais() -> Set[Tuple[str, str]]:
    if not os.path.exists(ARQUIVO_CAPITAIS):
        return set()
    with open(ARQUIVO_CAPITAIS, encoding="utf-8") as fh:
        return {
            (linha["uf"].strip().upper(), _normalizar(linha["municipio"]))
            for linha in csv.DictReader(fh)
        }


CAPITAIS: Set[Tuple[str, str]] = _carregar_capitais()

_NOMES_UF_NORMALIZADOS = {_normalizar(n) for n in NOMES_UF.values()}


def regiao(uf: Optional[str]) -> Optional[str]:
    """Região do RPPS a partir da UF.

    >>> regiao("ES")
    'Sudeste'
    >>> regiao("zz") is None
    True
    """
    if not uf:
        return None
    return REGIOES.get(uf.strip().upper())


def eh_estadual(uf: Optional[str], ente: Optional[str]) -> bool:
    """Se o ente é a própria unidade federativa.

    Os RPPS estaduais aparecem na base como ``Governo do Estado do Acre`` e
    variantes; alguns registros trazem só o nome do estado. Esse segundo caso é
    ambíguo de propósito em duas UF — a capital tem o mesmo nome do estado — e
    por isso a tabela de capitais desempata antes.

    >>> eh_estadual("AC", "Governo do Estado do Acre")
    True
    >>> eh_estadual("ES", "Espírito Santo")
    True
    >>> eh_estadual("ES", "Vitória")
    False
    >>> eh_estadual("SP", "São Paulo")          # o município, não o estado
    False
    >>> eh_estadual("RJ", "Rio de Janeiro")
    False
    >>> eh_estadual("SP", "Governo do Estado de São Paulo")
    True
    >>> eh_estadual("MG", "Governo do Município de Contagem")
    False
    >>> eh_estadual("MG", "Tocantins")          # o município mineiro
    False
    >>> eh_estadual("RN", "Espírito Santo")     # o município potiguar
    False
    """
    normal = _normalizar(ente)
    if not normal:
        return False
    if _MARCA_MUNICIPIO.search(normal):
        return False
    if _MARCA_ESTADUAL.match(normal):
        return True
    # Nome cru igual ao do PRÓPRIO estado, e não ao de qualquer um: há sete
    # municípios batizados com nome de outra unidade federativa — Tocantins em
    # Minas, Espírito Santo e Paraná no Rio Grande do Norte, Mato Grosso na
    # Paraíba —, e aceitar qualquer nome os promovia todos a governo estadual.
    # Ainda assim é só desempate: quando o SICONFI declara a esfera, ela vale.
    do_proprio_estado = _normalizar(NOMES_UF.get((uf or "").strip().upper(), ""))
    return bool(do_proprio_estado) and normal == do_proprio_estado \
        and not eh_capital(uf, ente)


def eh_capital(uf: Optional[str], ente: Optional[str]) -> bool:
    """Se o ente é a capital da sua UF, pela tabela auxiliar.

    >>> eh_capital("ES", "Vitória")
    True
    >>> eh_capital("ES", "Vila Velha")
    False
    """
    if not uf:
        return False
    return (uf.strip().upper(), _normalizar(ente)) in CAPITAIS


#: Como o SICONFI nomeia as esferas na tabela de entes da federação.
ESFERA_DO_SICONFI = {"E": ESTADUAL, "D": ESTADUAL, "M": MUNICIPAL}


def esfera(uf: Optional[str], ente: Optional[str],
           capital: Optional[bool] = None,
           esfera_fonte: Optional[str] = None) -> str:
    """Classifica em estadual, capital ou demais municípios.

    A ordem dos testes importa: o Distrito Federal é estadual e capital ao
    mesmo tempo, e conta como estadual, que é o que ele é do ponto de vista
    previdenciário.

    ``capital`` e ``esfera_fonte`` são as marcas autoritativas do SICONFI, que
    publica a tabela de entes da federação com a esfera ("E", "M", "D") e a
    capital sinalizadas. Quando elas vêm, nada é deduzido do nome: adivinhar só
    se justifica enquanto não há quem afirme, e a dedução por nome é justamente
    o que promovia o município de Amapá a governo do Amapá.

    >>> esfera("ES", "Governo do Estado do Espírito Santo")
    'estadual'
    >>> esfera("ES", "Vitória")
    'capital'
    >>> esfera("ES", "Vila Velha")
    'municipal'
    >>> esfera("SP", "São Paulo")
    'capital'
    >>> esfera("DF", "Governo do Distrito Federal")
    'estadual'
    """
    declarada = ESFERA_DO_SICONFI.get((esfera_fonte or "").strip().upper())
    if declarada == ESTADUAL:
        return ESTADUAL
    if declarada is None and eh_estadual(uf, ente):
        return ESTADUAL
    if capital if capital is not None else eh_capital(uf, ente):
        return CAPITAL
    return MUNICIPAL


def classificar(uf: Optional[str], ente: Optional[str],
                capital: Optional[bool] = None,
                esfera_fonte: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Todos os recortes de uma vez, com a origem de cada um."""
    return {
        "uf": (uf or "").strip().upper() or None,
        "regiao": regiao(uf),
        "esfera": esfera(uf, ente, capital, esfera_fonte),
    }


def cobertura_capitais() -> int:
    """Quantas capitais a tabela auxiliar conhece. Zero indica arquivo ausente."""
    return len(CAPITAIS)
