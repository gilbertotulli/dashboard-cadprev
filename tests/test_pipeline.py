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


class TestOrigemDosDados(unittest.TestCase):
    """A proteção contra misturar dados reais com sintéticos.

    Um banco pode acabar com as duas origens: a substituição na ingestão é por
    escopo, e o escopo do demo não coincide com o de uma carga real. O painel
    sairia carimbado como real exibindo números inventados.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cadprev-origem-")
        self.banco = os.path.join(self.dir, "t.sqlite3")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_banco_novo_nao_tem_origem(self):
        with Store(self.banco) as store:
            self.assertEqual(store.origens(), [])
            self.assertIsNone(store.origem_unica())

    def test_marca_e_idempotente(self):
        with Store(self.banco) as store:
            store.marcar_origem("api")
            store.marcar_origem("api")
            self.assertEqual(store.origens(), ["api"])
            self.assertEqual(store.origem_unica(), "api")

    def test_construir_recusa_banco_misturado(self):
        with Store(self.banco) as store:
            store.marcar_origem("api")
            store.marcar_origem("demonstracao")
            self.assertIsNone(store.origem_unica())
            with self.assertRaises(ValueError) as ctx:
                build.construir(store, dir_saida=os.path.join(self.dir, "data"))
            self.assertIn("origens diferentes", str(ctx.exception))

    def test_construir_recusa_carimbar_demo_como_api(self):
        with Store(self.banco) as store:
            store.marcar_origem("demonstracao")
            with self.assertRaises(ValueError) as ctx:
                build.construir(store, dir_saida=os.path.join(self.dir, "data"),
                                origem="api")
            self.assertIn("demonstracao", str(ctx.exception))


class TestLimiteDeTaxa(unittest.TestCase):
    """A API devolve 420 quando o volume acumulado incomoda."""

    def test_codigos_de_limite_reconhecidos(self):
        from cadprev.client import CODIGOS_DE_LIMITE
        self.assertIn(420, CODIGOS_DE_LIMITE)
        self.assertIn(429, CODIGOS_DE_LIMITE)

    def test_pausa_cresce_e_para_no_teto(self):
        from cadprev.client import Cliente
        cliente = Cliente(pausa=1.0, pausa_maxima=8.0)
        vistas = []
        for _ in range(5):
            cliente._desacelerar()
            vistas.append(cliente.pausa)
        self.assertEqual(vistas, [2.0, 4.0, 8.0, 8.0, 8.0])
        self.assertEqual(cliente.limites_recebidos, 5)

    def test_retry_after_manda(self):
        import urllib.error
        from cadprev.client import Cliente
        cliente = Cliente()
        erro = urllib.error.HTTPError(
            "http://x", 429, "slow down", {"Retry-After": "90"}, None)
        self.assertEqual(cliente._espera_do_limite(erro, 1), 90.0)

    def test_sem_retry_after_dobra_a_cada_tentativa(self):
        import urllib.error
        from cadprev.client import Cliente, ESPERA_INICIAL_LIMITE
        cliente = Cliente()
        erro = urllib.error.HTTPError("http://x", 420, "calm", {}, None)
        self.assertEqual(cliente._espera_do_limite(erro, 1), ESPERA_INICIAL_LIMITE)
        self.assertEqual(cliente._espera_do_limite(erro, 3), ESPERA_INICIAL_LIMITE * 4)


class TestIngestaoAtomica(unittest.TestCase):
    """Regressão: uma varredura interrompida no meio apagava os dados bons e
    deixava o pedaço gravado, sem registro de execução. O build seguinte tratava
    o pedaço como base completa."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cadprev-atomico-")
        self.banco = os.path.join(self.dir, "t.sqlite3")
        self.bom = [{"cnpj_ente": "00000000000001", "ente": "Bom", "uf": "ES",
                     "numero_crp": "1", "emissao": "2026-01-01",
                     "validade": "2027-01-01"}]

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _falha_no_meio(self):
        for i in range(5000):
            yield dict(self.bom[0], cnpj_ente="{:014d}".format(i + 100))
        raise RuntimeError("a API pediu calma")

    def test_falha_preserva_o_que_havia(self):
        with Store(self.banco) as store:
            store.gravar("RPPS_CRP", self.bom)
        with Store(self.banco) as store:
            with self.assertRaises(RuntimeError):
                store.gravar("RPPS_CRP", self._falha_no_meio())
        with Store(self.banco) as store:
            self.assertEqual(store.contar("RPPS_CRP"), 1)
            linha = store.consultar("SELECT ente FROM rpps_crp")[0]
            self.assertEqual(linha["ente"], "Bom")

    def test_falha_nao_registra_execucao(self):
        with Store(self.banco) as store:
            with self.assertRaises(RuntimeError):
                store.gravar("RPPS_CRP", self._falha_no_meio())
        with Store(self.banco) as store:
            self.assertIsNone(store.ultima_execucao("RPPS_CRP"))
            self.assertEqual(store.contar("RPPS_CRP"), 0)

    def test_sucesso_substitui(self):
        with Store(self.banco) as store:
            store.gravar("RPPS_CRP", self.bom)
            novos = [dict(self.bom[0], cnpj_ente="00000000000002", ente="Novo")]
            store.gravar("RPPS_CRP", novos)
            self.assertEqual(store.contar("RPPS_CRP"), 1)
            self.assertEqual(store.consultar("SELECT ente FROM rpps_crp")[0]["ente"],
                             "Novo")
