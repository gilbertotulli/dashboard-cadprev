"""Agregação: do banco local para os JSON que o painel lê.

O painel é estático — HTML, CSS e JavaScript, sem servidor. Quem serve os
números é este módulo, que pré-agrega tudo na ingestão. É a única escolha
compatível com a API: 100 a 170 mil linhas por competência não podem ser
somadas no navegador a cada clique, e a API não deve ser consultada ao vivo.

Cada arquivo gerado carrega a própria procedência: competência, quando foi
ingerido, e quantos RPPS ficaram de fora. Um total sem o denominador ao lado é
um número que engana.
"""

import json
import os
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from . import fundos, grupos
from .store import Store

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_SAIDA = os.path.join(RAIZ, "web", "data")

#: Segmento que a fonte traz junto dos demais mas que não é alocação de
#: investimento. Entra no total de recursos e sai da leitura de enquadramento.
SEGMENTO_DISPONIBILIDADES = "disponibilidades financeiras"


def _hoje() -> str:
    return date.today().isoformat()


def _gravar(nome: str, conteudo: Any, dir_saida: str = DIR_SAIDA) -> str:
    os.makedirs(dir_saida, exist_ok=True)
    caminho = os.path.join(dir_saida, nome)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(conteudo, fh, ensure_ascii=False, separators=(",", ":"))
    return caminho


def _pct(parte: float, total: float) -> float:
    return round(parte / total * 100, 2) if total else 0.0


# ---------------------------------------------------------------------------
# Índice de entes
# ---------------------------------------------------------------------------

def montar_entes(store: Store) -> Dict[str, Dict[str, Any]]:
    """Índice de RPPS, com os grupos já resolvidos.

    A união é feita sobre todas as tabelas ingeridas porque nenhuma delas é
    garantidamente completa: um RPPS pode aparecer no CRP e não no DAIR, ou o
    contrário, e sumir do índice por isso seria perder o ente.
    """
    entes: Dict[str, Dict[str, Any]] = {}
    for tabela in store.tabelas():
        if tabela == "execucao":
            continue
        try:
            linhas = store.consultar(
                "SELECT DISTINCT cnpj_ente, ente, uf FROM {}".format(tabela))
        except Exception:  # tabela sem as colunas de identificação
            continue
        for linha in linhas:
            cnpj = linha["cnpj_ente"]
            if not cnpj or cnpj in entes:
                continue
            registro = {"cnpj": cnpj, "ente": linha["ente"]}
            registro.update(grupos.classificar(linha["uf"], linha["ente"]))
            entes[cnpj] = registro
    return entes


# ---------------------------------------------------------------------------
# Aba 1 — Panorama
# ---------------------------------------------------------------------------

def montar_panorama(store: Store, entes: Mapping[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Situação do CRP por região, com os extremos de atraso."""
    if not store.tem_tabela("RPPS_CRP"):
        return {"disponivel": False}

    hoje = _hoje()
    linhas = store.consultar(
        "SELECT cnpj_ente, ente, uf, validade, judicial, situacao FROM rpps_crp")

    por_regiao: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"valido": 0, "judicial": 0, "vencido": 0})
    vencidos: List[Dict[str, Any]] = []
    total = valido = judicial = 0

    for linha in linhas:
        ente = entes.get(linha["cnpj_ente"], {})
        regiao = ente.get("regiao") or "Não classificado"
        esta_valido = bool(linha["validade"] and linha["validade"] >= hoje)
        if linha["situacao"]:
            # "VÁLIDO" e "VENCIDO" começam com a mesma letra: comparar o termo
            # inteiro, sem acento. Um prefixo aqui contaria todo CRP vencido
            # como regular.
            esta_valido = _normalizar_situacao(linha["situacao"]) == "valido"

        total += 1
        if linha["judicial"]:
            por_regiao[regiao]["judicial"] += 1
            judicial += 1
        elif esta_valido:
            por_regiao[regiao]["valido"] += 1
        else:
            por_regiao[regiao]["vencido"] += 1
        if esta_valido:
            valido += 1
        else:
            vencidos.append({
                "cnpj": linha["cnpj_ente"], "ente": linha["ente"],
                "uf": linha["uf"],
                "dias": _dias_desde(linha["validade"], hoje),
            })

    vencidos = [v for v in vencidos if v["dias"] is not None]
    vencidos.sort(key=lambda v: v["dias"], reverse=True)

    return {
        "disponivel": True,
        "referencia": hoje,
        "kpis": {
            "entes": total,
            "perc_valido": _pct(valido, total),
            "judicial": judicial,
            "perc_judicial": _pct(judicial, total),
        },
        "por_regiao": [
            dict(regiao=r, **por_regiao[r])
            for r in grupos.ORDEM_REGIOES if r in por_regiao
        ] + [dict(regiao=r, **v) for r, v in por_regiao.items()
             if r not in grupos.ORDEM_REGIOES],
        "vencidos_ha_mais_tempo": vencidos[:10],
    }


def _normalizar_situacao(texto: str) -> str:
    """Reduz a situação do CRP à forma comparável, sem acento."""
    decomposto = unicodedata.normalize("NFKD", texto.strip().lower())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _dias_desde(validade: Optional[str], hoje: str) -> Optional[int]:
    if not validade:
        return None
    try:
        return max(0, (date.fromisoformat(hoje) - date.fromisoformat(validade)).days)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Aba 4 — Carteira, visão nacional
# ---------------------------------------------------------------------------

def montar_carteira_nacional(store: Store,
                             entes: Mapping[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Agregado nacional da carteira, com os recortes por grupo.

    Os dois rankings usam regras diferentes de propósito. O dos maiores é
    trivial. O dos menores precisa excluir quem declarou zero — e quem não
    declarou já está fora por não ter linha. Sem essa regra, o topo da lista
    dos menores seria composto de declarações vazias.
    """
    if not store.tem_tabela("DAIR_CARTEIRA"):
        return {"disponivel": False}

    execucao = store.ultima_execucao("DAIR_CARTEIRA") or {}
    nivel = execucao.get("nivel") or fundos.NIVEL_B

    segregacao = _mapa_segregacao(store)
    linhas = [dict(linha) for linha in store.consultar(
        "SELECT cnpj_ente, segmento, valor_total, limite_cmn, plano "
        "FROM dair_carteira" if _tem_coluna(store, "dair_carteira", "plano")
        else "SELECT cnpj_ente, segmento, valor_total, limite_cmn FROM dair_carteira")]

    total = sum(linha.get("valor_total") or 0.0 for linha in linhas)

    por_fundo = fundos.agregar(linhas, nivel, segregacao)
    por_segmento: Dict[str, float] = defaultdict(float)
    por_esfera: Dict[str, float] = defaultdict(float)
    por_regiao: Dict[str, float] = defaultdict(float)
    por_ente: Dict[str, float] = defaultdict(float)

    for linha in linhas:
        valor = linha.get("valor_total") or 0.0
        por_segmento[(linha.get("segmento") or "Não informado").strip()] += valor
        por_ente[linha["cnpj_ente"]] += valor
        ente = entes.get(linha["cnpj_ente"], {})
        por_esfera[ente.get("esfera") or "municipal"] += valor
        por_regiao[ente.get("regiao") or "Não classificado"] += valor

    def _nomear(cnpj: str) -> Dict[str, Any]:
        ente = entes.get(cnpj, {})
        return {"cnpj": cnpj, "ente": ente.get("ente") or cnpj,
                "uf": ente.get("uf"), "valor": round(por_ente[cnpj], 2)}

    ordenados = sorted(por_ente, key=lambda c: por_ente[c], reverse=True)
    com_valor = [c for c in ordenados if por_ente[c] > 0]

    return {
        "disponivel": True,
        "nivel": nivel,
        "nivel_descricao": fundos.descrever_nivel(nivel),
        "competencia": (execucao.get("filtros") and
                        json.loads(execucao["filtros"])) or {},
        "total": round(total, 2),
        "rpps_com_dair": len(por_ente),
        "por_fundo": [
            {"categoria": categoria, "rotulo": fundos.ROTULOS.get(categoria, categoria),
             "valor": round(valor, 2), "perc": _pct(valor, total)}
            for categoria, valor in sorted(por_fundo.items(),
                                           key=lambda kv: kv[1], reverse=True)
        ],
        "por_segmento": _ranquear(por_segmento, total),
        "por_esfera": [
            {"chave": chave, "rotulo": grupos.ROTULOS_ESFERA.get(chave, chave),
             "valor": round(valor, 2), "perc": _pct(valor, total)}
            for chave, valor in sorted(por_esfera.items(),
                                       key=lambda kv: kv[1], reverse=True)
        ],
        "por_regiao": _ranquear(por_regiao, total),
        "maiores": [_nomear(c) for c in ordenados[:5]],
        "menores": [_nomear(c) for c in list(reversed(com_valor))[:5]],
        "excluidos_do_ranking_menores": len(ordenados) - len(com_valor),
        "regra_menores": ("Entre os RPPS que enviaram DAIR na competência e "
                          "declararam patrimônio maior que zero."),
    }


def _ranquear(mapa: Mapping[str, float], total: float) -> List[Dict[str, Any]]:
    return [{"rotulo": chave, "valor": round(valor, 2), "perc": _pct(valor, total)}
            for chave, valor in sorted(mapa.items(), key=lambda kv: kv[1], reverse=True)]


def _tem_coluna(store: Store, tabela: str, coluna: str) -> bool:
    linhas = store.consultar("PRAGMA table_info({})".format(tabela))
    return any(linha[1] == coluna for linha in linhas)


def _mapa_segregacao(store: Store) -> Dict[str, Optional[bool]]:
    """Quem segregou a massa — insumo do Nível B."""
    if not store.tem_tabela("DRAA_SEGREGACAO_MASSA"):
        return {}
    linhas = store.consultar(
        "SELECT cnpj_ente, possui_segregacao FROM draa_segregacao_massa")
    return {linha["cnpj_ente"]: (None if linha["possui_segregacao"] is None
                                 else bool(linha["possui_segregacao"]))
            for linha in linhas}


# ---------------------------------------------------------------------------
# Abas 2, 3, 4 e 5 — um arquivo por RPPS
# ---------------------------------------------------------------------------

def montar_ente(store: Store, cnpj: str, ente: Mapping[str, Any]) -> Dict[str, Any]:
    """Tudo que o painel mostra sobre um RPPS, num arquivo só.

    Um arquivo por ente, e não um endpoint por clique: cada ficha tem alguns
    poucos KB e o navegador busca exatamente um deles.
    """
    ficha: Dict[str, Any] = dict(ente)

    ficha["crp"] = _um(store, "rpps_crp",
                       "numero_crp, emissao, validade, judicial, situacao", cnpj)
    ficha["aliquotas"] = _varios(
        store, "rpps_aliquota",
        "plano, sujeito_passivo, aliquota, inicio_vigencia, fim_vigencia", cnpj,
        ordem="inicio_vigencia DESC")
    ficha["estatistica"] = _um(
        store, "draa_estatistica",
        "exercicio, ativos, aposentados, pensionistas, dependentes", cnpj,
        ordem="exercicio DESC")
    ficha["segregacao"] = _um(
        store, "draa_segregacao_massa",
        "exercicio, possui_segregacao, data_segregacao", cnpj,
        ordem="exercicio DESC")

    ficha["caixa"] = _montar_caixa(store, cnpj)
    ficha["carteira"] = _montar_carteira_ente(store, cnpj)
    ficha["atuaria"] = _montar_atuaria(store, cnpj)
    return ficha


def _um(store: Store, tabela: str, colunas: str, cnpj: str,
        ordem: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not store.tem_tabela(tabela.upper()):
        return None
    sql = "SELECT {} FROM {} WHERE cnpj_ente = ?".format(colunas, tabela)
    if ordem:
        sql += " ORDER BY " + ordem
    linhas = store.consultar(sql + " LIMIT 1", (cnpj,))
    return dict(linhas[0]) if linhas else None


def _varios(store: Store, tabela: str, colunas: str, cnpj: str,
            ordem: Optional[str] = None, limite: int = 200) -> List[Dict[str, Any]]:
    if not store.tem_tabela(tabela.upper()):
        return []
    sql = "SELECT {} FROM {} WHERE cnpj_ente = ?".format(colunas, tabela)
    if ordem:
        sql += " ORDER BY " + ordem
    return [dict(linha) for linha in
            store.consultar(sql + " LIMIT {}".format(limite), (cnpj,))]


def _montar_caixa(store: Store, cnpj: str) -> Dict[str, Any]:
    """Série mensal de ingressos e dispêndios, na mesma unidade e escala."""
    linhas = _varios(store, "dipr",
                     "ano, mes, plano, total_receita, total_despesa, resultado,"
                     " nb_aposentados, nb_pensionistas, nb_servidores", cnpj,
                     ordem="ano, mes")
    if not linhas:
        return {"disponivel": False}

    serie = []
    for linha in linhas:
        receita = linha.get("total_receita") or 0.0
        despesa = linha.get("total_despesa") or 0.0
        resultado = linha.get("resultado")
        serie.append({
            "ano": linha.get("ano"), "mes": linha.get("mes"),
            "plano": linha.get("plano"),
            "receita": round(receita, 2), "despesa": round(despesa, 2),
            # O resultado é derivado quando a API não o traz, e nunca
            # sobrescreve o valor declarado.
            "resultado": round(resultado if resultado is not None
                               else receita - despesa, 2),
        })
    ultimo = linhas[-1]
    return {
        "disponivel": True,
        "serie": serie,
        "total_receita": round(sum(p["receita"] for p in serie), 2),
        "total_despesa": round(sum(p["despesa"] for p in serie), 2),
        "resultado": round(sum(p["resultado"] for p in serie), 2),
        "beneficiarios": (ultimo.get("nb_aposentados") or 0)
                         + (ultimo.get("nb_pensionistas") or 0),
        "servidores": ultimo.get("nb_servidores"),
    }


def _montar_carteira_ente(store: Store, cnpj: str) -> Dict[str, Any]:
    """Alocação por segmento contra o limite legal, e as maiores posições."""
    colunas = ("segmento, tipo_ativo, nome_ativo, limite_cmn, valor_total,"
               " perc_recursos, pl_fundo, perc_pl_fundo")
    linhas = _varios(store, "dair_carteira", colunas, cnpj,
                     ordem="valor_total DESC", limite=5000)
    if not linhas:
        return {"disponivel": False}

    total = sum(linha.get("valor_total") or 0.0 for linha in linhas)
    por_segmento: Dict[str, Dict[str, Any]] = {}
    for linha in linhas:
        nome = (linha.get("segmento") or "Não informado").strip()
        alvo = por_segmento.setdefault(nome, {"rotulo": nome, "valor": 0.0,
                                              "limite": linha.get("limite_cmn")})
        alvo["valor"] += linha.get("valor_total") or 0.0
        if alvo["limite"] is None:
            alvo["limite"] = linha.get("limite_cmn")

    segmentos = []
    for dados in sorted(por_segmento.values(), key=lambda s: s["valor"], reverse=True):
        perc = _pct(dados["valor"], total)
        segmentos.append({
            "rotulo": dados["rotulo"], "valor": round(dados["valor"], 2),
            "perc": perc, "limite": dados["limite"],
            "excede": bool(dados["limite"] and perc > dados["limite"]),
            "alocacao": dados["rotulo"].strip().lower() != SEGMENTO_DISPONIBILIDADES,
        })

    posicoes = [{
        "nome": linha.get("nome_ativo") or linha.get("tipo_ativo") or "—",
        "segmento": linha.get("segmento"),
        "valor": round(linha.get("valor_total") or 0.0, 2),
        "perc_carteira": _pct(linha.get("valor_total") or 0.0, total),
        "perc_pl_fundo": linha.get("perc_pl_fundo"),
    } for linha in linhas[:10]]

    concentrados = [p for p in posicoes if (p["perc_pl_fundo"] or 0) > 10]
    return {
        "disponivel": True,
        "total": round(total, 2),
        "ativos": len(linhas),
        "segmentos": segmentos,
        "posicoes": posicoes,
        "fora_do_limite": sum(1 for s in segmentos if s["excede"]),
        "concentracao_pl": len(concentrados),
        "maior_posicao": posicoes[0]["perc_carteira"] if posicoes else 0.0,
    }


def _montar_atuaria(store: Store, cnpj: str) -> Dict[str, Any]:
    """Fluxo projetado, compromissos, custeio e as hipóteses que os sustentam."""
    fluxo = _varios(store, "draa_fluxo_atuarial",
                    "ano_projecao, receitas, despesas, saldo", cnpj,
                    ordem="ano_projecao", limite=200)
    compromissos = _varios(store, "draa_valores_compromissos",
                           "descricao, geracao_atual, geracao_futura", cnpj,
                           limite=60)
    hipoteses = _varios(store, "draa_hipotese_atuarial",
                        "descricao, valor", cnpj, limite=40)
    custeio = _um(store, "draa_plano_custeio",
                  "custo_normal, custo_suplementar", cnpj, ordem="exercicio DESC")

    if not (fluxo or compromissos or hipoteses or custeio):
        return {"disponivel": False}

    return {
        "disponivel": True,
        "fluxo": fluxo,
        "cruzamento": _ano_de_cruzamento(fluxo),
        "compromissos": compromissos,
        "hipoteses": hipoteses,
        "custeio": custeio,
    }


def _ano_de_cruzamento(fluxo: List[Dict[str, Any]]) -> Optional[int]:
    """Primeiro ano em que as despesas projetadas superam as receitas.

    É o número que o conselho fiscal procura primeiro, e ele não vem pronto da
    API — sai da leitura da série.
    """
    for ponto in fluxo:
        receitas, despesas = ponto.get("receitas"), ponto.get("despesas")
        if receitas is not None and despesas is not None and despesas > receitas:
            return ponto.get("ano_projecao")
    return None


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------

def construir(store: Store, dir_saida: str = DIR_SAIDA,
              origem: str = "api", limite_entes: Optional[int] = None
              ) -> Dict[str, Any]:
    """Gera todos os arquivos que o painel consome.

    Args:
        origem: ``api`` para dados reais, ``demonstracao`` para o conjunto
            sintético. A interface mostra um aviso permanente quando não é
            ``api`` — um painel de dados públicos não pode deixar dúvida
            sobre o que está na tela.
    """
    entes = montar_entes(store)
    panorama = montar_panorama(store, entes)
    carteira = montar_carteira_nacional(store, entes)

    gerados = [
        _gravar("panorama.json", panorama, dir_saida),
        _gravar("carteira-nacional.json", carteira, dir_saida),
    ]

    indice = sorted(
        ({"cnpj": dados["cnpj"], "ente": dados["ente"], "uf": dados["uf"],
          "esfera": dados["esfera"], "regiao": dados["regiao"]}
         for dados in entes.values()),
        key=lambda d: (d["uf"] or "", d["ente"] or ""))
    gerados.append(_gravar("entes.json", indice, dir_saida))

    escolhidos = list(entes.items())[:limite_entes] if limite_entes else entes.items()
    for cnpj, dados in escolhidos:
        _gravar(os.path.join("ente", cnpj + ".json"),
                montar_ente(store, cnpj, dados), dir_saida)

    meta = {
        "origem": origem,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entes": len(entes),
        "fichas": len(list(escolhidos)),
        "nivel_fundo": carteira.get("nivel"),
        "capitais_conhecidas": grupos.cobertura_capitais(),
        "execucoes": store.resumo(),
    }
    gerados.append(_gravar("meta.json", meta, dir_saida))
    return {"arquivos": len(gerados) + len(list(escolhidos)), "meta": meta}
