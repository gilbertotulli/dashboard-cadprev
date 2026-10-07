"""Baixar e converter as planilhas que a SPREV publica em HTML.

Separado de ``certificacao.py`` de propósito: ler o CSV do repositório é coisa de
todo dia, e baixar um ``.xlsx`` do gov.br é coisa de quando a SPREV republica.
Quem só quer o nível do Pró-Gestão não precisa de rede nem de ``openpyxl``.

**O endereço do arquivo muda a cada republicação** — ele carrega a data no
próprio nome (``...relacao-de-entes-24-09-2026.xlsx``). Por isso o endereço não
é fixo no código: a página de listagem é lida e o primeiro ``.xlsx`` dela é o
arquivo. Se a SPREV mudar a página, isso falha alto, com o endereço que tentou,
em vez de gravar silenciosamente uma planilha velha.
"""

import logging
import re
from typing import (Any, Dict, Iterable, Iterator, List, Optional, Sequence,
                    Tuple)

PAGINA_PROGESTAO = ("https://www.gov.br/previdencia/pt-br/assuntos/rpps/"
                    "pro-gestao-rpps-certificacao-institucional/"
                    "lista-de-entes-adesao-e-certificacao")
PAGINA_ISP = ("https://www.gov.br/previdencia/pt-br/assuntos/rpps/"
              "indice-de-situacao-previdenciaria")

#: O ISP republica a planilha preliminar antes da final, e as duas ficam na
#: mesma página. O resultado preliminar é expressamente substituído pelo final.
_PRELIMINAR = re.compile(r"prelimin|validacao|validao", re.I)

_LINK = re.compile(r'href="([^"]+\.xlsx)"', re.I)


class ErroDaPlanilha(RuntimeError):
    """A planilha não pôde ser localizada ou lida."""


#: Quantas vezes tentar antes de desistir. O gov.br derruba conexão com alguma
#: frequência no meio de um arquivo de três megabytes, e uma queda dessas não
#: diz nada sobre a planilha — só que a transferência não chegou ao fim.
TENTATIVAS = 4


def _baixar(url: str, tentativas: int = TENTATIVAS) -> bytes:
    import time
    import urllib.error
    import urllib.request
    pedido = urllib.request.Request(url, headers={"User-Agent": "dashboard-cadprev"})
    for tentativa in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(pedido, timeout=180) as resposta:
                return resposta.read()
        except urllib.error.HTTPError:
            # Resposta do servidor é resposta: 404 não melhora com insistência.
            raise
        except Exception as erro:
            if tentativa == tentativas:
                raise ErroDaPlanilha(
                    "{0} tentativas e nenhuma completou {1}: {2}".format(
                        tentativas, url, erro))
            espera = 2 ** tentativa
            logging.warning("tentativa %d de %d falhou em %s (%s); %ds",
                            tentativa, tentativas, url, erro, espera)
            time.sleep(espera)
    raise AssertionError("inalcançável")


_ANO = re.compile(r"(?:19|20)\d{2}")


def _ano_mais_alto(endereco: str) -> int:
    anos = [int(a) for a in _ANO.findall(endereco)]
    return max(anos) if anos else 0


def endereco_da_planilha(pagina: str, evitar: Optional[re.Pattern] = None) -> str:
    """O endereço do ``.xlsx`` mais recente anunciado numa página da SPREV.

    As duas páginas guardam todas as edições, e em ordens opostas: a do ISP põe
    a mais nova em cima e a do Pró-Gestão só tem uma. Escolher por posição
    acertaria numa e erraria na outra — a primeira tentativa pegou o ISP de
    2018. Vale a **maior data no nome do arquivo**, que é o que as duas páginas
    têm em comum. Empate fica com a primeira, e links que ``evitar`` casa (o
    resultado preliminar do ISP, que o final substitui) saem antes da escolha.
    """
    html = _baixar(pagina).decode("utf-8", "replace")
    achados = [u for u in _LINK.findall(html)
               if not (evitar and evitar.search(u))]
    if not achados:
        raise ErroDaPlanilha("nenhum .xlsx na página {0}".format(pagina))
    endereco = max(achados, key=_ano_mais_alto)
    if endereco.startswith("/"):
        endereco = "https://www.gov.br" + endereco
    return endereco


def _abrir(endereco: str):
    try:
        import openpyxl
    except ImportError:  # pragma: no cover - depende do ambiente
        raise ErroDaPlanilha("openpyxl não está instalado; "
                             "`pip install openpyxl` para converter as planilhas")
    import io
    return openpyxl.load_workbook(io.BytesIO(_baixar(endereco)),
                                  read_only=True, data_only=True)


def _texto(valor) -> str:
    if valor is None:
        return ""
    return " ".join(str(valor).split())


_DATA = re.compile(r"(\d{4})-(\d{2})-(\d{2})|(\d{2})/(\d{2})/(\d{4})")


def ultima_data(valor) -> str:
    """A data mais recente que a célula contém, em ISO, ou vazio.

    A planilha do Pró-Gestão guarda renovações sucessivas numa célula só
    (``26/01/2023-16/01/2026``), então ler "a data" exige escolher qual.
    """
    achadas = []
    for m in _DATA.finditer(_texto(valor)):
        if m.group(1):
            achadas.append("{0}-{1}-{2}".format(*m.group(1, 2, 3)))
        else:
            achadas.append("{0}-{1}-{2}".format(m.group(6), m.group(5), m.group(4)))
    return max(achadas) if achadas else ""


def _digitos(valor) -> str:
    so = re.sub(r"\D", "", _texto(valor))
    return so.zfill(14) if so else ""


def _cabecalho(ws, procurado: str, limite: int = 12) -> Tuple[int, List[str]]:
    """Em que linha está o cabeçalho e o que ele diz.

    As planilhas da SPREV começam com título e linhas em branco, e o número
    delas muda entre edições. Procurar a linha pelo conteúdo sobrevive a isso;
    fixar "linha 4" não sobrevive.
    """
    for n, linha in enumerate(ws.iter_rows(max_row=limite, values_only=True), start=1):
        valores = [_texto(c).upper() for c in linha]
        if procurado in valores:
            return n, valores
    raise ErroDaPlanilha(
        "nenhuma das {0} primeiras linhas tem a coluna {1!r}".format(limite, procurado))


def _coluna(cabecalho: Sequence[str], *pedacos: str) -> int:
    for i, c in enumerate(cabecalho):
        if all(p in c for p in pedacos):
            return i
    raise ErroDaPlanilha("coluna não encontrada: " + " + ".join(pedacos))


CAMPOS_PROGESTAO = ("cnpj_ente", "ente", "uf", "adesao", "certificacao",
                    "nivel_inicial", "renovacao", "nivel", "certificadora")


def ler_pro_gestao(endereco: str) -> Iterator[Dict[str, str]]:
    """As linhas da planilha de adesões e certificações, já normalizadas."""
    wb = _abrir(endereco)
    ws = wb.worksheets[0]
    n, cab = _cabecalho(ws, "CNPJ")
    return mapear_pro_gestao(cab, ws.iter_rows(min_row=n + 1, values_only=True))


def mapear_pro_gestao(cabecalho: Sequence[str],
                      linhas: Iterable[Sequence[Any]]) -> Iterator[Dict[str, str]]:
    """Casa o cabeçalho da planilha com os campos do projeto.

    Separado da leitura do arquivo de propósito: a armadilha está na **escolha
    das colunas**, não no xlsx. A planilha tem duas colunas de nível, e a
    errada — "nível inicial" — guarda o histórico numa string só, `I-II-II`
    para três certificações sucessivas. Trocar uma pela outra é uma mudança de
    uma palavra que nenhum teste de arquivo pega; com o mapeamento em função
    pura, um teste pega.
    """
    cab = list(cabecalho)
    c_cnpj = _coluna(cab, "CNPJ")
    c_ente = _coluna(cab, "ENTE")
    c_uf = _coluna(cab, "UF")
    c_adesao = _coluna(cab, "DATA", "TERMO DE ADES")
    c_cert = _coluna(cab, "CERTIFICA", "INICIAL")
    c_ni = _coluna(cab, "INICIAL", "VEL")
    c_ren = _coluna(cab, "RENOVA")
    c_nivel = _coluna(cab, "ATUAL")
    c_certa = _coluna(cab, "CERTI", "DORA")
    for linha in linhas:
        cnpj = _digitos(linha[c_cnpj])
        if len(cnpj) != 14:
            continue
        yield {
            "cnpj_ente": cnpj,
            "ente": _texto(linha[c_ente]),
            "uf": _texto(linha[c_uf]).upper(),
            # A primeira data da adesão é a do termo; a planilha traz também a
            # do recebimento, que é quando a SPREV o registrou.
            "adesao": ultima_data(linha[c_adesao]),
            "certificacao": ultima_data(linha[c_cert]),
            "nivel_inicial": _texto(linha[c_ni]),
            "renovacao": ultima_data(linha[c_ren]),
            "nivel": _texto(linha[c_nivel]),
            "certificadora": _texto(linha[c_certa]),
        }


def consolidar_pro_gestao(linhas: Iterator[Dict[str, str]]
                          ) -> Tuple[List[Dict[str, str]], List[str]]:
    """Uma linha por CNPJ, e a lista dos CNPJs que vieram repetidos.

    A planilha tem 717 linhas e 709 entes: sete CNPJs aparecem duas ou três
    vezes. A causa é sempre um registro antigo que ficou — Arvorezinha aparece
    com a adesão de 2025 já certificada e com uma adesão de 2026 sem
    certificação — e numa delas a SPREV escreveu o nome errado: o CNPJ
    46.634.218/0001-07 aparece como "Taquaritinga" e como "Taquarituba", e o
    cadastro do CADPREV diz que ele é de Taquarituba. Por isso a chave é o CNPJ
    e o nome da planilha não é usado: o painel já tem o nome certo.

    Fica a linha que **afirma mais**: o maior nível, e entre iguais a adesão
    mais recente. Deixar a última linha ganhar, que é o que um ``dict`` faz
    sozinho, daria "sem certificação" a um RPPS certificado por acidente de
    ordenação.

    Os repetidos são devolvidos à parte para a aba de qualidade poder dizer
    quantos são, em vez de a consolidação apagá-los em silêncio.
    """
    from cadprev import certificacao
    por_cnpj: Dict[str, Dict[str, str]] = {}
    repetidos: List[str] = []

    def forca(linha: Dict[str, str]) -> Tuple[int, str]:
        ordem = certificacao.ordem_do_nivel(linha.get("nivel"))
        return (-1 if ordem is None else ordem, linha.get("adesao") or "")

    for linha in linhas:
        cnpj = linha["cnpj_ente"]
        anterior = por_cnpj.get(cnpj)
        if anterior is None:
            por_cnpj[cnpj] = linha
            continue
        repetidos.append(cnpj)
        if forca(linha) > forca(anterior):
            por_cnpj[cnpj] = linha
    return (sorted(por_cnpj.values(), key=lambda l: l["cnpj_ente"]),
            sorted(set(repetidos)))


CAMPOS_ISP = ("cnpj_ente", "ente", "uf", "exercicio", "grupo", "subgrupo",
              "gestao", "financas", "atuaria", "isp")


def ler_isp(endereco: str, exercicio: str = "") -> Iterator[Dict[str, str]]:
    """As linhas da aba RESULTADO do ISP, já normalizadas.

    O exercício não está dentro da planilha em campo próprio; vem do nome do
    arquivo, e é gravado em cada linha para que a tela possa dizer de que ano é
    a nota sem depender de onde o CSV foi gerado.
    """
    wb = _abrir(endereco)
    ws = wb["RESULTADO"] if "RESULTADO" in wb.sheetnames else wb.worksheets[0]
    n, cab = _cabecalho(ws, "ENTE")
    return mapear_isp(cab, ws.iter_rows(min_row=n + 1, values_only=True),
                      exercicio)


def mapear_isp(cabecalho: Sequence[str], linhas: Iterable[Sequence[Any]],
               exercicio: str = "") -> Iterator[Dict[str, str]]:
    """Casa o cabeçalho da aba RESULTADO com os campos do projeto.

    Pelo mesmo motivo de ``mapear_pro_gestao``: a aba tem vinte e cinco
    colunas, três classificações por eixo e um indicador final, e pegar o eixo
    no lugar da nota é uma troca de índice que só um teste de mapeamento vê.
    """
    cab = list(cabecalho)
    c_cnpj = _coluna(cab, "CNPJ")
    c_ente = _coluna(cab, "ENTE")
    c_uf = _coluna(cab, "UF")
    c_grupo = _coluna(cab, "GRUPO")
    c_sub = _coluna(cab, "SUBGRUPO")
    c_gestao = _coluna(cab, "CLASSIFICA", "GEST")
    c_fin = _coluna(cab, "CLASSIFICA", "FINAN")
    c_atu = _coluna(cab, "CLASSIFICA", "ATU")
    c_isp = _coluna(cab, "INDICADOR DE SITUA")
    for linha in linhas:
        cnpj = _digitos(linha[c_cnpj])
        if len(cnpj) != 14:
            continue
        yield {
            "cnpj_ente": cnpj,
            "ente": _texto(linha[c_ente]),
            "uf": _texto(linha[c_uf]).upper(),
            "exercicio": exercicio,
            "grupo": _texto(linha[c_grupo]),
            "subgrupo": _texto(linha[c_sub]),
            "gestao": _texto(linha[c_gestao]),
            "financas": _texto(linha[c_fin]),
            "atuaria": _texto(linha[c_atu]),
            "isp": _texto(linha[c_isp]),
        }


def gravar(caminho: str, campos: Sequence[str], linhas: Iterator[Dict[str, str]]) -> int:
    """Grava o CSV e devolve quantas linhas gravou."""
    import csv
    materializadas = list(linhas)
    if not materializadas:
        raise ErroDaPlanilha("a planilha não rendeu nenhuma linha com CNPJ")
    with open(caminho, "w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(campos))
        escritor.writeheader()
        escritor.writerows(materializadas)
    logging.info("%s: %d linhas", caminho, len(materializadas))
    return len(materializadas)


def registrar_origem(caminho: str, qual: str, endereco: str, linhas: int) -> None:
    """Anota num JSON ao lado dos CSV de que arquivo cada um saiu.

    Sem isso a tela só poderia dizer "SPREV", e "SPREV" não diz se a relação é
    de setembro ou de três anos atrás. A data vem do **nome do arquivo**, que é
    como a SPREV versiona as duas planilhas, e não da hora da conversão: é a
    data da fonte que mede o quão atual o painel está.
    """
    import json
    import os
    anterior = {}
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as fh:
            anterior = json.load(fh)
    anterior[qual] = {"url": endereco, "arquivo": endereco.rsplit("/", 1)[-1],
                      "data": data_do_nome(endereco), "linhas": linhas}
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(anterior, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


_DATA_NO_NOME = re.compile(r"(\d{2})[_-](\d{2})[_-]((?:19|20)\d{2})")


def data_do_nome(endereco: str) -> str:
    """A data que o nome do arquivo carrega, em ISO, ou o ano sozinho.

    ``pro-gestao-rpps-relacao-de-entes-24-09-2026.xlsx`` é 2026-09-24. Quando só
    há ano — ``resultado-final-isp-2025-...`` tem os dois — vale a data mais
    alta encontrada, que é o que ``ultima_data`` já sabe fazer.
    """
    achadas = ["{2}-{1}-{0}".format(*m.groups())
               for m in _DATA_NO_NOME.finditer(endereco.rsplit("/", 1)[-1])]
    if achadas:
        return max(achadas)
    anos = _ANO.findall(endereco.rsplit("/", 1)[-1])
    return max(anos) if anos else ""


def ano_do_endereco(endereco: str) -> str:
    """O exercício que o nome do arquivo do ISP anuncia, ou vazio.

    ``resultado-final-isp-2025-_-publicado-em-04_12_2025-1.xlsx`` é 2025. O ano
    de publicação aparece depois, então vale o **primeiro** de quatro dígitos
    que vem logo após "isp".
    """
    m = re.search(r"isp[^0-9]{0,4}(20\d{2})", endereco, re.I)
    return m.group(1) if m else ""
