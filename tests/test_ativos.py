"""O nome do ativo, e o vencimento que só existe quando a fonte o escreveu."""

import unittest
from datetime import date

from cadprev import ativos


class TestNome(unittest.TestCase):
    """Qual dos dois campos é o nome — decidido pelo conteúdo, não pela classe."""

    def test_fundo_usa_o_nome_do_fundo(self):
        escolha = ativos.nome("CAIXA HEDGE FIC MULTIMERCADO LP", "30068135000150")
        self.assertEqual(escolha["rotulo"], "CAIXA HEDGE FIC MULTIMERCADO LP")
        self.assertEqual(escolha["campo"], "nome_ativo")

    def test_titulo_publico_usa_a_identificacao(self):
        """Nos títulos os dois campos trocam de papel.

        ``nome_ativo`` traz um número de contrato e ``identificacao_ativo`` traz
        a descrição. Em 22/09/2026 isso valia para 6.844 das 7.091 posições de
        título público do país — 97% —, e era por isso que a coluna "Ativo"
        mostrava um número.
        """
        escolha = ativos.nome("27626457", "Tesouro IPCA+ com Juros Semestrais (NTNB)")
        self.assertEqual(escolha["rotulo"], "Tesouro IPCA+ com Juros Semestrais (NTNB)")
        self.assertEqual(escolha["campo"], "identificacao_ativo")

    def test_numero_com_barra_ainda_e_numero(self):
        """"20500815/3" é contrato, não nome. Exigir só dígitos deixaria passar."""
        self.assertFalse(ativos.tem_letra("20500815/3"))
        self.assertEqual(ativos.nome("20500815/3", "NTNB 15082040")["campo"],
                         "identificacao_ativo")

    def test_sem_nenhum_dos_dois_sobra_a_classe(self):
        """Melhor a classe do ativo que um número solto na coluna do nome."""
        escolha = ativos.nome("123456", "789", "Títulos Públicos – Oferta Balcão")
        self.assertEqual(escolha["rotulo"], "Títulos Públicos – Oferta Balcão")
        self.assertEqual(escolha["campo"], "tipo_ativo")


class TestVencimento(unittest.TestCase):

    def test_data_de_compra_nao_e_vencimento(self):
        """A descrição traz as duas datas, e a palavra "compra" diz qual é qual.

        Ler pela ordem funciona em ``NTNB 15082040 (Compra em 06122024)`` e
        falha no inverso — e o inverso existe na base.
        """
        self.assertEqual(ativos.vencimento("NTNB 15082040 (Compra em 06122024 Tx 6)"),
                         date(2040, 8, 15))
        self.assertEqual(ativos.vencimento("NTNB (Compra em 06122024) 15082040"),
                         date(2040, 8, 15))

    def test_entre_duas_datas_soltas_vale_a_mais_distante(self):
        """Um título vence depois de ter sido comprado, sempre.

        ``NTNB_07032006_15052035`` não diz qual é qual, e a ordem não ajuda.
        O que decide é a aritmética do instrumento.
        """
        self.assertEqual(ativos.vencimento("NTNB_07032006_15052035"),
                         date(2035, 5, 15))
        self.assertEqual(
            ativos.vencimento("NTNB 760199 (30082012) 15082030 (23072025)"),
            date(2030, 8, 15))

    def test_sem_data_nao_inventa(self):
        """80% das descrições são o nome comercial do Tesouro Direto, sem data.

        Derivar um vencimento aí seria afirmar o que a fonte não disse.
        """
        self.assertIsNone(ativos.vencimento("Tesouro IPCA+ com Juros Semestrais (NTNB)"))
        self.assertIsNone(ativos.vencimento("Tesouro Prefixado (LTN)"))

    def test_data_impossivel_nao_passa(self):
        self.assertIsNone(ativos.vencimento("NTNB 32132040"))


class TestTitulo(unittest.TestCase):

    def test_sigla_normalizada(self):
        self.assertEqual(ativos.titulo("Tesouro IPCA+ (NTNB Princ)")["sigla"], "NTN-B")
        self.assertEqual(ativos.titulo("LFT 01092026")["sigla"], "LFT")

    def test_ntnb_nao_vira_ntn(self):
        """A ordem das siglas importa: "NTN" casa dentro de "NTNB"."""
        self.assertEqual(ativos.sigla("NTNB 15082040"), "NTN-B")
        self.assertEqual(ativos.sigla("NTNF 01012031"), "NTN-F")

    def test_rotulo_traz_o_vencimento_quando_existe(self):
        self.assertEqual(ativos.titulo("NTNB 15082040 (Compra em 06122024)")["rotulo"],
                         "NTN-B 15/08/2040")
        self.assertEqual(ativos.titulo("Tesouro IPCA+ (NTNB)")["rotulo"], "NTN-B")

    def test_sem_sigla_nao_ha_titulo(self):
        """Uma data solta num nome de fundo não faz dele um título público."""
        self.assertIsNone(ativos.titulo("FUNDO CAIXA BRASIL 2028 X TITULOS"))
        self.assertIsNone(ativos.titulo("CAIXA BRASIL IMA-B"))


if __name__ == "__main__":
    unittest.main()
