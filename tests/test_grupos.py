"""Classificação dos RPPS em grupos."""

import unittest

from cadprev import grupos


class TestEsfera(unittest.TestCase):

    def test_governo_do_estado(self):
        self.assertEqual(grupos.esfera("AC", "Governo do Estado do Acre"), "estadual")
        self.assertEqual(grupos.esfera("DF", "Governo do Distrito Federal"), "estadual")

    def test_nome_cru_do_estado(self):
        self.assertEqual(grupos.esfera("ES", "Espírito Santo"), "estadual")

    def test_capital_com_nome_igual_ao_do_estado(self):
        """Regressão: São Paulo e Rio de Janeiro são os dois maiores RPPS
        municipais do país e caíam como estaduais pela coincidência de nome."""
        self.assertEqual(grupos.esfera("SP", "São Paulo"), "capital")
        self.assertEqual(grupos.esfera("RJ", "Rio de Janeiro"), "capital")
        self.assertEqual(grupos.esfera("SP", "Governo do Estado de São Paulo"), "estadual")

    def test_municipio_com_governo_no_nome(self):
        self.assertEqual(grupos.esfera("MG", "Governo do Município de Contagem"),
                         "municipal")

    def test_capital_e_demais(self):
        self.assertEqual(grupos.esfera("ES", "Vitória"), "capital")
        self.assertEqual(grupos.esfera("ES", "Vila Velha"), "municipal")

    def test_acento_e_caixa_nao_importam(self):
        self.assertEqual(grupos.esfera("ES", "VITORIA"), "capital")
        self.assertEqual(grupos.esfera("MA", "sao luis"), "capital")


class TestRegiao(unittest.TestCase):

    def test_todas_as_ufs_tem_regiao(self):
        self.assertEqual(len(grupos.REGIOES), 27)
        for uf in grupos.NOMES_UF:
            self.assertIsNotNone(grupos.regiao(uf), uf)

    def test_uf_desconhecida(self):
        self.assertIsNone(grupos.regiao("ZZ"))
        self.assertIsNone(grupos.regiao(None))


class TestTabelaAuxiliar(unittest.TestCase):

    def test_capitais_carregadas(self):
        """A marcação de capitais não vem da API: depende deste arquivo."""
        self.assertEqual(grupos.cobertura_capitais(), 27)


if __name__ == "__main__":
    unittest.main()


class TestEsferaDeclarada(unittest.TestCase):
    """Quando o SICONFI declara a esfera, nada é deduzido do nome."""

    def test_municipio_com_nome_de_outro_estado(self):
        """Há sete municípios batizados com nome de unidade federativa.

        Aceitar qualquer nome de estado promovia todos a governo estadual.
        """
        self.assertEqual(grupos.esfera("MG", "Tocantins"), "municipal")
        self.assertEqual(grupos.esfera("RN", "Espírito Santo"), "municipal")
        self.assertEqual(grupos.esfera("PB", "Mato Grosso"), "municipal")
        self.assertEqual(grupos.esfera("TO", "Paranã"), "municipal")

    def test_o_proprio_estado_continua_estadual(self):
        self.assertEqual(grupos.esfera("ES", "Espírito Santo"), "estadual")
        self.assertEqual(grupos.esfera("AC", "Governo do Estado do Acre"),
                         "estadual")

    def test_declaracao_do_siconfi_vence_a_deducao(self):
        """O município de Amapá, no Amapá, é municipal — a fonte afirma."""
        self.assertEqual(
            grupos.esfera("AP", "Amapá", capital=False, esfera_fonte="M"),
            "municipal")
        self.assertEqual(
            grupos.esfera("GO", "Goiás", capital=False, esfera_fonte="M"),
            "municipal")

    def test_capital_declarada(self):
        self.assertEqual(
            grupos.esfera("SP", "São Paulo", capital=True, esfera_fonte="M"),
            "capital")
        self.assertEqual(
            grupos.esfera("SP", "Santos", capital=False, esfera_fonte="M"),
            "municipal")

    def test_distrito_federal_e_estadual(self):
        self.assertEqual(
            grupos.esfera("DF", "Governo do Distrito Federal",
                          capital=True, esfera_fonte="D"), "estadual")
