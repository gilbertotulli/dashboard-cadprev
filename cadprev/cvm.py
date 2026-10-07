"""Cliente dos dados abertos da CVM — o PL e os cotistas oficiais de cada fundo.

Terceira fonte do projeto, e a primeira que não fala de RPPS. Ela fala de
**fundos**, e é por aí que serve: a carteira do DAIR traz o CNPJ do fundo em que
cada RPPS aplicou, e a CVM publica, para esse mesmo CNPJ, o patrimônio líquido e
o número de cotistas apurados pelo administrador.

Isso resolve dois problemas que as outras fontes não resolviam:

* **O PL declarado pelo RPPS é ruidoso.** O mesmo fundo aparece na carteira de
  centenas de RPPS, cada um declara o PL dele, e eles discordam — de 867 fundos
  com PL declarado em 07/10/2026, 557 tinham mais de um valor distinto, com
  dispersão mediana de 85%. A CVM tem um número só, do administrador.
* **A régua de impossibilidade ganha fonte externa.** Uma posição maior que o
  fundo inteiro é impossível, e o painel já checava isso contra o maior PL que
  algum RPPS declarou — critério frouxo de propósito, porque o campo é ruim.
  Contra o PL oficial, a checagem fica firme: em setembro de 2026, 29 fundos
  tinham a soma das posições dos RPPS acima do PL da CVM, o pior em 7,5 vezes.

**A cobertura é parcial, e a assimetria importa.** Dos 3.327 fundos com CNPJ que
os RPPS declaram, 655 aparecem no informe diário — 19,7% por contagem e **95,5%
do valor**. Os que faltam são pequenos; o maior deles tem R$ 3,3 bi. Duas causas
prováveis: a reestruturação da Resolução CVM 175 partiu fundos em classes com
CNPJ novo, e parte do que o RPPS declara com CNPJ não é fundo (emissor de CDB,
banco). O painel diz quando não achou, em vez de mostrar vazio sem explicação.

O arquivo é mensal, com uma linha por fundo **por dia**: 54 MB de CSV para um
mês. O cliente lê em fluxo e guarda só a última data de cada CNPJ — é a posição
de fechamento que interessa, e carregar o mês inteiro na memória custaria
centenas de megabytes para descartar 95% deles.
"""

import csv
import io
import logging
import os
import re
import time
import urllib.error
import urllib.request
import zipfile
from typing import Any, Dict, Iterator, Optional

log = logging.getLogger(__name__)

BASE_URL = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS"

#: Identificação enviada no cabeçalho. Um serviço público tem direito de saber
#: quem o está consultando.
AGENTE = "painel-cadprev (github.com/gilbertotulli/dashboard-cadprev)"

#: O CNPJ do fundo mudou de nome quando a Resolução CVM 175 separou classes:
#: antes ``CNPJ_FUNDO``, hoje ``CNPJ_FUNDO_CLASSE``. O cliente aceita os dois
#: para que um arquivo antigo continue legível.
CHAVES_DO_CNPJ = ("CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO")

_SO_DIGITO = re.compile(r"\D")


class ErroDaCvm(RuntimeError):
    """O arquivo não veio, ou veio o que não dá para usar."""


def _numero(valor: Optional[str]) -> Optional[float]:
    if valor is None or valor == "":
        return None
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return None


def _inteiro(valor: Optional[str]) -> Optional[int]:
    numero = _numero(valor)
    return None if numero is None else int(numero)


class Cliente:
    """Baixa o informe diário de um mês e devolve o fechamento de cada fundo."""

    def __init__(self, base_url: str = BASE_URL, tentativas: int = 4,
                 timeout: float = 300.0, pausa: float = 1.0,
                 fixtures: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.tentativas = tentativas
        self.timeout = timeout
        self.pausa = pausa
        self.fixtures = fixtures

    def _abrir(self, ano: int, mes: int) -> bytes:
        nome = "inf_diario_fi_{:04d}{:02d}.zip".format(ano, mes)
        if self.fixtures:
            caminho = os.path.join(self.fixtures, nome)
            if not os.path.exists(caminho):
                raise ErroDaCvm("fixture ausente: " + caminho)
            with open(caminho, "rb") as fh:
                return fh.read()
        url = self.base_url + "/" + nome
        espera = self.pausa
        for tentativa in range(1, self.tentativas + 1):
            try:
                pedido = urllib.request.Request(
                    url, headers={"User-Agent": AGENTE})
                with urllib.request.urlopen(pedido, timeout=self.timeout) as r:
                    return r.read()
            except urllib.error.HTTPError as erro:
                # 404 é resposta, não falha: o mês ainda não foi publicado.
                if erro.code == 404:
                    raise ErroDaCvm(
                        "{} não existe na CVM — o mês ainda não foi publicado"
                        .format(nome))
                if tentativa == self.tentativas:
                    raise ErroDaCvm("{}: {}".format(url, erro))
            except Exception as erro:  # rede
                if tentativa == self.tentativas:
                    raise ErroDaCvm("{}: {}".format(url, erro))
            log.warning("falha em %s (tentativa %d/%d): repetindo em %.0fs",
                        nome, tentativa, self.tentativas, espera)
            time.sleep(espera)
            espera *= 2
        raise ErroDaCvm(url)

    def fechamento(self, ano: int, mes: int) -> Dict[str, Dict[str, Any]]:
        """O último dia declarado de cada fundo no mês, por CNPJ.

        Lê o CSV em fluxo: são 54 MB para um mês, uma linha por fundo por dia, e
        o que interessa é a última. Guardar o mês inteiro custaria centenas de
        megabytes para descartar quase tudo.
        """
        bruto = self._abrir(ano, mes)
        try:
            arquivo = zipfile.ZipFile(io.BytesIO(bruto))
        except zipfile.BadZipFile as erro:
            raise ErroDaCvm("o arquivo da CVM não é um zip: {}".format(erro))
        nomes = [n for n in arquivo.namelist() if n.lower().endswith(".csv")]
        if not nomes:
            raise ErroDaCvm("o zip da CVM não traz CSV")

        por_cnpj: Dict[str, Dict[str, Any]] = {}
        with arquivo.open(nomes[0]) as fh:
            texto = io.TextIOWrapper(fh, encoding="latin-1", newline="")
            leitor = csv.DictReader(texto, delimiter=";")
            campo = next((c for c in CHAVES_DO_CNPJ
                          if c in (leitor.fieldnames or [])), None)
            if not campo:
                raise ErroDaCvm(
                    "o CSV da CVM não traz nenhuma das colunas de CNPJ "
                    "conhecidas ({})".format(", ".join(CHAVES_DO_CNPJ)))
            for registro in leitor:
                cnpj = _SO_DIGITO.sub("", registro.get(campo) or "")
                data = (registro.get("DT_COMPTC") or "").strip()
                if len(cnpj) != 14 or not data:
                    continue
                anterior = por_cnpj.get(cnpj)
                if anterior is not None and anterior["data"] >= data:
                    continue
                por_cnpj[cnpj] = {
                    "cnpj_fundo": cnpj,
                    "data": data,
                    "patrimonio_liquido": _numero(registro.get("VL_PATRIM_LIQ")),
                    "cotistas": _inteiro(registro.get("NR_COTST")),
                    "valor_cota": _numero(registro.get("VL_QUOTA")),
                    "tipo": (registro.get("TP_FUNDO_CLASSE")
                             or registro.get("TP_FUNDO") or None),
                }
        if not por_cnpj:
            raise ErroDaCvm("o informe da CVM veio sem nenhum fundo legível")
        log.info("CVM %04d-%02d: %d fundos", ano, mes, len(por_cnpj))
        return por_cnpj

    def registros(self, ano: int, mes: int) -> Iterator[Dict[str, Any]]:
        """O fechamento como sequência, no formato que a ingestão grava."""
        for dados in self.fechamento(ano, mes).values():
            yield dict(dados, exercicio=ano, mes=mes)
