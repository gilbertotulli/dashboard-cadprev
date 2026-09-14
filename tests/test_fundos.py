"""Separação por natureza do fundo — Níveis A e B."""

import unittest

from cadprev import fundos


class TestClassificacao(unittest.TestCase):

    def test_rotulos_da_fonte(self):
        self.assertEqual(fundos.classificar_plano("PREVIDENCIÁRIO"), fundos.CAPITALIZADO)
        self.assertEqual(fundos.classificar_plano("Plano Financeiro"), fundos.REPARTICAO)
        self.assertEqual(fundos.classificar_plano("Taxa de Administração"),
                         fundos.TAXA_ADMINISTRACAO)

    def test_rotulo_desconhecido_nao_vira_capitalizado(self):
        """Somar o que não se reconhece ao maior balde é como erros somem."""
        self.assertIsNone(fundos.classificar_plano("Fundo XYZ"))
        self.assertIsNone(fundos.classificar_plano(None))

    def test_nivel_depende_do_campo_de_plano(self):
        self.assertEqual(fundos.detectar_nivel(["valor_total", "plano"]), fundos.NIVEL_A)
        self.assertEqual(fundos.detectar_nivel(["valor_total"]), fundos.NIVEL_B)

    def test_nivel_b_classifica_o_rpps(self):
        self.assertEqual(fundos.classificar_rpps(False), fundos.CAPITALIZADO)
        self.assertEqual(fundos.classificar_rpps(True), fundos.NAO_DECOMPOSTO)
        self.assertEqual(fundos.classificar_rpps(None), fundos.NAO_DECOMPOSTO)


class TestAgregacao(unittest.TestCase):

    LINHAS = [
        {"cnpj_ente": "A", "valor_total": 100.0, "plano": "PREVIDENCIÁRIO"},
        {"cnpj_ente": "A", "valor_total": 40.0, "plano": "FINANCEIRO"},
        {"cnpj_ente": "B", "valor_total": 60.0, "plano": "TAXA DE ADMINISTRAÇÃO"},
    ]

    def test_nivel_a_decompoe_em_tres_vias(self):
        total = fundos.agregar(self.LINHAS, fundos.NIVEL_A)
        self.assertEqual(total[fundos.CAPITALIZADO], 100.0)
        self.assertEqual(total[fundos.REPARTICAO], 40.0)
        self.assertEqual(total[fundos.TAXA_ADMINISTRACAO], 60.0)

    def test_nivel_b_usa_a_segregacao_do_rpps(self):
        """Sem o plano do ativo, não se rateia: o RPPS segregado fica inteiro
        em 'não decomposto'."""
        total = fundos.agregar(self.LINHAS, fundos.NIVEL_B,
                               {"A": True, "B": False})
        self.assertEqual(total[fundos.NAO_DECOMPOSTO], 140.0)
        self.assertEqual(total[fundos.CAPITALIZADO], 60.0)
        self.assertNotIn(fundos.REPARTICAO, total)

    def test_nivel_b_sem_informacao_de_segregacao(self):
        total = fundos.agregar(self.LINHAS, fundos.NIVEL_B, {})
        self.assertEqual(total[fundos.NAO_DECOMPOSTO], 200.0)

    def test_soma_preservada_em_qualquer_nivel(self):
        for nivel in (fundos.NIVEL_A, fundos.NIVEL_B):
            total = fundos.agregar(self.LINHAS, nivel, {"A": True, "B": False})
            self.assertAlmostEqual(sum(total.values()), 200.0)


if __name__ == "__main__":
    unittest.main()
