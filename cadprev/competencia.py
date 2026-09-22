"""Qual competência do DAIR já está fechada.

O workflow escolhia a competência por aritmética de calendário: ano corrente,
mês de três meses atrás. Funciona em nove meses do ano e quebra nos outros três
— em janeiro, "três meses atrás" é outubro, mas o ano continua sendo o corrente,
e pede-se uma competência que ainda não aconteceu. A carga voltaria vazia, a
guarda de endpoint essencial derrubaria o job, e o painel ficaria sem atualizar
de janeiro a março sem que ninguém entendesse por quê.

Aritmética de calendário também não sabe o que a fonte já publicou. Em 16/09/2026
a competência 8 tinha 17 linhas no país inteiro — existe, mas está começando a
ser preenchida, e publicá-la mostraria um patrimônio nacional de quase zero.

A saída é não adivinhar: pergunta-se à API. Uma página de cada competência,
caminhando para trás, e escolhe-se a mais recente que esteja substancialmente
cheia em relação à melhor vista. O critério é relativo de propósito — com filtro
de UF os volumes são duas ordens de grandeza menores, e qualquer piso absoluto
estaria errado num dos dois casos.

O que se conta é **declarante**, não linha de carteira, e a diferença é a que
separa esta régua de uma armadilha. A primeira versão contava linhas do
DAIR_CARTEIRA, que vêm paginadas de 5.000 em 5.000: em 17/09/2026 os meses 4, 5,
6 e 7 devolviam todos exatamente 5.000 na primeira página, indistinguíveis entre
si. Só que o mês 7 tinha 318 declarantes contra 1.882 do mês 6 — 15% dos RPPS —,
e escolhê-lo publicaria um patrimônio nacional de sessenta bilhões onde há
quatrocentos e onze.

O DAIR_IDENTIFICACAO traz uma linha por declaração, cerca de duas mil por mês, e
por isso cabe inteiro numa página: a contagem é exata, não saturada. Quando ainda
assim ela encostar no limite de paginação, a medida deixou de ser confiável e o
módulo diz isso em vez de ordenar competências por um número que empatou.
"""

from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from datetime import date

from . import endpoints

#: Quantas competências medir, a partir do mês anterior ao corrente. Treze
#: cobrem o ano inteiro mais a virada, e ainda assim é uma requisição por mês —
#: barato contra uma carga que leva vinte minutos.
#:
#: A janela inteira é medida antes de escolher, e isso não é desperdício: o
#: critério é relativo ao maior volume visto, e parar cedo o quebraria. Andando
#: para trás a partir de agosto de 2026, o primeiro mês visto tinha uma única
#: declaração — metade de um é meio, e uma parada antecipada teria escolhido
#: justamente o mês mais vazio da série.
MESES_PARA_TRAS = 13

#: Fração do maior volume visto a partir da qual a competência é considerada
#: fechada. Metade é folgado: a diferença entre um mês publicado e um mês em
#: preenchimento é de ordens de grandeza, não de porcentagem.
FRACAO_FECHADA = 0.5


def _anterior(ano: int, mes: int) -> Tuple[int, int]:
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


class MedidaSaturada(RuntimeError):
    """A contagem encostou no limite de paginação e não distingue mais nada."""


def volumes(cliente: Any, hoje: Optional[date] = None,
            uf: Optional[str] = None,
            meses: int = MESES_PARA_TRAS) -> List[Tuple[int, int, int]]:
    """Quantos RPPS declararam DAIR em cada competência recente.

    A caminhada começa no mês anterior, não no corrente. A competência do DAIR é
    uma posição do último dia do mês: enquanto o mês corre, não há o que
    declarar, e a consulta volta vazia todas as vezes. Era uma requisição
    desperdiçada por execução, e foi ela que apareceu no log da falha de
    21/09 — ``dt_mes=9`` pedido no dia 21 de setembro, um mês que ainda não
    tinha acabado.
    """
    hoje = hoje or date.today()
    ano, mes = _anterior(hoje.year, hoje.month)
    vistos: List[Tuple[int, int, int]] = []
    for _ in range(meses):
        filtros = {"dt_ano": ano, "dt_mes": mes}
        if uf:
            filtros["sg_uf"] = uf
        pagina = cliente.pagina("DAIR_IDENTIFICACAO", offset=0, **filtros)
        quantos = len(pagina.get("data") or [])
        if quantos >= endpoints.PAGE_SIZE:
            raise MedidaSaturada(
                "{}/{} devolveu a página cheia ({} declarações): a contagem "
                "saturou e não serve para comparar competências."
                .format(mes, ano, quantos))
        vistos.append((ano, mes, quantos))
        ano, mes = _anterior(ano, mes)
    return vistos


def mais_recente_fechada(cliente: Any, hoje: Optional[date] = None,
                         uf: Optional[str] = None,
                         meses: int = MESES_PARA_TRAS
                         ) -> Optional[Tuple[int, int]]:
    """A competência mais recente que a fonte já publicou por inteiro.

    Devolve ``None`` quando nenhuma competência tem linha nenhuma — situação em
    que adivinhar seria pior do que falhar alto e deixar quem chamou decidir.
    """
    vistos = volumes(cliente, hoje, uf, meses)
    return escolher(vistos)


def escolher(vistos: List[Tuple[int, int, int]]) -> Optional[Tuple[int, int]]:
    """A competência fechada mais recente, dada a medida de cada uma.

    Separada de ``volumes`` para que a escolha possa ser conferida sem rede — e
    para que quem chama possa mostrar a medida ao lado da escolha, que é o que
    torna uma competência errada diagnosticável pelo log.
    """
    melhor = max((linhas for _, _, linhas in vistos), default=0)
    if not melhor:
        return None
    piso = melhor * FRACAO_FECHADA
    for ano, mes, linhas in vistos:      # já vem do mais recente para o mais antigo
        if linhas >= piso:
            return ano, mes
    return None


def ultima_de_cada(linhas: Iterable[Mapping[str, Any]]) -> Dict[str, Tuple[int, int]]:
    """A última competência que cada ente declarou.

    O par (ano, mês) se compara inteiro. ``MAX(ano)`` e ``MAX(mes)`` separados
    dariam dezembro do ano mais recente para quem declarou dezembro de 2025 e
    março de 2026 — uma competência que o ente nunca entregou, e que o painel
    sairia pedindo à API.

    >>> ultima_de_cada([{"cnpj_ente": "1", "ano": 2025, "mes": 12},
    ...                 {"cnpj_ente": "1", "ano": 2026, "mes": 3}])
    {'1': (2026, 3)}
    """
    ultimas: Dict[str, Tuple[int, int]] = {}
    for linha in linhas:
        cnpj = linha.get("cnpj_ente")
        ano, mes = linha.get("ano"), linha.get("mes")
        if not cnpj or ano is None or mes is None:
            continue
        atual = ultimas.get(cnpj)
        if atual is None or (ano, mes) > atual:
            ultimas[cnpj] = (ano, mes)
    return ultimas
