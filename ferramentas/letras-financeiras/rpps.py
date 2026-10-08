# -*- coding: utf-8 -*-
"""Que Letras Financeiras um RPPS alcança, direta ou indiretamente.

Três caminhos, e o segundo é o que importa:

1. **Direta.** O RPPS declara a LF na própria carteira do DAIR, na classe
   "Ativos Renda Fixa com obrigação de IF — Art. 7º VI". Acontece: 85 ativos
   do DAIR dizem "Letra Financeira" ou "LF" no nome.
2. **Um fundo.** O RPPS tem cotas de um fundo, e o fundo tem LF (CDA, bloco 5).
3. **Dois fundos.** O RPPS tem cotas de um FIC, o FIC tem cotas de um fundo, e
   esse fundo tem LF (CDA, bloco 2 para a aresta entre fundos).

Sem o segundo salto, metade da exposição fica invisível: RPPS compram FIC, e a
LF mora um nível abaixo. Medido na competência 2026-06, o salto duplo responde
por R$ 43,8 bi contra R$ 26,0 bi do salto simples.

A exposição é **rateada pelo patrimônio**, não somada: se o fundo tem R$ 100 de
PL, R$ 10 de LF e o RPPS tem R$ 5 de cotas, a exposição do RPPS àquela LF é
R$ 0,50. Somar o valor da LF no fundo contaria o fundo inteiro como se fosse do
RPPS. Com dois saltos o rateio encadeia os dois patrimônios.

**O que isto não é.** Não é "o RPPS comprou esta LF". O RPPS comprou cotas de
um fundo que, na data da declaração, tinha aquela LF em carteira. A decisão de
comprar a LF foi do gestor do fundo. O que a planilha mede é *exposição*, não
autoria.
"""
import csv
import io
import json
import re
import zipfile
from collections import defaultdict

# Uma aspa solta no bloco 2 de 2024-05 faz o parser padrão engolir 171.142
# linhas numa só. Os arquivos da CVM não usam aspas para delimitar campo, então
# tratá-las como texto comum é o que corresponde ao arquivo.
csv.field_size_limit(10 ** 7)
LEITURA = {"delimiter": ";", "quoting": csv.QUOTE_NONE}

PAINEL = "https://gilbertotulli.github.io/dashboard-cadprev/data"
#: Reconhece a LF no texto livre que o RPPS escreveu no DAIR.
LF_NO_TEXTO = re.compile(r"letra\s*financeira|\bLFs?\b|\bLFSN|\bLFSC", re.I)


def digitos(v):
    return re.sub(r"\D", "", v or "")


def num(v):
    try:
        return float((v or "0").replace(",", "."))
    except ValueError:
        return 0.0


def _bloco(base, mes, bloco):
    z = zipfile.ZipFile("%s/cda/cda_%s.zip" % (base, mes))
    with z.open("cda_fi_BLC_%s_%s.csv" % (bloco, mes)) as fh:
        return list(csv.DictReader(
            io.TextIOWrapper(fh, encoding="latin-1", newline=""), **LEITURA))


def _pl(base, mes):
    z = zipfile.ZipFile("%s/cda/cda_%s.zip" % (base, mes))
    with z.open("cda_fi_PL_%s.csv" % mes) as fh:
        linhas = csv.DictReader(
            io.TextIOWrapper(fh, encoding="latin-1", newline=""), **LEITURA)
        return {digitos(l["CNPJ_FUNDO_CLASSE"]): num(l["VL_PATRIM_LIQ"])
                for l in linhas}


def _do_painel(base, nome):
    caminho = "%s/painel/%s" % (base, nome)
    import os
    if not os.path.exists(caminho):
        import urllib.request
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        urllib.request.urlretrieve("%s/%s" % (PAINEL, nome), caminho)
    with open(caminho, encoding="utf-8") as fh:
        return json.load(fh)


def carregar(base, mes):
    """Tudo que o cruzamento precisa, já indexado."""
    nacional = _do_painel(base, "ativos-nacional.json")
    cotistas = _do_painel(base, "ativos-cotistas.json").get("por_ativo", {})
    entes = _do_painel(base, "entes.json")
    entes = entes["entes"] if isinstance(entes, dict) else entes

    lf = [l for l in _bloco(base, mes, "5") if l["TP_ATIVO"] == "Letra Financeira"]
    por_fundo = defaultdict(list)
    for l in lf:
        por_fundo[digitos(l["CNPJ_FUNDO_CLASSE"])].append(l)

    arestas = defaultdict(list)
    for l in _bloco(base, mes, "2"):
        alvo = digitos(l.get("CNPJ_FUNDO_CLASSE_COTA") or "")
        if alvo:
            arestas[digitos(l["CNPJ_FUNDO_CLASSE"])].append(
                (alvo, num(l["VL_MERC_POS_FINAL"]),
                 (l.get("NM_FUNDO_CLASSE_SUBCLASSE_COTA") or "").strip()))

    return {"nacional": nacional, "cotistas": cotistas,
            "nomes": {e["cnpj"]: "%s/%s" % (e["ente"], e["uf"]) for e in entes},
            "lf_por_fundo": por_fundo, "arestas": arestas,
            "pl": _pl(base, mes), "competencia_cda": mes}


def _identidade(l):
    """A LF, do ponto de vista de quem a descreve: emissor, vencimento, taxa."""
    return (digitos(l["CNPJ_EMISSOR"]), l["DT_VENC"], l["CD_INDEXADOR_POSFX"],
            l["PR_INDEXADOR_POSFX"], l["PR_CUPOM_POSFX"], l["PR_TAXA_PREFX"])


def cruzar(dados, nomes_de_emissor, descrever_taxa):
    """Uma linha por (LF × veículo × caminho), com a exposição rateada."""
    nacional, cotistas = dados["nacional"], dados["cotistas"]
    lf_por_fundo, arestas, pl = (dados["lf_por_fundo"], dados["arestas"],
                                 dados["pl"])

    # O que cada RPPS tem em cada fundo, pelo último DAIR de cada um.
    posicao = defaultdict(list)   # cnpj do fundo -> [(cnpj do ente, valor)]
    for item in nacional["itens"]:
        if item.get("tipo_de_identidade") != "cnpj":
            continue
        for c in cotistas.get(item["chave"], []):
            posicao[digitos(item["identificacao"])].append((c["cnpj"], c["valor"]))

    linhas = []

    def emitir(fundo, fracao, caminho, intermediario, nome_intermediario):
        """Emite as LF de `fundo`, com a fração do patrimônio que cabe ao RPPS."""
        patrimonio = pl.get(fundo) or 0.0
        if patrimonio <= 0:
            return 0
        feitas = 0
        agrupado = defaultdict(lambda: {"valor": 0.0, "linha": None})
        for l in lf_por_fundo.get(fundo, []):
            k = _identidade(l)
            agrupado[k]["valor"] += num(l["VL_MERC_POS_FINAL"])
            agrupado[k]["linha"] = l
        for k, d in agrupado.items():
            l = d["linha"]
            parte = d["valor"] / patrimonio
            for ente, valor_no_veiculo in posicao.get(caminho[0], []):
                exposicao = valor_no_veiculo * fracao * parte
                if exposicao < 0.005:
                    continue
                desc, perc_idx, cupom = descrever_taxa(l)
                linhas.append({
                    "via": ("Um fundo" if intermediario is None else "Dois fundos"),
                    "rpps_cnpj": ente,
                    "rpps": dados["nomes"].get(ente, ente),
                    "veiculo_cnpj": caminho[0],
                    "veiculo": _nome_do_fundo(nacional, caminho[0]),
                    "rpps_no_veiculo": valor_no_veiculo,
                    "intermediario_cnpj": intermediario,
                    "intermediario": nome_intermediario,
                    "fundo_com_a_lf_cnpj": fundo,
                    "fundo_com_a_lf": (l["DENOM_SOCIAL"] or "").strip(),
                    "pl_do_fundo": patrimonio,
                    "lf_no_fundo": d["valor"],
                    "perc_lf_no_fundo": parte * 100,
                    "emissor": nomes_de_emissor.get(k[0], l["EMISSOR"].strip()),
                    "emissor_cnpj": k[0],
                    "vencimento": l["DT_VENC"],
                    "indexador": (l["DS_INDEXADOR_POSFX"] or "").strip(),
                    "taxa": desc,
                    "exposicao": exposicao,
                })
                feitas += 1
        return feitas

    for fundo in list(posicao):
        # 1. O próprio fundo que o RPPS declarou tem LF.
        if fundo in lf_por_fundo:
            emitir(fundo, 1.0, (fundo,), None, None)
        # 2. O fundo é FIC: a LF está num fundo em que ele investe. A fração é
        #    a cota que o FIC tem do outro fundo sobre o patrimônio do FIC.
        patrimonio_fic = pl.get(fundo) or 0.0
        if patrimonio_fic <= 0:
            continue
        for alvo, valor_cota, nome_alvo in arestas.get(fundo, []):
            if alvo in lf_por_fundo:
                emitir(alvo, valor_cota / patrimonio_fic, (fundo,), alvo, nome_alvo)
    return linhas


def _nome_do_fundo(nacional, cnpj):
    for item in nacional["itens"]:
        if item.get("tipo_de_identidade") == "cnpj" and \
                digitos(item["identificacao"]) == cnpj:
            return item["nome"]
    return ""


def diretas(dados, nacional=None):
    """As LF que o próprio RPPS declarou no DAIR, sem fundo no meio.

    O DAIR traz o nome que o RPPS escreveu — "LF BRADESCO IPCA", "Letra
    Financeira Banco Safra" — e nenhum CNPJ de emissor. Então aqui não há
    casamento com a CDA: o que a linha diz é o que o RPPS declarou, e o emissor
    fica como texto, não como CNPJ. Dizer o contrário seria inventar uma
    identificação que a fonte não dá.
    """
    nacional = nacional or dados["nacional"]
    saida = []
    for item in nacional["itens"]:
        alvo = (item.get("nome") or "") + " " + (item.get("classe") or "")
        if not LF_NO_TEXTO.search(alvo):
            continue
        if item.get("tipo_de_identidade") == "cnpj":
            continue   # tem CNPJ: é fundo, não LF declarada direto
        for c in dados["cotistas"].get(item["chave"], []):
            saida.append({
                "via": "Direta",
                "rpps_cnpj": c["cnpj"],
                "rpps": dados["nomes"].get(c["cnpj"], c["cnpj"]),
                "veiculo_cnpj": "", "veiculo": "",
                "rpps_no_veiculo": None,
                "intermediario_cnpj": None, "intermediario": None,
                "fundo_com_a_lf_cnpj": "", "fundo_com_a_lf": "",
                "pl_do_fundo": None, "lf_no_fundo": None,
                "perc_lf_no_fundo": None,
                "emissor": "", "emissor_cnpj": "",
                "vencimento": item.get("vencimento") or "",
                "indexador": "", "taxa": "",
                "declarado_pelo_rpps": item.get("nome") or "",
                "classe_no_dair": item.get("classe") or "",
                "exposicao": c["valor"],
            })
    return saida


def por_letra(linhas, diretas_, lf_por_fundo, nomes_de_emissor, descrever_taxa):
    """Uma linha por LF, que é o que a pergunta pede.

    No grão RPPS × LF são 335.922 linhas — a informação está lá, mas ninguém
    lê uma planilha assim. Agregando por LF ficam 2.585, e o que se perde (qual
    RPPS, exatamente) volta nas colunas de maior exposição e de contagem.
    """
    # Quanto de cada LF existe no conjunto dos fundos, para dar denominador à
    # exposição dos RPPS: sem isso "R$ 3 mi de exposição" não diz se é toda a
    # emissão ou uma fatia dela.
    no_mercado = defaultdict(float)
    for linhas_do_fundo in lf_por_fundo.values():
        for l in linhas_do_fundo:
            no_mercado[_identidade(l)] += num(l["VL_MERC_POS_FINAL"])

    por_chave = defaultdict(lambda: {
        "exposicao": 0.0, "rpps": set(), "fundos": set(), "vias": set(),
        "por_veiculo": defaultdict(float), "por_rpps": defaultdict(float)})
    exemplo = {}
    for l in linhas:
        k = (l["emissor_cnpj"], l["vencimento"], l["indexador"], l["taxa"])
        d = por_chave[k]
        d["exposicao"] += l["exposicao"]
        d["rpps"].add(l["rpps_cnpj"])
        d["fundos"].add(l["fundo_com_a_lf_cnpj"])
        d["vias"].add(l["via"])
        d["por_veiculo"][(l["veiculo_cnpj"], l["veiculo"])] += l["exposicao"]
        d["por_rpps"][(l["rpps_cnpj"], l["rpps"])] += l["exposicao"]
        exemplo.setdefault(k, l)

    saida = []
    for k, d in por_chave.items():
        l = exemplo[k]
        veiculo = max(d["por_veiculo"].items(), key=lambda kv: kv[1])
        maior = max(d["por_rpps"].items(), key=lambda kv: kv[1])
        # A identidade da LF no mercado inclui o percentual do indexador, que a
        # chave agregada não carrega; somar pelas quatro partes que a chave tem
        # é o que mantém numerador e denominador falando do mesmo papel.
        total = sum(v for ident, v in no_mercado.items()
                    if ident[0] == k[0] and ident[1] == k[1])
        saida.append({
            "via": " e ".join(sorted(d["vias"])),
            "emissor": l["emissor"], "emissor_cnpj": l["emissor_cnpj"],
            "vencimento": l["vencimento"], "indexador": l["indexador"],
            "taxa": l["taxa"],
            "declarado_no_dair": "",
            "valor_no_mercado": total or None,
            "exposicao": d["exposicao"],
            "perc_rpps": (d["exposicao"] / total * 100) if total else None,
            "rpps_alcancados": len(d["rpps"]),
            "fundos": len(d["fundos"]),
            "veiculo": veiculo[0][1], "veiculo_cnpj": veiculo[0][0],
            "exposicao_pelo_veiculo": veiculo[1],
            "maior_rpps": maior[0][1], "maior_exposicao": maior[1],
        })

    # As diretas entram com o texto que o RPPS escreveu; não têm CNPJ de
    # emissor nem fundo, e misturá-las às indiretas sem marcar isso faria uma
    # linha sem emissor parecer defeito.
    por_declarado = defaultdict(lambda: {"exposicao": 0.0, "rpps": set(),
                                         "por_rpps": defaultdict(float)})
    for l in diretas_:
        d = por_declarado[(l["declarado_pelo_rpps"], l["classe_no_dair"])]
        d["exposicao"] += l["exposicao"]
        d["rpps"].add(l["rpps_cnpj"])
        d["por_rpps"][(l["rpps_cnpj"], l["rpps"])] += l["exposicao"]
    for (texto, classe), d in por_declarado.items():
        maior = max(d["por_rpps"].items(), key=lambda kv: kv[1])
        saida.append({
            "via": "Direta", "emissor": "", "emissor_cnpj": "",
            "vencimento": "", "indexador": "", "taxa": "",
            "declarado_no_dair": texto,
            "valor_no_mercado": None, "exposicao": d["exposicao"],
            "perc_rpps": None, "rpps_alcancados": len(d["rpps"]),
            "fundos": None, "veiculo": "", "veiculo_cnpj": "",
            "exposicao_pelo_veiculo": None,
            "maior_rpps": maior[0][1], "maior_exposicao": maior[1],
        })

    saida.sort(key=lambda r: -r["exposicao"])
    return saida


class ExposicaoImpossivel(AssertionError):
    """A exposição apurada não cabe na carteira do RPPS."""


def conferir(linhas, dados, folga=0.0001):
    """A invariante que pega erro de rateio: exposição ≤ carteira.

    Um rateio errado — somar o valor da LF no fundo em vez da fatia do RPPS,
    ou encadear os patrimônios na ordem trocada — estoura esta conta na hora,
    porque a exposição de um RPPS a um pedaço da carteira não pode passar a
    carteira inteira. Com os dados de 2024-05 sobre o DAIR de 2026-06 a maior
    razão é 20,2% e o conjunto fica em 4,3%.

    Levanta em vez de avisar: uma planilha com exposição impossível é pior que
    planilha nenhuma, porque parece certa.
    """
    carteira = defaultdict(float)
    for item in dados["nacional"]["itens"]:
        for c in dados["cotistas"].get(item["chave"], []):
            carteira[c["cnpj"]] += c["valor"]
    exposto = defaultdict(float)
    for l in linhas:
        exposto[l["rpps_cnpj"]] += l["exposicao"]
    ruins = [(c, exposto[c], carteira.get(c, 0.0))
             for c in exposto if exposto[c] > carteira.get(c, 0.0) * (1 + folga)]
    if ruins:
        c, e, t = max(ruins, key=lambda r: r[1] - r[2])
        raise ExposicaoImpossivel(
            "%d RPPS com exposição a LF acima da própria carteira; o pior é "
            "%s, com R$ %.2f de exposição sobre R$ %.2f de carteira"
            % (len(ruins), c, e, t))
    return {"rpps": len(exposto), "exposicao": sum(exposto.values()),
            "carteira": sum(carteira.values())}
