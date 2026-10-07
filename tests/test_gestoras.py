"""A unidade gestora, e o corte por natureza jurídica."""

import unittest

from cadprev import build, gestoras


class TestGestoras(unittest.TestCase):
    """O cadastro da SPREV, que não vem da API."""

    def test_cnpj_da_ug_difere_do_cnpj_do_ente(self):
        """É a razão de a tabela existir.

        O CADPREV identifica tudo pelo CNPJ do ente federativo; quem administra
        os recursos quase sempre é pessoa jurídica própria, e é o CNPJ dela que
        aparece como cotista no extrato do administrador do fundo.
        """
        diferentes = sum(1 for cnpj, ug in gestoras.POR_ENTE.items()
                         if ug["cnpj"] != cnpj)
        self.assertGreater(diferentes, len(gestoras.POR_ENTE) // 2)

    def test_so_o_cnpj_vigente_entra(self):
        """O cadastro guarda o histórico: uma UG que mudou de CNPJ aparece duas
        vezes. Com as inativas, um ente teria duas gestoras e a consulta teria
        de escolher — entre as vigentes não há ambiguidade."""
        # Uma entrada por ente, e nenhuma com CNPJ vazio.
        self.assertTrue(gestoras.POR_ENTE)
        for cnpj, ug in gestoras.POR_ENTE.items():
            self.assertEqual(len(cnpj), 14)
            self.assertEqual(len(ug["cnpj"]), 14)
            self.assertTrue(ug["nome"])

    def test_ente_fora_do_cadastro_devolve_nada(self):
        """Ausência, não uma UG inativa qualquer."""
        self.assertIsNone(gestoras.da("00000000000000"))
        self.assertIsNone(gestoras.da(None))
        self.assertIsNone(gestoras.da(""))

    def test_cnpj_normaliza_pontuacao(self):
        """O cadastro vem com e sem pontuação, e um CNPJ curto é zero à
        esquerda — "3848000174" é o mesmo ente que "00003848000174"."""
        qualquer = sorted(gestoras.POR_ENTE)[0]
        sem_zeros = qualquer.lstrip("0")
        self.assertEqual(gestoras.da(qualquer), gestoras.da(sem_zeros))
        pontuado = "{}.{}.{}/{}-{}".format(
            qualquer[:2], qualquer[2:5], qualquer[5:8], qualquer[8:12], qualquer[12:])
        self.assertEqual(gestoras.da(qualquer), gestoras.da(pontuado))


class TestCarteiraPorNatureza(unittest.TestCase):
    """O corte de governança sobre a carteira."""

    ENTES = {
        "1": {"ug_natureza": "Autarquia"}, "2": {"ug_natureza": "Autarquia"},
        "3": {"ug_natureza": "Autarquia"}, "4": {"ug_natureza": "Adm Direta"},
        "5": {"ug_natureza": "Adm Direta"}, "6": {},
    }

    def _cortar(self, por_ente, fora=frozenset()):
        return {d["rotulo"]: d
                for d in build._carteira_por_natureza(por_ente, self.ENTES, fora)}

    def test_mediana_lidera_e_a_cauda_nao_a_move(self):
        """Vários RPPS estaduais grandes são autarquias, e a média da autarquia
        descreveria eles em vez do RPPS típico."""
        corte = self._cortar({"1": 10.0, "2": 20.0, "3": 10000.0,
                              "4": 50.0, "5": 70.0, "6": 5.0})
        autarquia = corte["Autarquia"]
        self.assertEqual(autarquia["rpps"], 3)
        self.assertEqual(autarquia["mediana"], 20.0)
        self.assertGreater(autarquia["media"], autarquia["mediana"])
        # O total responde a outra pergunta, e também está publicado.
        self.assertEqual(autarquia["total"], 10030.0)

    def test_grupo_pequeno_nao_ganha_mediana(self):
        """Com dois RPPS, "mediana" é a média deles."""
        corte = self._cortar({"1": 10.0, "2": 20.0, "3": 30.0,
                              "4": 50.0, "5": 70.0})
        self.assertTrue(corte["Autarquia"]["disponivel"])
        self.assertFalse(corte["Adm Direta"]["disponivel"])
        # Mas o total e a contagem continuam valendo: eles não são estatística.
        self.assertEqual(corte["Adm Direta"]["rpps"], 2)
        self.assertEqual(corte["Adm Direta"]["total"], 120.0)

    def test_ente_fora_do_cadastro_vira_grupo_proprio(self):
        """E não desaparece nem entra em "autarquia" por omissão: o painel não
        sabe a natureza dele, e dizer que sabe seria pior."""
        corte = self._cortar({"1": 10.0, "6": 5.0})
        self.assertIn("Não consta no cadastro", corte)
        self.assertEqual(corte["Não consta no cadastro"]["total"], 5.0)

    def test_ente_excluido_pelo_recorte_fica_fora(self):
        corte = self._cortar({"1": 10.0, "2": 20.0, "4": 50.0},
                             fora=frozenset({"2"}))
        self.assertEqual(corte["Autarquia"]["rpps"], 1)
        self.assertEqual(corte["Autarquia"]["total"], 10.0)


if __name__ == "__main__":
    unittest.main()
