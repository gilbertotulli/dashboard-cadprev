"""Descoberta da competência do DAIR.

Os volumes destes testes são os declarantes observados na API em 17/09/2026.
"""

import unittest
from datetime import date

from cadprev import competencia


class ClienteFalso:
    """Devolve volumes de um mapa, contando as requisições feitas."""

    def __init__(self, mapa):
        self.mapa, self.pedidos = mapa, []

    def pagina(self, nome, offset=0, **filtros):
        self.pedidos.append((filtros.get("dt_ano"), filtros.get("dt_mes"),
                             filtros.get("sg_uf"), nome))
        n = self.mapa.get((filtros["dt_ano"], filtros["dt_mes"]), 0)
        return {"data": [{"x": i} for i in range(n)]}


#: Declarantes por competência, como a API devolvia em 17/09/2026.
REAL = {(2026, 1): 2299, (2026, 2): 2322, (2026, 3): 2124, (2026, 4): 2139,
        (2026, 5): 2050, (2026, 6): 1882, (2026, 7): 318, (2026, 8): 1}


class TestMaisRecenteFechada(unittest.TestCase):

    def test_ignora_competencia_em_preenchimento(self):
        """Em 17/09/2026 o mês 7 tinha 318 declarantes contra 1.882 do mês 6.

        Regressão do defeito que motivou a troca de fonte: a régua antiga
        contava linhas do DAIR_CARTEIRA, que vêm paginadas de 5.000 em 5.000, e
        os meses 4 a 7 devolviam todos exatamente 5.000 — indistinguíveis.
        Escolher o 7 publicaria o patrimônio nacional com 15% dos RPPS.
        """
        c = ClienteFalso(REAL)
        self.assertEqual(
            competencia.mais_recente_fechada(c, date(2026, 9, 17)), (2026, 6))

    def test_a_virada_do_ano_nao_pede_competencia_inexistente(self):
        """O defeito que motivou o módulo: em janeiro, a aritmética de calendário
        pedia o mês de outubro do ano corrente."""
        c = ClienteFalso(REAL)
        self.assertEqual(
            competencia.mais_recente_fechada(c, date(2027, 1, 12)), (2026, 6))
        anos = {pedido[0] for pedido in c.pedidos}
        self.assertIn(2026, anos)

    def test_funciona_com_volumes_de_uma_uf(self):
        """Com filtro de UF os volumes caem duas ordens de grandeza, e um piso
        absoluto classificaria todo mês como vazio."""
        mapa = {(2026, m): 78 for m in range(1, 7)}
        mapa[(2026, 7)] = 12
        c = ClienteFalso(mapa)
        self.assertEqual(
            competencia.mais_recente_fechada(c, date(2026, 9, 17), uf="ES"),
            (2026, 6))
        self.assertTrue(all(p[2] == "ES" for p in c.pedidos))

    def test_conta_declaracoes_e_nao_linhas_de_carteira(self):
        """A fonte importa: a carteira satura na paginação, a identificação não."""
        c = ClienteFalso(REAL)
        competencia.mais_recente_fechada(c, date(2026, 9, 17), meses=3)
        self.assertTrue(all(p[3] == "DAIR_IDENTIFICACAO" for p in c.pedidos))

    def test_medida_saturada_falha_alto(self):
        """Página cheia significa que a contagem parou de distinguir."""
        from cadprev import endpoints
        c = ClienteFalso({(2026, 8): endpoints.PAGE_SIZE})
        with self.assertRaises(competencia.MedidaSaturada):
            competencia.mais_recente_fechada(c, date(2026, 9, 17), meses=2)

    def test_base_vazia_devolve_nada_em_vez_de_chutar(self):
        c = ClienteFalso({})
        self.assertIsNone(competencia.mais_recente_fechada(c, date(2026, 9, 16)))

    def test_caminha_para_tras_e_para(self):
        c = ClienteFalso(REAL)
        competencia.mais_recente_fechada(c, date(2026, 9, 17), meses=5)
        self.assertEqual(len(c.pedidos), 5)
        self.assertEqual(c.pedidos[0][:2], (2026, 8))
        self.assertEqual(c.pedidos[-1][:2], (2026, 4))

    def test_nao_pergunta_pelo_mes_corrente(self):
        """A competência do DAIR é a posição do último dia do mês: enquanto o
        mês corre, não há o que declarar.

        Era uma requisição desperdiçada por execução, e é a que aparece no log
        da falha de 21/09/2026 — ``dt_mes=9`` pedido no dia 21 de setembro.
        """
        c = ClienteFalso(REAL)
        competencia.mais_recente_fechada(c, date(2026, 9, 21))
        self.assertNotIn((2026, 9), [p[:2] for p in c.pedidos])
        self.assertEqual(c.pedidos[0][:2], (2026, 8))

    def test_a_janela_cobre_o_ano_inteiro_mesmo_comecando_um_mes_atras(self):
        """Encurtar o começo não pode encurtar o alcance: a régua precisa ver
        meses cheios para saber que os recentes estão vazios."""
        c = ClienteFalso(REAL)
        competencia.mais_recente_fechada(c, date(2026, 9, 21))
        vistos = [p[:2] for p in c.pedidos]
        self.assertEqual(len(vistos), competencia.MESES_PARA_TRAS)
        self.assertIn((2025, 9), vistos, "a janela tem de alcançar doze meses atrás")

    def test_volumes_vem_do_mais_recente_para_o_mais_antigo(self):
        c = ClienteFalso(REAL)
        vistos = competencia.volumes(c, date(2026, 2, 3), meses=3)
        self.assertEqual([(a, m) for a, m, _ in vistos],
                         [(2026, 1), (2025, 12), (2025, 11)])


class TestUltimaDeCada(unittest.TestCase):
    """A última competência de cada ente — o par comparado inteiro."""

    def test_ano_e_mes_nao_se_comparam_separados(self):
        """Quem declarou dezembro de 2025 e março de 2026 não declarou
        dezembro de 2026.

        ``MAX(ano)`` com ``MAX(mes)`` é a armadilha: combinaria o ano de uma
        linha com o mês de outra e produziria uma competência que nunca
        existiu. O painel sairia pedindo essa competência à API, e receberia
        vazio para todo mundo que virou o ano.
        """
        linhas = [{"cnpj_ente": "1", "ano": 2025, "mes": 12},
                  {"cnpj_ente": "1", "ano": 2026, "mes": 3}]
        self.assertEqual(competencia.ultima_de_cada(linhas), {"1": (2026, 3)})

    def test_um_por_ente(self):
        linhas = [{"cnpj_ente": "1", "ano": 2026, "mes": 6},
                  {"cnpj_ente": "1", "ano": 2026, "mes": 8},
                  {"cnpj_ente": "2", "ano": 2026, "mes": 2}]
        self.assertEqual(competencia.ultima_de_cada(linhas),
                         {"1": (2026, 8), "2": (2026, 2)})

    def test_linha_sem_competencia_nao_entra(self):
        """Ausência não é competência: um cabeçalho sem mês não pode virar o
        último mês declarado nem apagar o que já se sabia do ente."""
        linhas = [{"cnpj_ente": "1", "ano": 2026, "mes": 5},
                  {"cnpj_ente": "1", "ano": 2026, "mes": None},
                  {"cnpj_ente": "2", "ano": None, "mes": 7},
                  {"cnpj_ente": None, "ano": 2026, "mes": 9}]
        self.assertEqual(competencia.ultima_de_cada(linhas), {"1": (2026, 5)})


if __name__ == "__main__":
    unittest.main()
