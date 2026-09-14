"""Mapeamento entre os campos da resposta da API e os nomes usados no projeto.

Por que esta camada existe
--------------------------
Os nomes exatos dos campos devolvidos pela API do CADPREV não foram
confirmados: o levantamento que originou este projeto foi feito sem acesso de
rede aos domínios ``*.gov.br``, a partir do cliente R ``marcosfs2006/ADPrev`` e
dos conjuntos de dados abertos equivalentes. Ver docs/api-cadprev.md.

Em vez de espalhar palpites por todo o código, cada campo lógico declara aqui
uma lista de **candidatos**. Duas convenções coexistem nos artefatos públicos da
SPREV e ambas estão contempladas:

* a dos parâmetros de consulta, com prefixo de tipo — ``nr_cnpj_entidade``,
  ``sg_uf``, ``dt_ano``, e por extensão ``ds_``, ``vl_``, ``qt_``, ``pc_``;
* a dos arquivos de dados abertos, sem prefixo — ``cnpj``, ``uf``, ``segmento``,
  ``vlr_total_atual``.

A resolução acontece uma vez por endpoint, contra as chaves realmente
observadas. Se nenhum candidato casar, o erro lista as chaves que vieram — o
problema se diagnostica sozinho em vez de virar coluna nula.

Corrigir sem editar código
--------------------------
``fieldmap.local.json`` na raiz do repositório sobrepõe este mapa::

    {"DAIR_CARTEIRA": {"valor_total": "vl_total_atual"}}

``python -m cadprev inspect DAIR_CARTEIRA`` gera um rascunho desse arquivo a
partir de uma página real da API.
"""

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_OVERRIDE = os.path.join(RAIZ, "fieldmap.local.json")


class CampoNaoEncontrado(LookupError):
    """Nenhum candidato de um campo obrigatório existe na resposta."""


@dataclass(frozen=True)
class Campo:
    """Um campo lógico e os nomes sob os quais ele pode chegar.

    Attributes:
        nome: nome usado no projeto, estável mesmo que a API mude.
        candidatos: nomes possíveis na resposta, em ordem de preferência.
        tipo: ``texto``, ``inteiro``, ``decimal``, ``data``, ``cnpj`` ou ``booleano``.
        obrigatorio: se ausente, a ingestão falha em vez de seguir com nulo.
        nota: observação que sobrevive à leitura do código.
    """

    nome: str
    candidatos: Tuple[str, ...]
    tipo: str = "texto"
    obrigatorio: bool = True
    nota: str = ""


def _c(nome, *candidatos, tipo="texto", obrigatorio=True, nota=""):
    return Campo(nome, tuple(candidatos), tipo, obrigatorio, nota)


# Campos de identificação, repetidos em todos os endpoints.
_IDENT = (
    _c("cnpj_ente", "nr_cnpj_entidade", "cnpj_ente", "cnpj", tipo="cnpj"),
    _c("ente", "no_ente", "ente", "nm_ente"),
    _c("uf", "sg_uf", "uf"),
)

MAPA: Dict[str, Tuple[Campo, ...]] = {
    "RPPS_REGIME_PREVIDENCIARIO": _IDENT + (
        _c("regime", "ds_regime", "regime", "tp_regime",
           nota="RGPS, RPPS ou RPPS em extinção"),
    ),
    "RPPS_CRP": _IDENT + (
        _c("numero_crp", "nr_crp", "num_crp", "numero_crp"),
        _c("emissao", "dt_emissao", "dt_emissao_crp", "emissao", tipo="data"),
        _c("validade", "dt_validade", "dt_validade_crp", "validade", tipo="data"),
        _c("judicial", "st_judicial", "judicial", "in_judicial", tipo="booleano"),
        _c("situacao", "ds_situacao", "situacao", "st_situacao",
           obrigatorio=False, nota="VÁLIDO ou VENCIDO; derivável da validade"),
    ),
    "RPPS_ALIQUOTA": _IDENT + (
        _c("plano", "ds_plano_segregacao", "plano_segregacao", "plano_segreg",
           nota="FINANCEIRO (repartição) ou PREVIDENCIÁRIO (capitalização)"),
        _c("sujeito_passivo", "ds_sujeito_passivo", "sujeito_passivo"),
        _c("aliquota", "vl_aliquota", "pc_aliquota", "aliquota", tipo="decimal"),
        _c("inicio_vigencia", "dt_inicio_vigencia", "inic_vigencia",
           "dt_inic_vigencia", tipo="data"),
        _c("fim_vigencia", "dt_fim_vigencia", "fim_vigencia", tipo="data",
           obrigatorio=False, nota="nulo = vigente"),
    ),
    "DIPR": _IDENT + (
        _c("ano", "dt_ano", "ano", tipo="inteiro"),
        _c("mes", "dt_mes", "mes", tipo="inteiro"),
        _c("plano", "ds_plano_segregacao", "plano_segreg", "plano_segregacao",
           obrigatorio=False,
           nota="dimensão capitalizado x repartição — confirmada na API"),
        _c("total_receita", "vl_total_receita", "total_receita", tipo="decimal"),
        _c("total_despesa", "vl_total_despesa", "total_despesa", tipo="decimal"),
        _c("resultado", "vl_resultado_final", "resultado_final", tipo="decimal",
           obrigatorio=False, nota="derivável de receita - despesa"),
        _c("nb_aposentados", "qt_nb_apos", "nb_apos", tipo="inteiro",
           obrigatorio=False),
        _c("nb_pensionistas", "qt_nb_pen", "nb_pen", tipo="inteiro",
           obrigatorio=False),
        _c("nb_servidores", "qt_nb_serv", "nb_serv", tipo="inteiro",
           obrigatorio=False),
    ),
    "DAIR_CARTEIRA": _IDENT + (
        _c("competencia", "dt_competencia", "competencia",
           nota="mês e ano da posição"),
        _c("segmento", "ds_segmento", "segmento",
           nota="inclui 'Disponibilidades Financeiras', que não é alocação"),
        _c("tipo_ativo", "ds_tipo_ativo", "tipo_ativo", obrigatorio=False),
        _c("limite_cmn", "vl_limite_resol_cmn", "limite_resol_cmn",
           tipo="decimal", obrigatorio=False,
           nota="teto da Resolução CMN 3.922/10, no próprio registro"),
        _c("identificacao_ativo", "ds_ident_ativo", "ident_ativo",
           obrigatorio=False),
        _c("nome_ativo", "no_ativo", "nm_ativo", "nome_ativo", obrigatorio=False),
        _c("quantidade_cotas", "qt_quotas", "qtd_quotas", tipo="decimal",
           obrigatorio=False),
        _c("valor_unitario", "vl_atual_ativo", "vlr_atual_ativo", tipo="decimal",
           obrigatorio=False),
        _c("valor_total", "vl_total_atual", "vlr_total_atual", tipo="decimal"),
        _c("perc_recursos", "pc_recursos_rpps", "perc_recursos_rpps",
           tipo="decimal", obrigatorio=False),
        _c("pl_fundo", "vl_pl_fundo", "pl_fundo", tipo="decimal",
           obrigatorio=False),
        _c("perc_pl_fundo", "pc_pl_fundo", "perc_pl_fundo", tipo="decimal",
           obrigatorio=False),
        # --- o campo da pendência de maior impacto ---
        _c("plano", "ds_plano", "ds_plano_segregacao", "ds_tipo_recurso",
           "tp_recurso", "plano", "plano_segregacao", "tipo_recurso",
           tipo="texto", obrigatorio=False,
           nota="NÃO CONFIRMADO. Se existir, permite a decomposição de três vias "
                "(capitalizado / repartição / taxa de administração) — Nível A. "
                "Ausente, o projeto cai no Nível B e classifica o RPPS, "
                "não o ativo. Ver cadprev/fundos.py"),
    ),
    "DRAA_ESTATISTICA": _IDENT + (
        _c("exercicio", "dt_exercicio", "exercicio", tipo="inteiro"),
        _c("ativos", "qt_ativos", "ativos", tipo="inteiro", obrigatorio=False),
        _c("aposentados", "qt_aposentados", "aposentados", tipo="inteiro",
           obrigatorio=False),
        _c("pensionistas", "qt_pensionistas", "pensionistas", tipo="inteiro",
           obrigatorio=False),
        _c("dependentes", "qt_dependentes", "dependentes", tipo="inteiro",
           obrigatorio=False),
    ),
    "DRAA_SEGREGACAO_MASSA": _IDENT + (
        _c("exercicio", "dt_exercicio", "exercicio", tipo="inteiro"),
        _c("possui_segregacao", "st_segregacao", "possui_segregacao",
           "in_segregacao", tipo="booleano", obrigatorio=False),
        _c("data_segregacao", "dt_segregacao", "data_segregacao", tipo="data",
           obrigatorio=False),
    ),
    "DRAA_FLUXO_ATUARIAL": _IDENT + (
        _c("exercicio", "dt_exercicio", "exercicio", tipo="inteiro"),
        _c("ano_projecao", "dt_ano_projecao", "ano_projecao", "ano",
           tipo="inteiro"),
        _c("receitas", "vl_receitas", "receitas", tipo="decimal",
           obrigatorio=False),
        _c("despesas", "vl_despesas", "despesas", tipo="decimal",
           obrigatorio=False),
        _c("saldo", "vl_saldo", "saldo", tipo="decimal", obrigatorio=False),
    ),
    "DRAA_VALORES_COMPROMISSOS": _IDENT + (
        _c("exercicio", "dt_exercicio", "exercicio", tipo="inteiro"),
        _c("codigo", "cd_variavel", "codigo", obrigatorio=False),
        _c("descricao", "ds_variavel", "descr", "descricao"),
        _c("geracao_atual", "vl_geracao_atual", "vlr_geracao_atual",
           tipo="decimal", obrigatorio=False),
        _c("geracao_futura", "vl_geracao_futura", "vlr_geracao_futura",
           tipo="decimal", obrigatorio=False),
    ),
    "DRAA_PLANO_CUSTEIO": _IDENT + (
        _c("exercicio", "dt_exercicio", "exercicio", tipo="inteiro"),
        _c("descricao", "ds_custo", "descricao", obrigatorio=False),
        _c("custo_normal", "vl_custo_normal", "custo_normal", tipo="decimal",
           obrigatorio=False),
        _c("custo_suplementar", "vl_custo_suplementar", "custo_suplementar",
           tipo="decimal", obrigatorio=False),
    ),
    "DRAA_HIPOTESE_ATUARIAL": _IDENT + (
        _c("exercicio", "dt_exercicio", "exercicio", tipo="inteiro"),
        _c("descricao", "ds_hipotese", "descricao", "hipotese"),
        _c("valor", "vl_hipotese", "valor", obrigatorio=False),
    ),
}


# --------------------------------------------------------------------------
# Resolução
# --------------------------------------------------------------------------

def _normalizar(chave: str) -> str:
    """Reduz uma chave à sua forma comparável: sem acento, sem separador."""
    sem_acento = unicodedata.normalize("NFKD", chave)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def carregar_override(caminho: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """Lê ``fieldmap.local.json``, se existir. Ausência não é erro."""
    caminho = caminho or ARQUIVO_OVERRIDE
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class Resolucao:
    """O casamento entre campos lógicos e chaves reais de um endpoint."""

    endpoint: str
    encontrados: Dict[str, str]
    faltando_obrigatorios: List[str]
    faltando_opcionais: List[str]
    nao_mapeados: List[str]

    @property
    def completa(self) -> bool:
        return not self.faltando_obrigatorios

    def resumo(self) -> str:
        linhas = ["{}: {} campos resolvidos".format(self.endpoint, len(self.encontrados))]
        if self.faltando_obrigatorios:
            linhas.append("  obrigatórios ausentes: " + ", ".join(self.faltando_obrigatorios))
        if self.faltando_opcionais:
            linhas.append("  opcionais ausentes: " + ", ".join(self.faltando_opcionais))
        if self.nao_mapeados:
            mostra = self.nao_mapeados[:12]
            resto = len(self.nao_mapeados) - len(mostra)
            linhas.append("  chaves não mapeadas: " + ", ".join(mostra)
                          + (" (+{})".format(resto) if resto else ""))
        return "\n".join(linhas)


def resolver(endpoint: str, chaves: Iterable[str],
             override: Optional[Mapping[str, Mapping[str, str]]] = None) -> Resolucao:
    """Casa os campos declarados com as chaves observadas numa resposta.

    A busca é feita em três passadas, da mais estrita à mais tolerante: nome
    exato, depois sem diferenciar maiúsculas, depois ignorando acentos e
    separadores. Assim ``vlr_total_atual`` e ``VlrTotalAtual`` resolvem para o
    mesmo campo sem precisar de entrada nova no mapa.
    """
    chaves = list(chaves)
    por_exato = {k: k for k in chaves}
    por_minuscula = {k.lower(): k for k in chaves}
    por_normal = {_normalizar(k): k for k in chaves}

    override = (override if override is not None else carregar_override()).get(endpoint, {})
    campos = MAPA.get(endpoint, ())

    encontrados: Dict[str, str] = {}
    faltando_obr: List[str] = []
    faltando_opc: List[str] = []

    for campo in campos:
        forcado = override.get(campo.nome)
        candidatos = (forcado,) + campo.candidatos if forcado else campo.candidatos
        achado = None
        for cand in candidatos:
            achado = (por_exato.get(cand)
                      or por_minuscula.get(cand.lower())
                      or por_normal.get(_normalizar(cand)))
            if achado:
                break
        if achado:
            encontrados[campo.nome] = achado
        elif campo.obrigatorio:
            faltando_obr.append(campo.nome)
        else:
            faltando_opc.append(campo.nome)

    usadas = set(encontrados.values())
    nao_mapeados = [k for k in chaves if k not in usadas]
    return Resolucao(endpoint, encontrados, faltando_obr, faltando_opc, nao_mapeados)


def exigir(resolucao: Resolucao, chaves_observadas: Sequence[str]) -> Resolucao:
    """Levanta erro legível se faltar campo obrigatório."""
    if resolucao.completa:
        return resolucao
    raise CampoNaoEncontrado(
        "{}: não encontrei os campos obrigatórios {}.\n"
        "Chaves que a API devolveu: {}\n"
        "Corrija em fieldmap.local.json — veja `python -m cadprev inspect {}`."
        .format(resolucao.endpoint,
                ", ".join(resolucao.faltando_obrigatorios),
                ", ".join(sorted(chaves_observadas)),
                resolucao.endpoint)
    )


# --------------------------------------------------------------------------
# Conversão de tipos
# --------------------------------------------------------------------------

_VERDADEIRO = {"s", "sim", "true", "t", "1", "y", "yes"}
_FALSO = {"n", "nao", "não", "false", "f", "0", "no"}


def converter(valor: Any, tipo: str) -> Any:
    """Converte um valor cru da API para o tipo lógico do campo.

    A API pode devolver número como número ou como texto no formato brasileiro
    (``1.234,56``). Data pode vir ISO ou ``dd/mm/aaaa``. Os dois casos são
    tratados aqui para que o resto do código nunca precise saber disso.
    """
    if valor is None or valor == "":
        return None
    if tipo == "texto":
        return str(valor).strip()
    if tipo == "cnpj":
        return re.sub(r"\D", "", str(valor)).zfill(14)
    if tipo == "inteiro":
        if isinstance(valor, bool):
            return int(valor)
        if isinstance(valor, (int, float)):
            return int(valor)
        limpo = re.sub(r"[^\d-]", "", str(valor))
        return int(limpo) if limpo not in ("", "-") else None
    if tipo == "decimal":
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return float(valor)
        texto = str(valor).strip()
        if "," in texto:  # formato brasileiro: ponto é milhar
            texto = texto.replace(".", "").replace(",", ".")
        limpo = re.sub(r"[^\d.eE+-]", "", texto)
        try:
            return float(limpo)
        except ValueError:
            return None
    if tipo == "booleano":
        if isinstance(valor, bool):
            return valor
        t = _normalizar(str(valor))
        if t in _VERDADEIRO:
            return True
        if t in _FALSO:
            return False
        return None
    if tipo == "data":
        return _converter_data(valor)
    return valor


def _converter_data(valor: Any) -> Optional[str]:
    """Devolve a data em ISO (``aaaa-mm-dd``) ou ``None``."""
    if isinstance(valor, (date, datetime)):
        return valor.date().isoformat() if isinstance(valor, datetime) else valor.isoformat()
    texto = str(valor).strip()
    if not texto:
        return None
    if texto.isdigit() and len(texto) == 13:  # epoch em milissegundos
        return datetime.utcfromtimestamp(int(texto) / 1000).date().isoformat()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto[:len(formato) + 6], formato).date().isoformat()
        except ValueError:
            continue
    try:  # ISO com fuso
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def aplicar(resolucao: Resolucao, registro: Mapping[str, Any]) -> Dict[str, Any]:
    """Traduz um registro cru da API para os nomes e tipos do projeto."""
    tipos = {c.nome: c.tipo for c in MAPA.get(resolucao.endpoint, ())}
    saida: Dict[str, Any] = {}
    for logico, real in resolucao.encontrados.items():
        saida[logico] = converter(registro.get(real), tipos.get(logico, "texto"))
    for ausente in resolucao.faltando_opcionais:
        saida[ausente] = None
    return saida


def campos(endpoint: str) -> Tuple[Campo, ...]:
    return MAPA.get(endpoint, ())


def endpoints_mapeados() -> Tuple[str, ...]:
    return tuple(sorted(MAPA))
