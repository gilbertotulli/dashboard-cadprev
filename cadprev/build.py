"""Agregação: do banco local para os JSON que o painel lê.

O painel é estático — HTML, CSS e JavaScript, sem servidor. Quem serve os
números é este módulo, que pré-agrega tudo na ingestão. É a única escolha
compatível com a API: 100 a 170 mil linhas por competência não podem ser
somadas no navegador a cada clique, e a API não deve ser consultada ao vivo.

Cada arquivo gerado carrega a própria procedência: competência, quando foi
ingerido, e quantos RPPS ficaram de fora. Um total sem o denominador ao lado é
um número que engana.

Formato longo
-------------
A maior parte do trabalho aqui é converter formato longo em leitura. O DIPR vem
com uma linha por rubrica, o DRAA com uma linha por item de demonstrativo, e o
CRP com o histórico inteiro em vez da posição atual. Nenhum desses totais existe
como campo na API: todos saem de agregação, com o critério nomeado em
``codigos.py``.
"""

import json
import os
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from . import benchmark, codigos, fundos, grupos
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
    """Situação do CRP por região, com os extremos de atraso.

    O endpoint devolve o **histórico** de certificados, não a posição atual: um
    ente com vinte anos de RPPS tem dezenas de linhas. A posição de hoje é a
    emissão mais recente de cada ente — somar as linhas cruas contaria cada
    renovação como se fosse um RPPS diferente.
    """
    if not store.tem_tabela("RPPS_CRP"):
        return {"disponivel": False}

    hoje = _hoje()
    # Uma linha por ente: a de emissão mais recente. O desempate por número do
    # CRP cobre o caso de duas emissões no mesmo dia.
    linhas = store.consultar("""
        SELECT c.cnpj_ente, c.ente, c.uf, c.validade, c.campo_situacao, c.campo_tipo
          FROM rpps_crp c
          JOIN (SELECT cnpj_ente, MAX(COALESCE(emissao, '') || '|' ||
                       COALESCE(numero_crp, '')) AS marca
                  FROM rpps_crp GROUP BY cnpj_ente) u
            ON u.cnpj_ente = c.cnpj_ente
           AND u.marca = COALESCE(c.emissao, '') || '|' || COALESCE(c.numero_crp, '')
         GROUP BY c.cnpj_ente
    """)

    por_regiao: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"valido": 0, "judicial": 0, "vencido": 0})
    vencidos: List[Dict[str, Any]] = []
    total = valido = judicial = 0

    for linha in linhas:
        ente = entes.get(linha["cnpj_ente"], {})
        regiao = ente.get("regiao") or "Não classificado"
        leitura = _ler_crp(linha["campo_situacao"], linha["campo_tipo"],
                           linha["validade"], hoje)
        esta_valido, e_judicial = leitura["valido"], leitura["judicial"]

        total += 1
        if e_judicial:
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
                "uf": linha["uf"], "dias": _dias_desde(linha["validade"], hoje),
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
            "vencidos": total - valido,
        },
        "por_regiao": [
            dict(regiao=r, **por_regiao[r])
            for r in grupos.ORDEM_REGIOES if r in por_regiao
        ] + [dict(regiao=r, **v) for r, v in por_regiao.items()
             if r not in grupos.ORDEM_REGIOES],
        "vencidos_ha_mais_tempo": vencidos[:10],
    }


#: Como cada estado do CRP aparece na fonte, já sem acento.
_CRP_VIGENTE = {"valido", "vigente"}
_CRP_VENCIDO = {"vencido"}
_CRP_JUDICIAL = {"judicial"}
_CRP_ADMINISTRATIVO = {"administrativo"}


def _ler_crp(campo_situacao: Optional[str], campo_tipo: Optional[str],
             validade: Optional[str], hoje: str) -> Dict[str, bool]:
    """Lê situação e forma de emissão do CRP sem depender de qual campo é qual.

    A API e a sua documentação discordam: o Swagger descreve ``ds_situacao``
    como "Vigente ou Vencido" e ``tp_crp`` como "Administrativo ou Judicial",
    mas as respostas reais devolvem o contrário. Em vez de apostar num dos
    dois, cada campo é classificado pelo valor que carrega. Continua correto se
    a inversão for corrigida, e continua correto hoje.

    Comparar o termo inteiro, sem acento, importa: "VÁLIDO" e "VENCIDO" começam
    com a mesma letra, e um prefixo contaria todo certificado vencido como
    regular.
    """
    valido = judicial = None
    for bruto in (campo_situacao, campo_tipo):
        termo = _normalizar_situacao(bruto)
        if termo in _CRP_VIGENTE:
            valido = True
        elif termo in _CRP_VENCIDO:
            valido = False
        elif termo in _CRP_JUDICIAL:
            judicial = True
        elif termo in _CRP_ADMINISTRATIVO:
            judicial = False

    if valido is None:  # nenhum dos campos declarou: cai para a data
        valido = bool(validade and validade >= hoje)
    return {"valido": valido, "judicial": bool(judicial)}


def _normalizar_situacao(texto: Optional[str]) -> str:
    """Reduz um rótulo da fonte à forma comparável, sem acento."""
    decomposto = unicodedata.normalize("NFKD", str(texto or "").strip().lower())
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
        "SELECT cnpj_ente, segregacao FROM draa_segregacao_massa")
    mapa: Dict[str, Optional[bool]] = {}
    for linha in linhas:
        tem = fundos.possui_segregacao(linha["segregacao"])
        # Um RPPS aparece uma vez por plano. Basta um "possui" para que a
        # carteira não possa ser atribuída inteira ao fundo capitalizado.
        anterior = mapa.get(linha["cnpj_ente"])
        mapa[linha["cnpj_ente"]] = True if (tem or anterior) else tem
    return mapa


# ---------------------------------------------------------------------------
# Abas 2, 3, 4 e 5 — um arquivo por RPPS
# ---------------------------------------------------------------------------

def montar_ente(store: Store, cnpj: str, ente: Mapping[str, Any]) -> Dict[str, Any]:
    """Tudo que o painel mostra sobre um RPPS, num arquivo só.

    Um arquivo por ente, e não um endpoint por clique: cada ficha tem alguns
    poucos KB e o navegador busca exatamente um deles.
    """
    ficha: Dict[str, Any] = dict(ente)

    ficha["crp"] = _crp_do_ente(store, cnpj)
    ficha["aliquotas"] = _varios(
        store, "rpps_aliquota",
        "plano, sujeito_passivo, aliquota, inicio_vigencia, fim_vigencia", cnpj,
        ordem="inicio_vigencia DESC")
    ficha["estatistica"] = _montar_estatistica(store, cnpj)
    ficha["segregacao"] = _um(
        store, "draa_segregacao_massa",
        "exercicio, plano, segregacao, data_ingresso_segurado", cnpj,
        ordem="exercicio DESC")

    ficha["caixa"] = _montar_caixa(store, cnpj)
    ficha["carteira"] = _montar_carteira_ente(store, cnpj)
    ficha["atuaria"] = _montar_atuaria(store, cnpj)
    return ficha


def _crp_do_ente(store: Store, cnpj: str) -> Optional[Dict[str, Any]]:
    """O certificado vigente do ente: a emissão mais recente do histórico."""
    linha = _um(store, "rpps_crp",
                "numero_crp, emissao, validade, campo_situacao, campo_tipo",
                cnpj, ordem="emissao DESC, numero_crp DESC")
    if not linha:
        return None
    leitura = _ler_crp(linha["campo_situacao"], linha["campo_tipo"],
                       linha["validade"], _hoje())
    return {
        "numero_crp": linha["numero_crp"],
        "emissao": linha["emissao"],
        "validade": linha["validade"],
        "valido": leitura["valido"],
        "judicial": leitura["judicial"],
    }


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


def _montar_estatistica(store: Store, cnpj: str) -> Dict[str, Any]:
    """Massa de participantes, somando os grupos por tipo de população.

    O endpoint devolve uma linha por grupo — categoria funcional, plano e massa
    — com as contagens separadas por sexo. O que a ficha mostra é o total por
    tipo de população, então a soma acontece aqui.
    """
    linhas = _varios(store, "draa_estatistica",
                     "exercicio, tipo_populacao, qt_masculino, qt_feminino,"
                     " folha_masculino, folha_feminino", cnpj,
                     ordem="exercicio DESC", limite=2000)
    if not linhas:
        return {"disponivel": False}

    exercicio = linhas[0]["exercicio"]
    por_tipo: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"pessoas": 0, "folha": 0.0})
    for linha in linhas:
        if linha["exercicio"] != exercicio:
            continue  # só o exercício mais recente
        alvo = por_tipo[(linha["tipo_populacao"] or "Não informado").strip()]
        alvo["pessoas"] += (linha["qt_masculino"] or 0) + (linha["qt_feminino"] or 0)
        alvo["folha"] += (linha["folha_masculino"] or 0.0) + (linha["folha_feminino"] or 0.0)

    ativos = por_tipo.get("Servidores", {}).get("pessoas", 0)
    inativos = (por_tipo.get("Aposentados", {}).get("pessoas", 0)
                + por_tipo.get("Pensionistas", {}).get("pessoas", 0))
    return {
        "disponivel": True,
        "exercicio": exercicio,
        "grupos": [{"rotulo": rotulo, "pessoas": int(dados["pessoas"]),
                    "folha": round(dados["folha"], 2)}
                   for rotulo, dados in sorted(
                       por_tipo.items(), key=lambda kv: kv[1]["pessoas"], reverse=True)],
        "ativos": int(ativos),
        "inativos": int(inativos),
        "razao_ativos_inativos": round(ativos / inativos, 2) if inativos else None,
    }


def _montar_caixa(store: Store, cnpj: str) -> Dict[str, Any]:
    """Série mensal de ingressos e dispêndios, na mesma unidade e escala.

    O DIPR não tem campo de total. Vem uma linha por rubrica, por mês, por plano
    e por órgão, e a leitura depende de dois critérios que não estão no nome da
    rubrica: o prefixo ``UT-`` separa saída de entrada, e o ``id_rubrica``
    separa valor movimentado de base de cálculo. Os totais desta tela são soma,
    não leitura.
    """
    linhas = _varios(store, "dipr",
                     "ano, mes, plano, rubrica, codigo_rubrica, valor", cnpj,
                     ordem="ano, mes", limite=40000)
    if not linhas:
        return {"disponivel": False}

    # Fora as bases de cálculo: são a folha sobre a qual as contribuições
    # incidem, não dinheiro que entrou. Ver codigos.rubrica_e_base_de_calculo.
    linhas = [l for l in linhas
              if not codigos.rubrica_e_base_de_calculo(l["codigo_rubrica"])]
    if not linhas:
        return {"disponivel": False}

    meses: Dict[tuple, Dict[str, Any]] = {}
    origem: Dict[str, float] = defaultdict(float)
    destino: Dict[str, float] = defaultdict(float)
    planos = set()

    for linha in linhas:
        chave = (linha["ano"], linha["mes"])
        ponto = meses.setdefault(chave, {"receita": 0.0, "despesa": 0.0,
                                         "tem_receita": False, "tem_despesa": False})
        valor = linha["valor"] or 0.0
        grupo = codigos.grupo_da_rubrica(linha["rubrica"])
        if codigos.rubrica_e_dispendio(linha["rubrica"]):
            ponto["despesa"] += valor
            ponto["tem_despesa"] = True
            destino[grupo] += valor
        else:
            ponto["receita"] += valor
            ponto["tem_receita"] = True
            origem[grupo] += valor
        if linha["plano"]:
            planos.add(linha["plano"])

    # Mês sem nenhuma rubrica de um lado não é mês de valor zero: é mês sem
    # declaração daquele lado. A diferença importa — zero diz "não gastou",
    # ausência diz "não informou", e o painel não pode trocar uma pela outra.
    serie = []
    for (ano, mes), v in sorted(meses.items()):
        receita = round(v["receita"], 2) if v["tem_receita"] else None
        despesa = round(v["despesa"], 2) if v["tem_despesa"] else None
        serie.append({
            "ano": ano, "mes": mes, "receita": receita, "despesa": despesa,
            "resultado": (round(receita - despesa, 2)
                          if receita is not None and despesa is not None else None),
        })

    total_receita = sum(p["receita"] for p in serie if p["receita"] is not None)
    total_despesa = sum(p["despesa"] for p in serie if p["despesa"] is not None)
    completos = [p for p in serie if p["resultado"] is not None]
    return {
        "disponivel": True,
        "serie": serie,
        "planos": sorted(planos),
        "total_receita": round(total_receita, 2),
        "total_despesa": round(total_despesa, 2),
        "resultado": round(total_receita - total_despesa, 2),
        "meses_declarados": len(completos),
        "meses_sem_receita": sum(1 for p in serie if p["receita"] is None),
        "meses_sem_despesa": sum(1 for p in serie if p["despesa"] is None),
        "meses_superavitarios": sum(1 for p in completos if p["resultado"] >= 0),
        "origem": _ranquear(origem, total_receita),
        "destino": _ranquear(destino, total_despesa),
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
    """Resultado atuarial, fluxo projetado, custeio e hipóteses.

    Uma correção em relação ao anteprojeto: ``DRAA_FLUXO_ATUARIAL`` **não é
    série temporal**. Cada linha é um item do fluxo com um único valor
    projetado — receitas por origem, despesas por tipo de benefício, e os
    totais nos códigos 190000 e 240000. A projeção ano a ano, que renderia a
    curva de cruzamento, existe nos arquivos de dados abertos da SPREV e não
    nesta API. Em vez de forjar uma série, a tela mostra o que há: a comparação
    entre receitas e despesas projetadas e a composição de cada lado.
    """
    fluxo = _varios(store, "draa_fluxo_atuarial",
                    "exercicio, plano, codigo, descricao, valor", cnpj,
                    ordem="exercicio DESC, codigo", limite=2000)
    compromissos = _varios(store, "draa_valores_compromissos",
                           "exercicio, plano, codigo, descricao, categoria,"
                           " geracao_atual, geracao_futura", cnpj,
                           ordem="exercicio DESC, codigo", limite=2000)
    hipoteses = _varios(store, "draa_hipotese_atuarial",
                        "exercicio, descricao, unidade, valor, longo_prazo",
                        cnpj, ordem="exercicio DESC", limite=400)
    custeio = _varios(store, "draa_plano_custeio",
                      "exercicio, plano, tipo_contribuicao, aliquota,"
                      " aliquota_definida, contribuicao_definida", cnpj,
                      ordem="exercicio DESC", limite=200)

    if not (fluxo or compromissos or hipoteses or custeio):
        return {"disponivel": False}

    exercicio = next((linha["exercicio"] for linha in
                      (compromissos or fluxo or hipoteses or custeio)), None)

    def _do_exercicio(linhas):
        return [l for l in linhas if l["exercicio"] == exercicio]

    return {
        "disponivel": True,
        "exercicio": exercicio,
        "resultado": _resultado_atuarial(_do_exercicio(compromissos)),
        "fluxo": _resumir_fluxo(_do_exercicio(fluxo)),
        "compromissos": [
            {"descricao": l["descricao"], "plano": l["plano"],
             "geracao_atual": l["geracao_atual"],
             "geracao_futura": l["geracao_futura"]}
            for l in _do_exercicio(compromissos)
            if _normalizar_situacao(l["categoria"]) != codigos.CATEGORIA_TITULO
            and (l["geracao_atual"] or l["geracao_futura"])
        ][:14],
        "hipoteses": _hipoteses_destaque(_do_exercicio(hipoteses)),
        "custeio": _resumir_custeio(_do_exercicio(custeio)),
    }


def _resultado_atuarial(compromissos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Déficit ou superávit, lido do código do demonstrativo.

    A API declara os dois em linhas separadas (600100 e 600300) e preenche a que
    se aplica. Somar as duas seria errado; o que vale é qual delas tem valor.
    """
    deficit = superavit = 0.0
    ativos = provisoes = 0.0
    for linha in compromissos:
        valor = linha["geracao_atual"] or 0.0
        if linha["codigo"] == codigos.COMPROMISSO_DEFICIT:
            deficit += valor
        elif linha["codigo"] == codigos.COMPROMISSO_SUPERAVIT:
            superavit += valor
        elif linha["codigo"] == codigos.COMPROMISSO_ATIVOS_GARANTIDORES:
            ativos += valor
        elif linha["codigo"] in (codigos.COMPROMISSO_PROVISAO_CONCEDIDOS,
                                 codigos.COMPROMISSO_PROVISAO_A_CONCEDER):
            provisoes += valor
    return {
        "deficit": round(deficit, 2),
        "superavit": round(superavit, 2),
        "ativos_garantidores": round(ativos, 2),
        "provisoes": round(provisoes, 2),
        "situacao": ("deficit" if deficit > 0 else
                     "superavit" if superavit > 0 else "equilibrio"),
    }


def _resumir_fluxo(fluxo: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Totais e composição do fluxo atuarial projetado."""
    if not fluxo:
        return {"disponivel": False}
    receitas = despesas = 0.0
    # O mesmo item aparece uma vez por plano e por massa. A composição soma
    # essas linhas, para casar com os totais, que também vêm somados.
    por_receita: Dict[str, float] = defaultdict(float)
    por_despesa: Dict[str, float] = defaultdict(float)
    for linha in fluxo:
        valor = linha["valor"] or 0.0
        if linha["codigo"] == codigos.FLUXO_TOTAL_RECEITAS:
            receitas += valor
        elif linha["codigo"] == codigos.FLUXO_TOTAL_DESPESAS:
            despesas += valor
        elif codigos.fluxo_e_receita(linha["codigo"]) and valor:
            por_receita[linha["descricao"] or "—"] += valor
        elif codigos.fluxo_e_despesa(linha["codigo"]) and valor:
            por_despesa[linha["descricao"] or "—"] += valor

    ordenar = lambda mapa: [{"descricao": d, "valor": round(v, 2)} for d, v in
                            sorted(mapa.items(), key=lambda kv: kv[1], reverse=True)[:8]]
    return {
        "disponivel": True,
        "receitas": round(receitas, 2),
        "despesas": round(despesas, 2),
        "saldo": round(receitas - despesas, 2),
        "itens_receita": ordenar(por_receita),
        "itens_despesa": ordenar(por_despesa),
    }


def _hipoteses_destaque(hipoteses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """As hipóteses que mudam a leitura do resultado, na ordem da tela.

    São mais de vinte por RPPS. Exibir todas afogaria justamente as que o
    conselho fiscal precisa ver ao lado do déficit.
    """
    por_descricao = {(l["descricao"] or "").strip(): l for l in hipoteses}
    saida = []
    for alvo in codigos.HIPOTESES_DESTAQUE:
        linha = por_descricao.get(alvo)
        if not linha:
            continue
        valor = linha["valor"]
        if linha["unidade"] and "PERCENT" in str(linha["unidade"]).upper():
            try:
                valor = "{:.2f}% a.a.".format(float(str(valor).replace(",", ".")))
            except (TypeError, ValueError):
                pass
        saida.append({"descricao": alvo, "valor": valor,
                      "longo_prazo": linha["longo_prazo"]})
    return saida


def _resumir_custeio(custeio: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Plano de custeio por tipo de contribuição, na ordem do demonstrativo."""
    por_tipo: Dict[str, Dict[str, Any]] = {}
    for linha in custeio:
        tipo = (linha["tipo_contribuicao"] or "").strip()
        alvo = por_tipo.setdefault(tipo, {
            "rotulo": tipo, "aliquota": None, "contribuicao": 0.0})
        aliquota = linha["aliquota_definida"] or linha["aliquota"]
        if aliquota is not None:
            alvo["aliquota"] = aliquota
        alvo["contribuicao"] += linha["contribuicao_definida"] or 0.0

    ordem = {rotulo: i for i, rotulo in enumerate(codigos.CUSTEIO_ORDEM)}
    return [dict(dados, contribuicao=round(dados["contribuicao"], 2))
            for _, dados in sorted(por_tipo.items(),
                                   key=lambda kv: ordem.get(kv[0], 99))]


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
    origens = store.origens()
    if len(origens) > 1:
        raise ValueError(
            "este banco tem dados de origens diferentes ({}). Um painel "
            "carimbado como real exibindo números sintéticos é o erro mais caro "
            "que este projeto pode cometer, então a construção para aqui.\n"
            "Apague {} e ingira de novo, ou use --banco para separar as bases."
            .format(", ".join(origens), store.caminho))
    if origens and origem == "api" and origens[0] != "api":
        raise ValueError(
            "o banco foi preenchido com dados de {}, mas a construção pediu "
            "origem 'api'.".format(origens[0]))

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

    escolhidos = list(entes.items())[:limite_entes] if limite_entes else list(entes.items())
    fichas = {}
    for cnpj, dados in escolhidos:
        ficha = montar_ente(store, cnpj, dados)
        fichas[cnpj] = ficha
        _gravar(os.path.join("ente", cnpj + ".json"), ficha, dir_saida)

    gerados.append(_gravar("benchmark.json", benchmark.montar(fichas), dir_saida))

    meta = {
        "origem": store.origem_unica() or origem,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entes": len(entes),
        "fichas": len(escolhidos),
        "nivel_fundo": carteira.get("nivel"),
        "capitais_conhecidas": grupos.cobertura_capitais(),
        "execucoes": store.resumo(),
    }
    gerados.append(_gravar("meta.json", meta, dir_saida))
    return {"arquivos": len(gerados) + len(list(escolhidos)), "meta": meta}
