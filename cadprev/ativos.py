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
from typing import Any, Dict, Optional

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
