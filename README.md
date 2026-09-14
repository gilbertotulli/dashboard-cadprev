# dashboard-cadprev

Levantamento da API pública do CADPREV e anteprojeto de um painel sobre os dados
dos Regimes Próprios de Previdência Social (RPPS).

## Conteúdo

| Arquivo | O que é |
| --- | --- |
| [`docs/api-cadprev.md`](docs/api-cadprev.md) | Catálogo técnico: contrato, paginação, parâmetros e os 22 endpoints, por família |
| [`docs/anteprojeto-painel-cadprev.html`](docs/anteprojeto-painel-cadprev.html) | Anteprojeto visual do painel — cinco telas, com mockups em escala e a fonte de cada número |

## Resumo da API

- Host canônico `https://apicadprev.previdencia.gov.br`, espelhos em `apicadprev.trabalho.gov.br`
  e `apicadprev.economia.gov.br`; documentação Swagger 2.0 em `/api-docs/`.
- `GET /{ENDPOINT}`, sem autenticação, resposta JSON no envelope `{ data, count, limit }`.
- Paginação por `offset`, páginas de 5.000 registros.
- Filtros: `nr_cnpj_entidade`, `no_ente`, `sg_uf`, `dt_ano`, `dt_mes`, `dt_mes_bimestre`, `dt_exercicio`.
- 22 endpoints em quatro famílias: cadastro e regularidade (3), DIPR (1), DAIR (2) e DRAA (16).

## Ressalva importante

Nenhuma chamada à API foi executada durante este levantamento — a rede da sessão
bloqueia a saída para domínios `*.gov.br`. O contrato foi reconstruído a partir do
cliente R `marcosfs2006/ADPrev` e do tutorial `ADPrevBook`. Os nomes exatos dos campos
de resposta ainda precisam ser confirmados contra o Swagger. Os números dos mockups
são ilustrativos e não representam nenhum ente real.
