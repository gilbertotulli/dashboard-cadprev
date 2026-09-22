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
from typing import AbstractSet, Any, Dict, List, Mapping, Optional, Sequence

from . import (ativos, benchmark, codigos, distribuicao, fundos, grupos,
               massas, qualidade)
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
    """Índice de entes federativos, com os grupos e o regime já resolvidos.

    A união é feita sobre todas as tabelas ingeridas porque nenhuma delas é
    garantidamente completa: um ente pode aparecer no CRP e não no DAIR, ou o
    contrário, e sumir do índice por isso seria perder o ente.

    Ente federativo não é sinônimo de RPPS, e tratá-los como sinônimo foi um
    erro caro deste projeto. O ``RPPS_CRP`` cobre o país inteiro — 5.596 entes,
    que é praticamente 5.570 municípios mais 26 estados mais o Distrito Federal
    —, porque o certificado é do ente, não do fundo. Só 2.132 deles mantêm RPPS
    vigente; 3.411 migraram para o RGPS. Contar os 5.596 como RPPS inflava todo
    denominador nacional em quase três vezes.

    Quem decide é o ``RPPS_REGIME_PREVIDENCIARIO``, pela vigência mais recente.
    Onde ele não alcança, declarar carteira de investimentos é prova suficiente
    de que há RPPS: quem não tem fundo não tem o que aplicar.
    """
    regimes = _regime_vigente(store)
    com_carteira = _entes_com_carteira(store)
    do_siconfi = _tabela_do_siconfi(store)
    entes: Dict[str, Dict[str, Any]] = {}
    for tabela in store.tabelas():
        # A tabela do SICONFI é referência, não fonte: ela cobre os 5.598 entes
        # da federação, quatro dos quais o CADPREV não conhece. Uni-la ao índice
        # acrescentaria fichas vazias e mexeria no denominador nacional.
        if tabela in ("execucao", "siconfi_ente"):
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
            oficial = do_siconfi.get(cnpj) or {}
            registro = {"cnpj": cnpj, "ente": linha["ente"]}
            registro.update(grupos.classificar(
                linha["uf"], linha["ente"], oficial.get("capital"),
                oficial.get("esfera_siconfi")))
            if oficial:
                registro["populacao"] = oficial.get("populacao")
                registro["cod_ibge"] = oficial.get("cod_ibge")
            regime = regimes.get(cnpj)
            registro["regime"] = regime
            registro["tem_rpps"] = (
                regime in _REGIMES_COM_RPPS if regime else cnpj in com_carteira)
            entes[cnpj] = registro
    return entes


#: Como o endpoint de regime nomeia as situações em que existe RPPS. "Em
#: extinção" continua sendo RPPS: tem massa, tem patrimônio e tem obrigação de
#: declarar — só não admite novos segurados.
_REGIMES_COM_RPPS = {"rpps", "rpps em extincao", "rpps em extinção"}


def _regime_vigente(store: Store) -> Dict[str, str]:
    """Regime previdenciário de cada ente, pela vigência mais recente."""
    if not store.tem_tabela("RPPS_REGIME_PREVIDENCIARIO"):
        return {}
    linhas = store.consultar("""
        SELECT r.cnpj_ente, r.regime
          FROM rpps_regime_previdenciario r
          JOIN (SELECT cnpj_ente, MAX(COALESCE(inicio, '')) AS quando
                  FROM rpps_regime_previdenciario GROUP BY cnpj_ente) u
            ON u.cnpj_ente = r.cnpj_ente
           AND u.quando = COALESCE(r.inicio, '')
         GROUP BY r.cnpj_ente
    """)
    return {l["cnpj_ente"]: _normalizar_situacao(l["regime"]) for l in linhas}


def _tabela_do_siconfi(store: Store) -> Dict[str, Dict[str, Any]]:
    """Entes da federação como o Tesouro os publica, indexados por CNPJ.

    População e marca de capital vêm daqui quando a tabela está no banco. Foi a
    dedução por nome que classificou São Paulo e Rio de Janeiro como estaduais
    — o município tem o mesmo nome do estado —, e quem publica a lista de
    capitais não precisa deduzir.
    """
    if not store.tem_tabela("SICONFI_ENTE"):
        return {}
    return {l["cnpj_ente"]: dict(l) for l in store.consultar(
        "SELECT cnpj_ente, cod_ibge, populacao, capital, esfera_siconfi "
        "FROM siconfi_ente WHERE cnpj_ente IS NOT NULL")}


def _entes_com_carteira(store: Store) -> set:
    """Quem declarou carteira — prova de que há fundo, mesmo sem regime."""
    if not store.tem_tabela("DAIR_CARTEIRA"):
        return set()
    return {l["cnpj_ente"] for l in store.consultar(
        "SELECT DISTINCT cnpj_ente FROM dair_carteira")}


# ---------------------------------------------------------------------------
# Qualidade do cadastro
# ---------------------------------------------------------------------------

def montar_qualidade(store: Store, entes: Mapping[str, Dict[str, Any]],
                     hoje: Optional[str] = None) -> Dict[str, Any]:
    """Tudo o que a própria base contradiz, com a evidência ao lado.

    Separa dois tipos de achado, porque merecem tratamentos diferentes. O
    lançamento impossível é aritmética: a posição excede o fundo em que está
    aplicada, e sai da soma sempre — publicar um número já provado falso não é
    transparência, é propagação. Os demais são juízos sobre a atualidade do
    dado, e por isso viram chave que o leitor liga e desliga.
    """
    hoje = hoje or _hoje()
    linhas_fora, achados = _achados_da_carteira(store)
    marcas: Dict[str, Dict[str, Any]] = defaultdict(dict)

    for achado in achados:
        if achado["cnpj"]:
            marcas[achado["cnpj"]][qualidade.MARCA_POSICAO] = True

    for cnpj, meses in _defasagem_do_dair(store, hoje).items():
        if meses is None or meses > qualidade.MESES_DAIR:
            marcas[cnpj][qualidade.MARCA_DAIR] = meses

    for cnpj, meses in _defasagem_do_crp(store, hoje).items():
        if meses is not None and meses > qualidade.MESES_CRP:
            marcas[cnpj][qualidade.MARCA_CRP] = meses

    return {
        "referencia": hoje,
        "linhas_excluidas": linhas_fora,
        "achados": achados,
        "marcas": {c: m for c, m in marcas.items() if c in entes},
    }


#: Colunas de que a régua depende. São opcionais no mapa de campos, então um
#: banco antigo pode não tê-las — e aí não há régua a aplicar, em vez de haver
#: uma régua que não marca nada.
_COLUNAS_DA_REGUA = ("identificacao_ativo", "valor_total", "pl_fundo")


def _achados_da_carteira(store: Store):
    """Aplica a régua de impossibilidade sobre a carteira ingerida."""
    if not store.tem_tabela("DAIR_CARTEIRA"):
        return set(), []
    if not all(_tem_coluna(store, "dair_carteira", c) for c in _COLUNAS_DA_REGUA):
        return set(), []
    opcionais = [c for c in ("nome_ativo", "valor_unitario", "quantidade_cotas")
                 if _tem_coluna(store, "dair_carteira", c)]
    colunas = ", ".join(("rowid AS rowid", "cnpj_ente") +
                        _COLUNAS_DA_REGUA + tuple(opcionais))
    tem_data = all(_tem_coluna(store, "dair_carteira", c) for c in ("ano", "mes"))
    consulta = "SELECT {}{} FROM dair_carteira".format(
        colunas, ", ano, mes" if tem_data else "")
    linhas = [dict(l) for l in store.consultar(consulta)]

    # Uma competência por vez. A régua compara a posição contra a MAIOR
    # declaração crível do mesmo fundo, e esse consenso é de um mês: misturar
    # junho com agosto mudaria o teto de um fundo por causa de quem entrou ou
    # saiu dele no intervalo, não por causa do erro que a régua procura.
    grupos: Dict[tuple, List[Dict[str, Any]]] = {}
    for linha in linhas:
        grupos.setdefault((linha.get("ano"), linha.get("mes")), []).append(linha)

    fora: set = set()
    achados: List[Dict[str, Any]] = []
    vistos: set = set()
    for _, do_mes in sorted(grupos.items(), key=lambda kv: kv[0], reverse=True):
        marcas, do_grupo = qualidade.achados_da_carteira(do_mes)
        fora |= {do_mes[i]["rowid"] for i in marcas}
        for achado in do_grupo:
            # O mesmo erro repetido mês a mês é um erro, não vários — e o
            # valor muda de um mês para o outro, então a chave não pode incluí-lo.
            # Como o laço vai da competência mais recente para trás, o achado
            # que fica é o da posição publicada hoje.
            chave = (achado.get("cnpj"), achado.get("fundo"))
            if chave in vistos:
                continue
            vistos.add(chave)
            achados.append(achado)
    return fora, achados


def _defasagem_do_dair(store: Store, hoje: str) -> Dict[str, Optional[int]]:
    """Meses entre a posição do último DAIR de cada ente e hoje.

    ``None`` marca quem não declarou nada no exercício ingerido — situação pior
    que atraso, e que por isso não pode virar zero.
    """
    if not store.tem_tabela("DAIR_IDENTIFICACAO"):
        return {}
    linhas = store.consultar(
        "SELECT cnpj_ente, MAX(posicao) AS ultima FROM dair_identificacao "
        "GROUP BY cnpj_ente")
    return {l["cnpj_ente"]: qualidade.meses_entre(l["ultima"], hoje)
            for l in linhas}


def _defasagem_do_crp(store: Store, hoje: str) -> Dict[str, Optional[int]]:
    """Meses desde o vencimento, para quem está sem CRP válido.

    Quem tem CRP válido não entra no resultado: não há defasagem a medir.
    """
    if not store.tem_tabela("RPPS_CRP"):
        return {}
    linhas = store.consultar("""
        SELECT c.cnpj_ente, c.validade, c.campo_situacao, c.campo_tipo
          FROM rpps_crp c
          JOIN (SELECT cnpj_ente, MAX(COALESCE(emissao, '') || '|' ||
                       COALESCE(numero_crp, '')) AS marca
                  FROM rpps_crp GROUP BY cnpj_ente) u
            ON u.cnpj_ente = c.cnpj_ente
           AND u.marca = COALESCE(c.emissao, '') || '|' || COALESCE(c.numero_crp, '')
         GROUP BY c.cnpj_ente
    """)
    fora: Dict[str, Optional[int]] = {}
    for linha in linhas:
        leitura = _ler_crp(linha["campo_situacao"], linha["campo_tipo"],
                           linha["validade"], hoje)
        if leitura["valido"]:
            continue
        fora[linha["cnpj_ente"]] = qualidade.meses_entre(linha["validade"], hoje)
    return fora


# ---------------------------------------------------------------------------
# Aba 1 — Panorama
# ---------------------------------------------------------------------------

def montar_panorama(store: Store, entes: Mapping[str, Dict[str, Any]],
                    fora: Optional[AbstractSet[str]] = None) -> Dict[str, Any]:
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

    fora = fora or frozenset()
    for linha in linhas:
        if linha["cnpj_ente"] in fora:
            continue
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
# Conformidade — o que o regulador registrou
# ---------------------------------------------------------------------------

def resumir_divergencia(fichas: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """Como as duas fontes se comportam no país, para o leitor julgar a sua.

    Uma divergência isolada não diz nada sem a distribuição ao lado: 4% parece
    muito até se saber que setenta por cento dos RPPS ficam abaixo de cinco.

    Conta também quem não pôde ser confrontado, e por quê. São três razões
    distintas e nenhuma delas é divergência: o ente que entregou o Anexo 04 sem
    o saldo das aplicações, o que declarou saldo de um fundo e omitiu o de outro
    que movimenta receita, e o que declarou saldo negativo — descoberto bancário
    ou reclassificação contábil, que é número legítimo e não é carteira.
    """
    desvios, sem_saldo, parcial, negativo, com_anexo = [], 0, 0, 0, 0
    com_imoveis = imoveis_aproxima = imoveis_afasta = 0
    for ficha in fichas.values():
        contabil = ficha.get("contabil") or {}
        if not contabil.get("disponivel"):
            continue
        com_anexo += 1
        if not contabil.get("com_saldo"):
            sem_saldo += 1
        elif contabil.get("saldo_negativo"):
            negativo += 1
        elif not contabil.get("saldo_completo"):
            parcial += 1
        confronto = contabil.get("confronto")
        if confronto:
            desvios.append(abs(confronto["perc"]))
            # Os imóveis são a assimetria que continua em aberto entre as duas
            # fontes, e a contagem abaixo é o que diz que ela está em aberto:
            # se tirá-los aproximasse sempre, seria regra e o painel a
            # aplicaria; se afastasse sempre, não haveria ressalva a fazer.
            if confronto.get("imoveis"):
                com_imoveis += 1
                sem = confronto.get("perc_sem_imoveis")
                if sem is not None:
                    if abs(sem) < abs(confronto["perc"]):
                        imoveis_aproxima += 1
                    elif abs(sem) > abs(confronto["perc"]):
                        imoveis_afasta += 1
    imoveis = {"com_imoveis": com_imoveis,
               "imoveis_aproxima": imoveis_aproxima,
               "imoveis_afasta": imoveis_afasta}
    if not desvios:
        return dict({"disponivel": False, "com_anexo": com_anexo,
                     "sem_saldo": sem_saldo, "saldo_parcial": parcial,
                     "saldo_negativo": negativo}, **imoveis)
    desvios.sort()

    def _faixa(limite):
        return sum(1 for d in desvios if d <= limite)

    meio = len(desvios) // 2
    mediana = (desvios[meio] if len(desvios) % 2
               else (desvios[meio - 1] + desvios[meio]) / 2)
    return dict(imoveis, **{
        "disponivel": True,
        "com_anexo": com_anexo,
        "sem_saldo": sem_saldo,
        "saldo_parcial": parcial,
        "saldo_negativo": negativo,
        "confrontados": len(desvios),
        "mediana": round(mediana, 2),
        "ate_1": _faixa(1.0),
        "ate_5": _faixa(5.0),
        "acima_5": len(desvios) - _faixa(5.0),
        "perc_ate_5": _pct(_faixa(5.0), len(desvios)),
    })


def montar_conformidade_nacional(store: Store,
                                 entes: Mapping[str, Dict[str, Any]],
                                 fora: Optional[AbstractSet[str]] = None,
                                 hoje: Optional[str] = None) -> Dict[str, Any]:
    """Notificações da SPREV e entrega do DRAA, no agregado.

    O universo destas notificações é estreito e isso precisa ficar dito: em
    17/09/2026 eram 770 itens em 222 entes, **todos** sobre segregação de massa.
    Não é um retrato da conformidade geral dos RPPS — é o histórico de um tema
    específico, que por acaso é um dos mais consequentes.
    """
    if not store.tem_tabela("DRAA_NOTIFICACAO"):
        return {"disponivel": False}
    hoje = hoje or _hoje()
    fora = fora or frozenset()

    linhas = [dict(l) for l in store.consultar(
        "SELECT DISTINCT cnpj_ente, numero, item_analise, situacao_item, "
        "notificacao, preclusao, resposta, prazo_resposta FROM draa_notificacao")]
    linhas = [l for l in linhas if l["cnpj_ente"] not in fora]

    por_item: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"irregular": 0, "em_curso": 0, "encerrado": 0})
    estado_do_ente: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"irregular": 0, "em_curso": 0, "encerrado": 0})
    for linha in linhas:
        estado = _classificar_notificacao(linha.get("situacao_item"))
        por_item[(linha.get("item_analise") or "Não informado").strip()][estado] += 1
        estado_do_ente[linha["cnpj_ente"]][estado] += 1

    irregulares = sorted(
        ({"cnpj": cnpj, "ente": (entes.get(cnpj) or {}).get("ente") or cnpj,
          "uf": (entes.get(cnpj) or {}).get("uf"), "itens": dados["irregular"]}
         for cnpj, dados in estado_do_ente.items() if dados["irregular"]),
        key=lambda d: (-d["itens"], d["ente"] or ""))

    entregas = {}
    if store.tem_tabela("DRAA_ENCAMINHAMENTO"):
        for linha in store.consultar(
                "SELECT cnpj_ente, MAX(exercicio) AS ultimo "
                "FROM draa_encaminhamento GROUP BY cnpj_ente"):
            if linha["cnpj_ente"] not in fora:
                entregas[linha["cnpj_ente"]] = linha["ultimo"]
    ultimo_exercicio = max(entregas.values()) if entregas else None

    return {
        "disponivel": True,
        "referencia": hoje,
        "escopo": "Notificações da SPREV sobre o DRAA. Em 17/09/2026 o conjunto "
                  "inteiro tratava de segregação de massa.",
        "entes_notificados": len(estado_do_ente),
        "entes_com_irregular": len(irregulares),
        "itens": len(linhas),
        "por_item": [
            dict(rotulo=rotulo, total=sum(dados.values()), **dados)
            for rotulo, dados in sorted(por_item.items(),
                                        key=lambda kv: -sum(kv[1].values()))
        ],
        "com_irregular": irregulares[:15],
        "ultimo_exercicio_entregue": ultimo_exercicio,
        "entregaram_ultimo": sum(1 for v in entregas.values()
                                 if v == ultimo_exercicio),
        "com_encaminhamento": len(entregas),
    }


# ---------------------------------------------------------------------------
# Aba — Militares, visão nacional
# ---------------------------------------------------------------------------

# O bloco militar do Anexo 04 do RREO, com os nomes de conta como o SICONFI os
# publica — inclusive os erros de digitação dele ("Milirares", e "Inativos E
# Pensionistas" onde o rótulo diz "Pensões e Inativos"). Corrigir o código aqui
# seria deixar de encontrar a linha.
_CONTA_CONTRIBUICOES = "TotalDasContribucoesDosMilirares"
_CONTA_DESPESAS = "TotalDasDespesasComInativosEPensionistasMilirares"
_CONTA_RESULTADO = "ResultadoAssociadoAInativosEPensionistasMilirares"
_COLUNA_RECEITA_RREO = "RECEITAS REALIZADAS ATÉ O BIMESTRE (b)"
_COLUNA_DESPESA_RREO = "DESPESAS PAGAS ATÉ O BIMESTRE (f)"


def _rreo_militar(store: Store) -> Dict[str, Dict[str, Any]]:
    """Contribuições e despesas dos militares, por ente, como o RREO declara.

    Não é a mesma coisa que o DRAA: aqui é execução orçamentária do exercício
    corrente, ali é avaliação atuarial. Convivem na mesma tela porque respondem
    perguntas diferentes sobre a mesma massa — e a referência temporal de cada
    uma aparece ao lado do número.
    """
    if not store.tem_tabela("SICONFI_RREO"):
        return {}
    fichas: Dict[str, Dict[str, Any]] = {}
    for linha in store.consultar(
            "SELECT cnpj_ente, exercicio, periodo, cod_conta, coluna, valor "
            "FROM siconfi_rreo WHERE cod_conta IN (?, ?, ?)",
            (_CONTA_CONTRIBUICOES, _CONTA_DESPESAS, _CONTA_RESULTADO)):
        ficha = fichas.setdefault(linha["cnpj_ente"], {
            "exercicio": linha["exercicio"], "periodo": linha["periodo"],
            "contribuicoes": None, "despesas": None, "resultado": None})
        coluna = (linha["coluna"] or "").strip()
        conta = linha["cod_conta"]
        if conta == _CONTA_CONTRIBUICOES and coluna == _COLUNA_RECEITA_RREO:
            ficha["contribuicoes"] = linha["valor"]
        elif conta == _CONTA_DESPESAS and coluna == _COLUNA_DESPESA_RREO:
            ficha["despesas"] = linha["valor"]
        elif conta == _CONTA_RESULTADO and coluna == _COLUNA_DESPESA_RREO:
            ficha["resultado"] = linha["valor"]
    return fichas


def _fundo_militar(store: Store) -> Dict[str, Dict[str, Any]]:
    """Ativos garantidores e provisões da massa militar, por ente.

    Aqui a ausência e o zero se separam sozinhos, porque a fonte não deixa
    dúvida: em 17/09/2026 nenhum dos 26 Estados com massa militar omitia o
    item 500000 — **todos declaravam um valor**, e 14 declaravam exatamente
    zero. Zero declarado é declaração, não lacuna, e diz o que a lei diz: o
    sistema de proteção social dos militares é de repartição, custeado pelo
    tesouro estadual, sem fundo capitalizado próprio.

    Entre os 12 que declaram algo, a distância importa mais que o rótulo: Amapá
    cobre 31,5% das provisões e Roraima 30,1% — fundos de verdade —, o Rio
    Grande do Sul está em 5,1% e os outros nove ficam abaixo de 1%, com a Bahia
    em 0,004%. Por isso a tela publica a cobertura, e não um "tem fundo: sim/não"
    que colocaria a Bahia e o Amapá do mesmo lado.
    """
    if not store.tem_tabela("DRAA_VALORES_COMPROMISSOS"):
        return {}
    linhas = [dict(l) for l in store.consultar(
        "SELECT cnpj_ente, exercicio, plano, massa, codigo, geracao_atual, envio"
        " FROM draa_valores_compromissos WHERE codigo IN (?, ?, ?)",
        (codigos.COMPROMISSO_ATIVOS_GARANTIDORES,
         codigos.COMPROMISSO_PROVISAO_CONCEDIDOS,
         codigos.COMPROMISSO_PROVISAO_A_CONCEDER))] if _tem_coluna(
            store, "draa_valores_compromissos", "envio") else [
        dict(l, envio=None) for l in store.consultar(
            "SELECT cnpj_ente, exercicio, plano, massa, codigo, geracao_atual"
            " FROM draa_valores_compromissos WHERE codigo IN (?, ?, ?)",
            (codigos.COMPROMISSO_ATIVOS_GARANTIDORES,
             codigos.COMPROMISSO_PROVISAO_CONCEDIDOS,
             codigos.COMPROMISSO_PROVISAO_A_CONCEDER))]

    militares = [l for l in linhas if massas.eh_militar(l.get("massa"))]
    recente: Dict[str, Any] = {}
    for linha in militares:
        cnpj, exercicio = linha["cnpj_ente"], linha.get("exercicio")
        if exercicio is not None and (cnpj not in recente or exercicio > recente[cnpj]):
            recente[cnpj] = exercicio

    fichas: Dict[str, Dict[str, Any]] = {}
    for linha in militares:
        cnpj = linha["cnpj_ente"]
        if linha.get("exercicio") != recente.get(cnpj):
            continue
        ficha = fichas.setdefault(cnpj, {
            "exercicio": recente[cnpj], "ativos_garantidores": None,
            "provisoes": 0.0, "planos": set()})
        valor = linha.get("geracao_atual")
        if linha["codigo"] == codigos.COMPROMISSO_ATIVOS_GARANTIDORES:
            if valor is not None:
                ficha["ativos_garantidores"] = (
                    (ficha["ativos_garantidores"] or 0.0) + float(valor))
        elif valor is not None:
            ficha["provisoes"] += float(valor)
        if linha.get("plano"):
            ficha["planos"].add(linha["plano"].strip())

    for ficha in fichas.values():
        ativos = ficha["ativos_garantidores"]
        ficha["provisoes"] = round(ficha["provisoes"], 2)
        ficha["ativos_garantidores"] = (round(ativos, 2)
                                        if ativos is not None else None)
        ficha["cobertura"] = (round(ativos / ficha["provisoes"] * 100, 2)
                              if ativos is not None and ficha["provisoes"] else None)
        # A leitura é da fonte: ela declarou zero, ou não declarou nada.
        ficha["declara_fundo"] = bool(ativos)
        ficha["declarou_zero"] = ativos is not None and not ativos
        ficha["planos"] = sorted(ficha["planos"])
    return fichas


def _custeio_militar(store: Store) -> Dict[str, Dict[str, Any]]:
    """A alíquota que cada Estado fixou para a massa militar.

    Os Estados têm autonomia para decidir: 10,5% foi a decisão federal, que
    muitos seguiram, e divergir dela não é irregularidade — é a competência
    legislativa de cada um sendo exercida. Por isso o painel publica a
    distribuição e não marca ninguém: quem sinaliza "fora do padrão" sem base
    legal para o padrão está inventando uma regra.

    Também não há contribuição patronal neste sistema. A ausência da linha do
    ente é o normal, não uma falta.
    """
    if not store.tem_tabela("DRAA_PLANO_CUSTEIO"):
        return {}
    linhas = [dict(l) for l in store.consultar(
        "SELECT cnpj_ente, exercicio, massa, tipo_contribuicao, aliquota,"
        " aliquota_definida FROM draa_plano_custeio")]
    militares = [l for l in linhas if massas.eh_militar(l.get("massa"))]
    recente: Dict[str, Any] = {}
    for linha in militares:
        cnpj, exercicio = linha["cnpj_ente"], linha.get("exercicio")
        if exercicio is not None and (cnpj not in recente or exercicio > recente[cnpj]):
            recente[cnpj] = exercicio

    fichas: Dict[str, Dict[str, Any]] = {}
    for linha in militares:
        cnpj = linha["cnpj_ente"]
        if linha.get("exercicio") != recente.get(cnpj):
            continue
        aliquota = linha.get("aliquota_definida")
        if aliquota is None:
            aliquota = linha.get("aliquota")
        if aliquota is None:
            continue
        ficha = fichas.setdefault(cnpj, {"exercicio": recente[cnpj], "itens": {}})
        ficha["itens"][(linha.get("tipo_contribuicao") or "").strip()] = aliquota

    for ficha in fichas.values():
        itens = ficha.pop("itens")
        ficha["contribuicoes"] = [
            {"rotulo": rotulo, "aliquota": valor}
            for rotulo, valor in sorted(itens.items())]
        # A do segurado ativo é a que a norma federal fixou em 10,5% e a que os
        # Estados replicaram ou não; é ela que a comparação entre Estados usa.
        ativos = [v for r, v in itens.items() if "ativ" in r.lower()]
        ficha["aliquota_ativos"] = ativos[0] if ativos else None
        ficha["tem_patronal"] = any("ente" in r.lower() for r in itens)
    return fichas


def _consolidar(fichas: Mapping[str, Mapping[str, Any]],
                fora: AbstractSet[str],
                indicadores: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """A distribuição de cada indicador entre os RPPS que o declararam.

    ``indicadores`` mapeia o nome publicado para uma função que lê a ficha e
    devolve o número, ou ``None`` quando o ente não tem esse dado. ``None`` não
    entra na conta: indicador indefinido não é indicador zero, e somá-lo como
    zero premiaria quem não declarou na mediana de todo mundo.
    """
    valores: Dict[str, List[Any]] = {nome: [] for nome in indicadores}
    for cnpj, ficha in fichas.items():
        if cnpj in fora:
            continue
        for nome, ler in indicadores.items():
            try:
                valores[nome].append(ler(ficha))
            except (TypeError, ZeroDivisionError):
                valores[nome].append(None)
    return {nome: distribuicao.resumir(lista) for nome, lista in valores.items()}


def _soma_das_fichas(fichas: Mapping[str, Mapping[str, Any]],
                     fora: AbstractSet[str], ler) -> Dict[str, Any]:
    """Um total nacional e quantos entes entraram nele.

    O total só significa alguma coisa ao lado do número de declarantes: R$ 40
    bilhões somados por 1.500 RPPS e por 300 são dois fatos diferentes, e o
    segundo não é o país.
    """
    valores = [ler(ficha) for cnpj, ficha in fichas.items() if cnpj not in fora]
    presentes = [v for v in valores if v is not None]
    return {"total": round(sum(presentes), 2) if presentes else None,
            "entes": len(presentes),
            "sem_dado": len(valores) - len(presentes)}


def montar_ficha_nacional(fichas: Mapping[str, Mapping[str, Any]],
                          fora: Optional[AbstractSet[str]] = None
                          ) -> Dict[str, Any]:
    """O consolidado da aba Ficha: massa, alíquota, CRP e certificação.

    A aba respondia só sobre um RPPS por vez, e a pergunta que ela levanta é
    comparativa: 1,8 ativo por beneficiário é muito ou pouco? Sem a
    distribuição ao lado, cada ficha era um número sem régua.
    """
    fora = fora or frozenset()
    presentes = {c: f for c, f in fichas.items() if c not in fora}
    if not presentes:
        return {"disponivel": False}

    def _est(ficha, campo):
        est = ficha.get("estatistica") or {}
        return est.get(campo) if est.get("disponivel") else None

    def _aliquota(ficha, quem):
        for linha in ficha.get("aliquotas") or []:
            vigente = (linha.get("vigente") or "").upper()
            if vigente and "NÃO" in vigente.replace("NAO", "NÃO"):
                continue
            if (linha.get("sujeito_passivo") or "").strip().lower() == quem:
                return linha.get("aliquota")
        return None

    indicadores = {
        "ativos": lambda f: _est(f, "ativos"),
        "inativos": lambda f: _est(f, "inativos"),
        "razao_ativos_inativos": lambda f: _est(f, "razao_ativos_inativos"),
        "aliquota_ente": lambda f: _aliquota(f, "ente"),
        "aliquota_segurado": lambda f: _aliquota(f, "segurado"),
    }
    consolidado = _consolidar(presentes, frozenset(), indicadores)

    # CRP e certificação são contagens, não distribuições: o que se pergunta é
    # "quantos estão em dia", e a mediana de um sim/não não quer dizer nada.
    com_crp = vencido = 0
    governanca_regular = governanca_irregular = 0
    com_militar = 0
    for ficha in presentes.values():
        crp = ficha.get("crp") or {}
        if crp.get("validade"):
            com_crp += 1
            if crp.get("vencido"):
                vencido += 1
        gov = ficha.get("governanca") or {}
        if gov.get("disponivel"):
            if gov.get("so_vencidas") or gov.get("sem_certificacao"):
                governanca_irregular += 1
            else:
                governanca_regular += 1
        if (ficha.get("estatistica") or {}).get("tem_militar"):
            com_militar += 1

    return {
        "disponivel": True,
        "rpps": len(presentes),
        "indicadores": consolidado,
        "pessoas": {
            "ativos": _soma_das_fichas(presentes, frozenset(),
                                       lambda f: _est(f, "ativos")),
            "inativos": _soma_das_fichas(presentes, frozenset(),
                                         lambda f: _est(f, "inativos")),
        },
        "crp": {"com_validade": com_crp, "vencido": vencido,
                "em_dia": com_crp - vencido},
        "governanca": {"avaliados": governanca_regular + governanca_irregular,
                       "regulares": governanca_regular,
                       "irregulares": governanca_irregular},
        "com_massa_militar": com_militar,
    }


def montar_caixa_nacional(fichas: Mapping[str, Mapping[str, Any]],
                          fora: Optional[AbstractSet[str]] = None
                          ) -> Dict[str, Any]:
    """O consolidado da aba Caixa: ingressos, dispêndios e resultado.

    **O total nacional é mensal, não anual.** A janela do DIPR varia de ente
    para ente, e somar meia série de um com a série cheia de outro produz um
    total que nenhum dos dois declarou. A primeira tentativa de contornar isso
    somava só quem tivesse doze meses — e a publicação de 22/09/2026 mostrou o
    defeito: **no meio do exercício ninguém tem doze meses**, e o quadro saiu
    com um traço no lugar do número. Numa amostra de 45 RPPS daquele dia, a
    série ia de zero a seis meses, com seis sendo a mais comum.

    Então o total soma, por ente, o que ele declarou dividido pelos meses que
    declarou: o ritmo mensal de cada um, somado. Todo RPPS entra com a própria
    janela, ninguém é extrapolado para doze meses, e o número existe em
    qualquer ponto do exercício. Quem declarou dois meses contribui com uma
    média mais ruidosa — por isso a distribuição de meses declarados fica
    publicada ao lado, para o leitor ver de que séries o total é feito.
    """
    fora = fora or frozenset()
    presentes = {c: f for c, f in fichas.items() if c not in fora}
    if not presentes:
        return {"disponivel": False}

    def _caixa(ficha):
        c = ficha.get("caixa") or {}
        return c if c.get("disponivel") else None

    def _resultado_sobre_ingressos(ficha):
        c = _caixa(ficha)
        if not c or not c.get("total_receita"):
            return None
        return round((c["total_receita"] - (c.get("total_despesa") or 0.0))
                     / c["total_receita"] * 100, 2)

    def _mensal(ficha, campo):
        c = _caixa(ficha)
        meses = (c or {}).get("meses_declarados") or 0
        if not c or not meses or c.get(campo) is None:
            return None
        return round(c[campo] / meses, 2)

    indicadores = {
        "resultado_sobre_ingressos": _resultado_sobre_ingressos,
        "receita_mensal": lambda f: _mensal(f, "total_receita"),
        "despesa_mensal": lambda f: _mensal(f, "total_despesa"),
        "meses_declarados": lambda f: (_caixa(f) or {}).get("meses_declarados"),
    }

    deficitarios = sum(
        1 for f in presentes.values()
        if (_caixa(f) or {}).get("resultado") is not None
        and _caixa(f)["resultado"] < 0)
    com_caixa = sum(1 for f in presentes.values() if _caixa(f))

    return {
        "disponivel": bool(com_caixa),
        "rpps": len(presentes),
        "com_dipr": com_caixa,
        "deficitarios": deficitarios,
        "indicadores": _consolidar(presentes, frozenset(), indicadores),
        # O ritmo mensal do país: cada RPPS entra com a própria janela.
        "mensal": {
            "receita": _soma_das_fichas(
                presentes, frozenset(), lambda f: _mensal(f, "total_receita")),
            "despesa": _soma_das_fichas(
                presentes, frozenset(), lambda f: _mensal(f, "total_despesa")),
        },
    }


def montar_atuaria_nacional(fichas: Mapping[str, Mapping[str, Any]],
                            fora: Optional[AbstractSet[str]] = None
                            ) -> Dict[str, Any]:
    """O consolidado da aba Atuária: provisões, lastro e cobertura.

    A soma de provisões do país é legítima — são compromissos, e compromissos
    somam. O que não soma é **resultado com resultado**: o superávit de um RPPS
    não cobre o déficit de outro, e um "resultado nacional" líquido afirmaria
    exatamente isso. Por isso os dois lados aparecem separados, com a contagem
    de quantos estão de cada lado.
    """
    fora = fora or frozenset()
    presentes = {c: f for c, f in fichas.items() if c not in fora}
    if not presentes:
        return {"disponivel": False}

    def _somar(ficha, campo, militar=None):
        a = ficha.get("atuaria") or {}
        if not a.get("disponivel"):
            return None
        total = 0.0
        achou = False
        for bloco in a.get("blocos") or []:
            if militar is not None and bool(bloco.get("militar")) != militar:
                continue
            valor = (bloco.get("resultado") or {}).get(campo)
            if valor is not None:
                total += valor
                achou = True
        return total if achou else None

    def _cobertura(ficha):
        provisoes = _somar(ficha, "provisoes")
        ativos_g = _somar(ficha, "ativos_garantidores")
        if not provisoes or ativos_g is None:
            return None
        return round(ativos_g / provisoes * 100, 2)

    indicadores = {
        "cobertura": _cobertura,
        "provisoes": lambda f: _somar(f, "provisoes"),
        "ativos_garantidores": lambda f: _somar(f, "ativos_garantidores"),
    }

    com_deficit = com_superavit = com_draa = 0
    for ficha in presentes.values():
        a = ficha.get("atuaria") or {}
        if not a.get("disponivel"):
            continue
        com_draa += 1
        # Por ente: basta um fundo em déficit para o ente ter déficit em algum
        # fundo. Não se compensa um com o outro — são planos distintos.
        blocos = a.get("blocos") or []
        if any((b.get("resultado") or {}).get("situacao") == "deficit" for b in blocos):
            com_deficit += 1
        elif any((b.get("resultado") or {}).get("situacao") == "superavit"
                 for b in blocos):
            com_superavit += 1

    return {
        "disponivel": bool(com_draa),
        "rpps": len(presentes),
        "com_draa": com_draa,
        "com_deficit": com_deficit,
        "com_superavit": com_superavit,
        "indicadores": _consolidar(presentes, frozenset(), indicadores),
        "compromissos": {
            "provisoes": _soma_das_fichas(presentes, frozenset(),
                                          lambda f: _somar(f, "provisoes")),
            "ativos_garantidores": _soma_das_fichas(
                presentes, frozenset(), lambda f: _somar(f, "ativos_garantidores")),
            # Somados à parte, de propósito: ver o docstring.
            "deficit": _soma_das_fichas(presentes, frozenset(),
                                        lambda f: _somar(f, "deficit")),
            "superavit": _soma_das_fichas(presentes, frozenset(),
                                          lambda f: _somar(f, "superavit")),
        },
        "militar": {
            "provisoes": _soma_das_fichas(
                presentes, frozenset(), lambda f: _somar(f, "provisoes", militar=True)),
            "ativos_garantidores": _soma_das_fichas(
                presentes, frozenset(),
                lambda f: _somar(f, "ativos_garantidores", militar=True)),
        },
    }


def montar_militar_nacional(store: Store, entes: Mapping[str, Dict[str, Any]],
                            fora: Optional[AbstractSet[str]] = None
                            ) -> Dict[str, Any]:
    """A massa militar, que só existe nos Estados.

    Município não tem militar: a comparação é entre Estados e só entre Estados,
    porque não há outro termo de comparação. Em 17/09/2026 havia massa militar
    em 26 dos 27 governos estaduais — Minas Gerais não entrega DRAA — e em
    nenhum dos 5.569 municípios.
    """
    if not store.tem_tabela("DRAA_ESTATISTICA"):
        return {"disponivel": False}
    fora = fora or frozenset()

    linhas = [dict(l) for l in store.consultar(
        "SELECT cnpj_ente, exercicio, massa, tipo_populacao, categoria_populacao,"
        " qt_masculino, qt_feminino, folha_masculino, folha_feminino"
        " FROM draa_estatistica")]
    # Só o exercício mais recente de cada ente: o DRAA de 2026 e o de 2025
    # convivem na API e somá-los conta a mesma pessoa duas vezes.
    ultimo: Dict[str, Any] = {}
    for linha in linhas:
        cnpj, exercicio = linha["cnpj_ente"], linha.get("exercicio")
        if exercicio is not None and (cnpj not in ultimo or exercicio > ultimo[cnpj]):
            ultimo[cnpj] = exercicio

    contas: Dict[str, Dict[str, Any]] = {}
    for linha in linhas:
        cnpj = linha["cnpj_ente"]
        if cnpj in fora or linha.get("exercicio") != ultimo.get(cnpj):
            continue
        qual = massas.normalizar(linha.get("massa")) or massas.CIVIL
        ficha = contas.setdefault(cnpj, {
            "exercicio": ultimo[cnpj],
            "militar": {"ativo": 0, "inativo": 0, "pensionista": 0, "folha": 0.0},
            "civil": {"ativo": 0, "inativo": 0, "pensionista": 0, "folha": 0.0},
            "tem_militar": False})
        alvo = ficha["militar" if qual == massas.MILITAR else "civil"]
        pessoas = (linha["qt_masculino"] or 0) + (linha["qt_feminino"] or 0)
        qual_papel = massas.papel(qual, linha.get("tipo_populacao"),
                                  linha.get("categoria_populacao"))
        if qual_papel in alvo:
            alvo[qual_papel] += pessoas
        alvo["folha"] += ((linha["folha_masculino"] or 0.0)
                          + (linha["folha_feminino"] or 0.0))
        if qual == massas.MILITAR:
            ficha["tem_militar"] = True

    rreo = _rreo_militar(store)
    fundo = _fundo_militar(store)
    custeio = _custeio_militar(store)
    fichas = []
    for cnpj, dados in contas.items():
        if not dados["tem_militar"]:
            continue
        mil, civ = dados["militar"], dados["civil"]
        ente = entes.get(cnpj) or {}
        beneficiarios = mil["inativo"] + mil["pensionista"]
        total_mil = mil["ativo"] + beneficiarios
        total_civ = civ["ativo"] + civ["inativo"] + civ["pensionista"]
        orcamento = rreo.get(cnpj) or {}
        fichas.append({
            "cnpj": cnpj,
            "uf": ente.get("uf"),
            "ente": ente.get("ente") or cnpj,
            "exercicio": dados["exercicio"],
            "ativos": mil["ativo"],
            "inativos": mil["inativo"],
            "pensionistas": mil["pensionista"],
            "beneficiarios": beneficiarios,
            "pessoas": total_mil,
            "folha": round(mil["folha"], 2),
            "razao_ativos_inativos": (round(mil["ativo"] / beneficiarios, 2)
                                      if beneficiarios else None),
            "civis": total_civ,
            "razao_civil": (round(civ["ativo"] / (civ["inativo"] + civ["pensionista"]), 2)
                            if (civ["inativo"] + civ["pensionista"]) else None),
            "participacao": (round(total_mil / (total_mil + total_civ) * 100, 1)
                             if (total_mil + total_civ) else None),
            "planos": (fundo.get(cnpj) or {}).get("planos") or [],
            "aliquota_militar": (custeio.get(cnpj) or {}).get("aliquota_ativos"),
            "contribuicoes_militares": (custeio.get(cnpj) or {}).get("contribuicoes") or [],
            "tem_patronal": (custeio.get(cnpj) or {}).get("tem_patronal"),
            "ativos_garantidores": (fundo.get(cnpj) or {}).get("ativos_garantidores"),
            "provisoes": (fundo.get(cnpj) or {}).get("provisoes"),
            "cobertura": (fundo.get(cnpj) or {}).get("cobertura"),
            "declara_fundo": (fundo.get(cnpj) or {}).get("declara_fundo"),
            "declarou_zero": (fundo.get(cnpj) or {}).get("declarou_zero"),
            "exercicio_rreo": orcamento.get("exercicio"),
            "periodo_rreo": orcamento.get("periodo"),
            "contribuicoes": orcamento.get("contribuicoes"),
            "despesas": orcamento.get("despesas"),
            "resultado": orcamento.get("resultado"),
        })
    if not fichas:
        return {"disponivel": False}
    fichas.sort(key=lambda f: -f["pessoas"])

    razoes = [f["razao_ativos_inativos"] for f in fichas
              if f["razao_ativos_inativos"] is not None]
    ativos = sum(f["ativos"] for f in fichas)
    beneficiarios = sum(f["beneficiarios"] for f in fichas)
    estaduais = {cnpj for cnpj, dados in entes.items()
                 if dados.get("esfera") == grupos.ESTADUAL and cnpj not in fora}
    com_massa = {f["cnpj"] for f in fichas}
    return {
        "disponivel": True,
        "escopo": "Só os Estados têm massa militar. Município não entra nesta "
                  "comparação porque não há o que comparar.",
        "nota_nomenclatura": massas.NOTA_NOMENCLATURA,
        "nota_carteira": massas.NOTA_CARTEIRA,
        "entes": fichas,
        "estados_com_massa": len(fichas),
        "estados_sem_massa": sorted(
            (entes[cnpj].get("uf") or "?") for cnpj in estaduais - com_massa),
        # Massa militar declarada com zero pessoas é declaração, não ausência:
        # o ente diz que não tem militares no seu RPPS. Fica na lista, com o
        # zero dele, mas não conta como Estado com massa nem cobra RREO.
        "estados_com_pessoas": sum(1 for f in fichas if f["pessoas"]),
        "sem_rreo": sorted(f["uf"] or "?" for f in fichas
                           if f["contribuicoes"] is None and f["pessoas"]),
        # O fundo militar, onde ele existe. Zero declarado entra na conta dos
        # que não têm — e é o que a fonte diz, não uma dedução —, enquanto a
        # ausência de declaração fica à parte, porque não diz nada.
        "com_fundo": sum(1 for f in fichas if f.get("declara_fundo")),
        "declararam_zero": sum(1 for f in fichas if f.get("declarou_zero")),
        "sem_declaracao_de_fundo": sorted(
            f["uf"] or "?" for f in fichas
            if f["pessoas"] and f.get("ativos_garantidores") is None),
        "ativos_garantidores": round(
            sum(f["ativos_garantidores"] or 0.0 for f in fichas), 2),
        "provisoes": round(sum(f["provisoes"] or 0.0 for f in fichas), 2),
        # A alíquota dos militares ativos, Estado a Estado. Sem juízo: os
        # Estados têm competência para fixá-la, e 10,5% é a referência federal
        # que muitos adotaram, não um piso nem um teto legal.
        "aliquota_referencia": ALIQUOTA_MILITAR_FEDERAL,
        "com_aliquota": sum(1 for f in fichas
                            if f.get("aliquota_militar") is not None),
        "na_referencia": sum(
            1 for f in fichas
            if f.get("aliquota_militar") is not None
            and abs(f["aliquota_militar"] - ALIQUOTA_MILITAR_FEDERAL) < 0.005),
        "com_patronal": sorted(f["uf"] or "?" for f in fichas
                               if f.get("tem_patronal")),
        "ativos": ativos,
        "inativos": sum(f["inativos"] for f in fichas),
        "pensionistas": sum(f["pensionistas"] for f in fichas),
        "pessoas": sum(f["pessoas"] for f in fichas),
        "folha": round(sum(f["folha"] for f in fichas), 2),
        "razao_ativos_inativos": (round(ativos / beneficiarios, 2)
                                  if beneficiarios else None),
        # Grupo com menos de três declarantes não vira estatística.
        "resumo_razao": benchmark.resumir(razoes) if len(razoes) >= 3 else None,
    }


# ---------------------------------------------------------------------------
# Aba 4 — Carteira, visão nacional
# ---------------------------------------------------------------------------

def montar_carteira_nacional(store: Store,
                             entes: Mapping[str, Dict[str, Any]],
                             fora: Optional[AbstractSet[str]] = None,
                             linhas_fora: Optional[AbstractSet[int]] = None
                             ) -> Dict[str, Any]:
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
    competencia = _competencias_do_dair(store)

    segregacao = _mapa_segregacao(store)
    colunas = ("cnpj_ente, segmento, valor_total, limite_cmn, plano"
               if _tem_coluna(store, "dair_carteira", "plano")
               else "cnpj_ente, segmento, valor_total, limite_cmn")
    fora = fora or frozenset()
    linhas_fora = linhas_fora or frozenset()
    # A competência mais recente, e só ela: com duas no banco o patrimônio
    # nacional dobraria sem que um centavo tivesse sido aplicado.
    if competencia.get("ano") is not None:
        cru = store.consultar(
            "SELECT rowid AS rowid, {} FROM dair_carteira "
            "WHERE ano = ? AND mes = ?".format(colunas),
            (competencia["ano"], competencia["mes"]))
    else:
        cru = store.consultar(
            "SELECT rowid AS rowid, {} FROM dair_carteira".format(colunas))
    linhas = [dict(linha) for linha in cru
              if linha["rowid"] not in linhas_fora and linha["cnpj_ente"] not in fora]

    total = sum(linha.get("valor_total") or 0.0 for linha in linhas)

    por_fundo = fundos.agregar(linhas, nivel, segregacao)
    por_segmento: Dict[str, float] = defaultdict(float)
    por_esfera: Dict[str, float] = defaultdict(float)
    por_regiao: Dict[str, float] = defaultdict(float)
    por_ente: Dict[str, float] = defaultdict(float)

    # Ativo que a própria fonte marca como fora do rol da resolução. Não é teto
    # estourado — é outra coisa, e some se for tratada como ausência de limite.
    fora_da_norma: Dict[str, float] = defaultdict(float)
    for linha in linhas:
        valor = linha.get("valor_total") or 0.0
        segmento = (linha.get("segmento") or "Não informado").strip()
        por_segmento[segmento] += valor
        por_ente[linha["cnpj_ente"]] += valor
        ente = entes.get(linha["cnpj_ente"], {})
        por_esfera[ente.get("esfera") or "municipal"] += valor
        por_regiao[ente.get("regiao") or "Não classificado"] += valor
        if "nao enquadrad" in _normalizar_situacao(segmento):
            fora_da_norma[linha["cnpj_ente"]] += valor

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
        # O que os cinco maiores somam, contra o país: a concentração é o dado,
        # e ela não se lê linha a linha.
        "total_maiores": round(sum(por_ente[c] for c in ordenados[:5]), 2),
        "perc_maiores": _pct(sum(por_ente[c] for c in ordenados[:5]), total),
        "fora_da_norma": {
            "entes": len(fora_da_norma),
            "valor": round(sum(fora_da_norma.values()), 2),
            "perc": _pct(sum(fora_da_norma.values()), total),
            "maiores": [
                {"cnpj": c, "ente": (entes.get(c) or {}).get("ente") or c,
                 "uf": (entes.get(c) or {}).get("uf"),
                 "valor": round(v, 2),
                 "perc_da_carteira": _pct(v, por_ente[c])}
                for c, v in sorted(fora_da_norma.items(),
                                   key=lambda kv: kv[1], reverse=True)[:10]],
        },
        **competencia,
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

def montar_ente(store: Store, cnpj: str, ente: Mapping[str, Any],
                linhas_fora: Optional[AbstractSet[int]] = None,
                referencia: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
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
    ficha["carteira"] = _montar_carteira_ente(
        store, cnpj, linhas_fora, referencia)
    ficha["atuaria"] = _montar_atuaria(store, cnpj)
    ficha["amortizacao"] = _montar_amortizacao(store, cnpj)
    ficha["projetado_executado"] = _montar_projetado_executado(store, cnpj)
    ficha["conformidade"] = _montar_conformidade(store, cnpj)
    ficha["governanca"] = _montar_governanca(store, cnpj)
    ficha["contabil"] = _montar_contabil(
        store, cnpj, (ficha["carteira"] or {}).get("total"),
        (ficha["carteira"] or {}).get("segmentos"))
    ficha["contabil_anual"] = _montar_contabil_anual(
        store, cnpj, ficha["atuaria"])
    return ficha


def _do_ultimo_envio(linhas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Só as linhas da submissão mais recente do exercício.

    O DRAA pode ser reenviado, e a API devolve todas as versões convivendo: a
    substituída ("Substituída Antes da Recepção dos Arquivos Digitalizados"),
    a retificada e a válida, com o mesmo exercício e o mesmo ano projetado. Em
    17/09/2026 isso atingia 176 dos 1.652 entes com plano de amortização e 219
    dos 1.890 com comparativo de receita — somar as versões dobraria o saldo
    devedor de um em cada dez RPPS, e o gráfico desenharia duas curvas como se
    fossem uma.

    A regra é a mesma já usada no CRP: a emissão mais recente é a posição.
    """
    envios = [l.get("envio") for l in linhas if l.get("envio")]
    if not envios:
        return linhas
    ultimo = max(envios)
    return [l for l in linhas if l.get("envio") == ultimo]


#: Vocabulário observado em 17/09/2026, nas 770 notificações da base nacional.
#: A fonte escreve "pendencia" e "pendência", por isso a comparação é sem acento.
_SITUACAO_IRREGULAR = "irregular"
_SITUACAO_ENCERRADA = ("sem pendencia", "sem pendencias", "cancelada")


def _classificar_notificacao(situacao: Optional[str]) -> str:
    """Em que estado a SPREV deixou o item: irregular, encerrado ou em curso.

    Quem classifica é a fonte, não o painel. Ela escreve "Situacao irregular"
    com todas as letras em quatro das nove situações que usa, e escreve
    "Item sem pendencia" ou "Notificacao cancelada" quando encerrou. Derivar
    irregularidade por conta própria — comparando a data de preclusão com hoje,
    por exemplo — produziria uma acusação que o regulador não fez.

    O que sobra fica em curso: respondida, aguardando resposta, em análise. Sem
    situação declarada também é "em curso", porque afirmar encerramento sem
    respaldo é o erro mais caro dos três.
    """
    termo = _normalizar_situacao(situacao)
    if _SITUACAO_IRREGULAR in termo:
        return "irregular"
    if any(marca in termo for marca in _SITUACAO_ENCERRADA):
        return "encerrado"
    return "em_curso"


#: Os três fundos do RPPS, como o SICONFI os codifica no Anexo 04. É este mapa
#: que responde à pergunta que o CADPREV não responde: quanto do patrimônio está
#: em cada regime. O CADPREV traz a carteira ativo a ativo, mas sem o plano de
#: cada ativo — o projeto chama isso de Nível B e documenta a limitação. O
#: Anexo 04 não dá o plano de cada ativo, dá o total de cada fundo, que é
#: exatamente o que a tela de composição precisa.
_FUNDOS_DO_RREO = (
    ("capitalizado", "Fundo em capitalização",
     "InvestimentosDoRPPSPrevidenciario", "RREO4CaixaDoRPPSPrevidenciario",
     "TotalReceitasRPPSPrevidenciario", "TotalDasDespesasRPPSPrevidenciario"),
    ("reparticao", "Fundo em repartição",
     "InvestimentosEAplicacoesFundoEmReparticao",
     "CaixaEEquivalenteDeCaixaFundoEmReparticao",
     "TotalReceitasRPPSFinanceiro", "TotalDasDespesasRPPSFinanceiro"),
    ("administracao", "Taxa de administração",
     "InvestimentosEAplicacoesAdministracaoDoRPPS",
     "CaixaEEquivalenteDeCaixaAdministracaoDoRPPS",
     "TotalDasReceitasDaAdministracaoRPPS", "TotalDasDespesasDaAdministracaoRPPS"),
)

_COLUNA_SALDO = "SALDO ATUAL"
_COLUNA_RECEITA = "RECEITAS REALIZADAS ATÉ O BIMESTRE (b)"
_COLUNA_DESPESA = "DESPESAS PAGAS ATÉ O BIMESTRE (f)"


#: Segmentos da carteira do CADPREV cuja presença no Anexo 04 do SICONFI não é
#: uniforme entre os entes. Imóveis é o caso medido: em 22/09/2026, dos 857 RPPS
#: confrontáveis, 57 declaravam imóveis, e tirá-los da conta aproximava as duas
#: fontes em 40 deles e afastava nos outros 17. Em Diadema/SP a carteira tem 70%
#: em imóveis e a divergência é de −70,03%: tirando os imóveis, zero — o
#: município não os leva ao Anexo 04. No Rio de Janeiro/RJ são 59,9% em imóveis
#: e a divergência é de −0,29%: ali eles entram. Não é erro de nenhum dos dois,
#: é prática contábil que difere entre entes, e por isso o painel mostra a conta
#: dos dois jeitos em vez de escolher um.
_SEGMENTO_IMOVEIS = "imoveis"


def _montar_contabil(store: Store, cnpj: str,
                     total_da_carteira: Optional[float] = None,
                     segmentos_da_carteira: Optional[Sequence[Mapping[str, Any]]] = None
                     ) -> Dict[str, Any]:
    """O demonstrativo previdenciário do SICONFI, e o confronto com o CADPREV.

    Duas apurações independentes do mesmo patrimônio: o CADPREV pela declaração
    do RPPS, ativo a ativo; o SICONFI pela contabilidade do ente, fundo a fundo.
    Em Vitória, na competência de junho de 2026, elas diferem em 0,18%.

    A divergência é mostrada, não resolvida. Quando duas fontes públicas
    discordam sobre o mesmo fato, apresentar um número só — qualquer que seja —
    é esconder o achado mais interessante que o cruzamento produz.
    """
    if not store.tem_tabela("SICONFI_RREO"):
        return {"disponivel": False}
    linhas = _varios(store, "siconfi_rreo",
                     "exercicio, periodo, coluna, cod_conta, valor, demonstrativo",
                     cnpj, ordem="exercicio DESC, periodo DESC", limite=800)
    if not linhas:
        return {"disponivel": False}

    recente = max((l["exercicio"], l["periodo"]) for l in linhas)
    do_periodo = [l for l in linhas
                  if (l["exercicio"], l["periodo"]) == recente]
    por_conta = {(l["coluna"], l["cod_conta"]): l["valor"] for l in do_periodo}

    fundos, investido, caixa, com_saldo = [], 0.0, 0.0, False
    negativo = False
    for chave, rotulo, cod_inv, cod_caixa, cod_rec, cod_desp in _FUNDOS_DO_RREO:
        inv = por_conta.get((_COLUNA_SALDO, cod_inv))
        cx = por_conta.get((_COLUNA_SALDO, cod_caixa))
        receita = por_conta.get((_COLUNA_RECEITA, cod_rec))
        despesa = por_conta.get((_COLUNA_DESPESA, cod_desp))
        if inv is None and cx is None and receita is None and despesa is None:
            continue
        if inv is not None or cx is not None:
            com_saldo = True
            investido += inv or 0.0
            caixa += cx or 0.0
        # Saldo negativo não é carteira. Em 17/09/2026, 154 dos 1.432 entes
        # confrontáveis traziam ao menos uma conta de saldo negativa — quase
        # todas de caixa, que é onde cabe um descoberto bancário ou uma
        # reclassificação contábil. Somá-la à carteira e dividir por esse total
        # produz divergência a partir de um denominador que pode ser negativo:
        # Igarassu/PE aparecia com −130% contra o CADPREV. O número existe e é
        # declarado; o que não existe é a comparação.
        if (inv is not None and inv < 0) or (cx is not None and cx < 0):
            negativo = True
        fundos.append({
            "chave": chave, "rotulo": rotulo,
            "investimentos": inv, "caixa": cx,
            "receitas": receita, "despesas": despesa,
            "resultado": (None if receita is None and despesa is None
                          else (receita or 0.0) - (despesa or 0.0)),
        })
    if not fundos:
        return {"disponivel": False}

    # Ausência de saldo não é saldo zero. Em 17/09/2026, 280 dos 1.712 entes com
    # Anexo 04 declaravam receitas e despesas sem declarar o saldo das
    # aplicações. Somar `inv or 0` transformava esse silêncio em zero e produzia
    # um confronto de −100% contra a carteira do CADPREV: uma divergência que a
    # fonte nunca afirmou, em um de cada seis RPPS.
    # Um fundo que movimenta receita e não declara saldo é um buraco no total.
    # Sem esta conferência o confronto compara um fragmento do SICONFI contra a
    # carteira inteira do CADPREV: Doutor Maurício Cardoso/RS declarava só os
    # setenta e cinco mil da taxa de administração, e o painel anunciava 99,8%
    # de divergência contra os quarenta e sete milhões da carteira.
    completo = com_saldo and not negativo and all(
        fundo["investimentos"] is not None or fundo["caixa"] is not None
        for fundo in fundos
        if fundo["receitas"] is not None or fundo["despesas"] is not None)
    total = round(investido + caixa, 2) if com_saldo else None
    for fundo in fundos:
        recursos = (None if fundo["investimentos"] is None and fundo["caixa"] is None
                    else (fundo["investimentos"] or 0.0) + (fundo["caixa"] or 0.0))
        fundo["recursos"] = None if recursos is None else round(recursos, 2)
        fundo["perc"] = (_pct(recursos, total)
                         if recursos is not None and total else None)

    resultado = {
        "disponivel": True,
        "exercicio": recente[0],
        "periodo": recente[1],
        "demonstrativo": do_periodo[0].get("demonstrativo"),
        "fundos": fundos,
        "com_saldo": com_saldo,
        "saldo_negativo": negativo,
        "saldo_completo": completo,
        "investimentos": round(investido, 2) if com_saldo else None,
        "caixa": round(caixa, 2) if com_saldo else None,
        "total": total,
    }

    # O confronto. A carteira do CADPREV inclui disponibilidades financeiras
    # como segmento, e é por isso que a comparação soma investimentos e caixa do
    # lado do SICONFI: comparar só os investimentos deixaria de fora justamente
    # a parte que o outro lado conta.
    if total_da_carteira and total is not None and completo:
        diferenca = total - total_da_carteira
        confronto = {
            "cadprev": round(total_da_carteira, 2),
            "siconfi": round(total, 2),
            "diferenca": round(diferenca, 2),
            "perc": round(diferenca / total_da_carteira * 100, 2),
        }
        confronto.update(_imoveis_no_confronto(segmentos_da_carteira,
                                               total_da_carteira, total))
        resultado["confronto"] = confronto
    return resultado


def _imoveis_no_confronto(segmentos: Optional[Sequence[Mapping[str, Any]]],
                          total_cadprev: float,
                          total_siconfi: float) -> Dict[str, Any]:
    """O que a diferença seria sem os imóveis — quando o ente tem imóveis.

    O segmento existe na carteira do CADPREV e a conta de aplicações do Anexo
    04 nem sempre o alcança. Em vez de decidir por conta própria qual dos dois
    lados está certo, o painel oferece a segunda conta e deixa o leitor ver de
    que lado ela cai: quando a divergência desaparece ao tirar os imóveis, o
    ente não os levou ao balanço; quando ela aparece, levou.

    As disponibilidades financeiras **não** entram nesta ressalva, e é de
    propósito: o painel soma investimentos e caixa do lado do SICONFI
    justamente para que os dois lados contem a mesma coisa. Elas são a
    assimetria que já foi resolvida, não uma em aberto.
    """
    if not segmentos:
        return {}
    valor = sum(s.get("valor") or 0.0 for s in segmentos
                if _normalizar_situacao(s.get("rotulo") or "")
                .startswith(_SEGMENTO_IMOVEIS))
    if valor <= 0:
        return {}
    restante = total_cadprev - valor
    return {
        "imoveis": round(valor, 2),
        "perc_imoveis": _pct(valor, total_cadprev),
        # Sem base positiva não há razão a calcular: um ente cuja carteira é
        # só imóveis não tem "o resto" com que comparar.
        "perc_sem_imoveis": (round((total_siconfi - restante) / restante * 100, 2)
                             if restante > 0 else None),
    }


# O balanço patrimonial do ente, nas contas que dizem respeito ao RPPS. O
# prefixo "P" é da própria API do SICONFI.
_DCA_PROVISAO = "P2.2.7.2.0.00.00"
_DCA_ATIVO = "P1.0.0.0.0.00.00"
_DCA_INSUFICIENCIA = "P2.2.7.2.2.05.00"
_DCA_INVESTIMENTOS = ("P1.1.4.0.0.00.00", "P1.2.1.3.0.00.00")

#: A decomposição da provisão por fundo, como o plano de contas a separa. Cada
#: uma é opcional: numa amostra de 15 RPPS em 22/09/2026, as contas de
#: capitalização apareciam em 13 e as de repartição em 2 — a maioria dos
#: municípios não tem fundo em repartição, e exigir as quatro esconderia todos.
_DCA_FUNDOS = (
    ("reparticao", "Fundo em repartição",
     "P2.2.7.2.1.01.00", "P2.2.7.2.1.02.00"),
    ("capitalizacao", "Fundo em capitalização",
     "P2.2.7.2.1.03.00", "P2.2.7.2.1.04.00"),
)


def _montar_contabil_anual(store: Store, cnpj: str,
                           atuaria: Optional[Mapping[str, Any]] = None
                           ) -> Dict[str, Any]:
    """A provisão matemática como a contabilidade do ente a reconhece.

    O DRAA traz o compromisso avaliado pelo atuário; o Anexo I-AB da DCA traz o
    mesmo compromisso registrado no balanço, por outro profissional e sob outra
    norma. Divergir aí não é erro de ninguém por definição — é a distância entre
    duas apurações do mesmo passivo, e é exatamente o tipo de coisa que só
    aparece quando as duas ficam lado a lado.

    **O total vem da fonte, nunca da soma das partes.** As contas ``2.2.7.2.2``
    são redutoras, publicadas com sinal positivo: em Vitória elas somam
    R$ 4,8 bi que não entram no total de R$ 5,66 bi. Somar componentes daria um
    passivo que o balanço não declara.

    **O alinhamento temporal é a parte que mais facilmente sairia errada.** O
    DRAA do exercício N descreve a posição de 31/12 de N−1, e o balanço do
    exercício N fecha em 31/12 de N. O par que compara a mesma data é DRAA(N)
    com DCA(N−1) — e o confronto só acontece nessa relação. Fora dela os
    números aparecem, e a comparação não.
    """
    if not store.tem_tabela("SICONFI_DCA"):
        return {"disponivel": False}
    linhas = _varios(store, "siconfi_dca",
                     "exercicio, coluna, cod_conta, conta, valor", cnpj,
                     ordem="exercicio DESC", limite=2000)
    if not linhas:
        return {"disponivel": False}

    exercicio = max(l["exercicio"] for l in linhas
                    if l.get("exercicio") is not None)
    do_exercicio = [l for l in linhas if l.get("exercicio") == exercicio]
    por_conta = {l["cod_conta"]: l.get("valor") for l in do_exercicio}

    fundos = []
    for chave, rotulo, cod_concedidos, cod_a_conceder in _DCA_FUNDOS:
        concedidos = por_conta.get(cod_concedidos)
        a_conceder = por_conta.get(cod_a_conceder)
        if concedidos is None and a_conceder is None:
            continue
        fundos.append({
            "chave": chave, "rotulo": rotulo,
            "concedidos": concedidos, "a_conceder": a_conceder,
            "total": round((concedidos or 0.0) + (a_conceder or 0.0), 2),
        })

    investido = [por_conta.get(c) for c in _DCA_INVESTIMENTOS]
    ficha: Dict[str, Any] = {
        "disponivel": True,
        "exercicio": exercicio,
        "data_base": (do_exercicio[0].get("coluna") if do_exercicio else None),
        "provisao": por_conta.get(_DCA_PROVISAO),
        "provisao_negativa": bool((por_conta.get(_DCA_PROVISAO) or 0) < 0),
        "insuficiencia": por_conta.get(_DCA_INSUFICIENCIA),
        "ativo": por_conta.get(_DCA_ATIVO),
        "investimentos": (round(sum(v for v in investido if v is not None), 2)
                          if any(v is not None for v in investido) else None),
        "fundos": fundos,
        "contas": len(do_exercicio),
    }
    ficha["confronto"] = _confrontar_provisao(ficha, atuaria)
    return ficha


def _confrontar_provisao(contabil: Mapping[str, Any],
                         atuaria: Optional[Mapping[str, Any]]
                         ) -> Optional[Dict[str, Any]]:
    """A provisão atuarial contra a contábil, quando as datas batem.

    Só compara o par DRAA(N) × DCA(N−1): fora dele são avaliações de datas
    diferentes, e a diferença mediria o tempo, não a divergência.
    """
    contabil_valor = contabil.get("provisao")
    if contabil_valor is None or not atuaria or not atuaria.get("disponivel"):
        return None
    # Provisão negativa não é passivo menor: é lançamento que a contabilidade
    # publicou com sinal invertido ou conta redutora onde não devia. Medido em
    # 22/09/2026 sobre 198 entes com balanço: dois casos, Goianésia/GO com
    # −R$ 105,4 mi e Morrinhos/GO com −R$ 15,6 mi. O número é declarado e fica
    # na tela; o que não existe é a razão contra uma avaliação positiva.
    if contabil_valor <= 0:
        return None
    exercicio_draa = atuaria.get("exercicio")
    exercicio_dca = contabil.get("exercicio")
    if exercicio_draa is None or exercicio_dca is None:
        return None

    atuarial, tem = 0.0, False
    for bloco in atuaria.get("blocos") or []:
        provisoes = (bloco.get("resultado") or {}).get("provisoes")
        if provisoes:
            atuarial += provisoes
            tem = True
    if not tem or not atuarial:
        return None

    alinhado = exercicio_draa == exercicio_dca + 1
    diferenca = round(contabil_valor - atuarial, 2)
    return {
        "exercicio_draa": exercicio_draa,
        "exercicio_dca": exercicio_dca,
        "alinhado": alinhado,
        "atuarial": round(atuarial, 2),
        "contabil": round(contabil_valor, 2),
        "diferenca": diferenca if alinhado else None,
        "perc": (round(diferenca / atuarial * 100, 2)
                 if alinhado and atuarial else None),
    }


def _montar_conformidade(store: Store, cnpj: str,
                         hoje: Optional[str] = None) -> Dict[str, Any]:
    """O que a SPREV apontou sobre este ente, e o que segue em aberto.

    Não é análise do painel: é o que o regulador registrou, com o prazo que
    ele mesmo deu. O painel só separa o que ainda corre do que já encerrou.
    """
    if not store.tem_tabela("DRAA_NOTIFICACAO"):
        return {"disponivel": False}
    hoje = hoje or _hoje()
    linhas = _varios(
        store, "draa_notificacao",
        "numero, tipo_documento, item_analise, situacao_item, notificacao, "
        "preclusao, resposta, prazo_resposta", cnpj,
        ordem="notificacao DESC", limite=400)
    entregas = _varios(store, "draa_encaminhamento",
                       "exercicio, envio, situacao", cnpj,
                       ordem="exercicio DESC, envio DESC", limite=30)
    if not linhas:
        return {"disponivel": True, "itens": [], "total": 0,
                "irregular": 0, "em_curso": 0, "encerrado": 0,
                "entregas": entregas}

    # A fonte repete notificações: 46 das 770 linhas nacionais de 17/09/2026
    # são cópias exatas em todas as colunas. Exibi-las duas vezes sugeriria dois
    # apontamentos onde há um, e inflaria a contagem de irregulares.
    vistas, unicas = set(), []
    for l in linhas:
        assinatura = tuple(l.get(c) for c in (
            "numero", "item_analise", "situacao_item", "notificacao",
            "preclusao", "resposta", "prazo_resposta"))
        if assinatura in vistas:
            continue
        vistas.add(assinatura)
        unicas.append(l)
    linhas = unicas

    itens = [{
        "numero": l.get("numero"),
        "documento": l.get("tipo_documento"),
        "item": l.get("item_analise"),
        "situacao": l.get("situacao_item"),
        "estado": _classificar_notificacao(l.get("situacao_item")),
        "notificacao": l.get("notificacao"),
        "preclusao": l.get("preclusao"),
        "resposta": l.get("resposta"),
        "prazo_dias": l.get("prazo_resposta"),
    } for l in linhas]

    contagem = {estado: sum(1 for i in itens if i["estado"] == estado)
                for estado in ("irregular", "em_curso", "encerrado")}
    return dict({
        "disponivel": True,
        "referencia": hoje,
        "itens": itens[:60],
        "total": len(itens),
        "entregas": entregas,
    }, **contagem)


def _rotulo_do_fundo(plano: Optional[str], massa: Optional[str]) -> str:
    """Como o painel chama o par plano×massa que a fonte declara separado."""
    qual = massas.normalizar(massa)
    nome = (plano or "Plano não declarado").strip()
    if qual == massas.MILITAR:
        return nome + " · militar"
    if qual == massas.CIVIL:
        return nome + " · civil"
    return nome


def _por_fundo(linhas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Separa as linhas por plano e massa, que a fonte nunca soma entre si.

    O DRAA declara um conjunto de linhas por plano (Previdenciário, Financeiro,
    Mantidos pelo Tesouro) e por massa (Civil, Militar). Cada conjunto é uma
    avaliação própria, com seus próprios anos e seus próprios fluxos. Somá-los
    duplica o ano e desenha duas curvas como se fossem uma — em 17/09/2026 isso
    atingia 51 entes no plano de amortização e 263 no comparativo de receita.
    """
    caixas: Dict[tuple, List[Dict[str, Any]]] = {}
    for linha in linhas:
        caixas.setdefault(
            ((linha.get("plano") or "").strip(),
             massas.normalizar(linha.get("massa")) or ""), []).append(linha)
    blocos = []
    for (plano, massa), grupo in caixas.items():
        blocos.append({"plano": plano or None, "massa": massa or None,
                       "militar": massa == massas.MILITAR,
                       "rotulo": _rotulo_do_fundo(plano, massa),
                       "linhas": grupo})
    # Civil antes de militar; dentro de cada massa, o conjunto maior primeiro.
    blocos.sort(key=lambda b: (b["militar"], -len(b["linhas"]), b["rotulo"]))
    return blocos


def _montar_amortizacao(store: Store, cnpj: str) -> Dict[str, Any]:
    """O plano de amortização ano a ano — a única série temporal da API.

    O DRAA_FLUXO_ATUARIAL dá totais projetados, não a curva. Este endpoint dá a
    curva: saldo devedor, juros, amortização e aporte de cada ano até a
    quitação. É com ele que se vê se o plano de fato zera o déficit, e quando.

    Uma curva por plano e por massa. O Maranhão, por exemplo, tem dois planos de
    amortização no exercício de 2026 — R$ 91,9 bi de aportes civis e R$ 93,4 bi
    de aportes militares. Somados, viravam um saldo que não existe em lugar
    nenhum e um ano de quitação que não é o de nenhum dos dois.
    """
    if not store.tem_tabela("DRAA_PLANO_AMORTIZACAO"):
        return {"disponivel": False}
    linhas = _varios(
        store, "draa_plano_amortizacao",
        "exercicio, plano, massa, ano, saldo_inicial, juros, amortizacao, "
        "pagamentos, aporte, saldo_final, taxa_juros, envio", cnpj,
        ordem="exercicio DESC, ano", limite=2000)
    if not linhas:
        return {"disponivel": False}

    # Uma avaliação por vez, e uma submissão por avaliação.
    exercicio = max(l["exercicio"] for l in linhas if l.get("exercicio"))
    recentes = _do_ultimo_envio([l for l in linhas
                                 if l.get("exercicio") == exercicio])

    blocos = []
    for fundo in _por_fundo(recentes):
        serie = sorted(fundo["linhas"], key=lambda l: l.get("ano") or 0)
        anos = [{
            "ano": l.get("ano"),
            "saldo_inicial": l.get("saldo_inicial"),
            "juros": l.get("juros"),
            "amortizacao": l.get("amortizacao"),
            "pagamentos": l.get("pagamentos"),
            "aporte": l.get("aporte"),
            "saldo_final": l.get("saldo_final"),
        } for l in serie]
        if not anos:
            continue
        quitacao = next((a["ano"] for a in anos
                         if (a["saldo_final"] or 0) <= 0.005), None)
        blocos.append({
            "rotulo": fundo["rotulo"],
            "plano": fundo["plano"],
            "massa": fundo["massa"],
            "militar": fundo["militar"],
            "taxa_juros": serie[0].get("taxa_juros"),
            "anos": anos,
            "primeiro_ano": anos[0]["ano"],
            "ultimo_ano": anos[-1]["ano"],
            "saldo_inicial": anos[0]["saldo_inicial"],
            "ano_quitacao": quitacao,
            "total_juros": round(sum(a["juros"] or 0.0 for a in anos), 2),
            "total_amortizacao": round(sum(a["amortizacao"] or 0.0 for a in anos), 2),
            "total_aporte": round(sum(a["aporte"] or 0.0 for a in anos), 2),
        })
    if not blocos:
        return {"disponivel": False}
    return {
        "disponivel": True,
        "exercicio": exercicio,
        "blocos": blocos,
        "tem_militar": any(b["militar"] for b in blocos),
    }


def _montar_projetado_executado(store: Store, cnpj: str) -> Dict[str, Any]:
    """O que o atuário projetou contra o que o RPPS executou.

    A diferença vem calculada da fonte. O painel confere a conta em vez de
    refazê-la: divergir do que a fonte publica é, ele próprio, um achado.

    Uma tabela por plano e por massa: o mesmo fluxo aparece uma vez em cada, e
    empilhá-los listava a mesma rubrica duas vezes com valores de fundos
    diferentes.
    """
    if not store.tem_tabela("DRAA_COMPARATIVO_RECEITA"):
        return {"disponivel": False}
    linhas = _varios(
        store, "draa_comparativo_receita",
        "exercicio, plano, massa, exercicio_inicial, codigo_fluxo, fluxo, "
        "projetado, executado, diferenca, envio", cnpj,
        ordem="exercicio DESC", limite=2000)
    if not linhas:
        return {"disponivel": False}

    exercicio = max(l["exercicio"] for l in linhas if l.get("exercicio"))
    do_exercicio = _do_ultimo_envio(
        [l for l in linhas if l.get("exercicio") == exercicio])

    blocos = []
    inconsistentes = 0
    for fundo in _por_fundo(do_exercicio):
        itens = []
        for l in fundo["linhas"]:
            proj, exe = l.get("projetado"), l.get("executado")
            dif = l.get("diferenca")
            # A conferência: a fonte define diferença como PROJETADO menos
            # EXECUTADO, e não o contrário. Conferido contra a base nacional de
            # 17/09/2026: nesse sentido nenhuma das 79.986 linhas destoa; no
            # sentido inverso, 31.236 destoariam. Um sinal trocado aqui
            # produziria trinta mil acusações falsas.
            if proj is not None and exe is not None and dif is not None:
                if abs((proj - exe) - dif) > max(0.02, abs(dif) * 0.0001):
                    inconsistentes += 1
            # Item com projetado, executado e diferença todos em zero não diz
            # nada sobre o plano — enche a tela e empurra para baixo o que diz.
            if not any((proj, exe, dif)):
                continue
            itens.append({
                "codigo": l.get("codigo_fluxo"),
                "fluxo": l.get("fluxo"),
                "projetado": proj,
                "executado": exe,
                "diferenca": dif,
                "desvio": (round((exe - proj) / abs(proj) * 100, 1)
                           if proj not in (None, 0) and exe is not None else None),
            })
        if not itens:
            continue
        itens.sort(key=lambda i: -abs(i["diferenca"] or 0.0))
        blocos.append({
            "rotulo": fundo["rotulo"],
            "plano": fundo["plano"],
            "massa": fundo["massa"],
            "militar": fundo["militar"],
            "itens": itens[:20],
            "diferenca_total": round(sum(i["diferenca"] or 0.0 for i in itens), 2),
        })
    if not blocos:
        return {"disponivel": False}
    return {
        "disponivel": True,
        "exercicio": exercicio,
        "exercicio_referencia": (do_exercicio[0].get("exercicio_inicial")
                                 if do_exercicio else None),
        "blocos": blocos,
        "tem_militar": any(b["militar"] for b in blocos),
        "conferencia_falhou": inconsistentes,
    }


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
    """Massa de participantes, separada por massa antes de somar qualquer coisa.

    Civil e militar são populações distintas, com avaliação atuarial distinta e
    nomenclatura distinta, e a fonte as separa em campos diferentes: no civil o
    papel está em ``tp_populacao``; no militar esse campo diz sempre "Militares"
    e o papel está em ``no_cat_populacao``. Agrupar tudo por ``tp_populacao``,
    como o painel fazia, jogava os militares num balde único — ativos, reserva e
    pensionistas somados — e os deixava fora de ativos e de inativos. Nos 26
    governos estaduais isso escondia de 14% a 39% da população declarada.

    Ver ``cadprev.massas``.
    """
    linhas = _varios(store, "draa_estatistica",
                     "exercicio, massa, tipo_populacao, categoria_populacao,"
                     " qt_masculino, qt_feminino, folha_masculino, folha_feminino",
                     cnpj, ordem="exercicio DESC", limite=4000)
    if not linhas:
        return {"disponivel": False}

    exercicio = linhas[0]["exercicio"]
    # chave da massa -> rótulo do grupo -> contagem
    por_massa: Dict[str, Dict[str, Dict[str, Any]]] = {}
    papeis: Dict[str, Dict[str, int]] = {}
    ordem_das_massas: List[str] = []

    for linha in linhas:
        if linha["exercicio"] != exercicio:
            continue  # só o exercício mais recente
        qual = massas.normalizar(linha.get("massa")) or massas.CIVIL
        if qual not in por_massa:
            por_massa[qual] = {}
            papeis[qual] = defaultdict(int)
            ordem_das_massas.append(qual)
        rotulo, termo = massas.rotulo(
            qual, linha.get("tipo_populacao"), linha.get("categoria_populacao"))
        alvo = por_massa[qual].setdefault(
            rotulo, {"pessoas": 0, "folha": 0.0, "fonte": termo})
        pessoas = (linha["qt_masculino"] or 0) + (linha["qt_feminino"] or 0)
        alvo["pessoas"] += pessoas
        alvo["folha"] += (linha["folha_masculino"] or 0.0) + (linha["folha_feminino"] or 0.0)
        papeis[qual][massas.papel(qual, linha.get("tipo_populacao"),
                                  linha.get("categoria_populacao"))] += pessoas

    blocos = []
    for qual in ordem_das_massas:
        grupos = [{"rotulo": rotulo, "fonte": dados["fonte"],
                   "pessoas": int(dados["pessoas"]),
                   "folha": round(dados["folha"], 2)}
                  for rotulo, dados in sorted(por_massa[qual].items(),
                                              key=lambda kv: kv[1]["pessoas"],
                                              reverse=True)]
        conta = papeis[qual]
        ativos = conta.get(massas.ATIVO, 0)
        inativos = conta.get(massas.INATIVO, 0)
        pensionistas = conta.get(massas.PENSIONISTA, 0)
        beneficiarios = inativos + pensionistas
        blocos.append({
            "chave": qual.lower(),
            "rotulo": qual,
            "militar": qual == massas.MILITAR,
            "grupos": grupos,
            "ativos": int(ativos),
            "inativos": int(inativos),
            "pensionistas": int(pensionistas),
            "beneficiarios": int(beneficiarios),
            "pessoas": int(sum(g["pessoas"] for g in grupos)),
            "folha": round(sum(g["folha"] for g in grupos), 2),
            "razao_ativos_inativos": (round(ativos / beneficiarios, 2)
                                      if beneficiarios else None),
        })
    # Militar depois de civil, sempre — mesmo quando é o maior dos dois.
    blocos.sort(key=lambda b: (b["militar"], -b["pessoas"]))

    tem_militar = any(b["militar"] for b in blocos)
    ativos = sum(b["ativos"] for b in blocos)
    beneficiarios = sum(b["beneficiarios"] for b in blocos)
    ficha = {
        "disponivel": True,
        "exercicio": exercicio,
        "massas": blocos,
        "tem_militar": tem_militar,
        # O ente inteiro: é o que a aba de caixa usa, e a folha paga não
        # distingue farda de terno.
        "grupos": [dict(g, massa=b["rotulo"]) for b in blocos for g in b["grupos"]],
        "ativos": int(ativos),
        "inativos": int(beneficiarios),
        "razao_ativos_inativos": (round(ativos / beneficiarios, 2)
                                  if beneficiarios else None),
    }
    if tem_militar:
        ficha["nota_nomenclatura"] = massas.NOTA_NOMENCLATURA
    return ficha


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

    def _competencia(ponto) -> str:
        return "{:04d}-{:02d}".format(ponto["ano"], ponto["mes"])

    return {
        "disponivel": True,
        "serie": serie,
        # A janela da série, para que "ingressos no período" diga que período.
        "primeira_competencia": _competencia(serie[0]),
        "ultima_competencia": _competencia(serie[-1]),
        "competencias": len(serie),
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


#: O percentual vem da fonte com duas casas decimais. Meio centésimo de ponto
#: acima do teto é arredondamento dela, não excesso do RPPS — e a diferença
#: entre as duas leituras é a diferença entre informar e acusar.
MARGEM_DO_LIMITE = 0.05

#: A norma em vigor sobre aplicação dos recursos dos RPPS. Quem declara o teto
#: de cada classe é a API, no próprio registro do ativo (``pc_cmn``) — o painel
#: não mantém tabela de limites, justamente para não ficar defasado quando a
#: norma muda. Esta constante existe só para nomear a norma na tela, e é o
#: único lugar a mudar quando ela for substituída.
NORMA_DOS_INVESTIMENTOS = "Resolução CMN 5.272/2025"

#: A alíquota que a União fixou para a contribuição do militar, e que muitos
#: Estados adotaram. **Não é um piso nem um teto**: cada Estado legisla sobre a
#: sua, e divergir daqui não é irregularidade. Serve para a tela dizer quantos
#: seguiram a referência — informação —, nunca para marcar quem não seguiu.
ALIQUOTA_MILITAR_FEDERAL = 10.5


def _da_competencia_recente(linhas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Só as linhas da competência mais recente do conjunto.

    A mesma disciplina de ``_do_ultimo_envio`` no DRAA: a fonte pode devolver
    várias versões da mesma coisa, e o painel escolhe uma em vez de somar.
    """
    competencias = [(l.get("ano"), l.get("mes")) for l in linhas
                    if l.get("ano") is not None and l.get("mes") is not None]
    if not competencias:
        return linhas
    recente = max(competencias)
    return [l for l in linhas if (l.get("ano"), l.get("mes")) == recente]


def _competencias_do_dair(store: Store) -> Dict[str, Any]:
    """A que mês a carteira do país se refere — pergunta que a tela não
    respondia, e que passou a ter mais de uma resposta possível.

    A competência de referência é **a que o país declarou**, não a mais recente
    que existe no banco. A distinção deixou de ser acadêmica quando a base
    passou a guardar vários meses: a varredura nacional traz a competência
    fechada, e depois o ``dair-atrasados`` traz, ente a ente, o último mês de
    quem declarou adiantado e de quem parou antes. Escolher o mês mais recente
    faria seis RPPS que entregaram julho cedo definirem a data do patrimônio
    nacional, e os outros 1.815 sumiriam do agregado por não terem declarado
    esse mês.

    Então a referência é a competência com mais declarantes — o mês da
    varredura tem mil e oitocentos, o de um adiantado tem meia dúzia, e a
    diferença é de duas ordens de grandeza, não de margem. Empate desfeito pela
    mais recente.
    """
    if not store.tem_tabela("DAIR_CARTEIRA"):
        return {}
    linhas = [dict(l) for l in store.consultar(
        "SELECT ano, mes, COUNT(DISTINCT cnpj_ente) AS entes "
        "FROM dair_carteira WHERE ano IS NOT NULL AND mes IS NOT NULL "
        "GROUP BY ano, mes ORDER BY ano DESC, mes DESC")]
    if not linhas:
        return {}
    escolhida = max(linhas, key=lambda l: (l["entes"], l["ano"], l["mes"]))
    return {
        "ano": escolhida["ano"],
        "mes": escolhida["mes"],
        "competencia": "{:04d}-{:02d}".format(escolhida["ano"], escolhida["mes"]),
        "entes": escolhida["entes"],
        "varias": len(linhas) > 1,
        "disponiveis": ["{:04d}-{:02d}".format(l["ano"], l["mes"])
                        for l in linhas],
    }


def _identificar(linha: Mapping[str, Any]) -> Dict[str, Any]:
    """Como o ativo aparece na tela: nome, descrição da fonte e, se for título
    público, sigla e vencimento.

    A escolha do nome está em ``cadprev.ativos`` e vale para as duas telas — a
    ficha mostra as dez maiores posições e a tela detalhada mostra todas, e
    dois critérios de nome para o mesmo ativo seriam duas respostas para a
    mesma pergunta.
    """
    escolha = ativos.nome(linha.get("nome_ativo"),
                          linha.get("identificacao_ativo"),
                          linha.get("tipo_ativo"))
    dados: Dict[str, Any] = {
        "nome": escolha["rotulo"],
        "nome_de": escolha["campo"],
        "identificacao": linha.get("identificacao_ativo"),
    }
    # Só para quem a fonte descreve como título: num fundo, "NTN-B" no nome é
    # a estratégia do fundo, não o papel que o RPPS tem em carteira.
    classe = (linha.get("tipo_ativo") or "")
    if "ítulos Públicos" in classe or "itulos Publicos" in classe:
        reconhecido = ativos.titulo(escolha["rotulo"])
        if reconhecido:
            dados["titulo"] = reconhecido
    return dados


def _resumo_comparavel(linhas: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Total e alocação por segmento de uma competência — o que o comparativo
    precisa, e nada além disso.

    Quem declarou adiantado tem duas carteiras na base: a do mês que o país
    inteiro declarou e a dele, mais nova. A ficha mostra a mais nova, porque é
    a posição real do RPPS hoje; o comparativo usa a da competência de
    referência, porque comparar agosto de um com junho de outro é comparar
    datas, não carteiras. Guardar o bloco inteiro duas vezes dobraria a ficha —
    então o que sobrevive à segunda leitura é só o total e os percentuais por
    segmento, que é de onde saem os indicadores do comparativo.
    """
    if not linhas:
        return None
    total = sum(l.get("valor_total") or 0.0 for l in linhas)
    da_fonte = all(l.get("perc_recursos") is not None for l in linhas)
    por_segmento: Dict[str, float] = {}
    for linha in linhas:
        nome = (linha.get("segmento") or "Não informado").strip()
        perc = (linha.get("perc_recursos") or 0.0) if da_fonte else _pct(
            linha.get("valor_total") or 0.0, total)
        por_segmento[nome] = por_segmento.get(nome, 0.0) + perc
    ano, mes = linhas[0].get("ano"), linhas[0].get("mes")
    return {
        "disponivel": True,
        "total": round(total, 2),
        "ano": ano,
        "mes": mes,
        "competencia": ("{:04d}-{:02d}".format(ano, mes)
                        if ano and mes else None),
        "segmentos": [{"rotulo": nome, "perc": round(perc, 2)}
                      for nome, perc in sorted(por_segmento.items(),
                                               key=lambda kv: -kv[1])],
    }


def _montar_carteira_ente(store: Store, cnpj: str,
                          linhas_fora: Optional[AbstractSet[int]] = None,
                          referencia: Optional[Mapping[str, Any]] = None
                          ) -> Dict[str, Any]:
    """Composição da carteira, enquadramento por classe e maiores posições.

    **A ficha mostra a competência do próprio ente.** A base guarda mais de um
    mês de DAIR, e cada RPPS declara no seu ritmo: em 22/09/2026, 305 já tinham
    declarado julho ou agosto enquanto 261 não tinham chegado a junho, a
    competência de referência do painel. Mostrar a todos a mesma competência
    deixaria os 261 sem carteira nenhuma — como se nunca tivessem declarado — e
    esconderia dos 305 o demonstrativo que eles já entregaram. A tela diz
    sempre a que mês o número se refere, e avisa quando esse mês não é o da
    referência nacional.

    **O enquadramento é por classe de ativo, não por segmento.** A Resolução do
    CMN não fixa um teto por segmento: fixa um teto por classe, e dentro de um
    mesmo segmento eles são muito diferentes — em 17/09/2026 o segmento Renda
    Fixa reunia classes com teto de 5%, 20%, 80% e 100%. Comparar o total do
    segmento com um desses tetos é comparar coisas diferentes, e era o que este
    painel fazia: acusava 390 dos 1.821 RPPS com carteira de exceder o limite
    legal quando apenas 20 excedem de fato — 371 acusações falsas, e um excesso
    real que a regra antiga não via. Um RPPS com 55,7% em título público (teto
    de 100%) aparecia estourando um teto de 80% que é de outra classe.

    O percentual usado é o que a própria fonte calcula (``pc_recursos``), que
    soma 100% em 1.820 dos 1.821 entes. Quando o painel exclui alguma linha do
    ente — a regra de impossibilidade aritmética —, esse percentual deixa de
    valer sobre o total corrigido e é recalculado; a ficha diz qual dos dois
    está na tela.

    A linha que a base contradiz sai daqui pelo mesmo motivo que sai do total
    nacional: um painel que exclui um lançamento da soma do país e o mantém na
    ficha do ente publica dois números incompatíveis sobre o mesmo fato.
    """
    colunas = ("rowid AS rowid, ano, mes, segmento, tipo_ativo, nome_ativo,"
               " identificacao_ativo, limite_cmn, valor_total, perc_recursos,"
               " pl_fundo, perc_pl_fundo")
    linhas = _varios(store, "dair_carteira", colunas, cnpj,
                     ordem="valor_total DESC", limite=40000)
    linhas_fora = linhas_fora or frozenset()
    if referencia is None:
        referencia = _competencias_do_dair(store)
    referencia = referencia or {}
    ref_ano, ref_mes = referencia.get("ano"), referencia.get("mes")
    # Uma competência por vez. O DAIR é mensal e a base guarda várias — a tela
    # detalhada existe justamente para comparar uma com a outra. Somar junho
    # com agosto contaria o mesmo dinheiro duas vezes, e o total do país
    # cresceria a cada competência ingerida sem que nada tivesse sido aplicado.
    todas = linhas
    linhas = _da_competencia_recente(linhas)
    excluidas = [l for l in linhas if l["rowid"] in linhas_fora]
    linhas = [l for l in linhas if l["rowid"] not in linhas_fora]
    if not linhas:
        return {"disponivel": False,
                "excluidas": len(excluidas)} if excluidas else {"disponivel": False}

    total = sum(linha.get("valor_total") or 0.0 for linha in linhas)
    # Com linha excluída o percentual da fonte passa a se referir a um total
    # que a tela não mostra mais. Aí o painel refaz a conta e avisa.
    da_fonte = not excluidas and all(
        l.get("perc_recursos") is not None for l in linhas)

    def _perc(linha) -> float:
        if da_fonte:
            return linha.get("perc_recursos") or 0.0
        return _pct(linha.get("valor_total") or 0.0, total)

    por_segmento: Dict[str, Dict[str, Any]] = {}
    por_classe: Dict[tuple, Dict[str, Any]] = {}
    for linha in linhas:
        nome = (linha.get("segmento") or "Não informado").strip()
        alvo = por_segmento.setdefault(nome, {"rotulo": nome, "valor": 0.0,
                                              "perc": 0.0})
        alvo["valor"] += linha.get("valor_total") or 0.0
        alvo["perc"] += _perc(linha)

        classe = (linha.get("tipo_ativo") or "Não informada").strip()
        chave = (nome, classe)
        item = por_classe.setdefault(chave, {
            "segmento": nome, "rotulo": classe, "valor": 0.0, "perc": 0.0,
            "limite": linha.get("limite_cmn"), "ativos": 0})
        item["valor"] += linha.get("valor_total") or 0.0
        item["perc"] += _perc(linha)
        item["ativos"] += 1
        if item["limite"] is None:
            item["limite"] = linha.get("limite_cmn")

    segmentos = []
    for dados in sorted(por_segmento.values(), key=lambda s: s["valor"], reverse=True):
        segmentos.append({
            "rotulo": dados["rotulo"],
            "valor": round(dados["valor"], 2),
            "perc": round(dados["perc"], 2),
            "alocacao": dados["rotulo"].strip().lower() != SEGMENTO_DISPONIBILIDADES,
        })

    # Margem de 0,05 ponto: a fonte publica o percentual com duas casas, e um
    # arredondamento dela não é um estouro de limite.
    classes = []
    for dados in sorted(por_classe.values(), key=lambda c: c["valor"], reverse=True):
        limite = dados["limite"]
        perc = round(dados["perc"], 2)
        classes.append({
            "segmento": dados["segmento"],
            "rotulo": dados["rotulo"],
            "valor": round(dados["valor"], 2),
            "perc": perc,
            "limite": limite,
            "ativos": dados["ativos"],
            "excede": bool(limite is not None and perc > limite + MARGEM_DO_LIMITE),
            "folga": (round(limite - perc, 2) if limite is not None else None),
        })

    posicoes = [dict(_identificar(linha), **{
        "segmento": linha.get("segmento"),
        "classe": linha.get("tipo_ativo"),
        "valor": round(linha.get("valor_total") or 0.0, 2),
        "perc_carteira": round(_perc(linha), 2),
        "perc_pl_fundo": linha.get("perc_pl_fundo"),
    }) for linha in linhas[:10]]

    concentrados = [p for p in posicoes if (p["perc_pl_fundo"] or 0) > 10]
    mostradas = sum(p["valor"] for p in posicoes)
    excedidas = [c for c in classes if c["excede"]]
    # "Não enquadrado na Resolução CMN" é a própria fonte dizendo que o ativo
    # está fora da norma. Não é um limite estourado — é outra coisa, e some se
    # for tratada como ausência de limite.
    fora_da_norma = [c for c in classes
                     if "nao enquadrad" in _normalizar_situacao(c["segmento"])
                     or "nao enquadrad" in _normalizar_situacao(c["rotulo"])]
    return {
        "disponivel": True,
        "total": round(total, 2),
        "ativos": len(linhas),
        "total_posicoes": round(mostradas, 2),
        "perc_posicoes": round(sum(p["perc_carteira"] for p in posicoes), 2),
        "segmentos": segmentos,
        "classes": classes,
        "posicoes": posicoes,
        "percentual_da_fonte": da_fonte,
        "classes_fora_do_limite": len(excedidas),
        "fora_do_limite": len(excedidas),  # nome antigo, mesmo conteúdo
        "maior_excesso": (max((c["perc"] - c["limite"] for c in excedidas),
                              default=None)),
        "classes_sem_limite": sum(1 for c in classes if c["limite"] is None),
        "valor_fora_da_norma": round(sum(c["valor"] for c in fora_da_norma), 2),
        "perc_fora_da_norma": round(sum(c["perc"] for c in fora_da_norma), 2),
        "concentracao_pl": len(concentrados),
        "maior_posicao": posicoes[0]["perc_carteira"] if posicoes else 0.0,
        "excluidas": len(excluidas),
        "valor_excluido": round(sum(l.get("valor_total") or 0.0
                                    for l in excluidas), 2),
        "ano": linhas[0].get("ano"),
        "mes": linhas[0].get("mes"),
        "competencia": ("{:04d}-{:02d}".format(linhas[0]["ano"], linhas[0]["mes"])
                        if linhas[0].get("ano") and linhas[0].get("mes") else None),
        **_confrontar_com_a_referencia(linhas, todas, linhas_fora,
                                       ref_ano, ref_mes, referencia),
    }


def _confrontar_com_a_referencia(linhas: List[Dict[str, Any]],
                                 todas: List[Dict[str, Any]],
                                 linhas_fora: AbstractSet[int],
                                 ref_ano: Optional[int], ref_mes: Optional[int],
                                 referencia: Mapping[str, Any]) -> Dict[str, Any]:
    """Diz em que mês está a carteira da ficha e o que sobra para comparar.

    Três situações, e nenhuma delas é a ausência da carteira:

    * o ente está na competência de referência — a ficha e o comparativo leem
      o mesmo demonstrativo, e não há nada a ressalvar;
    * o ente declarou adiantado — a ficha mostra o mês novo e o comparativo
      volta ao de referência, que o ente também declarou;
    * o ente parou antes da referência — a ficha mostra a última declaração
      dele, com a data à vista, e ele fica fora dos indicadores derivados da
      carteira, porque não existe carteira dele na data em que os outros são
      medidos.

    ``na_referencia`` só vale ``False`` quando se sabe que diverge: sem
    competência de referência conhecida, fica indefinido, e o comparativo não
    exclui ninguém por uma dúvida.
    """
    ano, mes = linhas[0].get("ano"), linhas[0].get("mes")
    if ref_ano is None or ref_mes is None or ano is None or mes is None:
        return {"referencia": referencia.get("competencia"),
                "na_referencia": None, "defasagem_meses": None,
                "comparavel": None}
    na_referencia = (ano, mes) == (ref_ano, ref_mes)
    # Positivo: o ente está atrás da referência. Negativo: declarou adiantado.
    defasagem = (ref_ano * 12 + ref_mes) - (ano * 12 + mes)
    comparavel = None
    if not na_referencia:
        da_ref = [l for l in todas
                  if (l.get("ano"), l.get("mes")) == (ref_ano, ref_mes)
                  and l["rowid"] not in linhas_fora]
        comparavel = _resumo_comparavel(da_ref)
    return {
        "referencia": referencia.get("competencia"),
        "na_referencia": na_referencia,
        "defasagem_meses": defasagem,
        "comparavel": comparavel,
    }


def montar_carteira_detalhe(store: Store, cnpj: str,
                            linhas_fora: Optional[AbstractSet[int]] = None
                            ) -> Dict[str, Any]:
    """A carteira inteira, ativo a ativo, em cada competência que a base tem.

    Arquivo próprio, carregado só quando alguém abre a tela detalhada: a ficha
    do ente tem poucos KB porque mostra as dez maiores posições, e um RPPS
    grande declara centenas de ativos. Juntar tudo num arquivo só faria toda
    visita pagar o custo de uma tela que poucas visitas abrem.

    Uma competência por bloco, sem somar entre elas: a posição de junho e a de
    agosto são fotos do mesmo patrimônio em momentos diferentes, e somá-las
    contaria o mesmo dinheiro duas vezes. O que dá para fazer — e a tela faz —
    é olhar uma de cada vez e comparar os totais.
    """
    colunas = ("rowid AS rowid, ano, mes, segmento, tipo_ativo, nome_ativo,"
               " identificacao_ativo, limite_cmn, quantidade_cotas,"
               " valor_unitario, valor_total, perc_recursos, pl_fundo,"
               " perc_pl_fundo")
    linhas = _varios(store, "dair_carteira", colunas, cnpj,
                     ordem="ano DESC, mes DESC, valor_total DESC", limite=40000)
    if not linhas:
        return {"disponivel": False}
    linhas_fora = linhas_fora or frozenset()

    por_competencia: Dict[tuple, List[Dict[str, Any]]] = {}
    for linha in linhas:
        por_competencia.setdefault((linha.get("ano"), linha.get("mes")), []).append(linha)

    competencias = []
    for (ano, mes), do_mes in sorted(por_competencia.items(),
                                     key=lambda kv: kv[0], reverse=True):
        validas = [l for l in do_mes if l["rowid"] not in linhas_fora]
        excluidas = [l for l in do_mes if l["rowid"] in linhas_fora]
        if not validas:
            continue
        total = sum(l.get("valor_total") or 0.0 for l in validas)
        da_fonte = not excluidas and all(
            l.get("perc_recursos") is not None for l in validas)

        def _perc(linha) -> float:
            if da_fonte:
                return linha.get("perc_recursos") or 0.0
            return _pct(linha.get("valor_total") or 0.0, total)

        por_segmento: Dict[str, Dict[str, Any]] = {}
        por_classe: Dict[tuple, Dict[str, Any]] = {}
        itens = []
        for linha in validas:
            segmento = (linha.get("segmento") or "Não informado").strip()
            classe = (linha.get("tipo_ativo") or "Não informada").strip()
            perc = _perc(linha)
            valor = linha.get("valor_total") or 0.0

            alvo = por_segmento.setdefault(segmento, {
                "rotulo": segmento, "valor": 0.0, "perc": 0.0, "ativos": 0})
            alvo["valor"] += valor
            alvo["perc"] += perc
            alvo["ativos"] += 1

            item = por_classe.setdefault((segmento, classe), {
                "segmento": segmento, "rotulo": classe, "valor": 0.0,
                "perc": 0.0, "ativos": 0, "limite": linha.get("limite_cmn")})
            item["valor"] += valor
            item["perc"] += perc
            item["ativos"] += 1
            if item["limite"] is None:
                item["limite"] = linha.get("limite_cmn")

            itens.append(dict(_identificar(linha), **{
                "segmento": segmento,
                "classe": classe,
                "cotas": linha.get("quantidade_cotas"),
                "valor_unitario": linha.get("valor_unitario"),
                "valor": round(valor, 2),
                "perc": round(perc, 2),
                "pl_fundo": linha.get("pl_fundo"),
                "perc_pl_fundo": linha.get("perc_pl_fundo"),
            }))

        segmentos = [
            dict(d, valor=round(d["valor"], 2), perc=round(d["perc"], 2))
            for d in sorted(por_segmento.values(),
                            key=lambda x: x["valor"], reverse=True)]
        classes = []
        for dados in sorted(por_classe.values(), key=lambda c: c["valor"], reverse=True):
            perc = round(dados["perc"], 2)
            limite = dados["limite"]
            classes.append(dict(
                dados, valor=round(dados["valor"], 2), perc=perc,
                excede=bool(limite is not None and perc > limite + MARGEM_DO_LIMITE),
                folga=(round(limite - perc, 2) if limite is not None else None)))

        competencias.append({
            "ano": ano, "mes": mes,
            "competencia": ("{:04d}-{:02d}".format(ano, mes)
                            if ano and mes else None),
            "total": round(total, 2),
            "ativos": len(validas),
            "percentual_da_fonte": da_fonte,
            "excluidas": len(excluidas),
            "valor_excluido": round(sum(l.get("valor_total") or 0.0
                                        for l in excluidas), 2),
            "segmentos": segmentos,
            "classes": classes,
            "itens": itens,
        })

    if not competencias:
        return {"disponivel": False}
    return {"disponivel": True, "cnpj": cnpj, "competencias": competencias}


def _montar_governanca(store: Store, cnpj: str,
                       hoje: Optional[str] = None) -> Dict[str, Any]:
    """Quem responde pelos recursos, e se a certificação está em dia.

    **A leitura é por pessoa, não por linha.** A API devolve uma linha por
    certificação, e quem tem duas aparece duas vezes: é comum ter uma CPA
    vencida e outra vigente ao lado, e nesse caso o requisito de regularidade
    está atendido. Marcar a linha vencida acusaria de irregular quem está em
    ordem — o alerta só vale para quem **não tem nenhuma** certificação dentro
    da validade.

    Vale só para quem ainda está em exercício: certificação vencida de quem já
    saiu do colegiado não diz nada sobre a gestão de hoje.
    """
    if not store.tem_tabela("DAIR_GOVERNANCA"):
        return {"disponivel": False}
    linhas = _varios(
        store, "dair_governanca",
        "ano, mes, pessoa, cargo, vinculo, atribuicao, colegiado,"
        " inicio_atuacao, fim_atuacao, tipo_certificacao,"
        " validade_certificacao, entidade_certificadora", cnpj,
        ordem="ano DESC, mes DESC", limite=4000)
    if not linhas:
        return {"disponivel": False}

    hoje = hoje or _hoje()
    # Uma competência por vez, como no resto do DAIR.
    competencias = [(l.get("ano"), l.get("mes")) for l in linhas
                    if l.get("ano") is not None and l.get("mes") is not None]
    if competencias:
        recente = max(competencias)
        linhas = [l for l in linhas if (l.get("ano"), l.get("mes")) == recente]
    else:
        recente = (None, None)

    pessoas: Dict[tuple, Dict[str, Any]] = {}
    for linha in linhas:
        # Quem já deixou o colegiado não responde pela gestão de hoje.
        fim = linha.get("fim_atuacao")
        if fim and str(fim)[:10] < hoje:
            continue
        chave = ((linha.get("pessoa") or "").strip().upper(),
                 (linha.get("colegiado") or "").strip())
        ficha = pessoas.setdefault(chave, {
            "pessoa": (linha.get("pessoa") or "").strip(),
            "colegiado": (linha.get("colegiado") or "").strip(),
            "cargo": linha.get("cargo"),
            "vinculo": linha.get("vinculo"),
            "atribuicao": linha.get("atribuicao"),
            "certificacoes": [],
        })
        tipo = (linha.get("tipo_certificacao") or "").strip()
        validade = linha.get("validade_certificacao")
        if not tipo and not validade:
            continue
        ficha["certificacoes"].append({
            "tipo": tipo or "Não informada",
            "validade": validade,
            "vigente": bool(validade and str(validade)[:10] >= hoje),
            "entidade": linha.get("entidade_certificadora"),
        })

    fichas = []
    for dados in pessoas.values():
        certificacoes = dados["certificacoes"]
        # Sem nenhuma certificação cadastrada é caso diferente de ter só
        # vencidas, e as duas coisas são diferentes de estar em ordem.
        vigentes = [c for c in certificacoes if c["vigente"]]
        dados["certificacoes"] = sorted(
            certificacoes, key=lambda c: (not c["vigente"], c["validade"] or ""))
        dados["regular"] = bool(vigentes)
        dados["sem_certificacao"] = not certificacoes
        dados["so_vencidas"] = bool(certificacoes) and not vigentes
        dados["validade_mais_longa"] = max(
            (c["validade"] for c in vigentes if c["validade"]), default=None)
        fichas.append(dados)
    fichas.sort(key=lambda f: (f["regular"], f["pessoa"]))

    irregulares = [f for f in fichas if f["so_vencidas"]]
    return {
        "disponivel": True,
        "ano": recente[0],
        "mes": recente[1],
        "competencia": ("{:04d}-{:02d}".format(recente[0], recente[1])
                        if recente[0] and recente[1] else None),
        "referencia": hoje,
        "pessoas": fichas,
        "total": len(fichas),
        "regulares": sum(1 for f in fichas if f["regular"]),
        "so_vencidas": len(irregulares),
        "sem_certificacao": sum(1 for f in fichas if f["sem_certificacao"]),
        "nomes_so_vencidas": [f["pessoa"] for f in irregulares][:10],
    }


def _montar_atuaria(store: Store, cnpj: str) -> Dict[str, Any]:
    """Resultado atuarial, fluxo projetado, custeio e hipóteses — por fundo.

    Uma correção em relação ao anteprojeto: ``DRAA_FLUXO_ATUARIAL`` **não é
    série temporal**. Cada linha é um item do fluxo com um único valor
    projetado — receitas por origem, despesas por tipo de benefício, e os
    totais nos códigos 190000 e 240000. A projeção ano a ano, que renderia a
    curva de cruzamento, existe nos arquivos de dados abertos da SPREV e não
    nesta API. Em vez de forjar uma série, a tela mostra o que há.

    **Um bloco por plano e por massa.** O DRAA avalia cada fundo à parte, e
    somá-los produz números que não descrevem nenhum deles. Nos 26 governos
    estaduais isso juntava a avaliação civil com a militar — que não tem
    contribuição patronal e, em 14 Estados, não tem ativo garantidor nenhum: o
    tesouro paga direto. Um "resultado atuarial" somando os dois não é o
    resultado de coisa alguma.
    """
    fluxo = _varios(store, "draa_fluxo_atuarial",
                    "exercicio, plano, massa, codigo, descricao, valor", cnpj,
                    ordem="exercicio DESC, codigo", limite=4000)
    compromissos = _varios(store, "draa_valores_compromissos",
                           "exercicio, plano, massa, codigo, descricao,"
                           " categoria, geracao_atual, geracao_futura", cnpj,
                           ordem="exercicio DESC, codigo", limite=6000)
    hipoteses = _varios(store, "draa_hipotese_atuarial",
                        "exercicio, descricao, unidade, valor, longo_prazo",
                        cnpj, ordem="exercicio DESC", limite=400)
    custeio = _varios(store, "draa_plano_custeio",
                      "exercicio, plano, massa, tipo_contribuicao, aliquota,"
                      " aliquota_definida, contribuicao_definida", cnpj,
                      ordem="exercicio DESC", limite=600)

    if not (fluxo or compromissos or hipoteses or custeio):
        return {"disponivel": False}

    exercicio = next((linha["exercicio"] for linha in
                      (compromissos or fluxo or hipoteses or custeio)), None)

    def _do_exercicio(linhas):
        return [l for l in linhas if l["exercicio"] == exercicio]

    do_fluxo = _do_exercicio(fluxo)
    do_compromisso = _do_exercicio(compromissos)
    do_custeio = _do_exercicio(custeio)

    # A chave de um bloco é (plano, massa). Nem todo fundo aparece nas quatro
    # tabelas, então a união das chaves é quem manda.
    chaves: Dict[tuple, Dict[str, Any]] = {}
    for conjunto in (do_compromisso, do_fluxo, do_custeio):
        for fundo in _por_fundo(conjunto):
            chaves.setdefault((fundo["plano"], fundo["massa"]), fundo)

    def _daquele(linhas, plano, massa):
        return [l for l in linhas
                if (l.get("plano") or None) == plano
                and (massas.normalizar(l.get("massa")) or None) == massa]

    blocos = []
    for (plano, massa), fundo in chaves.items():
        blocos.append({
            "rotulo": _rotulo_do_fundo(plano, massa),
            "plano": plano,
            "massa": massa,
            "militar": massas.normalizar(massa) == massas.MILITAR,
            "resultado": _resultado_atuarial(
                _daquele(do_compromisso, plano, massa)),
            "fluxo": _resumir_fluxo(_daquele(do_fluxo, plano, massa)),
            "compromissos": [
                {"descricao": l["descricao"], "plano": l["plano"],
                 "geracao_atual": l["geracao_atual"],
                 "geracao_futura": l["geracao_futura"]}
                for l in _daquele(do_compromisso, plano, massa)
                if _normalizar_situacao(l["categoria"]) != codigos.CATEGORIA_TITULO
                and (l["geracao_atual"] or l["geracao_futura"])
            ][:14],
            "custeio": _resumir_custeio(_daquele(do_custeio, plano, massa)),
        })
    blocos.sort(key=lambda b: (b["militar"],
                               -(b["resultado"]["provisoes"] or 0.0), b["rotulo"]))
    if not blocos:
        return {"disponivel": False}

    return {
        "disponivel": True,
        "exercicio": exercicio,
        "blocos": blocos,
        "tem_militar": any(b["militar"] for b in blocos),
        # Hipóteses são da avaliação, não do fundo: juros e inflação de longo
        # prazo valem para o conjunto.
        "hipoteses": _hipoteses_destaque(_do_exercicio(hipoteses)),
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

#: Sufixos dos arquivos auxiliares de um ente, além da própria ficha. Existem
#: aqui para que a limpeza de órfãos saiba a que CNPJ cada arquivo pertence —
#: sem isso ela apagaria o detalhe da carteira logo depois de gravá-lo.
_SUFIXOS_DO_ENTE = ("-carteira",)


def _limpar_fichas_orfas(dir_saida: str, mantidos: AbstractSet[str]) -> int:
    """Apaga arquivos de entes que esta construção não gerou."""
    pasta = os.path.join(dir_saida, "ente")
    if not os.path.isdir(pasta):
        return 0
    apagadas = 0
    for nome in os.listdir(pasta):
        if not nome.endswith(".json"):
            continue
        base = nome[:-5]
        for sufixo in _SUFIXOS_DO_ENTE:
            if base.endswith(sufixo):
                base = base[:-len(sufixo)]
                break
        if base in mantidos:
            continue
        os.remove(os.path.join(pasta, nome))
        apagadas += 1
    return apagadas


def _situacao_da_fonte(store: Store) -> Dict[str, Any]:
    """A fonte respondeu na última carga, e desde quando está como está."""
    marco = store.ultimo_marco("fonte_alcancavel")
    if not marco:
        return {"fonte_alcancavel": None, "fonte_assim_desde": None}
    return {
        "fonte_alcancavel": marco.get("valor") == "sim",
        "fonte_assim_desde": marco.get("quando"),
    }


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
    qual = montar_qualidade(store, entes)
    linhas_fora = qual["linhas_excluidas"]
    marcas = qual["marcas"]

    # Uma variante por combinação de chaves. São dezesseis agregados pequenos:
    # pré-calcular sai mais barato que reimplementar as somas em JavaScript, e
    # garante que o número da tela vem do mesmo código que os testes cobrem.
    panoramas, carteiras, conformidades, militares = {}, {}, {}, {}
    for combinacao in qualidade.combinacoes():
        fora = qualidade.entes_fora(entes, marcas, combinacao)
        panoramas[combinacao] = montar_panorama(store, entes, fora)
        carteiras[combinacao] = montar_carteira_nacional(
            store, entes, fora, linhas_fora)
        conformidades[combinacao] = montar_conformidade_nacional(
            store, entes, fora)
        militares[combinacao] = montar_militar_nacional(store, entes, fora)

    gerados = [
        _gravar("panorama.json", {"variantes": panoramas}, dir_saida),
        _gravar("carteira-nacional.json", {"variantes": carteiras}, dir_saida),
        _gravar("conformidade.json", {"variantes": conformidades}, dir_saida),
        _gravar("militar.json", {"variantes": militares}, dir_saida),
    ]

    indice = sorted(
        ({"cnpj": dados["cnpj"], "ente": dados["ente"], "uf": dados["uf"],
          "esfera": dados["esfera"], "regiao": dados["regiao"],
          "tem_rpps": bool(dados.get("tem_rpps")),
          "populacao": dados.get("populacao"),
          "marcas": sorted(marcas.get(dados["cnpj"], {}))}
         for dados in entes.values()),
        key=lambda d: (d["uf"] or "", d["ente"] or ""))
    gerados.append(_gravar("entes.json", indice, dir_saida))

    escolhidos = list(entes.items())[:limite_entes] if limite_entes else list(entes.items())
    # Uma consulta só para o país inteiro: a competência de referência é a
    # mesma para todas as fichas, e perguntá-la por ente custaria 1.821
    # varreduras de uma tabela de milhões de linhas.
    referencia = _competencias_do_dair(store)
    fichas = {}
    for cnpj, dados in escolhidos:
        ficha = montar_ente(store, cnpj, dados, linhas_fora, referencia)
        fichas[cnpj] = ficha
        _gravar(os.path.join("ente", cnpj + ".json"), ficha, dir_saida)
        # A carteira ativo a ativo vai em arquivo separado: quem só abre a
        # ficha não paga o custo de centenas de linhas que não vai ver.
        detalhe = montar_carteira_detalhe(store, cnpj, linhas_fora)
        if detalhe.get("disponivel"):
            _gravar(os.path.join("ente", cnpj + "-carteira.json"),
                    detalhe, dir_saida)

    # Ficha de ente que saiu da base continuaria sendo servida: o índice não a
    # lista mais, mas o arquivo responde a quem tiver o link antigo — e responde
    # com números de uma carga que já não existe.
    _limpar_fichas_orfas(dir_saida, {cnpj for cnpj, _ in escolhidos})

    # Os consolidados das abas de ente. Vêm das fichas já montadas, não de uma
    # segunda leitura do banco: o número da tela consolidada tem de ser o mesmo
    # que está na ficha, e duas leituras independentes do mesmo fato são duas
    # chances de divergirem em silêncio.
    gerados.append(_gravar("consolidado.json", {"variantes": {
        combinacao: {
            "ficha": montar_ficha_nacional(
                fichas, qualidade.entes_fora(entes, marcas, combinacao)),
            "caixa": montar_caixa_nacional(
                fichas, qualidade.entes_fora(entes, marcas, combinacao)),
            "atuaria": montar_atuaria_nacional(
                fichas, qualidade.entes_fora(entes, marcas, combinacao)),
        }
        for combinacao in qualidade.combinacoes()
    }}, dir_saida))

    comparativo = benchmark.montar(fichas)
    comparativo["grupos"] = {
        "variantes": {
            combinacao: benchmark.resumir_grupos(
                comparativo["rpps"], comparativo["segmentos"],
                qualidade.entes_fora(entes, marcas, combinacao))
            for combinacao in qualidade.combinacoes()
        }
    }
    gerados.append(_gravar("benchmark.json", comparativo, dir_saida))

    # Uma chave sem a fonte que a alimenta não pode aparecer como "não exclui
    # ninguém": isso afirma que ninguém está atrasado quando o que houve foi
    # não ter como saber. A interface a desliga e diz o que falta.
    fontes = {
        "somente_rpps": "RPPS_REGIME_PREVIDENCIARIO",
        "sem_lancamento_impossivel": "DAIR_CARTEIRA",
        "sem_dair_defasado": "DAIR_IDENTIFICACAO",
        "sem_crp_vencido": "RPPS_CRP",
    }
    def _tem_base(chave: str) -> bool:
        # O recorte por RPPS vigente sobrevive sem o endpoint de regime:
        # declarar carteira já prova que há fundo. Os outros três não têm
        # substituto — ou a fonte está no banco, ou a chave não sabe nada.
        if chave == "somente_rpps":
            return (store.tem_tabela("RPPS_REGIME_PREVIDENCIARIO") or
                    store.tem_tabela("DAIR_CARTEIRA"))
        return store.tem_tabela(fontes[chave])

    gerados.append(_gravar("filtros.json", {
        "filtros": [dict(f.como_dicionario(), fonte=fontes[f.chave],
                         disponivel=_tem_base(f.chave))
                    for f in qualidade.FILTROS],
        "padrao": qualidade.chave_padrao(),
        "atingidos": {
            f.chave: len(qualidade.entes_fora(
                entes, marcas,
                "".join("1" if g is f else "0" for g in qualidade.FILTROS)))
            for f in qualidade.FILTROS
        },
    }, dir_saida))

    gerados.append(_gravar("qualidade.json", {
        "referencia": qual["referencia"],
        "divergencia_entre_fontes": resumir_divergencia(fichas),
        "achados": [dict(a, ente=(entes.get(a["cnpj"]) or {}).get("ente"),
                         uf=(entes.get(a["cnpj"]) or {}).get("uf"))
                    for a in qual["achados"]],
        "linhas_excluidas": len(linhas_fora),
        "entes_marcados": {
            marca: sum(1 for m in marcas.values() if marca in m)
            for marca in (qualidade.MARCA_POSICAO, qualidade.MARCA_DAIR,
                          qualidade.MARCA_CRP)
        },
        "rotulos": dict(qualidade.ROTULOS, **qualidade.ROTULOS_ENTE),
    }, dir_saida))

    meta = {
        "origem": store.origem_unica() or origem,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entes": len(entes),
        "com_rpps": sum(1 for d in entes.values() if d.get("tem_rpps")),
        "fichas": len(escolhidos),
        "nivel_fundo": carteiras[qualidade.chave_padrao()].get("nivel"),
        "norma_dos_investimentos": NORMA_DOS_INVESTIMENTOS,
        "competencia_dair": _competencias_do_dair(store).get("competencia"),
        "capitais_conhecidas": grupos.cobertura_capitais(),
        "execucoes": store.resumo(),
        # Carimbo da fonte e o histórico de quando ele mudou. Enquanto não
        # houver semanas suficientes registradas, isto é medição — nada é
        # cortado da varredura por causa dele.
        "fonte_atualizada_em": (store.ultimo_marco("data_atualizacao") or {}).get("valor"),
        "mudancas_da_fonte": store.marcos("data_atualizacao")[:12],
        # Quando a fonte parou de responder. O marco só grava mudanças de
        # estado, então a data aqui é a da transição — "inacessível desde".
        # Sem isso o painel republica com a data antiga e o leitor não tem como
        # distinguir dado que envelheceu por descuido de dado que envelheceu
        # porque a origem saiu do ar.
        **_situacao_da_fonte(store),
    }
    gerados.append(_gravar("meta.json", meta, dir_saida))
    return {"arquivos": len(gerados) + len(list(escolhidos)), "meta": meta}
