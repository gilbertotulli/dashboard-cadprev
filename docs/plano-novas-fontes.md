# Plano de novas fontes e de carga incremental

Levantado entre 16 e 17/09/2026, contra as APIs reais. Os números aqui não são
estimativas: cada um saiu de uma consulta registrada, e as que me contrariaram
estão anotadas como tal.

## Por que este documento existe

O painel nasceu sobre uma fonte só, o CADPREV, varrida por inteiro toda semana.
Isso funcionou enquanto a base era pequena. Com um milhão de linhas por carga, e
com a perspectiva de somar o SICONFI, duas perguntas passaram a ter resposta
cara: **o que realmente muda entre uma semana e outra** e **o que se pode
comparar com o quê**.

## Duas correções de avaliações anteriores

Registradas porque a conclusão errada já estava escrita em outro lugar.

**A cobertura do SICONFI não é 53%, é 96%.** A primeira medição consultou apenas
`co_tipo_demonstrativo=RREO`. Municípios menores entregam **RREO Simplificado** —
rótulo diferente, mesmo Anexo 04. Medindo os dois tipos numa amostra de 70 RPPS:
67 têm o anexo (37 pelo RREO comum, 30 pelo simplificado).

**O RREO é bimestral, não anual.** A diferença por porte está no RGF:
quadrimestral acima de 50 mil habitantes, semestral abaixo.

## Periodicidade real de cada grupo

| grupo | periodicidade | filtro disponível | janela de mudança |
|---|---|---|---|
| DRAA (18 endpoints) | anual (`dt_exercicio`) | exercício | entrega até 30/04, retificações até ~julho |
| DIPR | mensal | ano + mês | mês seguinte + retificações |
| DAIR (8 endpoints) | mensal | ano + mês | ~30 dias após o mês |
| CRP, alíquota, regime | cadastral | nenhum | contínua |
| RREO (SICONFI) | bimestral | ano + período | ~30 dias após o bimestre |
| RGF (SICONFI) | quadrimestral ou semestral | ano + período | conforme porte |
| DCA (SICONFI) | anual | exercício | até 30/04 |

### O custo do que não muda

Composição da carga de 16/09/2026, 1.018.863 linhas:

| grupo | linhas | % | muda quando |
|---|---:|---:|---|
| Cadastral (CRP, alíquota, regime) | 334.817 | 32,9% | contínuo, pouco |
| DRAA | 315.329 | 30,9% | uma vez por ano |
| DIPR | 295.712 | 29,0% | só os meses recentes |
| DAIR | 73.005 | 7,2% | mensal |

De agosto a fevereiro, quase um terço da carga semanal é DRAA idêntico ao da
semana anterior.

## Índices de mudança

Nenhum endpoint do CADPREV aceita filtro por data de alteração. Há, porém, três
atalhos que a própria fonte entrega.

| índice | custo | o que diz |
|---|---|---|
| `DATA_ATUALIZACAO` | 1 requisição | carimbo global; em 17/09/2026 marcava 15/08/2026 |
| `DAIR_IDENTIFICACAO` | 13 mil linhas/ano | `dt_envio` e motivo de retificação por ente e mês |
| `DRAA_ENCAMINHAMENTO` | pequeno | `dt_envio` e situação por ente e exercício |
| `extrato_entregas` (SICONFI) | 1 req/ente/ano | `data_status` de cada entregável, ano inteiro |

Como os endpoints filtram por `nr_cnpj_entidade`, a re-ingestão pode ser
cirúrgica: cinquenta entes retificaram, cinquenta requisições — não uma varredura
de trezentas mil linhas.

## Estratégia incremental, em quatro níveis

0. **Portão global.** `DATA_ATUALIZACAO` inalterado desde a última carga
   bem-sucedida: republica do cache e encerra.
1. **Sazonal.** DRAA só entre março e julho, ou quando o índice de encaminhamento
   acusar envio novo.
2. **Por competência.** DIPR e DAIR recarregam a última competência fechada e as
   duas anteriores, que é a janela de retificação.
3. **Cirúrgico.** Onde o índice apontar ente específico, re-ingere por CNPJ.

**Instrumentar antes de cortar.** Registrar os índices a cada carga por três ou
quatro semanas e comparar com o que de fato mudou. Só então ligar o portão. Um
corte ligado cedo demais congela o painel sem avisar — e a salvaguarda é uma
varredura completa obrigatória a cada quatro semanas, independentemente do
portão.

## Alinhamento temporal dos cruzamentos

Nenhuma comparação sem a referência temporal declarada na tela.

| cruzamento | CADPREV | SICONFI | regra |
|---|---|---|---|
| Investimentos | DAIR mensal (saldo) | RREO Anexo 04 (saldo do bimestre) | só meses pares, contra o bimestre que os fecha |
| Receitas e despesas | DIPR mensal | RREO Anexo 04 acumulado | acumular DIPR de janeiro ao mês do bimestre |
| Provisões | DRAA exercício N | DCA Anexo I-AB (31/12) | DRAA de N descreve N−1 |
| Massa | DRAA exercício N | — | comparar com DIPR e DAIR de N−1 |

Validação feita: Vitória, DAIR de junho/2026 contra RREO do 3º bimestre/2026 —
R$ 1.407.901.392,17 contra R$ 1.405.333.216,77, **0,18% de diferença**. Duas
apurações independentes, uma declaratória e outra contábil, no mesmo número.

## Fases

**Fase 1 — colher o que já está ligado.** Quatro endpoints do CADPREV que o
projeto não consumia, todos anuais e baratos:

- `DRAA_NOTIFICACAO` — apontamentos da SPREV, com item de análise, prazo de
  resposta, data de preclusão e situação. São ações de correção já existindo.
- `DRAA_COMPARATIVO_RECEITA` — projetado, executado e diferença por item de
  fluxo. Divergência calculada na fonte.
- `DRAA_PLANO_AMORTIZACAO` — saldo, juros, amortização e aporte ano a ano. Fecha
  a lacuna que o README declarava aberta.
- `DRAA_ENCAMINHAMENTO` — o índice de mudança do DRAA.

**Fase 2 — instrumentar.** Gravar `DATA_ATUALIZACAO` e os `dt_envio` a cada
carga, e mostrá-los na aba Qualidade junto da procedência. Sem cortar nada.

**Fase 3 — ligar os cortes.** Com evidência acumulada, ativar os níveis 0 a 3.

**Fase 4 — SICONFI `/entes`.** Uma requisição. População e marca de capital
autoritativas, substituindo heurísticas que já custaram um erro de classificação
a este projeto.

**Fase 5 — SICONFI RREO Anexo 04.** Entrega a decomposição capitalização /
repartição / taxa de administração — o Nível A que o projeto declarava
impossível a partir do CADPREV — e a comparação entre fontes.

### Situação em 17/09/2026

As fases 1, 2, 4 e 5 estão implantadas. A fase 3 depende de semanas de medição
acumulada e não pode ser antecipada sem desfazer o próprio motivo dela existir.

**Fase 6, a próxima — DCA.** Trazer o Anexo I-AB e confrontar a provisão
matemática contábil com a avaliação atuarial do DRAA, respeitando a defasagem de
um exercício entre os dois. Uma requisição por ente e por ano.

## Bases ainda a estudar

Sondadas em 17/09/2026, com o que já se sabe e o que falta descobrir.

### DCA — Declaração de Contas Anuais

`/dca`, anual, um pedido por ente. O Anexo I-AB é o balanço patrimonial e traz,
para Vitória em 2025:

| conta | valor |
|---|---:|
| 2.2.7.2 Provisões Matemáticas Previdenciárias | R$ 5.665.228.213,93 |
| 2.2.7.2.1.01/02 Fundo em Repartição | R$ 5.533.359.879,21 |
| 2.2.7.2.1.03/04 Fundo em Capitalização | R$ 131.868.334,72 |
| 1.1.4.4 Investimentos e Aplicações Temporárias | R$ 1.344.935.455,56 |

É o **passivo atuarial reconhecido na contabilidade**, separado pelos mesmos dois
fundos, e cruza diretamente com `DRAA_VALORES_COMPROMISSOS`. Divergência entre o
que o atuário avaliou e o que o contador registrou é achado de primeira ordem.

Custo medido: o Anexo I-AB inteiro vem em **uma requisição por ente e por
exercício** — 161 linhas para Vitória, das quais 9 são de provisão matemática.
Para os 1.821 RPPS dá cerca de vinte e cinco minutos por exercício, uma vez por
ano. É o melhor retorno por requisição das quatro bases restantes.

O alinhamento temporal pede atenção: o DCA fecha em 31/12 do exercício e o DRAA
do exercício N descreve a posição de N−1. Comparar o DRAA de 2026 com o DCA de
2026 confrontaria avaliações de datas diferentes; o par correto é o DRAA de N com
o DCA de N−1, e a tela precisa dizer isso.

Prioridade alta — é a próxima a entrar.

### RGF — Relatório de Gestão Fiscal

`/rgf`, quadrimestral ou semestral. O Anexo 01 traz a despesa com pessoal em
`<MR-11>` (últimos doze meses). Relevante de forma indireta: a despesa com
pessoal é a base sobre a qual as contribuições incidem, e o limite prudencial
contextualiza a capacidade do ente de honrar aportes. Prioridade média.

### CAPAG — Capacidade de Pagamento

Planilhas XLSX no CKAN do Tesouro, uma por ano, com nota A a D por município.
Contextualiza a saúde fiscal do ente por trás do RPPS: um plano de amortização de
trinta anos apoiado num ente nota D é informação que nenhuma das outras bases dá.
Formato diferente de tudo o que o projeto lê hoje — exige leitor de XLSX, e o
projeto não tem dependências. Avaliar se há a mesma tabela em CSV antes de
decidir. Prioridade média, esforço maior que o aparente.

### MSC — Matriz de Saldos Contábeis

`/msc_patrimonial` e `/msc_orcamentaria`, mensal. A primeira sondagem voltou
vazia; o parâmetro que faltava era **`id_tv`** (tipo de valor), e não
`co_tipo_valor`. A combinação que responde é:

```
/msc_patrimonial?an_referencia=2025&me_referencia=12&id_ente=3205309
                &co_tipo_matriz=MSCC&classe_conta=1&id_tv=period_change
```

Devolve 1.128 linhas só para a classe 1 de um município num mês, com
`conta_contabil` no PCASP, `poder_orgao`, `natureza_conta` e `valor`.

E é justamente por responder que dá para calcular o custo: `classe_conta` é
obrigatório, então são oito requisições por ente e por mês de referência —
1.821 RPPS dão cerca de **catorze mil requisições por mês de referência**, mais
de três horas. Para o ano, quarenta horas.

**A MSC é dominada pelo DCA** para o que este painel precisa. As contas que
interessam — provisões matemáticas e investimentos — estão no DCA consolidadas
no exercício, a uma requisição por ente. A MSC só se justifica se aparecer uma
pergunta que exija granularidade mensal, e nenhuma das perguntas atuais exige.
Prioridade baixa, agora por medida e não por desconhecimento.

### Fora do escopo

A API do `dados.gov.br` responde 401 e exige chave de registro. Os conjuntos
ligados a RPPS que ela indexa são, em boa parte, espelhos do que o CADPREV e o
Tesouro já servem direto.
