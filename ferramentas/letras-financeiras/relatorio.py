# -*- coding: utf-8 -*-
"""O conteúdo das abas de leitura do levantamento.

Texto, não cálculo: os números abaixo saem das abas de dados e estão aqui
transcritos para quem lê o resumo sem abrir o resto. Quando a ferramenta rodar
noutra competência, estes textos precisam ser revistos — por isso cada bloco
nomeia a competência de que fala.
"""

COMPETENCIA_CDA = "maio/2024"
COMPETENCIA_DAIR = "2026-06"

ABERTURA = [
    ("O que é este documento", (
        "Levantamento informal sobre Letras Financeiras e a exposição dos RPPS "
        "a elas, feito com dados públicos. NENHUM ACHADO AQUI REPRESENTA, POR "
        "SI, IRREGULARIDADE. São medidas objetivas, reproduzíveis, que servem "
        "para separar o que merece uma pergunta do que não merece.")),
    ("De onde vêm os números", (
        "Dados abertos da CVM (CDA — Composição e Diversificação das Aplicações, "
        "competências 2024-04 e 2024-05; registro de fundos e classes) e o painel "
        "público do CADPREV, que agrega o DAIR de cada RPPS. Nada aqui usa dado "
        "restrito, e todo número é reproduzível a partir das fontes citadas.")),
    ("A ressalva de datas, que vale para tudo", (
        "As Letras Financeiras são da CDA de maio/2024. As carteiras dos RPPS "
        "são do último DAIR de cada um, competência 2026-06 — a API do CADPREV "
        "está indisponível desde 22/09/2026 e essa é a safra mais recente "
        "disponível. São dois anos de distância: o levantamento mede por qual "
        "fundo um RPPS alcança uma LF, não que ele a tenha comprado naquele "
        "mês.")),
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
        "falsos positivos legítimos. E o lado \"taxa baixa demais\" — que é o "
        "que interessaria a quem procura prejuízo na carteira — fica sem "
        "referência confiável pelo mesmo motivo.")),
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
        "papel. O DAIR_CARTEIRA não tem campo de emissor — e a APR tem, "
        "escolhido de uma lista de instituições credenciadas, só que não chega "
        "ao dado aberto. Exemplos reais: "
        "\"LF\", \"Letra Financeira - 14/08/2025\", \"quisiçao LF SENIOR 10 "
        "anos\". Este é o principal obstáculo a qualquer verificação feita de "
        "fora, e é de publicação, não de método: o dado existe no sistema. "
        "Quem tem acesso ao CADPREV identifica o emissor de cada uma dessas "
        "operações hoje.")),
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
    "A pergunta que puxou este levantamento — alguma LF foi comprada a preço ou "
    "taxa fora do mercado? — não pode ser respondida com os dados públicos "
    "disponíveis hoje, e a razão é de publicação, não de análise. O CADPREV já "
    "coleta, na tela da APR, quase tudo que faria falta: emissora, "
    "intermediária, custodiante, taxa de juros de emissão, indexador e "
    "percentual, datas de emissão, operação e liquidação, rating e agência, e "
    "até uma descrição do processo de investimento desde a distribuição "
    "inicial. Nada disso chega ao dado aberto. A aba \"Dados da APR\" compara "
    "o que a tela pede com o que a análise alcança.")


#: O que a tela de cadastro da APR pede, e o que chega ao dado aberto.
#:
#: A lista anterior partia de premissa errada — supunha que a SPREV não
#: coletava. Coleta: a tela de Aplicações e Resgates do CADPREV tem 49 campos,
#: entre eles emissora, intermediária e custodiante, taxa de juros de emissão,
#: indexador e percentual, três datas, rating com agência, e quatro blocos de
#: texto de 2.000 caracteres sobre o processo de investimento e o parecer dos
#: colegiados. A recomendação muda de "coletar" para "publicar".
#:
#: Ressalva de método: não foi possível inspecionar o endpoint
#: DAIR_APLICACOES_RESGATE — a API está fora do ar desde 22/09/2026 e o projeto
#: nunca o ingeriu. A coluna "chega ao dado aberto?" afirma com segurança só
#: sobre o DAIR_CARTEIRA, cujos dezesseis campos foram observados em resposta
#: real. Para a APR ela diz "não verificável", que é o que se sabe.
MELHORIAS = [
    ("1", "Instituição Emissora", "Instituições",
     "Sim, com credenciamento e validade", "Não verificável",
     "O que falta a toda análise de posição: o DAIR_CARTEIRA não tem emissor, e "
     "em 44 das 95 declarações de LF o texto livre do nome não o nomeia. Na APR "
     "o emissor sai de uma lista de instituições credenciadas — é entidade, não "
     "texto. Publicado com CNPJ, destrava limite por emissor, cruzamento com os "
     "regimes especiais do Banco Central e casamento com a carteira dos fundos "
     "publicada pela CVM.", "Alta"),
    ("2", "Instituição Intermediária", "Instituições",
     "Sim, com credenciamento e validade", "Não verificável",
     "QUEM COLOCOU O PAPEL NO RPPS. Permitiria ver se um mesmo intermediário se "
     "repete em muitos RPPS que compraram o mesmo ativo em condições parecidas. "
     "Nenhuma fonte pública tem isso, e nada neste levantamento pôde olhar "
     "nessa direção. É o item de maior valor da lista.", "Alta"),
    ("3", "Instituição Custodiante", "Instituições",
     "Sim, com credenciamento e validade", "Não verificável",
     "Fecha o trio da operação e permite conferir se a custódia é de "
     "instituição credenciada e com credenciamento vigente na data — a tela já "
     "guarda a validade ao lado de cada uma.", "Média"),
    ("4", "Taxa de Juros de Emissão, Indexador e Perc. do Indexador",
     "Detalhes da Operação", "Sim, três campos separados", "Não verificável",
     "A remuneração contratada, que é exatamente o que falta para comparar uma "
     "compra com o mercado. A tela já separa os três — a mesma estrutura que a "
     "CVM usa nos fundos. Publicados, tornam possível a comparação que este "
     "levantamento não pôde fazer.", "Alta"),
    ("5", "Código de Registro", "Identificação do Ativo",
     "Sim", "Não verificável",
     "Identifica o papel, não só o emissor. Sem ele, duas LF do mesmo banco com "
     "o mesmo vencimento são indistinguíveis — foi essa indistinção que "
     "inviabilizou a comparação de taxa aqui.", "Alta"),
    ("6", "Data da Operação, da Liquidação e da Emissão",
     "Detalhes da Operação", "Sim, as três", "Não verificável",
     "Permite comparar a taxa contratada com o mercado NA DATA DA COMPRA, que é "
     "a única comparação válida. Hoje, mesmo que houvesse taxa na posição, não "
     "se saberia contra que dia compará-la.", "Alta"),
    ("7", "Valor da Operação, Quantidade, Quantidade antes e após",
     "Dados da operação", "Sim", "Não verificável",
     "Preço unitário sai da divisão. As quantidades antes e depois permitem "
     "reconstruir a posição operação a operação e conferi-la contra a carteira "
     "declarada — uma checagem de consistência que hoje não existe.", "Alta"),
    ("8", "Nota de Classificação de Risco e Agência",
     "Detalhes da Operação", "Sim, obrigatório, com lista de agências",
     "Não verificável",
     "Separa prêmio por risco de preço ruim. O contraste vale ser dito: na CDA "
     "da CVM o campo equivalente existe e só 4,2% das linhas o trazem; aqui a "
     "tela o marca como obrigatório. É dado de qualidade melhor que o do outro "
     "regulador, e mesmo assim não sai.", "Média"),
    ("9", "\"Descreva como foi o processo de investimento do ativo desde a "
     "distribuição inicial até a aplicação dos recursos\"",
     "Dados da Operação", "Sim, texto de até 2.000 caracteres",
     "Não verificável",
     "A PERGUNTA CERTA JÁ É FEITA. O campo descreve o caminho pelo qual o papel "
     "chegou ao RPPS. Texto livre não cabe em dado aberto como está, mas cabe "
     "em triagem interna — e é onde um padrão de colocação apareceria antes de "
     "qualquer estatística. Para quem trabalha dentro do CADPREV, está "
     "disponível hoje, sem depender de mudança nenhuma.", "Alta"),
    ("10", "Análise/Parecer do Conselho Deliberativo e Comitê de Investimentos",
     "Dados da Operação", "Sim, texto de até 2.000 caracteres",
     "Não verificável",
     "Permite ver se a operação foi ao colegiado e o que ele disse. Com as "
     "assinaturas ao lado — representante legal, proponente e liquidante, cada "
     "uma com data —, dá a cadeia de decisão da operação. Também coletado, "
     "também não publicado.", "Média"),
    ("11", "Espécie da LF: sênior, subordinada ou complementar",
     "Subtipo de Ativo", "NÃO — a tela só tem \"LF - Letra Financeira\"",
     "Não existe",
     "LACUNA REAL, de cadastro e não de publicação. LF subordinada paga "
     "legitimamente muito mais que sênior, e nenhuma fonte as separa — nem a "
     "CVM. Foi uma das duas causas de o teste de taxa não ser possível. A "
     "ANBIMA já divulga taxas por classe (LF, LFSN5-, LFSN5+, LFSC): a "
     "segmentação existe no mercado e falta no cadastro.", "Alta"),
    ("12", "Mercado da operação: primário ou secundário",
     "Detalhes da Operação",
     "NÃO — há intermediária e sistema de registro, não o tipo de mercado",
     "Não existe",
     "LACUNA REAL. Subscrever uma emissão e comprar de terceiro no secundário "
     "são atos diferentes, com preços e riscos diferentes. Separá-los muda a "
     "leitura de qualquer desvio de taxa, e o preenchimento é trivial para quem "
     "registra a operação.", "Média"),
    ("13", "Publicar o endpoint DAIR_APLICACOES_RESGATE com os campos acima",
     "API do CADPREV", "—", "Endpoint existe; conteúdo não verificável",
     "O encaminhamento que resume os doze anteriores. A APR registra operação a "
     "operação e alimenta o DAIR; é onde um desvio de preço efetivamente "
     "acontece, e o único nível em que ele seria auditável em dados. Sem isso, "
     "cada campo acima segue existindo no sistema e invisível fora dele.",
     "Alta"),
    ("14", "Levar emissor, código de registro, taxa e vencimento também para a "
     "posição (DAIR_CARTEIRA)", "API do CADPREV", "Coletado na APR",
     "Não — verificado: 16 campos",
     "A carteira foi observada em resposta real e tem dezesseis campos: ano, "
     "mês, identificador, ente, nome do ativo em texto livre, segmento, tipo, "
     "CNPJ do ente, UF, quantidade, valor unitário, valor total, patrimônio, "
     "dois percentuais e o teto da classe. A posição não sabe de que emissor é "
     "o papel que carrega. Herdar da APR o que já foi digitado resolveria sem "
     "pedir nada novo ao RPPS.", "Alta"),
]

def _contar(prefixo):
    return sum(1 for x in MELHORIAS if x[3].startswith(prefixo))


#: Contado sobre a lista, não escrito à mão: já errei esse número uma vez
#: afirmando "oito dos doze" onde eram sete, num texto que ia para fora.
JA_COLETADOS = _contar("Sim") + _contar("Coletado")
LACUNAS = _contar("NÃO")

NOTA_MELHORIAS = (
    "A tela de cadastro da APR no CADPREV tem 49 campos, e {0} dos {1} "
    "itens desta lista JÁ SÃO COLETADOS por ela — emissora, intermediária e "
    "custodiante com validade de credenciamento, taxa de juros de emissão, "
    "indexador e percentual, as três datas, rating com agência, e quatro blocos "
    "de texto sobre o processo de investimento e o parecer dos colegiados. O "
    "problema não é de coleta: é que nada disso chega ao dado aberto, e a "
    "posição publicada (DAIR_CARTEIRA, dezesseis campos observados) não carrega "
    "nem o emissor do papel. Só {2} itens são lacuna real de cadastro: a "
    "espécie da LF e o mercado da operação. Para quem trabalha dentro do "
    "CADPREV a consequência é melhor do que parece — boa parte do que falta a "
    "este levantamento pode ser consultada hoje, operação a operação, sem "
    "depender de mudança nenhuma.").format(JA_COLETADOS, len(MELHORIAS), LACUNAS)


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
