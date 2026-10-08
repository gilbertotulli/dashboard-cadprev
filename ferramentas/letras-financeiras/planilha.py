# -*- coding: utf-8 -*-
"""Escreve a planilha de Letras Financeiras de maio/2024."""
import sys
from collections import defaultdict

sys.path.insert(0, sys.argv[2])
from montar import montar  # noqa: E402

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

BASE, SAIDA = sys.argv[1], sys.argv[3]
#: A competência da CDA. Vem do quarto argumento para a ferramenta servir a
#: qualquer mês; sem ele, maio de 2024, que é o da planilha publicada.
MES = sys.argv[4] if len(sys.argv) > 4 else "202405"
COMPETENCIA = "%s-%s" % (MES[:4], MES[4:])

FONTE = "Arial"
TINTA = "1F3864"
CAB = PatternFill("solid", fgColor="1F3864")
FAIXA = PatternFill("solid", fgColor="EEF2F8")
NOTA = PatternFill("solid", fgColor="FFF4CE")
BORDA = Border(bottom=Side(style="thin", color="BFBFBF"))

DIN = '#,##0.00;(#,##0.00);"-"'
QTD = '#,##0.000000;(#,##0.000000);"-"'
PCT = '0.0000"%";(0.0000"%");"-"'

COLUNAS = [
    ("Evidencia_da_Negociacao", "evidencia", "texto", 34),
    ("Fundo_Declarou_Negociacao", "declarou_negociacao", "texto", 12),
    ("Competencia_Posicao", "competencia", "data", 13),
    ("Data_Vencimento", "vencimento", "data", 13),
    ("Instrumento", "instrumento", "texto", 17),
    ("Emissor_Razao_Social", "emissor", "texto", 34),
    ("Emissor_CNPJ", "emissor_cnpj", "cnpj", 19),
    ("Emissor_Como_Declarado", "emissor_declarado", "texto", 24),
    ("Emissor_Ligado_ao_Fundo", "emissor_ligado", "texto", 11),
    ("Indexador_Descricao", "indexador", "texto", 26),
    ("Taxa_Contratada", "taxa", "texto", 24),
    ("Perc_do_Indexador", "perc_indexador", "pct", 12),
    ("Cupom_aa", "cupom", "pct", 11),
    ("Taxa_Prefixada_aa", "taxa_prefixada", "pct", 12),
    ("Qtd_Adquirida_no_Mes", "qt_aquis", "qtd", 15),
    ("Valor_Adquirido_no_Mes_RS", "vl_aquis", "din", 18),
    ("Valor_Vendido_no_Mes_RS", "vl_venda", "din", 18),
    ("Qtd_Posicao_Final", "qt_final", "qtd", 15),
    ("Variacao_Qtd_vs_Abril", "qt_variacao", "qtd", 15),
    ("Valor_Mercado_Posicao_RS", "vl_mercado", "din", 18),
    ("Fundo_Comprador_Nome", "fundo", "texto", 46),
    ("Fundo_Comprador_CNPJ", "fundo_cnpj", "cnpj", 19),
    ("Fundo_Tipo", "fundo_tipo", "texto", 9),
    ("Fundo_Gestor", "gestor", "texto", 36),
    ("Fundo_Administrador", "administrador", "texto", 32),
    ("Classificacao_Contabil", "classificacao_negoc", "texto", 20),
    ("Agencia_Risco", "agencia_risco", "texto", 13),
    ("Grau_Risco", "grau_risco", "texto", 10),
    ("ANBIMA_Taxa_Indicativa", None, "pct", 14),
    ("Oferta_Publica_CVM", None, "texto", 14),
]


def cnpj(d):
    d = (d or "").zfill(14)
    return "%s.%s.%s/%s-%s" % (d[:2], d[2:5], d[5:8], d[8:12], d[12:]) if len(d) == 14 else d


def cabecalho(ws, titulos, larguras):
    for i, t in enumerate(titulos, start=1):
        c = ws.cell(row=1, column=i, value=t)
        c.font = Font(name=FONTE, size=9, bold=True, color="FFFFFF")
        c.fill = CAB
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = larguras[i - 1]
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:%s1" % get_column_letter(len(titulos))


#: Formato por tipo de coluna. Aplicar só o formato numérico, e deixar fonte,
#: borda e faixa a cargo do estilo padrao da pasta, e o que torna o arquivo
#: viavel: estilizar celula a celula 48 mil linhas x 30 colunas cria 1,4 milhao
#: de registros de estilo, e o LibreOffice nao terminava de recalcular em
#: quinze minutos. Com o estilo padrao o cabecalho continua destacado e o corpo
#: fica legivel — a faixa alternada era conforto, nao informacao.
FORMATO = {"din": DIN, "qtd": QTD, "pct": PCT}


def escrever(ws, registros):
    cabecalho(ws, [c[0] for c in COLUNAS], [c[3] for c in COLUNAS])
    formatos = [FORMATO.get(c[2]) for c in COLUNAS]
    campos = [c[1] for c in COLUNAS]
    ehcnpj = [c[2] == "cnpj" for c in COLUNAS]
    for n, r in enumerate(registros, start=2):
        for i in range(len(COLUNAS)):
            campo = campos[i]
            v = r.get(campo) if campo else None
            if v is None:
                continue
            if ehcnpj[i]:
                v = cnpj(v)
            c = ws.cell(row=n, column=i + 1, value=v)
            if formatos[i]:
                c.number_format = formatos[i]
    return len(registros) + 1


def totalizar(ws, ultima, colunas_soma):
    linha = ultima + 1
    c = ws.cell(row=linha, column=1, value="TOTAL")
    c.font = Font(name=FONTE, size=9, bold=True)
    for titulo in colunas_soma:
        i = [x[0] for x in COLUNAS].index(titulo) + 1
        letra = get_column_letter(i)
        cel = ws.cell(row=linha, column=i,
                      value="=SUM(%s2:%s%d)" % (letra, letra, ultima))
        cel.font = Font(name=FONTE, size=9, bold=True)
        cel.number_format = DIN
    ws.cell(row=linha + 2, column=1,
            value="Fonte: CVM, Dados Abertos, CDA — Composição e Diversificação das "
                  "Aplicações, bloco 5 (cda_fi_BLC_5_202405.csv e _202404.csv). "
                  "Gestor e administrador: registro_fundo_classe.zip e cad_fi.csv. "
                  "Extraído em 07/10/2026.").font = Font(name=FONTE, size=8, italic=True)


def aba_emissores(wb, registros, aba_posicoes):
    """Um emissor por linha, somando o bloco que ele ocupa na aba de posições.

    As somas são fórmulas, não números calculados aqui: quem corrigir um valor
    vê o resumo acompanhar. Mas cada uma soma **o intervalo exato** do emissor,
    não a coluna inteira com SUMIF — a aba tem 43.949 linhas e 102 emissores, e
    um SUMIF por emissor faria o LibreOffice comparar texto 13,4 milhões de
    vezes; com três colunas, 13,4 vezes isso. O recálculo não terminava em dez
    minutos. Somando blocos, cada célula é lida uma vez.

    A aba de posições vem ordenada por CNPJ do emissor justamente para que cada
    emissor seja um bloco contíguo. Mudar aquela ordem quebra estas somas.
    """
    ws = wb.create_sheet("Resumo por emissor")
    titulos = ["Emissor_Razao_Social", "Emissor_CNPJ", "Fundos_Investidores",
               "Posicao_Total_RS", "Perc_do_Total", "Adquirido_em_Maio_RS",
               "Vendido_em_Maio_RS", "Linhas_com_Movimento_em_Maio"]
    cabecalho(ws, titulos, [38, 20, 15, 20, 12, 20, 20, 17])

    blocos = []
    for n, r in enumerate(registros, start=2):
        if blocos and blocos[-1]["cnpj"] == r["emissor_cnpj"]:
            blocos[-1]["fim"] = n
        else:
            blocos.append({"cnpj": r["emissor_cnpj"], "nome": r["emissor"],
                           "ini": n, "fim": n, "fundos": set(), "mov": 0})
        blocos[-1]["fundos"].add(r["fundo_cnpj"])
        if r["evidencia"]:
            blocos[-1]["mov"] += 1
    blocos.sort(key=lambda b: -len(b["fundos"]))

    P = "'%s'" % aba_posicoes
    col = {t[0]: get_column_letter(i + 1) for i, t in enumerate(COLUNAS)}

    def soma(titulo, b):
        L = col[titulo]
        return "=SUM(%s!%s%d:%s%d)" % (P, L, b["ini"], L, b["fim"])

    for n, b in enumerate(blocos, start=2):
        ws.cell(row=n, column=1, value=b["nome"])
        ws.cell(row=n, column=2, value=cnpj(b["cnpj"]))
        ws.cell(row=n, column=3, value=len(b["fundos"]))
        ws.cell(row=n, column=4, value=soma("Valor_Mercado_Posicao_RS", b))
        ws.cell(row=n, column=6, value=soma("Valor_Adquirido_no_Mes_RS", b))
        ws.cell(row=n, column=7, value=soma("Valor_Vendido_no_Mes_RS", b))
        ws.cell(row=n, column=8, value=b["mov"])
        for i in range(1, 9):
            ws.cell(row=n, column=i).border = BORDA
        for i in (4, 6, 7):
            ws.cell(row=n, column=i).number_format = DIN
        for i in (3, 8):
            ws.cell(row=n, column=i).number_format = "#,##0"

    ult = len(blocos) + 1
    total = ult + 1
    for n in range(2, ult + 1):
        c = ws.cell(row=n, column=5,
                    value='=IF($D$' + str(total) + '=0,"",D' + str(n) +
                          '/$D$' + str(total) + ')')
        c.number_format = "0.00%"
        c.border = BORDA
    for i, letra in ((3, "C"), (4, "D"), (6, "F"), (7, "G"), (8, "H")):
        c = ws.cell(row=total, column=i, value="=SUM(%s2:%s%d)" % (letra, letra, ult))
        c.font = Font(name=FONTE, size=9, bold=True)
        c.number_format = DIN if i in (4, 6, 7) else "#,##0"
    ws.cell(row=total, column=1, value="TOTAL").font = Font(name=FONTE, size=9, bold=True)
    ws.cell(row=total + 2, column=1, value=(
        "Cada soma cobre o intervalo exato do emissor na aba \"" + aba_posicoes +
        "\", que vem ordenada por CNPJ do emissor.")
    ).font = Font(name=FONTE, size=8, italic=True)
    return ws


LIMITES = [
    ("Data_Aquisicao", "Não existe publicamente",
     "A CDA é uma declaração mensal de posição: a data mais fina que ela tem é a "
     "competência (31/05/2024). A data exata de cada compra só está no registro da "
     "B3/CETIP, que não é público. A coluna Competencia_Posicao a substitui."),
    ("Data_Vencimento", "CVM · CDA bloco 5 (DT_VENC)", "Completa nas 43.949 linhas."),
    ("Instrumento", "CVM · CDA bloco 5 (TP_ATIVO)",
     "A CDA só diz \"Letra Financeira\". Não distingue LF sênior de LF subordinada "
     "nem de LF subordinada complementar — o campo TP_APLIC é o mesmo nas 43.949 "
     "linhas (\"Depósitos a prazo e outros títulos de IF\")."),
    ("Codigo_Papel", "Não existe no bloco 5",
     "A CVM publica código do ativo e ISIN no bloco 4 (títulos privados), não no "
     "bloco 5, onde a LF está. Sem código do papel não há como juntar duas linhas "
     "de fundos diferentes no mesmo papel com certeza, nem casar com a ANBIMA."),
    ("Codigo_ISIN", "Não existe no bloco 5", "Mesma razão do código do papel."),
    ("Emissor_Razao_Social", "CVM · CDA bloco 5 (EMISSOR)",
     "Texto livre: \"BRADESCO\", \"BANCO BRADESCO S.A.\" e \"BCO BRADESCO SA\" são o "
     "mesmo CNPJ. A coluna traz a grafia mais completa de cada CNPJ, e "
     "Emissor_Como_Declarado traz o que o fundo escreveu."),
    ("Emissor_CNPJ", "CVM · CDA bloco 5 (CNPJ_EMISSOR)",
     "Completo nas 43.949 linhas. É a chave confiável do emissor."),
    ("Indexador_Descricao", "CVM · CDA bloco 5 (DS_INDEXADOR_POSFX)",
     "97,1% preenchido. Os 2,9% restantes são LF prefixada, que não tem indexador."),
    ("Taxa_Contratada", "CVM · CDA bloco 5",
     "Pós-fixada vem em duas partes (% do índice e cupom) e prefixada numa só. A "
     "coluna descreve a remuneração; as três colunas seguintes trazem os números "
     "crus, para cálculo."),
    ("Quantidade", "CVM · CDA bloco 5 (QT_POS_FINAL / QT_AQUIS_NEGOC)",
     "Quantidade adquirida no mês e quantidade em posição no fim do mês, separadas."),
    ("Valor_Aquisicao_RS", "CVM · CDA bloco 5 (VL_AQUIS_NEGOC)",
     "Só 17,5% dos fundos preenchem as colunas de negociação; 499 linhas declaram "
     "aquisição em maio. É por isso que existe a coluna Evidencia_da_Negociacao."),
    ("Valor_Mercado_Posicao_RS", "CVM · CDA bloco 5 (VL_MERC_POS_FINAL)",
     "Completo. VL_CUSTO_POS_FINAL vem vazio em 100% das linhas de LF."),
    ("Fundo_Comprador_Nome", "CVM · CDA bloco 5 (DENOM_SOCIAL)", "Completo."),
    ("Fundo_Comprador_CNPJ", "CVM · CDA bloco 5 (CNPJ_FUNDO_CLASSE)",
     "Completo. Depois da Resolução CVM 175 é o CNPJ da classe, não do fundo."),
    ("Fundo_Gestor", "CVM · registro_fundo_classe.zip + cad_fi.csv",
     "86,8% dos 2.997 fundos. O cadastro antigo sozinho alcançaria 7,3%: a RCVM 175 "
     "partiu o fundo em fundo e classe, e a CDA usa o CNPJ da classe."),
    ("ANBIMA_Spread_Indicativo_Sec", "ANBIMA Data — não existe para maio/2024",
     "Três obstáculos, verificados nesta ordem. (1) A ANBIMA Data mostra uma janela "
     "curta: o rótulo da própria tabela, no código da página, é \"Abas de mais ou "
     "menos cinco dias de LFs\". Maio de 2024 não está lá — o histórico fica no "
     "ANBIMA Feed, que é por assinatura. (2) A API (data-api.prd.anbima.com.br/"
     "web-bff/v1/letras-financeiras?letra-financeira=LF&data-referencia=AAAA-MM-DD) "
     "responde 401 \"token cannot be blank\": exige token de sessão/reCAPTCHA. "
     "(3) A ANBIMA divulga taxas de LF desde 09/10/2023 por classe e faixa de prazo "
     "— LF, LFSN5-, LFSN5+, LFSC —, não por papel."),
    ("ANBIMA_Spread_Compra", "ANBIMA Data — não existe para maio/2024", "Mesma razão."),
    ("ANBIMA_Spread_Venda", "ANBIMA Data — não existe para maio/2024", "Mesma razão."),
    ("ANBIMA_Tipo_Curva", "ANBIMA Data — não existe para maio/2024",
     "Mesma razão, e mais uma: a CDA não traz código do papel nem ISIN para LF, "
     "então mesmo com as taxas em mãos o casamento possível seria por classe e "
     "faixa de prazo, nunca papel a papel. A coluna fica como está, pronta para "
     "receber uma exportação do ANBIMA Feed se houver assinatura."),
    ("— aba RPPS: Via", "Derivado · CDA blocos 5 e 2 + painel CADPREV",
     "Três caminhos, nesta ordem de alcance. \"Dois fundos\" (RPPS → FIC → fundo "
     "com LF) responde por R$ 43,8 bi na competência casada, contra R$ 26,0 bi "
     "de \"Um fundo\" — sem o salto duplo, metade da exposição fica invisível, "
     "porque RPPS compram FIC e a LF mora um nível abaixo. \"Direta\" é a LF que "
     "o próprio RPPS declarou no DAIR."),
    ("— aba RPPS: datas", "Bases de competências diferentes",
     "A LF é da CDA de maio/2024; a carteira dos RPPS é do último DAIR de cada "
     "um, competência 2026-06 — a API do CADPREV está fora do ar desde 22/09/2026 "
     "e essa é a safra mais recente que o painel tem. São dois anos de distância. "
     "A aba mede por qual fundo um RPPS alcança uma LF, não que ele a tenha "
     "comprado naquele mês. Para um cruzamento de datas casadas, rodar a "
     "ferramenta com a CDA de 2026-06."),
    ("— aba RPPS: Exposicao_RPPS_RS", "Derivado · rateio pelo patrimônio",
     "Não é o valor da LF no fundo: é a parte dela que cabe ao RPPS. Fundo com "
     "R$ 100 de PL, R$ 10 de LF, RPPS com R$ 5 de cotas → exposição R$ 0,50. Com "
     "dois saltos o rateio encadeia os dois patrimônios. Somar o valor da LF no "
     "fundo contaria o fundo inteiro como se fosse do RPPS."),
    ("— aba RPPS: Emissor nas diretas", "Não existe no DAIR",
     "O DAIR traz o texto que o RPPS escreveu — \"LF BRADESCO IPCA\", \"Letra "
     "Financeira Banco Safra\" — e nenhum CNPJ de emissor. As linhas diretas "
     "ficam com o texto em Declarado_no_DAIR e sem CNPJ; deduzir o emissor do "
     "nome seria inventar uma identificação que a fonte não dá."),
    ("Oferta_Publica_Reg", "Não existe — verificado",
     "Letra Financeira não aparece em nenhum dos dois arquivos de ofertas da CVM "
     "(oferta_distribuicao.csv, 48.944 linhas, e oferta_resolucao_160.csv, 14.772). "
     "LF é captação bancária regida por lei própria e registrada na B3/CETIP, não "
     "oferta pública registrada na CVM."),
]


def aba_limites(wb, numeros):
    ws = wb.create_sheet("Fontes e limites")
    ws.column_dimensions["A"].width = 2
    ws["B2"] = "Letras Financeiras — maio/2024"
    ws["B2"].font = Font(name=FONTE, size=15, bold=True, color=TINTA)
    ws["B3"] = ("O que cada coluna do modelo recebeu, de que fonte, e o que não existe "
                "publicamente.")
    ws["B3"].font = Font(name=FONTE, size=10, italic=True, color="595959")

    linha = 5
    ws.cell(row=linha, column=2, value="Os números").font = Font(
        name=FONTE, size=11, bold=True, color=TINTA)
    linha += 1
    for rot, val in numeros:
        ws.cell(row=linha, column=2, value=rot).font = Font(name=FONTE, size=9)
        c = ws.cell(row=linha, column=3, value=val)
        c.font = Font(name=FONTE, size=9, bold=True)
        c.alignment = Alignment(horizontal="left")
        linha += 1

    linha += 1
    aviso = ws.cell(row=linha, column=2, value=(
        "Leitura obrigatória: só 17,5% dos fundos preenchem as colunas de compra e "
        "venda da CDA. Por isso a planilha marca a evidência de cada linha — 499 são "
        "aquisição declarada pelo próprio fundo, e as demais são posições que "
        "apareceram ou cresceram entre 30/04 e 31/05. As duas medidas concordam onde "
        "ambas existem: das 497 aquisições declaradas comparáveis, 474 (95%) também "
        "aparecem como posição nova."))
    aviso.font = Font(name=FONTE, size=9)
    aviso.alignment = Alignment(wrap_text=True, vertical="top")
    aviso.fill = NOTA
    ws.merge_cells(start_row=linha, start_column=2, end_row=linha + 3, end_column=5)
    linha += 5

    ws.cell(row=linha, column=2, value="Coluna do modelo").font = Font(
        name=FONTE, size=9, bold=True, color="FFFFFF")
    ws.cell(row=linha, column=3, value="Fonte").font = Font(
        name=FONTE, size=9, bold=True, color="FFFFFF")
    ws.cell(row=linha, column=4, value="Observação").font = Font(
        name=FONTE, size=9, bold=True, color="FFFFFF")
    for col in (2, 3, 4):
        ws.cell(row=linha, column=col).fill = CAB
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 42
    ws.column_dimensions["D"].width = 86
    linha += 1
    for rot, fonte, obs in LIMITES:
        ws.cell(row=linha, column=2, value=rot).font = Font(name=FONTE, size=9, bold=True)
        ws.cell(row=linha, column=3, value=fonte).font = Font(name=FONTE, size=9)
        c = ws.cell(row=linha, column=4, value=obs)
        c.font = Font(name=FONTE, size=9)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        for col in (2, 3, 4):
            ws.cell(row=linha, column=col).border = BORDA
            ws.cell(row=linha, column=col).alignment = Alignment(
                wrap_text=True, vertical="top")
        ws.row_dimensions[linha].height = 15 * (1 + len(obs) // 95)
        linha += 1
    return ws


def main():
    regs = montar()
    mov = [r for r in regs if r["evidencia"]]
    ordem_ev = {"Aquisição declarada pelo fundo": 0,
                "Posição nova (não existia em 30/04)": 1,
                "Posição aumentada em maio": 2}
    mov.sort(key=lambda r: (ordem_ev[r["evidencia"]],
                            -(r["vl_aquis"] or r["vl_mercado"] or 0)))
    # Ordenada por CNPJ do emissor: e o que torna cada emissor um bloco
    # contiguo, do qual o resumo depende para somar por intervalo.
    regs_ord = sorted(regs, key=lambda r: (r["emissor_cnpj"],
                                           -(r["vl_mercado"] or 0)))

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    wb._named_styles["Normal"].font = Font(name=FONTE, size=9)
    # O openpyxl grava fórmula sem valor em cache. Sem isto, um leitor que só
    # olha o cache — e vários olham — veria as somas vazias. Com isto, a
    # planilha recalcula tudo no instante em que abre.
    wb.calculation.fullCalcOnLoad = True

    ws1 = wb.create_sheet("LFs Negociadas Maio-2024")
    ult1 = escrever(ws1, mov)
    totalizar(ws1, ult1, ["Valor_Adquirido_no_Mes_RS", "Valor_Vendido_no_Mes_RS",
                          "Valor_Mercado_Posicao_RS"])

    ws2 = wb.create_sheet("Posicoes 31-05-2024")
    ult2 = escrever(ws2, regs_ord)
    totalizar(ws2, ult2, ["Valor_Adquirido_no_Mes_RS", "Valor_Vendido_no_Mes_RS",
                          "Valor_Mercado_Posicao_RS"])

    aba_emissores(wb, regs_ord, "Posicoes 31-05-2024")

    # O cruzamento com os RPPS é opcional: depende de baixar o bloco 2 e o
    # patrimônio líquido, e de três arquivos do painel. Sem eles a planilha
    # continua saindo, com uma aba a menos, em vez de falhar inteira.
    try:
        from rpps import carregar, conferir, cruzar, diretas, por_letra
        dados = carregar(BASE, MES)
        import montar as _m
        nomes = _m.nomes_de_emissor(_m.letras(MES))
        indiretas = cruzar(dados, nomes, _m.taxa)
        diretas_ = diretas(dados)
        quantos_rpps = len({l["rpps_cnpj"] for l in indiretas + diretas_})
        # Levanta se algum RPPS ficar com exposição acima da própria carteira,
        # que é o sintoma de rateio errado. Deixar passar daria uma planilha
        # que parece certa.
        conferir(indiretas + diretas_, dados)
        agregado = por_letra(indiretas, diretas_,
                             dados["lf_por_fundo"], nomes, _m.taxa)
        aba_rpps(wb, agregado, COMPETENCIA, (dados["nacional"]["competencias"] or ["?"])[-1])
        print("  exposição de RPPS: %d LF, R$ %.0f, %d RPPS alcançados" % (
            len(agregado), sum(r["exposicao"] for r in agregado), quantos_rpps))
    except Exception as erro:
        print("  aba de RPPS não gerada: %s" % erro)

    aq = sum(1 for r in regs if r["evidencia"] == "Aquisição declarada pelo fundo")
    novas = sum(1 for r in regs if r["evidencia"] == "Posição nova (não existia em 30/04)")
    aum = sum(1 for r in regs if r["evidencia"] == "Posição aumentada em maio")
    aba_limites(wb, [
        ("Competência", "maio/2024 (posição em 31/05/2024)"),
        ("Linhas com movimento em maio", "{:,}".format(len(mov)).replace(",", ".")),
        ("  das quais, aquisição declarada pelo fundo", "{:,}".format(aq).replace(",", ".")),
        ("  posição nova em maio", "{:,}".format(novas).replace(",", ".")),
        ("  posição aumentada em maio", "{:,}".format(aum).replace(",", ".")),
        ("Posições de LF em 31/05/2024", "{:,}".format(len(regs)).replace(",", ".")),
        ("Fundos investidores", "{:,}".format(len({r['fundo_cnpj'] for r in regs})).replace(",", ".")),
        ("Emissores distintos (por CNPJ)", str(len({r["emissor_cnpj"] for r in regs}))),
        ("Valor adquirido declarado em maio",
         "R$ {:,.2f}".format(sum(r["vl_aquis"] or 0 for r in regs)).replace(",", "X").replace(".", ",").replace("X", ".")),
        ("Posição total em 31/05/2024",
         "R$ {:,.2f}".format(sum(r["vl_mercado"] or 0 for r in regs)).replace(",", "X").replace(".", ",").replace("X", ".")),
    ])
    # Primeira aba, sempre: quem abre o arquivo lê os limites antes dos
    # números. O deslocamento tem de ser calculado, não fixo — ele quebrou
    # em silêncio quando a quinta aba entrou.
    wb.move_sheet("Fontes e limites",
                  offset=-wb.sheetnames.index("Fontes e limites"))
    wb.save(SAIDA)
    print("gravado:", SAIDA)
    print("  movimento:", len(mov), "· posições:", len(regs))




COLUNAS_RPPS = [
    ("Via", "via", "texto", 20),
    ("Emissor_Razao_Social", "emissor", "texto", 34),
    ("Emissor_CNPJ", "emissor_cnpj", "cnpj", 19),
    ("Data_Vencimento", "vencimento", "data", 13),
    ("Indexador_Descricao", "indexador", "texto", 26),
    ("Taxa_Contratada", "taxa", "texto", 24),
    ("Declarado_no_DAIR", "declarado_no_dair", "texto", 42),
    ("Valor_da_LF_nos_Fundos_RS", "valor_no_mercado", "din", 20),
    ("Exposicao_RPPS_RS", "exposicao", "din", 19),
    ("Perc_da_LF_em_Maos_de_RPPS", "perc_rpps", "pct", 14),
    ("RPPS_Alcancados", "rpps_alcancados", "int", 12),
    ("Fundos_que_Carregam", "fundos", "int", 12),
    ("Principal_Veiculo", "veiculo", "texto", 46),
    ("Principal_Veiculo_CNPJ", "veiculo_cnpj", "cnpj", 19),
    ("Exposicao_pelo_Principal_Veiculo_RS", "exposicao_pelo_veiculo", "din", 20),
    ("Maior_RPPS", "maior_rpps", "texto", 30),
    ("Maior_RPPS_Exposicao_RS", "maior_exposicao", "din", 19),
]


def aba_rpps(wb, agregado, competencia_cda, competencia_dair):
    """Que LF cada RPPS alcança, direta ou indiretamente.

    Vem depois das outras porque depende de todas: a LF sai da CDA, o RPPS sai
    do painel, e o elo é o CNPJ do fundo.
    """
    ws = wb.create_sheet("RPPS - exposicao a LF")
    aviso = ws.cell(row=1, column=1, value=(
        "ATENÇÃO ÀS DATAS: as Letras Financeiras são da CDA de %s; as carteiras "
        "dos RPPS são do último DAIR de cada um, competência %s. São bases de "
        "datas diferentes, e o que a aba mede é por qual fundo um RPPS alcança "
        "uma LF — não que ele a tenha comprado naquele mês. A exposição é "
        "rateada pelo patrimônio do fundo, nunca somada: se o fundo tem R$ 100 "
        "de PL, R$ 10 de LF e o RPPS tem R$ 5 de cotas, a exposição é R$ 0,50."
        % (competencia_cda, competencia_dair)))
    aviso.font = Font(name=FONTE, size=9, bold=True, color="7F4F00")
    aviso.fill = NOTA
    aviso.alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=1, start_column=1, end_row=3, end_column=9)

    titulos = [c[0] for c in COLUNAS_RPPS]
    for i, t in enumerate(titulos, start=1):
        c = ws.cell(row=5, column=i, value=t)
        c.font = Font(name=FONTE, size=9, bold=True, color="FFFFFF")
        c.fill = CAB
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = COLUNAS_RPPS[i - 1][3]
    ws.row_dimensions[5].height = 30
    ws.freeze_panes = "A6"
    ws.auto_filter.ref = "A5:%s5" % get_column_letter(len(titulos))

    formatos = {"din": DIN, "pct": PCT, "int": "#,##0"}
    for n, r in enumerate(agregado, start=6):
        for i, (_t, campo, tipo, _l) in enumerate(COLUNAS_RPPS, start=1):
            v = r.get(campo)
            if v is None or v == "":
                continue
            if tipo == "cnpj":
                v = cnpj(v)
            c = ws.cell(row=n, column=i, value=v)
            if tipo in formatos:
                c.number_format = formatos[tipo]
    fim = len(agregado) + 5

    linha = fim + 1
    ws.cell(row=linha, column=1, value="TOTAL").font = Font(name=FONTE, size=9, bold=True)
    for titulo in ("Exposicao_RPPS_RS",):
        i = titulos.index(titulo) + 1
        L = get_column_letter(i)
        c = ws.cell(row=linha, column=i, value="=SUM(%s6:%s%d)" % (L, L, fim))
        c.font = Font(name=FONTE, size=9, bold=True)
        c.number_format = DIN

    ws.cell(row=linha + 2, column=1, value=(
        "Três caminhos. \"Direta\": o RPPS declarou a LF na própria carteira do "
        "DAIR — o texto que ele escreveu está em Declarado_no_DAIR, e não há "
        "CNPJ de emissor porque a fonte não o traz. \"Um fundo\": o RPPS tem "
        "cotas de um fundo que tem a LF. \"Dois fundos\": o RPPS tem cotas de um "
        "FIC, o FIC tem cotas de outro fundo, e esse fundo tem a LF — sem este "
        "salto, metade da exposição ficaria invisível.")
    ).font = Font(name=FONTE, size=8, italic=True)
    ws.cell(row=linha + 3, column=1, value=(
        "Fontes: CVM, CDA %s, blocos 5 (letras financeiras), 2 (cotas de fundos) "
        "e o arquivo de patrimônio líquido. Carteiras dos RPPS: painel CADPREV, "
        "ativos-nacional.json e ativos-cotistas.json, DAIR %s."
        % (competencia_cda, competencia_dair))
    ).font = Font(name=FONTE, size=8, italic=True)
    return ws


if __name__ == "__main__":
    main()
