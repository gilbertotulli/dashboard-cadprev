"""Ingestão: da API para o banco local.

O fluxo é sempre o mesmo e tem uma ordem que importa:

1. pegar o primeiro registro e **resolver os campos** contra o que veio;
2. falhar alto se faltar campo obrigatório, com as chaves reais no erro;
3. só então percorrer o resto, traduzindo registro a registro.

Resolver antes de gravar é o que impede a falha silenciosa: uma coluna inteira
de ``NULL`` descoberta semanas depois, quando o número já circulou.
"""

import itertools
import json
import logging
import os
from typing import Any, Dict, Iterable, Iterator, Mapping, Optional, Tuple

from . import endpoints, fieldmap, fundos
from .client import Cliente
from .store import Store

log = logging.getLogger("cadprev.ingest")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_SCHEMA = os.path.join(RAIZ, "docs", "schema-observado")


def _espiar(iterador: Iterator[Dict[str, Any]]
            ) -> Tuple[Optional[Dict[str, Any]], Iterator[Dict[str, Any]]]:
    """Olha o primeiro item sem consumi-lo do fluxo."""
    try:
        primeiro = next(iterador)
    except StopIteration:
        return None, iter(())
    return primeiro, itertools.chain([primeiro], iterador)


def inspecionar(cliente: Cliente, endpoint: str, salvar: bool = False,
                **filtros: Any) -> Dict[str, Any]:
    """Baixa uma página e relata o que a API realmente devolve.

    É o comando que resolve a pendência central do projeto: com acesso de rede,
    uma chamada por endpoint fixa os nomes de campo de uma vez.
    """
    registros = list(cliente.amostra(endpoint, **filtros))
    if not registros:
        return {"endpoint": endpoint, "registros": 0, "chaves": [],
                "resolucao": None, "amostra": None}

    chaves = sorted({k for registro in registros for k in registro})
    resolucao = fieldmap.resolver(endpoint, chaves)
    relatorio = {
        "endpoint": endpoint,
        "registros": len(registros),
        "chaves": chaves,
        "resolucao": resolucao,
        "amostra": registros[0],
        "sugestao_override": dict(resolucao.encontrados),
    }

    if salvar:
        os.makedirs(DIR_SCHEMA, exist_ok=True)
        destino = os.path.join(DIR_SCHEMA, endpoint + ".json")
        with open(destino, "w", encoding="utf-8") as fh:
            json.dump({
                "endpoint": endpoint,
                "filtros": filtros,
                "chaves_observadas": chaves,
                "campos_resolvidos": resolucao.encontrados,
                "obrigatorios_ausentes": resolucao.faltando_obrigatorios,
                "opcionais_ausentes": resolucao.faltando_opcionais,
                "chaves_nao_mapeadas": resolucao.nao_mapeados,
                "registro_exemplo": registros[0],
            }, fh, ensure_ascii=False, indent=2)
        relatorio["salvo_em"] = destino
    return relatorio


def ingerir(cliente: Cliente, store: Store, endpoint: str,
            escopo: Optional[Mapping[str, Any]] = None,
            limite_paginas: Optional[int] = None, **filtros: Any) -> Dict[str, Any]:
    """Traz um endpoint inteiro (dentro dos filtros) para o banco local.

    Args:
        escopo: colunas lógicas que delimitam a substituição, por exemplo
            ``{"ano": 2025}``. Reingerir o mesmo escopo é idempotente.
        limite_paginas: para explorar sem baixar tudo.
        filtros: parâmetros de consulta da API.
    """
    endpoints.get(endpoint)  # valida o nome cedo
    bruto = cliente.registros(endpoint, limite_paginas=limite_paginas, **filtros)
    primeiro, fluxo = _espiar(bruto)

    if primeiro is None:
        log.warning("%s: a API não devolveu registros para %s", endpoint, filtros)
        return {"endpoint": endpoint, "linhas": 0, "resolucao": None,
                "nivel": None, "vazio": True}

    resolucao = fieldmap.resolver(endpoint, primeiro.keys())
    fieldmap.exigir(resolucao, list(primeiro.keys()))

    nivel = (fundos.detectar_nivel(resolucao.encontrados)
             if endpoint == "DAIR_CARTEIRA" else None)

    traduzidos = (fieldmap.aplicar(resolucao, registro) for registro in fluxo)
    linhas = store.gravar(endpoint, traduzidos, escopo)
    store.registrar_execucao(endpoint, dict(filtros), linhas, resolucao, nivel)

    log.info("%s: %d linhas (%d campos resolvidos%s)", endpoint, linhas,
             len(resolucao.encontrados),
             ", nível {}".format(nivel) if nivel else "")
    return {"endpoint": endpoint, "linhas": linhas, "resolucao": resolucao,
            "nivel": nivel, "vazio": False}


def ingerir_varios(cliente: Cliente, store: Store, nomes: Iterable[str],
                   escopo: Optional[Mapping[str, Any]] = None,
                   **filtros: Any) -> Dict[str, Any]:
    """Ingere vários endpoints, seguindo adiante quando um falha.

    Uma falha isolada não deve derrubar a carga inteira: o relatório final diz
    o que entrou e o que não entrou, e o operador decide.
    """
    resultados, erros = [], []
    for nome in nomes:
        filtros_validos = _filtrar_aplicaveis(nome, filtros)
        escopo_valido = _escopo_aplicavel(nome, escopo)
        try:
            resultados.append(ingerir(cliente, store, nome, escopo=escopo_valido,
                                      **filtros_validos))
        except Exception as erro:  # noqa: BLE001 — relatar, não abortar
            log.error("%s falhou: %s", nome, erro)
            erros.append({"endpoint": nome, "erro": str(erro)})
    return {"ok": resultados, "erros": erros}


def _escopo_aplicavel(endpoint: str, escopo: Optional[Mapping[str, Any]]
                      ) -> Optional[Dict[str, Any]]:
    """Restringe o escopo às colunas que o endpoint realmente tem.

    ``--ano`` delimita DIPR e DAIR; ``--exercicio`` delimita o DRAA. Aplicar o
    escopo inteiro a todos faria a substituição falhar com "no such column"
    justamente nos endpoints em que ela não se aplica.
    """
    if not escopo:
        return None
    colunas = {campo.nome for campo in fieldmap.campos(endpoint)}
    recorte = {k: v for k, v in escopo.items() if k in colunas}
    return recorte or None


def _filtrar_aplicaveis(endpoint: str, filtros: Mapping[str, Any]) -> Dict[str, Any]:
    """Descarta filtros que o endpoint não aceita.

    Assim ``--ano 2025`` pode ser passado a uma carga que inclui endpoints
    cadastrais, sem virar parâmetro inválido numa consulta que não o entende.
    """
    aceitos = set(endpoints.get(endpoint).filtros)
    return {k: v for k, v in filtros.items() if k in aceitos and v is not None}
