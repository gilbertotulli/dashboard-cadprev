"""Pró-Gestão e ISP: as duas planilhas da SPREV que não vêm da API."""

import unittest

from cadprev import certificacao, planilhas


class TestNiveis(unittest.TestCase):
    """A escala do Pró-Gestão, que ordena e compara."""

    def test_a_escala_vai_de_acesso_a_quatro(self):
        self.assertEqual(certificacao.ordem_do_nivel("Acesso"), 0)
        self.assertEqual(certificacao.ordem_do_nivel("I"), 1)
        self.assertEqual(certificacao.ordem_do_nivel("IV"), 4)

    def test_vencida_nao_e_nivel(self):
        """A SPREV escreve "vencida" no lugar do nível de quem perdeu a
        certificação. Tratá-la como nível a poria na escala, entre "IV" e nada,
        e um RPPS sem certificação apareceria como certificado."""
        self.assertIsNone(certificacao.ordem_do_nivel("vencida"))
        self.assertIsNone(certificacao.ordem_do_nivel(""))
        self.assertIsNone(certificacao.ordem_do_nivel(None))

    def test_quem_so_aderiu_nao_e_certificado(self):
        """385 dos 709 entes da relação assinaram o termo e não certificaram.
        Aderir não é certificar, e ausência de nível não é nível zero."""
        so_aderiram = [c for c, l in certificacao.PROGESTAO.items()
                       if not l.get("nivel")]
        self.assertTrue(so_aderiram)
        registro = certificacao.pro_gestao(so_aderiram[0])
        self.assertIsNone(registro["nivel"])
        self.assertFalse(registro["certificado"])
        self.assertTrue(registro["aderiu"])


class TestRelacaoReal(unittest.TestCase):
    """O CSV versionado no repositório, convertido da planilha da SPREV."""

    def test_a_chave_e_o_cnpj_do_ente_e_e_unica(self):
        self.assertTrue(certificacao.PROGESTAO)
        for cnpj in certificacao.PROGESTAO:
            self.assertEqual(len(cnpj), 14, cnpj)

    def test_todos_os_niveis_da_escala_aparecem(self):
        """Se um nível sumisse da conversão, a coluna lida estaria errada —
        foi assim que a primeira versão leu "nível inicial", que guarda o
        histórico numa string só ("I-II-II") em vez do nível de hoje."""
        niveis = {l.get("nivel") for l in certificacao.PROGESTAO.values()}
        for esperado in certificacao.NIVEIS:
            self.assertIn(esperado, niveis, esperado)
        # E nenhum valor com hífen, que é a assinatura da coluna errada.
        self.assertFalse([n for n in niveis if n and "-" in n], niveis)

    def test_o_isp_classifica_de_a_a_d(self):
        notas = {l.get("isp") for l in certificacao.ISP.values()}
        self.assertEqual(notas - {None}, {"A", "B", "C", "D"})

    def test_a_fonte_diz_de_quando_e(self):
        """"SPREV" sozinho não diz se a relação é de setembro ou de três anos
        atrás, e as duas planilhas têm periodicidades diferentes."""
        self.assertRegex(certificacao.FONTE_PROGESTAO, r"\d{4}-\d{2}-\d{2}")
        self.assertRegex(certificacao.FONTE_ISP, r"\d{4}")


class TestConversao(unittest.TestCase):
    """A leitura das planilhas, que é onde as armadilhas estão."""

    def test_a_celula_com_varias_renovacoes_rende_a_mais_recente(self):
        """A planilha guarda renovações sucessivas numa célula só."""
        self.assertEqual(planilhas.ultima_data("26/01/2023-16/01/2026"),
                         "2026-01-16")
        self.assertEqual(planilhas.ultima_data("2025-12-09 00:00:00"),
                         "2025-12-09")
        self.assertEqual(planilhas.ultima_data(None), "")

    def test_cnpj_repetido_fica_com_a_linha_que_afirma_mais(self):
        """Sete CNPJ aparecem duas ou três vezes na planilha, e numa delas a
        linha nova é a adesão sem certificação. Deixar a última ganhar, que é
        o que um dict faz sozinho, tiraria a certificação de quem a tem.

        Nas duas ordens, de propósito: com as linhas numa ordem só, "fica a
        última" e "fica a que afirma mais" dão o mesmo resultado, e o teste
        passaria em cima do defeito — foi o que aconteceu aqui.
        """
        sem = {"cnpj_ente": "87612750000100", "nivel": "", "adesao": "2026-02-23"}
        com = {"cnpj_ente": "87612750000100", "nivel": "II", "adesao": "2025-02-20"}
        for ordem in ([sem, com], [com, sem]):
            linhas, repetidos = planilhas.consolidar_pro_gestao(iter(ordem))
            self.assertEqual(len(linhas), 1)
            self.assertEqual(linhas[0]["nivel"], "II",
                             "ordem {0}".format([l["nivel"] for l in ordem]))
            self.assertEqual(repetidos, ["87612750000100"])

    def test_entre_linhas_sem_nivel_fica_a_adesao_mais_recente(self):
        velha = {"cnpj_ente": "10408839000117", "nivel": "", "adesao": "2023-07-18"}
        nova = {"cnpj_ente": "10408839000117", "nivel": "", "adesao": "2026-07-16"}
        for ordem in ([velha, nova], [nova, velha]):
            linhas, _ = planilhas.consolidar_pro_gestao(iter(ordem))
            self.assertEqual(linhas[0]["adesao"], "2026-07-16",
                             "ordem {0}".format([l["adesao"] for l in ordem]))

    def test_tres_linhas_do_mesmo_cnpj_rendem_uma(self):
        """O CNPJ 46.634.218/0001-07 aparece três vezes, e numa delas com o
        nome de outro município. A chave é o CNPJ."""
        linhas, repetidos = planilhas.consolidar_pro_gestao(iter([
            {"cnpj_ente": "46634218000107", "ente": "Taquaritinga",
             "nivel": "", "adesao": "2024-12-17"},
            {"cnpj_ente": "46634218000107", "ente": "Taquarituba",
             "nivel": "II", "adesao": "2024-12-17"},
            {"cnpj_ente": "46634218000107", "ente": "Taquarituba",
             "nivel": "II", "adesao": "2021-05-03"},
        ]))
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["nivel"], "II")
        self.assertEqual(linhas[0]["adesao"], "2024-12-17")
        self.assertEqual(repetidos, ["46634218000107"])

    def test_o_link_escolhido_e_o_da_data_mais_alta(self):
        """A página do ISP guarda todas as edições desde 2017, e a mais nova
        fica em cima; a do Pró-Gestão tem uma só. Escolher por posição pegou o
        ISP de 2018 na primeira tentativa."""
        self.assertEqual(planilhas._ano_mais_alto("isp-2025-publicado-2025.xlsx"),
                         2025)
        self.assertGreater(planilhas._ano_mais_alto("resultado-isp-2025-1.xlsx"),
                           planilhas._ano_mais_alto("ISP_2018_resultado.xlsx"))

    #: O cabeçalho real da planilha de adesões, com as duas colunas de nível.
    CABECALHO_PROGESTAO = [
        "", "CNPJ", "ENTE FEDERATIVO", "UF", "DATA RECEBIMENTO TERMO DE ADESÃO",
        "DATA DO TERMO DE ADESÃO", "DATA DA CERTIFICAÇÃO INICIAL",
        "NÍVEL INICIAL", "DATA DA RENOVAÇÃO DA CERTIFICAÇÃO", "NÍVEL ATUAL",
        "ENTIDADE CERTICADORA"]

    def test_o_nivel_lido_e_o_atual_e_nao_o_historico(self):
        """A planilha tem duas colunas de nível. A de "nível inicial" guarda o
        histórico numa string só — "I-II-II" são três certificações sucessivas
        — e lê-la como nível daria "I-II-II" a quem hoje é nível II.

        O teste existe porque a troca é de uma palavra e não aparece em lugar
        nenhum: o CSV convertido já está certo, e o demo escreve o seu direto.
        """
        linha = ("", "46.634.218/0001-07", "Taquarituba", "SP",
                 "2024-12-17 00:00:00", "2024-12-17 00:00:00",
                 "2021-05-03 00:00:00", "I-II-II",
                 "26/01/2023-16/01/2026", "II", "ICQ BRASIL")
        lido = list(planilhas.mapear_pro_gestao(self.CABECALHO_PROGESTAO, [linha]))
        self.assertEqual(len(lido), 1)
        self.assertEqual(lido[0]["nivel"], "II")
        self.assertEqual(lido[0]["nivel_inicial"], "I-II-II")
        # E o CNPJ chega sem pontuação, com catorze dígitos.
        self.assertEqual(lido[0]["cnpj_ente"], "46634218000107")
        # A renovação múltipla vira a mais recente, que é a que vale.
        self.assertEqual(lido[0]["renovacao"], "2026-01-16")

    def test_linha_sem_cnpj_nao_vira_registro(self):
        """A planilha tem linhas de rodapé e separadores. Uma delas viraria um
        ente de CNPJ vazio, que casaria com nada e inflaria a contagem."""
        vazia = ("", None, "total", "", "", "", "", "", "", "", "")
        self.assertEqual(
            list(planilhas.mapear_pro_gestao(self.CABECALHO_PROGESTAO, [vazia])), [])

    def test_a_nota_do_isp_e_o_indicador_final_e_nao_um_eixo(self):
        """A aba RESULTADO tem três classificações por eixo e o indicador
        final, todos com as mesmas letras. Pegar um eixo no lugar da nota
        passaria despercebido: o valor continua sendo "A", "B", "C" ou "D"."""
        cab = ["ENTE", "CNPJ", "UF", "GRUPO", "SUBGRUPO",
               "INDICADOR DE REGULARIDADE", "INDICADOR ENVIO DE INFORMAÇÕES",
               "INDICADOR DE GESTÃO", "CLASSIFICAÇÃO EM GESTÃO E TRANSPARÊNCIA",
               "INDICADOR DE SUFICIÊNCIA FINANCEIRA",
               "INDICADOR ACUMULAÇÃO DE RECURSOS",
               "INDICADOR DE RESULTADO FINANCEIRO",
               "CLASSIFICAÇÃO EM FINANÇAS E LIQUIDEZ",
               "INDICADOR DE COBERTURA PREVIDENCIÁRIA",
               "INDICADOR DE SUSTENTABILIDADE",
               "INDICADOR DE REFORMA RPPS E VIGÊNCIA RPC",
               "CLASSIFICAÇÃO EM ATUÁRIA",
               "INDICADOR DE SITUAÇÃO PREVIDENCIÁRIA", "PERFIL ATUARIAL"]
        linha = ("ABADIA DE GOIÁS - GO", 1613940000119, "GO", "MÉDIO PORTE",
                 "MENOR MATURIDADE", "A", "B", "C", "B", "A", "A", "C", "D",
                 "C", "C", "B", "A", "C", "II")
        lido = list(planilhas.mapear_isp(cab, [linha], "2025"))[0]
        self.assertEqual(lido["isp"], "C")
        # Os três eixos têm valores distintos de propósito: se o mapeamento
        # deslizasse uma coluna, pelo menos um deles mudaria.
        self.assertEqual(lido["gestao"], "B")
        self.assertEqual(lido["financas"], "D")
        self.assertEqual(lido["atuaria"], "A")
        self.assertEqual(lido["exercicio"], "2025")
        # O CNPJ vem como número e perde o zero da frente na planilha.
        self.assertEqual(lido["cnpj_ente"], "01613940000119")

    def test_coluna_que_nao_existe_falha_alto(self):
        """Se a SPREV renomear uma coluna, a conversão para — em vez de gravar
        um CSV com a coluna em branco e o painel dizer que ninguém tem nível."""
        cab = [c for c in self.CABECALHO_PROGESTAO if c != "NÍVEL ATUAL"]
        with self.assertRaises(planilhas.ErroDaPlanilha):
            list(planilhas.mapear_pro_gestao(cab, []))

    def test_a_pagina_rende_o_arquivo_mais_novo_e_nao_o_preliminar(self):
        """A escolha é feita sobre o HTML da página, que guarda todas as
        edições. O preliminar do ISP convive com o final na mesma página e é
        expressamente substituído por ele."""
        html = (b'<a href="/a/ISP_2018_resultado.xlsx">2018</a>'
                b'<a href="/a/copy_of_ISP_2025DADOSPRELIMINARES.xlsx">previa</a>'
                b'<a href="/a/resultado-final-isp-2025-04_12_2025.xlsx">final</a>'
                b'<a href="/a/ISP_2024_resultado_final.xlsx">2024</a>')
        original = planilhas._baixar
        planilhas._baixar = lambda *a, **k: html
        try:
            achado = planilhas.endereco_da_planilha(
                "https://exemplo", evitar=planilhas._PRELIMINAR)
        finally:
            planilhas._baixar = original
        self.assertEqual(
            achado,
            "https://www.gov.br/a/resultado-final-isp-2025-04_12_2025.xlsx")

    def test_pagina_sem_planilha_falha_alto(self):
        """Devolver silêncio deixaria o CSV antigo no lugar, e o painel diria
        uma data que não é mais a da fonte."""
        original = planilhas._baixar
        planilhas._baixar = lambda *a, **k: b"<p>nada aqui</p>"
        try:
            with self.assertRaises(planilhas.ErroDaPlanilha):
                planilhas.endereco_da_planilha("https://exemplo")
        finally:
            planilhas._baixar = original

    def test_a_data_do_nome_do_arquivo_vira_iso(self):
        self.assertEqual(
            planilhas.data_do_nome("pro-gestao-rpps-relacao-de-entes-24-09-2026.xlsx"),
            "2026-09-24")
        self.assertEqual(
            planilhas.data_do_nome("resultado-final-isp-2025-_-publicado-em-04_12_2025-1.xlsx"),
            "2025-12-04")

    def test_o_exercicio_do_isp_vem_do_nome(self):
        """O ano-base não está em campo próprio dentro da planilha, e o ano de
        publicação aparece depois no nome — o ISP de 2025 foi publicado em
        dezembro de 2025, mas o de 2024 foi publicado em 2024 e revisado em
        2024 também. Vale o que vem logo depois de "isp"."""
        self.assertEqual(planilhas.ano_do_endereco(
            "resultado-final-isp-2025-_-publicado-em-04_12_2025-1.xlsx"), "2025")
        self.assertEqual(planilhas.ano_do_endereco(
            "ISP_2024_resultado_final_Revisado_29_11_2024.xlsx"), "2024")


if __name__ == "__main__":
    unittest.main()
