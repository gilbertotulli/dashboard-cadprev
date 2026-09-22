"""O ``dair-atrasados``: uma requisição por ente, e nada apagado por ela."""

import argparse
import json
import os
import shutil
import tempfile
import unittest

from cadprev import __main__ as cli
from cadprev import fieldmap
from cadprev.store import Store

#: CNPJ de catorze dígitos: o fieldmap normaliza, e um "1" vira "00000000000001".
UM = "10000000000001"
DOIS = "10000000000002"
TRES = "10000000000003"


def _carteira(cnpj, ano, mes, valor):
    """Uma linha de carteira já no vocabulário da API."""
    return {"nr_cnpj_entidade": cnpj, "dt_ano": ano, "dt_mes_bimestre": mes,
            "no_segmento": "Renda Fixa", "no_tipo_ativo": "Títulos públicos",
            "pc_cmn": 100.0, "vl_total_atual": valor, "pc_recursos": 100.0,
            "sg_uf": "ES", "no_ente": "Teste"}


class ClienteFalso:
    """Devolve só o que foi pedido — é o contrato que o comando depende."""

    def __init__(self, base):
        self.base = base
        self.pedidos = []

    def registros(self, endpoint, **filtros):
        self.pedidos.append((endpoint, filtros))
        cnpj = filtros["nr_cnpj_entidade"]
        chave = (cnpj, filtros["dt_ano"], filtros["dt_mes_bimestre"])
        return list(self.base.get(chave, []))


class TestDairAtrasados(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="atrasados-")
        self.banco = os.path.join(self.dir, "t.sqlite3")
        self.anterior = cli.Cliente

    def tearDown(self):
        cli.Cliente = self.anterior
        shutil.rmtree(self.dir, ignore_errors=True)

    def _preparar(self):
        """Três entes: um na competência varrida, dois parados em fevereiro.

        Dois no mesmo mês de propósito — é o par que prova o escopo. Com um
        só, um escopo por competência apagaria linhas de mês nenhum e o teste
        passaria com o defeito dentro.
        """
        with Store(self.banco) as store:
            resolucao = fieldmap.resolver(
                "DAIR_IDENTIFICACAO",
                ["nr_cnpj_entidade", "dt_ano", "dt_mes", "sg_uf", "no_ente"])
            ident = []
            for cnpj, ate in ((UM, 6), (DOIS, 2), (TRES, 2)):
                for mes in range(1, ate + 1):
                    ident.append(fieldmap.aplicar(resolucao, {
                        "nr_cnpj_entidade": cnpj, "dt_ano": 2026, "dt_mes": mes,
                        "sg_uf": "ES", "no_ente": "Ente " + cnpj[-1]}))
            store.gravar("DAIR_IDENTIFICACAO", ident, {"ano": 2026})

            rc = fieldmap.resolver("DAIR_CARTEIRA", _carteira(UM, 2026, 6, 1).keys())
            store.gravar("DAIR_CARTEIRA",
                         [fieldmap.aplicar(rc, _carteira(UM, 2026, 6, 100.0))],
                         {"ano": 2026, "mes": 6})
            store.registrar_execucao("DAIR_CARTEIRA", {"ano": 2026, "mes": 6},
                                     1, None, "A")

    def _rodar(self, cliente):
        cli.Cliente = lambda **kw: cliente
        args = argparse.Namespace(banco=self.banco, uf=None, limite=None,
                                  pausa=0)
        return cli.cmd_dair_atrasados(args)

    def _atrasados(self):
        return ClienteFalso({(DOIS, 2026, 2): [_carteira(DOIS, 2026, 2, 50.0)],
                             (TRES, 2026, 2): [_carteira(TRES, 2026, 2, 70.0)]})

    def test_pede_so_a_competencia_de_quem_ficou_de_fora(self):
        """Uma requisição por ente, e nenhuma para quem já tem a dele."""
        self._preparar()
        cliente = self._atrasados()
        self.assertEqual(self._rodar(cliente), 0)
        self.assertEqual(sorted(p[1]["nr_cnpj_entidade"] for p in cliente.pedidos),
                         [DOIS, TRES])
        self.assertTrue(all(p[1]["dt_mes_bimestre"] == 2 for p in cliente.pedidos))

    def test_trazer_um_nao_apaga_o_outro(self):
        """A gravação é no escopo do ente, não no da competência.

        Dois atrasados param no mesmo mês — é o caso comum, não a exceção. Com
        escopo por competência, gravar o segundo apagaria o primeiro, e o único
        sinal seria um total nacional menor do que na carga anterior. E se o
        escopo fosse só a competência de referência, a primeira gravação
        apagaria a carteira do país inteiro.
        """
        self._preparar()
        self._rodar(self._atrasados())
        with Store(self.banco) as store:
            linhas = [dict(l) for l in store.consultar(
                "SELECT cnpj_ente, ano, mes FROM dair_carteira "
                "ORDER BY cnpj_ente")]
        self.assertEqual(linhas, [{"cnpj_ente": UM, "ano": 2026, "mes": 6},
                                  {"cnpj_ente": DOIS, "ano": 2026, "mes": 2},
                                  {"cnpj_ente": TRES, "ano": 2026, "mes": 2}])

    def test_nao_rebaixa_o_nivel_apurado_pela_varredura(self):
        """A procedência da varredura sobrevive ao complemento.

        A última execução do endpoint é quem diz em que nível o painel lê a
        separação por fundo. Registrar esta como nível desconhecido rebaixaria
        o painel inteiro para o Nível B sem que nada tivesse mudado na fonte.
        """
        self._preparar()
        self._rodar(self._atrasados())
        with Store(self.banco) as store:
            execucao = store.ultima_execucao("DAIR_CARTEIRA")
        self.assertEqual(execucao["nivel"], "A")
        filtros = json.loads(execucao["filtros"])
        self.assertEqual(filtros["mes"], 6, "a competência varrida continua dita")
        self.assertEqual(filtros["atrasados_por_ente"], 2)

    def test_fonte_fora_do_ar_desiste_em_vez_de_insistir(self):
        """Centenas de 404 a uma requisição por segundo não trazem dado nenhum
        — e o silêncio faria a fonte caída parecer base sem atrasados."""
        class Caido:
            pedidos = []

            def registros(self, endpoint, **filtros):
                Caido.pedidos.append(filtros)
                raise RuntimeError("404 Not Found")

        with Store(self.banco) as store:
            resolucao = fieldmap.resolver(
                "DAIR_IDENTIFICACAO",
                ["nr_cnpj_entidade", "dt_ano", "dt_mes", "sg_uf", "no_ente"])
            store.gravar("DAIR_IDENTIFICACAO", [
                fieldmap.aplicar(resolucao, {
                    "nr_cnpj_entidade": "1000000000{:04d}".format(n), "dt_ano": 2026, "dt_mes": 2,
                    "sg_uf": "ES", "no_ente": "E"})
                for n in range(100)], {"ano": 2026})
            rc = fieldmap.resolver("DAIR_CARTEIRA", _carteira(UM, 2026, 6, 1).keys())
            store.gravar("DAIR_CARTEIRA",
                         [fieldmap.aplicar(rc, _carteira(UM, 2026, 6, 1.0))],
                         {"ano": 2026, "mes": 6})
        self._rodar(Caido())
        self.assertEqual(len(Caido.pedidos), cli.FALHAS_SEGUIDAS,
                         "desistiu tarde demais ou cedo demais")


if __name__ == "__main__":
    unittest.main()
