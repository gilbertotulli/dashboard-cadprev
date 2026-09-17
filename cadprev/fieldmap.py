"""Mapeamento entre os campos da resposta da API e os nomes usados no projeto.

Os nomes aqui foram **verificados contra respostas reais** da API em 15/09/2026,
com amostras do Espírito Santo. A evidência está em ``docs/schema-observado/``:
um arquivo por endpoint, com as chaves observadas e registros de exemplo.

A camada continua existindo por dois motivos. Primeiro, porque a API já mudou de
host uma vez e pode mudar de campo: um nome novo entra como candidato e nada
mais no projeto precisa saber. Segundo, porque a resolução falha alto quando um
campo obrigatório some — melhor do que gravar uma coluna de nulos que ninguém
percebe até o número já ter circulado.

Formato longo
-------------
Vários endpoints não devolvem uma linha por ente, e sim uma linha por item:

* ``DIPR`` — uma linha por rubrica, por mês e por plano. Os totais de ingresso e
  dispêndio não existem como campo: saem da soma das rubricas. Ver ``rubricas.py``.
* ``DRAA_ESTATISTICA`` — uma linha por grupo populacional, com contagem separada
  por sexo.
* ``DRAA_FLUXO_ATUARIAL`` — uma linha por item de fluxo, com um único valor
  projetado. **Não é série temporal**: a projeção ano a ano existe nos arquivos
  de dados abertos, não na API.
* ``DRAA_VALORES_COMPROMISSOS``, ``DRAA_HIPOTESE_ATUARIAL``,
  ``DRAA_PLANO_CUSTEIO`` — uma linha por item do demonstrativo.
* ``RPPS_CRP`` e ``RPPS_ALIQUOTA`` — o histórico inteiro, não a posição atual.

A agregação de cada um está em ``build.py``; aqui ficam só os nomes e os tipos.

Corrigir sem editar código
--------------------------
``fieldmap.local.json`` na raiz do repositório sobrepõe este mapa::

    {"DAIR_CARTEIRA": {"valor_total": "vl_total_atual"}}

``python -m cadprev inspect DAIR_CARTEIRA --uf ES`` mostra o que a API devolve
hoje e sugere o conteúdo desse arquivo.
"""

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_OVERRIDE = os.path.join(RAIZ, "fieldmap.local.json")


class CampoNaoEncontrado(LookupError):
    """Nenhum candidato de um campo obrigatório existe na resposta."""


@dataclass(frozen=True)
class Campo:
    """Um campo lógico e os nomes sob os quais ele pode chegar.

    Attributes:
        nome: nome usado no projeto, estável mesmo que a API mude.
        candidatos: nomes possíveis na resposta, em ordem de preferência.
        tipo: ``texto``, ``inteiro``, ``decimal``, ``data``, ``cnpj`` ou ``booleano``.
        obrigatorio: se ausente, a ingestão falha em vez de seguir com nulo.
        nota: observação que sobrevive à leitura do código.
    """

    nome: str
    candidatos: Tuple[str, ...]
    tipo: str = "texto"
    obrigatorio: bool = True
    nota: str = ""


def _c(nome, *candidatos, tipo="texto", obrigatorio=True, nota=""):
    return Campo(nome, tuple(candidatos), tipo, obrigatorio, nota)


# Campos de identificação, presentes em todos os endpoints.
_IDENT = (
    _c("cnpj_ente", "nr_cnpj_entidade", "cnpj_ente", "cnpj", tipo="cnpj"),
    _c("ente", "no_ente", "ente", "nm_ente"),
    _c("uf", "sg_uf", "uf"),
)

# O DRAA repete plano e massa em quase todos os seus recursos.
_PLANO_MASSA = (
    _c("exercicio", "dt_exercicio", "exercicio", tipo="inteiro"),
    _c("plano", "tp_plano", "ds_plano_segregacao", obrigatorio=False,
       nota="Previdenciário (capitalização), Financeiro (repartição) ou "
            "Mantidos pelo Tesouro"),
    _c("massa", "tp_massa", obrigatorio=False, nota="Civil ou Militar"),
)

MAPA: Dict[str, Tuple[Campo, ...]] = {
    "RPPS_REGIME_PREVIDENCIARIO": _IDENT + (
        _c("regime", "tp_regime", "ds_regime", "regime",
           nota="RPPS ou RGPS"),
        _c("inicio", "dt_inicio", tipo="data", obrigatorio=False),
        _c("fim", "dt_fim", tipo="data", obrigatorio=False,
           nota="nulo = vigente; o endpoint devolve o histórico de legislação"),
        _c("tipo_legislacao", "no_tipo_legislacao", obrigatorio=False),
        _c("numero_legislacao", "nr_legislacao", obrigatorio=False),
    ),
    # Os dois campos abaixo estão TROCADOS na API em relação à própria
    # documentação. O Swagger descreve ds_situacao como "Vigente ou Vencido" e
    # tp_crp como "Administrativo ou Judicial"; as respostas reais de 15/09/2026
    # devolvem o contrário. Por isso os dois são lidos crus e a classificação
    # acontece pelo VALOR, em build.py — assim continua certo se a SPREV
    # corrigir a inversão.
    "RPPS_CRP": _IDENT + (
        _c("numero_crp", "nr_crp", "num_crp"),
        _c("emissao", "dt_emissao", tipo="data"),
        _c("validade", "dt_validade", tipo="data"),
        _c("campo_situacao", "ds_situacao", obrigatorio=False,
           nota="documentado como Vigente/Vencido; na prática traz "
                "Administrativo/Judicial"),
        _c("campo_tipo", "tp_crp", obrigatorio=False,
           nota="documentado como Administrativo/Judicial; na prática traz "
                "Válido/Vencido"),
    ),
    "RPPS_ALIQUOTA": _IDENT + (
        _c("plano", "ds_plano_segregacao", "plano_segregacao",
           nota="'Fundo em Capitalização' ou 'Fundo em Repartição'"),
        _c("sujeito_passivo", "no_sujeito_passivo", "ds_sujeito_passivo"),
        _c("aliquota", "vl_aliquota", "aliquota", tipo="decimal"),
        _c("inicio_vigencia", "dt_inicio_vigencia", tipo="data"),
        _c("fim_vigencia", "dt_fim_vigencia", tipo="data", obrigatorio=False),
        _c("vigente", "id_vigente", obrigatorio=False,
           nota="VIGENTE ou NÃO VIGENTE — declarado, não inferido da data"),
    ),
    "DIPR": _IDENT + (
        _c("ano", "dt_ano", "ano", tipo="inteiro"),
        _c("mes", "dt_mes", "mes", tipo="inteiro"),
        _c("plano", "no_plano", "ds_plano_segregacao", obrigatorio=False,
           nota="PREVIDENCIARIO ou FINANCEIRO — a dimensão capitalizado x "
                "repartição, confirmada na API"),
        _c("rubrica", "no_rubrica",
           nota="sigla da rubrica; o prefixo UT- marca dispêndio. Ver rubricas.py"),
        _c("descricao_rubrica", "te_rubrica", obrigatorio=False),
        _c("codigo_rubrica", "id_rubrica", tipo="inteiro", obrigatorio=False),
        _c("valor", "vl_rubrica", tipo="decimal"),
        _c("orgao", "no_orgao", obrigatorio=False),
        _c("envio", "dt_envio", tipo="data", obrigatorio=False),
    ),
    "DAIR_IDENTIFICACAO": _IDENT + (
        _c("ano", "dt_ano", tipo="inteiro"),
        _c("mes", "dt_mes", tipo="inteiro",
           nota="mensal, ao contrário da carteira, que vem por bimestre"),
        _c("posicao", "dt_posicao", tipo="data",
           nota="data a que o demonstrativo se refere; é dela que sai a "
                "defasagem de quem parou de declarar"),
        _c("envio", "dt_envio", tipo="data", obrigatorio=False,
           nota="quando chegou; comparada à posição, dá o atraso de entrega"),
        _c("finalidade", "te_finalidade", obrigatorio=False),
        _c("motivo_retificacao", "te_motivo_retificacao", obrigatorio=False),
    ),

    "DAIR_CARTEIRA": _IDENT + (
        _c("ano", "dt_ano", tipo="inteiro"),
        _c("mes", "dt_mes_bimestre", tipo="inteiro"),
        _c("segmento", "no_segmento", "ds_segmento", "segmento",
           nota="inclui 'Disponibilidades Financeiras', que não é alocação"),
        _c("tipo_ativo", "no_tipo_ativo", "tipo_ativo", obrigatorio=False),
        _c("limite_cmn", "pc_cmn", "limite_resol_cmn", tipo="decimal",
           obrigatorio=False,
           nota="teto da Resolução CMN 3.922/10, no próprio registro do ativo"),
        _c("identificacao_ativo", "id_ativo", "ident_ativo", obrigatorio=False),
        _c("nome_ativo", "no_fundo", "nm_ativo", obrigatorio=False),
        _c("quantidade_cotas", "qt_rpps", "qtd_quotas", tipo="decimal",
           obrigatorio=False),
        _c("valor_unitario", "vl_atual_ativo", "vlr_atual_ativo", tipo="decimal",
           obrigatorio=False),
        _c("valor_total", "vl_total_atual", "vlr_total_atual", tipo="decimal"),
        _c("perc_recursos", "pc_rpps", "perc_recursos_rpps", tipo="decimal",
           obrigatorio=False),
        _c("pl_fundo", "vl_patrimonio", "pl_fundo", tipo="decimal", obrigatorio=False),
        _c("perc_pl_fundo", "pc_patrimonio", "perc_pl_fundo", tipo="decimal",
           obrigatorio=False),
        # --- a pergunta central do projeto, agora respondida ---
        _c("plano", "ds_plano", "ds_plano_segregacao", "tp_recurso",
           obrigatorio=False,
           nota="NÃO EXISTE na API (verificado em 15/09/2026). A carteira não "
                "traz o plano do ativo, então o projeto opera no Nível B: "
                "classifica o RPPS, não o ativo. Mantido como candidato para o "
                "dia em que a SPREV expuser o campo. Ver fundos.py"),
    ),
    "DRAA_ESTATISTICA": _IDENT + _PLANO_MASSA + (
        _c("tipo_populacao", "tp_populacao",
           nota="Servidores, Aposentados, Pensionistas, Servidores Iminentes, "
                "Militares"),
        _c("categoria_populacao", "no_cat_populacao", obrigatorio=False),
        _c("qt_masculino", "qt_grupo_masc", tipo="inteiro", obrigatorio=False),
        _c("qt_feminino", "qt_grupo_fem", tipo="inteiro", obrigatorio=False),
        _c("folha_masculino", "vl_folha_mensal_masc", tipo="decimal",
           obrigatorio=False),
        _c("folha_feminino", "vl_folha_mensal_fem", tipo="decimal",
           obrigatorio=False),
        _c("idade_media_masculino", "vl_idade_media_masc", tipo="decimal",
           obrigatorio=False),
        _c("idade_media_feminino", "vl_idade_media_fem", tipo="decimal",
           obrigatorio=False),
    ),
    "DRAA_SEGREGACAO_MASSA": _IDENT + _PLANO_MASSA + (
        _c("segregacao", "no_segregacao_massa", obrigatorio=False,
           nota="'Não Possui' ou 'Instituida neste Exercicio ou Mantida'"),
        _c("data_ingresso_segurado", "dt_ingresso_segurado", tipo="data",
           obrigatorio=False),
        _c("norma", "nr_norma_fundamento", obrigatorio=False),
        _c("data_norma", "dt_norma_fundamento", tipo="data", obrigatorio=False),
    ),
    "DRAA_FLUXO_ATUARIAL": _IDENT + _PLANO_MASSA + (
        _c("codigo", "nr_fluxo", tipo="inteiro",
           nota="190000 = total das receitas; 240000 = total das despesas; "
                "250001 = insuficiência ou excedente. Ver codigos.py"),
        _c("descricao", "no_fluxo"),
        _c("valor", "vl_projetado", tipo="decimal", obrigatorio=False),
    ),
    "DRAA_VALORES_COMPROMISSOS": _IDENT + _PLANO_MASSA + (
        _c("codigo", "cd_demonstrativo", tipo="inteiro",
           nota="600100 = déficit atuarial; 600300 = superávit. Ver codigos.py"),
        _c("descricao", "ds_item_resultado", "ds_variavel"),
        _c("categoria", "no_categoria_demonstrativo", obrigatorio=False,
           nota="'Titulo' é cabeçalho de seção; só 'Resultado' tem valor"),
        _c("geracao_atual", "vl_geracao_atual", tipo="decimal", obrigatorio=False),
        _c("geracao_futura", "vl_geracao_futura", tipo="decimal",
           obrigatorio=False),
    ),
    "DRAA_HIPOTESE_ATUARIAL": _IDENT + _PLANO_MASSA + (
        _c("codigo", "cd_hipotese_demografica", tipo="inteiro",
           obrigatorio=False),
        _c("descricao", "ds_hipotese_demografica", "ds_hipotese"),
        _c("unidade", "tp_unidade", obrigatorio=False,
           nota="PERCENTUAL, ANOS, etc."),
        _c("valor", "te_hipotese_demografica", obrigatorio=False,
           nota="texto: pode ser número, tábua ou justificativa"),
        _c("longo_prazo", "vl_perspectiva_longo_prazo", tipo="decimal",
           obrigatorio=False),
    ),
    # --- SICONFI: outra fonte, outros nomes, mesma chave ---
    #
    # A tabela de entes da federação do Tesouro. Não usa _IDENT porque o
    # SICONFI nomeia as colunas de identificação de outro jeito: `cnpj`, `ente`
    # e `uf`, sem o prefixo. O que casa as duas bases é o CNPJ, e ele casa em
    # 5.594 dos 5.596 entes que o CADPREV conhece.
    "SICONFI_ENTE": (
        _c("cnpj_ente", "cnpj", tipo="cnpj"),
        _c("ente", "ente"),
        _c("uf", "uf"),
        _c("cod_ibge", "cod_ibge", tipo="inteiro", obrigatorio=False),
        _c("populacao", "populacao", tipo="inteiro", obrigatorio=False),
        _c("capital", "capital", tipo="booleano", obrigatorio=False,
           nota="vem como texto com espaços à direita — \"1  \", \"0  \" — e é "
                "a marca autoritativa de capital, no lugar da dedução por nome "
                "que classificou São Paulo e Rio de Janeiro como estaduais"),
        _c("esfera_siconfi", "esfera", obrigatorio=False, nota="M, E, U ou D"),
        _c("regiao_siconfi", "regiao", obrigatorio=False),
        _c("exercicio", "exercicio", tipo="inteiro", obrigatorio=False),
    ),

    # O RREO Anexo 04 é o demonstrativo previdenciário do RPPS. A resposta não
    # traz CNPJ — só o código IBGE —, então quem ingere acrescenta o `cnpj_ente`
    # a partir da tabela de entes, que é o que casa as duas bases.
    #
    # O `cod_conta` é semântico e é ele que separa os três fundos:
    # ...RPPSPrevidenciario é a capitalização, ...FundoEmReparticao é a
    # repartição e ...AdministracaoDoRPPS é a taxa de administração. Essa é a
    # decomposição que o CADPREV não expõe e que este projeto documentava como
    # inalcançável.
    "SICONFI_RREO": (
        _c("cnpj_ente", "cnpj_ente", tipo="cnpj"),
        _c("cod_ibge", "cod_ibge", tipo="inteiro"),
        _c("ente", "instituicao", obrigatorio=False),
        _c("uf", "uf", obrigatorio=False),
        _c("exercicio", "exercicio", tipo="inteiro"),
        _c("periodo", "periodo", tipo="inteiro"),
        _c("anexo", "anexo", obrigatorio=False),
        _c("demonstrativo", "demonstrativo", obrigatorio=False,
           nota="RREO ou RREO Simplificado; municípios menores usam o segundo, "
                "e consultar só o primeiro esconde 45% dos entes"),
        _c("coluna", "coluna",
           nota="PREVISÃO ATUALIZADA, RECEITAS REALIZADAS ATÉ O BIMESTRE, "
                "DESPESAS PAGAS ATÉ O BIMESTRE, SALDO ATUAL e congêneres"),
        _c("cod_conta", "cod_conta"),
        _c("conta", "conta", obrigatorio=False),
        _c("valor", "valor", tipo="decimal", obrigatorio=False),
    ),

    # --- o que a SPREV apontou, e o que o próprio demonstrativo confronta ---
    "DRAA_ENCAMINHAMENTO": _IDENT + (
        _c("exercicio", "dt_exercicio", tipo="inteiro"),
        _c("envio", "dt_envio", tipo="data",
           nota="é daqui que sai o índice de mudança do DRAA: sem filtro por "
                "data de alteração na API, esta é a forma barata de saber "
                "quem reenviou desde a última carga"),
        _c("situacao", "te_situacao", obrigatorio=False,
           nota="Documentos Digitalizados, Substituída Antes da Recepção..."),
    ),

    "DRAA_NOTIFICACAO": _IDENT + (
        _c("numero", "nr_notificacao"),
        _c("tipo_documento", "no_tipo_documento", obrigatorio=False),
        _c("item_analise", "no_item_analise", obrigatorio=False,
           nota="o que a SPREV examinou, por exemplo "
                "'Consistência - Segregação da Massa'"),
        _c("situacao_item", "no_situacao_item_analise", obrigatorio=False,
           nota="'Resposta analisada. Item sem pendencia' e congêneres; é o "
                "que separa apontamento aberto de encerrado"),
        _c("notificacao", "dt_notificao", "dt_notificacao", tipo="data",
           obrigatorio=False,
           nota="o nome vem grafado sem o 'ca' na API (dt_notificao); o "
                "candidato correto fica listado para o dia em que corrigirem"),
        _c("preclusao", "dt_preclusao", tipo="data", obrigatorio=False),
        _c("resposta", "dt_resposta", tipo="data", obrigatorio=False),
        _c("prazo_resposta", "nr_prazo_resposta", tipo="inteiro",
           obrigatorio=False),
    ),

    "DRAA_COMPARATIVO_RECEITA": _IDENT + _PLANO_MASSA + (
        _c("exercicio_inicial", "dt_exercicio_inicial", tipo="inteiro",
           obrigatorio=False),
        _c("codigo_fluxo", "nr_fluxo", tipo="inteiro", obrigatorio=False),
        _c("fluxo", "no_fluxo", obrigatorio=False),
        _c("projetado", "vl_projetado", tipo="decimal", obrigatorio=False),
        _c("executado", "vl_executado", tipo="decimal", obrigatorio=False),
        _c("diferenca", "vl_diferenca", tipo="decimal", obrigatorio=False,
           nota="a fonte já calcula; o painel confere em vez de recalcular"),
        _c("envio", "dt_envio", tipo="data", obrigatorio=False),
        _c("situacao", "te_situacao", obrigatorio=False),
    ),

    "DRAA_PLANO_AMORTIZACAO": _IDENT + _PLANO_MASSA + (
        _c("ano", "dt_ano", tipo="inteiro",
           nota="o ano projetado, que pode estar décadas à frente do exercício "
                "— esta é a única série temporal ano a ano da API"),
        _c("saldo_inicial", "vl_saldo_inicial", tipo="decimal", obrigatorio=False),
        _c("juros", "vl_juros", tipo="decimal", obrigatorio=False),
        _c("amortizacao", "vl_amortizacao", tipo="decimal", obrigatorio=False),
        _c("pagamentos", "vl_pagamentos", tipo="decimal", obrigatorio=False),
        _c("aporte", "vl_aporte", tipo="decimal", obrigatorio=False),
        _c("saldo_final", "vl_saldo_final", tipo="decimal", obrigatorio=False),
        _c("base_calculo", "vl_base_calculo", tipo="decimal", obrigatorio=False),
        _c("aliquotas", "vl_aliquotas", tipo="decimal", obrigatorio=False),
        _c("taxa_juros", "tx_juros", tipo="decimal", obrigatorio=False),
        _c("envio", "dt_envio", tipo="data", obrigatorio=False),
        _c("situacao", "te_situacao", obrigatorio=False),
    ),

    "DRAA_PLANO_CUSTEIO": _IDENT + _PLANO_MASSA + (
        _c("tipo_contribuicao", "tp_contribuicao",
           nota="Segurados Ativos, Aposentados, Pensionistas, Ente Federativo, "
                "Ente Federativo - Total, Taxa de Administração, Aporte Anual"),
        _c("base_calculo", "vl_anual_base_calculo", tipo="decimal",
           obrigatorio=False),
        _c("aliquota", "vl_aliquota", tipo="decimal", obrigatorio=False),
        _c("contribuicao_esperada", "vl_contribuicao_esperada", tipo="decimal",
           obrigatorio=False),
        _c("aliquota_definida", "vl_aliquota_definida", tipo="decimal",
           obrigatorio=False),
        _c("contribuicao_definida", "vl_contribuicao_definida", tipo="decimal",
           obrigatorio=False),
    ),
}


# --------------------------------------------------------------------------
# Resolução
# --------------------------------------------------------------------------

def _normalizar(chave: str) -> str:
    """Reduz uma chave à sua forma comparável: sem acento, sem separador."""
    sem_acento = unicodedata.normalize("NFKD", chave)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def carregar_override(caminho: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """Lê ``fieldmap.local.json``, se existir. Ausência não é erro."""
    caminho = caminho or ARQUIVO_OVERRIDE
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class Resolucao:
    """O casamento entre campos lógicos e chaves reais de um endpoint."""

    endpoint: str
    encontrados: Dict[str, str]
    faltando_obrigatorios: List[str]
    faltando_opcionais: List[str]
    nao_mapeados: List[str]

    @property
    def completa(self) -> bool:
        return not self.faltando_obrigatorios

    def resumo(self) -> str:
        linhas = ["{}: {} campos resolvidos".format(self.endpoint, len(self.encontrados))]
        if self.faltando_obrigatorios:
            linhas.append("  obrigatórios ausentes: " + ", ".join(self.faltando_obrigatorios))
        if self.faltando_opcionais:
            linhas.append("  opcionais ausentes: " + ", ".join(self.faltando_opcionais))
        if self.nao_mapeados:
            mostra = self.nao_mapeados[:12]
            resto = len(self.nao_mapeados) - len(mostra)
            linhas.append("  chaves não mapeadas: " + ", ".join(mostra)
                          + (" (+{})".format(resto) if resto else ""))
        return "\n".join(linhas)


def resolver(endpoint: str, chaves: Iterable[str],
             override: Optional[Mapping[str, Mapping[str, str]]] = None) -> Resolucao:
    """Casa os campos declarados com as chaves observadas numa resposta.

    A busca é feita em três passadas, da mais estrita à mais tolerante: nome
    exato, depois sem diferenciar maiúsculas, depois ignorando acentos e
    separadores. Assim ``vlr_total_atual`` e ``VlrTotalAtual`` resolvem para o
    mesmo campo sem precisar de entrada nova no mapa.
    """
    chaves = list(chaves)
    por_exato = {k: k for k in chaves}
    por_minuscula = {k.lower(): k for k in chaves}
    por_normal = {_normalizar(k): k for k in chaves}

    override = (override if override is not None else carregar_override()).get(endpoint, {})
    campos = MAPA.get(endpoint, ())

    encontrados: Dict[str, str] = {}
    faltando_obr: List[str] = []
    faltando_opc: List[str] = []

    for campo in campos:
        forcado = override.get(campo.nome)
        candidatos = (forcado,) + campo.candidatos if forcado else campo.candidatos
        achado = None
        for cand in candidatos:
            achado = (por_exato.get(cand)
                      or por_minuscula.get(cand.lower())
                      or por_normal.get(_normalizar(cand)))
            if achado:
                break
        if achado:
            encontrados[campo.nome] = achado
        elif campo.obrigatorio:
            faltando_obr.append(campo.nome)
        else:
            faltando_opc.append(campo.nome)

    usadas = set(encontrados.values())
    nao_mapeados = [k for k in chaves if k not in usadas]
    return Resolucao(endpoint, encontrados, faltando_obr, faltando_opc, nao_mapeados)


def exigir(resolucao: Resolucao, chaves_observadas: Sequence[str]) -> Resolucao:
    """Levanta erro legível se faltar campo obrigatório."""
    if resolucao.completa:
        return resolucao
    raise CampoNaoEncontrado(
        "{}: não encontrei os campos obrigatórios {}.\n"
        "Chaves que a API devolveu: {}\n"
        "Corrija em fieldmap.local.json — veja `python -m cadprev inspect {}`."
        .format(resolucao.endpoint,
                ", ".join(resolucao.faltando_obrigatorios),
                ", ".join(sorted(chaves_observadas)),
                resolucao.endpoint)
    )


# --------------------------------------------------------------------------
# Conversão de tipos
# --------------------------------------------------------------------------

_VERDADEIRO = {"s", "sim", "true", "t", "1", "y", "yes"}
_FALSO = {"n", "nao", "não", "false", "f", "0", "no"}


def converter(valor: Any, tipo: str) -> Any:
    """Converte um valor cru da API para o tipo lógico do campo.

    A API pode devolver número como número ou como texto no formato brasileiro
    (``1.234,56``). Data pode vir ISO ou ``dd/mm/aaaa``. Os dois casos são
    tratados aqui para que o resto do código nunca precise saber disso.
    """
    if valor is None or valor == "":
        return None
    if tipo == "texto":
        return str(valor).strip()
    if tipo == "cnpj":
        return re.sub(r"\D", "", str(valor)).zfill(14)
    if tipo == "inteiro":
        if isinstance(valor, bool):
            return int(valor)
        if isinstance(valor, (int, float)):
            return int(valor)
        limpo = re.sub(r"[^\d-]", "", str(valor))
        return int(limpo) if limpo not in ("", "-") else None
    if tipo == "decimal":
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return float(valor)
        texto = str(valor).strip()
        if "," in texto:  # formato brasileiro: ponto é milhar
            texto = texto.replace(".", "").replace(",", ".")
        limpo = re.sub(r"[^\d.eE+-]", "", texto)
        try:
            return float(limpo)
        except ValueError:
            return None
    if tipo == "booleano":
        if isinstance(valor, bool):
            return valor
        t = _normalizar(str(valor))
        if t in _VERDADEIRO:
            return True
        if t in _FALSO:
            return False
        return None
    if tipo == "data":
        return _converter_data(valor)
    return valor


def _converter_data(valor: Any) -> Optional[str]:
    """Devolve a data em ISO (``aaaa-mm-dd``) ou ``None``."""
    if isinstance(valor, (date, datetime)):
        return valor.date().isoformat() if isinstance(valor, datetime) else valor.isoformat()
    texto = str(valor).strip()
    if not texto:
        return None
    if texto.isdigit() and len(texto) == 13:  # epoch em milissegundos
        return datetime.utcfromtimestamp(int(texto) / 1000).date().isoformat()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto[:len(formato) + 6], formato).date().isoformat()
        except ValueError:
            continue
    try:  # ISO com fuso
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def aplicar(resolucao: Resolucao, registro: Mapping[str, Any]) -> Dict[str, Any]:
    """Traduz um registro cru da API para os nomes e tipos do projeto."""
    tipos = {c.nome: c.tipo for c in MAPA.get(resolucao.endpoint, ())}
    saida: Dict[str, Any] = {}
    for logico, real in resolucao.encontrados.items():
        saida[logico] = converter(registro.get(real), tipos.get(logico, "texto"))
    for ausente in resolucao.faltando_opcionais:
        saida[ausente] = None
    return saida


def campos(endpoint: str) -> Tuple[Campo, ...]:
    return MAPA.get(endpoint, ())


def endpoints_mapeados() -> Tuple[str, ...]:
    return tuple(sorted(MAPA))
