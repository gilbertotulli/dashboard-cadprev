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


def _passo_de_competencia():
    with open(CAMINHO, encoding="utf-8") as fh:
        texto = fh.read()
    inicio = texto.index("name: Definir a competência")
    fim = texto.index("name: Conjunto de demonstração")
    return texto[inicio:fim]


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

    def test_carteira_traz_mais_de_uma_competencia(self):
        """A tela detalhada compara meses; sem três no banco não há o que
        comparar. E a mais recente vem primeiro: se a API cansar no meio, o
        painel fica com a competência que sustenta os agregados."""
        passo = self.passo
        self.assertIn("for VOLTA in 0 1 2", passo)
        self.assertIn("DAIR_CARTEIRA", passo)
        # A volta do ano é tratada: dezembro para janeiro não pode pedir mês 0.
        self.assertIn("M + 12", passo)
        self.assertIn("ANO - 1", passo)

    def test_api_fora_do_ar_nao_derruba_o_agendamento(self):
        """A execução nº 29 morreu aqui: a API respondeu 404 na descoberta da
        competência e o job inteiro abortou, sem sequer chegar à publicação.

        Com banco em cache há o que publicar — os mesmos números, com as datas
        antigas à vista. Abortar deixa o painel sem publicar e sem dizer por
        quê, que é pior.
        """
        passo = _passo_de_competencia()
        self.assertIn("origem=", passo)
        self.assertIn("::warning::", passo,
                      "cair para o banco precisa ficar visível")
        # A falha real continua sendo falha: sem API e sem banco não há painel.
        self.assertIn("::error::", passo)

    def test_varreu_exige_que_algo_tenha_sido_varrido(self):
        """Com o cache restaurado, a guarda de essenciais passa mesmo que a API
        não tenha respondido a nada — os dados estão no banco, só não vieram
        desta carga. Gravar isso no cache como varredura seria carimbar de
        fresco um banco que ninguém atualizou."""
        passo = self.passo
        self.assertIn("EXECUCOES_ANTES", passo)
        self.assertIn("EXECUCOES_DEPOIS", passo)
        self.assertLess(passo.index("EXECUCOES_ANTES"),
                        passo.index("EXECUCOES_DEPOIS"),
                        "a contagem anterior tem de vir antes da ingestão")
        # `varreu=nao` também aparece no atalho de republicação do cache, lá em
        # cima; procurá-lo solto não prova nada. O que precisa existir é a
        # comparação entre as duas contagens decidindo a marca.
        depois = passo[passo.index("EXECUCOES_DEPOIS"):]
        self.assertIn('[ "$EXECUCOES_DEPOIS" -gt "$EXECUCOES_ANTES" ]', depois)
        self.assertIn("varreu=sim", depois)
        self.assertIn("varreu=nao", depois)
        # E a marca não pode ser dada fora dessa decisão.
        antes = passo[:passo.index("EXECUCOES_DEPOIS")]
        self.assertNotIn("varreu=sim", antes,
                         "varreu=sim antes de conferir se algo foi varrido")

    def test_balanco_vem_depois_da_tabela_de_entes(self):
        """A DCA é consultada por código IBGE, que vem da tabela de entes."""
        passo = self.passo
        self.assertIn("siconfi-dca", passo)
        self.assertLess(passo.index("cadprev siconfi "),
                        passo.index("siconfi-dca"))

    def test_balanco_pede_dois_exercicios(self):
        """A entrega da DCA de um exercício vai até abril do seguinte: no começo
        do ano o balanço mais recente ainda é o de dois anos atrás, e pedir só
        um deixaria o confronto sem o lado contábil por quatro meses."""
        passo = self.passo
        self.assertIn("ANO - 1", passo)
        self.assertIn("ANO - 2", passo)

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
