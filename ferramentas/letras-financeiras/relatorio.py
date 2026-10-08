# -*- coding: utf-8 -*-
"""O conteúdo das abas que vão para a SPREV.

Texto, não cálculo: os números abaixo saem das abas de dados e estão aqui
transcritos para quem lê o resumo sem abrir o resto. Quando a ferramenta rodar
noutra competência, estes textos precisam ser revistos — por isso cada bloco
nomeia a competência de que fala.
"""

COMPETENCIA_CDA = "maio/2024"
COMPETENCIA_DAIR = "2026-06"

ABERTURA = [
    ("O que é este documento", (
        "Estudo preliminar, feito com dados públicos, sobre Letras Financeiras "
        "e a exposição dos RPPS a elas. NENHUM ACHADO AQUI REPRESENTA, POR SI, "
        "IRREGULARIDADE. São medidas objetivas que podem justificar — ou "
        "dispensar — um pedido de auditoria mais detalhada.")),
    ("Quem fez e com o quê", (
        "Dados abertos da CVM (CDA — Composição e Diversificação das Aplicações, "
        "competências 2024-04 e 2024-05; registro de fundos e classes) e o painel "
        "público do CADPREV, que agrega o DAIR de cada RPPS. Nada aqui usa dado "
        "restrito, e todo número é reproduzível a partir das fontes citadas.")),
    ("A ressalva de datas, que vale para tudo", (
        "As Letras Financeiras são da CDA de maio/2024. As carteiras dos RPPS "
        "são do último DAIR de cada um, competência 2026-06 — a API do CADPREV "
        "está indisponível desde 22/09/2026 e essa é a safra mais recente "
        "disponível. São dois anos de distância: o estudo mede por qual fundo um "
        "RPPS alcança uma LF, não que ele a tenha comprado naquele mês.")),
]

NUMEROS = [
    ("Letras Financeiras na CDA de maio/2024", "43.949 posições · R$ 457,3 bi"),
    ("Fundos que as detinham", "2.997"),
    ("Emissores distintos (por CNPJ)", "102"),
    ("Aquisições declaradas pelos fundos no mês", "499 linhas · R$ 4,32 bi"),
    ("", ""),
    ("Exposição dos RPPS a LF (look-through)", "R$ 17,5 bi"),
    ("RPPS alcançados", "1.509"),
    ("LF distintas que algum RPPS alcança", "2.669"),
    ("  por compra direta do RPPS", "84 papéis · R$ 1,37 bi"),
    ("  por um ou dois fundos", "2.585 papéis · R$ 16,17 bi"),
    ("", ""),
    ("RPPS que declararam LF direto", "43"),
    ("Declarações diretas", "95"),
]

NAO_DA = [
    ("A taxa da compra não está no DAIR", (
        "O DAIR_CARTEIRA tem dezesseis campos e nenhum é remuneração: nome do "
        "ativo em texto livre, quantidade, valor unitário de hoje, valor total, "
        "patrimônio, percentuais e o teto da classe. Não há taxa contratada, "
        "data de aquisição, data de emissão nem CNPJ do emissor. Sem isso não "
        "existe comparação de preço possível a partir da posição declarada.")),
    ("A CDA tem taxa, mas não identifica o papel", (
        "A CDA publica indexador, percentual do índice e cupom de cada LF, mas "
        "não publica ISIN nem código do papel, e não distingue sênior de "
        "subordinada. O agrupamento mais fino possível é emissor × vencimento. "
        "Nos 1.056 grupos com oito ou mais observações, em 316 (30%) o maior "
        "cupom é o dobro do menor e em 67 (6%) é cinco vezes. Bradesco com "
        "vencimento em 17/09/2027 tem 234 observações entre 0,41% e 1,40% sobre "
        "o DI; BTG em 17/11/2031 vai de 2,30% a 13,54%. A data 2050-12-31 "
        "aparece 637 vezes, marcando papel perpétuo. São papéis diferentes sob o "
        "mesmo rótulo: apontar \"fora da média\" nessa base produziria acusação "
        "a partir de ruído, e o alvo seriam municípios nomeados.")),
    ("Por que o viés é perverso", (
        "LF subordinada paga legitimamente muito mais que sênior. Como a fonte "
        "não as separa, qualquer teste de \"taxa alta demais\" se encheria de "
        "falsos positivos legítimos. O lado \"taxa baixa demais\" — que é o que "
        "interessaria a uma denúncia de prejuízo — fica sem referência confiável "
        "pelo mesmo motivo.")),
]

NEGATIVOS = [
    ("Nenhum RPPS acima do teto da classe", (
        "Dos 43 RPPS com LF direta, nenhum excede o limite de 20% para \"Ativos "
        "Renda Fixa com obrigação de IF — Art. 7º VI\". O teto vem declarado no "
        "próprio registro de cada classe, não de interpretação externa.")),
    ("Nenhum veículo sob medida concentrado num emissor", (
        "A hipótese de um fundo criado para colocar o papel de um emissor "
        "específico em RPPS foi testada: fundos com até 60 RPPS, 20% ou mais do "
        "patrimônio em mãos de RPPS e 10% ou mais em LF. São sete, e todos "
        "diversificados — de 9 a 22 emissores, com o maior entre 10% e 40% da "
        "LF do fundo. Nenhum concentrado num emissor só.")),
    ("Os emissores identificáveis são instituições grandes", (
        "Onde a declaração nomeia o banco, são BTG (R$ 352 mi), Caixa (R$ 249 "
        "mi), Bradesco (R$ 161 mi), Daycoval, Santander, Safra, Itaú, XP e "
        "Votorantim. Nenhuma instituição pequena ou em dificuldade aparece entre "
        "as compras diretas identificáveis.")),
]

ATENCAO = [
    ("R$ 235 milhões sem emissor identificado", (
        "44 das 95 declarações diretas, em 21 RPPS, não dizem de que banco é o "
        "papel — e o DAIR não tem campo de CNPJ do emissor. Exemplos reais: "
        "\"LF\", \"Letra Financeira - 14/08/2025\", \"quisiçao LF SENIOR 10 "
        "anos\". Este é o principal obstáculo a qualquer verificação, e é "
        "cadastral, não analítico: não se confere o que não se identifica.")),
    ("Seis declarações truncadas no meio da palavra", (
        "Em 3 RPPS, o nome do ativo começa no meio: \"nvest em Letra Financeira "
        "da CEF IPCA + 6 31%\", \"tivos Finan Emit por Inst Finan LF 2034\", "
        "\"etra Financeira LF-002500OL1\". Sugere limite de caracteres cortando "
        "o início do campo, ou colagem malfeita — e indica que o campo não tem "
        "validação.")),
    ("Dez papéis com 5% ou mais da carteira de um RPPS", (
        "Em 9 RPPS. Os maiores: São José dos Pinhais/PR com 11,4% da carteira "
        "num único papel, Taió/SC com 8,5%, Campos dos Goytacazes/RJ com 7,9%. "
        "A norma limita a classe, não o papel individual — então isto é "
        "concentração a observar, não infração.")),
    ("Três fundos concentram 56,5% da exposição indireta", (
        "A exposição indireta de R$ 16,17 bi passa por 106 veículos, mas três "
        "deles respondem por 56,5% e dez por 87,3% — fundos de Caixa, Bradesco, "
        "Banco do Brasil, Itaú e Santander. É risco de concentração de "
        "intermediário, e explica por que certos papéis aparecem com maioria "
        "em mãos de RPPS: não é direcionamento, é que quase mil RPPS passam "
        "pelos mesmos poucos fundos.")),
]

CONCLUSAO = (
    "A denúncia que motivou este estudo — RPPS influenciados a comprar LF que "
    "geraram prejuízo — não pode ser confirmada nem afastada com os dados "
    "públicos de hoje, e a razão é de coleta, não de análise. Falta ao DAIR o "
    "que identificaria o papel e o preço pago. As abas seguintes propõem os "
    "campos que destravariam a verificação e listam os casos que, pelos "
    "critérios objetivos disponíveis, justificariam um olhar detalhado.")


#: Campos sugeridos. A coluna "já existe em" é o argumento: quase tudo que
#: falta ao DAIR a CVM já exige dos fundos na CDA há anos, com nome de campo e
#: tudo. Não se está pedindo que a SPREV invente coisa nova — se está pedindo
#: paridade com o que o outro regulador já coleta sobre o mesmo ativo.
MELHORIAS = [
    ("1", "CNPJ do emissor", "DAIR_CARTEIRA e APR",
     "CDA, bloco 5: CNPJ_EMISSOR",
     "O campo que falta e trava tudo o mais. Hoje o emissor só existe como "
     "texto livre, e em 44 das 95 declarações de LF o texto não o nomeia. Com o "
     "CNPJ: confronto com os limites por emissor, cruzamento com a lista de "
     "regimes especiais do Banco Central, e casamento direto com a carteira dos "
     "fundos publicada pela CVM.",
     "Alta"),
    ("2", "Código do ativo e ISIN", "DAIR_CARTEIRA e APR",
     "CDA, bloco 4: CD_ATIVO, CD_ISIN (a CVM não os publica no bloco 5)",
     "Identifica o papel, não só o emissor. Sem isso, duas LF do mesmo banco "
     "com o mesmo vencimento são indistinguíveis, e foi exatamente o que "
     "impediu a comparação de taxa neste estudo. Com o ISIN, o mesmo papel pode "
     "ser comparado entre RPPS, contra fundos e contra as taxas da ANBIMA.",
     "Alta"),
    ("3", "Remuneração contratada, em quatro campos",
     "DAIR_CARTEIRA e APR",
     "CDA, bloco 5: CD_INDEXADOR_POSFX, PR_INDEXADOR_POSFX, PR_CUPOM_POSFX, "
     "PR_TAXA_PREFX",
     "Indexador, percentual do indexador, cupom e taxa prefixada — quatro "
     "campos, exatamente como a CVM já coleta dos fundos. É o que permite "
     "perguntar se o RPPS recebeu o que o mercado pagava. Um campo único de "
     "\"taxa\" não serve: \"100% do DI\" e \"DI + 1,15%\" são remunerações "
     "diferentes e caberiam no mesmo campo.",
     "Alta"),
    ("4", "Data de aquisição e preço unitário pago", "APR",
     "CDA, bloco 5: VL_AQUIS_NEGOC, QT_AQUIS_NEGOC (valor, não preço unitário)",
     "A APR já registra operação a operação; faltam a data exata e o preço "
     "unitário da operação. Com eles, a taxa pode ser comparada contra o "
     "mercado na data da compra, que é a única comparação válida — hoje, "
     "mesmo que houvesse taxa, não se saberia contra que dia compará-la.",
     "Alta"),
    ("5", "Espécie do papel: sênior, subordinada, complementar",
     "DAIR_CARTEIRA e APR",
     "Nenhuma fonte pública separa — nem a CVM",
     "LF subordinada paga legitimamente muito mais que sênior. Sem esse campo, "
     "qualquer teste estatístico de taxa mistura as duas e produz falso "
     "positivo. Foi a segunda causa de o teste de preço não ser possível aqui. "
     "A ANBIMA já divulga taxas separadas por classe (LF, LFSN5-, LFSN5+, "
     "LFSC), então a segmentação existe no mercado — falta na coleta.",
     "Alta"),
    ("6", "Contraparte e intermediário da operação", "APR",
     "Não existe em fonte pública",
     "Quem vendeu o papel ao RPPS, e por meio de quem. É O CAMPO QUE DETECTA "
     "DIRECIONAMENTO: um mesmo distribuidor aparecendo em muitos RPPS que "
     "compraram o mesmo papel em condições piores que o mercado é um padrão "
     "que nenhum outro dado revela. Nada neste estudo pôde testar essa hipótese "
     "por falta deste campo.",
     "Alta"),
    ("7", "Mercado da operação: primário ou secundário", "APR",
     "Não existe em fonte pública",
     "Subscrever uma emissão e comprar de um terceiro no secundário são atos "
     "diferentes, com riscos e preços diferentes. Separá-los muda a leitura de "
     "qualquer desvio de taxa.",
     "Média"),
    ("8", "Data de emissão e data de vencimento em campo próprio",
     "DAIR_CARTEIRA",
     "CDA, bloco 5: DT_VENC",
     "Hoje o vencimento, quando aparece, vem dentro do texto livre do nome "
     "(\"Letra Financeira - 14/08/2025\"). Em campo próprio, permite medir prazo "
     "e montar curva por emissor.",
     "Média"),
    ("9", "Valor de aquisição ao lado do valor de mercado",
     "DAIR_CARTEIRA",
     "CDA, bloco 5: VL_CUSTO_POS_FINAL (a CVM coleta, mas vem vazio nas LF)",
     "Com custo e mercado lado a lado, o resultado acumulado do papel fica "
     "visível na própria posição — que é a pergunta direta de uma denúncia de "
     "prejuízo. Observação: na CDA este campo existe e vem vazio em 100% das "
     "linhas de LF, o que sugere que coletar não basta: é preciso validar.",
     "Alta"),
    ("10", "Rating e agência, com data", "DAIR_CARTEIRA",
     "CDA, bloco 5: AG_RISCO, GRAU_RISCO, DT_RISCO (preenchidos em 4,2%)",
     "Permite separar o que é prêmio por risco do que é preço ruim. O exemplo "
     "da CDA mostra o cuidado necessário: o campo existe e só 4,2% das linhas o "
     "trazem — campo opcional é campo vazio.",
     "Média"),
    ("11", "Validação de preenchimento do nome do ativo",
     "DAIR_CARTEIRA (sistema CADPREV)",
     "—",
     "Seis declarações começam no meio da palavra — \"nvest em Letra "
     "Financeira\", \"quisiçao LF SENIOR\", \"tivos Finan Emit por Inst\". "
     "Sugere limite de caracteres cortando o início. Com os campos estruturados "
     "acima, o nome livre deixa de ser a única identificação e o problema perde "
     "gravidade; enquanto isso, uma validação simples já evitaria o pior.",
     "Média"),
    ("12", "Publicar a APR na API, com os campos acima",
     "API do CADPREV",
     "—",
     "A APR alimenta o DAIR no CADPREV e registra operação a operação, mas não "
     "é explorável hoje. Publicada com emissor, ISIN, taxa, preço, data, "
     "contraparte e mercado, ela permitiria auditoria no nível da operação — "
     "que é onde uma irregularidade de preço efetivamente acontece. Nenhum dos "
     "outros campos, sozinho, substitui isto.",
     "Alta"),
]

NOTA_MELHORIAS = (
    "A coluna \"já existe em\" é o ponto central desta aba: sete dos doze itens "
    "têm campo equivalente já coletado pela CVM dos fundos de investimento, com "
    "nome definido, sobre o mesmo ativo — os itens 1, 2, 3, 4, 8, 9 e 10. Não se "
    "trata de criar exigência nova, e sim de alinhar a coleta do DAIR ao que "
    "outro regulador já pratica. Os cinco restantes — espécie do papel, "
    "contraparte, mercado da operação, validação de preenchimento e a publicação "
    "da APR — não existem em fonte pública nenhuma, e três deles (contraparte, "
    "mercado e a APR publicada) são justamente os que decidiriam uma apuração de "
    "direcionamento.")


#: Acima disto, um único papel pesa o bastante para justificar conferência.
#: Não é limite normativo — a norma limita a classe, não o papel.
PAPEL_CONCENTRADO = 5.0
#: Abaixo disto, o valor não identificado não compensa abrir verificação.
VALOR_QUE_IMPORTA = 5_000_000.0


def casos(linhas_da_triagem):
    """Os casos que justificariam olhar de perto, a partir da triagem.

    Calculado, não escrito à mão: roda noutra competência e a lista se refaz.
    Cada caso diz o que chama atenção, com o número que sustenta, e o que se
    verificaria — nunca o que teria acontecido.
    """
    casos_ = []

    for l in linhas_da_triagem:
        perc = l.get("perc_da_carteira") or 0.0
        valor = l.get("valor") or 0.0
        nome = l.get("declarado_no_dair") or ""
        sem_emissor = "não nomeia" in (l.get("o_que_olhar") or "")
        truncada = "truncada" in (l.get("o_que_olhar") or "")

        if perc >= PAPEL_CONCENTRADO and sem_emissor:
            casos_.append((1, "Concentração + emissor não identificado", l, (
                "%.1f%% da carteira num único papel, e a declaração não diz de "
                "que banco é: \"%s\"." % (perc, nome)), (
                "Pedir ao RPPS o CNPJ do emissor, o ISIN e o boletim da "
                "operação. Sem o emissor, nem o limite por emissor pode ser "
                "conferido.")))
        elif perc >= PAPEL_CONCENTRADO:
            casos_.append((2, "Concentração num único papel", l, (
                "%.1f%% da carteira num único papel (%s)." % (perc, nome)), (
                "Confirmar o enquadramento no limite por emissor e a decisão "
                "do comitê de investimentos que autorizou a posição.")))
        elif sem_emissor and valor >= VALOR_QUE_IMPORTA:
            casos_.append((3, "Valor relevante sem emissor identificado", l, (
                "R$ %s declarados como \"%s\", sem identificação do emissor."
                % ("{:,.2f}".format(valor).replace(",", "X").replace(".", ",")
                   .replace("X", "."), nome)), (
                "Pedir o CNPJ do emissor e o ISIN. É o mínimo para que "
                "qualquer confronto de preço se torne possível.")))
        elif truncada:
            casos_.append((4, "Declaração truncada", l, (
                "O nome do ativo começa no meio da palavra: \"%s\"." % nome), (
                "Verificar se o campo foi cortado no preenchimento e obter a "
                "descrição completa do papel.")))

    casos_.sort(key=lambda c: (c[0], -(c[1 + 1].get("perc_da_carteira") or 0)))
    saida = []
    for ordem, tipo, l, porque, verificar in casos_:
        saida.append({
            "prioridade": {1: "Alta", 2: "Média", 3: "Média", 4: "Baixa"}[ordem],
            "tipo": tipo,
            "rpps": l["rpps"],
            "rpps_cnpj": l["rpps_cnpj"],
            "declarado_no_dair": l["declarado_no_dair"],
            "valor": l["valor"],
            "perc_da_carteira": l.get("perc_da_carteira"),
            "perc_em_lf_direta": l.get("perc_em_lf_direta"),
            "teto_da_classe": l.get("teto_da_classe"),
            "excede_o_teto": l.get("excede_o_teto"),
            "o_que_chama_atencao": porque,
            "o_que_verificar": verificar,
            "competencia": l.get("competencia", ""),
        })
    return saida


NOTA_CASOS = (
    "Esta lista não afirma irregularidade. Cada linha diz o que, nos dados "
    "públicos, destoa — e o que se pediria para esclarecer. A maioria dos casos "
    "provavelmente tem explicação simples; o objetivo é separar o que merece "
    "uma pergunta do que não merece. Nenhum dos RPPS listados excede o teto da "
    "classe, e a concentração num papel individual não é vedada pela norma: é "
    "sinal de atenção, não de infração.")
