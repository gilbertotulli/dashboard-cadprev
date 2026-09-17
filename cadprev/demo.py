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

#: Segmentos e limites como a API os devolve (``no_segmento`` e ``pc_cmn``).
_SEGMENTOS = [
    ("Renda Fixa", 100, 0.74),
    ("Renda Variável", 30, 0.11),
    ("Investimentos Estruturados", 10, 0.045),
    ("Investimentos no Exterior", 10, 0.04),
    ("Fundos Imobiliários", 5, 0.02),
    ("Disponibilidades Financeiras", None, 0.045),
]

#: Valor de cota único, para que a aritmética do demo seja conferível a olho:
#: quantidade x cota tem de bater com o valor total, e é a violação dessa
#: identidade que revela o lançamento envenenado.
_COTA = 4.1571579040

#: Piso do patrimônio líquido dos fundos do catálogo. Compartilhar fundos entre
#: os entes é o que permite ao painel saber o tamanho de cada um: com um
#: declarante só não há consenso, e sem consenso não há régua.
#:
#: O PL declarado varia de declarante para declarante, como na fonte real — lá
#: o mesmo fundo aparece com valores que diferem em ordens de grandeza. O que
#: não varia é a relação: nenhum RPPS é dono de mais do que o fundo inteiro.
_PL_FUNDO = 5.2e8

#: O ente cuja carteira traz a cota com a vírgula seis casas fora do lugar,
#: reproduzindo Santo Afonso/MT na carga de 15/09/2026.
_ENTE_ENVENENADO = 3

#: Entes que pararam de entregar o DAIR no segundo mês do exercício.
_ENTES_DEFASADOS = frozenset({5, 11})

#: Entes que reenviaram o DRAA: a API devolve as duas versões convivendo, e
#: somá-las dobraria o saldo devedor. Em 17/09/2026 isso atingia 176 dos 1.652
#: entes com plano de amortização.
_ENTES_REENVIARAM = frozenset({1, 6, 17})

#: A submissão que foi substituída — anterior à válida, e que não pode entrar
#: em nenhuma soma.
_ENVIO_SUBSTITUIDO = "{}-03-30 09:00:00.000".format(ANO)

#: Entes com notificação da SPREV. O conjunto real é estreito: em 17/09/2026,
#: 770 itens em 222 entes, todos sobre segregação de massa.
_ENTES_NOTIFICADOS = frozenset({0, 4, 12, 20})

#: Ente cujo pagamento não cobre os juros nos primeiros anos, de modo que o
#: saldo devedor cresce em vez de amortizar.
_ENTES_SALDO_CRESCENTE = frozenset({0})

#: Situações, com as grafias que a fonte usa — inclusive "pendencia" sem acento.
_NOTIFICACOES = (
    ("Consistência - Segregação da Massa",
     "Resposta analisada. Item sem pendencia"),
    ("Alteração de Segregação de Massa - Parecer Prévio",
     "Notificacao respondida fora do prazo. Situacao irregular."),
    ("Implantação Segregação da Massa - Estudo Técnico",
     "Notificacao emitida. Aguardando resposta"),
)

#: Itens de fluxo comparados entre projetado e executado.
_FLUXOS_COMPARADOS = (
    (190000, "TOTAL DAS RECEITAS COM CONTRIBUIÇÕES E COMPENSAÇÃO", 1.0),
    (109001, "Base de Cálculo da Contribuição Normal", 2.4),
    (240000, "TOTAL DAS DESPESAS COM BENEFÍCIOS DO PLANO", 1.45),
    (215001, "Plano de Amortização do Déficit Atuarial", 0.32),
)


def _versoes(reenviou, envio_valido):
    """As submissões de um exercício: a substituída, quando houve, e a válida."""
    if reenviou:
        return ((_ENVIO_SUBSTITUIDO,
                 "Substituída Antes da Recepção dos Arquivos Digitalizados"),
                (envio_valido, "Documentos Digitalizados"))
    return ((envio_valido, "Documentos Digitalizados"),)


#: Entes cujo CRP venceu há mais de meio ano — irregularidade instalada, e não
#: renovação em curso. Sem um caso assim o filtro correspondente não teria o
#: que excluir em nenhum teste.
_ENTES_CRP_ANTIGO = frozenset({2, 9})

#: Entes que migraram para o RGPS: continuam no CRP, que é do ente federativo,
#: mas não têm RPPS. São 3.411 no país, e contá-los como RPPS inflava todo
#: denominador nacional.
_ENTES_SEM_RPPS = frozenset({7, 13, 19})

_ULTIMO_DIA = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
               7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def _fundo(segmento, n):
    """Identificação e nome de um fundo do catálogo compartilhado."""
    codigo = "{:03d}{:011d}".format(n + 1, abs(hash(segmento)) % 10**11)
    return codigo, "{} — fundo exemplo {}".format(segmento, n + 1)


#: Descrições exatamente como a API as devolve — o painel casa por texto.
_HIPOTESES = [
    ("Projeção da Taxa de Juros Real para o Exercício", "5.38"),
    ("Projeção da Taxa de Inflação de Longo Prazo", "4.00"),
    ("Projeção de Crescimento Real do Salário", "1.00"),
    ("Projeção de Crescimento Real dos Benefícios do Plano", "0.00"),
    ("Projeção da Taxa de Rotatividade", "1.00"),
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
    """Monta o conjunto completo, no formato cru da API.

    Os nomes e as formas seguem o que a API devolve de verdade — inclusive os
    formatos longos (uma linha por rubrica, por item de fluxo, por grupo
    populacional) e o histórico completo de CRP. Um demo em formato diferente
    do real não testaria nada do que importa.
    """
    rnd = random.Random(semente)
    entes = [(uf, nome, porte) for uf, nome, porte in _ENTES]
    entes += [(uf, nome, round(rnd.uniform(0.18, 4.2), 2))
              for uf, nome in _MUNICIPIOS]

    tabelas: Dict[str, List[Dict[str, Any]]] = {
        nome: [] for nome in (
            "RPPS_REGIME_PREVIDENCIARIO", "RPPS_CRP", "RPPS_ALIQUOTA", "DIPR",
            "DAIR_CARTEIRA", "DAIR_IDENTIFICACAO",
            "DRAA_ESTATISTICA", "DRAA_SEGREGACAO_MASSA",
            "DRAA_FLUXO_ATUARIAL", "DRAA_VALORES_COMPROMISSOS",
            "DRAA_HIPOTESE_ATUARIAL", "DRAA_PLANO_CUSTEIO",
            "DRAA_ENCAMINHAMENTO", "DRAA_NOTIFICACAO",
            "DRAA_COMPARATIVO_RECEITA", "DRAA_PLANO_AMORTIZACAO")
    }

    for indice, (uf, nome, porte) in enumerate(entes):
        cnpj = _cnpj(indice)
        ident = {"nr_cnpj_entidade": cnpj, "no_ente": nome, "sg_uf": uf}
        segregado = rnd.random() < 0.38
        patrimonio = porte * 1e9

        # Quem migrou para o RGPS tem duas vigências: o RPPS antigo e o regime
        # atual. É a mais recente que vale.
        sem_rpps = indice in _ENTES_SEM_RPPS
        tabelas["RPPS_REGIME_PREVIDENCIARIO"].append(dict(
            ident, tp_regime="RPPS", dt_inicio="1991-05-21 03:00:00.000",
            dt_fim=None, no_tipo_legislacao="LEI", nr_legislacao=str(1000 + indice)))
        if sem_rpps:
            tabelas["RPPS_REGIME_PREVIDENCIARIO"].append(dict(
                ident, tp_regime="RGPS", dt_inicio="2015-03-10 03:00:00.000",
                dt_fim=None, no_tipo_legislacao="LEI",
                nr_legislacao=str(2000 + indice)))

        # CRP: o endpoint devolve o histórico. Três emissões por ente, e a
        # situação da mais recente é o que o painel deve ler.
        crp_antigo = indice in _ENTES_CRP_ANTIGO
        for anos_atras in (2, 1, 0):
            vencido = anos_atras == 0 and (crp_antigo or rnd.random() > 0.82)
            judicial = anos_atras == 0 and not crp_antigo and rnd.random() > 0.94
            emissao = "{}-{:02d}-{:02d}".format(
                ANO - anos_atras, rnd.randint(1, 12), rnd.randint(1, 28))
            if anos_atras == 0 and crp_antigo:
                # Emitido no começo do exercício e vencido logo depois: em
                # setembro já são meses de irregularidade, não atraso de papel.
                emissao = "{}-01-15".format(ANO)
                validade = "{}-02-10".format(ANO)
            else:
                validade = "{}-{:02d}-{:02d}".format(
                    ANO - anos_atras + (0 if vencido else 1),
                    rnd.randint(1, 12), rnd.randint(1, 28))
            tabelas["RPPS_CRP"].append(dict(
                ident, nr_crp="{:06d}-{:06d}".format(indice + 1, rnd.randint(1, 999999)),
                dt_emissao=emissao, dt_validade=validade,
                # Os dois campos vêm trocados na API real; o demo reproduz isso.
                ds_situacao="JUDICIAL" if judicial else "ADMINISTRATIVO",
                tp_crp="VENCIDO" if vencido else "VÁLIDO"))

        for sujeito, aliquota in (("Ativos", 14.0), ("Aposentados", 14.0),
                                  ("Pensionistas", 14.0),
                                  ("Ente", round(rnd.uniform(14, 24), 2))):
            tabelas["RPPS_ALIQUOTA"].append(dict(
                ident, ds_plano_segregacao="Fundo em Capitalização",
                no_sujeito_passivo=sujeito, vl_aliquota="{:.2f}".format(aliquota),
                dt_inicio_vigencia="2024-01-01 03:00:00.000",
                dt_fim_vigencia=None, id_vigente="VIGENTE", tp_regime="RPPS"))

        # DIPR: uma linha por rubrica, por mês e por plano. Os ids abaixo de 33
        # são bases de cálculo — entram na amostra justamente para que o
        # pipeline continue tendo de excluí-los.
        folha = patrimonio / 1e9 * 3.1e6
        for mes in range(1, 13):
            extra = 1.45 if mes in (6, 12) else 1.0
            base = folha * extra
            tabelas["DIPR"].append(dict(
                ident, dt_ano=ANO, dt_mes=mes, no_plano="PREVIDENCIARIO",
                no_orgao="Prefeitura", id_rubrica=19, no_rubrica="PAT-SEG",
                te_rubrica="Patronal relativa aos servidores",
                vl_rubrica="{:.2f}".format(base)))
            tabelas["DIPR"].append(dict(
                ident, dt_ano=ANO, dt_mes=mes, no_plano="PREVIDENCIARIO",
                no_orgao="Prefeitura", id_rubrica=27, no_rubrica="SEG",
                te_rubrica="Dos servidores", vl_rubrica="{:.2f}".format(base)))
            for id_rub, sigla, fator in ((56, "PAT-SEG", 0.22), (64, "SEG", 0.14),
                                         (79, "ING-REND-APL", 0.09),
                                         (82, "UT-APO", 0.26), (83, "UT-PEN", 0.05),
                                         (96, "UT-DESP-ADM", 0.012)):
                tabelas["DIPR"].append(dict(
                    ident, dt_ano=ANO, dt_mes=mes, no_plano="PREVIDENCIARIO",
                    no_orgao="Prefeitura", id_rubrica=id_rub, no_rubrica=sigla,
                    te_rubrica=sigla, vl_rubrica="{:.2f}".format(base * fator)))

        # Os fundos são compartilhados entre os entes, como na realidade: os
        # mesmos BB e SICREDI aparecem em centenas de carteiras. Sem esse
        # compartilhamento não há consenso sobre o tamanho de cada fundo, e a
        # régua de lançamento impossível não teria contra o que comparar.
        for segmento, limite, fatia in _SEGMENTOS:
            valor_segmento = patrimonio * fatia * rnd.uniform(0.85, 1.15)
            ativos = 1 if segmento == "Disponibilidades Financeiras" else rnd.randint(2, 4)
            for n in range(ativos):
                valor = valor_segmento / ativos
                fundo_id, fundo_nome = _fundo(segmento, n)
                # Conta e caixa não têm PL; fundo tem, e é sempre maior que a
                # posição de um cotista só.
                fundo_pl = (None if segmento == "Disponibilidades Financeiras"
                            else max(_PL_FUNDO, valor * rnd.uniform(8, 300)))
                cotas = valor / _COTA
                registro = dict(
                    ident, dt_ano=ANO, dt_mes_bimestre=MES_DAIR,
                    no_segmento=segmento, no_tipo_ativo="Tipo exemplo",
                    pc_cmn=limite, id_ativo=fundo_id, no_fundo=fundo_nome,
                    qt_rpps="{:.10f}".format(cotas),
                    vl_atual_ativo="{:.10f}".format(_COTA),
                    vl_total_atual="{:.2f}".format(valor),
                    pc_rpps="{:.2f}".format(valor / patrimonio * 100),
                    vl_patrimonio="{:.2f}".format(fundo_pl) if fundo_pl else None,
                    pc_patrimonio="{:.2f}".format(rnd.uniform(0.4, 16.0)))
                # Um lançamento envenenado, reproduzindo o caso de Santo
                # Afonso/MT: a cota digitada com a vírgula seis casas à direita.
                if indice == _ENTE_ENVENENADO and segmento == "Renda Variável" and n == 0:
                    registro["vl_atual_ativo"] = "{:.10f}".format(_COTA * 1e6)
                    registro["vl_total_atual"] = "{:.2f}".format(valor * 1e6)
                    registro["pc_patrimonio"] = "1611016.66"
                if nivel_a:
                    registro["ds_plano"] = (
                        "TAXA DE ADMINISTRAÇÃO" if n == 0 and rnd.random() < 0.12
                        else ("FINANCEIRO" if segregado and rnd.random() < 0.3
                              else "PREVIDENCIARIO"))
                tabelas["DAIR_CARTEIRA"].append(registro)

        # DAIR_IDENTIFICACAO: o cabeçalho mensal da declaração. É dele que sai a
        # defasagem — quem parou de entregar não some da base, fica com a última
        # posição envelhecendo.
        ultimo_mes = 2 if indice in _ENTES_DEFASADOS else MES_DAIR
        for mes in range(1, ultimo_mes + 1):
            tabelas["DAIR_IDENTIFICACAO"].append(dict(
                ident, dt_ano=ANO, dt_mes=mes,
                dt_posicao="{}-{:02d}-{:02d} 03:00:00.000".format(
                    ANO, mes, _ULTIMO_DIA[mes]),
                dt_envio="{}-{:02d}-15 10:00:00.000".format(
                    ANO + (1 if mes == 12 else 0), 1 if mes == 12 else mes + 1),
                te_finalidade="ENCERRAMENTO_MES", te_justificativa=None,
                te_motivo_retificacao=None, te_descricao_retificacao=None,
                te_justicativa_retificacao=None))

        # DRAA_ESTATISTICA: uma linha por grupo populacional, contagem por sexo.
        for tipo, fator in (("Servidores", 138), ("Aposentados", 47),
                            ("Pensionistas", 11), ("Servidores Iminentes", 9)):
            total = int(porte * fator)
            tabelas["DRAA_ESTATISTICA"].append(dict(
                ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
                cd_populacao=1110100, tp_populacao=tipo,
                no_cat_populacao="DEMAIS SERVIDORES",
                qt_grupo_masc=total // 2, qt_grupo_fem=total - total // 2,
                vl_folha_mensal_masc=total // 2 * 3200.0,
                vl_folha_mensal_fem=(total - total // 2) * 3100.0,
                vl_idade_media_masc=54.2, vl_idade_media_fem=52.8))

        tabelas["DRAA_SEGREGACAO_MASSA"].append(dict(
            ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
            no_segregacao_massa=("Instituida neste Exercicio ou Mantida"
                                 if segregado else "Não Possui"),
            dt_ingresso_segurado="2012-01-01 00:00:00.000" if segregado else None,
            nr_norma_fundamento="1262",
            dt_norma_fundamento="2004-12-27 02:00:00.000"))

        # DRAA_FLUXO_ATUARIAL: itens de fluxo com um valor projetado cada,
        # incluindo a base de cálculo (109001) e os dois totais.
        receitas = patrimonio / 1e9 * 42e6
        despesas = patrimonio / 1e9 * 61e6
        for codigo, descricao, valor in (
                (109001, "Base de Cálculo da Contribuição Normal", receitas * 2.4),
                (121000, "Benefícios a Conceder - Contribuições do Ente", receitas * 0.6),
                (122000, "Benefícios a Conceder - Contribuições dos Segurados Ativos", receitas * 0.3),
                (111000, "Benefícios Concedidos - Contribuições dos Aposentados", receitas * 0.1),
                (190000, "TOTAL DAS RECEITAS COM CONTRIBUIÇÕES E COMPENSAÇÃO PREVIDENCIÁRIA", receitas),
                (211001, "Benefícios Concedidos - Encargos - Aposentadorias Programadas", despesas * 0.74),
                (215001, "Benefícios Concedidos - Encargos - Pensões Por Morte", despesas * 0.12),
                (221000, "Benefícios a Conceder - Encargos -  Aposentadorias Programadas", despesas * 0.14),
                (240000, "TOTAL  DAS DESPESAS COM BENEFÍCIOS DO PLANO", despesas)):
            tabelas["DRAA_FLUXO_ATUARIAL"].append(dict(
                ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
                nr_fluxo=codigo, no_fluxo=descricao, vl_projetado=round(valor, 2)))

        deficit = patrimonio * rnd.uniform(1.8, 4.6)
        for codigo, descricao, categoria, atual, futura in (
                (300000, "PROVISÃO MATEMÁTICA DOS BENEFÍCIOS CONCEDIDOS", "Titulo", 0, 0),
                (500000, "ATIVOS GARANTIDORES DOS COMPROMISSOS DO PLANO", "Resultado",
                 patrimonio, 0),
                (600100, "Déficit Atuarial", "Resultado", deficit, 0),
                (121000, "Benefícios a Conceder - Contribuições Futuras do Ente",
                 "Resultado", deficit * 0.35, deficit * 0.12),
                (211000, "Benefícios Concedidos - Encargos - Aposentadorias Programadas",
                 "Resultado", deficit * 0.9, 0)):
            tabelas["DRAA_VALORES_COMPROMISSOS"].append(dict(
                ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
                cd_demonstrativo=codigo, ds_item_resultado=descricao,
                no_categoria_demonstrativo=categoria,
                vl_geracao_atual="{:.2f}".format(atual),
                vl_geracao_futura="{:.2f}".format(futura) if futura else None))

        for descricao, valor in _HIPOTESES:
            tabelas["DRAA_HIPOTESE_ATUARIAL"].append(dict(
                ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
                cd_hipotese_demografica=10001,
                ds_hipotese_demografica=descricao, tp_unidade="PERCENTUAL",
                te_hipotese_demografica=valor,
                vl_perspectiva_longo_prazo=valor))

        for tipo, aliquota in (("Segurados Ativos", 14.0), ("Aposentados", 14.0),
                               ("Pensionistas", 14.0), ("Ente Federativo", 19.12),
                               ("Ente Federativo - Total", 22.0),
                               ("Taxa de Administração", 2.88)):
            tabelas["DRAA_PLANO_CUSTEIO"].append(dict(
                ident, dt_exercicio=ANO, tp_plano="Previdenciário", tp_massa="Civil",
                tp_contribuicao=tipo, vl_anual_base_calculo=folha * 12,
                vl_aliquota=aliquota, vl_contribuicao_esperada=folha * 12 * aliquota / 100,
                vl_aliquota_definida=aliquota,
                vl_contribuicao_definida=folha * 12 * aliquota / 100))

        # --- encaminhamento do DRAA, com reenvio para alguns ---
        envio_valido = "{}-04-{:02d} 10:12:00.000".format(ANO, rnd.randint(3, 28))
        reenviou = indice in _ENTES_REENVIARAM
        if reenviou:
            tabelas["DRAA_ENCAMINHAMENTO"].append(dict(
                ident, dt_exercicio=ANO, dt_envio=_ENVIO_SUBSTITUIDO,
                te_situacao="Substituída Antes da Recepção dos Arquivos Digitalizados"))
        tabelas["DRAA_ENCAMINHAMENTO"].append(dict(
            ident, dt_exercicio=ANO, dt_envio=envio_valido,
            te_situacao="Documentos Digitalizados"))

        # --- notificações da SPREV, nos três estados que a fonte usa ---
        if indice in _ENTES_NOTIFICADOS:
            for n, (item, situacao) in enumerate(_NOTIFICACOES):
                tabelas["DRAA_NOTIFICACAO"].append(dict(
                    ident, nr_notificacao="{:06d}.{:02d}/{}".format(
                        90000 + indice, n + 1, ANO - 1),
                    no_tipo_documento="DRAA", no_item_analise=item,
                    no_situacao_item_analise=situacao,
                    dt_notificao="{}-03-{:02d} 03:00:00.000".format(ANO - 1, 5 + n),
                    dt_preclusao="{}-04-{:02d} 03:00:00.000".format(ANO - 1, 5 + n),
                    dt_resposta=None, nr_prazo_resposta=30))

        # --- projetado contra executado; a diferença é projetado menos
        # executado, como na fonte, e não o contrário ---
        for codigo, descricao, base in _FLUXOS_COMPARADOS:
            projetado = receitas * base
            executado = projetado * rnd.uniform(0.55, 1.35)
            for quando, situacao in _versoes(reenviou, envio_valido):
                tabelas["DRAA_COMPARATIVO_RECEITA"].append(dict(
                    ident, dt_exercicio=ANO, dt_exercicio_inicial=ANO - 11,
                    tp_plano="Previdenciário", tp_massa="Civil",
                    nr_fluxo=codigo, no_fluxo=descricao,
                    vl_projetado="{:.2f}".format(projetado),
                    vl_executado="{:.2f}".format(executado),
                    vl_diferenca="{:.2f}".format(projetado - executado),
                    dt_envio=quando, te_situacao=situacao))

        # --- plano de amortização ano a ano; o primeiro ente da lista paga
        # menos que os juros, e por isso vê o saldo crescer ---
        saldo = patrimonio * 0.9
        taxa = 5.49
        paga_pouco = indice in _ENTES_SALDO_CRESCENTE
        for passo, ano_projetado in enumerate(range(ANO, ANO + 30)):
            juros = saldo * taxa / 100
            pagamento = juros * (0.7 if paga_pouco and passo < 4 else 1.0
                                 ) + saldo * 0.02 * (passo + 1) / 30
            amortizacao = pagamento - juros
            saldo_final = max(0.0, saldo - amortizacao)
            for quando, situacao in _versoes(reenviou, envio_valido):
                tabelas["DRAA_PLANO_AMORTIZACAO"].append(dict(
                    ident, dt_exercicio=ANO, tp_plano="Previdenciário",
                    tp_massa="Civil", dt_ano=ano_projetado, tx_juros=taxa,
                    vl_saldo_inicial="{:.2f}".format(saldo),
                    vl_juros="{:.2f}".format(juros),
                    vl_amortizacao="{:.2f}".format(amortizacao),
                    vl_pagamentos="{:.2f}".format(pagamento),
                    vl_aporte="{:.2f}".format(saldo * 0.001),
                    vl_saldo_final="{:.2f}".format(saldo_final),
                    vl_base_calculo="{:.2f}".format(folha * 12),
                    vl_aliquotas=taxa, dt_envio=quando, te_situacao=situacao))
            saldo = saldo_final
            if saldo <= 0:
                break

    return tabelas
def entes_do_siconfi(tabelas: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """A tabela de entes da federação, no formato do SICONFI.

    Espelha os mesmos entes do conjunto do CADPREV, com a esfera e a capital
    declaradas — que é o ponto: sem elas, a classificação volta a deduzir pelo
    nome, e a dedução por nome é o que promovia o município de Amapá a governo
    estadual.
    """
    vistos, saida = set(), []
    for registro in tabelas["RPPS_CRP"]:
        cnpj = registro["nr_cnpj_entidade"]
        if cnpj in vistos:
            continue
        vistos.add(cnpj)
        nome, uf = registro["no_ente"], registro["sg_uf"]
        estadual = nome.lower().startswith(("governo do estado",
                                            "governo do distrito"))
        saida.append({
            "cod_ibge": 3200000 + len(vistos),
            "ente": nome,
            "capital": "1  " if (not estadual and len(vistos) % 9 == 1) else "0  ",
            "regiao": "SE",
            "uf": uf,
            "esfera": "E" if estadual else "M",
            "exercicio": ANO,
            "populacao": 10000 + len(vistos) * 137,
            "cnpj": cnpj,
        })
    return saida


def escrever(destino: str = DIR_DEMO, nivel_a: bool = False) -> Dict[str, int]:
    """Grava as amostras no formato de página da API."""
    os.makedirs(destino, exist_ok=True)
    tabelas = gerar(nivel_a=nivel_a)
    # O SICONFI é outra API e tem outro envelope: o cliente dele procura o
    # arquivo pelo caminho do recurso, não pelo nome do endpoint.
    with open(os.path.join(destino, "entes.json"), "w", encoding="utf-8") as fh:
        json.dump({"items": entes_do_siconfi(tabelas), "hasMore": False},
                  fh, ensure_ascii=False)
    contagem = {}
    for nome, registros in tabelas.items():
        caminho = os.path.join(destino, nome + ".json")
        with open(caminho, "w", encoding="utf-8") as fh:
            json.dump({"data": registros, "count": len(registros), "limit": 5000},
                      fh, ensure_ascii=False)
        contagem[nome] = len(registros)
    return contagem
