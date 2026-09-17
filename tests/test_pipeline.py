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

    def _nacional(self, nome):
        """O agregado nacional na combinação de chaves que abre por padrão."""
        from cadprev import qualidade
        return self._json(nome)["variantes"][qualidade.chave_padrao()]

    def test_ingestao_sem_erros(self):
        self.assertEqual(self.resultado["erros"], [])
        self.assertTrue(all(r["linhas"] > 0 for r in self.resultado["ok"]))

    def test_demo_roda_em_nivel_b(self):
        """O padrão reflete o que se sabe da API hoje: sem plano do ativo."""
        carteira = self._nacional("carteira-nacional.json")
        self.assertEqual(carteira["nivel"], fundos.NIVEL_B)

    def test_meta_declara_a_origem(self):
        meta = self._json("meta.json")
        self.assertEqual(meta["origem"], "demonstracao")
        self.assertEqual(meta["capitais_conhecidas"], 27)

    def test_crp_vencido_nao_conta_como_valido(self):
        """Regressão: 'VÁLIDO' e 'VENCIDO' começam com a mesma letra, e um
        prefixo contava todo certificado vencido como regular."""
        panorama = self._nacional("panorama.json")
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
        panorama = self._nacional("panorama.json")
        entes = [e for e in self._json("entes.json") if e["tem_rpps"]]
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
        vencidos = self._nacional("panorama.json")["vencidos_ha_mais_tempo"]
        dias = [v["dias"] for v in vencidos]
        self.assertEqual(dias, sorted(dias, reverse=True))

    def test_ranking_dos_menores_exclui_zerados(self):
        carteira = self._nacional("carteira-nacional.json")
        for item in carteira["menores"]:
            self.assertGreater(item["valor"], 0)
        self.assertLessEqual(carteira["menores"][0]["valor"],
                             carteira["maiores"][0]["valor"])

    def test_recortes_somam_o_total(self):
        """Cada corte por grupo tem de fechar com o patrimônio total."""
        carteira = self._nacional("carteira-nacional.json")
        for chave in ("por_fundo", "por_segmento", "por_esfera", "por_regiao"):
            soma = sum(item["valor"] for item in carteira[chave])
            self.assertAlmostEqual(soma, carteira["total"], places=0,
                                   msg="{} não fecha com o total".format(chave))

    def test_esferas_e_regioes_reconhecidas(self):
        carteira = self._nacional("carteira-nacional.json")
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

    # ------------------------------------------------ qualidade e filtros

    def test_lancamento_impossivel_sai_de_todas_as_somas(self):
        """Excluir do total nacional e manter na ficha do ente publicaria dois
        números incompatíveis sobre o mesmo fato."""
        q = self._json("qualidade.json")
        self.assertEqual(len(q["achados"]), 1)
        achado = q["achados"][0]
        ficha = self._json(os.path.join("ente", achado["cnpj"] + ".json"))
        carteira = ficha["carteira"]
        self.assertEqual(carteira["excluidas"], 1)
        self.assertAlmostEqual(carteira["valor_excluido"], achado["posicao"], places=2)
        # o que sobrou não contém mais o valor impossível
        self.assertLess(carteira["total"], achado["posicao"] / 1000)
        nacional = self._nacional("carteira-nacional.json")
        self.assertLess(nacional["total"], achado["posicao"])

    def test_achado_traz_a_evidencia_e_nao_o_conserto(self):
        achado = self._json("qualidade.json")["achados"][0]
        for campo in ("fundo", "posicao", "maior_pl_declarado", "vezes",
                      "valor_unitario", "quantidade_cotas", "ente", "uf"):
            self.assertIn(campo, achado)
        self.assertGreater(achado["vezes"], 10)
        self.assertNotIn("posicao_corrigida", achado)

    def test_ente_sem_rpps_nao_conta_como_rpps(self):
        """O CRP é do ente federativo: a base cobre quem migrou para o RGPS."""
        indice = self._json("entes.json")
        sem_rpps = [e for e in indice if not e["tem_rpps"]]
        self.assertTrue(sem_rpps, "o demo precisa conter entes sem RPPS")
        meta = self._json("meta.json")
        self.assertEqual(meta["com_rpps"], len(indice) - len(sem_rpps))
        self.assertLess(meta["com_rpps"], meta["entes"])

    def test_todas_as_combinacoes_de_chaves_existem(self):
        from cadprev import qualidade
        esperadas = set(qualidade.combinacoes())
        for arquivo in ("panorama.json", "carteira-nacional.json"):
            self.assertEqual(set(self._json(arquivo)["variantes"]), esperadas)
        self.assertEqual(
            set(self._json("benchmark.json")["grupos"]["variantes"]), esperadas)

    def test_cada_chave_encolhe_o_universo(self):
        """Uma chave que não muda nada é uma chave que engana."""
        from cadprev import qualidade
        variantes = self._json("panorama.json")["variantes"]
        nenhuma = "0" * len(qualidade.FILTROS)
        base = variantes[nenhuma]["kpis"]["entes"]
        filtros = self._json("filtros.json")
        for i, filtro in enumerate(qualidade.FILTROS):
            if not filtros["atingidos"][filtro.chave]:
                continue
            chave = "".join("1" if j == i else "0"
                            for j in range(len(qualidade.FILTROS)))
            self.assertLess(variantes[chave]["kpis"]["entes"], base,
                            "a chave {} não excluiu ninguém".format(filtro.chave))

    def test_chaves_do_ente_marcam_quem_deve(self):
        indice = {e["cnpj"]: e for e in self._json("entes.json")}
        q = self._json("qualidade.json")
        alvo = q["achados"][0]["cnpj"]
        self.assertIn("posicao_impossivel", indice[alvo]["marcas"])
        marcados = sum(1 for e in indice.values()
                       if "dair_defasado" in e["marcas"])
        self.assertEqual(marcados, q["entes_marcados"]["dair_defasado"])


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


class TestChaveSemFonte(unittest.TestCase):
    """Uma chave cuja fonte não está no banco não pode dizer "−0".

    Zero afirma que ninguém está atrasado. A verdade, quando falta o endpoint,
    é que não há como saber — e as duas coisas levam a leituras opostas.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cadprev-chaves-")
        self.fixtures = os.path.join(self.dir, "fx")
        demo.escrever(self.fixtures)
        self.banco = os.path.join(self.dir, "t.sqlite3")
        self.saida = os.path.join(self.dir, "data")
        from cadprev import ingest
        cliente = Cliente(fixtures=self.fixtures, pausa=0)
        with Store(self.banco) as store:
            # De propósito sem DAIR_IDENTIFICACAO.
            ingest.ingerir_varios(cliente, store, [
                "RPPS_CRP", "RPPS_REGIME_PREVIDENCIARIO", "DAIR_CARTEIRA"])
            build.construir(store, dir_saida=self.saida, origem="demonstracao")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_chave_sem_endpoint_fica_indisponivel(self):
        with open(os.path.join(self.saida, "filtros.json"), encoding="utf-8") as fh:
            filtros = {f["chave"]: f for f in json.load(fh)["filtros"]}
        self.assertFalse(filtros["sem_dair_defasado"]["disponivel"])
        self.assertEqual(filtros["sem_dair_defasado"]["fonte"], "DAIR_IDENTIFICACAO")
        for chave in ("somente_rpps", "sem_lancamento_impossivel", "sem_crp_vencido"):
            self.assertTrue(filtros[chave]["disponivel"], chave)

    def test_a_regua_continua_valendo_sem_os_outros_endpoints(self):
        """A exclusão do lançamento impossível não depende de DAIR nem de CRP."""
        with open(os.path.join(self.saida, "qualidade.json"), encoding="utf-8") as fh:
            self.assertEqual(len(json.load(fh)["achados"]), 1)


class TestNovasFontesDoDRAA(unittest.TestCase):
    """Notificação, encaminhamento, amortização e projetado contra executado."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="cadprev-draa-")
        fixtures = os.path.join(cls.dir, "fx")
        demo.escrever(fixtures)
        from cadprev import ingest
        cls.banco = os.path.join(cls.dir, "t.sqlite3")
        cls.saida = os.path.join(cls.dir, "data")
        cliente = Cliente(fixtures=fixtures, pausa=0)
        with Store(cls.banco) as store:
            ingest.ingerir_varios(cliente, store, [
                "RPPS_CRP", "RPPS_REGIME_PREVIDENCIARIO", "DAIR_CARTEIRA",
                "DRAA_NOTIFICACAO", "DRAA_ENCAMINHAMENTO",
                "DRAA_COMPARATIVO_RECEITA", "DRAA_PLANO_AMORTIZACAO"])
            build.construir(store, dir_saida=cls.saida, origem="demonstracao")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def _ficha(self, cnpj):
        with open(os.path.join(self.saida, "ente", cnpj + ".json"),
                  encoding="utf-8") as fh:
            return json.load(fh)

    def _entes(self):
        with open(os.path.join(self.saida, "entes.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_reenvio_nao_dobra_o_plano_de_amortizacao(self):
        """A API devolve a versão substituída junto da válida.

        Somá-las dobraria o saldo devedor de um em cada dez RPPS e desenharia
        duas curvas como se fossem uma.
        """
        vistos = 0
        for ente in self._entes():
            amort = self._ficha(ente["cnpj"]).get("amortizacao") or {}
            if not amort.get("disponivel"):
                continue
            vistos += 1
            anos = [a["ano"] for a in amort["anos"]]
            self.assertEqual(len(anos), len(set(anos)),
                             "anos repetidos em " + ente["ente"])
        self.assertTrue(vistos, "o demo precisa gerar plano de amortização")

    def test_reenvio_nao_dobra_o_comparativo(self):
        for ente in self._entes():
            pe = self._ficha(ente["cnpj"]).get("projetado_executado") or {}
            if not pe.get("disponivel"):
                continue
            codigos = [i["codigo"] for i in pe["itens"]]
            self.assertEqual(len(codigos), len(set(codigos)))

    def test_diferenca_e_projetado_menos_executado(self):
        """O sinal da fonte, conferido: 79.986 linhas nacionais fecham assim, e
        nenhuma fecha no sentido inverso."""
        achou = False
        for ente in self._entes():
            pe = self._ficha(ente["cnpj"]).get("projetado_executado") or {}
            if not pe.get("disponivel"):
                continue
            achou = True
            self.assertEqual(pe["conferencia_falhou"], 0)
            for item in pe["itens"]:
                self.assertAlmostEqual(
                    item["projetado"] - item["executado"], item["diferenca"],
                    places=2)
        self.assertTrue(achou)

    def test_saldo_crescente_aparece(self):
        """Pagamento que não cobre os juros faz o saldo subir — e isso não
        aparece em nenhum total, só na curva."""
        crescentes = 0
        for ente in self._entes():
            amort = self._ficha(ente["cnpj"]).get("amortizacao") or {}
            if amort.get("disponivel") and any(
                    (a["amortizacao"] or 0) < 0 for a in amort["anos"]):
                crescentes += 1
        self.assertTrue(crescentes)

    def test_notificacao_classificada_pelas_palavras_da_fonte(self):
        from cadprev import build as b
        self.assertEqual(
            b._classificar_notificacao("Notificacao respondida fora do prazo. "
                                       "Situacao irregular."), "irregular")
        self.assertEqual(
            b._classificar_notificacao("Resposta analisada. Item sem pendencia"),
            "encerrado")
        self.assertEqual(
            b._classificar_notificacao("Notificacao cancelada"), "encerrado")
        self.assertEqual(
            b._classificar_notificacao("Notificacao emitida. Aguardando resposta"),
            "em_curso")
        self.assertEqual(b._classificar_notificacao(None), "em_curso")

    def test_conformidade_nacional_conta_os_estados(self):
        with open(os.path.join(self.saida, "conformidade.json"),
                  encoding="utf-8") as fh:
            variantes = json.load(fh)["variantes"]
        from cadprev import qualidade
        c = variantes[qualidade.chave_padrao()]
        self.assertTrue(c["disponivel"])
        self.assertTrue(c["entes_notificados"])
        self.assertEqual(
            c["itens"],
            sum(i["irregular"] + i["em_curso"] + i["encerrado"]
                for i in c["por_item"]))

    def test_ficha_orfa_e_removida(self):
        """Uma carga menor não pode deixar no ar a ficha de quem saiu da base."""
        orfa = os.path.join(self.saida, "ente", "99999999999999.json")
        with open(orfa, "w", encoding="utf-8") as fh:
            fh.write("{}")
        with Store(self.banco) as store:
            build.construir(store, dir_saida=self.saida, origem="demonstracao")
        self.assertFalse(os.path.exists(orfa))
