"""Conjunto de demonstração — dados sintéticos, no formato da API.

Para que serve
--------------
O painel precisa abrir e funcionar para quem clona o repositório sem ter a API à
mão: para desenvolver a interface, para revisar um ajuste e para os testes. Este
módulo escreve amostras no **formato cru da API**, que depois passam pelo mesmo
caminho de ingestão dos dados reais — o pipeline é exercitado por inteiro, e não
contornado.

Nada aqui é dado real
---------------------
Os valores são gerados com semente fixa e ordem de grandeza plausível. Todo
build feito a partir deles carimba ``origem: demonstracao`` no ``meta.json``, e
a interface mostra aviso permanente. Um painel de dados públicos não pode deixar
dúvida sobre o que está na tela.

Nível de decomposição
---------------------
Por padrão, a carteira sai **sem** o campo de plano do ativo — que é exatamente
o que se sabe hoje sobre a API. O demo então roda no Nível B, mostrando a
interface no estado honesto. ``--nivel-a`` gera o campo para quem quiser ver a
decomposição de três vias antes de o Swagger ser lido.
"""

import json
import os
import random
from typing import Any, Dict, List

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_DEMO = os.path.join(RAIZ, "fixtures", "demo")

ANO = 2026
MES_DAIR = 8

#: As competências do DAIR que a amostra traz. Mais de uma de propósito: a tela
#: detalhada da carteira compara meses, e é com várias no banco que se prova que
#: os agregados nacionais escolhem uma em vez de somar todas.
_COMPETENCIAS_DO_DAIR = (MES_DAIR, MES_DAIR - 1, MES_DAIR - 2)

_ENTES = [
    # (uf, nome, esfera esperada, porte relativo)
    ("SP", "Governo do Estado de São Paulo", 240.0),
    ("RJ", "Governo do Estado do Rio de Janeiro", 132.0),
    ("MG", "Governo do Estado de Minas Gerais", 98.0),
    ("RS", "Governo do Estado do Rio Grande do Sul", 61.0),
    ("BA", "Governo do Estado da Bahia", 44.0),
    ("ES", "Governo do Estado do Espírito Santo", 27.0),
    ("SP", "São Paulo", 72.0),
    ("RJ", "Rio de Janeiro", 38.0),
    ("MG", "Belo Horizonte", 21.0),
    ("ES", "Vitória", 9.4),
    ("PR", "Curitiba", 12.6),
    ("PE", "Recife", 7.1),
    ("SC", "Florianópolis", 5.2),
    ("GO", "Goiânia", 6.3),
    ("PA", "Belém", 3.8),
    ("AM", "Manaus", 4.1),
]

_MUNICIPIOS = [
    ("ES", "Vila Velha"), ("ES", "Serra"), ("ES", "Cariacica"),
    ("ES", "Linhares"), ("ES", "Colatina"), ("ES", "Guarapari"),
    ("RJ", "Quatis"), ("RJ", "Volta Redonda"), ("RJ", "Niterói"),
    ("SP", "Campinas"), ("SP", "Santos"), ("SP", "Sorocaba"),
    ("MG", "Contagem"), ("MG", "Uberlândia"), ("MG", "Juiz de Fora"),
    ("PR", "Londrina"), ("PR", "Maringá"), ("RS", "Caxias do Sul"),
    ("SC", "Joinville"), ("SC", "Blumenau"), ("BA", "Feira de Santana"),
    ("BA", "Vitória da Conquista"), ("PE", "Olinda"), ("CE", "Sobral"),
    ("MA", "Imperatriz"), ("PI", "Parnaíba"), ("PB", "Campina Grande"),
    ("RN", "Mossoró"), ("AL", "Arapiraca"), ("SE", "Lagarto"),
    ("GO", "Anápolis"), ("MT", "Rondonópolis"), ("MS", "Dourados"),
    ("PA", "Santarém"), ("AM", "Parintins"), ("RO", "Ji-Paraná"),
    ("AC", "Cruzeiro do Sul"), ("TO", "Gurupi"), ("AP", "Santana"),
    ("RR", "Rorainópolis"),
]

#: Segmentos e limites como a API os devolve (``no_segmento`` e ``pc_cmn``).
#: Classes de ativo como a API as devolve: o teto é da CLASSE, não do segmento,
#: e dentro de Renda Fixa convivem tetos de 20%, 80% e 100%. É essa convivência
#: que torna errado comparar o total do segmento com um teto qualquer dele — e
#: uma amostra com uma classe por segmento não teria como revelar o erro.
#:
#: (segmento, classe, teto da classe, fatia do patrimônio)
_CLASSES = [
    ("Renda Fixa", "Fundo/Classe 100% Títulos Públicos ou ETF TP TN  Art. 7° I", 100.0, 0.30),
    ("Renda Fixa", "Títulos Públicos – Oferta Balcão  Art. 7° III", 100.0, 0.22),
    ("Renda Fixa", "Fundo/Classe de Investimento em Renda Fixa/ETF sem subclasse  Art. 7° IV", 80.0, 0.17),
    ("Renda Fixa", "Fundo/Classe de Investimento em Crédito Privado  Art. 7° VII", 20.0, 0.05),
    ("Renda Variável", "Fundo/Classe de Investimento em Ações  Art. 8° I", 40.0, 0.09),
    ("Renda Variável", "Fundo/Classe de Investimento em BDR-Ações e BDR-ETF  Art. 9°-A III", 10.0, 0.02),
    ("Investimentos Estruturados", "Fundo/Classe de Investimento Multimercado  Art. 10", 15.0, 0.035),
    ("Investimentos Estruturados", "Fundo/Classe de Investimento em Participações (FIP)  Art. 10", 10.0, 0.01),
    ("Investimentos no Exterior", "Fundo/Classe de Investimento no Exterior Investidor Profissional  Art. 9°", 10.0, 0.04),
    ("Fundos Imobiliários", "Fundo/Classe de Investimento Imobiliário  art. 11", 20.0, 0.02),
    ("Empréstimos Consignados", "Empréstimos Consignados  art. 12", 5.0, 0.005),
    ("Imóveis", "Imóveis  art. 13", None, 0.02),
    ("Disponibilidades Financeiras", None, None, 0.045),
]

#: Entes que declaram imóveis na carteira. Só 57 dos 857 RPPS confrontáveis
#: fazem isso em 22/09/2026, e a amostra reproduz os dois comportamentos que a
#: base nacional tem: o ente que **não** leva os imóveis às contas de aplicação
#: do Anexo 04 (o caso de Diadema/SP, 70% da carteira em imóveis e −70,03% de
#: divergência que some ao tirá-los) e o que leva (o Rio de Janeiro/RJ, 59,9%
#: em imóveis e 0,29% de divergência). É esse par que sustenta a palavra
#: "depende" na tela — com um caso só, o painel teria de afirmar uma regra que
#: a fonte não tem.
_ENTE_IMOVEIS_FORA = 12
_ENTE_IMOVEIS_DENTRO = 15
_ENTES_COM_IMOVEIS = frozenset({_ENTE_IMOVEIS_FORA, _ENTE_IMOVEIS_DENTRO})

#: A classe que a própria fonte marca como fora do rol da resolução. Não é teto
#: estourado: é ativo que a norma não prevê. Em 17/09/2026 eram 45 entes.
_CLASSE_FORA_DA_NORMA = ("Demais ativos não enquadrados na Resolução CMN",
                         "Outros Ativos Não Enquadrados na Resolução CMN", None, 0.03)

#: O ente cujo balanço mais recente é de dois exercícios antes do esperado.
#: O par DRAA(N) × DCA(N−1) deixa de valer, e a tela mostra os dois números sem
#: a diferença.
_ENTE_BALANCO_ATRASADO = 3

#: A conta do total da provisão matemática no plano de contas. Repetida aqui
#: com o mesmo código que o painel lê, para que a amostra e a leitura não possam
#: divergir em silêncio.
_DCA_TOTAL = "P2.2.7.2.0.00.00"

#: Governança: (pessoa, colegiado, [(certificação, mês de validade)]).
#: Mês positivo = vence no ano seguinte (vigente); negativo = venceu no anterior.
#: O segundo caso é o que o painel não pode acusar: uma certificação vencida
#: convivendo com outra vigente atende o requisito.
_GOVERNANCA = (
    ("ANA PAULA SOUZA", "GESTOR DE RECURSOS DO RPPS",
     (("CPA 20", 6), ("CGRPPS", -5))),
    ("CARLOS EDUARDO LIMA", "COMITÊ DE INVESTIMENTOS",
     (("CPA 10", -3), ("CPA 20", -11))),
    ("MARIA DE FÁTIMA ROCHA", "COMITÊ DE INVESTIMENTOS",
     (("CPA 10", 9),)),
)

#: Entes que carregam ativo fora do rol.
_ENTES_FORA_DA_NORMA = frozenset({7, 14, 23})

#: Entes em que alguém responde pelos recursos sem nenhuma certificação
#: vigente. É o alerta da aba Ficha, e precisa de contraparte: se todos
#: estivessem irregulares, o consolidado nacional não provaria que sabe contar
#: os dois lados.
_ENTES_GOVERNANCA_IRREGULAR = frozenset({1, 4, 9, 16, 22, 30, 41})

#: O ente cuja folha de inativos supera os ingressos. Sem ele, o quadro
#: consolidado de caixa não tem nenhum RPPS deficitário para sinalizar.
_ENTE_CAIXA_DEFICITARIO = 10

#: Entes que declararam só parte do ano no DIPR. Sem eles, o total nacional de
#: caixa somaria todo mundo e passaria no teste — a regra que exclui a série
#: incompleta só é testável quando existe uma série incompleta.
_ENTES_DIPR_PARCIAL = frozenset({8, 19, 27})

#: Estados que fixaram alíquota militar diferente da referência federal de
#: 10,5%. Não é irregularidade: é competência legislativa deles.
_ALIQUOTAS_MILITARES = {2: 14.0, 5: 11.0}

#: Os Estados que declaram ativo garantidor para a massa militar. Na base real
#: são 2 de 26 com cobertura relevante (Amapá, 31,5%; Roraima, 30,1%) e um
#: terceiro começando (Rio Grande do Sul, 5,1%); os outros 14 declaram zero e os
#: 9 restantes declaram valores simbólicos, abaixo de 1% das provisões.
_ESTADOS_COM_FUNDO_MILITAR = frozenset({4})

#: O ente que estoura um teto de verdade: BDR bem acima dos 10% da classe.
_ENTE_EXCEDE_CLASSE = 8

#: O ente cujo segmento Renda Fixa passa de 80% com todas as classes dentro dos
#: próprios tetos. Pela regra antiga — segmento contra um teto qualquer do
#: segmento — ele era acusado de ilegalidade; pela regra correta, está em ordem.
#: Nacionalmente esse era o caso de 371 dos 390 RPPS acusados.
_ENTE_FALSO_EXCESSO = 9

#: Valor de cota único, para que a aritmética do demo seja conferível a olho:
#: quantidade x cota tem de bater com o valor total, e é a violação dessa
#: identidade que revela o lançamento envenenado.
_COTA = 4.1571579040

#: Piso do patrimônio líquido dos fundos do catálogo. Compartilhar fundos entre
#: os entes é o que permite ao painel saber o tamanho de cada um: com um
#: declarante só não há consenso, e sem consenso não há régua.
#:
#: O PL declarado varia de declarante para declarante, como na fonte real — lá
#: o mesmo fundo aparece com valores que diferem em ordens de grandeza. O que
#: não varia é a relação: nenhum RPPS é dono de mais do que o fundo inteiro.
_PL_FUNDO = 5.2e8

#: O ente cuja carteira traz a cota com a vírgula seis casas fora do lugar,
#: reproduzindo Santo Afonso/MT na carga de 15/09/2026. É um município pequeno,
#: como o caso real: o erro de digitação não escolhe ente grande, e num ente
#: grande a posição envenenada passaria de um quatrilhão de reais — magnitude
#: em que o próprio float perde os centavos, o que é problema do demo e não do
#: painel.
_ENTE_ENVENENADO = 20

#: Entes que pararam de entregar o DAIR no segundo mês do exercício. O
#: primeiro deles ainda tem a carteira daquele mês guardada — é o caso que a
#: varredura nacional não alcança e o ``dair-atrasados`` vai buscar ente a
#: ente: a ficha dele mostra fevereiro, com a data à vista, em vez de não
#: mostrar carteira nenhuma. O segundo entregou só o cabeçalho, sem carteira,
#: e continua sem nada a mostrar — ausência que não é zero nem defasagem.
_ENTES_DEFASADOS = frozenset({5, 11})
_ENTE_SO_CABECALHO = 11

#: Entes que declararam adiantado: entregaram o mês seguinte ao que o país
#: declarou. O prazo do DAIR vai até o fim do mês seguinte, então uma minoria
#: sempre está à frente — em 22/09/2026 eram 305 dos 1.821. A ficha deles
#: mostra o mês novo, que é a posição real; o comparativo continua lendo a
#: competência de referência, que eles também declararam.
_ENTES_ADIANTADOS = frozenset({3, 9})

#: Entes que reenviaram o DRAA: a API devolve as duas versões convivendo, e
#: somá-las dobraria o saldo devedor. Em 17/09/2026 isso atingia 176 dos 1.652
#: entes com plano de amortização.
_ENTES_REENVIARAM = frozenset({1, 6, 17})

#: A submissão que foi substituída — anterior à válida, e que não pode entrar
#: em nenhuma soma.
_ENVIO_SUBSTITUIDO = "{}-03-30 09:00:00.000".format(ANO)

#: Entes com notificação da SPREV. O conjunto real é estreito: em 17/09/2026,
#: 770 itens em 222 entes, todos sobre segregação de massa.
_ENTES_NOTIFICADOS = frozenset({0, 4, 12, 20})

#: Ente cujo pagamento não cobre os juros nos primeiros anos, de modo que o
#: saldo devedor cresce em vez de amortizar.
_ENTES_SALDO_CRESCENTE = frozenset({0})

#: Situações, com as grafias que a fonte usa — inclusive "pendencia" sem acento.
_NOTIFICACOES = (
    ("Consistência - Segregação da Massa",
     "Resposta analisada. Item sem pendencia"),
    ("Alteração de Segregação de Massa - Parecer Prévio",
     "Notificacao respondida fora do prazo. Situacao irregular."),
    ("Implantação Segregação da Massa - Estudo Técnico",
     "Notificacao emitida. Aguardando resposta"),
)

#: Itens de fluxo comparados entre projetado e executado.
_FLUXOS_COMPARADOS = (
    (190000, "TOTAL DAS RECEITAS COM CONTRIBUIÇÕES E COMPENSAÇÃO", 1.0),
    (109001, "Base de Cálculo da Contribuição Normal", 2.4),
    (240000, "TOTAL DAS DESPESAS COM BENEFÍCIOS DO PLANO", 1.45),
    (215001, "Plano de Amortização do Déficit Atuarial", 0.32),
)


def _versoes(reenviou, envio_valido):
    """As submissões de um exercício: a substituída, quando houve, e a válida."""
    if reenviou:
        return ((_ENVIO_SUBSTITUIDO,
                 "Substituída Antes da Recepção dos Arquivos Digitalizados"),
                (envio_valido, "Documentos Digitalizados"))
    return ((envio_valido, "Documentos Digitalizados"),)


#: Entes cujo CRP venceu há mais de meio ano — irregularidade instalada, e não
#: renovação em curso. Sem um caso assim o filtro correspondente não teria o
#: que excluir em nenhum teste.
_ENTES_CRP_ANTIGO = frozenset({2, 9})

#: Entes que migraram para o RGPS: continuam no CRP, que é do ente federativo,
#: mas não têm RPPS. São 3.411 no país, e contá-los como RPPS inflava todo
#: denominador nacional.
_ENTES_SEM_RPPS = frozenset({7, 13, 19})

_ULTIMO_DIA = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
               7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def _fundo(segmento, n):
    """Identificação e nome de um fundo do catálogo compartilhado."""
    codigo = "{:03d}{:011d}".format(n + 1, abs(hash(segmento)) % 10**11)
    return codigo, "{} — fundo exemplo {}".format(segmento, n + 1)


#: Como o RPPS descreve um título público comprado no balcão. São textos livres,
#: e a amostra traz os quatro formatos que a base nacional tem em 22/09/2026:
#: com vencimento e data de compra, com as duas datas sem dizer qual é qual,
#: só o nome comercial do Tesouro Direto (80% dos casos, sem vencimento
#: nenhum), e com o declarante trocando os campos de lugar.
_TITULOS = (
    "NTNB 15082040 (Compra em 06122024 Tx 67643)",
    "NTNB 15052055 (Compra em 10042025 Tx 7,3600)",
    "LFT 01092026 (Compra em 12032024)",
    "NTNB_07032006_15052035",
    "Tesouro IPCA+ com Juros Semestrais (NTNB)",
    "Tesouro Prefixado (LTN)",
    "NTNB 19052025 (Compra em 15052045 Tx 7,1730)",
)


def _titulo_publico(n):
    """Identificação e nome de um título público — na ordem que a fonte usa.

    **Os dois campos trocam de papel aqui.** Num fundo, ``no_fundo`` é o nome e
    ``id_ativo`` é o CNPJ; num título público, ``id_ativo`` traz a descrição
    escrita à mão e ``no_fundo`` traz um número de contrato. Em 22/09/2026 isso
    valia para 6.844 das 7.091 posições de título público do país — e era por
    isso que a tela mostrava um número na coluna "Ativo".
    """
    return _TITULOS[n % len(_TITULOS)], str(20500815 + n * 7919)


#: Descrições exatamente como a API as devolve — o painel casa por texto.
_HIPOTESES = [
    ("Projeção da Taxa de Juros Real para o Exercício", "5.38"),
    ("Projeção da Taxa de Inflação de Longo Prazo", "4.00"),
    ("Projeção de Crescimento Real do Salário", "1.00"),
    ("Projeção de Crescimento Real dos Benefícios do Plano", "0.00"),
    ("Projeção da Taxa de Rotatividade", "1.00"),
]

_COMPROMISSOS = [
    ("1.1", "Provisões de benefícios concedidos", 1.00, 0.0),
    ("1.2", "Provisões de benefícios a conceder", 0.81, 0.35),
    ("2.1", "Contribuições futuras do ente", -0.63, -0.25),
    ("2.2", "Contribuições futuras dos segurados", -0.40, -0.16),
    ("3.1", "Ativos garantidores", -0.17, 0.0),
]


def _cnpj(indice: int) -> str:
    return "{:014d}".format(10000000000000 + indice * 137)


def gerar(nivel_a: bool = False, semente: int = 20260914) -> Dict[str, List[Dict[str, Any]]]:
    """Monta o conjunto completo, no formato cru da API.

    Os nomes e as formas seguem o que a API devolve de verdade — inclusive os
    formatos longos (uma linha por rubrica, por item de fluxo, por grupo
    populacional) e o histórico completo de CRP. Um demo em formato diferente
    do real não testaria nada do que importa.
    """
    rnd = random.Random(semente)
    entes = [(uf, nome, porte) for uf, nome, porte in _ENTES]
    entes += [(uf, nome, round(rnd.uniform(0.18, 4.2), 2))
              for uf, nome in _MUNICIPIOS]

    tabelas: Dict[str, List[Dict[str, Any]]] = {
        nome: [] for nome in (
            "RPPS_REGIME_PREVIDENCIARIO", "RPPS_CRP", "RPPS_ALIQUOTA", "DIPR",
            "DAIR_CARTEIRA", "DAIR_IDENTIFICACAO", "DAIR_GOVERNANCA",
            "DRAA_ESTATISTICA", "DRAA_SEGREGACAO_MASSA",
            "DRAA_FLUXO_ATUARIAL", "DRAA_VALORES_COMPROMISSOS",
            "DRAA_HIPOTESE_ATUARIAL", "DRAA_PLANO_CUSTEIO",
            "DRAA_ENCAMINHAMENTO", "DRAA_NOTIFICACAO",
            "DRAA_COMPARATIVO_RECEITA", "DRAA_PLANO_AMORTIZACAO")
    }

    for indice, (uf, nome, porte) in enumerate(entes):
        cnpj = _cnpj(indice)
        ident = {"nr_cnpj_entidade": cnpj, "no_ente": nome, "sg_uf": uf}
        segregado = rnd.random() < 0.38
        patrimonio = porte * 1e9
        # Só os Estados têm militares. Nenhum município do demo recebe massa
        # militar, porque nenhum município do país tem uma.
        eh_governo_estadual = nome.startswith("Governo do Estado")

        # Quem migrou para o RGPS tem duas vigências: o RPPS antigo e o regime
        # atual. É a mais recente que vale.
        sem_rpps = indice in _ENTES_SEM_RPPS
        tabelas["RPPS_REGIME_PREVIDENCIARIO"].append(dict(
            ident, tp_regime="RPPS", dt_inicio="1991-05-21 03:00:00.000",
            dt_fim=None, no_tipo_legislacao="LEI", nr_legislacao=str(1000 + indice)))
        if sem_rpps:
            tabelas["RPPS_REGIME_PREVIDENCIARIO"].append(dict(
                ident, tp_regime="RGPS", dt_inicio="2015-03-10 03:00:00.000",
                dt_fim=None, no_tipo_legislacao="LEI",
                nr_legislacao=str(2000 + indice)))

        # CRP: o endpoint devolve o histórico. Três emissões por ente, e a
        # situação da mais recente é o que o painel deve ler.
        crp_antigo = indice in _ENTES_CRP_ANTIGO
        for anos_atras in (2, 1, 0):
            vencido = anos_atras == 0 and (crp_antigo or rnd.random() > 0.82)
            judicial = anos_atras == 0 and not crp_antigo and rnd.random() > 0.94
            emissao = "{}-{:02d}-{:02d}".format(
                ANO - anos_atras, rnd.randint(1, 12), rnd.randint(1, 28))
            if anos_atras == 0 and crp_antigo:
                # Emitido no começo do exercício e vencido logo depois: em
                # setembro já são meses de irregularidade, não atraso de papel.
                emissao = "{}-01-15".format(ANO)
                validade = "{}-02-10".format(ANO)
            else:
                validade = "{}-{:02d}-{:02d}".format(
                    ANO - anos_atras + (0 if vencido else 1),
                    rnd.randint(1, 12), rnd.randint(1, 28))
            tabelas["RPPS_CRP"].append(dict(
                ident, nr_crp="{:06d}-{:06d}".format(indice + 1, rnd.randint(1, 999999)),
                dt_emissao=emissao, dt_validade=validade,
                # Os dois campos vêm trocados na API real; o demo reproduz isso.
                ds_situacao="JUDICIAL" if judicial else "ADMINISTRATIVO",
                tp_crp="VENCIDO" if vencido else "VÁLIDO"))

        for sujeito, aliquota in (("Ativos", 14.0), ("Aposentados", 14.0),
                                  ("Pensionistas", 14.0),
                                  ("Ente", round(rnd.uniform(14, 24), 2))):
            tabelas["RPPS_ALIQUOTA"].append(dict(
                ident, ds_plano_segregacao="Fundo em Capitalização",
                no_sujeito_passivo=sujeito, vl_aliquota="{:.2f}".format(aliquota),
                dt_inicio_vigencia="2024-01-01 03:00:00.000",
                dt_fim_vigencia=None, id_vigente="VIGENTE", tp_regime="RPPS"))

        # DIPR: uma linha por rubrica, por mês e por plano. Os ids abaixo de 33
        # são bases de cálculo — entram na amostra justamente para que o
        # pipeline continue tendo de excluí-los.
        folha = patrimonio / 1e9 * 3.1e6
        # Nem todo ente declara o ano inteiro, e é o que faz o total nacional
        # de caixa não poder somar todo mundo: meia série de um ao lado da
        # série cheia de outro dá um total que nenhum dos dois declarou.
        meses_do_dipr = 5 if indice in _ENTES_DIPR_PARCIAL else 12
        for mes in range(1, meses_do_dipr + 1):
            extra = 1.45 if mes in (6, 12) else 1.0
            base = folha * extra
            tabelas["DIPR"].append(dict(
                ident, dt_ano=ANO, dt_mes=mes, no_plano="PREVIDENCIARIO",
                no_orgao="Prefeitura", id_rubrica=19, no_rubrica="PAT-SEG",
                te_rubrica="Patronal relativa aos servidores",
                vl_rubrica="{:.2f}".format(base)))
            tabelas["DIPR"].append(dict(
                ident, dt_ano=ANO, dt_mes=mes, no_plano="PREVIDENCIARIO",
                no_orgao="Prefeitura", id_rubrica=27, no_rubrica="SEG",
                te_rubrica="Dos servidores", vl_rubrica="{:.2f}".format(base)))
            # A folha de inativos varia entre os entes, e é o que faz o
            # resultado de caixa ser um do RPPS e não do painel: com um fator
            # só, a distribuição nacional teria desvio zero e o quadro
            # consolidado passaria no teste sem medir nada. Um ente fecha no
            # vermelho, que é o caso que a tela precisa ter o que sinalizar.
            peso_inativos = 0.26 * (0.55 + (indice % 7) * 0.22)
            if indice == _ENTE_CAIXA_DEFICITARIO:
                peso_inativos = 1.35
            for id_rub, sigla, fator in ((56, "PAT-SEG", 0.22), (64, "SEG", 0.14),
                                         (79, "ING-REND-APL", 0.09),
                                         (82, "UT-APO", peso_inativos),
                                         (83, "UT-PEN", 0.05),
                                         (96, "UT-DESP-ADM", 0.012)):
                tabelas["DIPR"].append(dict(
                    ident, dt_ano=ANO, dt_mes=mes, no_plano="PREVIDENCIARIO",
                    no_orgao="Prefeitura", id_rubrica=id_rub, no_rubrica=sigla,
                    te_rubrica=sigla, vl_rubrica="{:.2f}".format(base * fator)))

        # Os fundos são compartilhados entre os entes, como na realidade: os
        # mesmos BB e SICREDI aparecem em centenas de carteiras. Sem esse
        # compartilhamento não há consenso sobre o tamanho de cada fundo, e a
        # régua de lançamento impossível não teria contra o que comparar.
        # Duas passagens: a primeira decide os valores, a segunda os grava com
        # o percentual sobre o total que de fato resultou. Na API o pc_recursos
        # de um ente soma 100% (1.820 dos 1.821 entes em 17/09/2026), e uma
        # amostra em que ele não soma não exercita o enquadramento.
        fatias = []
        catalogo = [c for c in _CLASSES
                    if c[0] != "Imóveis" or indice in _ENTES_COM_IMOVEIS]
        if indice in _ENTES_FORA_DA_NORMA:
            catalogo.append(_CLASSE_FORA_DA_NORMA)
        for segmento, classe, teto, fatia in catalogo:
            peso = fatia * rnd.uniform(0.85, 1.15)
            if indice == _ENTE_FALSO_EXCESSO:
                # Renda Variável em 47% do total, com 38% em ações (teto 40%) e
                # 9% em BDR (teto 10%): as duas classes dentro dos próprios
                # tetos, o segmento acima do maior deles. A regra antiga
                # comparava o segmento com o teto da maior classe e acusava
                # ilegalidade. Era o caso de 371 dos 390 RPPS acusados.
                peso = {0.09: 0.38, 0.02: 0.09}.get(fatia, peso * 0.55)
            if indice == _ENTE_EXCEDE_CLASSE and teto == 10.0 and "BDR" in (classe or ""):
                peso = 0.14  # estouro real: 14% numa classe de teto 10%
            fatias.append((segmento, classe, teto, peso))
        soma = sum(f[3] for f in fatias) or 1.0

        # Três competências, como a base real passa a ter quando a tela
        # detalhada permite comparar meses. É esta amostra que garante que os
        # agregados nacionais não somem competências: com três no banco, um
        # total que somasse meses daria quase o triplo do patrimônio real.
        competencias = list(_COMPETENCIAS_DO_DAIR)
        if indice in _ENTES_ADIANTADOS:
            competencias.insert(0, MES_DAIR + 1)
        if indice in _ENTES_DEFASADOS:
            competencias = [] if indice == _ENTE_SO_CABECALHO else [2]
        for competencia in competencias:
            # A carteira se move de um mês para o outro; o que não muda é a
            # identidade quantidade × cota = valor total.
            deriva = 1.0 + (competencia - MES_DAIR) * 0.012
            for ordem, (segmento, classe, teto, peso) in enumerate(fatias):
                valor_classe = patrimonio * peso / soma * deriva
                ativos = (1 if segmento == "Disponibilidades Financeiras"
                          else rnd.randint(1, 3))
                for n in range(ativos):
                    valor = valor_classe / ativos
                    if "Títulos Públicos" in (classe or ""):
                        fundo_id, fundo_nome = _titulo_publico(ordem * 4 + n)
                    else:
                        fundo_id, fundo_nome = _fundo(segmento, ordem * 4 + n)
                    # Conta e caixa não têm PL; fundo tem, e é sempre maior que
                    # a posição de um cotista só.
                    fundo_pl = (None if segmento == "Disponibilidades Financeiras"
                                else max(_PL_FUNDO, valor * rnd.uniform(8, 300)))
                    cotas = valor / _COTA
                    registro = dict(
                        ident, dt_ano=ANO, dt_mes_bimestre=competencia,
                        no_segmento=segmento,
                        no_tipo_ativo=classe or "Conta corrente",
                        pc_cmn=teto, id_ativo=fundo_id, no_fundo=fundo_nome,
                        qt_rpps="{:.10f}".format(cotas),
                        vl_atual_ativo="{:.10f}".format(_COTA),
                        vl_total_atual="{:.2f}".format(valor),
                        pc_rpps="{:.2f}".format(peso / soma / ativos * 100),
                        vl_patrimonio="{:.2f}".format(fundo_pl) if fundo_pl else None,
                        pc_patrimonio="{:.2f}".format(rnd.uniform(0.4, 16.0)))
                    # Um lançamento envenenado, reproduzindo o caso de Santo
                    # Afonso/MT: a cota digitada com a vírgula seis casas à
                    # direita, na menor classe da carteira de um município
                    # pequeno. Numa classe grande a posição envenenada passaria
                    # de 9e13 reais, ponto em que o float64 deixa de representar
                    # centavos e o demo passa a testar a aritmética da linguagem
                    # em vez da regra do painel.
                    if (indice == _ENTE_ENVENENADO
                            and segmento == "Empréstimos Consignados" and n == 0):
                        registro["vl_atual_ativo"] = "{:.10f}".format(_COTA * 1e6)
                        registro["vl_total_atual"] = "{:.2f}".format(valor * 1e6)
                        registro["pc_patrimonio"] = "1611016.66"
                    if nivel_a:
                        registro["ds_plano"] = (
                            "TAXA DE ADMINISTRAÇÃO" if n == 0 and rnd.random() < 0.12
                            else ("FINANCEIRO" if segregado and rnd.random() < 0.3
                                  else "PREVIDENCIARIO"))
                    tabelas["DAIR_CARTEIRA"].append(registro)

        # DAIR_IDENTIFICACAO: o cabeçalho mensal da declaração. É dele que sai a
        # defasagem — quem parou de entregar não some da base, fica com a última
        # posição envelhecendo.
        ultimo_mes = (2 if indice in _ENTES_DEFASADOS
                      else MES_DAIR + (1 if indice in _ENTES_ADIANTADOS else 0))
        for mes in range(1, ultimo_mes + 1):
            tabelas["DAIR_IDENTIFICACAO"].append(dict(
                ident, dt_ano=ANO, dt_mes=mes,
                dt_posicao="{}-{:02d}-{:02d} 03:00:00.000".format(
                    ANO, mes, _ULTIMO_DIA[mes]),
                dt_envio="{}-{:02d}-15 10:00:00.000".format(
                    ANO + (1 if mes == 12 else 0), 1 if mes == 12 else mes + 1),
                te_finalidade="ENCERRAMENTO_MES", te_justificativa=None,
                te_motivo_retificacao=None, te_descricao_retificacao=None,
                te_justicativa_retificacao=None))

        # DAIR_GOVERNANCA: uma linha por pessoa E POR CERTIFICAÇÃO. Quem tem
        # duas aparece duas vezes, e é comum ter uma vencida ao lado de uma
        # vigente — nesse caso o requisito está atendido e o painel não pode
        # acusar ninguém. A amostra traz os três casos: em ordem, vencida com
        # outra vigente, e só vencidas.
        # Só uma parte dos entes tem alguém sem certificação vigente. Com
        # todos irregulares, o consolidado nacional diria "0 regulares" e a
        # contagem não provaria que sabe separar os dois casos.
        equipe = (_GOVERNANCA if indice in _ENTES_GOVERNANCA_IRREGULAR
                  else _GOVERNANCA[:1] + _GOVERNANCA[2:])
        for pessoa, papel, certificacoes in equipe:
            for tipo, meses in certificacoes:
                validade = (
                    None if meses is None
                    else "{}-{:02d}-15 03:00:00.000".format(
                        ANO + (1 if meses > 0 else -1), abs(meses)))
                tabelas["DAIR_GOVERNANCA"].append(dict(
                    ident, dt_ano=ANO, dt_mes=MES_DAIR,
                    dt_envio="{}-{:02d}-14 22:53:30.503".format(ANO, MES_DAIR),
                    no_pessoa="{} · {}".format(pessoa, nome[:18]),
                    no_cargo=None, tp_vinculo="SERVIDOR EFETIVO",
                    no_atribuicao="OUTROS", no_entidade_governanca=papel,
                    dt_inicio_atuacao="2021-01-01 03:00:00.000",
                    dt_fim_atuacao=None,
                    no_tipo_certificacao=tipo,
                    dt_validade_certificacao=validade,
                    no_entidade_certificadora="Outros"))

        # DRAA_ESTATISTICA: uma linha por grupo populacional, contagem por sexo.
        # A razão civil também varia entre entes — de 0,43 a 5,43 na base real.
        # Um demo em que todo mundo tem a mesma razão desenharia uma parede
        # reta ao lado das barras militares e esconderia justamente o contraste
        # que a separação das massas existe para mostrar.
        madura = rnd.uniform(0.6, 2.1)
        for tipo, fator in (("Servidores", 138), ("Aposentados", 47 * madura),
                            ("Pensionistas", 11 * madura),
                            ("Servidores Iminentes", 9)):
            total = int(porte * fator)
            tabelas["DRAA_ESTATISTICA"].append(dict(
                ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
                cd_populacao=1110100, tp_populacao=tipo,
                no_cat_populacao="DEMAIS SERVIDORES",
                qt_grupo_masc=total // 2, qt_grupo_fem=total - total // 2,
                vl_folha_mensal_masc=total // 2 * 3200.0,
                vl_folha_mensal_fem=(total - total // 2) * 3100.0,
                vl_idade_media_masc=54.2, vl_idade_media_fem=52.8))

        # A massa militar só existe nos Estados, e a fonte a declara de um jeito
        # diferente do civil: tp_populacao diz sempre "Militares" e é
        # no_cat_populacao que separa ativo, reserva/reforma e pensionista.
        # O demo reproduz essa assimetria — é ela que o pipeline tem de tratar.
        if eh_governo_estadual:
            # A razão militar não é a mesma em todo Estado — na base real vai de
            # 0,56 no Rio Grande do Sul a 17,44 em Roraima. Um demo com seis
            # Estados idênticos desenharia uma parede reta e não exercitaria a
            # comparação que a aba existe para fazer.
            maturidade = rnd.uniform(0.55, 2.4)
            for categoria, fator in (("MILITARES - ATIVOS", 41 * maturidade),
                                     ("MILITARES - APOSENTADOS", 23),
                                     ("MILITARES - PENSIONISTAS", 12)):
                total = int(porte * fator)
                tabelas["DRAA_ESTATISTICA"].append(dict(
                    ident, dt_exercicio=ANO, tp_plano="Previdenciário",
                    tp_massa="Militar", cd_populacao=1120100,
                    tp_populacao="Militares", no_cat_populacao=categoria,
                    qt_grupo_masc=total - total // 6, qt_grupo_fem=total // 6,
                    vl_folha_mensal_masc=(total - total // 6) * 7900.0,
                    vl_folha_mensal_fem=total // 6 * 7400.0,
                    vl_idade_media_masc=46.9, vl_idade_media_fem=42.1))

        tabelas["DRAA_SEGREGACAO_MASSA"].append(dict(
            ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
            no_segregacao_massa=("Instituida neste Exercicio ou Mantida"
                                 if segregado else "Não Possui"),
            dt_ingresso_segurado="2012-01-01 00:00:00.000" if segregado else None,
            nr_norma_fundamento="1262",
            dt_norma_fundamento="2004-12-27 02:00:00.000"))

        # DRAA_FLUXO_ATUARIAL: itens de fluxo com um valor projetado cada,
        # incluindo a base de cálculo (109001) e os dois totais.
        receitas = patrimonio / 1e9 * 42e6
        despesas = patrimonio / 1e9 * 61e6
        for codigo, descricao, valor in (
                (109001, "Base de Cálculo da Contribuição Normal", receitas * 2.4),
                (121000, "Benefícios a Conceder - Contribuições do Ente", receitas * 0.6),
                (122000, "Benefícios a Conceder - Contribuições dos Segurados Ativos", receitas * 0.3),
                (111000, "Benefícios Concedidos - Contribuições dos Aposentados", receitas * 0.1),
                (190000, "TOTAL DAS RECEITAS COM CONTRIBUIÇÕES E COMPENSAÇÃO PREVIDENCIÁRIA", receitas),
                (211001, "Benefícios Concedidos - Encargos - Aposentadorias Programadas", despesas * 0.74),
                (215001, "Benefícios Concedidos - Encargos - Pensões Por Morte", despesas * 0.12),
                (221000, "Benefícios a Conceder - Encargos -  Aposentadorias Programadas", despesas * 0.14),
                (240000, "TOTAL  DAS DESPESAS COM BENEFÍCIOS DO PLANO", despesas)):
            tabelas["DRAA_FLUXO_ATUARIAL"].append(dict(
                ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
                nr_fluxo=codigo, no_fluxo=descricao, vl_projetado=round(valor, 2)))

        deficit = patrimonio * rnd.uniform(1.8, 4.6)
        for codigo, descricao, categoria, atual, futura in (
                (300000, "PROVISÃO MATEMÁTICA DOS BENEFÍCIOS CONCEDIDOS",
                 "Resultado", deficit * 0.62, 0),
                (400000, "PROVISÃO MATEMÁTICA DOS BENEFÍCIOS A CONCEDER",
                 "Resultado", deficit * 0.46, deficit * 0.18),
                (500000, "ATIVOS GARANTIDORES DOS COMPROMISSOS DO PLANO", "Resultado",
                 patrimonio, 0),
                (600100, "Déficit Atuarial", "Resultado", deficit, 0),
                (121000, "Benefícios a Conceder - Contribuições Futuras do Ente",
                 "Resultado", deficit * 0.35, deficit * 0.12),
                (211000, "Benefícios Concedidos - Encargos - Aposentadorias Programadas",
                 "Resultado", deficit * 0.9, 0)):
            tabelas["DRAA_VALORES_COMPROMISSOS"].append(dict(
                ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
                cd_demonstrativo=codigo, ds_item_resultado=descricao,
                no_categoria_demonstrativo=categoria,
                vl_geracao_atual="{:.2f}".format(atual),
                vl_geracao_futura="{:.2f}".format(futura) if futura else None))

        for descricao, valor in _HIPOTESES:
            tabelas["DRAA_HIPOTESE_ATUARIAL"].append(dict(
                ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
                cd_hipotese_demografica=10001,
                ds_hipotese_demografica=descricao, tp_unidade="PERCENTUAL",
                te_hipotese_demografica=valor,
                vl_perspectiva_longo_prazo=valor))

        for tipo, aliquota in (("Segurados Ativos", 14.0), ("Aposentados", 14.0),
                               ("Pensionistas", 14.0), ("Ente Federativo", 19.12),
                               ("Ente Federativo - Total", 22.0),
                               ("Taxa de Administração", 2.88)):
            tabelas["DRAA_PLANO_CUSTEIO"].append(dict(
                ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
                tp_contribuicao=tipo, vl_anual_base_calculo=folha * 12,
                vl_aliquota=aliquota, vl_contribuicao_esperada=folha * 12 * aliquota / 100,
                vl_aliquota_definida=aliquota,
                vl_contribuicao_definida=folha * 12 * aliquota / 100))

        # A avaliação atuarial da massa militar, que existe só nos Estados e é
        # uma avaliação à parte — outro fundo, outro resultado, outro custeio.
        #
        # Dois traços que a amostra precisa ter, porque descrevem o regime e não
        # o desempenho: não há contribuição patronal (o tesouro estadual arca
        # com toda a despesa), e na maioria dos Estados não há ativo garantidor
        # nenhum. Em 17/09/2026, 14 dos 26 Estados com massa militar declaravam
        # ZERO ativo garantidor — declaravam, não omitiam. Só o Amapá (31,5%) e
        # Roraima (30,1%) têm cobertura relevante, e o Rio Grande do Sul começa
        # a formar a dele (5,1%).
        if eh_governo_estadual:
            tem_fundo_militar = indice in _ESTADOS_COM_FUNDO_MILITAR
            receitas_mil = receitas * 0.33
            despesas_mil = despesas * 0.41
            for codigo, descricao, valor in (
                    (109001, "Base de Cálculo da Contribuição Normal", receitas_mil * 2.4),
                    (122000, "Benefícios a Conceder - Contribuições dos Segurados Ativos", receitas_mil * 0.55),
                    (111000, "Benefícios Concedidos - Contribuições dos Aposentados", receitas_mil * 0.45),
                    (190000, "TOTAL DAS RECEITAS COM CONTRIBUIÇÕES E COMPENSAÇÃO PREVIDENCIÁRIA", receitas_mil),
                    (211001, "Benefícios Concedidos - Encargos - Aposentadorias Programadas", despesas_mil * 0.8),
                    (215001, "Benefícios Concedidos - Encargos - Pensões Por Morte", despesas_mil * 0.2),
                    (240000, "TOTAL  DAS DESPESAS COM BENEFÍCIOS DO PLANO", despesas_mil)):
                tabelas["DRAA_FLUXO_ATUARIAL"].append(dict(
                    ident, dt_exercicio=ANO, tp_plano="Previdenciário",
                    tp_massa="Militar", nr_fluxo=codigo, no_fluxo=descricao,
                    vl_projetado=round(valor, 2)))

            deficit_mil = patrimonio * rnd.uniform(1.2, 2.8)
            garantidores = patrimonio * 0.31 if tem_fundo_militar else 0.0
            for codigo, descricao, categoria, atual, futura in (
                    (300000, "PROVISÃO MATEMÁTICA DOS BENEFÍCIOS CONCEDIDOS",
                     "Resultado", deficit_mil * 0.71, 0),
                    (400000, "PROVISÃO MATEMÁTICA DOS BENEFÍCIOS A CONCEDER",
                     "Resultado", deficit_mil * 0.29, 0),
                    (500000, "ATIVOS GARANTIDORES DOS COMPROMISSOS DO PLANO",
                     "Resultado", garantidores, 0),
                    (600100, "Déficit Atuarial", "Resultado", deficit_mil, 0),
                    (211000, "Benefícios Concedidos - Encargos - Aposentadorias Programadas",
                     "Resultado", deficit_mil * 0.88, 0)):
                tabelas["DRAA_VALORES_COMPROMISSOS"].append(dict(
                    ident, dt_exercicio=ANO, tp_plano="Previdenciário",
                    tp_massa="Militar", cd_demonstrativo=codigo,
                    ds_item_resultado=descricao,
                    no_categoria_demonstrativo=categoria,
                    vl_geracao_atual="{:.2f}".format(atual),
                    vl_geracao_futura="{:.2f}".format(futura) if futura else None))

            # 10,5% sobre o valor integral, e nenhuma linha de ente: a
            # contribuição patronal não existe neste sistema.
            #
            # Nem todos no mesmo percentual: 10,5% foi a decisão federal, que
            # muitos Estados seguiram, e cada um legisla sobre a sua. Uma
            # amostra em que todos coincidem esconderia que divergir é legítimo.
            aliquota_militar = _ALIQUOTAS_MILITARES.get(indice, 10.5)
            for tipo, aliquota in (("Segurados Ativos", aliquota_militar),
                                   ("Aposentados", aliquota_militar),
                                   ("Pensionistas", aliquota_militar)):
                tabelas["DRAA_PLANO_CUSTEIO"].append(dict(
                    ident, dt_exercicio=ANO, tp_plano="Previdenciário",
                    tp_massa="Militar", tp_contribuicao=tipo,
                    vl_anual_base_calculo=folha * 4,
                    vl_aliquota=aliquota,
                    vl_contribuicao_esperada=folha * 4 * aliquota / 100,
                    vl_aliquota_definida=aliquota,
                    vl_contribuicao_definida=folha * 4 * aliquota / 100))

        # --- encaminhamento do DRAA, com reenvio para alguns ---
        envio_valido = "{}-04-{:02d} 10:12:00.000".format(ANO, rnd.randint(3, 28))
        reenviou = indice in _ENTES_REENVIARAM
        if reenviou:
            tabelas["DRAA_ENCAMINHAMENTO"].append(dict(
                ident, dt_exercicio=ANO, dt_envio=_ENVIO_SUBSTITUIDO,
                te_situacao="Substituída Antes da Recepção dos Arquivos Digitalizados"))
        tabelas["DRAA_ENCAMINHAMENTO"].append(dict(
            ident, dt_exercicio=ANO, dt_envio=envio_valido,
            te_situacao="Documentos Digitalizados"))

        # --- notificações da SPREV, nos três estados que a fonte usa ---
        if indice in _ENTES_NOTIFICADOS:
            for n, (item, situacao) in enumerate(_NOTIFICACOES):
                tabelas["DRAA_NOTIFICACAO"].append(dict(
                    ident, nr_notificacao="{:06d}.{:02d}/{}".format(
                        90000 + indice, n + 1, ANO - 1),
                    no_tipo_documento="DRAA", no_item_analise=item,
                    no_situacao_item_analise=situacao,
                    dt_notificao="{}-03-{:02d} 03:00:00.000".format(ANO - 1, 5 + n),
                    dt_preclusao="{}-04-{:02d} 03:00:00.000".format(ANO - 1, 5 + n),
                    dt_resposta=None, nr_prazo_resposta=30))

        # --- projetado contra executado; a diferença é projetado menos
        # executado, como na fonte, e não o contrário ---
        for codigo, descricao, base in _FLUXOS_COMPARADOS:
            projetado = receitas * base
            executado = projetado * rnd.uniform(0.55, 1.35)
            for quando, situacao in _versoes(reenviou, envio_valido):
                tabelas["DRAA_COMPARATIVO_RECEITA"].append(dict(
                    ident, dt_exercicio=ANO, dt_exercicio_inicial=ANO - 11,
                    tp_plano="Previdenciário", tp_massa="Civil",
                    nr_fluxo=codigo, no_fluxo=descricao,
                    vl_projetado="{:.2f}".format(projetado),
                    vl_executado="{:.2f}".format(executado),
                    vl_diferenca="{:.2f}".format(projetado - executado),
                    dt_envio=quando, te_situacao=situacao))

        # O mesmo item de fluxo é declarado uma vez por massa, com valores de
        # avaliações diferentes. Empilhá-los listaria a rubrica duas vezes.
        if eh_governo_estadual:
            for codigo, descricao, base in _FLUXOS_COMPARADOS:
                projetado = receitas * base * 0.31
                executado = projetado * rnd.uniform(0.6, 1.2)
                for quando, situacao in _versoes(reenviou, envio_valido):
                    tabelas["DRAA_COMPARATIVO_RECEITA"].append(dict(
                        ident, dt_exercicio=ANO, dt_exercicio_inicial=ANO - 11,
                        tp_plano="Previdenciário", tp_massa="Militar",
                        nr_fluxo=codigo, no_fluxo=descricao,
                        vl_projetado="{:.2f}".format(projetado),
                        vl_executado="{:.2f}".format(executado),
                        vl_diferenca="{:.2f}".format(projetado - executado),
                        dt_envio=quando, te_situacao=situacao))

        # --- plano de amortização ano a ano; o primeiro ente da lista paga
        # menos que os juros, e por isso vê o saldo crescer ---
        saldo = patrimonio * 0.9
        taxa = 5.49
        paga_pouco = indice in _ENTES_SALDO_CRESCENTE
        for passo, ano_projetado in enumerate(range(ANO, ANO + 30)):
            juros = saldo * taxa / 100
            pagamento = juros * (0.7 if paga_pouco and passo < 4 else 1.0
                                 ) + saldo * 0.02 * (passo + 1) / 30
            amortizacao = pagamento - juros
            saldo_final = max(0.0, saldo - amortizacao)
            for quando, situacao in _versoes(reenviou, envio_valido):
                tabelas["DRAA_PLANO_AMORTIZACAO"].append(dict(
                    ident, dt_exercicio=ANO, tp_plano="Previdenciário",
                    tp_massa="Civil", dt_ano=ano_projetado, tx_juros=taxa,
                    vl_saldo_inicial="{:.2f}".format(saldo),
                    vl_juros="{:.2f}".format(juros),
                    vl_amortizacao="{:.2f}".format(amortizacao),
                    vl_pagamentos="{:.2f}".format(pagamento),
                    vl_aporte="{:.2f}".format(saldo * 0.001),
                    vl_saldo_final="{:.2f}".format(saldo_final),
                    vl_base_calculo="{:.2f}".format(folha * 12),
                    vl_aliquotas=taxa, dt_envio=quando, te_situacao=situacao))
            saldo = saldo_final
            if saldo <= 0:
                break

        # Dois planos de amortização no mesmo exercício, um por massa, com
        # saldos e anos de quitação diferentes. É o caso do Maranhão na base
        # real: R$ 39,5 bi civis e R$ 18,0 bi militares, que somados viravam um
        # saldo que não existe em nenhum dos dois.
        if eh_governo_estadual:
            saldo = patrimonio * 0.4
            taxa_mil = 5.0
            for ano_projetado in range(ANO, ANO + 22):
                juros = saldo * taxa_mil / 100
                pagamento = juros + saldo * 0.06
                amortizacao = pagamento - juros
                saldo_final = max(0.0, saldo - amortizacao)
                for quando, situacao in _versoes(reenviou, envio_valido):
                    tabelas["DRAA_PLANO_AMORTIZACAO"].append(dict(
                        ident, dt_exercicio=ANO, tp_plano="Previdenciário",
                        tp_massa="Militar", dt_ano=ano_projetado,
                        tx_juros=taxa_mil,
                        vl_saldo_inicial="{:.2f}".format(saldo),
                        vl_juros="{:.2f}".format(juros),
                        vl_amortizacao="{:.2f}".format(amortizacao),
                        vl_pagamentos="{:.2f}".format(pagamento),
                        vl_aporte="{:.2f}".format(saldo * 0.002),
                        vl_saldo_final="{:.2f}".format(saldo_final),
                        vl_base_calculo="{:.2f}".format(folha * 4),
                        vl_aliquotas=taxa_mil, dt_envio=quando,
                        te_situacao=situacao))
                saldo = saldo_final
                if saldo <= 0:
                    break

    return tabelas
def entes_do_siconfi(tabelas: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """A tabela de entes da federação, no formato do SICONFI.

    Espelha os mesmos entes do conjunto do CADPREV, com a esfera e a capital
    declaradas — que é o ponto: sem elas, a classificação volta a deduzir pelo
    nome, e a dedução por nome é o que promovia o município de Amapá a governo
    estadual.
    """
    vistos, saida = set(), []
    for registro in tabelas["RPPS_CRP"]:
        cnpj = registro["nr_cnpj_entidade"]
        if cnpj in vistos:
            continue
        vistos.add(cnpj)
        nome, uf = registro["no_ente"], registro["sg_uf"]
        estadual = nome.lower().startswith(("governo do estado",
                                            "governo do distrito"))
        saida.append({
            "cod_ibge": 3200000 + len(vistos),
            "ente": nome,
            "capital": "1  " if (not estadual and len(vistos) % 9 == 1) else "0  ",
            "regiao": "SE",
            "uf": uf,
            "esfera": "E" if estadual else "M",
            "exercicio": ANO,
            "populacao": 10000 + len(vistos) * 137,
            "cnpj": cnpj,
        })
    return saida


#: Como o SICONFI nomeia, no Anexo 04, as contas de cada um dos três fundos.
#: São os códigos reais, observados em 17/09/2026.
_CONTAS_DO_RREO = (
    ("InvestimentosDoRPPSPrevidenciario", "RREO4CaixaDoRPPSPrevidenciario",
     "TotalReceitasRPPSPrevidenciario", "TotalDasDespesasRPPSPrevidenciario", 0.47),
    ("InvestimentosEAplicacoesFundoEmReparticao",
     "CaixaEEquivalenteDeCaixaFundoEmReparticao",
     "TotalReceitasRPPSFinanceiro", "TotalDasDespesasRPPSFinanceiro", 0.50),
    ("InvestimentosEAplicacoesAdministracaoDoRPPS",
     "CaixaEEquivalenteDeCaixaAdministracaoDoRPPS",
     "TotalDasReceitasDaAdministracaoRPPS",
     "TotalDasDespesasDaAdministracaoRPPS", 0.03),
)


def rreo_do_siconfi(tabelas: Dict[str, List[Dict[str, Any]]],
                    entes_siconfi: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """O Anexo 04 de cada ente, coerente com a carteira que ele declarou.

    Coerente de propósito: o painel confronta as duas apurações do mesmo
    patrimônio, e uma amostra em que elas não conversam não testaria esse
    confronto — testaria só que a tela desenha.
    """
    # Só a competência mais recente: o Anexo 04 é uma posição, não um acumulado,
    # e somar meses daria um patrimônio que nenhuma das duas fontes declara.
    carteira: Dict[str, float] = {}
    imoveis: Dict[str, float] = {}
    for registro in tabelas["DAIR_CARTEIRA"]:
        if registro["dt_mes_bimestre"] != MES_DAIR:
            continue
        cnpj = registro["nr_cnpj_entidade"]
        valor = float(registro["vl_total_atual"])
        carteira[cnpj] = carteira.get(cnpj, 0.0) + valor
        if registro["no_segmento"] == "Imóveis":
            imoveis[cnpj] = imoveis.get(cnpj, 0.0) + valor

    linhas: List[Dict[str, Any]] = []
    for n, ente in enumerate(entes_siconfi):
        total = carteira.get(ente["cnpj"])
        if not total:
            continue
        # Dois casos que o painel precisa distinguir de divergência, e que
        # custaram duas correções: o ente que entrega receitas e despesas sem o
        # saldo das aplicações, e o que declara o saldo de um fundo e omite o de
        # outro que movimenta receita. Tratados como zero, acusariam uma
        # diferença de cem por cento que a fonte nunca declarou.
        sem_saldo = n == 4
        saldo_parcial = n == 6
        # Um terceiro caso que também não é divergência: o caixa negativo.
        # Descoberto bancário ou reclassificação contábil — número legítimo,
        # declarado, e que não é carteira. Somá-lo e dividir por esse total
        # produzia divergência a partir de denominador negativo em 154 dos
        # 1.432 entes confrontáveis da base nacional.
        caixa_negativo = n == 8
        # Uma diferença pequena entre as fontes é o esperado: datas de posição e
        # critérios distintos. Um ente foge da faixa para que a tela tenha o que
        # sinalizar.
        desvio = 1.12 if n == 2 else 1.0 + (n % 5) * 0.004
        # Os imóveis, quando o ente não os leva às contas de aplicação. É a
        # assimetria que o painel não resolve e mostra: aqui um dos dois entes
        # com imóveis os omite do Anexo 04 e o outro não, como na base real.
        base_do_anexo = total
        if n == _ENTE_IMOVEIS_FORA:
            base_do_anexo = total - imoveis.get(ente["cnpj"], 0.0)
        for ordem, (cod_inv, cod_caixa, cod_rec, cod_desp,
                    fatia) in enumerate(_CONTAS_DO_RREO):
            recursos = base_do_anexo * desvio * fatia
            base = {"exercicio": ANO, "periodo": 3, "cod_ibge": ente["cod_ibge"],
                    "uf": ente["uf"], "instituicao": ente["ente"],
                    "anexo": "RREO-Anexo 04", "populacao": ente["populacao"]}
            omite_saldo = sem_saldo or (saldo_parcial and ordem == 0)
            valores = [
                ("RECEITAS REALIZADAS ATÉ O BIMESTRE (b)", cod_rec, recursos * 0.11),
                ("DESPESAS PAGAS ATÉ O BIMESTRE (f)", cod_desp, recursos * 0.09),
            ]
            if not omite_saldo:
                valores = [("SALDO ATUAL", cod_inv, recursos * 0.98),
                           ("SALDO ATUAL", cod_caixa,
                            recursos * (-0.06 if caixa_negativo else 0.02))] + valores
            for coluna, cod, valor in valores:
                linhas.append(dict(base, coluna=coluna, cod_conta=cod,
                                   conta=cod, valor=round(valor, 2)))

        # O bloco militar do Anexo 04, que só os Estados declaram — e nem todos.
        # Um Estado fica de fora para que a tela tenha de dizer que a linha
        # falta, em vez de tratar a ausência como zero.
        if ente["ente"].startswith("Governo do Estado") and n != 3:
            contribuicoes = total * 0.021
            despesas = total * 0.09
            base = {"exercicio": ANO, "periodo": 3, "cod_ibge": ente["cod_ibge"],
                    "uf": ente["uf"], "instituicao": ente["ente"],
                    "anexo": "RREO-Anexo 04", "populacao": ente["populacao"]}
            for coluna, cod, valor in (
                    ("RECEITAS REALIZADAS ATÉ O BIMESTRE (b)",
                     "TotalDasContribucoesDosMilirares", contribuicoes),
                    ("DESPESAS PAGAS ATÉ O BIMESTRE (f)",
                     "TotalDasDespesasComInativosEPensionistasMilirares", despesas),
                    ("DESPESAS PAGAS ATÉ O BIMESTRE (f)",
                     "ResultadoAssociadoAInativosEPensionistasMilirares",
                     contribuicoes - despesas)):
                linhas.append(dict(base, coluna=coluna, cod_conta=cod,
                                   conta=cod, valor=round(valor, 2)))
    return linhas


def dca_do_siconfi(tabelas: Dict[str, List[Dict[str, Any]]],
                   entes_siconfi: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """O Anexo I-AB de cada ente, coerente com a avaliação atuarial dele.

    Coerente, mas não idêntica: o balanço reconhece o mesmo passivo sob outra
    norma e em outra data de corte, e uma amostra em que os dois números batem
    exatamente não testaria o confronto — testaria só que a tela soma.

    Três coisas que a amostra precisa ter, porque são as que a fonte real tem e
    a leitura descuidada erraria:

    * as contas redutoras ``2.2.7.2.2``, publicadas com sinal positivo e **fora**
      do total — somar componentes daria um passivo que o balanço não declara;
    * entes sem a conta de fundo em repartição, que é a maioria: em 22/09/2026,
      13 de 15 RPPS amostrados declaravam capitalização e só 2, repartição;
    * um ente que entrega o balanço **sem** a conta de provisão.
    """
    provisoes: Dict[str, float] = {}
    for linha in tabelas["DRAA_VALORES_COMPROMISSOS"]:
        if linha["cd_demonstrativo"] in (300000, 400000):
            cnpj = linha["nr_cnpj_entidade"]
            provisoes[cnpj] = provisoes.get(cnpj, 0.0) + float(
                linha["vl_geracao_atual"])

    linhas: List[Dict[str, Any]] = []
    for n, ente in enumerate(entes_siconfi):
        atuarial = provisoes.get(ente["cnpj"])
        if not atuarial:
            continue
        # O balanço fecha em 31/12 do exercício anterior ao do DRAA: é esse o
        # par que compara a mesma data.
        #
        # Um ente fica com o balanço de dois exercícios atrás — quem atrasou a
        # entrega, o que acontece. Aí o par deixa de descrever a mesma data, e
        # subtrair um do outro mediria o tempo entre eles em vez da divergência
        # entre as apurações. Sem esse caso na amostra, a regra do alinhamento
        # não teria como ser conferida.
        exercicio = ANO - 3 if n == _ENTE_BALANCO_ATRASADO else ANO - 1
        base = {"exercicio": exercicio, "cod_ibge": ente["cod_ibge"],
                "uf": ente["uf"], "instituicao": ente["ente"],
                "anexo": "DCA-Anexo I-AB", "rotulo": "Padrão",
                "coluna": "31/12/{}".format(exercicio),
                "populacao": ente["populacao"]}
        # A contabilidade reconhece um pouco menos que a avaliação atuarial na
        # maioria dos casos, e bem menos em um deles — que é o achado.
        desvio = 0.62 if n == 5 else 1.0 - (n % 7) * 0.012
        contabil = atuarial * desvio
        tem_reparticao = n % 6 == 0
        sem_provisao = n == 9
        # Provisão negativa: medida em 22/09/2026 em 2 de 198 entes com balanço
        # — Goianésia/GO e Morrinhos/GO. O número é declarado e fica na tela; o
        # que não dá é calcular razão contra uma avaliação positiva sobre ele.
        if n == 12:
            contabil = -abs(contabil) * 0.2

        contas = [("P1.0.0.0.0.00.00", "1.0.0.0.0.00.00 - Ativo", contabil * 1.4)]
        if not sem_provisao:
            contas.append((_DCA_TOTAL,
                           "2.2.7.2.0.00.00 - Provisões Matemáticas "
                           "Previdenciárias a Longo Prazo", contabil))
        if tem_reparticao:
            contas += [
                ("P2.2.7.2.1.01.00", "2.2.7.2.1.01.00 - Fundo em Repartição - "
                 "Provisões de Benefícios Concedidos", contabil * 0.68),
                ("P2.2.7.2.1.02.00", "2.2.7.2.1.02.00 - Fundo em Repartição - "
                 "Provisões de Benefícios a Conceder", contabil * 0.29),
                # Redutoras: positivas na publicação e fora do total.
                ("P2.2.7.2.2.01.00", "2.2.7.2.2.01.00 - (-) Fundo em Repartição",
                 contabil * 0.55),
                ("P2.2.7.2.2.05.00", "2.2.7.2.2.05.00 - Obrigação Atual de "
                 "Cobertura de Insuficiência Financeira", contabil * 0.55),
            ]
        else:
            contas += [
                ("P2.2.7.2.1.03.00", "2.2.7.2.1.03.00 - Fundo em Capitalização - "
                 "Provisões de Benefícios Concedidos", contabil * 0.2),
                ("P2.2.7.2.1.04.00", "2.2.7.2.1.04.00 - Fundo em Capitalização - "
                 "Provisões de Benefícios a Conceder", contabil * 0.8),
            ]
        contas.append(("P1.1.4.0.0.00.00", "1.1.4.0.0.00.00 - Investimentos e "
                       "Aplicações Temporárias a Curto Prazo", contabil * 0.24))
        for cod, nome_conta, valor in contas:
            linhas.append(dict(base, cod_conta=cod, conta=nome_conta,
                               valor=round(valor, 2)))
    return linhas


def escrever(destino: str = DIR_DEMO, nivel_a: bool = False) -> Dict[str, int]:
    """Grava as amostras no formato de página da API."""
    os.makedirs(destino, exist_ok=True)
    tabelas = gerar(nivel_a=nivel_a)
    # O SICONFI é outra API e tem outro envelope: o cliente dele procura o
    # arquivo pelo caminho do recurso, não pelo nome do endpoint.
    entes_siconfi = entes_do_siconfi(tabelas)
    with open(os.path.join(destino, "entes.json"), "w", encoding="utf-8") as fh:
        json.dump({"items": entes_siconfi, "hasMore": False}, fh,
                  ensure_ascii=False)
    with open(os.path.join(destino, "rreo.json"), "w", encoding="utf-8") as fh:
        json.dump({"items": rreo_do_siconfi(tabelas, entes_siconfi),
                   "hasMore": False}, fh, ensure_ascii=False)
    with open(os.path.join(destino, "dca.json"), "w", encoding="utf-8") as fh:
        json.dump({"items": dca_do_siconfi(tabelas, entes_siconfi),
                   "hasMore": False}, fh, ensure_ascii=False)
    contagem = {}
    for nome, registros in tabelas.items():
        caminho = os.path.join(destino, nome + ".json")
        with open(caminho, "w", encoding="utf-8") as fh:
            json.dump({"data": registros, "count": len(registros), "limit": 5000},
                      fh, ensure_ascii=False)
        contagem[nome] = len(registros)
    return contagem
