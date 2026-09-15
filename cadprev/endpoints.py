"""Catálogo dos endpoints da API do CADPREV.

A API segue um padrão único: o nome do recurso em maiúsculas é o próprio
caminho, os filtros vão na query string e a resposta volta sempre no mesmo
envelope ``{data, count, limit}``.

Fonte do catálogo: cliente R ``marcosfs2006/ADPrev`` e o tutorial ADPrev.
Ver docs/api-cadprev.md para a ressalva de verificação.
"""

from dataclasses import dataclass, field
from typing import Dict, Sequence, Tuple

#: Host da API, verificado contra DNS e contra respostas reais em 15/09/2026.
#:
#: Atenção ao histórico: este projeto chegou a adotar
#: `apicadprev.previdencia.gov.br` por inferência sobre a renomeação da pasta
#: ministerial. Esse host **não existe** — não resolve em DNS. Nem
#: `apicadprev.economia.gov.br`, que aparece em buscas como endereço da
#: documentação. O único host que responde é o `trabalho.gov.br`, o mesmo que o
#: cliente R de referência sempre usou.
BASE_URL = "https://apicadprev.trabalho.gov.br"

#: Hosts que já foram citados para esta API e hoje não resolvem. Ficam
#: registrados para que ninguém os reintroduza por inferência.
HOSTS_MORTOS = (
    "https://apicadprev.previdencia.gov.br",
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
    # --- serviço ---
    _e("DATA_ATUALIZACAO", "servico",
       "Data da última atualização dos dados da API", (), "—"),

    # --- cadastro e regularidade ---
    _e("RPPS_REGIME_PREVIDENCIARIO", "cadastro",
       "Regime previdenciário do ente e a legislação que o criou"),
    _e("RPPS_CRP", "cadastro",
       "Histórico de Certificados de Regularidade Previdenciária"),
    _e("RPPS_ALIQUOTA", "cadastro",
       "Alíquotas de contribuição por plano e sujeito passivo, com vigência"),

    # --- DIPR ---
    _e("DIPR", "dipr",
       "Informações previdenciárias e repasses, uma linha por rubrica, "
       "mês, plano e órgão",
       ENTE_MES, "mensal"),

    # --- DAIR ---
    _e("DAIR_CARTEIRA", "dair",
       "Carteira de investimentos ativo a ativo, com o limite da Resolução "
       "CMN 3.922/10 no próprio registro",
       ENTE_BIMESTRE, "mensal"),
    _e("DAIR_APLICACOES_RESGATE", "dair",
       "APR — aplicações e resgates, com o plano/fundo de cada operação",
       ENTE_MES, "mensal"),
    _e("DAIR_IDENTIFICACAO", "dair",
       "Identificação do DAIR: finalidade, data de posição e retificações",
       ENTE_MES, "mensal"),
    _e("DAIR_FORMA_GESTAO", "dair",
       "Forma de gestão dos recursos e contratos de consultoria",
       ENTE_MES, "mensal"),
    _e("DAIR_GOVERNANCA", "dair",
       "Colegiados, comitê de investimentos e certificações dos responsáveis",
       ENTE_MES, "mensal"),
    _e("DAIR_INSTITUICAO_CREDENCIADA", "dair",
       "Instituições financeiras credenciadas pelo RPPS", ENTE_MES, "mensal"),
    _e("DAIR_FUNDO_INVEST_ANALISADOS", "dair",
       "Fundos de investimento analisados pelo RPPS", ENTE_MES, "mensal"),
    _e("DAIR_REGIME_ATA", "dair",
       "Atas das reuniões dos colegiados", ENTE_MES, "mensal"),

    # --- DRAA ---
    _e("DRAA_ENCAMINHAMENTO", "draa",
       "Envio do DRAA à SPREV: data e situação", ENTE_EXERCICIO, "anual"),
    _e("DRAA_DADOS_CONSOLIDADOS", "draa",
       "Contratos e responsáveis consolidados", ENTE_MES, "anual"),
    _e("DRAA_ESTATISTICA", "draa",
       "Massa de participantes por grupo populacional, com contagem, folha e "
       "idades médias separadas por sexo",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_ORGAO_ENTIDADE", "draa",
       "Órgãos e entidades cobertos pelo plano", ENTE_EXERCICIO, "anual"),
    _e("DRAA_VALORES_COMPROMISSOS", "draa",
       "Demonstrativo de resultado atuarial por item, em geração atual e futura",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_SEGREGACAO_MASSA", "draa",
       "Segregação da massa, previdência complementar e norma que a instituiu",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_PLANO_CUSTEIO", "draa",
       "Plano de custeio por tipo de contribuição, com alíquota definida",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_PLANO_BENEFICIO", "draa",
       "Benefícios do plano e o regime financeiro de cada um",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_CONTRIBUICAO", "draa",
       "Contribuições por base de cálculo e tipo de beneficiário",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_BASE_CALCULO_ENTE", "draa",
       "Bases de cálculo das contribuições do ente", ENTE_EXERCICIO, "anual"),
    _e("DRAA_BASE_CALCULO_AMORTIZACAO", "draa",
       "Bases de cálculo do plano de amortização", ENTE_EXERCICIO, "anual"),
    _e("DRAA_PLANO_AMORTIZACAO", "draa",
       "Plano de amortização ano a ano: saldo inicial, juros, pagamentos e "
       "saldo final — a única série temporal da família DRAA",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_PLANO_AMORTIZACAO_DEFICIT", "draa",
       "Bases de cálculo da amortização do déficit", ENTE_EXERCICIO, "anual"),
    _e("DRAA_FORMA_AMORTIZACAO", "draa",
       "Forma de amortização adotada", ENTE_EXERCICIO, "anual"),
    _e("DRAA_CUSTO_NORMAL_BENEF_CAPIT", "draa",
       "Custo normal dos benefícios em capitalização", ENTE_EXERCICIO, "anual"),
    _e("DRAA_CUSTO_NORMAL_BENEF_COB", "draa",
       "Custo normal dos benefícios cobertos", ENTE_EXERCICIO, "anual"),
    _e("DRAA_CUSTO_NORMAL_REP_APOS", "draa",
       "Custo normal em repartição — aposentadorias", ENTE_EXERCICIO, "anual"),
    _e("DRAA_CUSTO_NORMAL_REP_AUX", "draa",
       "Custo normal em repartição — auxílios", ENTE_EXERCICIO, "anual"),
    _e("DRAA_FLUXO_ATUARIAL", "draa",
       "Fluxo atuarial por item, com um valor projetado cada. NÃO é série "
       "temporal: a projeção ano a ano só existe nos dados abertos",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_HIPOTESE_ATUARIAL", "draa",
       "Hipóteses demográficas e econômicas, com previsto e ocorrido",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_HIPOTESE_BIOMETRICA", "draa",
       "Tábuas de mortalidade, invalidez e sobrevivência, por sexo",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_PARECER_ATUARIAL", "draa",
       "Parecer do atuário responsável, por tema", ENTE_EXERCICIO, "anual"),
    _e("DRAA_COMPARATIVO_AVALIACAO", "draa",
       "Comparação de itens entre exercícios", ENTE_EXERCICIO, "anual"),
    _e("DRAA_COMPARATIVO_RECEITA", "draa",
       "Receitas projetadas contra executadas, por item de fluxo",
       ENTE_EXERCICIO, "anual"),
    _e("DRAA_NOTIFICACAO", "draa",
       "Notificações da SPREV sobre o demonstrativo, com prazo e resposta"),
    _e("DRAA_RETIFICACAO_NOTIFICACAO", "draa",
       "Retificações motivadas por notificação", ENTE_EXERCICIO, "anual"),
)

POR_NOME: Dict[str, Endpoint] = {e.nome: e for e in CATALOGO}

FAMILIAS = {
    "servico": "Serviço",
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
