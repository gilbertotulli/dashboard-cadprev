"""Conjunto de demonstração — dados sintéticos, no formato da API.

Para que serve
--------------
O painel precisa abrir e funcionar para quem clona o repositório sem ter a API à
mão: para desenvolver a interface, para revisar um ajuste e para os testes. Este
módulo escreve amostras no **formato cru da API**, que depois passam pelo mesmo
caminho de ingestão dos dados reais — o pipeline é exercitado por inteiro, e não
contornado.

Nada aqui é dado real
---------------------
Os valores são gerados com semente fixa e ordem de grandeza plausível. Todo
build feito a partir deles carimba ``origem: demonstracao`` no ``meta.json``, e
a interface mostra aviso permanente. Um painel de dados públicos não pode deixar
dúvida sobre o que está na tela.

Nível de decomposição
---------------------
Por padrão, a carteira sai **sem** o campo de plano do ativo — que é exatamente
o que se sabe hoje sobre a API. O demo então roda no Nível B, mostrando a
interface no estado honesto. ``--nivel-a`` gera o campo para quem quiser ver a
decomposição de três vias antes de o Swagger ser lido.
"""

import json
import os
import random
from typing import Any, Dict, List

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_DEMO = os.path.join(RAIZ, "fixtures", "demo")

ANO = 2026
MES_DAIR = 8

_ENTES = [
    # (uf, nome, esfera esperada, porte relativo)
    ("SP", "Governo do Estado de São Paulo", 240.0),
    ("RJ", "Governo do Estado do Rio de Janeiro", 132.0),
    ("MG", "Governo do Estado de Minas Gerais", 98.0),
    ("RS", "Governo do Estado do Rio Grande do Sul", 61.0),
    ("BA", "Governo do Estado da Bahia", 44.0),
    ("ES", "Governo do Estado do Espírito Santo", 27.0),
    ("SP", "São Paulo", 72.0),
    ("RJ", "Rio de Janeiro", 38.0),
    ("MG", "Belo Horizonte", 21.0),
    ("ES", "Vitória", 9.4),
    ("PR", "Curitiba", 12.6),
    ("PE", "Recife", 7.1),
    ("SC", "Florianópolis", 5.2),
    ("GO", "Goiânia", 6.3),
    ("PA", "Belém", 3.8),
    ("AM", "Manaus", 4.1),
]

_MUNICIPIOS = [
    ("ES", "Vila Velha"), ("ES", "Serra"), ("ES", "Cariacica"),
    ("ES", "Linhares"), ("ES", "Colatina"), ("ES", "Guarapari"),
    ("RJ", "Quatis"), ("RJ", "Volta Redonda"), ("RJ", "Niterói"),
    ("SP", "Campinas"), ("SP", "Santos"), ("SP", "Sorocaba"),
    ("MG", "Contagem"), ("MG", "Uberlândia"), ("MG", "Juiz de Fora"),
    ("PR", "Londrina"), ("PR", "Maringá"), ("RS", "Caxias do Sul"),
    ("SC", "Joinville"), ("SC", "Blumenau"), ("BA", "Feira de Santana"),
    ("BA", "Vitória da Conquista"), ("PE", "Olinda"), ("CE", "Sobral"),
    ("MA", "Imperatriz"), ("PI", "Parnaíba"), ("PB", "Campina Grande"),
    ("RN", "Mossoró"), ("AL", "Arapiraca"), ("SE", "Lagarto"),
    ("GO", "Anápolis"), ("MT", "Rondonópolis"), ("MS", "Dourados"),
    ("PA", "Santarém"), ("AM", "Parintins"), ("RO", "Ji-Paraná"),
    ("AC", "Cruzeiro do Sul"), ("TO", "Gurupi"), ("AP", "Santana"),
    ("RR", "Rorainópolis"),
]

_SEGMENTOS = [
    ("Renda Fixa", 100.0, 0.74),
    ("Renda Variável", 30.0, 0.11),
    ("Investimentos Estruturados", 10.0, 0.045),
    ("Investimentos no Exterior", 10.0, 0.04),
    ("Fundos Imobiliários", 5.0, 0.02),
    ("Disponibilidades Financeiras", None, 0.045),
]

_HIPOTESES = [
    ("Taxa de juros atuarial", "5,04% a.a."),
    ("Crescimento real da remuneração", "1,00% a.a."),
    ("Rotatividade", "1,00% a.a."),
    ("Tábua de mortalidade geral", "IBGE 2023"),
    ("Tábua de mortalidade de inválidos", "IBGE 2023"),
    ("Tábua de entrada em invalidez", "Álvaro Vindas"),
]

_COMPROMISSOS = [
    ("1.1", "Provisões de benefícios concedidos", 1.00, 0.0),
    ("1.2", "Provisões de benefícios a conceder", 0.81, 0.35),
    ("2.1", "Contribuições futuras do ente", -0.63, -0.25),
    ("2.2", "Contribuições futuras dos segurados", -0.40, -0.16),
    ("3.1", "Ativos garantidores", -0.17, 0.0),
]


def _cnpj(indice: int) -> str:
    return "{:014d}".format(10000000000000 + indice * 137)


def gerar(nivel_a: bool = False, semente: int = 20260914) -> Dict[str, List[Dict[str, Any]]]:
    """Monta o conjunto completo, no formato cru da API."""
    rnd = random.Random(semente)
    entes = [(uf, nome, porte) for uf, nome, porte in _ENTES]
    entes += [(uf, nome, round(rnd.uniform(0.18, 4.2), 2))
              for uf, nome in _MUNICIPIOS]

    tabelas: Dict[str, List[Dict[str, Any]]] = {
        nome: [] for nome in (
            "RPPS_REGIME_PREVIDENCIARIO", "RPPS_CRP", "RPPS_ALIQUOTA", "DIPR",
            "DAIR_CARTEIRA", "DRAA_ESTATISTICA", "DRAA_SEGREGACAO_MASSA",
            "DRAA_FLUXO_ATUARIAL", "DRAA_VALORES_COMPROMISSOS",
            "DRAA_HIPOTESE_ATUARIAL", "DRAA_PLANO_CUSTEIO")
    }

    for indice, (uf, nome, porte) in enumerate(entes):
        cnpj = _cnpj(indice)
        ident = {"nr_cnpj_entidade": cnpj, "no_ente": nome, "sg_uf": uf}
        segregado = rnd.random() < 0.38
        patrimonio = porte * 1e9 if porte > 5 else porte * 1e9

        tabelas["RPPS_REGIME_PREVIDENCIARIO"].append(dict(ident, ds_regime="RPPS"))

        # CRP: a maioria válida, alguns vencidos, poucos por via judicial.
        sorteio = rnd.random()
        judicial = sorteio > 0.94
        vencido = 0.78 < sorteio <= 0.94
        validade = "{}-{:02d}-{:02d}".format(
            ANO - 1 if vencido else ANO + 1, rnd.randint(1, 12), rnd.randint(1, 28))
        tabelas["RPPS_CRP"].append(dict(
            ident, nr_crp="{:05d}/{}".format(indice + 1, ANO),
            dt_emissao="{}-0{}-15".format(ANO, rnd.randint(1, 9)),
            dt_validade=validade, st_judicial="S" if judicial else "N",
            ds_situacao="VENCIDO" if vencido else "VÁLIDO"))

        for sujeito, aliquota in (("Ativos", 14.0), ("Aposentados", 14.0),
                                  ("Pensionistas", 14.0),
                                  ("Ente", round(rnd.uniform(14, 24), 2))):
            tabelas["RPPS_ALIQUOTA"].append(dict(
                ident, ds_plano_segregacao="PREVIDENCIÁRIO",
                ds_sujeito_passivo=sujeito, vl_aliquota=aliquota,
                dt_inicio_vigencia="2024-01-01", dt_fim_vigencia=None))

        # DIPR: doze meses, com os picos de 13º em junho e dezembro.
        base_receita = patrimonio / 1e9 * 1.35
        base_despesa = base_receita * rnd.uniform(0.72, 0.98)
        for mes in range(1, 13):
            extra = 1.45 if mes in (6, 12) else 1.0
            deriva = 1 + (mes - 1) * 0.008
            tabelas["DIPR"].append(dict(
                ident, dt_ano=ANO, dt_mes=mes,
                ds_plano_segregacao="PREVIDENCIÁRIO",
                vl_total_receita=round(base_receita * extra * deriva * 1e6, 2),
                vl_total_despesa=round(base_despesa * extra * deriva * 1e6, 2),
                qt_nb_apos=int(porte * 47), qt_nb_pen=int(porte * 11),
                qt_nb_serv=int(porte * 138)))

        # DAIR: a carteira por segmento, com alguns ativos em cada.
        for segmento, limite, fatia in _SEGMENTOS:
            valor_segmento = patrimonio * fatia * rnd.uniform(0.85, 1.15)
            ativos = 1 if segmento == "Disponibilidades Financeiras" else rnd.randint(2, 4)
            for n in range(ativos):
                valor = valor_segmento / ativos
                registro = dict(
                    ident, dt_competencia="{:02d}/{}".format(MES_DAIR, ANO),
                    ds_segmento=segmento, ds_tipo_ativo="Tipo exemplo",
                    vl_limite_resol_cmn=limite,
                    no_ativo="{} — fundo exemplo {}".format(segmento, n + 1),
                    vl_total_atual=round(valor, 2),
                    pc_recursos_rpps=round(valor / patrimonio * 100, 2),
                    pc_pl_fundo=round(rnd.uniform(0.4, 16.0), 2))
                if nivel_a:
                    registro["ds_plano"] = (
                        "TAXA DE ADMINISTRAÇÃO" if n == 0 and rnd.random() < 0.12
                        else ("FINANCEIRO" if segregado and rnd.random() < 0.3
                              else "PREVIDENCIÁRIO"))
                tabelas["DAIR_CARTEIRA"].append(registro)

        tabelas["DRAA_ESTATISTICA"].append(dict(
            ident, dt_exercicio=ANO, qt_ativos=int(porte * 138),
            qt_aposentados=int(porte * 47), qt_pensionistas=int(porte * 11),
            qt_dependentes=int(porte * 196)))

        tabelas["DRAA_SEGREGACAO_MASSA"].append(dict(
            ident, dt_exercicio=ANO, st_segregacao="S" if segregado else "N",
            dt_segregacao="2012-01-01" if segregado else None))

        # Fluxo atuarial: receitas caindo, despesas em corcova.
        for passo, ano in enumerate(range(ANO, ANO + 76, 5)):
            t = passo / 15
            receitas = patrimonio / 1e9 * 42 * (1 + 0.25 * t - 1.15 * t ** 2)
            despesas = patrimonio / 1e9 * 30 * (1 + 3.4 * t - 3.1 * t ** 2)
            tabelas["DRAA_FLUXO_ATUARIAL"].append(dict(
                ident, dt_exercicio=ANO, dt_ano_projecao=ano,
                vl_receitas=round(max(receitas, 0) * 1e6, 2),
                vl_despesas=round(max(despesas, 0) * 1e6, 2)))

        deficit = patrimonio * rnd.uniform(1.8, 4.6)
        for codigo, descricao, fator_atual, fator_futuro in _COMPROMISSOS:
            tabelas["DRAA_VALORES_COMPROMISSOS"].append(dict(
                ident, dt_exercicio=ANO, cd_variavel=codigo,
                ds_variavel=descricao,
                vl_geracao_atual=round(deficit * fator_atual, 2),
                vl_geracao_futura=round(deficit * fator_futuro, 2)))

        for descricao, valor in _HIPOTESES:
            tabelas["DRAA_HIPOTESE_ATUARIAL"].append(dict(
                ident, dt_exercicio=ANO, ds_hipotese=descricao, vl_hipotese=valor))

        tabelas["DRAA_PLANO_CUSTEIO"].append(dict(
            ident, dt_exercicio=ANO, ds_custo="Plano previdenciário",
            vl_custo_normal=round(rnd.uniform(18, 32), 2),
            vl_custo_suplementar=round(rnd.uniform(0, 12), 2)))

    return tabelas


def escrever(destino: str = DIR_DEMO, nivel_a: bool = False) -> Dict[str, int]:
    """Grava as amostras no formato de página da API."""
    os.makedirs(destino, exist_ok=True)
    tabelas = gerar(nivel_a=nivel_a)
    contagem = {}
    for nome, registros in tabelas.items():
        caminho = os.path.join(destino, nome + ".json")
        with open(caminho, "w", encoding="utf-8") as fh:
            json.dump({"data": registros, "count": len(registros), "limit": 5000},
                      fh, ensure_ascii=False)
        contagem[nome] = len(registros)
    return contagem
