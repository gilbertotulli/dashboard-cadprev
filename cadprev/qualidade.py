"""O que o próprio CADPREV contradiz.

O cadastro tem erros de digitação, e um só deles distorce o país inteiro: em
15/09/2026 uma única linha respondia por 88,49% do patrimônio nacional. Filtrar
isso por "valor muito alto" seria arbitrário — o maior RPPS do país é
legitimamente milhares de vezes maior que o menor, e nenhum corte estatístico
separa um estado grande de um erro de vírgula.

A saída é não inventar critério. Cada linha da carteira traz a posição do RPPS
**e** o patrimônio líquido do fundo onde ela está aplicada, e o mesmo fundo
aparece na carteira de centenas de RPPS. Uma posição maior que o fundo inteiro
é impossível — não por convenção, por aritmética.

Só que esse campo é ruidoso. O PL declarado para um mesmo fundo varia cinco
ordens de grandeza entre declarantes: o PATRIA PRIVATE EQUITY VII aparece com 22
declarações entre R$ 0,01 e R$ 4,42 bilhões. Divergir do consenso, portanto, não
é sinal de erro — é o estado normal do campo, e marcar RPPS por isso seria
acusar quem declarou certo com a mesma frequência de quem declarou errado.

Por isso a régua aqui é deliberadamente frouxa: a posição precisa exceder em mais
de dez vezes a **maior** declaração crível já feita para aquele fundo. Não é
calibragem fina, é margem grosseira — e é de propósito. Entre 1,01 e 1.000 vezes
a régua devolve exatamente a mesma linha, o que mostra que o resultado não vem do
parâmetro escolhido, e sim da distância entre um erro de vírgula e a realidade.

O que esta régua **não** faz: corrigir. Santo Afonso declarou a cota a R$
36.640.481,00 quando ela vale R$ 36,640481, e dividir por um milhão daria o valor
certo. Dividir seria inventar um número que a fonte não diz. A linha sai da
conta e aparece nomeada no painel de qualidade, com a evidência ao lado, para que
quem puder corrigir na fonte corrija.
"""

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from datetime import date

#: Abaixo disto o PL declarado não descreve um fundo de investimento — é
#: preenchimento simbólico. Aparece como 0,01 em dezenas de linhas, e usá-lo
#: como referência marcaria posições legítimas de milhões.
PISO_PL_CRIVEL = 100_000.0

#: Quantos RPPS precisam declarar o mesmo fundo para haver com que comparar.
MIN_DECLARANTES = 3

#: Quantas vezes a posição precisa exceder a MAIOR declaração crível do fundo.
#: Uma ordem de grandeza, contra um campo que varia várias — a margem existe
#: para que o ruído do cadastro nunca fabrique uma acusação.
MARGEM = 10.0

MARCA_POSICAO = "posicao_impossivel"

ROTULOS = {
    MARCA_POSICAO: "Posição maior que o fundo em que está aplicada",
}


def _num(valor: Any) -> Optional[float]:
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def teto_por_fundo(linhas: Iterable[Mapping[str, Any]]) -> Dict[str, float]:
    """Maior patrimônio crível já declarado para cada fundo.

    O máximo, e não a mediana, porque o objetivo não é estimar o tamanho do
    fundo: é estabelecer um limite acima do qual nenhum declarante sustenta a
    posição. Usar a mediana apertaria a régua sobre um campo que não merece
    essa precisão.
    """
    declaracoes: Dict[str, List[float]] = {}
    for linha in linhas:
        fundo = linha.get("identificacao_ativo")
        pl = _num(linha.get("pl_fundo"))
        if not fundo or pl is None or pl < PISO_PL_CRIVEL:
            continue
        declaracoes.setdefault(fundo, []).append(pl)
    return {fundo: max(valores) for fundo, valores in declaracoes.items()
            if len(valores) >= MIN_DECLARANTES}


def achados_da_carteira(linhas: Sequence[Mapping[str, Any]]
                        ) -> Tuple[Dict[int, str], List[Dict[str, Any]]]:
    """Marca as linhas que a própria base contradiz.

    Devolve o índice das linhas marcadas — por posição na sequência, para que a
    exclusão não dependa de as linhas terem identidade própria — e os achados
    com a evidência que sustenta cada um.
    """
    teto = teto_por_fundo(linhas)
    marcas: Dict[int, str] = {}
    achados: List[Dict[str, Any]] = []

    for i, linha in enumerate(linhas):
        fundo = linha.get("identificacao_ativo")
        posicao = _num(linha.get("valor_total"))
        if not fundo or posicao is None or fundo not in teto:
            continue
        limite = teto[fundo]
        if posicao <= limite * MARGEM:
            continue
        marcas[i] = MARCA_POSICAO
        achados.append({
            "marca": MARCA_POSICAO,
            "rotulo": ROTULOS[MARCA_POSICAO],
            "cnpj": linha.get("cnpj_ente"),
            "fundo": linha.get("nome_ativo"),
            "posicao": round(posicao, 2),
            "maior_pl_declarado": round(limite, 2),
            "vezes": round(posicao / limite, 1),
            "valor_unitario": _num(linha.get("valor_unitario")),
            "quantidade_cotas": _num(linha.get("quantidade_cotas")),
        })

    achados.sort(key=lambda a: -a["posicao"])
    return marcas, achados


# ---------------------------------------------------------------------------
# Marcas por ente
# ---------------------------------------------------------------------------

MARCA_DAIR = "dair_defasado"
MARCA_CRP = "crp_nao_valido"

#: Meses de defasagem do DAIR a partir dos quais o ente está fora do ritmo. O
#: normal são dois: o demonstrativo de um mês chega no mês seguinte ou no outro.
MESES_DAIR = 3

#: Meses com o CRP não-válido a partir dos quais a situação deixa de parecer
#: renovação em curso e passa a ser irregularidade instalada.
MESES_CRP = 6

ROTULOS_ENTE = {
    MARCA_DAIR: "Último DAIR com mais de {} meses de defasagem".format(MESES_DAIR),
    MARCA_CRP: "CRP não-válido há mais de {} meses".format(MESES_CRP),
}


def meses_entre(inicio: Optional[str], fim: str) -> Optional[int]:
    """Meses cheios entre duas datas ISO, ou ``None`` se a primeira faltar."""
    if not inicio:
        return None
    try:
        a = date.fromisoformat(str(inicio)[:10])
        b = date.fromisoformat(str(fim)[:10])
    except ValueError:
        return None
    meses = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        meses -= 1
    return max(0, meses)


# ---------------------------------------------------------------------------
# As chaves que o leitor liga e desliga
# ---------------------------------------------------------------------------

class Filtro:
    """Uma chave do topo do painel.

    Attributes:
        chave: nome estável, usado na URL e no nome da variante.
        rotulo: o que aparece na chave.
        padrao: se vem ligada. Só o recorte de RPPS vigente vem ligado: é
            correção de denominador, não opinião. Os outros três são juízos
            sobre a atualidade do dado, e quem lê decide.
        nota: por que a chave existe, em uma frase.
    """

    __slots__ = ("chave", "rotulo", "situacao", "padrao", "nota")

    def __init__(self, chave, rotulo, situacao, padrao, nota):
        self.chave, self.rotulo, self.situacao = chave, rotulo, situacao
        self.padrao, self.nota = padrao, nota

    def como_dicionario(self):
        return {"chave": self.chave, "rotulo": self.rotulo,
                "situacao": self.situacao, "padrao": self.padrao,
                "nota": self.nota}


FILTROS = (
    Filtro("somente_rpps", "Somente entes com RPPS vigente",
           "entes sem RPPS vigente", True,
           "O CRP é emitido ao ente federativo, não ao fundo, então a base "
           "cobre os 5.596 entes do país. Sem este recorte, os 3.411 que "
           "migraram para o RGPS entram nos percentuais como se fossem RPPS."),
    Filtro("sem_lancamento_impossivel",
           "Excluir RPPS com lançamento impossível",
           "RPPS com lançamento impossível", False,
           "O lançamento em si já está fora de toda soma, sempre. Esta chave "
           "vai além e descarta o RPPS inteiro, para quem prefere não usar "
           "nenhum número de quem errou um deles."),
    Filtro("sem_dair_defasado",
           "Excluir DAIR defasado há mais de {} meses".format(MESES_DAIR),
           "RPPS com DAIR defasado há mais de {} meses".format(MESES_DAIR), False,
           "Mede a distância entre hoje e a data de posição do último "
           "demonstrativo entregue. O ritmo normal é de dois meses."),
    Filtro("sem_crp_vencido",
           "Excluir CRP não-válido há mais de {} meses".format(MESES_CRP),
           "Entes com CRP não-válido há mais de {} meses".format(MESES_CRP), False,
           "Vencimento recente costuma ser renovação em curso; meio ano "
           "depois, já é irregularidade instalada."),
)

#: Marca que cada filtro procura no ente. ``somente_rpps`` não olha marca — olha
#: o regime — e por isso não aparece aqui.
_MARCA_DO_FILTRO = {
    "sem_lancamento_impossivel": MARCA_POSICAO,
    "sem_dair_defasado": MARCA_DAIR,
    "sem_crp_vencido": MARCA_CRP,
}


def chave_padrao() -> str:
    return "".join("1" if f.padrao else "0" for f in FILTROS)


def combinacoes():
    """Todas as combinações de chaves, como strings de zeros e uns."""
    for n in range(2 ** len(FILTROS)):
        yield format(n, "0{}b".format(len(FILTROS)))


def ligados(combinacao: str):
    """Os filtros ativos numa combinação."""
    return [f for f, bit in zip(FILTROS, combinacao) if bit == "1"]


def entes_fora(entes: Mapping[str, Mapping[str, Any]],
               marcas: Mapping[str, Mapping[str, Any]],
               combinacao: str) -> set:
    """Quem fica de fora das estatísticas nacionais nesta combinação."""
    fora = set()
    for filtro in ligados(combinacao):
        if filtro.chave == "somente_rpps":
            fora |= {c for c, d in entes.items() if not d.get("tem_rpps")}
            continue
        alvo = _MARCA_DO_FILTRO[filtro.chave]
        fora |= {c for c, m in marcas.items() if alvo in m}
    return fora
