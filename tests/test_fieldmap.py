"""Resolução de campos e conversão de tipos."""

import unittest

from cadprev import fieldmap


class TestResolucao(unittest.TestCase):
    """A API pode usar qualquer uma das duas convenções observadas."""

    def test_convencao_com_prefixo(self):
        r = fieldmap.resolver("DAIR_CARTEIRA", [
            "nr_cnpj_entidade", "no_ente", "sg_uf", "dt_competencia",
            "ds_segmento", "vl_total_atual"])
        self.assertTrue(r.completa)
        self.assertEqual(r.encontrados["valor_total"], "vl_total_atual")
        self.assertEqual(r.encontrados["cnpj_ente"], "nr_cnpj_entidade")

    def test_convencao_dos_dados_abertos(self):
        r = fieldmap.resolver("DAIR_CARTEIRA", [
            "cnpj", "ente", "uf", "competencia", "segmento", "vlr_total_atual"])
        self.assertTrue(r.completa)
        self.assertEqual(r.encontrados["valor_total"], "vlr_total_atual")

    def test_ignora_caixa_e_separadores(self):
        r = fieldmap.resolver("DAIR_CARTEIRA", [
            "NrCnpjEntidade", "NoEnte", "SgUf", "DtCompetencia",
            "DsSegmento", "VlTotalAtual"])
        self.assertTrue(r.completa)
        self.assertEqual(r.encontrados["uf"], "SgUf")

    def test_chave_nao_mapeada_e_relatada(self):
        r = fieldmap.resolver("RPPS_CRP", [
            "nr_cnpj_entidade", "no_ente", "sg_uf", "nr_crp", "dt_emissao",
            "dt_validade", "st_judicial", "campo_novo_da_api"])
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
            "DAIR_CARTEIRA",
            ["nr_cnpj_entidade", "no_ente", "sg_uf", "dt_competencia",
             "ds_segmento", "vl_total_atual", "vl_inventado"],
            override={"DAIR_CARTEIRA": {"valor_total": "vl_inventado"}})
        self.assertEqual(r.encontrados["valor_total"], "vl_inventado")

    def test_plano_da_carteira_e_opcional(self):
        """É a pendência central: ausente, a ingestão segue em Nível B."""
        r = fieldmap.resolver("DAIR_CARTEIRA", [
            "nr_cnpj_entidade", "no_ente", "sg_uf", "dt_competencia",
            "ds_segmento", "vl_total_atual"])
        self.assertTrue(r.completa)
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

    def test_aplicar_preenche_opcionais_ausentes(self):
        r = fieldmap.resolver("RPPS_CRP", [
            "nr_cnpj_entidade", "no_ente", "sg_uf", "nr_crp", "dt_emissao",
            "dt_validade", "st_judicial"])
        saida = fieldmap.aplicar(r, {
            "nr_cnpj_entidade": "39.560.008/0001-48", "no_ente": "Quatis",
            "sg_uf": "RJ", "nr_crp": "02417/2026", "dt_emissao": "14/09/2026",
            "dt_validade": "14/03/2027", "st_judicial": "N"})
        self.assertEqual(saida["cnpj_ente"], "39560008000148")
        self.assertEqual(saida["validade"], "2027-03-14")
        self.assertFalse(saida["judicial"])
        self.assertIsNone(saida["situacao"])


if __name__ == "__main__":
    unittest.main()
