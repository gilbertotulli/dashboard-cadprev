"""Comparação de um RPPS contra um grupo de referência.

Por que indicadores, e não valores
----------------------------------
Comparar o patrimônio de um RPPS estadual com o de um município de cinco mil
habitantes não informa nada: a diferença é de porte, não de gestão. O que
compara é a razão — patrimônio por beneficiário, resultado sobre ingressos,
despesa média por inativo. Todos os indicadores aqui são normalizados por
tamanho ou expressos em percentual.

Por que mediana, e não média
----------------------------
As distribuições são fortemente assimétricas: uns poucos RPPS estaduais
concentram a maior parte do patrimônio e puxariam qualquer média para longe do
RPPS típico. A mediana responde "como está o RPPS do meio", que é a pergunta
que o comparativo faz. Os quartis vão junto, para que a posição seja lida
dentro da dispersão e não contra um ponto só.

Sobre direção
-------------
Alguns indicadores têm direção clara — mais ativos por inativo é melhor. Outros
não: uma carteira mais concentrada em renda fixa é mais segura e rende menos, e
qual dos dois importa depende da política de investimentos do RPPS. Só os de
direção inequívoca são marcados; os demais aparecem sem juízo de valor.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from . import grupos

#: Faixas de porte, por número de segurados (ativos + aposentados + pensionistas).
#: Os cortes são redondos de propósito: servem para agrupar, não para classificar
#: oficialmente nada, e um corte redondo é mais fácil de conferir.
FAIXAS_PORTE = (
    (1000, "pequeno", "Até 1.000 segurados"),
    (10000, "medio", "De 1.000 a 10.000 segurados"),
    (None, "grande", "Acima de 10.000 segurados"),
)


@dataclass(frozen=True)
class Indicador:
    """Um indicador comparável entre RPPS.

    Attributes:
        chave: nome estável usado nos arquivos e na interface.
        rotulo: como aparece na tela.
        unidade: ``percentual``, ``reais`` ou ``razao``.
        direcao: ``maior`` ou ``menor`` quando há direção inequívoca,
            ``None`` quando o juízo depende da política do RPPS.
        nota: o que o número quer dizer, em uma frase.
        fonte: endpoints de origem.
    """

    chave: str
    rotulo: str
    unidade: str
    direcao: Optional[str]
    nota: str
    fonte: str


INDICADORES: Sequence[Indicador] = (
    Indicador("razao_ativos_inativos", "Ativos por inativo", "razao", "maior",
              "Quantos servidores na ativa sustentam cada aposentado ou "
              "pensionista. Abaixo de 1, a massa já inverteu.",
              "DRAA_ESTATISTICA"),
    Indicador("patrimonio_por_beneficiario", "Patrimônio por beneficiário",
              "reais", "maior",
              "Quanto há investido para cada aposentado e pensionista na folha.",
              "DAIR_CARTEIRA + DRAA_ESTATISTICA"),
    Indicador("cobertura_atuarial", "Cobertura das provisões", "percentual",
              "maior",
              "Quanto dos compromissos já está lastreado por ativos "
              "garantidores.", "DRAA_VALORES_COMPROMISSOS"),
    Indicador("resultado_sobre_ingressos", "Resultado sobre ingressos",
              "percentual", None,
              "Quanto sobrou do que entrou no período. Depende do estágio do "
              "plano: um regime maduro gasta o que acumulou.", "DIPR"),
    Indicador("despesa_por_inativo", "Despesa mensal por inativo", "reais",
              None,
              "Valor médio pago por beneficiário. Reflete o perfil da carreira, "
              "não a eficiência da gestão.", "DIPR + DRAA_ESTATISTICA"),
    Indicador("perc_renda_fixa", "Carteira em renda fixa", "percentual", None,
              "Concentração no segmento mais conservador. Mais seguro e menos "
              "rentável — qual dos dois pesa é decisão de política.",
              "DAIR_CARTEIRA"),
    Indicador("aliquota_ente", "Alíquota do ente", "percentual", None,
              "Contribuição patronal vigente declarada.", "RPPS_ALIQUOTA"),
)

POR_CHAVE: Dict[str, Indicador] = {i.chave: i for i in INDICADORES}

ROTULOS_PORTE = {chave: rotulo for _, chave, rotulo in FAIXAS_PORTE}


def porte(segurados: Optional[int]) -> Optional[str]:
    """Faixa de porte a partir do total de segurados.

    >>> porte(400)
    'pequeno'
    >>> porte(5000)
    'medio'
    >>> porte(42000)
    'grande'
    >>> porte(None) is None
    True
    """
    if not segurados:
        return None
    for limite, chave, _ in FAIXAS_PORTE:
        if limite is None or segurados < limite:
            return chave
    return "grande"


def calcular(ficha: Mapping[str, Any]) -> Dict[str, Optional[float]]:
    """Extrai os indicadores de uma ficha já montada.

    Um indicador que não pode ser calculado vira ``None`` e fica de fora das
    estatísticas do grupo — nunca zero, que seria lido como valor real.
    """
    est = ficha.get("estatistica") or {}
    caixa = ficha.get("caixa") or {}
    carteira = ficha.get("carteira") or {}
    atuaria = ficha.get("atuaria") or {}

    inativos = est.get("inativos") or 0
    patrimonio = carteira.get("total") if carteira.get("disponivel") else None
    receita = caixa.get("total_receita") if caixa.get("disponivel") else None
    despesa = caixa.get("total_despesa") if caixa.get("disponivel") else None
    meses = caixa.get("meses_declarados") or 0

    resultado: Dict[str, Optional[float]] = {
        "razao_ativos_inativos": est.get("razao_ativos_inativos"),
        "patrimonio_por_beneficiario": (
            round(patrimonio / inativos, 2)
            if patrimonio and inativos else None),
        "cobertura_atuarial": _cobertura(atuaria),
        "resultado_sobre_ingressos": (
            round((receita - despesa) / receita * 100, 2)
            if receita and despesa is not None and receita > 0 else None),
        # Divide pelos meses efetivamente declarados, não por doze: um RPPS que
        # informou metade do ano não tem despesa mensal pela metade.
        "despesa_por_inativo": (
            round(despesa / meses / inativos, 2)
            if despesa and meses and inativos else None),
        "perc_renda_fixa": _perc_renda_fixa(carteira),
        "aliquota_ente": _aliquota_ente(ficha.get("aliquotas") or []),
    }
    return resultado


def _cobertura(atuaria: Mapping[str, Any]) -> Optional[float]:
    if not atuaria.get("disponivel"):
        return None
    r = atuaria.get("resultado") or {}
    provisoes = r.get("provisoes") or 0
    ativos = r.get("ativos_garantidores") or 0
    if not provisoes:
        return None
    return round(ativos / provisoes * 100, 2)


def _perc_renda_fixa(carteira: Mapping[str, Any]) -> Optional[float]:
    if not carteira.get("disponivel"):
        return None
    for segmento in carteira.get("segmentos") or []:
        if (segmento.get("rotulo") or "").strip().lower().startswith("renda fixa"):
            return segmento.get("perc")
    return 0.0


def _aliquota_ente(aliquotas: Sequence[Mapping[str, Any]]) -> Optional[float]:
    """Alíquota patronal vigente. 'Ente-suplementar' não entra: é amortização
    de déficit, não custeio normal, e somá-la mudaria o que se compara."""
    for linha in aliquotas:
        vigente = (linha.get("vigente") or "").upper()
        if vigente and "NÃO" in vigente.replace("NAO", "NÃO"):
            continue
        if (linha.get("sujeito_passivo") or "").strip().lower() == "ente":
            return linha.get("aliquota")
    return None


# ---------------------------------------------------------------------------
# Estatísticas de grupo
# ---------------------------------------------------------------------------

def _percentil(ordenados: List[float], p: float) -> float:
    """Percentil por interpolação linear, como o método padrão do NumPy."""
    if not ordenados:
        raise ValueError("lista vazia")
    if len(ordenados) == 1:
        return ordenados[0]
    posicao = (len(ordenados) - 1) * p
    baixo = int(posicao)
    alto = min(baixo + 1, len(ordenados) - 1)
    peso = posicao - baixo
    return ordenados[baixo] * (1 - peso) + ordenados[alto] * peso


def resumir(valores: Sequence[Optional[float]]) -> Optional[Dict[str, float]]:
    """Mediana, quartis e extremos de um conjunto de valores.

    Grupos com menos de três RPPS não produzem estatística: quartis sobre dois
    pontos são aritmética, não informação.
    """
    limpos = sorted(v for v in valores if v is not None)
    if len(limpos) < 3:
        return None
    return {
        "n": len(limpos),
        "min": round(limpos[0], 2),
        "p25": round(_percentil(limpos, 0.25), 2),
        "mediana": round(_percentil(limpos, 0.50), 2),
        "p75": round(_percentil(limpos, 0.75), 2),
        "max": round(limpos[-1], 2),
    }


def posicao(valor: Optional[float], valores: Sequence[Optional[float]]
            ) -> Optional[int]:
    """Percentil em que o valor se encontra dentro do grupo, de 0 a 100."""
    limpos = sorted(v for v in valores if v is not None)
    if valor is None or len(limpos) < 3:
        return None
    abaixo = sum(1 for v in limpos if v < valor)
    return round(abaixo / len(limpos) * 100)


def montar(fichas: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """Indicadores por RPPS e estatísticas de cada grupo de referência.

    Args:
        fichas: mapa de CNPJ para a ficha montada em ``build``.
    """
    indicadores: Dict[str, Dict[str, Any]] = {}
    for cnpj, ficha in fichas.items():
        est = ficha.get("estatistica") or {}
        segurados = (est.get("ativos") or 0) + (est.get("inativos") or 0)
        indicadores[cnpj] = {
            "ente": ficha.get("ente"),
            "uf": ficha.get("uf"),
            "regiao": ficha.get("regiao"),
            "esfera": ficha.get("esfera"),
            "segurados": segurados or None,
            "porte": porte(segurados),
            "valores": calcular(ficha),
        }

    def _grupo(filtro) -> Dict[str, Any]:
        membros = [d for d in indicadores.values() if filtro(d)]
        estatisticas = {}
        for indicador in INDICADORES:
            valores = [m["valores"].get(indicador.chave) for m in membros]
            resumo = resumir(valores)
            if resumo:
                estatisticas[indicador.chave] = resumo
        return {"rpps": len(membros), "estatisticas": estatisticas}

    regioes = {r: _grupo(lambda d, r=r: d["regiao"] == r)
               for r in grupos.ORDEM_REGIOES
               if any(d["regiao"] == r for d in indicadores.values())}
    portes = {p: _grupo(lambda d, p=p: d["porte"] == p)
              for _, p, _ in FAIXAS_PORTE
              if any(d["porte"] == p for d in indicadores.values())}

    return {
        "indicadores": [
            {"chave": i.chave, "rotulo": i.rotulo, "unidade": i.unidade,
             "direcao": i.direcao, "nota": i.nota, "fonte": i.fonte}
            for i in INDICADORES
        ],
        "rotulos_porte": ROTULOS_PORTE,
        "grupos": {
            "brasil": _grupo(lambda d: True),
            "regiao": regioes,
            "porte": portes,
        },
        "rpps": indicadores,
    }
