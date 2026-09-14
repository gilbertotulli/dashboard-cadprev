"""Separação dos recursos investidos por natureza do fundo.

O problema
----------
A dimensão de plano existe na API e é nomeada ``FINANCEIRO`` (repartição
simples) e ``PREVIDENCIÁRIO`` (capitalização). Está **confirmada** em
``DIPR.plano_segreg``, ``RPPS_ALIQUOTA.plano_segregacao`` e
``DRAA_SEGREGACAO_MASSA``.

Na carteira do DAIR, **não**: o arquivo de dados abertos tem 15 colunas e
nenhuma identifica plano ou fundo. A informação existe na declaração de origem
— os DAIR em PDF gerados pelo CADPREV mostram os recursos vinculados aos planos
e à taxa de administração, e a Portaria MTP nº 1.467/2022 exige que a taxa de
administração seja mantida segregada — mas não se sabe se o endpoint a expõe.

A resposta do projeto
---------------------
Dois níveis, escolhidos em tempo de execução pelo que a API de fato entregou, e
declarados na interface:

**Nível A** — o endpoint expõe o plano do ativo. Decomposição de três vias do
patrimônio investido: capitalizado, repartição simples e taxa de administração.

**Nível B** — não expõe. Classifica-se o **RPPS**, não o ativo: sem segregação
de massa, a carteira inteira é capitalizada; com segregação, fica marcada como
*não decomposta*.

O que este módulo não faz, deliberadamente: ratear a carteira entre planos no
Nível B. Não há base no dado para isso, e o número resultante sairia daqui para
dentro de um ofício.
"""

import unicodedata
from typing import Dict, Iterable, Mapping, Optional

NIVEL_A = "A"
NIVEL_B = "B"

CAPITALIZADO = "capitalizado"
REPARTICAO = "reparticao"
TAXA_ADMINISTRACAO = "taxa_administracao"
NAO_DECOMPOSTO = "nao_decomposto"

ROTULOS = {
    CAPITALIZADO: "Capitalizado",
    REPARTICAO: "Repartição simples",
    TAXA_ADMINISTRACAO: "Taxa de administração",
    NAO_DECOMPOSTO: "Não decomposto",
}

#: Como cada rótulo aparece na fonte. A chave é a forma normalizada.
_SINONIMOS = {
    "previdenciario": CAPITALIZADO,
    "planoprevidenciario": CAPITALIZADO,
    "capitalizacao": CAPITALIZADO,
    "capitalizado": CAPITALIZADO,
    "financeiro": REPARTICAO,
    "planofinanceiro": REPARTICAO,
    "reparticao": REPARTICAO,
    "reparticaosimples": REPARTICAO,
    "taxadeadministracao": TAXA_ADMINISTRACAO,
    "taxaadministracao": TAXA_ADMINISTRACAO,
    "administrativa": TAXA_ADMINISTRACAO,
    "reservaadministrativa": TAXA_ADMINISTRACAO,
    "txadministracao": TAXA_ADMINISTRACAO,
}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return "".join(c for c in sem_acento.lower() if c.isalnum())


def classificar_plano(valor: Optional[str]) -> Optional[str]:
    """Traduz o rótulo de plano da fonte para a categoria do projeto.

    Devolve ``None`` quando o valor não corresponde a nenhuma categoria
    conhecida — o que precisa aparecer como "não classificado" na interface,
    nunca ser silenciosamente somado a capitalizado.

    >>> classificar_plano("PREVIDENCIÁRIO")
    'capitalizado'
    >>> classificar_plano("Plano Financeiro")
    'reparticao'
    >>> classificar_plano("qualquer outra coisa") is None
    True
    """
    if valor is None:
        return None
    return _SINONIMOS.get(_normalizar(valor))


def detectar_nivel(campos_resolvidos: Iterable[str]) -> str:
    """Decide o nível a partir do que a resolução de campos encontrou.

    >>> detectar_nivel(["cnpj_ente", "valor_total", "plano"])
    'A'
    >>> detectar_nivel(["cnpj_ente", "valor_total"])
    'B'
    """
    return NIVEL_A if "plano" in set(campos_resolvidos) else NIVEL_B


def classificar_rpps(possui_segregacao: Optional[bool]) -> str:
    """Classificação de Nível B: vale para a carteira inteira do RPPS.

    Sem segregação de massa, todo o patrimônio está no plano previdenciário —
    logo, capitalizado. Com segregação, o RPPS opera os dois planos e a carteira
    da base é única: qualquer divisão seria arbitrada.

    >>> classificar_rpps(False)
    'capitalizado'
    >>> classificar_rpps(True)
    'nao_decomposto'
    >>> classificar_rpps(None)
    'nao_decomposto'
    """
    if possui_segregacao is False:
        return CAPITALIZADO
    return NAO_DECOMPOSTO


def agregar(linhas: Iterable[Mapping], nivel: str,
            segregacao_por_cnpj: Optional[Mapping[str, Optional[bool]]] = None
            ) -> Dict[str, float]:
    """Soma o patrimônio por categoria de fundo, conforme o nível em vigor.

    Args:
        linhas: registros da carteira já traduzidos pelo ``fieldmap``.
        nivel: ``NIVEL_A`` ou ``NIVEL_B``.
        segregacao_por_cnpj: no Nível B, se cada RPPS segregou a massa.
    """
    segregacao = segregacao_por_cnpj or {}
    total: Dict[str, float] = {}
    for linha in linhas:
        valor = linha.get("valor_total") or 0.0
        if nivel == NIVEL_A:
            categoria = classificar_plano(linha.get("plano")) or NAO_DECOMPOSTO
        else:
            categoria = classificar_rpps(segregacao.get(linha.get("cnpj_ente")))
        total[categoria] = total.get(categoria, 0.0) + valor
    return total


def descrever_nivel(nivel: str) -> str:
    """Frase que a interface mostra para declarar o nível em vigor."""
    if nivel == NIVEL_A:
        return ("Nível A — a API expõe o plano de cada ativo; a carteira está "
                "decomposta entre capitalizado, repartição simples e taxa de "
                "administração.")
    return ("Nível B — a API não expõe o plano do ativo. A classificação é do "
            "RPPS, não do ativo: sem segregação de massa a carteira inteira é "
            "capitalizada; com segregação, fica como não decomposta.")
