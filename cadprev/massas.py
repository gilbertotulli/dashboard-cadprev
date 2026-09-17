"""Civil e militar não são rótulos da mesma coisa: são massas separadas.

Só os Estados têm massa militar. Em 17/09/2026 a base nacional trazia massa
``Militar`` em 26 dos 27 governos estaduais — Minas Gerais não entrega DRAA — e
em nenhum dos 5.569 municípios. Nos governos estaduais os militares são de 14%
(Tocantins) a 39% (Rio de Janeiro) da população declarada.

A separação não é cosmética. A avaliação atuarial é própria, o plano de custeio
é próprio e a nomenclatura é própria: o militar não se aposenta — passa à
reserva e, depois, à reforma. O CADPREV grava esse grupo como
``MILITARES - APOSENTADOS``; o painel mostra o termo correto e guarda o termo da
fonte ao lado, para que a troca seja rastreável.

Duas assimetrias da fonte, que este módulo existe para absorver:

* no civil o papel está em ``tp_populacao`` (Servidores, Aposentados,
  Pensionistas) e ``no_cat_populacao`` traz a carreira (professores,
  magistrados, demais);
* no militar ``tp_populacao`` diz sempre "Militares" e é
  ``no_cat_populacao`` que traz o papel.

Somar os dois pelo mesmo campo mistura carreira com papel e perde os militares
inteiros — era o que acontecia antes desta separação.
"""

from typing import Optional, Tuple

CIVIL = "Civil"
MILITAR = "Militar"

ATIVO = "ativo"
INATIVO = "inativo"
PENSIONISTA = "pensionista"
OUTRO = "outro"

# Civil — o papel está no tipo de população.
#
# "Servidores Iminentes" fica fora de ativos e de inativos de propósito: são
# servidores que já cumpriram os requisitos e ainda não requereram o benefício.
# Contá-los como ativos infla a razão; como inativos, deprime. A fonte os
# declara à parte e o painel os mostra à parte.
_PAPEL_CIVIL = {
    "servidores": ATIVO,
    "aposentados": INATIVO,
    "pensionistas": PENSIONISTA,
    "servidores iminentes": OUTRO,
}

# Militar — o papel está na categoria de população.
_PREFIXO_MILITAR = "militares - "

_PAPEL_MILITAR = {
    "militares - ativos": ATIVO,
    "militares - aposentados": INATIVO,
    "militares - pensionistas": PENSIONISTA,
}

# O militar não se aposenta: vai para a reserva e depois para a reforma.
_ROTULO_MILITAR = {
    ATIVO: "Ativos",
    INATIVO: "Reserva e reforma",
    PENSIONISTA: "Pensionistas",
}

NOTA_NOMENCLATURA = (
    "O CADPREV grava o grupo como “MILITARES - APOSENTADOS”. "
    "Militar não se aposenta: passa à reserva e depois à reforma. O painel "
    "mostra o termo do regime e registra o termo da fonte ao lado."
)

# O que a fonte não separa, e por isso o painel não atribui: o DAIR traz a
# carteira ativo a ativo sem plano nem massa — em 17/09/2026 o campo de plano
# vinha vazio em todas as 59.843 linhas da base nacional. Patrimônio investido,
# portanto, é do RPPS inteiro; não existe patrimônio "do fundo militar" nesta
# fonte, e o painel não inventa rateio.
NOTA_CARTEIRA = (
    "O DAIR não separa a carteira por massa: o patrimônio mostrado é o do RPPS "
    "inteiro, civil e militar juntos. Não há base para reparti-lo."
)


def normalizar(massa: Optional[str]) -> Optional[str]:
    """Civil, Militar ou None — sem depender de caixa ou espaço da fonte."""
    if not massa:
        return None
    limpo = massa.strip().lower()
    if limpo.startswith("milit"):
        return MILITAR
    if limpo.startswith("civ"):
        return CIVIL
    return massa.strip()


def eh_militar(massa: Optional[str]) -> bool:
    return normalizar(massa) == MILITAR


def papel(massa: Optional[str], tipo: Optional[str],
          categoria: Optional[str]) -> str:
    """Ativo, inativo, pensionista ou outro — lendo o campo certo de cada massa."""
    if eh_militar(massa):
        return _PAPEL_MILITAR.get((categoria or "").strip().lower(), OUTRO)
    return _PAPEL_CIVIL.get((tipo or "").strip().lower(), OUTRO)


def rotulo(massa: Optional[str], tipo: Optional[str],
           categoria: Optional[str]) -> Tuple[str, Optional[str]]:
    """O rótulo do grupo e, quando o painel troca o termo, o termo da fonte.

    O segundo valor só vem preenchido quando há troca — é o que permite ao leitor
    conferir a substituição sem abrir a API.
    """
    if not eh_militar(massa):
        return ((tipo or "Não informado").strip(), None)
    origem = (categoria or "").strip()
    qual = _PAPEL_MILITAR.get(origem.lower(), OUTRO)
    traduzido = _ROTULO_MILITAR.get(qual)
    if traduzido is None:
        return (origem or "Não informado", None)
    # Só vale registrar a troca quando ela muda o que o termo diz. Encurtar
    # "MILITARES - ATIVOS" para "Ativos" dentro de um bloco já intitulado
    # "Militar" não troca nada — e a nota, repetida em toda linha, viraria
    # ruído que faz a única troca real passar despercebida.
    nu = origem.lower()
    if nu.startswith(_PREFIXO_MILITAR):
        nu = nu[len(_PREFIXO_MILITAR):].strip()
    return (traduzido, origem if traduzido.lower() != nu else None)
