# -*- coding: utf-8 -*-
"""Pontos a verificar nas LF que os RPPS compraram direto.

**O que esta ferramenta não faz, e por quê.** A pergunta natural — "esta LF foi
comprada a uma taxa fora do mercado?" — não tem resposta nos dados públicos, e
a razão é dupla:

1. **O DAIR não traz taxa.** São dezesseis campos, e nenhum é remuneração:
   nome do ativo em texto livre, quantidade, valor unitário de hoje, valor
   total, patrimônio, percentuais e o teto da classe. Sem taxa contratada não
   há o que comparar.
2. **A CDA traz taxa, mas não serve de referência para um papel.** Ela não
   publica ISIN nem código do papel das LF, e não separa sênior de subordinada.
   Agrupando por emissor e vencimento — o mais fino que a fonte permite —, em
   30% dos grupos o maior cupom é o dobro do menor e em 6% é cinco vezes, com
   grupos indo de 0,41% a 1,40% sobre o DI e de 2,6% a 26,9%. A data 2050-12-31
   aparece 637 vezes, marcando papel perpétuo. São papéis diferentes sob o
   mesmo rótulo: apontar "fora da média" aí produziria acusação a partir de
   ruído.

O que sobra é verificável e não depende de taxa: **concentração** medida contra
o teto que a própria fonte declara, e **qualidade da declaração**. Nenhum sinal
aqui é irregularidade. São pontos que justificam olhar o papel — e só isso.
"""
import json
import os
import re
from collections import defaultdict

LF_NO_TEXTO = re.compile(r"letra\s*financeira|\bLFs?\b|\bLFSN|\bLFSC", re.I)

#: Um nome que começa no meio da palavra é declaração truncada: "nvest em
#: Letra Financeira da CEF", "quisiçao LF SENIOR", "tivos Finan Emit por Inst".
#: Importa para fiscalização: não se confere o que não se identifica.
TRUNCADO = re.compile(r"^[a-z]{1,4}(?=[a-z]*\s)", re.U)

#: Bancos que os RPPS nomeiam nas declarações. Serve só para dizer se o texto
#: permite reconhecer o emissor — não para afirmar qual é.
NOMEIA_BANCO = re.compile(
    r"bradesco|ita[uú]|santander|safra|btg|daycoval|banco do brasil|\bbb\b|"
    r"caixa|\bcef\b|votorantim|\babc\b|pine|sofisa|inter|xp|pan|bmg|"
    r"original|fibra|paran[aá]|rci|nu\s*financeira|c6|master|banrisul", re.I)

#: Acima disto, um único papel pesa o bastante na carteira para justificar
#: conferência. Não é limite normativo: a norma limita a classe, não o papel.
CONCENTRACAO_DE_ATENCAO = 5.0


def _carteira_do_ente(pasta, cnpj):
    caminho = os.path.join(pasta, "ente", "%s-carteira.json" % cnpj)
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as fh:
        d = json.load(fh)
    comp = (d.get("competencias") or [None])[0]
    return comp


def levantar(pasta):
    """Uma linha por (RPPS × LF declarada direto), com os sinais objetivos."""
    with open(os.path.join(pasta, "ativos-nacional.json"), encoding="utf-8") as fh:
        nacional = json.load(fh)
    with open(os.path.join(pasta, "ativos-cotistas.json"), encoding="utf-8") as fh:
        cotistas = json.load(fh)["por_ativo"]
    with open(os.path.join(pasta, "entes.json"), encoding="utf-8") as fh:
        entes = json.load(fh)
    entes = entes["entes"] if isinstance(entes, dict) else entes
    quem = {e["cnpj"]: e for e in entes}

    diretas = [i for i in nacional["itens"]
               if i.get("tipo_de_identidade") != "cnpj"
               and LF_NO_TEXTO.search((i.get("nome") or "") + " " +
                                      (i.get("classe") or ""))]

    carteira = defaultdict(float)
    for item in nacional["itens"]:
        for c in cotistas.get(item["chave"], []):
            carteira[c["cnpj"]] += c["valor"]

    somado = defaultdict(float)
    for i in diretas:
        for c in cotistas.get(i["chave"], []):
            somado[c["cnpj"]] += c["valor"]

    linhas = []
    for i in diretas:
        nome = (i.get("nome") or "").strip()
        for c in cotistas.get(i["chave"], []):
            cnpj = c["cnpj"]
            total = carteira.get(cnpj) or 0.0
            comp = _carteira_do_ente(pasta, cnpj) or {}
            classe = i.get("classe") or ""
            da_classe = next((x for x in comp.get("classes", [])
                              if x.get("rotulo") == classe), {})
            perc = (c["valor"] / total * 100) if total else None
            perc_lf = (somado[cnpj] / total * 100) if total else None

            sinais = []
            if da_classe.get("excede"):
                sinais.append("classe acima do teto da norma")
            if perc is not None and perc >= CONCENTRACAO_DE_ATENCAO:
                sinais.append("um papel com %.1f%% da carteira" % perc)
            if TRUNCADO.match(nome):
                sinais.append("declaração truncada")
            if not NOMEIA_BANCO.search(nome):
                sinais.append("texto não nomeia o emissor")

            linhas.append({
                "sinais": len(sinais),
                "o_que_olhar": "; ".join(sinais),
                "rpps": "%s/%s" % (quem.get(cnpj, {}).get("ente", cnpj),
                                   quem.get(cnpj, {}).get("uf", "")),
                "rpps_cnpj": cnpj,
                "declarado_no_dair": nome,
                "valor": c["valor"],
                "perc_da_carteira": perc,
                "carteira_do_rpps": total or None,
                "total_em_lf_direta": somado[cnpj],
                "perc_em_lf_direta": perc_lf,
                "classe_no_dair": classe,
                "perc_da_classe": da_classe.get("perc"),
                "teto_da_classe": da_classe.get("limite"),
                "excede_o_teto": ("sim" if da_classe.get("excede") else
                                  ("não" if da_classe else "")),
                "folga_ate_o_teto": da_classe.get("folga"),
                "competencia": comp.get("competencia", ""),
            })
    linhas.sort(key=lambda l: (-l["sinais"], -(l["perc_da_carteira"] or 0)))
    return linhas
