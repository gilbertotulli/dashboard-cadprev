"""A mediana lidera, e ausência não é zero."""

import unittest

from cadprev import distribuicao


class TestResumir(unittest.TestCase):

    def test_a_cauda_move_a_media_e_nao_a_mediana(self):
        """O motivo de a mediana liderar todo quadro consolidado.

        Uns poucos RPPS estaduais reúnem a maior parte do patrimônio. Numa
        média eles respondem pelo país; numa mediana, por um RPPS cada.
        """
        sem = distribuicao.resumir([10, 20, 30, 40, 50])
        com = distribuicao.resumir([10, 20, 30, 40, 100000])
        self.assertEqual(sem["mediana"], com["mediana"])
        self.assertGreater(com["media"], sem["media"] * 100)

    def test_ausencia_fica_de_fora_da_conta(self):
        """Indicador indefinido não é indicador zero.

        Somar ``None`` como zero puxaria a mediana de todo mundo em favor de
        quem não declarou — e mudaria o retrato do país conforme a cobertura
        da ingestão, não conforme os RPPS.
        """
        self.assertEqual(distribuicao.resumir([10, None, 20, None, 30])["n"], 3)
        self.assertEqual(distribuicao.resumir([10, None, 20, None, 30])["mediana"],
                         distribuicao.resumir([10, 20, 30])["mediana"])

    def test_grupo_pequeno_nao_produz_estatistica(self):
        """Com dois RPPS, "mediana" é a média deles e "quartil" não quer dizer
        nada. O resumo diz quantos são e para por aí — que é diferente de
        dizer zero."""
        r = distribuicao.resumir([5, 7])
        self.assertFalse(r["disponivel"])
        self.assertEqual(r["n"], 2)
        self.assertNotIn("mediana", r)

    def test_quartis_delimitam_a_metade_do_meio(self):
        r = distribuicao.resumir([1, 2, 3, 4, 5, 6, 7, 8, 9])
        self.assertEqual(r["mediana"], 5.0)
        self.assertEqual(r["p25"], 3.0)
        self.assertEqual(r["p75"], 7.0)
        self.assertEqual(r["minimo_obs"], 1.0)
        self.assertEqual(r["maximo_obs"], 9.0)

    def test_desvio_e_amostral(self):
        """O conjunto é o dos RPPS que declararam, não a população dos que
        existem: o denominador é n−1."""
        r = distribuicao.resumir([2, 4, 6])
        self.assertEqual(r["media"], 4.0)
        self.assertEqual(r["desvio"], 2.0)   # populacional daria 1,63

    def test_concentracao_e_a_distancia_entre_media_e_mediana(self):
        r = distribuicao.resumir([1, 1, 1, 1, 96])
        self.assertEqual(r["mediana"], 1.0)
        self.assertEqual(distribuicao.concentracao(r), 20.0)
        self.assertIsNone(distribuicao.concentracao({"disponivel": False}))


if __name__ == "__main__":
    unittest.main()
