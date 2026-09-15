"""Indicadores comparativos e estatísticas de grupo."""

import unittest

from cadprev import benchmark


class TestPorte(unittest.TestCase):

    def test_faixas(self):
        self.assertEqual(benchmark.porte(1), "pequeno")
        self.assertEqual(benchmark.porte(999), "pequeno")
        self.assertEqual(benchmark.porte(1000), "medio")
        self.assertEqual(benchmark.porte(9999), "medio")
        self.assertEqual(benchmark.porte(10000), "grande")

    def test_sem_segurados(self):
        self.assertIsNone(benchmark.porte(None))
        self.assertIsNone(benchmark.porte(0))


class TestEstatisticas(unittest.TestCase):

    def test_percentil_interpola(self):
        valores = [1, 2, 3, 4, 5]
        self.assertEqual(benchmark._percentil(valores, 0.50), 3)
        self.assertEqual(benchmark._percentil(valores, 0.25), 2)
        self.assertEqual(benchmark._percentil(valores, 0.75), 4)

    def test_grupo_pequeno_demais_nao_gera_estatistica(self):
        """Quartis sobre dois pontos são aritmética, não informação."""
        self.assertIsNone(benchmark.resumir([1, 2]))
        self.assertIsNotNone(benchmark.resumir([1, 2, 3]))

    def test_nulos_ficam_de_fora(self):
        resumo = benchmark.resumir([1.0, None, 3.0, None, 5.0])
        self.assertEqual(resumo["n"], 3)
        self.assertEqual(resumo["mediana"], 3.0)

    def test_mediana_resiste_a_valor_extremo(self):
        """O motivo de não usar média: um estadual distorceria o grupo."""
        tipicos = [10.0, 11.0, 12.0, 13.0, 14.0]
        com_gigante = tipicos + [9000.0]
        self.assertEqual(benchmark.resumir(tipicos)["mediana"], 12.0)
        self.assertEqual(benchmark.resumir(com_gigante)["mediana"], 12.5)

    def test_posicao_no_grupo(self):
        self.assertEqual(benchmark.posicao(4, [1, 2, 3, 4, 5]), 60)
        self.assertEqual(benchmark.posicao(1, [1, 2, 3, 4, 5]), 0)
        self.assertIsNone(benchmark.posicao(None, [1, 2, 3]))


class TestIndicadores(unittest.TestCase):

    FICHA = {
        "ente": "Exemplo", "uf": "ES", "regiao": "Sudeste", "esfera": "capital",
        "estatistica": {"disponivel": True, "ativos": 1000, "inativos": 500,
                        "razao_ativos_inativos": 2.0},
        "carteira": {"disponivel": True, "total": 100_000_000.0, "segmentos": [
            {"rotulo": "Renda Fixa", "perc": 80.0, "alocacao": True},
            {"rotulo": "Renda Variável", "perc": 20.0, "alocacao": True}]},
        "caixa": {"disponivel": True, "total_receita": 50_000_000.0,
                  "total_despesa": 30_000_000.0, "meses_declarados": 12},
        "atuaria": {"disponivel": True, "resultado": {
            "provisoes": 400_000_000.0, "ativos_garantidores": 100_000_000.0}},
        "aliquotas": [{"sujeito_passivo": "Ente", "aliquota": 22.0,
                       "vigente": "VIGENTE"},
                      {"sujeito_passivo": "Ente-suplementar", "aliquota": 9.0,
                       "vigente": "VIGENTE"}],
    }

    def test_calculos(self):
        v = benchmark.calcular(self.FICHA)
        self.assertEqual(v["razao_ativos_inativos"], 2.0)
        self.assertEqual(v["patrimonio_por_beneficiario"], 200_000.0)
        self.assertEqual(v["cobertura_atuarial"], 25.0)
        self.assertEqual(v["resultado_sobre_ingressos"], 40.0)
        self.assertEqual(v["perc_renda_fixa"], 80.0)

    def test_despesa_usa_meses_declarados(self):
        """Quem informou metade do ano não tem despesa mensal pela metade."""
        v = benchmark.calcular(self.FICHA)
        self.assertEqual(v["despesa_por_inativo"], 5000.0)
        parcial = dict(self.FICHA, caixa=dict(self.FICHA["caixa"],
                                              meses_declarados=6))
        self.assertEqual(benchmark.calcular(parcial)["despesa_por_inativo"],
                         10000.0)

    def test_aliquota_suplementar_nao_entra(self):
        """É amortização de déficit, não custeio normal."""
        self.assertEqual(benchmark.calcular(self.FICHA)["aliquota_ente"], 22.0)

    def test_dado_ausente_vira_nulo_e_nao_zero(self):
        vazia = {"ente": "Sem dados"}
        v = benchmark.calcular(vazia)
        self.assertTrue(all(x is None for x in v.values()), v)

    def test_alocacao_em_percentual(self):
        perfil = benchmark.alocacao(self.FICHA)
        self.assertEqual(perfil["Renda Fixa"], 80.0)
        self.assertEqual(perfil["Renda Variável"], 20.0)
        self.assertEqual(benchmark.alocacao({"ente": "x"}), {})


class TestMontar(unittest.TestCase):

    def _fichas(self, n=6):
        fichas = {}
        for i in range(n):
            f = dict(TestIndicadores.FICHA)
            f["ente"] = "Ente {}".format(i)
            f["estatistica"] = {"disponivel": True, "ativos": 100 * (i + 1),
                                "inativos": 50, "razao_ativos_inativos": i + 1.0}
            fichas["{:014d}".format(i)] = f
        return fichas

    def test_grupos_e_segmentos(self):
        b = benchmark.montar(self._fichas())
        self.assertEqual(b["grupos"]["brasil"]["rpps"], 6)
        self.assertIn("Sudeste", b["grupos"]["regiao"])
        self.assertEqual(b["segmentos"], ["Renda Fixa", "Renda Variável"])
        self.assertIn("Renda Fixa", b["grupos"]["brasil"]["alocacao"])

    def test_todo_rpps_tem_entrada(self):
        b = benchmark.montar(self._fichas())
        self.assertEqual(len(b["rpps"]), 6)
        for dados in b["rpps"].values():
            self.assertIn("valores", dados)
            self.assertIn("alocacao", dados)
            self.assertIn("porte", dados)

    def test_indicadores_carregam_direcao_e_fonte(self):
        b = benchmark.montar(self._fichas())
        for ind in b["indicadores"]:
            self.assertIn(ind["unidade"], ("percentual", "reais", "razao"))
            self.assertIn(ind["direcao"], ("maior", "menor", None))
            self.assertTrue(ind["fonte"])


if __name__ == "__main__":
    unittest.main()
