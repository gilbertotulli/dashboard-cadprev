"""Como o ativo se chama na tela — e o que o DAIR chama de nome.

Dois campos descrevem cada posição da carteira, e o que cabe em cada um muda
conforme a natureza do ativo:

* num **fundo**, ``nome_ativo`` é o nome do fundo e ``identificacao_ativo`` é o
  CNPJ dele. Era esse o caso que o painel assumia, e para fundos ele vale.
* num **título público**, os dois trocam de papel: ``identificacao_ativo`` traz
  a descrição que o RPPS escreveu à mão ("NTNB 15082040 (Compra em 06122024 Tx
  67643)") e ``nome_ativo`` traz um número de contrato. Em 22/09/2026, 6.844 das
  7.091 posições de título público nacionais — 97% — tinham um número puro no
  campo que a tela mostrava como nome do ativo.

Daí a regra deste módulo: **o nome é o primeiro dos dois campos que tenha
letras.** Não é uma heurística sobre a classe do ativo, é uma sobre o conteúdo,
e por isso continua valendo se amanhã outra classe repetir a inversão.

O vencimento é outra história. A sigla do título aparece em praticamente todas
as descrições, mas a data de vencimento só existe em 12% delas: 80% são o nome
comercial do Tesouro Direto, sem data nenhuma ("Tesouro IPCA+ com Juros
Semestrais (NTNB)"). O painel mostra o vencimento de quem o escreveu e não
inventa o dos outros — e mantém a descrição original à vista, porque ela é o
que a fonte afirmou.
"""

import re
import unicodedata
from datetime import date
from typing import Any, Dict, Mapping, Optional, Tuple

#: As siglas do Tesouro, na grafia normalizada que a tela usa. A ordem importa:
#: "NTN-B" tem de ser testada antes de "NTN", senão toda NTN-B vira NTN.
_SIGLAS = (
    ("NTNB", "NTN-B"), ("NTN-B", "NTN-B"),
    ("NTNF", "NTN-F"), ("NTN-F", "NTN-F"),
    ("NTNC", "NTN-C"), ("NTN-C", "NTN-C"),
    ("LFT", "LFT"), ("LTN", "LTN"), ("NTN", "NTN"),
)

#: Palavras que marcam uma data de compra. A descrição típica traz as duas datas
#: — "NTNB 15082040 (Compra em 06122024)" — e tomar a primeira que aparecer
#: funcionaria só enquanto o vencimento viesse antes. Estas palavras dizem qual
#: descartar, em vez de confiar na ordem.
_DE_COMPRA = ("compra", "aquis", "aplic", "adquir")

_DATA = re.compile(r"(\d{2})[/.\-]?(\d{2})[/.\-]?((?:19|20)\d{2})")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn").lower()


def tem_letra(texto: Optional[str]) -> bool:
    """Se o campo diz alguma coisa ou é só um número de contrato.

    >>> tem_letra("BB PREVIDENCIARIO RENDA FIXA")
    True
    >>> tem_letra("20500815/3")
    False
    >>> tem_letra(None)
    False
    """
    return bool(texto) and any(c.isalpha() for c in str(texto))


def nome(nome_ativo: Optional[str], identificacao: Optional[str],
         classe: Optional[str] = None) -> Dict[str, Any]:
    """O nome do ativo e de que campo ele veio.

    >>> nome("CAIXA HEDGE FIC", "30068135000150")["rotulo"]
    'CAIXA HEDGE FIC'
    >>> nome("27626457", "Tesouro IPCA+ (NTNB)")["rotulo"]
    'Tesouro IPCA+ (NTNB)'
    >>> nome("27626457", "Tesouro IPCA+ (NTNB)")["campo"]
    'identificacao_ativo'
    """
    for campo, valor in (("nome_ativo", nome_ativo),
                         ("identificacao_ativo", identificacao)):
        if tem_letra(valor):
            return {"rotulo": str(valor).strip(), "campo": campo}
    # Nenhum dos dois diz nada: a classe é o que sobra, e é melhor que um
    # número de contrato solto na coluna "Ativo".
    return {"rotulo": (classe or "—").strip(), "campo": "tipo_ativo"}


def vencimento(texto: Optional[str]) -> Optional[date]:
    """A data de vencimento escrita na descrição, quando há uma.

    Duas regras, e as duas vêm do que a descrição realmente traz:

    1. **Data precedida de "compra" não é vencimento.** É a armadilha óbvia:
       ler ``NTNB 15082040 (Compra em 06122024)`` pela ordem funciona, ler
       ``NTNB (Compra em 06122024) 15082040`` pela ordem não.
    2. **Entre as que sobram, vale a mais distante.** Um título vence depois de
       ter sido comprado, sempre; então quando a descrição traz duas datas e
       nenhuma diz qual é qual — ``NTNB_07032006_15052035``, dez casos em
       22/09/2026 —, a maior é o vencimento e a menor é a aquisição.

    Sobram seis descrições, das 761 com data, em que o próprio declarante
    inverteu os campos (``NTNB 19052025 (Compra em 15052045)``). Não há regra
    que as recupere, e é por isso que a tela mostra a descrição original ao
    lado do rótulo derivado: o que a fonte escreveu fica conferível.

    >>> vencimento("NTNB 15082040 (Compra em 06122024 Tx 67643)").isoformat()
    '2040-08-15'
    >>> vencimento("Tesouro IPCA+ com Juros Semestrais (NTNB)") is None
    True
    >>> vencimento("NTNB (Compra em 06122024) 15082040").isoformat()
    '2040-08-15'
    >>> vencimento("NTNB_07032006_15052035").isoformat()
    '2035-05-15'
    """
    if not texto:
        return None
    limpo = _sem_acento(str(texto))
    candidatas = []
    for achado in _DATA.finditer(limpo):
        antes = limpo[max(0, achado.start() - 14):achado.start()]
        if any(p in antes for p in _DE_COMPRA):
            continue
        dia, mes, ano = (int(achado.group(1)), int(achado.group(2)),
                         int(achado.group(3)))
        try:
            candidatas.append(date(ano, mes, dia))
        except ValueError:
            continue
    return max(candidatas) if candidatas else None


def sigla(texto: Optional[str]) -> Optional[str]:
    """A sigla do título do Tesouro, normalizada.

    >>> sigla("Tesouro IPCA+ com Juros Semestrais (NTNB)")
    'NTN-B'
    >>> sigla("LFT 01092026 (Compra em 12032024)")
    'LFT'
    >>> sigla("BB PREVIDENCIARIO RENDA FIXA") is None
    True
    """
    if not texto:
        return None
    alvo = re.sub(r"[^A-Z-]", " ", str(texto).upper())
    for procurada, normalizada in _SIGLAS:
        if re.search(r"\b" + re.escape(procurada) + r"\b", alvo):
            return normalizada
    return None


def titulo(texto: Optional[str]) -> Optional[Dict[str, Any]]:
    """Sigla e vencimento, quando o texto descreve um título público.

    Devolve ``None`` quando não há sigla — sem ela não há título reconhecido, e
    inventar um a partir do vencimento solto seria afirmar o que a fonte não
    disse. O vencimento pode faltar mesmo havendo sigla: é o caso dos 80% que
    trazem só o nome comercial do Tesouro Direto.

    >>> titulo("NTNB 15082040 (Compra em 06122024)")["rotulo"]
    'NTN-B 15/08/2040'
    >>> titulo("Tesouro IPCA+ (NTNB Princ)")["rotulo"]
    'NTN-B'
    >>> titulo("CAIXA BRASIL IMA-B") is None
    True
    """
    qual = sigla(texto)
    if not qual:
        return None
    venc = vencimento(texto)
    return {
        "sigla": qual,
        "vencimento": venc.isoformat() if venc else None,
        "rotulo": (qual + " " + venc.strftime("%d/%m/%Y")) if venc else qual,
    }


#: Quantos dígitos tem um CNPJ. Quando ``identificacao_ativo`` traz exatamente
#: isso, o campo é o CNPJ do fundo e identifica o ativo entre todos os RPPS.
DIGITOS_DO_CNPJ = 14

_SO_DIGITO = re.compile(r"\D")


def identidade(linha: Mapping[str, Any]) -> Tuple[Tuple[str, str], Dict[str, Any]]:
    """A chave que diz quando dois RPPS estão no mesmo ativo.

    Devolve ``(chave, dados)``. A chave é o par ``(tipo, valor)`` pelo qual o
    agregado nacional soma; ``dados`` é o que a tela mostra.

    Três identidades, porque a fonte dá três respostas:

    * **CNPJ** — nos fundos. É a única identidade forte: dois RPPS que declaram
      o mesmo CNPJ estão no mesmo fundo ainda que escrevam o nome diferente, e
      escrevem. Em 07/10/2026 identificava 3.327 dos 4.557 ativos do país.
    * **Título** — a sigla com o vencimento. Não há CNPJ num título público, e
      o que define o papel é vencer em tal data. Quem não declarou o
      vencimento entra na linha da sigla sem data, que é informação verdadeira
      sobre um conjunto, não um ativo inventado.
    * **Nome** — nem CNPJ nem sigla: CDB, poupança, imóvel, consignado em texto
      livre. Eram 1.204 ativos e 6,3% do total. Agrupar pelo nome normalizado é
      o que a fonte permite; a tela marca a linha para que ninguém confunda
      isso com identidade de registro.

    >>> chave, d = identidade({"identificacao_ativo": "30068135000150",
    ...                        "nome_ativo": "CAIXA HEDGE FIC",
    ...                        "tipo_ativo": "Fundo", "segmento": "Renda Fixa"})
    >>> chave
    ('cnpj', '30068135000150')
    >>> d["tipo_de_identidade"], d["identificacao"]
    ('cnpj', '30068135000150')
    """
    classe = (linha.get("tipo_ativo") or "").strip()
    segmento = (linha.get("segmento") or "Não informado").strip()
    escolha = nome(linha.get("nome_ativo"), linha.get("identificacao_ativo"), classe)
    rotulo = escolha["rotulo"]

    bruto = str(linha.get("identificacao_ativo") or "")
    digitos = _SO_DIGITO.sub("", bruto)
    if len(digitos) == DIGITOS_DO_CNPJ:
        return ("cnpj", digitos), {
            "nome": rotulo, "identificacao": digitos,
            "tipo_de_identidade": "cnpj",
            "segmento": segmento, "classe": classe}

    reconhecido = titulo(rotulo) if ("ítulos Públicos" in classe
                                     or "itulos Publicos" in classe) else None
    if reconhecido:
        return ("titulo", reconhecido["rotulo"]), {
            "nome": reconhecido["rotulo"],
            "identificacao": reconhecido["sigla"],
            "tipo_de_identidade": "titulo",
            "vencimento": reconhecido["vencimento"],
            "segmento": segmento, "classe": classe}

    # Nome normalizado: sem acento, sem caixa e sem espaço repetido, para que
    # "CDB  Banco do Brasil" e "cdb banco do brasil" não virem dois ativos.
    normalizado = " ".join(_sem_acento(rotulo).split())
    return ("nome", normalizado), {
        "nome": rotulo, "identificacao": None,
        "tipo_de_identidade": "nome",
        "segmento": segmento, "classe": classe}
