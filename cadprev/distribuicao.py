"""Como resumir um conjunto de RPPS sem que um estado responda pelo país.

O patrimônio dos regimes próprios é concentrado: uns poucos RPPS estaduais
reúnem a maior parte de tudo, e qualquer média puxada por eles descreve um RPPS
que não existe. Por isso a **mediana lidera** todo quadro consolidado deste
painel, com os quartis ao lado para dizer onde está a metade do meio.

A média e o desvio padrão continuam publicados, num segundo plano, porque há
perguntas que só eles respondem — e porque a distância entre média e mediana é,
ela própria, a medida da concentração. O que não se faz é mostrar a média
sozinha.

Grupos de menos de três não produzem estatística: com dois RPPS, "mediana" é a
média deles e "quartil" não quer dizer nada. Nesses casos o resumo diz quantos
são e para por aí — que é diferente de dizer zero.
"""

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

#: Abaixo disto não há distribuição a descrever, só os próprios números.
MINIMO = 3


def _quantil(ordenados: Sequence[float], q: float) -> float:
    """Quantil por interpolação linear, como o método 7 do R e o do NumPy.

    >>> _quantil([1, 2, 3, 4], 0.5)
    2.5
    >>> _quantil([1, 2, 3, 4], 0.25)
    1.75
    """
    if len(ordenados) == 1:
        return float(ordenados[0])
    posicao = (len(ordenados) - 1) * q
    baixo = math.floor(posicao)
    alto = math.ceil(posicao)
    if baixo == alto:
        return float(ordenados[baixo])
    return (float(ordenados[baixo]) * (alto - posicao)
            + float(ordenados[alto]) * (posicao - baixo))


def resumir(valores: Iterable[Optional[float]],
            minimo: int = MINIMO) -> Dict[str, Any]:
    """A distribuição de um indicador, com a mediana à frente.

    ``None`` não entra: indicador que não pôde ser calculado é indefinido, e
    tratá-lo como zero mudaria a mediana em favor de quem não declarou.

    >>> r = resumir([10, 20, 30, 40, 1000])
    >>> r["mediana"], r["n"]
    (30.0, 5)
    >>> r["media"] > r["mediana"]        # a cauda puxa a média, não a mediana
    True
    >>> resumir([5, 7])["disponivel"]
    False
    >>> resumir([5, 7])["n"]
    2
    """
    limpos: List[float] = [float(v) for v in valores
                           if v is not None and not _nan(v)]
    if len(limpos) < minimo:
        return {"disponivel": False, "n": len(limpos), "minimo": minimo}
    limpos.sort()
    media = sum(limpos) / len(limpos)
    # Desvio amostral (n−1): o conjunto é os RPPS que declararam, não a
    # população inteira dos que existem.
    variancia = (sum((v - media) ** 2 for v in limpos) / (len(limpos) - 1)
                 if len(limpos) > 1 else 0.0)
    return {
        "disponivel": True,
        "n": len(limpos),
        "soma": round(sum(limpos), 2),
        "mediana": round(_quantil(limpos, 0.5), 2),
        "p25": round(_quantil(limpos, 0.25), 2),
        "p75": round(_quantil(limpos, 0.75), 2),
        "minimo_obs": round(limpos[0], 2),
        "maximo_obs": round(limpos[-1], 2),
        "media": round(media, 2),
        "desvio": round(math.sqrt(variancia), 2),
    }


def _nan(valor: Any) -> bool:
    try:
        return math.isnan(float(valor))
    except (TypeError, ValueError):
        return True


def concentracao(resumo: Dict[str, Any]) -> Optional[float]:
    """Quantas vezes a média é maior que a mediana.

    É a leitura curta da concentração, e o motivo de a mediana liderar: um
    valor perto de 1 diz que média e mediana contam a mesma história; 5 diz que
    a média descreve os maiores, não o RPPS típico.

    >>> concentracao({"disponivel": True, "media": 100.0, "mediana": 20.0})
    5.0
    >>> concentracao({"disponivel": False}) is None
    True
    """
    if not resumo.get("disponivel") or not resumo.get("mediana"):
        return None
    return round(resumo["media"] / resumo["mediana"], 2)
