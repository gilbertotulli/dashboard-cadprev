"""Regras de qualidade do cadastro.

Os números destes testes vêm da carga nacional de 15/09/2026, não de exemplos
inventados: a linha de Santo Afonso/MT é o caso real que motivou o módulo.
"""

import unittest

from cadprev import qualidade


def _linha(fundo, posicao, pl, **extra):
    base = {"identificacao_ativo": fundo, "valor_total": posicao,
            "pl_fundo": pl, "cnpj_ente": "00000000000191",
            "nome_ativo": "FUNDO X"}
    base.update(extra)
    return base


class TestTetoPorFundo(unittest.TestCase):

    def test_usa_a_maior_declaracao(self):
        linhas = [_linha("F", 1, 200.0e6), _linha("F", 1, 100.0e6),
                  _linha("F", 1, 150.0e6)]
        self.assertEqual(qualidade.teto_por_fundo(linhas), {"F": 200.0e6})

    def test_fundo_com_poucos_declarantes_nao_tem_teto(self):
        linhas = [_linha("F", 1, 200.0e6), _linha("F", 1, 100.0e6)]
        self.assertEqual(qualidade.teto_por_fundo(linhas), {})

    def test_pl_simbolico_nao_serve_de_referencia(self):
        """O 0,01 aparece às dezenas na base e marcaria posições legítimas."""
        linhas = [_linha("F", 5.0e6, 0.01) for _ in range(5)]
        self.assertEqual(qualidade.teto_por_fundo(linhas), {})
        marcas, achados = qualidade.achados_da_carteira(linhas)
        self.assertEqual(marcas, {})
        self.assertEqual(achados, [])


class TestPosicaoImpossivel(unittest.TestCase):

    def test_o_caso_de_santo_afonso(self):
        """Cota declarada a R$ 36.640.481,00 quando vale R$ 36,640481."""
        outros = [_linha("SICREDI", 3.0e6, 196261988.60) for _ in range(3)]
        ruim = _linha("SICREDI", 3161813338273.49, 196261988.60,
                      valor_unitario=36640481.0, quantidade_cotas=86292.8993283)
        marcas, achados = qualidade.achados_da_carteira(outros + [ruim])
        self.assertEqual(list(marcas), [3])
        self.assertEqual(achados[0]["marca"], qualidade.MARCA_POSICAO)
        self.assertGreater(achados[0]["vezes"], 1000)

    def test_posicao_igual_ao_fundo_e_legitima(self):
        """Fundo exclusivo: o RPPS é dono do fundo inteiro."""
        linhas = [_linha("F", 100.0e6, 100.0e6) for _ in range(3)]
        marcas, _ = qualidade.achados_da_carteira(linhas)
        self.assertEqual(marcas, {})

    def test_margem_de_uma_ordem_de_grandeza(self):
        base = [_linha("F", 1.0, 100.0e6) for _ in range(3)]
        dentro = _linha("F", 9.0 * 100.0e6, 100.0e6)
        fora = _linha("F", 11.0 * 100.0e6, 100.0e6)
        marcas, _ = qualidade.achados_da_carteira(base + [dentro])
        self.assertEqual(marcas, {})
        marcas, _ = qualidade.achados_da_carteira(base + [fora])
        self.assertEqual(list(marcas), [3])

    def test_o_resultado_nao_depende_da_margem_escolhida(self):
        """A distância entre erro de vírgula e realidade é grande demais.

        Se trocar a margem por qualquer valor entre 2 e 1.000 mudasse o
        conjunto marcado, a régua estaria decidindo — e não a evidência.
        """
        base = [_linha("F", 5.0e6, 200.0e6) for _ in range(4)]
        erro = _linha("F", 3.16e12, 200.0e6)
        original = qualidade.MARGEM
        try:
            marcados = []
            for margem in (2.0, 10.0, 100.0, 1000.0):
                qualidade.MARGEM = margem
                marcas, _ = qualidade.achados_da_carteira(base + [erro])
                marcados.append(sorted(marcas))
            self.assertEqual(marcados, [[4]] * 4)
        finally:
            qualidade.MARGEM = original

    def test_nao_corrige_o_valor(self):
        """Dividir por um milhão daria o número certo — e seria inventá-lo."""
        base = [_linha("F", 1.0, 200.0e6) for _ in range(3)]
        erro = _linha("F", 3.16e12, 200.0e6)
        _, achados = qualidade.achados_da_carteira(base + [erro])
        self.assertEqual(achados[0]["posicao"], 3.16e12)
        self.assertNotIn("posicao_corrigida", achados[0])


class TestMesesEntre(unittest.TestCase):

    def test_meses_cheios(self):
        self.assertEqual(qualidade.meses_entre("2026-06-30", "2026-09-16"), 2)
        self.assertEqual(qualidade.meses_entre("2026-03-31", "2026-09-16"), 5)

    def test_mesmo_dia_conta_o_mes(self):
        self.assertEqual(qualidade.meses_entre("2026-06-16", "2026-09-16"), 3)

    def test_vespera_nao_conta(self):
        self.assertEqual(qualidade.meses_entre("2026-06-17", "2026-09-16"), 2)

    def test_sem_data(self):
        self.assertIsNone(qualidade.meses_entre(None, "2026-09-16"))
        self.assertIsNone(qualidade.meses_entre("sem data", "2026-09-16"))

    def test_data_futura_nao_fica_negativa(self):
        self.assertEqual(qualidade.meses_entre("2026-12-01", "2026-09-16"), 0)


if __name__ == "__main__":
    unittest.main()
