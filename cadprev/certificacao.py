"""O que a SPREV já apurou sobre cada RPPS: Pró-Gestão e ISP.

**Nenhum dos dois vem da API.** São duas planilhas que a SPREV publica no Portal
da Previdência, e entram aqui pela mesma porta que o cadastro de unidades
gestoras: convertidas para CSV em ``data/``, com a data da fonte registrada, e
regeneráveis por ``python -m cadprev certificacao``.

**Pró-Gestão** é a certificação institucional, em níveis crescentes — Acesso, I,
II, III e IV. A planilha lista 717 entes, dos quais 332 têm certificação em
vigor e 385 só assinaram o termo de adesão. Aderir não é certificar, e o painel
mostra os dois estados separados: quem aderiu e ainda não certificou tem nível
vazio, não nível zero.

A coluna que vale é **NÍVEL ATUAL**. A coluna "nível inicial" guarda o histórico
numa string só — "I-II-II" são três certificações sucessivas — e lê-la como
nível daria "I-II-II" a um RPPS que hoje é nível II.

Dois valores da planilha não são nível nenhum e são publicados como a fonte os
escreve: "Acesso", que é a faixa abaixo do nível I, e "vencida", que é o que a
SPREV escreveu no lugar do nível de um ente cuja certificação caducou.

**O nível importa para investimentos.** A Resolução CMN 5.272/2025, que desde
02/02/2026 substitui a 4.963/2021, condiciona ao nível de adesão ao Pró-Gestão
quais ativos o RPPS pode ter e em que limite (art. 6º, § 3º). O painel mostra o
nível ao lado do nome e não emite juízo sobre a carteira: o rol por nível está
na resolução, e o limite de cada classe já vem declarado no próprio DAIR.

**ISP** é o Índice de Situação Previdenciária, anual. A edição de 2025 usa dados
de 2024 e classifica 2.133 entes em A, B, C ou D, com três eixos por trás —
gestão e transparência, finanças e liquidez, atuária. Um dos indicadores do eixo
de gestão é derivado do próprio Pró-Gestão, então os dois não são independentes.

As duas planilhas trazem o **CNPJ do ente**, que é a chave do projeto: 708 dos
709 entes do Pró-Gestão e os 2.133 do ISP casam com o índice do painel.
"""

import csv
import os
import re
from typing import Dict, Optional

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_PROGESTAO = os.path.join(RAIZ, "data", "pro-gestao.csv")
ARQUIVO_ISP = os.path.join(RAIZ, "data", "isp.csv")
ARQUIVO_ORIGEM = os.path.join(RAIZ, "data", "certificacao-fonte.json")


def _origem() -> Dict[str, Dict[str, str]]:
    import json
    if not os.path.exists(ARQUIVO_ORIGEM):
        return {}
    with open(ARQUIVO_ORIGEM, encoding="utf-8") as fh:
        return json.load(fh)


ORIGEM = _origem()


def _fonte(qual: str, rotulo: str) -> str:
    data = (ORIGEM.get(qual) or {}).get("data")
    return "{0}{1}".format(rotulo, ", de " + data if data else "")


#: De onde cada tabela vem. A data é a da planilha da SPREV, não a da conversão:
#: é ela que diz o quão atual o cadastro está.
FONTE_PROGESTAO = _fonte("pro_gestao",
                         "SPREV · relação de adesões e certificações Pró-Gestão")
FONTE_ISP = _fonte("isp", "SPREV · ISP, resultado final")

#: A ordem dos níveis, do menor para o maior. "vencida" não entra: não é nível,
#: é a ausência dele depois de ter havido um.
NIVEIS = ("Acesso", "I", "II", "III", "IV")

_SO_DIGITO = re.compile(r"\D")


def _normalizar_cnpj(valor: Optional[str]) -> str:
    return _SO_DIGITO.sub("", valor or "").zfill(14)


def _ler(arquivo: str) -> Dict[str, Dict[str, str]]:
    if not os.path.exists(arquivo):
        return {}
    with open(arquivo, encoding="utf-8", newline="") as fh:
        linhas = list(csv.DictReader(fh))
    return {
        _normalizar_cnpj(l["cnpj_ente"]):
            {k: (v or "").strip() or None for k, v in l.items() if k != "cnpj_ente"}
        for l in linhas
    }


PROGESTAO: Dict[str, Dict[str, str]] = _ler(ARQUIVO_PROGESTAO)
ISP: Dict[str, Dict[str, str]] = _ler(ARQUIVO_ISP)


def recarregar(pasta: Optional[str] = None) -> None:
    """Relê as tabelas, opcionalmente de outra pasta.

    Existe para o conjunto de demonstração: os CNPJ sintéticos do demo não
    estão na relação da SPREV, e sem isso o selo do Pró-Gestão nunca apareceria
    numa execução de demonstração — nem nos testes, que é onde ele precisa
    aparecer. A pasta ``None`` volta para ``data/``.
    """
    global PROGESTAO, ISP, ORIGEM, FONTE_PROGESTAO, FONTE_ISP
    base = pasta or os.path.join(RAIZ, "data")
    PROGESTAO = _ler(os.path.join(base, "pro-gestao.csv"))
    ISP = _ler(os.path.join(base, "isp.csv"))
    caminho = os.path.join(base, "certificacao-fonte.json")
    import json
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as fh:
            ORIGEM = json.load(fh)
    else:
        ORIGEM = {}
    FONTE_PROGESTAO = _fonte(
        "pro_gestao", "SPREV · relação de adesões e certificações Pró-Gestão")
    FONTE_ISP = _fonte("isp", "SPREV · ISP, resultado final")


def ordem_do_nivel(nivel: Optional[str]) -> Optional[int]:
    """A posição do nível na escala, ou ``None`` se não for um nível.

    Serve para ordenar e comparar sem espalhar a tabela de níveis pelo código.

    >>> ordem_do_nivel("III")
    3
    >>> ordem_do_nivel("Acesso")
    0
    >>> ordem_do_nivel("vencida") is None
    True
    """
    if not nivel:
        return None
    try:
        return NIVEIS.index(nivel.strip())
    except ValueError:
        return None


def pro_gestao(cnpj_ente: Optional[str]) -> Optional[Dict[str, object]]:
    """O que a planilha do Pró-Gestão diz sobre um ente, ou ``None``.

    Devolve o registro mesmo para quem só aderiu — nesse caso ``nivel`` é
    ``None`` e ``aderiu`` é a data do termo. Ausência de certificação não é
    ausência de registro.
    """
    if not cnpj_ente:
        return None
    linha = PROGESTAO.get(_normalizar_cnpj(cnpj_ente))
    if linha is None:
        return None
    nivel = linha.get("nivel")
    return {
        "nivel": nivel,
        "ordem": ordem_do_nivel(nivel),
        "certificado": ordem_do_nivel(nivel) is not None,
        "aderiu": linha.get("adesao"),
        "desde": linha.get("renovacao") or linha.get("certificacao"),
        "certificadora": linha.get("certificadora"),
        "fonte": FONTE_PROGESTAO,
    }


def isp(cnpj_ente: Optional[str]) -> Optional[Dict[str, object]]:
    """A nota do ISP de um ente e os três eixos por trás dela, ou ``None``."""
    if not cnpj_ente:
        return None
    linha = ISP.get(_normalizar_cnpj(cnpj_ente))
    if linha is None:
        return None
    return {
        "nota": linha.get("isp"),
        "gestao": linha.get("gestao"),
        "financas": linha.get("financas"),
        "atuaria": linha.get("atuaria"),
        "grupo": linha.get("grupo"),
        "subgrupo": linha.get("subgrupo"),
        "exercicio": linha.get("exercicio"),
        "fonte": FONTE_ISP,
    }


def cobertura() -> Dict[str, int]:
    """Quantos entes cada tabela alcança — para a aba de qualidade."""
    return {
        "pro_gestao": len(PROGESTAO),
        "certificados": sum(1 for l in PROGESTAO.values()
                            if ordem_do_nivel(l.get("nivel")) is not None),
        "isp": len(ISP),
    }
