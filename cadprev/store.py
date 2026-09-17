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

_DDL_ORIGEM = """
CREATE TABLE IF NOT EXISTS origem (
    marca  TEXT PRIMARY KEY,
    quando TEXT NOT NULL
)
"""

#: Carimbos observados na fonte a cada carga. Existe para responder, com
#: histórico em vez de suposição, à pergunta que decide a carga incremental: o
#: que de fato mudou desde a semana passada. Enquanto não houver semanas
#: suficientes registradas, nada é cortado — só medido.
_DDL_MARCO = """
CREATE TABLE IF NOT EXISTS marco (
    nome   TEXT NOT NULL,
    valor  TEXT,
    quando TEXT NOT NULL,
    PRIMARY KEY (nome, quando)
)
"""

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
        self.con.execute(_DDL_ORIGEM)
        self.con.execute(_DDL_MARCO)
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

    # -- origem dos dados -------------------------------------------------

    def registrar_marco(self, nome: str, valor: Optional[str]) -> bool:
        """Anota um carimbo da fonte, e diz se ele mudou desde o anterior.

        Só grava quando o valor muda: a série fica sendo a lista de mudanças,
        não a de execuções, e uma olhada nela responde de imediato com que
        frequência a fonte realmente se move.
        """
        anterior = self.ultimo_marco(nome)
        if anterior and anterior.get("valor") == valor:
            return False
        self.con.execute(
            "INSERT OR REPLACE INTO marco (nome, valor, quando) VALUES (?, ?, ?)",
            (nome, valor,
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
        self.con.commit()
        return True

    def ultimo_marco(self, nome: str) -> Optional[Dict[str, Any]]:
        linha = self.con.execute(
            "SELECT nome, valor, quando FROM marco WHERE nome = ? "
            "ORDER BY quando DESC LIMIT 1", (nome,)).fetchone()
        return dict(linha) if linha else None

    def marcos(self, nome: Optional[str] = None) -> List[Dict[str, Any]]:
        """Histórico de mudanças dos carimbos, do mais recente ao mais antigo."""
        sql = "SELECT nome, valor, quando FROM marco"
        args: tuple = ()
        if nome:
            sql += " WHERE nome = ?"
            args = (nome,)
        return [dict(l) for l in
                self.con.execute(sql + " ORDER BY quando DESC", args)]

    def marcar_origem(self, marca: str) -> None:
        """Registra que este banco recebeu dados de uma origem.

        Um banco pode acabar com dados reais e sintéticos misturados — basta
        ingerir por cima de um ``demo``, já que a substituição é por escopo e os
        escopos não coincidem. O resultado seria um painel carimbado como real
        exibindo números inventados, que é justamente o que este projeto não
        pode deixar acontecer. Daí a marca.
        """
        self.con.execute(
            "INSERT OR IGNORE INTO origem (marca, quando) VALUES (?, ?)",
            (marca, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        self.con.commit()

    def origens(self) -> List[str]:
        """Todas as origens já gravadas neste banco."""
        return [linha[0] for linha in
                self.con.execute("SELECT marca FROM origem ORDER BY marca")]

    def origem_unica(self) -> Optional[str]:
        """A origem do banco, ou ``None`` se houver mistura ou nada."""
        marcas = self.origens()
        return marcas[0] if len(marcas) == 1 else None

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
        sql = "INSERT INTO {} ({}) VALUES ({})".format(
            tabela, ", ".join(colunas + ["_ingerido_em"]),
            ", ".join("?" * (len(colunas) + 1)))

        # Tudo ou nada. A fonte dos registros é um gerador que vai buscando
        # página por página na API, e uma falha no meio é normal — a rede cai, a
        # API pede calma. Sem a transação, o DELETE já teria apagado os dados
        # bons e as inserções parciais ficariam: o endpoint apareceria com
        # centenas de milhares de linhas e nenhum registro de execução, e o
        # build seguinte trataria o pedaço como se fosse a base inteira.
        total = 0
        try:
            if escopo:
                onde = " AND ".join("{} = ?".format(k) for k in escopo)
                self.con.execute("DELETE FROM {} WHERE {}".format(tabela, onde),
                                 tuple(escopo.values()))
            else:
                self.con.execute("DELETE FROM {}".format(tabela))

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
        except BaseException:
            self.con.rollback()
            raise

        self.con.commit()
        return total

    def registrar_execucao(self, endpoint: str, filtros: Mapping[str, Any],
                           linhas: int,
                           resolucao: Optional[fieldmap.Resolucao] = None,
                           nivel: Optional[str] = None) -> None:
        """Guarda a procedência da ingestão.

        ``resolucao`` é opcional porque nem toda fonte passa pelo mapa de
        campos: a tabela de entes do SICONFI tem nomes estáveis e é traduzida
        no próprio cliente.
        """
        encontrados = resolucao.encontrados if resolucao else {}
        nao_mapeados = resolucao.nao_mapeados if resolucao else []
        self.con.execute(
            "INSERT INTO execucao (endpoint, filtros, linhas, nivel, resolucao,"
            " nao_mapeado, quando) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (endpoint, json.dumps(filtros, ensure_ascii=False), linhas, nivel,
             json.dumps(encontrados, ensure_ascii=False),
             json.dumps(nao_mapeados, ensure_ascii=False),
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
