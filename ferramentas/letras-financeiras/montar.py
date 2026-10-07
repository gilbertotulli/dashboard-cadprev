# -*- coding: utf-8 -*-
"""Letras Financeiras negociadas em maio/2024, a partir dos dados abertos da CVM.

Fontes, todas públicas e baixadas nesta sessão:
  CDA (Composição e Diversificação das Aplicações) 2024-04 e 2024-05, bloco 5,
  que é onde a CVM põe "Depósitos a prazo e outros títulos de IF" — a Letra
  Financeira está aí, e não no bloco de títulos privados.
  Registro de fundos e classes (RCVM 175) e o cadastro antigo, para o gestor.
"""
import csv
import io
import re
import sys
import zipfile
from collections import Counter, defaultdict

BASE = sys.argv[1]
SO_DIGITO = re.compile(r"\D")


def digitos(v):
    return SO_DIGITO.sub("", v or "")


def num(v):
    try:
        return float((v or "0").replace(",", "."))
    except ValueError:
        return 0.0


def ler_zip(caminho, nome):
    z = zipfile.ZipFile(caminho)
    with z.open(nome) as fh:
        texto = io.TextIOWrapper(fh, encoding="latin-1", newline="")
        return list(csv.DictReader(texto, delimiter=";"))


def letras(mes):
    linhas = ler_zip("%s/cda/cda_%s.zip" % (BASE, mes),
                     "cda_fi_BLC_5_%s.csv" % mes)
    return [l for l in linhas if l["TP_ATIVO"] == "Letra Financeira"]


# ---------------------------------------------------------------- gestores
def gestores():
    """CNPJ da classe -> (gestor, administrador).

    Dois cadastros, porque a RCVM 175 partiu o fundo em fundo e classe: o
    registro novo casa a classe com o fundo e o fundo traz o gestor; o cadastro
    antigo cobre o que ainda não migrou. Juntos alcançam 86,8% dos fundos com
    LF; sozinho, o antigo alcança 7,3%.
    """
    z = zipfile.ZipFile("%s/cda/reg.zip" % BASE)

    def ler(nome):
        with z.open(nome) as fh:
            texto = io.TextIOWrapper(fh, encoding="latin-1", newline="")
            return list(csv.DictReader(texto, delimiter=";"))

    por_fundo = {f["ID_Registro_Fundo"]: f for f in ler("registro_fundo.csv")}
    saida = {}
    for c in ler("registro_classe.csv"):
        f = por_fundo.get(c["ID_Registro_Fundo"])
        if f:
            saida[digitos(c["CNPJ_Classe"])] = (
                (f.get("Gestor") or "").strip(),
                (f.get("Administrador") or "").strip())
    with open("%s/cda/cad_fi.csv" % BASE, encoding="latin-1", newline="") as fh:
        for l in csv.DictReader(fh, delimiter=";"):
            k = digitos(l["CNPJ_FUNDO"])
            if k and not saida.get(k, ("",))[0] and (l.get("GESTOR") or "").strip():
                saida[k] = (l["GESTOR"].strip(), (l.get("ADMIN") or "").strip())
    return saida


# ------------------------------------------------------ nome do emissor
#: O que um nome de instituição pode conter. Serve para descartar grafias
#: corrompidas: "BANCO_BRADESCO_SA________" está no arquivo e venceria qualquer
#: critério de comprimento.
LIMPO = re.compile(r"^[A-ZÁÂÃÀÇÉÊÍÓÔÕÚÜ0-9 ./&()'-]+$", re.I)

#: Quanto das ocorrências a grafia escolhida precisa representar. Entre as
#: grafias que somam essa fatia, vence a mais completa.
MAIORIA = 0.6


def nomes_de_emissor(linhas):
    """CNPJ -> grafia consolidada.

    O campo é texto livre e cada fundo escreve como quer. O CNPJ 60.746.948/
    0001-12 aparece como "BRADESCO" (2.467 vezes), "BANCO BRADESCO S.A."
    (2.074), "BANCO BRADESCO" (1.904), "BCO BRADESCO SA" (225) e mais quatro
    grafias. A chave é o CNPJ; esta grafia é derivada e vai numa coluna à
    parte, com a declarada ao lado.

    Nem a mais frequente nem a mais longa servem sozinhas. A mais frequente dá
    "BANCO BTG PACTU", que é um nome cortado em quinze caracteres. A mais longa
    dá "BANCO_BRADESCO_SA________", que é lixo, e "BCO ABC BRASIL SA (EX BCO
    ABC ROMA SA)", que é uma observação, não um nome.

    A regra: ordenar por frequência, tomar as grafias que juntas cobrem 60% das
    ocorrências, e entre elas ficar com a mais completa que passe no teste de
    nome limpo. Isso dá "BANCO BRADESCO S.A.", "BANCO BTG PACTUAL S A" e
    "BANCO ABC BRASIL S.A." — as três conferidas contra o arquivo.
    """
    variantes = defaultdict(Counter)
    for l in linhas:
        nome = " ".join((l["EMISSOR"] or "").split())
        if nome:
            variantes[digitos(l["CNPJ_EMISSOR"])][nome] += 1

    saida = {}
    for cnpj_em, contagem in variantes.items():
        total = sum(contagem.values())
        acumulado, candidatas = 0, []
        for nome, n in contagem.most_common():
            candidatas.append(nome)
            acumulado += n
            if acumulado >= total * MAIORIA:
                break
        limpas = [n for n in candidatas if LIMPO.match(n)] or candidatas
        saida[cnpj_em] = max(limpas, key=lambda n: (len(n), contagem[n]))
    return saida


# ------------------------------------------------------------- a taxa
def taxa(l):
    """A remuneração contratada, como a fonte a declara.

    Pós-fixada vem em duas partes — percentual do índice e cupom — e juntá-las
    num número só perderia a diferença entre "100% do DI" e "DI + 1,15%", que
    são remunerações diferentes. Prefixada vem numa parte só.
    """
    def br(valor, casas=4):
        # Vírgula decimal: a planilha é lida no Brasil e "0.4500%" num campo de
        # texto lê-se como quatro mil e quinhentos avos em qualquer leitura
        # apressada. As colunas numéricas ao lado seguem numéricas.
        return ("%.*f" % (casas, valor)).replace(".", ",")

    if (l["TITULO_POSFX"] or "").strip() == "N":
        pre = num(l["PR_TAXA_PREFX"])
        return ("%s%% a.a. (prefixado)" % br(pre)) if pre else "", None, pre
    indice = (l["DS_INDEXADOR_POSFX"] or "").strip()
    perc = num(l["PR_INDEXADOR_POSFX"])
    cupom = num(l["PR_CUPOM_POSFX"])
    if not indice:
        return "", perc or None, cupom or None
    partes = []
    if perc:
        inteiro = perc == int(perc)
        partes.append("%s%% do %s" % (br(perc, 0 if inteiro else 2),
                                      l["CD_INDEXADOR_POSFX"] or indice))
    if cupom:
        partes.append("+ %s%%" % br(cupom))
    return " ".join(partes) or indice, perc or None, cupom or None


def chave(l):
    """O papel, do ponto de vista de um fundo.

    Não há código do papel nem ISIN no bloco 5 — a CVM só os publica no bloco 4,
    de títulos privados. Então "o mesmo papel" é emissor + vencimento + a
    remuneração contratada, que é o mais perto que a fonte permite chegar.
    """
    return (digitos(l["CNPJ_FUNDO_CLASSE"]), digitos(l["CNPJ_EMISSOR"]),
            l["DT_VENC"], l["CD_INDEXADOR_POSFX"],
            l["PR_INDEXADOR_POSFX"], l["PR_CUPOM_POSFX"], l["PR_TAXA_PREFX"])


def montar():
    abril, maio = letras("202404"), letras("202405")
    gest = gestores()
    nomes = nomes_de_emissor(maio + abril)

    antes = defaultdict(float)
    for l in abril:
        antes[chave(l)] += num(l["QT_POS_FINAL"])

    registros = []
    for l in maio:
        k = chave(l)
        qt = num(l["QT_POS_FINAL"])
        qt_antes = antes.get(k, 0.0)
        vl_aquis = num(l["VL_AQUIS_NEGOC"])
        qt_aquis = num(l["QT_AQUIS_NEGOC"])
        vl_venda = num(l["VL_VENDA_NEGOC"])
        declarou = bool((l["VL_AQUIS_NEGOC"] or "").strip())

        if vl_aquis > 0:
            evidencia = "Aquisição declarada pelo fundo"
        elif qt_antes == 0 and qt > 0:
            evidencia = "Posição nova (não existia em 30/04)"
        elif qt > qt_antes:
            evidencia = "Posição aumentada em maio"
        else:
            evidencia = ""

        desc, perc_idx, cupom = taxa(l)
        cnpj_em = digitos(l["CNPJ_EMISSOR"])
        g, a = gest.get(digitos(l["CNPJ_FUNDO_CLASSE"]), ("", ""))
        registros.append({
            "evidencia": evidencia,
            "declarou_negociacao": "sim" if declarou else "não",
            "competencia": l["DT_COMPTC"],
            "vencimento": l["DT_VENC"],
            "instrumento": l["TP_ATIVO"],
            "emissor": nomes.get(cnpj_em, l["EMISSOR"]),
            "emissor_declarado": (l["EMISSOR"] or "").strip(),
            "emissor_cnpj": cnpj_em,
            "emissor_ligado": "sim" if l["EMISSOR_LIGADO"] == "S" else "não",
            "indexador": (l["DS_INDEXADOR_POSFX"] or "").strip(),
            "taxa": desc,
            "perc_indexador": perc_idx,
            "cupom": cupom,
            "taxa_prefixada": num(l["PR_TAXA_PREFX"]) or None,
            "qt_aquis": qt_aquis or None,
            "vl_aquis": vl_aquis or None,
            "vl_venda": vl_venda or None,
            "qt_final": qt or None,
            "qt_variacao": round(qt - qt_antes, 6) or None,
            "vl_mercado": num(l["VL_MERC_POS_FINAL"]) or None,
            "fundo": (l["DENOM_SOCIAL"] or "").strip(),
            "fundo_cnpj": digitos(l["CNPJ_FUNDO_CLASSE"]),
            "fundo_tipo": l["TP_FUNDO_CLASSE"],
            "gestor": g,
            "administrador": a,
            "classificacao_negoc": l["TP_NEGOC"],
            "agencia_risco": (l["AG_RISCO"] or "").strip(),
            "grau_risco": (l["GRAU_RISCO"] or "").strip(),
        })
    return registros


if __name__ == "__main__":
    regs = montar()
    mov = [r for r in regs if r["evidencia"]]
    print("posições em 31/05/2024:", len(regs))
    print("com movimento em maio :", len(mov))
    print(Counter(r["evidencia"] for r in mov).most_common())
