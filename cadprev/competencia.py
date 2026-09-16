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
"""

from typing import Any, List, Optional, Tuple
from datetime import date

#: Até quando caminhar para trás. Catorze meses cobrem o ano inteiro mais a
#: virada, e ainda assim é uma requisição por mês — barato contra uma carga que
#: leva vinte minutos.
MESES_PARA_TRAS = 14

#: Fração do maior volume visto a partir da qual a competência é considerada
#: fechada. Metade é folgado: a diferença entre um mês publicado e um mês em
#: preenchimento é de ordens de grandeza, não de porcentagem.
FRACAO_FECHADA = 0.5


def _anterior(ano: int, mes: int) -> Tuple[int, int]:
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def volumes(cliente: Any, hoje: Optional[date] = None,
            uf: Optional[str] = None,
            meses: int = MESES_PARA_TRAS) -> List[Tuple[int, int, int]]:
    """Quantas linhas a primeira página traz em cada competência recente."""
    hoje = hoje or date.today()
    ano, mes = hoje.year, hoje.month
    vistos: List[Tuple[int, int, int]] = []
    for _ in range(meses):
        filtros = {"dt_ano": ano, "dt_mes_bimestre": mes}
        if uf:
            filtros["sg_uf"] = uf
        pagina = cliente.pagina("DAIR_CARTEIRA", offset=0, **filtros)
        vistos.append((ano, mes, len(pagina.get("data") or [])))
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
    melhor = max((linhas for _, _, linhas in vistos), default=0)
    if not melhor:
        return None
    piso = melhor * FRACAO_FECHADA
    for ano, mes, linhas in vistos:      # já vem do mais recente para o mais antigo
        if linhas >= piso:
            return ano, mes
    return None
