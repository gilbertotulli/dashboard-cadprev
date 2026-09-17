"""O workflow de publicação, lido como código.

Ninguém executa o workflow localmente: ele só roda no runner, uma vez por
semana, e um erro de ordenação ali fica invisível até a segunda-feira. Estes
testes conferem as poucas propriedades de que a carga depende.

O caso que os motivou: o passo do Anexo 04 foi inserido ancorado numa string que
aparecia duas vezes, e caiu dentro do ramo que republica a partir do cache — o
ramo que existe justamente para não varrer nada. Rodaria meia hora de coleta num
push de CSS, e nunca rodaria na carga de verdade.
"""

import os
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO = os.path.join(RAIZ, ".github", "workflows", "publicar.yml")


def _passo_de_ingestao():
    with open(CAMINHO, encoding="utf-8") as fh:
        texto = fh.read()
    inicio = texto.index("name: Ingerir dados reais")
    fim = texto.index("name: Guardar o banco")
    return texto[inicio:fim]


class TestOrdemDaCarga(unittest.TestCase):

    def setUp(self):
        self.passo = _passo_de_ingestao()

    def test_republicacao_do_cache_nao_consulta_api_nenhuma(self):
        """O ramo do cache existe para não bater na API. Nada de coleta nele."""
        ramo = self.passo[:self.passo.index("exit 0")]
        for comando in ("cadprev ingest", "cadprev siconfi", "cadprev marco"):
            self.assertNotIn(comando, ramo,
                             "{} dentro do ramo de republicação".format(comando))

    def test_anexo_04_vem_depois_da_carga_do_cadprev(self):
        """É a coleta mais cara; só faz sentido com o essencial já no banco."""
        self.assertLess(self.passo.index("cadprev ingest DAIR_CARTEIRA"),
                        self.passo.index("cadprev siconfi-rreo"))
        self.assertLess(self.passo.index("cadprev ingest DRAA_NOTIFICACAO"),
                        self.passo.index("cadprev siconfi-rreo"))

    def test_tabela_de_entes_vem_antes_do_anexo_04(self):
        """O Anexo 04 é consultado por código IBGE, que vem da tabela de entes."""
        self.assertLess(self.passo.index("cadprev siconfi 2>&1"),
                        self.passo.index("cadprev siconfi-rreo"))

    def test_guarda_de_essenciais_e_a_ultima_palavra(self):
        """Ela precisa ver tudo o que foi ingerido antes de decidir."""
        for comando in ("cadprev ingest DAIR_CARTEIRA", "cadprev siconfi-rreo"):
            self.assertLess(self.passo.index(comando),
                            self.passo.index("endpoints essenciais"))

    def test_filtro_de_uf_definido_antes_de_ser_usado(self):
        primeiro_uso = self.passo.index("$FILTRO_UF")
        self.assertLess(self.passo.index('FILTRO_UF=""'), primeiro_uso)


if __name__ == "__main__":
    unittest.main()
