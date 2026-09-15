"""Códigos de domínio do CADPREV, observados nas respostas da API.

Vários endpoints vêm em formato longo — uma linha por item, identificada por um
código ou uma sigla. Classificar esses itens é o que transforma a resposta crua
em número de painel, e o critério precisa ficar num lugar só, nomeado, em vez de
espalhado em condições soltas pelo código de agregação.

Evidência: ``docs/schema-observado/``, coletado em 15/09/2026.
"""

from typing import Optional

# ---------------------------------------------------------------------------
# DIPR — rubricas
# ---------------------------------------------------------------------------
#
# O DIPR devolve uma linha por rubrica, por mês e por plano. Não há campo de
# total: ingressos e dispêndios saem da soma das rubricas certas.
#
# As siglas seguem um padrão: o prefixo ``UT-`` marca utilização de recursos
# (o bloco 11 do demonstrativo). Tudo o mais é entrada — contribuições
# (SEG, PAT-*, APO, PEN, UG-*, MIL-*), ingressos financeiros (ING-*), aportes
# (APORTE-*), transferências (TRANSF-*) e parcelamentos (PARC).

PREFIXO_DISPENDIO = "UT-"

#: Primeiro ``id_rubrica`` que representa valor efetivamente movimentado.
#:
#: O DIPR repete as mesmas siglas em dois blocos. Os ids até 32 são o bloco 1 —
#: as **bases de cálculo**, isto é, as folhas sobre as quais as contribuições
#: incidem. De 33 em diante vêm as contribuições de fato repassadas, e a partir
#: de 70 os ingressos, aportes, transferências e a utilização de recursos.
#:
#: A distinção não está no nome: ``PAT-SEG`` aparece com id 19 e com id 56, com
#: a mesma descrição. Está no valor. No bloco 1, a linha patronal e a linha do
#: servidor trazem número idêntico, porque são a mesma folha; no bloco 2 elas
#: divergem, porque as alíquotas são diferentes. Somar o bloco 1 como receita
#: multiplica o caixa do RPPS por várias vezes.
CODIGO_MINIMO_VALOR_EFETIVO = 33


def rubrica_e_base_de_calculo(codigo: Optional[int]) -> bool:
    """Se a linha é base de cálculo, e não dinheiro movimentado.

    >>> rubrica_e_base_de_calculo(19)   # PAT-SEG do bloco 1
    True
    >>> rubrica_e_base_de_calculo(56)   # PAT-SEG do bloco 2
    False
    >>> rubrica_e_base_de_calculo(None)
    False
    """
    return codigo is not None and int(codigo) < CODIGO_MINIMO_VALOR_EFETIVO


def rubrica_e_dispendio(rubrica: Optional[str]) -> bool:
    """Se a rubrica é saída de recursos.

    >>> rubrica_e_dispendio("UT-APO")
    True
    >>> rubrica_e_dispendio("PAT-SEG")
    False
    >>> rubrica_e_dispendio("ING-REND-APL")
    False
    >>> rubrica_e_dispendio(None)
    False
    """
    return bool(rubrica) and str(rubrica).strip().upper().startswith(PREFIXO_DISPENDIO)


#: Rubricas de dispêndio agrupadas para a leitura de "para onde vai".
GRUPOS_DISPENDIO = {
    "UT-APO": "Aposentadorias",
    "UT-PEN": "Pensões por morte",
    "UT-MIL-RES-REF": "Reserva e reforma de militares",
    "UT-APO-TES": "Aposentadorias do Tesouro",
    "UT-PEN-TES": "Pensões do Tesouro",
    "UT-DESP-ADM": "Despesas administrativas",
    "UT-DESP-INV": "Despesas com investimentos",
    "UT-DEC-JUD": "Decisões judiciais",
    "UT-COMP-FIN": "Compensação previdenciária paga",
    "UT-SAL-FAM": "Salário-família",
    "UT-OUT-DESP": "Outras despesas",
}

#: Rubricas de ingresso agrupadas para a leitura de "de onde vem".
GRUPOS_INGRESSO = {
    "ING-REND-APL": "Rendimentos de aplicações",
    "ING-REND-ATIVOS": "Rendimentos de demais ativos",
    "ING-COMP-FIN": "Compensação previdenciária recebida",
    "ING-CED-LIC": "Contribuições de cedidos e licenciados",
    "ING-OUT-REC": "Outras receitas",
    "PARC": "Parcelamentos",
    "APORTE-DEF": "Aporte para amortização do déficit",
    "APORTE-DEF-UG": "Aporte para amortização do déficit (UG)",
    "TRANSF-INS": "Cobertura de insuficiência financeira",
    "TRANSF-ADM": "Transferência para despesas administrativas",
    "TRANSF-TES": "Transferência para benefícios do Tesouro",
    "MIL-TRANSF-INS": "Cobertura de insuficiência (militares)",
}


def grupo_da_rubrica(rubrica: Optional[str]) -> str:
    """Nome legível do grupo de uma rubrica.

    Contribuições não têm entrada nos dicionários acima porque são muitas
    variantes da mesma coisa — patronal, segurado, 13º, unidade gestora — e
    somá-las numa linha só é o que a leitura pede.

    >>> grupo_da_rubrica("UT-APO")
    'Aposentadorias'
    >>> grupo_da_rubrica("13-PAT-SEG")
    'Contribuições'
    """
    if not rubrica:
        return "Não identificado"
    chave = str(rubrica).strip().upper()
    if chave in GRUPOS_DISPENDIO:
        return GRUPOS_DISPENDIO[chave]
    if chave in GRUPOS_INGRESSO:
        return GRUPOS_INGRESSO[chave]
    if rubrica_e_dispendio(chave):
        return "Outras despesas"
    return "Contribuições"


# ---------------------------------------------------------------------------
# DRAA_FLUXO_ATUARIAL — códigos de fluxo
# ---------------------------------------------------------------------------
#
# Atenção: este endpoint **não é série temporal**. Cada linha é um item do
# fluxo com um único valor projetado. A projeção ano a ano, que o anteprojeto
# do painel previa, existe nos arquivos de dados abertos da SPREV e não aqui.

FLUXO_TOTAL_RECEITAS = 190000
FLUXO_TOTAL_DESPESAS = 240000
FLUXO_RESULTADO_FINANCEIRO = 250001
FLUXO_RENTABILIDADE_ESPERADA = 270001

#: Primeira receita de fato. O código 109001 é "Base de Cálculo da Contribuição
#: Normal" — a folha sobre a qual a contribuição incide, não dinheiro a receber.
#: É o mesmo engano do bloco 1 do DIPR, na outra ponta do demonstrativo.
FLUXO_PRIMEIRA_RECEITA = 110000
FLUXO_BASE_CALCULO = 109001


def fluxo_e_receita(codigo: Optional[int]) -> bool:
    """Se o código é de receita projetada.

    >>> fluxo_e_receita(121000)
    True
    >>> fluxo_e_receita(109001)   # base de cálculo, não receita
    False
    >>> fluxo_e_receita(211001)
    False
    """
    return bool(codigo) and FLUXO_PRIMEIRA_RECEITA <= int(codigo) < 190000


def fluxo_e_despesa(codigo: Optional[int]) -> bool:
    """Se o código é de despesa.

    >>> fluxo_e_despesa(211001)
    True
    >>> fluxo_e_despesa(121000)
    False
    """
    return bool(codigo) and 200000 <= int(codigo) < FLUXO_TOTAL_DESPESAS


# ---------------------------------------------------------------------------
# DRAA_VALORES_COMPROMISSOS — códigos do demonstrativo
# ---------------------------------------------------------------------------

COMPROMISSO_DEFICIT = 600100
COMPROMISSO_EQUILIBRIO = 600200
COMPROMISSO_SUPERAVIT = 600300
COMPROMISSO_PROVISAO_CONCEDIDOS = 300000
COMPROMISSO_PROVISAO_A_CONCEDER = 400000
COMPROMISSO_ATIVOS_GARANTIDORES = 500000
COMPROMISSO_RECEITAS_ESTIMADAS = 900100
COMPROMISSO_DESPESAS_ESTIMADAS = 900200

CATEGORIA_TITULO = "titulo"

#: Itens que o painel destaca, na ordem em que aparecem na tela.
COMPROMISSOS_DESTAQUE = (
    (COMPROMISSO_DEFICIT, "Déficit atuarial"),
    (COMPROMISSO_SUPERAVIT, "Superávit atuarial"),
    (COMPROMISSO_ATIVOS_GARANTIDORES, "Ativos garantidores"),
    (COMPROMISSO_RECEITAS_ESTIMADAS, "Receitas estimadas no exercício"),
    (COMPROMISSO_DESPESAS_ESTIMADAS, "Despesas estimadas no exercício"),
)


# ---------------------------------------------------------------------------
# DRAA_HIPOTESE_ATUARIAL — as hipóteses que o painel mostra
# ---------------------------------------------------------------------------
#
# São mais de vinte por RPPS. A tela mostra as que mudam a leitura do
# resultado atuarial; o resto fica na fonte.

HIPOTESES_DESTAQUE = (
    "Projeção da Taxa de Juros Real para o Exercício",
    "Projeção da Taxa de Inflação de Longo Prazo",
    "Projeção de Crescimento Real do Salário",
    "Projeção de Crescimento Real dos Benefícios do Plano",
    "Projeção da Taxa de Rotatividade",
    "Composição Familiar - Servidores em atividade",
)


# ---------------------------------------------------------------------------
# DRAA_PLANO_CUSTEIO — tipos de contribuição
# ---------------------------------------------------------------------------

CUSTEIO_ENTE_TOTAL = "Ente Federativo - Total"
CUSTEIO_TAXA_ADMINISTRACAO = "Taxa de Administração"
CUSTEIO_APORTE = "Aporte Anual para Custeio das Despesas"

#: Ordem de exibição na ficha.
CUSTEIO_ORDEM = (
    "Segurados Ativos", "Aposentados", "Pensionistas",
    "Ente Federativo", CUSTEIO_ENTE_TOTAL, CUSTEIO_TAXA_ADMINISTRACAO,
    CUSTEIO_APORTE,
)
