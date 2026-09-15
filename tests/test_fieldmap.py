"""Resolução de campos e conversão de tipos."""

import unittest

from cadprev import fieldmap


#: As chaves que a API devolve de verdade em DAIR_CARTEIRA, observadas em
#: 15/09/2026. A evidência completa está em docs/schema-observado/.
CHAVES_DAIR_REAIS = [
    "nr_cnpj_entidade", "sg_uf", "no_ente", "dt_mes_bimestre", "dt_ano",
    "no_segmento", "no_tipo_ativo", "pc_cmn", "id_ativo", "no_fundo",
    "qt_rpps", "vl_atual_ativo", "vl_total_atual", "pc_rpps",
    "vl_patrimonio", "pc_patrimonio",
]


class TestResolucao(unittest.TestCase):

    def test_chaves_reais_da_api(self):
        r = fieldmap.resolver("DAIR_CARTEIRA", CHAVES_DAIR_REAIS)
        self.assertTrue(r.completa, r.resumo())
        self.assertEqual(r.encontrados["valor_total"], "vl_total_atual")
        self.assertEqual(r.encontrados["segmento"], "no_segmento")
        self.assertEqual(r.encontrados["limite_cmn"], "pc_cmn")
        self.assertEqual(r.encontrados["nome_ativo"], "no_fundo")
        self.assertEqual(r.nao_mapeados, [])

    def test_convencao_dos_dados_abertos_ainda_resolve(self):
        """Os arquivos de dados abertos usam outros nomes para o mesmo campo."""
        r = fieldmap.resolver("DAIR_CARTEIRA", [
            "cnpj", "ente", "uf", "dt_ano", "dt_mes_bimestre", "ds_segmento",
            "vlr_total_atual"])
        self.assertTrue(r.completa, r.resumo())
        self.assertEqual(r.encontrados["valor_total"], "vlr_total_atual")

    def test_ignora_caixa_e_separadores(self):
        r = fieldmap.resolver("DAIR_CARTEIRA", [
            "NrCnpjEntidade", "NoEnte", "SgUf", "DtAno", "DtMesBimestre",
            "NoSegmento", "VlTotalAtual"])
        self.assertTrue(r.completa, r.resumo())
        self.assertEqual(r.encontrados["uf"], "SgUf")

    def test_chave_nao_mapeada_e_relatada(self):
        r = fieldmap.resolver("RPPS_CRP", [
            "nr_cnpj_entidade", "no_ente", "sg_uf", "nr_crp", "dt_emissao",
            "dt_validade", "tp_crp", "campo_novo_da_api"])
        self.assertIn("campo_novo_da_api", r.nao_mapeados)

    def test_falta_de_obrigatorio_lista_as_chaves_reais(self):
        """O erro precisa dizer o que veio, senão o diagnóstico é adivinhação."""
        chaves = ["algo", "outra_coisa"]
        r = fieldmap.resolver("DAIR_CARTEIRA", chaves)
        self.assertFalse(r.completa)
        with self.assertRaises(fieldmap.CampoNaoEncontrado) as ctx:
            fieldmap.exigir(r, chaves)
        mensagem = str(ctx.exception)
        self.assertIn("algo", mensagem)
        self.assertIn("outra_coisa", mensagem)
        self.assertIn("fieldmap.local.json", mensagem)

    def test_override_tem_precedencia(self):
        r = fieldmap.resolver(
            "DAIR_CARTEIRA", CHAVES_DAIR_REAIS + ["vl_inventado"],
            override={"DAIR_CARTEIRA": {"valor_total": "vl_inventado"}})
        self.assertEqual(r.encontrados["valor_total"], "vl_inventado")

    def test_api_real_nao_traz_o_plano_do_ativo(self):
        """A pergunta central do projeto, fixada como teste.

        Verificado contra a API em 15/09/2026: DAIR_CARTEIRA devolve dezesseis
        campos e nenhum identifica plano ou fundo. Se um dia passar a trazer,
        este teste falha — e é exatamente quando o projeto deve mudar de nível.
        """
        r = fieldmap.resolver("DAIR_CARTEIRA", CHAVES_DAIR_REAIS)
        self.assertTrue(r.completa, r.resumo())
        self.assertIn("plano", r.faltando_opcionais)


class TestConversao(unittest.TestCase):

    def test_decimal_no_formato_brasileiro(self):
        self.assertEqual(fieldmap.converter("1.234,56", "decimal"), 1234.56)
        self.assertEqual(fieldmap.converter("0,04", "decimal"), 0.04)

    def test_decimal_como_numero(self):
        self.assertEqual(fieldmap.converter(1234.56, "decimal"), 1234.56)

    def test_decimal_invalido_vira_nulo(self):
        self.assertIsNone(fieldmap.converter("n/d", "decimal"))

    def test_datas_em_varios_formatos(self):
        for entrada in ("2027-03-14", "14/03/2027", "2027-03-14T10:30:00"):
            self.assertEqual(fieldmap.converter(entrada, "data"), "2027-03-14")

    def test_cnpj_normalizado(self):
        self.assertEqual(fieldmap.converter("39.560.008/0001-48", "cnpj"),
                         "39560008000148")

    def test_booleano_em_portugues(self):
        self.assertTrue(fieldmap.converter("S", "booleano"))
        self.assertTrue(fieldmap.converter("Sim", "booleano"))
        self.assertFalse(fieldmap.converter("NÃO", "booleano"))
        self.assertIsNone(fieldmap.converter("talvez", "booleano"))

    def test_vazio_vira_nulo(self):
        self.assertIsNone(fieldmap.converter("", "texto"))
        self.assertIsNone(fieldmap.converter(None, "decimal"))

    def test_aplicar_converte_um_registro_real_do_crp(self):
        """Registro copiado de uma resposta real da API."""
        r = fieldmap.resolver("RPPS_CRP", [
            "nr_cnpj_entidade", "no_ente", "sg_uf", "nr_crp", "ds_situacao",
            "dt_emissao", "dt_validade", "tp_crp"])
        saida = fieldmap.aplicar(r, {
            "nr_cnpj_entidade": "01609408000128", "no_ente": "Marataízes",
            "sg_uf": "ES", "nr_crp": "980760-104543",
            "ds_situacao": "ADMINISTRATIVO", "dt_emissao": "09/04/2012",
            "dt_validade": "06/10/2012", "tp_crp": "VENCIDO"})
        self.assertEqual(saida["cnpj_ente"], "01609408000128")
        self.assertEqual(saida["emissao"], "2012-04-09")
        self.assertEqual(saida["validade"], "2012-10-06")
        self.assertEqual(saida["campo_situacao"], "ADMINISTRATIVO")
        self.assertEqual(saida["campo_tipo"], "VENCIDO")

    def test_data_com_hora_no_formato_da_api(self):
        """RPPS_ALIQUOTA devolve TIMESTAMP com milissegundos."""
        self.assertEqual(
            fieldmap.converter("1997-05-08 03:00:00.000", "data"), "1997-05-08")


if __name__ == "__main__":
    unittest.main()
