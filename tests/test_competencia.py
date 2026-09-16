"""Descoberta da competência do DAIR.

Os volumes destes testes são os observados na API em 16/09/2026: as competências
1 a 7 de 2026 devolviam página cheia, a 8 devolvia 17 linhas e as seguintes,
nenhuma.
"""

import unittest
from datetime import date

from cadprev import competencia


class ClienteFalso:
    """Devolve volumes de um mapa, contando as requisições feitas."""

    def __init__(self, mapa):
        self.mapa, self.pedidos = mapa, []

    def pagina(self, nome, offset=0, **filtros):
        self.pedidos.append((filtros.get("dt_ano"), filtros.get("dt_mes_bimestre"),
                             filtros.get("sg_uf")))
        n = self.mapa.get((filtros["dt_ano"], filtros["dt_mes_bimestre"]), 0)
        return {"data": [{"x": i} for i in range(n)]}


#: O que a API devolvia no dia em que este módulo foi escrito.
REAL = {(2026, m): 5000 for m in range(1, 8)}
REAL[(2026, 8)] = 17


class TestMaisRecenteFechada(unittest.TestCase):

    def test_ignora_competencia_em_preenchimento(self):
        """A competência 8 existe e tem 17 linhas no país: publicá-la mostraria
        um patrimônio nacional de quase zero."""
        c = ClienteFalso(REAL)
        self.assertEqual(
            competencia.mais_recente_fechada(c, date(2026, 9, 16)), (2026, 7))

    def test_a_virada_do_ano_nao_pede_competencia_inexistente(self):
        """O defeito que motivou o módulo: em janeiro, a aritmética de calendário
        pedia o mês de outubro do ano corrente."""
        c = ClienteFalso(REAL)
        self.assertEqual(
            competencia.mais_recente_fechada(c, date(2027, 1, 12)), (2026, 7))
        anos = {ano for ano, _, _ in c.pedidos}
        self.assertIn(2026, anos)

    def test_funciona_com_volumes_de_uma_uf(self):
        """Com filtro de UF os volumes caem duas ordens de grandeza, e um piso
        absoluto classificaria todo mês como vazio."""
        mapa = {(2026, m): 310 for m in range(1, 7)}
        mapa[(2026, 7)] = 300
        mapa[(2026, 8)] = 2
        c = ClienteFalso(mapa)
        self.assertEqual(
            competencia.mais_recente_fechada(c, date(2026, 9, 16), uf="ES"),
            (2026, 7))
        self.assertTrue(all(p[2] == "ES" for p in c.pedidos))

    def test_base_vazia_devolve_nada_em_vez_de_chutar(self):
        c = ClienteFalso({})
        self.assertIsNone(competencia.mais_recente_fechada(c, date(2026, 9, 16)))

    def test_caminha_para_tras_e_para(self):
        c = ClienteFalso(REAL)
        competencia.mais_recente_fechada(c, date(2026, 9, 16), meses=5)
        self.assertEqual(len(c.pedidos), 5)
        self.assertEqual(c.pedidos[0][:2], (2026, 9))
        self.assertEqual(c.pedidos[-1][:2], (2026, 5))

    def test_volumes_vem_do_mais_recente_para_o_mais_antigo(self):
        c = ClienteFalso(REAL)
        vistos = competencia.volumes(c, date(2026, 2, 3), meses=3)
        self.assertEqual([(a, m) for a, m, _ in vistos],
                         [(2026, 2), (2026, 1), (2025, 12)])


if __name__ == "__main__":
    unittest.main()
