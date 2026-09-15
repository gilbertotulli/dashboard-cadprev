# API CADPREV — catálogo técnico

Levantamento da API pública do CADPREV, mantida pela Subsecretaria dos Regimes
Próprios de Previdência Social (SRPPS), Ministério da Previdência Social.

**Verificado contra a API em 15/09/2026**, com amostras do Espírito Santo. As
respostas observadas estão em [`schema-observado/`](schema-observado/) — um
arquivo por endpoint, com as chaves e registros de exemplo.

## O host

| | |
| --- | --- |
| Host | `https://apicadprev.trabalho.gov.br` |
| Documentação | `/api-docs/` — Swagger 2.0, protegido por captcha |
| Verbo | `GET`, sempre |
| Autenticação | nenhuma |
| Formato | JSON ou CSV |
| Limite de uso | **1 requisição por segundo**, declarado na documentação |
| Data dos dados | 15/08/2026, conforme a própria documentação |

> **Cuidado com o host.** `apicadprev.previdencia.gov.br` e
> `apicadprev.economia.gov.br` **não existem** — não resolvem em DNS. O primeiro
> parece plausível pela renomeação da pasta ministerial e aparece em buscas; o
> segundo é citado como endereço da documentação. Nenhum dos dois responde. Este
> projeto chegou a adotar o primeiro por inferência e só descobriu o erro quando
> um runner do GitHub devolveu `Name or service not known`.

## Envelope e paginação

```json
{ "success": true, "data": [ … ], "count": 3728, "query": "…",
  "offset": 0, "limit": 5000 }
```

`offset` avança de `limit` em `limit`; a última página é aquela em que
`count < limit`.

## Parâmetros de consulta

| Parâmetro | Onde se aplica |
| --- | --- |
| `nr_cnpj_entidade` | todos — filtro preferencial |
| `no_ente`, `sg_uf` | todos |
| `dt_ano`, `dt_mes` | DIPR, DAIR |
| `dt_mes_bimestre` | carteira do DAIR |
| `dt_exercicio` | DRAA |
| `offset` | paginação |

Qualquer campo da resposta também serve como filtro.

## Os 39 endpoints

`python -m cadprev endpoints` lista o catálogo e marca os que já têm mapa de
campos neste projeto.

| Família | Nº | Conteúdo |
| --- | --- | --- |
| Serviço | 1 | `DATA_ATUALIZACAO` |
| Cadastro e regularidade | 3 | regime, CRP, alíquotas |
| DIPR | 1 | informações previdenciárias e repasses |
| DAIR | 8 | carteira, APR, governança, credenciamento, gestão |
| DRAA | 26 | avaliação atuarial, em vinte e seis recortes |

## Armadilhas verificadas

Quatro coisas que a leitura ingênua erra, todas confirmadas em dados reais.

### 1. No CRP, os campos estão trocados em relação à documentação

O Swagger descreve:

- `ds_situacao` — "Situação do CRP (Vigente ou Vencido)"
- `tp_crp` — "Tipo de Emissão do CRP (Administrativo ou Judicial)"

As respostas reais devolvem o contrário:

```json
{ "nr_crp": "980760-104543", "ds_situacao": "ADMINISTRATIVO",
  "dt_emissao": "09/04/2012", "dt_validade": "06/10/2012", "tp_crp": "VENCIDO" }
```

Este projeto lê os dois campos crus e classifica **pelo valor**, não pelo nome —
continua correto hoje e continuará se a inversão for corrigida. Ver
`cadprev/build.py::_ler_crp`.

Um detalhe adicional: "VÁLIDO" e "VENCIDO" começam com a mesma letra. Comparar
prefixo conta todo certificado vencido como regular.

### 2. O endpoint do CRP devolve o histórico, não a posição atual

3.728 registros só para o Espírito Santo, que tem 79 RPPS. São todas as emissões
desde sempre. A situação de hoje é a emissão mais recente de cada ente; contar as
linhas cruas trata cada renovação como se fosse outro RPPS.

O mesmo vale para `RPPS_ALIQUOTA`, que traz o campo `id_vigente`
(`VIGENTE` / `NÃO VIGENTE`) — melhor do que inferir pela data de fim.

### 3. No DIPR, metade das linhas é base de cálculo, não dinheiro

O DIPR vem em formato longo: uma linha por rubrica, mês, plano e órgão. E as
mesmas siglas aparecem **duas vezes**, com `id_rubrica` diferente e descrição
idêntica:

```
id=19  PAT-SEG  27.578.569,67     id=56  PAT-SEG   8.510.586,83
id=27  SEG      27.578.569,67     id=64  SEG       3.929.609,71
```

Os ids abaixo de 33 são o **bloco 1** — as bases de cálculo, isto é, a folha
sobre a qual as contribuições incidem. A pista está no valor: no bloco 1 a linha
patronal e a do servidor são idênticas, porque são a mesma folha; no bloco 2 elas
divergem, porque as alíquotas diferem.

Somar o bloco 1 como receita multiplica o caixa do RPPS por várias vezes. Em
Vitória, inflava a receita anual de R$ 464 mi para R$ 1,4 bi.

A separação entre entrada e saída está no prefixo da sigla: `UT-` é utilização de
recursos; todo o resto é ingresso.

### 4. O fluxo atuarial não é série temporal

`DRAA_FLUXO_ATUARIAL` devolve nove campos e um único `vl_projetado` por item de
fluxo. Não há ano de projeção. A curva de receitas e despesas ao longo de décadas
— e com ela o ano de cruzamento — está nos arquivos de dados abertos da SPREV,
não na API.

O que a API dá: totais projetados (código `190000` para receitas, `240000` para
despesas) e a composição de cada lado. Cuidado com o código `109001`, "Base de
Cálculo da Contribuição Normal", que está na faixa das receitas sem ser receita —
o mesmo engano do bloco 1 do DIPR, na outra ponta.

**Há uma série temporal no DRAA**, em outro endpoint: `DRAA_PLANO_AMORTIZACAO`
traz `dt_ano`, saldo inicial, juros, pagamentos, amortização e saldo final, ano a
ano. Ainda não consumido por este projeto.

## A dimensão de fundo: resposta definitiva

A pergunta central do projeto era se a carteira pode ser separada entre fundo
capitalizado, repartição simples e taxa de administração.

**Na carteira, não.** `DAIR_CARTEIRA` devolve dezesseis campos e nenhum identifica
plano ou fundo:

```
nr_cnpj_entidade · sg_uf · no_ente · dt_mes_bimestre · dt_ano · no_segmento
no_tipo_ativo · pc_cmn · id_ativo · no_fundo · qt_rpps · vl_atual_ativo
vl_total_atual · pc_rpps · vl_patrimonio · pc_patrimonio
```

`no_fundo` é o nome do fundo de investimento, não o plano previdenciário.

**Em caixa e atuária, sim.** A dimensão existe e está confirmada:

| Endpoint | Campo | Valores |
| --- | --- | --- |
| `DIPR` | `no_plano` | `PREVIDENCIARIO`, `FINANCEIRO` |
| `RPPS_ALIQUOTA` | `ds_plano_segregacao` | `Fundo em Capitalização`, `Fundo em Repartição` |
| `DRAA_*` | `tp_plano` | `Previdenciário`, `Financeiro`, `Mantidos pelo Tesouro` |

O mesmo conceito com três grafias — `cadprev/fundos.py` reconhece as três.

**A pista mais próxima de um Nível A** está em `DAIR_APLICACOES_RESGATE`, que tem
o campo `no_fundo_constituido` ("Plano/Fundo Constituido", com exemplo
`FUNDO SOLIDÁRIO GARANTIDOR`). As **movimentações** carregam o fundo; a
**posição** não. Reconstruir a carteira por fundo a partir do histórico de
aplicações e resgates seria possível em tese e frágil na prática — precisaria da
série completa desde a constituição de cada fundo. Não está feito, e não seria
honesto apresentar o resultado como posição declarada.

Portanto o projeto opera no **Nível B**: sem segregação de massa, a carteira
inteira é capitalizada; com segregação, fica marcada como não decomposta, sem
rateio arbitrado.

## Volumetria observada

Espírito Santo, 79 RPPS, uma competência:

| Endpoint | Linhas | Observação |
| --- | --- | --- |
| `RPPS_CRP` | 3.728 | histórico completo |
| `DIPR` | 20.445 | ano inteiro, formato longo |
| `DAIR_CARTEIRA` | 1.778 | uma competência |
| `DRAA_VALORES_COMPROMISSOS` | 3.159 | um exercício |
| `DRAA_FLUXO_ATUARIAL` | 2.048 | um exercício |

O Espírito Santo é cerca de 3,7% dos RPPS do país. Uma carga nacional da carteira
numa competência fica na ordem de 50 mil linhas; o DIPR de um ano, na casa das
centenas de milhares.

## O que não vem pela API

ISP (Indicador de Situação Previdenciária), MSC (Matriz de Saldos Contábeis),
acordos de parcelamento de débitos e o enquadramento de fundos existem como
planilha em dados abertos, não como endpoint. A marcação de capitais também não
vem da API: depende de [`../data/capitais.csv`](../data/capitais.csv).
