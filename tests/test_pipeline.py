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
                "DAIR_CARTEIRA", "DAIR_GOVERNANCA",
                "DRAA_ESTATISTICA", "DRAA_SEGREGACAO_MASSA",
                "DRAA_FLUXO_ATUARIAL", "DRAA_VALORES_COMPROMISSOS",
                "DRAA_HIPOTESE_ATUARIAL", "DRAA_PLANO_CUSTEIO"])
            cls._siconfi(store)
            cls.saida = os.path.join(cls.dir, "data")
            build.construir(store, dir_saida=cls.saida, origem="demonstracao")

    @classmethod
    def _siconfi(cls, store):
        """A segunda fonte, do Tesouro.

        Sem ela o confronto entre as duas apurações do mesmo patrimônio não
        existe na saída, e os testes que o guardam passariam por não ter o que
        conferir — que é o pior jeito de um teste passar.
        """
        from cadprev import fieldmap, siconfi
        brutos = siconfi.Cliente(fixtures=cls.fixtures, pausa=0).entes()
        resolucao = fieldmap.resolver("SICONFI_ENTE", brutos[0].keys())
        store.gravar("SICONFI_ENTE",
                     (fieldmap.aplicar(resolucao, b) for b in brutos))

        rreo = siconfi.ClienteRREO(fixtures=cls.fixtures, pausa=0)
        do_anexo = []
        for alvo in store.consultar(
                "SELECT cnpj_ente, cod_ibge, esfera_siconfi FROM siconfi_ente"):
            itens = rreo.anexo_rpps(alvo["cod_ibge"], alvo["esfera_siconfi"],
                                    demo.ANO, 3)
            for item in itens:
                item["cnpj_ente"] = alvo["cnpj_ente"]
            do_anexo.extend(itens)
        if do_anexo:
            resolucao = fieldmap.resolver("SICONFI_RREO", do_anexo[0].keys())
            store.gravar("SICONFI_RREO",
                         (fieldmap.aplicar(resolucao, l) for l in do_anexo),
                         {"exercicio": demo.ANO, "periodo": 3})

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
        conferidos = 0
        for bloco in ficha["atuaria"]["blocos"]:
            fluxo = bloco["fluxo"]
            if not fluxo["disponivel"]:
                continue
            conferidos += 1
            soma_receitas = sum(i["valor"] for i in fluxo["itens_receita"])
            self.assertAlmostEqual(soma_receitas, fluxo["receitas"], places=0)
            soma_despesas = sum(i["valor"] for i in fluxo["itens_despesa"])
            self.assertAlmostEqual(soma_despesas, fluxo["despesas"], places=0)
        self.assertTrue(conferidos)

    def test_resultado_atuarial_vem_do_codigo(self):
        entes = self._json("entes.json")
        ficha = self._json(os.path.join("ente", entes[0]["cnpj"] + ".json"))
        blocos = ficha["atuaria"]["blocos"]
        self.assertTrue(blocos)
        for bloco in blocos:
            resultado = bloco["resultado"]
            self.assertIn(resultado["situacao"],
                          ("deficit", "superavit", "equilibrio"))
        self.assertTrue(any(b["resultado"]["ativos_garantidores"] > 0
                            for b in blocos))

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

    # ------------------------------------------- enquadramento na norma

    def test_enquadramento_compara_classe_com_o_teto_da_classe(self):
        """O teto é da classe de ativo, não do segmento.

        Dentro de Renda Fixa convivem classes com teto de 5%, 20%, 80% e 100%.
        Comparar o total do segmento com um desses tetos acusava, em
        17/09/2026, 390 dos 1.821 RPPS com carteira de exceder o limite legal
        quando só 20 excedem de fato — 371 acusações falsas de ilegalidade.
        """
        achou_sem_teto = False
        for ente in self._json("entes.json"):
            carteira = self._json(
                os.path.join("ente", ente["cnpj"] + ".json")).get("carteira") or {}
            if not carteira.get("disponivel"):
                continue
            classes = carteira["classes"]
            self.assertTrue(classes)
            # Dentro de um segmento, tetos diferentes: é isto que torna errado
            # comparar o segmento com um teto qualquer dele.
            for classe in classes:
                if classe["limite"] is None:
                    achou_sem_teto = True
                    self.assertFalse(classe["excede"])
                    continue
                self.assertEqual(
                    classe["excede"],
                    classe["perc"] > classe["limite"] + 0.05,
                    "{}: {}".format(ente["ente"], classe["rotulo"]))
            self.assertEqual(carteira["classes_fora_do_limite"],
                             sum(1 for c in classes if c["excede"]))
        self.assertTrue(achou_sem_teto,
                        "o demo precisa de classe sem teto (disponibilidades)")

    def test_segmento_acima_do_teto_de_uma_classe_nao_e_ilegalidade(self):
        """A regressão: 371 das 390 acusações vinham daqui.

        Um RPPS com 38% em ações (teto de 40%) e 9% em BDR (teto de 10%) tem o
        segmento Renda Variável em 47% — acima do teto da maior classe dele, e
        com as duas classes rigorosamente dentro dos próprios tetos.
        """
        achou = False
        for ente in self._json("entes.json"):
            carteira = self._json(
                os.path.join("ente", ente["cnpj"] + ".json")).get("carteira") or {}
            if not carteira.get("disponivel"):
                continue
            # o teto que a regra antiga usava: o da maior classe do segmento
            teto_antigo = {}
            for classe in carteira["classes"]:
                if classe["limite"] is not None:
                    teto_antigo.setdefault(classe["segmento"], classe["limite"])
            acusados = [s for s in carteira["segmentos"]
                        if teto_antigo.get(s["rotulo"])
                        and s["perc"] > teto_antigo[s["rotulo"]]]
            if acusados and not carteira["classes_fora_do_limite"]:
                achou = True
        self.assertTrue(
            achou, "o demo precisa de um ente que a regra antiga acusaria "
                   "e a correta absolve")

    def test_excesso_real_continua_visivel(self):
        excessos = []
        for ente in self._json("entes.json"):
            carteira = self._json(
                os.path.join("ente", ente["cnpj"] + ".json")).get("carteira") or {}
            if carteira.get("classes_fora_do_limite"):
                excessos.append(ente["ente"])
                self.assertGreater(carteira["maior_excesso"], 0)
        self.assertTrue(excessos, "o demo precisa de um excesso real")

    def test_percentual_e_o_que_a_fonte_calcula(self):
        """A fonte publica pc_recursos e ele soma 100%. Recalcular seria
        substituir a declaração por uma derivação — e só faz sentido quando o
        painel excluiu alguma linha do ente."""
        for ente in self._json("entes.json"):
            carteira = self._json(
                os.path.join("ente", ente["cnpj"] + ".json")).get("carteira") or {}
            if not carteira.get("disponivel"):
                continue
            soma = sum(c["perc"] for c in carteira["classes"])
            self.assertAlmostEqual(soma, 100.0, delta=1.0, msg=ente["ente"])
            self.assertEqual(carteira["percentual_da_fonte"],
                             not carteira["excluidas"])

    def test_competencia_acompanha_o_patrimonio(self):
        """Patrimônio sem competência é valor sem data."""
        nacional = self._nacional("carteira-nacional.json")
        self.assertTrue(nacional["competencia"])
        # A base guarda várias competências — a tela detalhada compara meses —
        # e o agregado usa exatamente uma. Somá-las contaria o mesmo dinheiro
        # duas vezes e o patrimônio do país cresceria a cada carga.
        self.assertTrue(nacional["varias"],
                        "o demo precisa de mais de uma competência no banco")
        detalhe = self._json(os.path.join(
            "ente", self._json("entes.json")[0]["cnpj"] + "-carteira.json"))
        self.assertGreater(len(detalhe["competencias"]), 1)
        recente = detalhe["competencias"][0]
        self.assertEqual(recente["competencia"], nacional["competencia"])
        soma_de_tudo = sum(c["total"] for c in detalhe["competencias"])
        ficha = self._json(os.path.join(
            "ente", self._json("entes.json")[0]["cnpj"] + ".json"))["carteira"]
        self.assertAlmostEqual(ficha["total"], recente["total"], places=2)
        self.assertLess(ficha["total"], soma_de_tudo)
        self.assertEqual(self._json("meta.json")["competencia_dair"],
                         nacional["competencia"])
        for ente in self._json("entes.json"):
            carteira = self._json(
                os.path.join("ente", ente["cnpj"] + ".json")).get("carteira") or {}
            if carteira.get("disponivel"):
                self.assertTrue(carteira["competencia"], ente["ente"])

    # ------------------------- a competência de cada um, e a de referência

    def _carteiras(self):
        """A carteira de cada ente, indexada pelo nome."""
        saida = {}
        for ente in self._json("entes.json"):
            ficha = self._json(os.path.join("ente", ente["cnpj"] + ".json"))
            saida[ente["ente"]] = ficha.get("carteira") or {}
        return saida

    def test_ficha_mostra_a_competencia_do_proprio_ente(self):
        """Cada RPPS declara no seu ritmo, e a ficha mostra o que ele entregou.

        O prazo do DAIR vai até o fim do mês seguinte: uma minoria sempre está
        à frente da competência que o país declarou, e uma minoria parou antes
        dela. Fixar a ficha na competência de referência esconderia o
        demonstrativo novo de uns e deixaria os outros sem carteira nenhuma —
        como se nunca tivessem declarado.
        """
        carteiras = self._carteiras()
        referencia = self._nacional("carteira-nacional.json")["competencia"]

        adiantados = [n for n, c in carteiras.items()
                      if c.get("disponivel") and c["competencia"] > referencia]
        atrasados = [n for n, c in carteiras.items()
                     if c.get("disponivel") and c["competencia"] < referencia]
        self.assertTrue(adiantados, "o demo precisa de quem declarou adiantado")
        self.assertTrue(atrasados, "o demo precisa de quem parou antes")

        for nome in adiantados + atrasados:
            c = carteiras[nome]
            self.assertFalse(c["na_referencia"], nome)
            self.assertEqual(c["referencia"], referencia, nome)
            # A ficha nunca omite a data do que está na tela.
            self.assertTrue(c["competencia"], nome)
        # Sinal do lado: positivo atrás da referência, negativo à frente.
        self.assertGreater(carteiras[atrasados[0]]["defasagem_meses"], 0)
        self.assertLess(carteiras[adiantados[0]]["defasagem_meses"], 0)

    def test_competencia_de_referencia_e_a_que_o_pais_declarou(self):
        """E não a mais recente que existe no banco.

        Depois do ``dair-atrasados`` a base guarda meses esparsos, trazidos
        ente a ente. Se a referência fosse o máximo da tabela, dois RPPS que
        entregaram adiantado definiriam a data do patrimônio nacional e todos
        os outros sumiriam do agregado por não terem declarado aquele mês.
        """
        nacional = self._nacional("carteira-nacional.json")
        with Store(self.banco) as store:
            competencias = build._competencias_do_dair(store)
        mais_recente = max(competencias["disponiveis"])
        self.assertEqual(competencias["competencia"], nacional["competencia"])
        self.assertLess(competencias["competencia"], mais_recente,
                        "o demo precisa de competência mais nova que a de "
                        "referência, senão a regra não é testada")
        # E a de referência é a que reúne quase todo mundo.
        com_carteira = sum(1 for c in self._carteiras().values()
                           if c.get("disponivel"))
        self.assertGreater(competencias["entes"], com_carteira / 2)

    def test_quem_declarou_adiantado_guarda_a_competencia_de_referencia(self):
        """A ficha mostra agosto; o comparativo continua lendo junho.

        Comparar o patrimônio de agosto de um RPPS com o de junho de outro
        mistura dois meses de aplicação com a diferença entre as carteiras. O
        bloco ``comparavel`` é a carteira do adiantado na data em que todos os
        outros são medidos — e é dele que saem os indicadores.
        """
        referencia = self._nacional("carteira-nacional.json")["competencia"]
        adiantados = [c for c in self._carteiras().values()
                      if c.get("disponivel") and c["na_referencia"] is False
                      and c["competencia"] > referencia]
        self.assertTrue(adiantados)
        for c in adiantados:
            comparavel = c["comparavel"]
            self.assertIsNotNone(comparavel)
            self.assertEqual(comparavel["competencia"], referencia)
            # Não é a mesma carteira: um mês de aplicação separa as duas.
            self.assertNotAlmostEqual(comparavel["total"], c["total"], places=2)
            self.assertAlmostEqual(
                sum(s["perc"] for s in comparavel["segmentos"]), 100.0, delta=1.0)

    def test_quem_parou_antes_nao_tem_o_que_comparar(self):
        """Ficha sim, comparativo não — e indefinido, nunca zero.

        Um RPPS cuja última declaração é de fevereiro aparece na tela com a
        carteira de fevereiro e a data à vista. O que não existe é carteira
        dele na data em que os outros são medidos, e um indicador derivado
        dela seria uma comparação entre meses disfarçada de comparação entre
        RPPS.
        """
        from cadprev import benchmark
        referencia = self._nacional("carteira-nacional.json")["competencia"]
        atrasados = [c for c in self._carteiras().values()
                     if c.get("disponivel") and c["competencia"] < referencia]
        self.assertTrue(atrasados)
        for c in atrasados:
            self.assertIsNone(c["comparavel"])
            self.assertIsNone(benchmark.base_comparavel(c))
            self.assertEqual(benchmark.alocacao({"carteira": c}), {})
            # Mas a carteira está lá, com total e composição.
            self.assertGreater(c["total"], 0)
            self.assertTrue(c["segmentos"])

    def test_indicadores_da_carteira_saem_da_competencia_de_referencia(self):
        """O número do comparativo é o da referência, não o da ficha."""
        from cadprev import benchmark
        referencia = self._nacional("carteira-nacional.json")["competencia"]
        for ente in self._json("entes.json"):
            ficha = self._json(os.path.join("ente", ente["cnpj"] + ".json"))
            c = ficha.get("carteira") or {}
            if not (c.get("disponivel") and c.get("comparavel")):
                continue
            indicadores = benchmark.calcular(ficha)
            inativos = (ficha.get("estatistica") or {}).get("inativos") or 0
            if not inativos:
                continue
            esperado = round(c["comparavel"]["total"] / inativos, 2)
            self.assertAlmostEqual(
                indicadores["patrimonio_por_beneficiario"], esperado, places=2,
                msg=ente["ente"])
            # E não o da competência que a ficha mostra.
            self.assertNotAlmostEqual(
                indicadores["patrimonio_por_beneficiario"],
                round(c["total"] / inativos, 2), places=2, msg=ente["ente"])

    # ------------------------------ o que cada fonte conta, e os imóveis

    def test_imoveis_sao_a_assimetria_que_o_painel_nao_resolve(self):
        """A prática contábil difere entre entes, e a amostra tem as duas.

        Em 22/09/2026, dos 857 RPPS confrontáveis, 57 declaravam imóveis:
        tirá-los da conta aproximava as duas fontes em 40 deles e afastava nos
        outros 17. Em Diadema/SP a divergência de −70,03% some ao tirar os
        imóveis; no Rio de Janeiro/RJ ela aparece. Com um caso só, o painel
        teria de afirmar uma regra que a fonte não tem.
        """
        aproxima = afasta = 0
        for ente in self._json("entes.json"):
            ficha = self._json(os.path.join("ente", ente["cnpj"] + ".json"))
            c = ((ficha.get("contabil") or {}).get("confronto") or {})
            if not c.get("imoveis"):
                continue
            self.assertGreater(c["perc_imoveis"], 0, ente["ente"])
            if abs(c["perc_sem_imoveis"]) < abs(c["perc"]):
                aproxima += 1
            else:
                afasta += 1
        self.assertTrue(aproxima, "falta o ente que não leva os imóveis ao Anexo 04")
        self.assertTrue(afasta, "falta o ente que leva")

        nacional = self._json("qualidade.json")["divergencia_entre_fontes"]
        self.assertEqual(nacional["imoveis_aproxima"], aproxima)
        self.assertEqual(nacional["imoveis_afasta"], afasta)
        self.assertEqual(nacional["com_imoveis"], aproxima + afasta)

    def test_disponibilidades_entram_dos_dois_lados(self):
        """A assimetria que já foi resolvida, e que precisa continuar assim.

        As disponibilidades financeiras são um segmento da carteira no CADPREV,
        e por isso o confronto soma caixa e investimentos do lado do SICONFI.
        Comparar só os investimentos deixaria de fora justamente a parte que o
        outro lado conta — e produziria uma divergência de critério em quase
        todo RPPS.
        """
        achou = False
        for ente in self._json("entes.json"):
            ficha = self._json(os.path.join("ente", ente["cnpj"] + ".json"))
            contabil = ficha.get("contabil") or {}
            carteira = ficha.get("carteira") or {}
            if not (contabil.get("confronto") and carteira.get("disponivel")):
                continue
            tem_disponibilidades = any(
                "isponibilidade" in (s.get("rotulo") or "")
                for s in carteira.get("segmentos") or [])
            if not tem_disponibilidades:
                continue
            achou = True
            # O total confrontado é investimentos + caixa, não só investimentos.
            self.assertAlmostEqual(
                contabil["confronto"]["siconfi"],
                round((contabil["investimentos"] or 0.0)
                      + (contabil["caixa"] or 0.0), 2),
                places=2, msg=ente["ente"])
        self.assertTrue(achou, "o demo precisa de disponibilidades na carteira")

    # ------------------------------------- nome do ativo e título público

    def test_ativo_nao_aparece_como_numero_de_contrato(self):
        """Nos títulos públicos os dois campos trocam de papel.

        ``nome_ativo`` traz um número e ``identificacao_ativo`` traz a
        descrição — e a tela mostrava o número. A regra é sobre o conteúdo, não
        sobre a classe: vale o primeiro dos dois campos que tenha letras.
        """
        achou = False
        for ente in self._json("entes.json"):
            caminho = os.path.join("ente", ente["cnpj"] + "-carteira.json")
            if not os.path.exists(os.path.join(self.saida, caminho)):
                continue
            for competencia in self._json(caminho)["competencias"]:
                for item in competencia["itens"]:
                    self.assertTrue(
                        any(ch.isalpha() for ch in item["nome"]),
                        "ativo publicado como número puro: " + repr(item["nome"]))
                    if item.get("nome_de") == "identificacao_ativo":
                        achou = True
        self.assertTrue(achou, "o demo precisa do caso em que os campos se invertem")

    def test_vencimento_do_titulo_so_quando_a_fonte_o_escreveu(self):
        """Sigla para quem a tem, vencimento só para quem o declarou.

        80% das descrições nacionais são o nome comercial do Tesouro Direto,
        sem data nenhuma. Derivar um vencimento aí seria afirmar o que a fonte
        não disse — e a tela mantém a descrição original ao lado do rótulo
        derivado justamente para que a derivação fique conferível.
        """
        com_venc = sem_venc = 0
        for ente in self._json("entes.json"):
            caminho = os.path.join("ente", ente["cnpj"] + "-carteira.json")
            if not os.path.exists(os.path.join(self.saida, caminho)):
                continue
            for competencia in self._json(caminho)["competencias"]:
                for item in competencia["itens"]:
                    titulo = item.get("titulo")
                    if not titulo:
                        continue
                    self.assertTrue(titulo["sigla"].startswith(("NTN", "LFT", "LTN")))
                    # A descrição original continua publicada ao lado.
                    self.assertTrue(item["nome"])
                    if titulo["vencimento"]:
                        com_venc += 1
                        self.assertIn(titulo["vencimento"][8:10], titulo["rotulo"])
                    else:
                        sem_venc += 1
        self.assertTrue(com_venc, "o demo precisa de título com vencimento escrito")
        self.assertTrue(sem_venc, "o demo precisa de título sem vencimento escrito")

    # -------------------------------------------- consolidados nacionais

    def _consolidado(self, qual):
        from cadprev import qualidade
        return self._json("consolidado.json")["variantes"][qualidade.chave_padrao()][qual]

    def test_consolidado_nao_conta_ausencia_como_zero(self):
        """O total nacional diz quantos entraram nele.

        R$ 40 bilhões somados por 1.500 RPPS e por 300 são dois fatos
        diferentes, e o segundo não é o país. Quem não declarou fica de fora e
        é contado à parte.
        """
        atuaria = self._consolidado("atuaria")
        provisoes = atuaria["compromissos"]["provisoes"]
        self.assertEqual(provisoes["entes"] + provisoes["sem_dado"], atuaria["rpps"])
        self.assertEqual(atuaria["indicadores"]["provisoes"]["n"], provisoes["entes"])

    def test_deficit_e_superavit_nao_se_compensam(self):
        """O superávit de um RPPS não cobre o déficit de outro.

        Um resultado nacional líquido afirmaria exatamente isso. Os dois lados
        somam à parte, com a contagem de quantos estão de cada lado.
        """
        atuaria = self._consolidado("atuaria")
        k = atuaria["compromissos"]
        self.assertIn("deficit", k)
        self.assertIn("superavit", k)
        self.assertNotIn("resultado", k)
        self.assertGreaterEqual(k["deficit"]["total"], 0)
        self.assertGreaterEqual(k["superavit"]["total"], 0)
        self.assertLessEqual(atuaria["com_deficit"] + atuaria["com_superavit"],
                             atuaria["com_draa"])

    def test_total_de_caixa_e_mensal_e_nao_extrapola_ninguem(self):
        """A janela do DIPR varia de ente para ente, e o total vive com isso.

        Somar meia série de um com a série cheia de outro daria um total que
        nenhum dos dois declarou. Exigir doze meses tampouco serve: no meio do
        exercício ninguém tem doze, e a publicação de 22/09/2026 saiu com um
        traço no lugar do número. O total soma o ritmo mensal de cada um — a
        própria janela dele, sem extrapolação.
        """
        caixa = self._consolidado("caixa")
        mensal = caixa["mensal"]
        self.assertNotIn("ano_completo", caixa,
                         "o total anual voltou, e ele zera no meio do exercício")
        # Todo RPPS com DIPR entra: ninguém fica de fora por ter janela curta.
        self.assertEqual(mensal["receita"]["entes"], caixa["com_dipr"])
        self.assertGreater(mensal["receita"]["total"], 0)

        # E o total é de fato mensal. A conferência usa a variante sem nenhum
        # filtro de qualidade — "0000" —, porque é a única em que o conjunto
        # publicado é o mesmo que o índice de entes.
        sem_filtro = self._json("consolidado.json")["variantes"]["0000"]["caixa"]
        soma_mensal = soma_do_periodo = 0.0
        parciais = 0
        for ente in self._json("entes.json"):
            c = (self._json(os.path.join("ente", ente["cnpj"] + ".json"))
                 .get("caixa") or {})
            if not c.get("disponivel") or not c.get("meses_declarados"):
                continue
            soma_mensal += c["total_receita"] / c["meses_declarados"]
            soma_do_periodo += c["total_receita"]
            if c["meses_declarados"] < 12:
                parciais += 1
        self.assertTrue(parciais, "o demo precisa de RPPS com série parcial")
        self.assertAlmostEqual(sem_filtro["mensal"]["receita"]["total"],
                               round(soma_mensal, 2), delta=1.0)
        self.assertLess(sem_filtro["mensal"]["receita"]["total"], soma_do_periodo)

        # O indicador percentual continua com todo mundo que declarou.
        self.assertEqual(caixa["indicadores"]["resultado_sobre_ingressos"]["n"],
                         caixa["com_dipr"])

    def test_consolidado_da_ficha_separa_regular_de_irregular(self):
        """A contagem tem de saber contar os dois lados.

        Um consolidado que dissesse "0 regulares" porque a amostra é uniforme
        não provaria nada sobre a leitura por pessoa.
        """
        ficha = self._consolidado("ficha")
        gov = ficha["governanca"]
        self.assertTrue(gov["regulares"], "falta RPPS com todos certificados")
        self.assertTrue(gov["irregulares"], "falta RPPS com alguém sem certificação")
        self.assertEqual(gov["regulares"] + gov["irregulares"], gov["avaliados"])
        # E a distribuição da massa existe e tem dispersão real.
        razao = ficha["indicadores"]["razao_ativos_inativos"]
        self.assertTrue(razao["disponivel"])
        self.assertLess(razao["p25"], razao["p75"])

    def test_norma_dos_investimentos_vem_de_um_lugar_so(self):
        """O painel não mantém tabela de limites — quem declara o teto de cada
        classe é a API. A norma aparece na tela só como referência, e de uma
        constante só, para não haver duas versões dela em telas diferentes."""
        from cadprev import build as b
        meta = self._json("meta.json")
        self.assertEqual(meta["norma_dos_investimentos"],
                         b.NORMA_DOS_INVESTIMENTOS)
        self.assertIn("CMN", meta["norma_dos_investimentos"])

    # ------------------------------------------ governança e certificação

    def test_certificacao_vencida_so_conta_sem_outra_vigente(self):
        """A API devolve uma linha por certificação, não por pessoa.

        É comum alguém ter uma CPA vencida ao lado de uma vigente, e nesse caso
        o requisito de regularidade está atendido. Ler linha a linha acusaria de
        irregular quem está em ordem.
        """
        achou_conviventes = achou_irregular = False
        for ente in self._json("entes.json"):
            g = self._json(
                os.path.join("ente", ente["cnpj"] + ".json")).get("governanca") or {}
            if not g.get("disponivel"):
                continue
            for pessoa in g["pessoas"]:
                vigentes = [c for c in pessoa["certificacoes"] if c["vigente"]]
                vencidas = [c for c in pessoa["certificacoes"] if not c["vigente"]]
                self.assertEqual(pessoa["regular"], bool(vigentes), pessoa["pessoa"])
                if vigentes and vencidas:
                    achou_conviventes = True
                    self.assertFalse(pessoa["so_vencidas"],
                                     "vencida ao lado de vigente não é achado")
                if pessoa["so_vencidas"]:
                    achou_irregular = True
                    self.assertFalse(vigentes)
            self.assertEqual(g["so_vencidas"],
                             sum(1 for p in g["pessoas"] if p["so_vencidas"]))
            self.assertEqual(g["regulares"],
                             sum(1 for p in g["pessoas"] if p["regular"]))
        self.assertTrue(achou_conviventes,
                        "o demo precisa de alguém com vencida e vigente juntas")
        self.assertTrue(achou_irregular,
                        "o demo precisa de alguém só com vencidas")

    def test_governanca_ignora_quem_ja_saiu(self):
        """Certificação vencida de quem deixou o colegiado não diz nada sobre a
        gestão de hoje."""
        from cadprev import build as b
        from cadprev.store import Store as _Store
        with _Store(self.banco) as store:
            g = b._montar_governanca(store, self._json("entes.json")[0]["cnpj"],
                                     hoje="2026-09-17")
        self.assertTrue(g["disponivel"])
        for pessoa in g["pessoas"]:
            self.assertIn("colegiado", pessoa)

    def test_ativos_fora_do_rol_tem_agregado_nacional(self):
        """Ativo que a fonte marca como não enquadrado não é teto estourado."""
        nacional = self._nacional("carteira-nacional.json")
        fora = nacional["fora_da_norma"]
        self.assertTrue(fora["entes"], "o demo precisa de ativo fora do rol")
        self.assertGreater(fora["valor"], 0)
        self.assertEqual(
            fora["valor"],
            round(sum(m["valor"] for m in fora["maiores"]), 2)
            if len(fora["maiores"]) == fora["entes"] else fora["valor"])
        for maior in fora["maiores"]:
            self.assertLessEqual(maior["perc_da_carteira"], 100.0)

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
            for bloco in amort["blocos"]:
                anos = [a["ano"] for a in bloco["anos"]]
                self.assertEqual(len(anos), len(set(anos)),
                                 "anos repetidos em " + ente["ente"])
        self.assertTrue(vistos, "o demo precisa gerar plano de amortização")

    def test_reenvio_nao_dobra_o_comparativo(self):
        for ente in self._entes():
            pe = self._ficha(ente["cnpj"]).get("projetado_executado") or {}
            if not pe.get("disponivel"):
                continue
            for bloco in pe["blocos"]:
                codigos = [i["codigo"] for i in bloco["itens"]]
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
            for bloco in pe["blocos"]:
                for item in bloco["itens"]:
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
                    (a["amortizacao"] or 0) < 0
                    for bloco in amort["blocos"] for a in bloco["anos"]):
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


class TestSiconfiNoIndice(unittest.TestCase):
    """A tabela de entes do Tesouro é referência, não fonte de entes."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="cadprev-siconfi-")
        cls.fixtures = os.path.join(cls.dir, "fx")
        demo.escrever(cls.fixtures)
        from cadprev import ingest, siconfi, fieldmap
        cls.banco = os.path.join(cls.dir, "t.sqlite3")
        cls.saida = os.path.join(cls.dir, "data")
        with Store(cls.banco) as store:
            ingest.ingerir_varios(
                Cliente(fixtures=cls.fixtures, pausa=0), store,
                ["RPPS_CRP", "RPPS_REGIME_PREVIDENCIARIO", "DAIR_CARTEIRA"])
            brutos = siconfi.Cliente(fixtures=cls.fixtures, pausa=0).entes()
            resolucao = fieldmap.resolver("SICONFI_ENTE", brutos[0].keys())
            store.gravar("SICONFI_ENTE",
                         (fieldmap.aplicar(resolucao, b) for b in brutos))
            build.construir(store, dir_saida=cls.saida, origem="demonstracao")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def _entes(self):
        with open(os.path.join(self.saida, "entes.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_tabela_de_referencia_nao_vira_ente_do_painel(self):
        """Ela cobre os 5.598 entes da federação; quatro o CADPREV não conhece.

        Uni-la ao índice acrescentaria fichas vazias e mexeria no denominador.
        """
        indice = self._entes()
        with Store(self.banco) as store:
            do_siconfi = store.consultar("SELECT COUNT(*) n FROM siconfi_ente")[0]["n"]
            do_crp = store.consultar(
                "SELECT COUNT(DISTINCT cnpj_ente) n FROM rpps_crp")[0]["n"]
        self.assertTrue(do_siconfi)
        self.assertEqual(len(indice), do_crp)

    def test_populacao_chega_ao_indice(self):
        comunidade = [e for e in self._entes() if e.get("populacao")]
        self.assertTrue(comunidade)

    def test_capital_vem_declarada(self):
        capitais = [e for e in self._entes() if e["esfera"] == "capital"]
        self.assertTrue(capitais)


class TestComposicaoContabil(unittest.TestCase):
    """O Anexo 04 do SICONFI e o confronto com a carteira do CADPREV."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="cadprev-contabil-")
        cls.fixtures = os.path.join(cls.dir, "fx")
        demo.escrever(cls.fixtures)
        from cadprev import ingest, siconfi, fieldmap
        cls.banco = os.path.join(cls.dir, "t.sqlite3")
        cls.saida = os.path.join(cls.dir, "data")
        with Store(cls.banco) as store:
            ingest.ingerir_varios(
                Cliente(fixtures=cls.fixtures, pausa=0), store,
                ["RPPS_CRP", "RPPS_REGIME_PREVIDENCIARIO", "DAIR_CARTEIRA",
                 "DRAA_VALORES_COMPROMISSOS"])
            brutos = siconfi.Cliente(fixtures=cls.fixtures, pausa=0).entes()
            resolucao = fieldmap.resolver("SICONFI_ENTE", brutos[0].keys())
            store.gravar("SICONFI_ENTE",
                         (fieldmap.aplicar(resolucao, b) for b in brutos))
            rreo = siconfi.ClienteRREO(fixtures=cls.fixtures, pausa=0)
            linhas = []
            for alvo in store.consultar(
                    "SELECT cnpj_ente, cod_ibge, esfera_siconfi FROM siconfi_ente"):
                itens = rreo.anexo_rpps(alvo["cod_ibge"], alvo["esfera_siconfi"],
                                        demo.ANO, 3)
                for item in itens:
                    item["cnpj_ente"] = alvo["cnpj_ente"]
                linhas.extend(itens)
            resolucao = fieldmap.resolver("SICONFI_RREO", linhas[0].keys())
            store.gravar("SICONFI_RREO",
                         (fieldmap.aplicar(resolucao, l) for l in linhas))
            # O balanço patrimonial é anual e fecha no exercício anterior ao do
            # DRAA — é esse par que compara a mesma data.
            dca = siconfi.ClienteDCA(fixtures=cls.fixtures, pausa=0)
            do_balanco = []
            for alvo in store.consultar(
                    "SELECT cnpj_ente, cod_ibge FROM siconfi_ente"):
                itens = dca.balanco(alvo["cod_ibge"], demo.ANO - 1)
                for item in itens:
                    item["cnpj_ente"] = alvo["cnpj_ente"]
                do_balanco.extend(itens)
            resolucao = fieldmap.resolver("SICONFI_DCA", do_balanco[0].keys())
            store.gravar("SICONFI_DCA",
                         (fieldmap.aplicar(resolucao, l) for l in do_balanco))
            build.construir(store, dir_saida=cls.saida, origem="demonstracao")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def _fichas(self):
        with open(os.path.join(self.saida, "entes.json"), encoding="utf-8") as fh:
            indice = json.load(fh)
        for ente in indice:
            caminho = os.path.join(self.saida, "ente", ente["cnpj"] + ".json")
            with open(caminho, encoding="utf-8") as fh:
                yield json.load(fh)

    def test_amostra_e_recortada_por_ente(self):
        """Sem o recorte, todo ente receberia as linhas do mesmo município — e o
        confronto entre fontes compararia coisas de RPPS diferentes."""
        totais = set()
        for ficha in self._fichas():
            c = ficha.get("contabil") or {}
            if c.get("disponivel"):
                totais.add(c["total"])
        self.assertGreater(len(totais), 1)

    def test_fundos_com_saldo_somam_o_total(self):
        """Só entra na soma o fundo que declarou saldo — e a soma é o total."""
        vistos = 0
        for ficha in self._fichas():
            c = ficha.get("contabil") or {}
            if not c.get("disponivel") or not c.get("com_saldo"):
                continue
            vistos += 1
            declarados = [f for f in c["fundos"] if f["recursos"] is not None]
            self.assertAlmostEqual(
                sum(f["recursos"] for f in declarados), c["total"], places=2)
            self.assertAlmostEqual(
                sum(f["perc"] for f in declarados), 100.0, places=1)
        self.assertTrue(vistos)

    def test_confronto_compara_as_duas_fontes(self):
        for ficha in self._fichas():
            c = ficha.get("contabil") or {}
            confronto = c.get("confronto")
            if not confronto:
                continue
            carteira = (ficha.get("carteira") or {}).get("total")
            self.assertAlmostEqual(confronto["cadprev"], carteira, places=2)
            self.assertAlmostEqual(
                confronto["diferenca"],
                confronto["siconfi"] - confronto["cadprev"], places=2)

    def test_divergencia_grande_existe_na_amostra(self):
        """Sem um caso fora da faixa, o aviso da tela nunca seria exercitado."""
        grandes = [f for f in self._fichas()
                   if abs((((f.get("contabil") or {}).get("confronto") or {})
                           .get("perc")) or 0) > 5]
        self.assertTrue(grandes)

    def test_ausencia_de_saldo_nao_vira_zero(self):
        """Em 17/09/2026, 278 dos 1.712 entes com Anexo 04 entregavam receitas
        e despesas sem o saldo das aplicações. Somar `inv or 0` acusava cada um
        deles de 100% de divergência contra a carteira do CADPREV."""
        achou = False
        for ficha in self._fichas():
            c = ficha.get("contabil") or {}
            if not c.get("disponivel") or c.get("com_saldo"):
                continue
            achou = True
            self.assertIsNone(c["total"])
            self.assertIsNone(c.get("confronto"))
            self.assertTrue(any(f["receitas"] is not None for f in c["fundos"]))
        self.assertTrue(achou, "o demo precisa conter um ente sem saldo")

    def test_soma_parcial_nao_e_confrontada(self):
        """Fundo que movimenta receita sem declarar saldo é buraco no total."""
        achou = False
        for ficha in self._fichas():
            c = ficha.get("contabil") or {}
            if not c.get("disponivel") or not c.get("com_saldo"):
                continue
            if c.get("saldo_completo") or c.get("saldo_negativo"):
                continue  # o saldo negativo é outro caso, com teste próprio
            achou = True
            self.assertIsNone(c.get("confronto"))
            self.assertTrue(any(f["recursos"] is None and f["receitas"] is not None
                                for f in c["fundos"]))
        self.assertTrue(achou, "o demo precisa conter um ente com saldo parcial")

    def test_provisao_contabil_usa_o_total_da_fonte(self):
        """As contas 2.2.7.2.2 são redutoras, publicadas com sinal positivo e
        fora do total. Somar componentes daria um passivo que o balanço não
        reconhece — em Vitória, R$ 4,8 bi a mais sobre R$ 5,66 bi."""
        from cadprev.store import Store as _Store
        with _Store(self.banco) as store:
            cruas = [dict(l) for l in store.consultar(
                "SELECT cnpj_ente, cod_conta, valor FROM siconfi_dca "
                "WHERE cod_conta LIKE 'P2.2.7.2%'")]
        por_ente = {}
        for linha in cruas:
            por_ente.setdefault(linha["cnpj_ente"], {})[
                linha["cod_conta"]] = linha["valor"]

        com_redutora = 0
        for ficha in self._fichas():
            c = ficha.get("contabil_anual") or {}
            if not c.get("disponivel") or c.get("provisao") is None:
                continue
            contas = por_ente.get(ficha["cnpj"]) or {}
            # O valor publicado é o da conta de total, exatamente.
            self.assertAlmostEqual(c["provisao"], contas["P2.2.7.2.0.00.00"],
                                   places=2)
            redutoras = {k: v for k, v in contas.items()
                         if k.startswith("P2.2.7.2.2") and v is not None}
            if not redutoras:
                continue
            com_redutora += 1
            # E não é a soma cega de todas as linhas 2.2.7.2: as redutoras são
            # publicadas com sinal positivo e ficam fora do total.
            soma_cega = sum(v for k, v in contas.items()
                            if v is not None and k != "P2.2.7.2.0.00.00")
            self.assertNotAlmostEqual(c["provisao"], soma_cega, places=2)
        self.assertTrue(com_redutora,
                        "o demo precisa de ente com conta redutora")

    def test_confronto_atuarial_so_no_par_de_mesma_data(self):
        """O DRAA de N descreve 31/12 de N−1; o balanço de N fecha em 31/12 de
        N. Comparar DRAA(N) com DCA(N) subtrairia avaliações de datas
        diferentes, e a diferença mediria o tempo."""
        achou = False
        for ficha in self._fichas():
            c = ficha.get("contabil_anual") or {}
            confronto = c.get("confronto")
            if not confronto:
                continue
            achou = True
            esperado = confronto["exercicio_draa"] == confronto["exercicio_dca"] + 1
            self.assertEqual(confronto["alinhado"], esperado)
            if not confronto["alinhado"]:
                self.assertIsNone(confronto["diferenca"])
                self.assertIsNone(confronto["perc"])
            else:
                self.assertAlmostEqual(
                    confronto["diferenca"],
                    confronto["contabil"] - confronto["atuarial"], places=2)
        self.assertTrue(achou, "o demo precisa de ente com os dois lados")

    def test_provisao_negativa_nao_vira_razao(self):
        """Provisão negativa não é passivo menor.

        Medido em 22/09/2026 sobre 198 entes com balanço: dois casos —
        Goianésia/GO com −R$ 105,4 mi e Morrinhos/GO com −R$ 15,6 mi. O número
        é declarado e fica na tela; o que não existe é a razão contra uma
        avaliação atuarial positiva.
        """
        achou = False
        for ficha in self._fichas():
            c = ficha.get("contabil_anual") or {}
            if not c.get("provisao_negativa"):
                continue
            achou = True
            self.assertLess(c["provisao"], 0)
            self.assertIsNone(c.get("confronto"))
        self.assertTrue(achou, "o demo precisa de ente com provisão negativa")

    def test_balanco_sem_conta_de_provisao_nao_vira_zero(self):
        """Entregar o balanço sem a conta 2.2.7.2 é diferente de declarar zero:
        numa amostra de 15 RPPS em 22/09/2026, um não a trazia."""
        achou = False
        for ficha in self._fichas():
            c = ficha.get("contabil_anual") or {}
            if not c.get("disponivel") or c.get("provisao") is not None:
                continue
            achou = True
            self.assertIsNone(c.get("confronto"),
                              "sem provisão declarada não há o que confrontar")
        self.assertTrue(achou,
                        "o demo precisa de ente que entrega o balanço sem a conta")

    def test_saldo_negativo_sai_do_confronto(self):
        """Descoberto bancário é número legítimo e não é carteira.

        Em 17/09/2026, 154 dos 1.432 entes confrontáveis traziam ao menos uma
        conta de saldo negativa — quase todas de caixa. Somá-la à carteira e
        dividir por esse total produz divergência calculada sobre denominador
        negativo: Igarassu/PE aparecia com −130% contra o CADPREV.
        """
        achou = False
        for ente in self._fichas():
            contabil = ente.get("contabil") or {}
            if not contabil.get("saldo_negativo"):
                continue
            achou = True
            self.assertIsNone(contabil.get("confronto"),
                              "saldo negativo não pode virar divergência")
            self.assertTrue(any((f.get("investimentos") or 0) < 0
                                or (f.get("caixa") or 0) < 0
                                for f in contabil["fundos"]))
        self.assertTrue(achou, "o demo precisa de um ente com saldo negativo")

    def test_distribuicao_nacional_da_divergencia(self):
        with open(os.path.join(self.saida, "qualidade.json"), encoding="utf-8") as fh:
            dv = json.load(fh)["divergencia_entre_fontes"]
        self.assertTrue(dv["disponivel"])
        # As três razões de não confrontar, mais os confrontados, fecham o
        # universo. Uma razão que não aparecesse aqui viraria divergência.
        self.assertEqual(
            dv["com_anexo"],
            dv["sem_saldo"] + dv["saldo_parcial"] + dv["saldo_negativo"]
            + dv["confrontados"])
        self.assertLessEqual(dv["ate_1"], dv["ate_5"])
        self.assertEqual(dv["ate_5"] + dv["acima_5"], dv["confrontados"])


class TestMassaMilitar(unittest.TestCase):
    """Civil e militar são massas separadas, e só os Estados têm a segunda.

    Os números vêm da base nacional de 17/09/2026: massa militar em 26 dos 27
    governos estaduais, em nenhum município, e de 14% a 39% da população
    declarada onde existe.
    """

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="cadprev-militar-")
        fixtures = os.path.join(cls.dir, "fx")
        demo.escrever(fixtures)
        from cadprev import ingest, siconfi, fieldmap
        cls.saida = os.path.join(cls.dir, "data")
        cliente = Cliente(fixtures=fixtures, pausa=0)
        with Store(os.path.join(cls.dir, "t.sqlite3")) as store:
            ingest.ingerir_varios(cliente, store, [
                "RPPS_CRP", "RPPS_REGIME_PREVIDENCIARIO", "DAIR_CARTEIRA",
                "DIPR", "DRAA_ESTATISTICA", "DRAA_VALORES_COMPROMISSOS",
                "DRAA_FLUXO_ATUARIAL", "DRAA_PLANO_CUSTEIO",
                "DRAA_COMPARATIVO_RECEITA", "DRAA_PLANO_AMORTIZACAO"])
            # O SICONFI é outra API, com outro envelope: o bloco militar do
            # Anexo 04 só existe lá.
            brutos = siconfi.Cliente(fixtures=fixtures, pausa=0).entes()
            resolucao = fieldmap.resolver("SICONFI_ENTE", brutos[0].keys())
            store.gravar("SICONFI_ENTE",
                         (fieldmap.aplicar(resolucao, b) for b in brutos))
            rreo = siconfi.ClienteRREO(fixtures=fixtures, pausa=0)
            linhas = []
            for alvo in store.consultar(
                    "SELECT cnpj_ente, cod_ibge, esfera_siconfi FROM siconfi_ente"):
                itens = rreo.anexo_rpps(alvo["cod_ibge"], alvo["esfera_siconfi"],
                                        demo.ANO, 3)
                for item in itens:
                    item["cnpj_ente"] = alvo["cnpj_ente"]
                linhas.extend(itens)
            resolucao = fieldmap.resolver("SICONFI_RREO", linhas[0].keys())
            store.gravar("SICONFI_RREO",
                         (fieldmap.aplicar(resolucao, l) for l in linhas))
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

    def _nacional(self, nome):
        from cadprev import qualidade
        with open(os.path.join(self.saida, nome), encoding="utf-8") as fh:
            return json.load(fh)["variantes"][qualidade.chave_padrao()]

    def test_so_estados_tem_massa_militar(self):
        estaduais = militares = 0
        for ente in self._entes():
            est = self._ficha(ente["cnpj"]).get("estatistica") or {}
            if not est.get("disponivel"):
                continue
            if ente["esfera"] == "estadual":
                estaduais += 1
            if est.get("tem_militar"):
                militares += 1
                self.assertEqual(
                    ente["esfera"], "estadual",
                    "município não tem militar: " + ente["ente"])
        self.assertTrue(estaduais and militares)

    def test_militar_usa_a_nomenclatura_do_regime_e_guarda_a_da_fonte(self):
        """O militar não se aposenta: passa à reserva e depois à reforma.

        A troca de termo é visível — o rótulo do regime na tela, o termo do
        CADPREV ao lado —, porque uma substituição silenciosa não se confere.
        """
        achou = False
        for ente in self._entes():
            est = self._ficha(ente["cnpj"]).get("estatistica") or {}
            if not est.get("tem_militar"):
                continue
            bloco = next(b for b in est["massas"] if b["militar"])
            rotulos = {g["rotulo"]: g["fonte"] for g in bloco["grupos"]}
            self.assertIn("Reserva e reforma", rotulos)
            self.assertNotIn("Aposentados", rotulos)
            self.assertEqual(rotulos["Reserva e reforma"],
                             "MILITARES - APOSENTADOS")
            achou = True
        self.assertTrue(achou)

    def test_as_duas_massas_nao_se_somam_num_grupo_so(self):
        """Antes desta separação os militares caíam num balde único.

        ``tp_populacao`` diz sempre "Militares", então agrupar por ele juntava
        ativos, reserva e pensionistas num número sem significado — e deixava
        os três fora de ativos e de inativos.
        """
        for ente in self._entes():
            est = self._ficha(ente["cnpj"]).get("estatistica") or {}
            if not est.get("tem_militar"):
                continue
            mil = next(b for b in est["massas"] if b["militar"])
            civ = next(b for b in est["massas"] if not b["militar"])
            self.assertEqual(len(mil["grupos"]), 3)
            self.assertTrue(mil["ativos"] and mil["inativos"]
                            and mil["pensionistas"])
            # O total do ente é a soma das duas massas, e nenhuma delas some.
            self.assertEqual(est["ativos"], mil["ativos"] + civ["ativos"])
            self.assertEqual(est["inativos"],
                             mil["beneficiarios"] + civ["beneficiarios"])
            self.assertGreater(est["ativos"], civ["ativos"])

    def test_um_plano_de_amortizacao_por_massa(self):
        """Somar as duas curvas produz um saldo que não existe em nenhuma."""
        achou = False
        for ente in self._entes():
            amort = self._ficha(ente["cnpj"]).get("amortizacao") or {}
            if not amort.get("tem_militar"):
                continue
            achou = True
            mil = next(b for b in amort["blocos"] if b["militar"])
            civ = next(b for b in amort["blocos"] if not b["militar"])
            self.assertNotEqual(mil["saldo_inicial"], civ["saldo_inicial"])
            for bloco in amort["blocos"]:
                anos = [a["ano"] for a in bloco["anos"]]
                self.assertEqual(len(anos), len(set(anos)))
        self.assertTrue(achou, "o demo precisa ter plano de amortização militar")

    def test_uma_tabela_de_fluxos_por_massa(self):
        achou = False
        for ente in self._entes():
            pe = self._ficha(ente["cnpj"]).get("projetado_executado") or {}
            if not pe.get("tem_militar"):
                continue
            achou = True
            rotulos = [b["rotulo"] for b in pe["blocos"]]
            self.assertEqual(len(rotulos), len(set(rotulos)))
            self.assertIn("Previdenciário · militar", rotulos)
        self.assertTrue(achou)

    def test_comparativo_militar_so_existe_onde_ha_massa_militar(self):
        """Município não devolve zero neste indicador: devolve indefinido.

        Zero seria lido como "nenhum militar na ativa para muitos na reserva",
        que é o pior resultado possível — e ele não tem militar nenhum.
        """
        with open(os.path.join(self.saida, "benchmark.json"),
                  encoding="utf-8") as fh:
            b = json.load(fh)
        self.assertIn("razao_militar", [i["chave"] for i in b["indicadores"]])
        com, sem = 0, 0
        for cnpj, rpps in b["rpps"].items():
            valor = rpps["valores"].get("razao_militar")
            est = self._ficha(cnpj).get("estatistica") or {}
            if est.get("tem_militar"):
                self.assertIsNotNone(valor)
                com += 1
            else:
                self.assertIsNone(valor)
                sem += 1
        self.assertTrue(com and sem)

    def test_grupo_sem_estados_nao_ganha_referencia_militar(self):
        """A regra dos três declarantes já basta para manter o município fora.

        Não é preciso uma exceção para militares: um grupo de municípios não
        tem três valores definidos, então não produz mediana nenhuma.
        """
        from cadprev import qualidade
        with open(os.path.join(self.saida, "benchmark.json"),
                  encoding="utf-8") as fh:
            grupos_ = json.load(fh)["grupos"]["variantes"][qualidade.chave_padrao()]
        with_ = [g["estatisticas"].get("razao_militar")
                 for g in grupos_["porte"].values()]
        self.assertTrue(any(v is not None for v in with_))
        self.assertTrue(any(v is None for v in with_))

    def test_painel_nacional_militar_so_tem_estados(self):
        m = self._nacional("militar.json")
        self.assertTrue(m["disponivel"])
        self.assertTrue(m["estados_com_pessoas"])
        esferas = {e["cnpj"]: e for e in self._entes()}
        for ficha in m["entes"]:
            self.assertEqual(esferas[ficha["cnpj"]]["esfera"], "estadual")
        self.assertEqual(m["ativos"], sum(e["ativos"] for e in m["entes"]))
        # A razão nacional é a do conjunto, não a média das razões.
        beneficiarios = sum(e["beneficiarios"] for e in m["entes"])
        self.assertAlmostEqual(m["razao_ativos_inativos"],
                               round(m["ativos"] / beneficiarios, 2), places=2)

    def test_ausencia_de_bloco_militar_no_rreo_nao_vira_zero(self):
        """Estado sem a linha no Anexo 04 fica nomeado, não zerado."""
        m = self._nacional("militar.json")
        self.assertTrue(m["sem_rreo"], "o demo precisa de um Estado sem o bloco")
        for ficha in m["entes"]:
            if ficha["uf"] in m["sem_rreo"]:
                self.assertIsNone(ficha["contribuicoes"])
                self.assertIsNone(ficha["despesas"])

    def test_fundo_militar_zero_declarado_nao_e_ausencia(self):
        """Zero aqui é o que a lei diz, e a fonte declara — não uma lacuna.

        Em 17/09/2026 nenhum dos 26 Estados com massa militar omitia o item
        500000: todos declaravam um valor, e 14 declaravam exatamente zero. O
        sistema de proteção social dos militares é de repartição, custeado pelo
        tesouro estadual; só o Amapá (31,5%) e Roraima (30,1%) têm cobertura
        relevante, e o Rio Grande do Sul começa a formar a dele (5,1%).
        """
        m = self._nacional("militar.json")
        self.assertIn("com_fundo", m)
        self.assertTrue(m["declararam_zero"],
                        "o demo precisa de Estado que declara zero")
        self.assertTrue(m["com_fundo"], "o demo precisa de Estado com fundo")
        for ficha in m["entes"]:
            if not ficha["pessoas"]:
                continue
            # Declarar zero e não declarar são estados distintos, e nenhum dos
            # dois vira o outro.
            if ficha["declarou_zero"]:
                self.assertEqual(ficha["ativos_garantidores"], 0)
                self.assertFalse(ficha["declara_fundo"])
            if ficha["ativos_garantidores"] is None:
                self.assertIsNone(ficha["cobertura"])
                self.assertIn(ficha["uf"], m["sem_declaracao_de_fundo"])

    def test_cobertura_militar_so_para_quem_tem_massa_militar(self):
        with open(os.path.join(self.saida, "benchmark.json"),
                  encoding="utf-8") as fh:
            b = json.load(fh)
        self.assertIn("cobertura_militar", [i["chave"] for i in b["indicadores"]])
        for cnpj, rpps in b["rpps"].items():
            atuaria = self._ficha(cnpj).get("atuaria") or {}
            tem = any(x.get("militar") for x in atuaria.get("blocos") or [])
            if not tem:
                self.assertIsNone(rpps["valores"].get("cobertura_militar"))

    def test_atuaria_separa_os_fundos(self):
        """Somar avaliações de fundos diferentes produz um resultado que não é
        de nenhum deles — e a militar não tem contribuição patronal."""
        achou = False
        for ente in self._entes():
            atuaria = self._ficha(ente["cnpj"]).get("atuaria") or {}
            if not atuaria.get("tem_militar"):
                continue
            achou = True
            mil = next(b for b in atuaria["blocos"] if b["militar"])
            civ = next(b for b in atuaria["blocos"] if not b["militar"])
            self.assertNotEqual(mil["resultado"]["provisoes"],
                                civ["resultado"]["provisoes"])
            # sem linha de ente no custeio militar
            sujeitos = [c["rotulo"].lower() for c in mil["custeio"]]
            self.assertFalse([x for x in sujeitos if "ente" in x],
                             "custeio militar não tem contribuição patronal")
            self.assertTrue([x for x in (c["rotulo"].lower() for c in civ["custeio"])
                             if "ente" in x])
        self.assertTrue(achou)

    def test_carteira_nao_e_atribuida_a_nenhuma_massa(self):
        """O DAIR não separa a carteira por massa, e o painel diz isso.

        Em 17/09/2026 o campo de plano vinha vazio nas 59.843 linhas da base
        nacional. Ratear o patrimônio entre civis e militares seria inventar
        uma repartição que nenhuma fonte declara.
        """
        m = self._nacional("militar.json")
        self.assertIn("nota_carteira", m)
        for ficha in m["entes"]:
            self.assertNotIn("patrimonio", ficha)
