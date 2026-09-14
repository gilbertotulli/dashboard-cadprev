"""Armazenamento local em SQLite.

A API não oferece filtro por data de alteração e pagina de 5.000 em 5.000, então
consultá-la a cada clique seria hostil com um serviço público gratuito e lento
para quem usa o painel. O caminho é ingerir uma vez e servir do disco.

Cada endpoint vira uma tabela cujas colunas são os **nomes lógicos** do
``fieldmap`` — se a API renomear um campo, a tabela não muda.

A tabela ``execucao`` guarda a procedência de cada ingestão: filtros usados,
quantas linhas vieram, e o casamento campo lógico → chave real que valia na
hora. Sem isso, um número na tela não tem como ser auditado seis meses depois.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from . import fieldmap

CAMINHO_PADRAO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cadprev.sqlite3"
)

_TIPOS_SQL = {
    "texto": "TEXT", "cnpj": "TEXT", "data": "TEXT",
    "inteiro": "INTEGER", "decimal": "REAL", "booleano": "INTEGER",
}

_DDL_EXECUCAO = """
CREATE TABLE IF NOT EXISTS execucao (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint    TEXT NOT NULL,
    filtros     TEXT NOT NULL,
    linhas      INTEGER NOT NULL,
    nivel       TEXT,
    resolucao   TEXT NOT NULL,
    nao_mapeado TEXT NOT NULL,
    quando      TEXT NOT NULL
)
"""


class Store:
    """Banco local. Usar como gerenciador de contexto."""

    def __init__(self, caminho: str = CAMINHO_PADRAO) -> None:
        self.caminho = caminho
        self.con = sqlite3.connect(caminho)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute(_DDL_EXECUCAO)
        self.con.commit()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_exc) -> None:
        self.fechar()

    def fechar(self) -> None:
        self.con.commit()
        self.con.close()

    # -- esquema ----------------------------------------------------------

    def criar_tabela(self, endpoint: str) -> List[str]:
        """Cria a tabela do endpoint a partir do mapa de campos."""
        campos = fieldmap.campos(endpoint)
        if not campos:
            raise KeyError(
                "{} não tem mapa de campos em cadprev/fieldmap.py".format(endpoint))
        colunas = ["{} {}".format(c.nome, _TIPOS_SQL.get(c.tipo, "TEXT"))
                   for c in campos]
        self.con.execute("CREATE TABLE IF NOT EXISTS {} ({})".format(
            endpoint.lower(), ", ".join(colunas + ["_ingerido_em TEXT"])))
        self.con.execute(
            "CREATE INDEX IF NOT EXISTS idx_{0}_cnpj ON {0} (cnpj_ente)".format(
                endpoint.lower()))
        self.con.commit()
        return [c.nome for c in campos]

    # -- escrita ----------------------------------------------------------

    def gravar(self, endpoint: str, registros: Iterable[Mapping[str, Any]],
               escopo: Optional[Mapping[str, Any]] = None) -> int:
        """Substitui as linhas do escopo pelos registros dados.

        ``escopo`` são as colunas que delimitam a ingestão — por exemplo
        ``{"ano": 2025}``. Reingerir o mesmo escopo é idempotente; escopo vazio
        limpa a tabela inteira.
        """
        colunas = self.criar_tabela(endpoint)
        tabela = endpoint.lower()
        agora = datetime.now(timezone.utc).isoformat(timespec="seconds")

        if escopo:
            onde = " AND ".join("{} = ?".format(k) for k in escopo)
            self.con.execute("DELETE FROM {} WHERE {}".format(tabela, onde),
                             tuple(escopo.values()))
        else:
            self.con.execute("DELETE FROM {}".format(tabela))

        sql = "INSERT INTO {} ({}) VALUES ({})".format(
            tabela, ", ".join(colunas + ["_ingerido_em"]),
            ", ".join("?" * (len(colunas) + 1)))

        total = 0
        lote: List[Sequence[Any]] = []
        for registro in registros:
            lote.append(tuple(registro.get(c) for c in colunas) + (agora,))
            if len(lote) >= 2000:
                self.con.executemany(sql, lote)
                total += len(lote)
                lote.clear()
        if lote:
            self.con.executemany(sql, lote)
            total += len(lote)
        self.con.commit()
        return total

    def registrar_execucao(self, endpoint: str, filtros: Mapping[str, Any],
                           linhas: int, resolucao: fieldmap.Resolucao,
                           nivel: Optional[str] = None) -> None:
        """Guarda a procedência da ingestão."""
        self.con.execute(
            "INSERT INTO execucao (endpoint, filtros, linhas, nivel, resolucao,"
            " nao_mapeado, quando) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (endpoint, json.dumps(filtros, ensure_ascii=False), linhas, nivel,
             json.dumps(resolucao.encontrados, ensure_ascii=False),
             json.dumps(resolucao.nao_mapeados, ensure_ascii=False),
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
        self.con.commit()

    # -- leitura ----------------------------------------------------------

    def consultar(self, sql: str, parametros: Sequence[Any] = ()) -> List[sqlite3.Row]:
        return list(self.con.execute(sql, parametros))

    def tabelas(self) -> List[str]:
        linhas = self.con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")
        return [linha[0] for linha in linhas]

    def tem_tabela(self, endpoint: str) -> bool:
        return endpoint.lower() in self.tabelas()

    def contar(self, endpoint: str) -> int:
        if not self.tem_tabela(endpoint):
            return 0
        return self.con.execute(
            "SELECT COUNT(*) FROM {}".format(endpoint.lower())).fetchone()[0]

    def ultima_execucao(self, endpoint: str) -> Optional[Dict[str, Any]]:
        linha = self.con.execute(
            "SELECT * FROM execucao WHERE endpoint = ? ORDER BY id DESC LIMIT 1",
            (endpoint,)).fetchone()
        return dict(linha) if linha else None

    def resumo(self) -> List[Dict[str, Any]]:
        """Uma linha por endpoint ingerido, para o comando ``status``."""
        saida = []
        for endpoint in fieldmap.endpoints_mapeados():
            if not self.tem_tabela(endpoint):
                continue
            execucao = self.ultima_execucao(endpoint) or {}
            saida.append({
                "endpoint": endpoint,
                "linhas": self.contar(endpoint),
                "quando": execucao.get("quando"),
                "filtros": json.loads(execucao.get("filtros") or "{}"),
                "nivel": execucao.get("nivel"),
            })
        return saida
