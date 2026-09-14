# API CADPREV — catálogo técnico

Levantamento da superfície da API pública do CADPREV (Cadastro dos Regimes Próprios
de Previdência Social), mantida pela Secretaria de Regimes Próprios de Previdência
Social (SRPPS/SPREV), Ministério da Previdência Social.

## Como este levantamento foi feito

O ambiente desta sessão bloqueia a saída HTTPS para os domínios `*.gov.br`
(o proxy de egresso responde `403` ao `CONNECT`), então **nenhuma chamada real à API
foi executada**. O contrato abaixo foi reconstruído a partir de:

- `marcosfs2006/ADPrev` — cliente R oficialmente publicado para esta API, que contém
  as URLs, os parâmetros de consulta e o laço de paginação;
- `marcosfs2006/ADPrevBook` — tutorial do mesmo autor, que documenta a estrutura dos
  conjuntos de dados correspondentes;
- catálogo de APIs governamentais e Portal de Dados Abertos.

Tudo que está marcado como **não confirmado** precisa ser validado contra o Swagger
(`/api-docs/`) a partir de uma rede com acesso liberado.

## Contrato

| Item | Valor |
| --- | --- |
| Host canônico | `https://apicadprev.previdencia.gov.br` |
| Espelhos históricos | `apicadprev.trabalho.gov.br`, `apicadprev.economia.gov.br` (mesmo serviço, renomeações de pasta ministerial) |
| Documentação | `/api-docs/` — Swagger 2.0, `api cadprev 1.0.0 oas 2.0` |
| Verbo | `GET` |
| Autenticação | nenhuma — API aberta, sem chave nem cabeçalho |
| Formato | JSON |
| Caminho | `/{ENDPOINT}` — o nome do recurso em MAIÚSCULAS é o próprio caminho |

### Envelope de resposta

```json
{
  "data":  [ { "...": "..." } ],
  "count": 5000,
  "limit": 5000
}
```

### Paginação

`offset` avança de `limit` em `limit`. A página é a última quando `count < limit`.
O `limit` padrão observado é **5000**.

```
GET /DIPR?nr_cnpj_entidade=39560008000148&dt_ano=2021&offset=0
GET /DIPR?nr_cnpj_entidade=39560008000148&dt_ano=2021&offset=5000
```

### Parâmetros de consulta

| Parâmetro | Tipo | Observação |
| --- | --- | --- |
| `nr_cnpj_entidade` | string | CNPJ do ente (só dígitos). **Filtro preferencial** |
| `no_ente` | string | nome do ente, exatamente como na base |
| `sg_uf` | string | sigla da UF, em maiúsculas |
| `dt_ano` | inteiro | ano de competência (DIPR, DAIR) |
| `dt_mes` | inteiro | mês de competência (DIPR, DAIR/APR) |
| `dt_mes_bimestre` | inteiro | mês/bimestre de competência (DAIR/carteira) |
| `dt_exercicio` | inteiro | exercício do DRAA |
| `offset` | inteiro | deslocamento da paginação |

Os parâmetros aceitos variam por endpoint; a recomendação do cliente R é consultar
com poucos filtros (CNPJ, ano, UF) e refinar do lado do cliente.

## Endpoints

### Cadastro e regularidade

| Endpoint | Conteúdo | Filtros |
| --- | --- | --- |
| `RPPS_REGIME_PREVIDENCIARIO` | regime do ente: RGPS, RPPS ou RPPS em extinção | `nr_cnpj_entidade`, `no_ente`, `sg_uf` |
| `RPPS_CRP` | Certificado de Regularidade Previdenciária: número, emissão, validade, se judicial, situação | `nr_cnpj_entidade`, `no_ente`, `sg_uf` |
| `RPPS_ALIQUOTA` | alíquotas de contribuição por plano e sujeito passivo, com vigência | `nr_cnpj_entidade`, `no_ente`, `sg_uf` |

### DIPR — Demonstrativo de Informações Previdenciárias e Repasses

| Endpoint | Conteúdo | Filtros |
| --- | --- | --- |
| `DIPR` | bases de cálculo, contribuições repassadas, deduções, aportes, parcelamentos, remuneração bruta, nº de beneficiários, ingressos, dispêndios, resultado do período e bloco de militares | `nr_cnpj_entidade`, `no_ente`, `sg_uf`, `dt_ano`, `dt_mes` |

O DIPR é declarado bimestralmente, com dados mensais. A base correspondente tem
**91 variáveis em 14 blocos**:

| Bloco | Conteúdo | Prefixo |
| --- | --- | --- |
| 0 | identificação (ente, uf, competência, plano de segregação, data da informação) | — |
| 1 | bases de cálculo — folhas do ente | `bc_` |
| 2 | contribuições repassadas | `ct_` |
| 3 | deduções | `deduc_` |
| 4 | aportes e transferências | `aportes_` |
| 5 | parcelamentos | `parcelamentos` |
| 6 | bases de cálculo — folha da unidade gestora | `bcug_` |
| 7 | contribuições arrecadadas pela unidade gestora | `ctug_` |
| 8 | remuneração bruta | `rb_` |
| 9 | número de beneficiários | `nb_` |
| 10 | ingressos de recursos | `ing_` |
| 11 | utilização de recursos | `desp_` |
| 12 | resultado final | `total_`, `resultado_final` |
| 13 | militares | `...mil_` |

### DAIR — Demonstrativo das Aplicações e Investimentos de Recursos

| Endpoint | Conteúdo | Filtros |
| --- | --- | --- |
| `DAIR_CARTEIRA` | carteira por ativo: segmento, tipo de ativo, limite da Resolução CMN 3.922/10, identificação e nome do ativo, cotas, valor unitário e total, % dos recursos do RPPS, PL do fundo e % do PL | `nr_cnpj_entidade`, `no_ente`, `sg_uf`, `dt_ano`, `dt_mes_bimestre` |
| `DAIR_APLICACOES_RESGATE` | APR — Autorizações para Aplicação e Resgate | `nr_cnpj_entidade`, `no_ente`, `sg_uf`, `dt_ano`, `dt_mes` |

### DRAA — Demonstrativo de Resultados da Avaliação Atuarial

Todos aceitam `nr_cnpj_entidade`, `no_ente`, `sg_uf`, `dt_exercicio`.

| Endpoint | Conteúdo |
| --- | --- |
| `DRAA_ENCAMINHAMENTO` | envio do DRAA à SPREV: data, situação |
| `DRAA_DADOS_CONSOLIDADOS` | consolidação do demonstrativo |
| `DRAA_ESTATISTICA` | massa de participantes: ativos, aposentados, pensionistas, dependentes |
| `DRAA_VALORES_COMPROMISSOS` | compromissos por código/descrição, em geração atual e geração futura |
| `DRAA_SEGREGACAO_MASSA` | plano financeiro × plano previdenciário |
| `DRAA_PLANO_CUSTEIO` | custo normal e suplementar |
| `DRAA_PLANO_BENEFICIO` | benefícios cobertos pelo plano |
| `DRAA_CONTRIBUICAO` | contribuições consideradas na avaliação |
| `DRAA_PLANO_AMORTIZACAO` | plano de equacionamento do déficit |
| `DRAA_FORMA_AMORTIZACAO` | forma de amortização adotada |
| `DRAA_FLUXO_ATUARIAL` | projeção anual de receitas, despesas e saldo do plano |
| `DRAA_HIPOTESE_ATUARIAL` | taxa de juros, crescimento salarial, rotatividade |
| `DRAA_HIPOTESE_BIOMETRICA` | tábuas de mortalidade, invalidez e sobrevivência |
| `DRAA_PARECER_ATUARIAL` | parecer do atuário responsável |
| `DRAA_COMPARATIVO_AVALIACAO` | comparação entre exercícios |
| `DRAA_COMPARATIVO_RECEITA` | comparação de receitas entre exercícios |

## A dimensão de fundo: capitalizado, repartição simples e taxa de administração

Esta separação foi investigada especificamente. O resultado é misto e vale registrar
com precisão, porque muda o que o painel pode prometer.

### O que está confirmado na API

A dimensão de plano **existe** e é nomeada `FINANCEIRO` (repartição simples) e
`PREVIDENCIÁRIO` (capitalização):

| Onde | Campo | O que permite |
| --- | --- | --- |
| `DIPR` | `plano_segreg` | Ingressos, dispêndios e resultado **por plano**, mês a mês |
| `RPPS_ALIQUOTA` | `plano_segregacao` | Alíquotas por plano e por sujeito passivo |
| `DRAA_SEGREGACAO_MASSA` | — | Se o RPPS segregou a massa e como o fez |

Ou seja: o **fluxo de caixa** e a **estrutura atuarial** já se separam entre capitalizado
e não capitalizado hoje, sem nenhuma derivação.

### O que não está confirmado

O arquivo de dados abertos da carteira do DAIR tem **exatamente 15 colunas** e nenhuma
delas identifica plano ou fundo:

```
cnpj · uf · ente · competencia · segmento · tipo_ativo · limite_resol_cmn ·
ident_ativo · nm_ativo · qtd_quotas · vlr_atual_ativo · vlr_total_atual ·
perc_recursos_rpps · pl_fundo · perc_pl_fundo
```

Os DAIR em PDF gerados pelo próprio CADPREV mostram os recursos vinculados aos
respectivos planos e à taxa de administração, e a Portaria MTP nº 1.467/2022 exige que
os recursos da taxa de administração sejam mantidos **de forma segregada** dos recursos
destinados ao pagamento de benefícios. Logo a informação existe na declaração de origem.
**O que não se sabe é se o endpoint `DAIR_CARTEIRA` a expõe** — só a leitura do Swagger
resolve isso.

A taxa de administração como massa investida também não aparece na carteira. O que a API
entrega hoje é a **despesa** (`desp_despadm`, no bloco 11 do DIPR), não a reserva aplicada.

### Como o painel deve tratar isso

Dois níveis, com degradação declarada na própria tela:

- **Nível A — se `DAIR_CARTEIRA` expuser o plano do ativo.** Decomposição de três vias do
  patrimônio investido: capitalizado, repartição simples e taxa de administração.
- **Nível B — garantido hoje.** Classificar o **RPPS**, não o ativo: sem segregação de
  massa, toda a carteira é capitalizada; com segregação, a carteira é marcada como
  *não decomposta*. O agregado nacional continua respondendo “quanto do patrimônio está
  em regimes integralmente capitalizados”, que é a pergunta de risco relevante.

A distinção entre classificar o ativo e classificar o RPPS não pode ficar implícita: no
Nível B, um RPPS com massa segregada tem carteira única na base e qualquer rateio entre
planos seria invenção.

## Agregação nacional da carteira

A visão nacional dispensa filtro por CNPJ: basta `dt_ano` + `dt_mes_bimestre`, paginando
até o fim.

| Item | Estimativa |
| --- | --- |
| RPPS que enviam DAIR numa competência | ~2.000 |
| Ativos por RPPS | dezenas |
| Linhas por competência | ~100 mil a 170 mil |
| Páginas de 5.000 | ~20 a 35 |

Recortes por grupo, e de onde vem cada um:

| Grupo | Origem |
| --- | --- |
| Região | derivada de `sg_uf` — direto da API |
| Estaduais × municipais | derivável de `no_ente` (os RPPS estaduais aparecem como `Governo do Estado do …`); confirmar contra `RPPS_REGIME_PREVIDENCIARIO` |
| Capitais | **não vem da API** — exige tabela auxiliar de 27 CNPJs mantida no repositório |

Dois cuidados nos extremos do ranking:

1. `segmento` inclui `Disponibilidades Financeiras`, com `tipo_ativo` e `limite_resol_cmn`
   nulos. Decidir explicitamente se entra no patrimônio investido — entra no total de
   recursos, mas não é alocação.
2. O ranking dos **menores** patrimônios é o mais fácil de errar: quem não enviou o DAIR
   na competência simplesmente não tem linha, e quem enviou com valor zerado apareceria no
   topo da lista de menores. A regra tem de ser explícita — menor patrimônio **entre os que
   enviaram DAIR na competência e com total maior que zero** — e a tela precisa dizer
   quantos RPPS ficaram de fora.

## O que não vem pela API

Estas bases existem no ecossistema do CADPREV/SPREV, mas são publicadas como
planilhas em dados abertos, não como endpoint:

- **ISP** — Indicador de Situação Previdenciária (nota A–D em 3 dimensões e 6 indicadores);
- **MSC** — Matriz de Saldos Contábeis;
- **Parcelamento de débitos** — acordos de parcelamento entre ente e RPPS;
- **Enquadramento de fundos** e **relação de fundos vedados** (CGACI-RPPS).

Para um painel que precise desses blocos, a alternativa é ingerir as planilhas e
cruzar pelo CNPJ do ente.

## Pendências de validação

1. Nomes exatos dos campos de cada resposta — os campos descritos aqui vêm dos
   conjuntos de dados equivalentes, não de uma resposta capturada da API.
2. Comportamento de erro (códigos e corpo) e existência de `rate limit`.
3. Se `limit` é ajustável por parâmetro.
4. Profundidade histórica por endpoint (o DIPR em dados abertos começa em 2014).
5. **Se `DAIR_CARTEIRA` expõe o plano/fundo do ativo** — é a pendência de maior impacto:
   decide entre o Nível A e o Nível B da decomposição por fundo.
6. Se a carteira do DAIR traz os recursos da taxa de administração como massa investida.
