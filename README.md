# dashboard-cadprev

Levantamento da API pública do CADPREV e anteprojeto de um painel sobre os dados
dos Regimes Próprios de Previdência Social (RPPS).

## Conteúdo

| Arquivo | O que é |
| --- | --- |
| [`docs/api-cadprev.md`](docs/api-cadprev.md) | Catálogo técnico: contrato, paginação, parâmetros e os 22 endpoints, por família |
| [`docs/anteprojeto-painel-cadprev.html`](docs/anteprojeto-painel-cadprev.html) | Anteprojeto visual do painel — seis telas, com mockups em escala e a fonte de cada número |

## Resumo da API

- Host canônico `https://apicadprev.previdencia.gov.br`, espelhos em `apicadprev.trabalho.gov.br`
  e `apicadprev.economia.gov.br`; documentação Swagger 2.0 em `/api-docs/`.
- `GET /{ENDPOINT}`, sem autenticação, resposta JSON no envelope `{ data, count, limit }`.
- Paginação por `offset`, páginas de 5.000 registros.
- Filtros: `nr_cnpj_entidade`, `no_ente`, `sg_uf`, `dt_ano`, `dt_mes`, `dt_mes_bimestre`, `dt_exercicio`.
- 22 endpoints em quatro famílias: cadastro e regularidade (3), DIPR (1), DAIR (2) e DRAA (16).

## A separação da carteira por fundo

Investigada especificamente, com resultado misto:

- **Confirmado.** A dimensão de plano existe e é nomeada `FINANCEIRO` (repartição simples) e
  `PREVIDENCIÁRIO` (capitalização), em `DIPR.plano_segreg`, `RPPS_ALIQUOTA.plano_segregacao` e
  `DRAA_SEGREGACAO_MASSA`. Caixa e atuária já se separam entre capitalizado e não capitalizado.
- **Não confirmado.** O arquivo de dados abertos da carteira do DAIR tem 15 colunas e nenhuma
  identifica plano ou fundo. A informação existe na declaração de origem — os DAIR em PDF do
  CADPREV mostram os recursos vinculados aos planos e à taxa de administração, e a Portaria MTP
  nº 1.467/2022 exige que a taxa de administração seja mantida segregada — mas não se sabe se o
  endpoint `DAIR_CARTEIRA` a expõe.

O painel prevê os dois níveis, com o nível em vigor declarado na própria tela. Detalhes em
[`docs/api-cadprev.md`](docs/api-cadprev.md).

## Ressalva importante

Nenhuma chamada à API foi executada durante este levantamento — a rede da sessão
bloqueia a saída para domínios `*.gov.br`. O contrato foi reconstruído a partir do
cliente R `marcosfs2006/ADPrev` e do tutorial `ADPrevBook`. Os nomes exatos dos campos
de resposta ainda precisam ser confirmados contra o Swagger. Os números dos mockups
são ilustrativos e não representam nenhum ente real.
