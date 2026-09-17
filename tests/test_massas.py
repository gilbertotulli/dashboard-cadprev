"""A leitura das massas civil e militar, que a fonte declara em campos diferentes."""

import unittest

from cadprev import massas


class TestMassas(unittest.TestCase):

    def test_o_papel_esta_em_campos_diferentes_em_cada_massa(self):
        """A assimetria da fonte é o motivo deste módulo existir.

        No civil o papel está em ``tp_populacao``. No militar esse campo diz
        sempre "Militares" e o papel está em ``no_cat_populacao``. Ler os dois
        pelo mesmo campo perde a massa militar inteira.
        """
        self.assertEqual(
            massas.papel("Civil", "Aposentados", "DEMAIS SERVIDORES"),
            massas.INATIVO)
        self.assertEqual(
            massas.papel("Militar", "Militares", "MILITARES - APOSENTADOS"),
            massas.INATIVO)
        # O mesmo tp_populacao, três papéis diferentes — só a categoria separa.
        papeis = {massas.papel("Militar", "Militares", c) for c in (
            "MILITARES - ATIVOS", "MILITARES - APOSENTADOS",
            "MILITARES - PENSIONISTAS")}
        self.assertEqual(papeis, {massas.ATIVO, massas.INATIVO,
                                  massas.PENSIONISTA})

    def test_iminentes_ficam_fora_de_ativos_e_de_inativos(self):
        """Já cumpriram os requisitos e ainda não requereram o benefício.

        Contá-los como ativos infla a razão; como inativos, deprime. A fonte os
        declara à parte e o painel os mantém à parte.
        """
        self.assertEqual(
            massas.papel("Civil", "Servidores Iminentes", "DEMAIS SERVIDORES"),
            massas.OUTRO)

    def test_reserva_e_reforma_no_lugar_de_aposentadoria(self):
        """Militar não se aposenta, e a troca de termo fica rastreável."""
        rotulo, fonte = massas.rotulo("Militar", "Militares",
                                      "MILITARES - APOSENTADOS")
        self.assertEqual(rotulo, "Reserva e reforma")
        self.assertEqual(fonte, "MILITARES - APOSENTADOS")

    def test_so_registra_a_fonte_quando_houve_troca(self):
        """Repetir o termo idêntico ao lado dele não informa nada."""
        _, fonte = massas.rotulo("Militar", "Militares", "MILITARES - ATIVOS")
        self.assertIsNone(fonte)
        _, fonte = massas.rotulo("Civil", "Servidores", "DEMAIS SERVIDORES")
        self.assertIsNone(fonte)

    def test_categoria_militar_desconhecida_aparece_como_a_fonte_escreveu(self):
        """Se o CADPREV criar um grupo novo, ele aparece — não some."""
        rotulo, fonte = massas.rotulo("Militar", "Militares",
                                      "MILITARES - DEPENDENTES")
        self.assertEqual(rotulo, "MILITARES - DEPENDENTES")
        self.assertIsNone(fonte)
        self.assertEqual(
            massas.papel("Militar", "Militares", "MILITARES - DEPENDENTES"),
            massas.OUTRO)

    def test_normalizar_nao_depende_de_caixa_nem_de_espaco(self):
        for bruto in ("Militar", " militar ", "MILITARES", "Militares"):
            self.assertTrue(massas.eh_militar(bruto), bruto)
        for bruto in ("Civil", "civil ", "CIVIS"):
            self.assertFalse(massas.eh_militar(bruto), bruto)
        self.assertIsNone(massas.normalizar(None))
        self.assertFalse(massas.eh_militar(None))

    def test_massa_desconhecida_nao_vira_civil_por_omissao(self):
        """Inventar a massa é pior que dizer que não se sabe qual é."""
        self.assertEqual(massas.normalizar("Previdenciário"), "Previdenciário")


if __name__ == "__main__":
    unittest.main()
