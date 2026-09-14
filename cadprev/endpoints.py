"""Catálogo dos endpoints da API do CADPREV.

A API segue um padrão único: o nome do recurso em maiúsculas é o próprio
caminho, os filtros vão na query string e a resposta volta sempre no mesmo
envelope ``{data, count, limit}``.

Fonte do catálogo: cliente R ``marcosfs2006/ADPrev`` e o tutorial ADPrev.
Ver docs/api-cadprev.md para a ressalva de verificação.
"""

from dataclasses import dataclass, field
from typing import Dict, Sequence, Tuple

#: Host canônico. Os espelhos `apicadprev.trabalho.gov.br` e
#: `apicadprev.economia.gov.br` respondem ao mesmo serviço — sobraram das
#: renomeações de pasta ministerial.
BASE_URL = "https://apicadprev.previdencia.gov.br"

MIRRORS = (
    "https://apicadprev.previdencia.gov.br",
    "https://apicadprev.trabalho.gov.br",
    "https://apicadprev.economia.gov.br",
)

#: Tamanho de página observado no cliente R. A última página é aquela em que
#: ``count < limit``.
PAGE_SIZE = 5000

# Conjuntos de filtros que se repetem entre endpoints.
ENTE = ("nr_cnpj_entidade", "no_ente", "sg_uf")
ENTE_MES = ENTE + ("dt_ano", "dt_mes")
ENTE_BIMESTRE = ENTE + ("dt_ano", "dt_mes_bimestre")
ENTE_EXERCICIO = ENTE + ("dt_exercicio",)


@dataclass(frozen=True)
class Endpoint:
    """Um recurso da API.

    Attributes:
        nome: caminho do recurso, em maiúsculas.
        familia: agrupamento usado no painel e na documentação.
        descricao: o que o recurso devolve.
        filtros: parâmetros de consulta aceitos, além de ``offset``.
        periodicidade: unidade de tempo do registro, quando há.
    """

    nome: str
    familia: str
    descricao: str
    filtros: Sequence[str] = field(default=ENTE)
    periodicidade: str = "cadastral"

    @property
    def path(self) -> str:
        return "/" + self.nome


def _e(nome, familia, descricao, filtros=ENTE, periodicidade="cadastral"):
    return Endpoint(nome, familia, descricao, filtros, periodicidade)


CATALOGO: Tuple[Endpoint, ...] = (
    # --- cadastro e regularidade ---
    _e("RPPS_REGIME_PREVIDENCIARIO", "cadastro",
       "Regime previdenciário do ente: RGPS, RPPS ou RPPS em extinção"),
    _e("RPPS_CRP", "cadastro",
       "Certificado de Regularidade Previdenciária: número, emissão, validade, "
       "via judicial e situação"),
    _e("RPPS_ALIQUOTA", "cadastro",
       "Alíquotas de contribuição por plano e sujeito passivo, com vigência"),

    # --- DIPR ---
    _e("DIPR", "dipr",
       "Informações previdenciárias e repasses: bases de cálculo, contribuições, "
       "aportes, ingressos, dispêndios e resultado do período",
       ENTE_MES, "mensal"),

    # --- DAIR ---
    _e("DAIR_CARTEIRA", "dair",
       "Carteira de investimentos ativo a ativo, com o limite da Resolução "
       "CMN 3.922/10 no próprio registro",
       ENTE_BIMESTRE, "mensal"),
    _e("DAIR_APLICACOES_RESGATE", "dair",
       "APR — autorizações para aplicação e resgate",
       ENTE_MES, "mensal"),

    # --- DRAA ---
    _e("DRAA_ENCAMINHAMENTO", "draa",
       "Envio do DRAA à SPREV: data e situação", ENTE_EXERCICIO, "anual"),
    _e("DRAA_DADOS_CONSOLIDADOS", "draa",
       "Consolidação do demonstrativo", ENTE_EXERCICIO, "anual"),
    _e("DRAA_ESTATISTICA", "draa",
       "Massa de participantes: ativos, aposentados, pensionistas, dependentes",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_VALORES_COMPROMISSOS", "draa",
       "Compromissos por código e descrição, em geração atual e futura",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_SEGREGACAO_MASSA", "draa",
       "Divisão entre plano financeiro e plano previdenciário",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_PLANO_CUSTEIO", "draa",
       "Custo normal e custo suplementar", ENTE_EXERCICIO, "anual"),
    _e("DRAA_PLANO_BENEFICIO", "draa",
       "Benefícios cobertos pelo plano", ENTE_EXERCICIO, "anual"),
    _e("DRAA_CONTRIBUICAO", "draa",
       "Contribuições consideradas na avaliação", ENTE_EXERCICIO, "anual"),
    _e("DRAA_PLANO_AMORTIZACAO", "draa",
       "Plano de equacionamento do déficit atuarial", ENTE_EXERCICIO, "anual"),
    _e("DRAA_FORMA_AMORTIZACAO", "draa",
       "Forma de amortização adotada", ENTE_EXERCICIO, "anual"),
    _e("DRAA_FLUXO_ATUARIAL", "draa",
       "Projeção anual de receitas, despesas e saldo do plano",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_HIPOTESE_ATUARIAL", "draa",
       "Taxa de juros, crescimento salarial e rotatividade",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_HIPOTESE_BIOMETRICA", "draa",
       "Tábuas de mortalidade, invalidez e sobrevivência",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_PARECER_ATUARIAL", "draa",
       "Parecer do atuário responsável", ENTE_EXERCICIO, "anual"),
    _e("DRAA_COMPARATIVO_AVALIACAO", "draa",
       "Comparação entre exercícios", ENTE_EXERCICIO, "anual"),
    _e("DRAA_COMPARATIVO_RECEITA", "draa",
       "Comparação de receitas entre exercícios", ENTE_EXERCICIO, "anual"),
)

POR_NOME: Dict[str, Endpoint] = {e.nome: e for e in CATALOGO}

FAMILIAS = {
    "cadastro": "Cadastro e regularidade",
    "dipr": "DIPR — informações previdenciárias e repasses",
    "dair": "DAIR — aplicações e investimentos",
    "draa": "DRAA — avaliação atuarial",
}


def get(nome: str) -> Endpoint:
    """Devolve o endpoint pelo nome, com erro legível se não existir."""
    try:
        return POR_NOME[nome]
    except KeyError:
        conhecidos = ", ".join(sorted(POR_NOME))
        raise KeyError(
            "endpoint desconhecido: {!r}.\nDisponíveis: {}".format(nome, conhecidos)
        ) from None
