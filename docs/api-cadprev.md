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
