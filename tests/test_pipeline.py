"""Ingestão e agregação, de ponta a ponta, sobre as amostras de demonstração."""

import json
import os
import shutil
import tempfile
import unittest

from cadprev import build, demo, fundos
from cadprev.client import Cliente
from cadprev.store import Store


class TestPipeline(unittest.TestCase):
    """Roda o caminho real: amostra crua → fieldmap → SQLite → JSON."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="cadprev-teste-")
        cls.fixtures = os.path.join(cls.dir, "fixtures")
        demo.escrever(cls.fixtures)

        from cadprev import ingest
        cls.banco = os.path.join(cls.dir, "teste.sqlite3")
        cliente = Cliente(fixtures=cls.fixtures, pausa=0)
        with Store(cls.banco) as store:
            cls.resultado = ingest.ingerir_varios(cliente, store, [
                "RPPS_REGIME_PREVIDENCIARIO", "RPPS_CRP", "RPPS_ALIQUOTA", "DIPR",
                "DAIR_CARTEIRA", "DRAA_ESTATISTICA", "DRAA_SEGREGACAO_MASSA",
                "DRAA_FLUXO_ATUARIAL", "DRAA_VALORES_COMPROMISSOS",
                "DRAA_HIPOTESE_ATUARIAL", "DRAA_PLANO_CUSTEIO"])
            cls.saida = os.path.join(cls.dir, "data")
            build.construir(store, dir_saida=cls.saida, origem="demonstracao")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def _json(self, nome):
        with open(os.path.join(self.saida, nome), encoding="utf-8") as fh:
            return json.load(fh)

    def test_ingestao_sem_erros(self):
        self.assertEqual(self.resultado["erros"], [])
        self.assertTrue(all(r["linhas"] > 0 for r in self.resultado["ok"]))

    def test_demo_roda_em_nivel_b(self):
        """O padrão reflete o que se sabe da API hoje: sem plano do ativo."""
        carteira = self._json("carteira-nacional.json")
        self.assertEqual(carteira["nivel"], fundos.NIVEL_B)

    def test_meta_declara_a_origem(self):
        meta = self._json("meta.json")
        self.assertEqual(meta["origem"], "demonstracao")
        self.assertEqual(meta["capitais_conhecidas"], 27)

    def test_crp_vencido_nao_conta_como_valido(self):
        """Regressão: 'VÁLIDO' e 'VENCIDO' começam com a mesma letra, e um
        prefixo contava todo certificado vencido como regular."""
        panorama = self._json("panorama.json")
        self.assertLess(panorama["kpis"]["perc_valido"], 100.0)
        self.assertTrue(panorama["vencidos_ha_mais_tempo"])
        for item in panorama["vencidos_ha_mais_tempo"]:
            self.assertGreaterEqual(item["dias"], 0)

    def test_crp_lido_por_valor_e_nao_por_campo(self):
        """A API e a sua documentação discordam sobre qual campo é qual;
        a leitura precisa funcionar nas duas ordens."""
        from cadprev.build import _ler_crp
        hoje = "2026-09-15"
        # ordem real da API
        self.assertEqual(_ler_crp("ADMINISTRATIVO", "VENCIDO", None, hoje),
                         {"valido": False, "judicial": False})
        self.assertEqual(_ler_crp("JUDICIAL", "VÁLIDO", None, hoje),
                         {"valido": True, "judicial": True})
        # ordem documentada, caso a SPREV corrija a inversão
        self.assertEqual(_ler_crp("Vigente", "Judicial", None, hoje),
                         {"valido": True, "judicial": True})
        self.assertEqual(_ler_crp("Vencido", "Administrativo", None, hoje),
                         {"valido": False, "judicial": False})

    def test_crp_usa_a_emissao_mais_recente(self):
        """O endpoint devolve o histórico; contar linhas cruas trataria cada
        renovação como um RPPS diferente."""
        panorama = self._json("panorama.json")
        entes = self._json("entes.json")
        self.assertEqual(panorama["kpis"]["entes"], len(entes))

    def test_bases_de_calculo_fora_do_caixa(self):
        """Regressão: as rubricas de id abaixo de 33 são a folha sobre a qual a
        contribuição incide, não dinheiro que entrou. Somá-las multiplicava o
        caixa do RPPS por várias vezes."""
        from cadprev import codigos
        entes = self._json("entes.json")
        ficha = self._json(os.path.join("ente", entes[0]["cnpj"] + ".json"))
        caixa = ficha["caixa"]
        with Store(self.banco) as store:
            bruto = store.consultar(
                "SELECT SUM(valor) FROM dipr WHERE cnpj_ente = ?",
                (entes[0]["cnpj"],))[0][0] or 0.0
            bases = store.consultar(
                "SELECT SUM(valor) FROM dipr WHERE cnpj_ente = ? AND codigo_rubrica < ?",
                (entes[0]["cnpj"], codigos.CODIGO_MINIMO_VALOR_EFETIVO))[0][0] or 0.0
        self.assertGreater(bases, 0, "o demo precisa conter bases de cálculo")
        movimentado = caixa["total_receita"] + caixa["total_despesa"]
        self.assertAlmostEqual(movimentado, bruto - bases, places=0)

    def test_vencidos_ordenados_do_maior_atraso(self):
        vencidos = self._json("panorama.json")["vencidos_ha_mais_tempo"]
        dias = [v["dias"] for v in vencidos]
        self.assertEqual(dias, sorted(dias, reverse=True))

    def test_ranking_dos_menores_exclui_zerados(self):
        carteira = self._json("carteira-nacional.json")
        for item in carteira["menores"]:
            self.assertGreater(item["valor"], 0)
        self.assertLessEqual(carteira["menores"][0]["valor"],
                             carteira["maiores"][0]["valor"])

    def test_recortes_somam_o_total(self):
        """Cada corte por grupo tem de fechar com o patrimônio total."""
        carteira = self._json("carteira-nacional.json")
        for chave in ("por_fundo", "por_segmento", "por_esfera", "por_regiao"):
            soma = sum(item["valor"] for item in carteira[chave])
            self.assertAlmostEqual(soma, carteira["total"], places=0,
                                   msg="{} não fecha com o total".format(chave))

    def test_esferas_e_regioes_reconhecidas(self):
        carteira = self._json("carteira-nacional.json")
        rotulos = {item["rotulo"] for item in carteira["por_esfera"]}
        self.assertIn("Estaduais", rotulos)
        self.assertIn("Capitais", rotulos)
        regioes = {item["rotulo"] for item in carteira["por_regiao"]}
        self.assertNotIn("Não classificado", regioes)

    def test_ficha_do_ente_tem_as_quatro_abas(self):
        entes = self._json("entes.json")
        self.assertTrue(entes)
        ficha = self._json(os.path.join("ente", entes[0]["cnpj"] + ".json"))
        for secao in ("caixa", "carteira", "atuaria", "estatistica"):
            self.assertTrue(ficha[secao]["disponivel"], secao)
        self.assertIsNotNone(ficha["crp"])
        self.assertIn("valido", ficha["crp"])

    def test_fluxo_atuarial_fecha_com_os_totais(self):
        """A composição soma exatamente o total declarado pela própria API.

        É a checagem que pega erro de classificação: se um item de base de
        cálculo entrasse como receita, a soma estouraria o total.
        """
        entes = self._json("entes.json")
        ficha = self._json(os.path.join("ente", entes[0]["cnpj"] + ".json"))
        fluxo = ficha["atuaria"]["fluxo"]
        self.assertTrue(fluxo["disponivel"])
        soma_receitas = sum(i["valor"] for i in fluxo["itens_receita"])
        self.assertAlmostEqual(soma_receitas, fluxo["receitas"], places=0)
        soma_despesas = sum(i["valor"] for i in fluxo["itens_despesa"])
        self.assertAlmostEqual(soma_despesas, fluxo["despesas"], places=0)

    def test_resultado_atuarial_vem_do_codigo(self):
        entes = self._json("entes.json")
        ficha = self._json(os.path.join("ente", entes[0]["cnpj"] + ".json"))
        resultado = ficha["atuaria"]["resultado"]
        self.assertIn(resultado["situacao"], ("deficit", "superavit", "equilibrio"))
        self.assertGreater(resultado["ativos_garantidores"], 0)

    def test_mes_sem_rubrica_nao_vira_zero(self):
        """Ausência de declaração e valor zero são coisas diferentes."""
        entes = self._json("entes.json")
        ficha = self._json(os.path.join("ente", entes[0]["cnpj"] + ".json"))
        caixa = ficha["caixa"]
        self.assertIn("meses_declarados", caixa)
        for ponto in caixa["serie"]:
            if ponto["receita"] is None or ponto["despesa"] is None:
                self.assertIsNone(ponto["resultado"])

    def test_disponibilidades_marcadas_como_nao_alocacao(self):
        """Disponibilidades financeiras entram no total mas não na leitura
        de enquadramento."""
        entes = self._json("entes.json")
        ficha = self._json(os.path.join("ente", entes[0]["cnpj"] + ".json"))
        por_rotulo = {s["rotulo"]: s for s in ficha["carteira"]["segmentos"]}
        self.assertIn("Disponibilidades Financeiras", por_rotulo)
        self.assertFalse(por_rotulo["Disponibilidades Financeiras"]["alocacao"])
        self.assertTrue(por_rotulo["Renda Fixa"]["alocacao"])

    def test_reingestao_e_idempotente(self):
        from cadprev import ingest
        cliente = Cliente(fixtures=self.fixtures, pausa=0)
        with Store(self.banco) as store:
            antes = store.contar("DAIR_CARTEIRA")
            ingest.ingerir(cliente, store, "DAIR_CARTEIRA")
            self.assertEqual(store.contar("DAIR_CARTEIRA"), antes)


class TestClienteOffline(unittest.TestCase):

    def test_amostra_ausente_explica_o_que_fazer(self):
        from cadprev.client import Cliente, ErroDaAPI
        cliente = Cliente(fixtures=tempfile.mkdtemp())
        with self.assertRaises(ErroDaAPI) as ctx:
            list(cliente.registros("RPPS_CRP"))
        self.assertIn("inspect", str(ctx.exception))

    def test_endpoint_desconhecido(self):
        from cadprev import endpoints
        with self.assertRaises(KeyError):
            endpoints.get("NAO_EXISTE")


if __name__ == "__main__":
    unittest.main()
