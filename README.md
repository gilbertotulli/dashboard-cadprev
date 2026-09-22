# Painel CADPREV

Leitura visual dos dados públicos do [CADPREV](https://cadprev.previdencia.gov.br/Cadprev/)
sobre os Regimes Próprios de Previdência Social (RPPS).

Consome a API aberta da Subsecretaria dos Regimes Próprios de Previdência Social e
reorganiza o que já é público em seis telas que respondem a perguntas diretas: o regime
está regular, arrecada mais do que paga, onde investe e se as promessas de aposentadoria
fecham no longo prazo.

> **Projeto independente**, sem vínculo com o Ministério da Previdência Social, com a
> SRPPS ou com qualquer RPPS. Para uso oficial, fiscal ou jurídico, a fonte é o CADPREV.

## Como rodar

Precisa de Python 3.9 ou mais novo. **Não há dependências para instalar** — o pacote usa
só a biblioteca padrão.

```bash
git clone https://github.com/gilbertotulli/dashboard-cadprev
cd dashboard-cadprev

# painel de pé em um comando, com dados sintéticos
python -m cadprev demo
python -m cadprev serve          # http://localhost:8000
```

Com acesso de rede à API, os dados reais entram assim:

```bash
# 1. descubra os nomes reais dos campos (ver "A pendência aberta" abaixo)
python -m cadprev inspect DAIR_CARTEIRA RPPS_CRP --uf ES --salvar --override

# 2. traga os dados
python -m cadprev ingest --tudo --uf ES --ano 2026 --mes 8

# 3. gere os JSON do painel
python -m cadprev build
python -m cadprev serve
```

| Comando | O que faz |
| --- | --- |
| `demo` | gera dados sintéticos, ingere e constrói o painel |
| `inspect` | baixa uma página e relata os campos que a API realmente devolve |
| `ingest` | traz endpoints para o banco local (SQLite), paginando |
| `build` | pré-agrega tudo nos JSON que o painel lê |
| `serve` | serve `web/` localmente |
| `status` | o que já foi ingerido, quando e com quais filtros |
| `endpoints` | o catálogo dos 39 recursos da API |

## Como está montado

```
cadprev/        ingestão e agregação (Python, sem dependências)
  endpoints.py    catálogo dos 39 recursos da API
  fieldmap.py     ⚠ mapeamento campo lógico → chave real da API
  client.py       GET paginado, com repetição e modo offline
  store.py        SQLite + procedência de cada ingestão
  fundos.py       separação por natureza do fundo (Níveis A e B)
  qualidade.py    o que a própria base contradiz, e as chaves de recorte
  competencia.py  pergunta à API qual competência do DAIR já fechou
  siconfi.py      cliente da segunda fonte: o SICONFI, do Tesouro Nacional
  grupos.py       esfera, região e capitais
  build.py        agregação para os JSON do painel
web/            painel estático (HTML, CSS e JS, sem build)
data/           tabelas auxiliares que não vêm da API
fixtures/demo/  amostras sintéticas, no formato da API
docs/           levantamento da API e anteprojeto do painel
```

A API não filtra por data de alteração e pagina de 5.000 em 5.000 — uma competência da
carteira nacional são 100 a 170 mil linhas. Por isso o painel **não consulta a API ao
vivo**: ingere uma vez, pré-agrega, e serve arquivos estáticos. Dá para hospedar em
qualquer lugar que sirva HTML.

## Os nomes dos campos: resolvidos

O levantamento inicial foi feito **sem acesso de rede** aos domínios `*.gov.br`,
então os nomes dos campos eram candidatos, não certezas. Em 15/09/2026 a API foi
consultada de verdade e os nomes foram fixados. A evidência está em
[`docs/schema-observado/`](docs/schema-observado/), um arquivo por endpoint.

A camada de mapeamento em [`cadprev/fieldmap.py`](cadprev/fieldmap.py) continua
existindo, agora por outro motivo: a API já mudou de host uma vez, e quando um
campo mudar de nome basta acrescentar um candidato. A resolução falha alto se um
campo obrigatório sumir, com as chaves reais na mensagem.

```bash
python -m cadprev inspect DAIR_CARTEIRA --uf ES --salvar --override
```

**Cuidado com o host.** `apicadprev.previdencia.gov.br` e
`apicadprev.economia.gov.br` não existem — não resolvem em DNS. O único host vivo
é `apicadprev.trabalho.gov.br`.

## A separação por natureza do fundo

Investigada e **respondida contra a API real**:

- **Na carteira, não existe.** `DAIR_CARTEIRA` devolve dezesseis campos e nenhum
  identifica plano ou fundo. (`no_fundo` é o nome do fundo de investimento, não o
  plano previdenciário.)
- **Em caixa e atuária, existe.** `DIPR.no_plano`, `RPPS_ALIQUOTA.ds_plano_segregacao`
  e `DRAA_*.tp_plano` trazem a dimensão, com três grafias diferentes para o mesmo
  conceito.
- **A pista mais próxima** está em `DAIR_APLICACOES_RESGATE.no_fundo_constituido`: as
  movimentações carregam o fundo, a posição não.

O painel opera portanto no **Nível B**, declarado na tela:

| Nível | Quando | O que mostra |
| --- | --- | --- |
| **A** | o endpoint expõe o plano do ativo | decomposição de três vias: capitalizado, repartição simples e taxa de administração |
| **B** | não expõe — **é o caso hoje** | classifica o **RPPS**, não o ativo: sem segregação de massa a carteira inteira é capitalizada; com segregação, fica *não decomposta* |

No Nível B o projeto **não rateia** a carteira entre planos. Não há base no dado para
isso, e o número resultante sairia daqui para dentro de um ofício.

## O que não vem pela API

ISP (Indicador de Situação Previdenciária), MSC (Matriz de Saldos Contábeis), acordos de
parcelamento de débitos e o enquadramento de fundos existem como planilha em dados
abertos, não como endpoint. A marcação de capitais também não vem da API: depende de
[`data/capitais.csv`](data/capitais.csv), mantido aqui.

## Publicar para outros RPPS

O painel é um site estático: `web/` são arquivos soltos, sem servidor nem banco de
dados. Isso abre três caminhos.

### GitHub Pages (o caminho curto)

Já existe o workflow `publicar painel`, que **ingere dados reais da API** — os runners
do GitHub alcançam `apicadprev.previdencia.gov.br` — e publica o resultado.

1. **Settings → Pages → Source: GitHub Actions**
2. **Actions → publicar painel → Run workflow**

Deixe `uf` em branco para o país inteiro, ou preencha (`ES`, por exemplo) para uma
publicação mais rápida. Marque `usar_demonstracao` para subir o conjunto sintético e
mostrar a forma do painel antes de os dados reais estarem resolvidos.

O endereço fica `https://gilbertotulli.github.io/dashboard-cadprev/`, público para
qualquer pessoa com o link. Depois disso ele se republica sozinho toda segunda-feira,
e a cada push no `main`.

Para um endereço institucional, Pages aceita domínio próprio (Settings → Pages →
Custom domain) com um registro CNAME apontando para `gilbertotulli.github.io`.

### No servidor do próprio instituto

Rode `python -m cadprev ingest ...` e `python -m cadprev build` numa máquina com
acesso à API e sirva a pasta `web/` em qualquer servidor web. Não há processo para
manter no ar — é HTML, CSS, JS e JSON.

Para atualizar sozinho, um `cron` semanal com os mesmos dois comandos basta.

### Controle de acesso

O Pages público é o ajuste natural aqui: são dados que já são públicos, e a restrição
de acesso seria ruído. Se ainda assim o acesso precisar ser restrito, o Pages privado
exige GitHub Enterprise; a alternativa é servir a pasta `web/` atrás da autenticação
que o instituto já usa.

## O comparativo

A aba **Comparativo** põe o RPPS selecionado contra uma referência escolhida:
todos os RPPS ingeridos, a região, a faixa de porte, ou outro RPPS específico.

Duas decisões sustentam a leitura:

- **Indicadores normalizados, não valores absolutos.** Percentuais e razões —
  ativos por inativo, cobertura das provisões, resultado sobre ingressos, perfil
  da carteira por segmento. Comparar patrimônio bruto mediria porte, não gestão.
- **Mediana, não média.** As distribuições são fortemente assimétricas: uns
  poucos RPPS estaduais concentram a maior parte do patrimônio. A tela mostra
  também o intervalo interquartil, para que a posição seja lida dentro da
  dispersão e não contra um ponto só.

A quarta referência é um conjunto montado à mão: busca por nome (sem exigir
acento), filtro por UF, e um atalho para somar o estado inteiro de uma vez. Com
um RPPS escolhido a comparação é direta; com vários, a referência passa a ser a
mediana deles.

Essa mediana é calculada no navegador — não há como pré-computar a mediana de um
conjunto que o leitor monta na hora. É a única aritmética do projeto que existe
nos dois lados, e duas implementações da mesma conta divergem sozinhas: o teste
`tests/estatistica-do-navegador.mjs` extrai as funções do próprio `web/app.js`,
remonta em JavaScript os grupos que o Python pré-calculou e exige igualdade até o
centésimo. Ele já pegou duas divergências de arredondamento — multiplicar por cem
antes de arredondar, e o empate exato que o Python manda para o par.

Grupos com menos de três RPPS não geram estatística, e verde e vermelho aparecem
só nos indicadores de direção inequívoca — mais renda fixa não é melhor nem pior
por si. Faixas de porte, por segurados: até 1.000, de 1.000 a 10.000, acima disso.

## Qualidade do cadastro

A fonte tem erros de digitação, e eles não são pequenos: em 15/09/2026, uma
única linha respondia por **88,49%** do patrimônio nacional. O RPPS de Santo
Afonso/MT declarou a cota de um fundo a R$ 36.640.481,00 quando ela vale
R$ 36,640481 — vírgula seis casas fora do lugar —, e o painel somava
R$ 3,57 trilhões onde há R$ 411 bilhões.

Filtrar isso por "valor muito alto" seria arbitrário: o maior RPPS do país é
legitimamente milhares de vezes maior que o menor, e nenhum corte estatístico
separa um estado grande de um erro de vírgula. A régua, então, é aritmética.

Cada linha da carteira traz a posição do RPPS **e** o patrimônio líquido do
fundo em que ela está aplicada, e o mesmo fundo aparece na carteira de centenas
de RPPS. Quando a posição excede em mais de dez vezes a maior declaração já
feita para aquele fundo, ela é impossível e sai de todas as somas — do total
nacional e da ficha do próprio ente, porque excluir de um e manter no outro
publicaria dois números incompatíveis sobre o mesmo fato.

Três decisões deliberadas:

- **A margem é grosseira de propósito.** Entre uma vez e mil vezes ela devolve
  exatamente as mesmas linhas. Se o resultado mudasse com o parâmetro, quem
  estaria decidindo seria a régua, e não a evidência.
- **O campo de PL é ruidoso, e a régua respeita isso.** O mesmo fundo aparece
  com PL declarado entre R$ 0,01 e R$ 4,42 bilhões. Divergir do consenso, por
  isso, não é sinal de erro — é o estado normal do campo. A referência é a
  *maior* declaração crível, não a mediana.
- **O valor não é corrigido.** Dividir por um milhão daria o número certo e
  seria inventá-lo. A linha é omitida e o caso aparece nomeado na aba
  **Qualidade**, com a evidência ao lado, para quem puder corrigir na fonte.

### As chaves do topo

As estatísticas nacionais dependem de quem entra na conta. Quatro chaves
recortam o universo, e a URL carrega o recorte — um link compartilhado mostra ao
destinatário o mesmo que o remetente viu.

| Chave | Padrão | O que exclui |
|---|---|---|
| Somente entes com RPPS vigente | **ligada** | os entes cujo regime vigente é o RGPS |
| Excluir RPPS com lançamento impossível | desligada | o ente inteiro, não só a linha |
| Excluir DAIR defasado há mais de 3 meses | desligada | quem parou de declarar |
| Excluir CRP não-válido há mais de 6 meses | desligada | irregularidade instalada |

A primeira vem ligada porque não é recorte, é correção de denominador. O CRP é
emitido ao **ente federativo**, não ao fundo, então `RPPS_CRP` cobre os 5.596
entes do país — praticamente 5.570 municípios mais 26 estados mais o DF. Só
2.132 mantêm RPPS vigente e 37 estão em extinção; 3.411 migraram para o RGPS.
Tratar ente federativo como sinônimo de RPPS, como este projeto fazia, inflava
todo denominador nacional em quase três vezes.

As outras três medem a atualidade do dado, não a sua correção. Quem entregou o
último DAIR há cinco meses não errou nada — apenas descreve uma situação mais
antiga. Se isso desqualifica o número depende da pergunta, e quem decide é quem
pergunta.

## A segunda fonte

O SICONFI, do Tesouro Nacional, entrou pela tabela de entes da federação —
`python -m cadprev siconfi`, uma requisição para o país inteiro. O que casa as
duas bases é o CNPJ, e ele casa em **5.594 dos 5.596** entes que o CADPREV
conhece: igualdade de chave, sem correspondência aproximada.

Com ela, esfera e capital deixaram de ser deduzidas do nome. A dedução era
frágil e errava: há sete municípios batizados com nome de unidade federativa —
Tocantins em Minas, Espírito Santo e Paraná no Rio Grande do Norte, Mato Grosso
na Paraíba —, e a regra antiga promovia todos a governo estadual. O país tem 27
governos estaduais; o painel contava 34. Agora a esfera vem declarada, e a
contagem fecha.

A tabela é **referência, não fonte de entes**: ela cobre 5.598 entidades, quatro
das quais o CADPREV não conhece, e uni-la ao índice acrescentaria fichas vazias e
mexeria no denominador nacional.

Veio de brinde a população de cada ente, que abre indicadores per capita ainda
não explorados.

### O Anexo 04, e o Nível A por outro caminho

O RREO Anexo 04 é o demonstrativo previdenciário do RPPS dentro da contabilidade
do ente. Ele traz o que este README documentava como inalcançável: a separação
dos recursos entre **fundo em capitalização**, **fundo em repartição** e **taxa
de administração**. Não por ativo — o CADPREV é que traz a carteira ativo a
ativo, sem o plano de cada um —, mas por total de fundo, que é o que a tela de
composição precisa.

Quem separa é o `cod_conta`, e ele é semântico: `InvestimentosDoRPPSPrevidenciario`
é a capitalização, `InvestimentosEAplicacoesFundoEmReparticao` é a repartição,
`InvestimentosEAplicacoesAdministracaoDoRPPS` é a taxa de administração.

A coleta é uma requisição por ente e por competência — a API exige `id_ente`,
não há varredura em bloco —, o que dá cerca de meia hora para os RPPS do país.
Municípios com menos de cinquenta mil habitantes entregam o **RREO Simplificado**,
sob outro nome de demonstrativo; consultar só o comum faz 45% dos RPPS parecerem
ausentes. A primeira medição deste projeto caiu exatamente nessa armadilha e
concluiu 53% de cobertura onde há 96%.

E quando as duas fontes discordam sobre o mesmo patrimônio, **as duas aparecem**.
Escolher uma esconderia o achado: são apurações independentes, com datas de
posição e critérios distintos, e a distância entre elas diz algo sobre o
cadastro. Em Vitória, junho de 2026, elas diferem em 0,18%.

#### Duas divergências que o painel não pode fabricar

A carga nacional de 17/09/2026 trouxe o Anexo 04 de 1.712 entes, e duas
armadilhas apareceram só ao medir a distribuição das diferenças:

**Ausência de saldo não é saldo zero.** 278 entes entregaram receitas e despesas
sem declarar o saldo das aplicações. Somar `investimentos or 0` transformava esse
silêncio em zero e acusava cada um deles de 100% de divergência contra a carteira
do CADPREV — um em cada seis RPPS, acusado de algo que a fonte nunca disse.

**Soma parcial não é soma.** Outros 451 declararam o saldo de um fundo e omitiram
o de outro que movimenta receita. O total do SICONFI ficava incompleto, e
confrontá-lo com a carteira inteira comparava um fragmento com o todo: Doutor
Maurício Cardoso/RS declarava só os R$ 75 mil da taxa de administração, e o
painel anunciava 99,8% de divergência contra os R$ 47 milhões da carteira.

Os dois casos saem do confronto e aparecem nomeados, em vez de virar divergência.
Com eles fora, sobram 983 entes confrontáveis: divergência típica de **0,73%**,
70% dentro de 5%. A distribuição fica na aba Qualidade, para que uma diferença
isolada possa ser lida contra o país — 4% parece muito até se saber quantos ficam
abaixo de cinco.

## O agendamento

A carga roda às segundas, 06:17 UTC. A competência **não** é deduzida do
calendário: o passo `python -m cadprev competencia` pergunta à API qual é a mais
recente já publicada, caminhando para trás e escolhendo a primeira que esteja
substancialmente cheia em relação à melhor vista.

A conta anterior — ano corrente, mês de três meses atrás — funcionava em nove
meses do ano e quebrava nos outros três: em janeiro pedia o mês de outubro do ano
corrente, uma competência que ainda não aconteceu. A carga voltaria vazia, a
guarda de endpoint essencial derrubaria o job, e o painel ficaria sem atualizar
de janeiro a março, todo ano.

O critério é relativo, e não um piso absoluto, porque com filtro de UF os volumes
caem duas ordens de grandeza — qualquer número fixo estaria errado num dos dois
casos. Em 16/09/2026 a competência 8 existia com 17 linhas no país inteiro:
publicá-la mostraria um patrimônio nacional de quase zero.

O que protege a base entre uma carga e outra:

- **Gravação transacional.** Um endpoint que falha desfaz o próprio trabalho; o
  que estava lá continua lá. Nunca fica meia varredura gravada.
- **Guarda de endpoints essenciais.** Sem CRP e sem carteira o job falha, e a
  versão publicada continua no ar.
- **Cache só do que deu certo.** O banco só é guardado quando a varredura fechou
  e os essenciais vieram.
- **Procedência à vista.** A aba Qualidade lista a data de ingestão de cada
  endpoint e marca os que ficaram para trás — a mistura de safras que a gravação
  transacional torna possível não pode ser invisível.

## Conformidade e amortização

Quatro endpoints do DRAA que o projeto não consumia entraram depois do
levantamento de `docs/plano-novas-fontes.md`.

O **plano de amortização** fecha uma lacuna que este README declarava aberta: o
`DRAA_FLUXO_ATUARIAL` dá totais projetados, não a curva; o
`DRAA_PLANO_AMORTIZACAO` dá saldo, juros e amortização ano a ano, até 2084 nos
planos mais longos. Com ele a pergunta que importa fica visível: o saldo devedor
chega a zero, e quando. Ourinhos/SP amortiza R$ 954 milhões até 2054 pagando
R$ 1,08 bilhão de juros — mais juros que principal —, e em 2026 a amortização é
negativa: o pagamento previsto não cobre nem os juros do ano, de modo que o saldo
cresce. Isso não aparece em nenhum total, só na curva, e por isso a tela avisa.

O **comparativo de receita** traz projetado, executado e a diferença por item de
fluxo, calculada na fonte. A diferença é **projetado menos executado** — sentido
conferido contra as 79.986 linhas nacionais, em que nenhuma destoa; no sentido
inverso, 31.236 destoariam, e um sinal trocado teria produzido trinta mil
acusações falsas.

A aba **Conformidade** mostra o que a SPREV registrou, com as palavras dela: a
fonte escreve "Situacao irregular" em quatro das nove situações que usa, e é
essa declaração que o painel exibe — não um juízo derivado de comparar a data de
preclusão com hoje. O escopo é estreito e a tela diz isso: em 17/09/2026 eram 724
itens em 222 entes, todos sobre segregação de massa.

Duas regras de leitura nasceram aqui:

- **Uma submissão por avaliação.** O DRAA pode ser reenviado, e a API devolve as
  versões convivendo — a substituída, a retificada e a válida, com o mesmo
  exercício e o mesmo ano projetado. Em 17/09/2026 isso atingia 176 dos 1.652
  entes com plano de amortização. Vale a mais recente, como no CRP.
- **Cópia exata não é apontamento novo.** 46 das 770 linhas de notificação são
  idênticas em todas as colunas; exibi-las duas vezes sugeriria dois
  apontamentos onde há um.

## Limites de aplicação: o teto é da classe, não do segmento

O painel acusava 390 dos 1.821 RPPS com carteira de exceder o limite legal.
Excedem 20.

A Resolução do CMN não fixa teto por segmento, e sim por classe de ativo. Em
17/09/2026 o segmento Renda Fixa reunia classes com teto de 5%, 20%, 80% e
100%, e o painel comparava o total do segmento com o teto de uma delas — a da
maior posição, porque era a primeira linha na ordem de valor. Um RPPS com 55,7%
em título público (teto de 100%) aparecia estourando um teto de 80% que é de
outra classe. Das 390 acusações, 371 eram assim; e um excesso real passava
despercebido.

Quem declara o teto de cada classe é a própria API, em `pc_cmn`, no registro de
cada ativo. **O projeto não mantém tabela de limites** — é assim que ele
acompanha a norma sem depender de alguém vir atualizá-lo quando ela muda. A
constante `NORMA_DOS_INVESTIMENTOS` existe só para nomear a norma na tela.

Pelo mesmo motivo o percentual é o que a fonte calcula (`pc_recursos`, que soma
100% em 1.820 dos 1.821 entes), e não uma derivação do painel. Ele só é refeito
quando alguma linha do ente foi excluída pela regra de impossibilidade
aritmética — aí o percentual da fonte passa a se referir a um total que a tela
não mostra mais, e a ficha diz qual dos dois está ali.

Uma distinção que a regra antiga apagava: ativo que a fonte classifica como
**não enquadrado na resolução** não é teto estourado, é ativo fora do rol. São
coisas diferentes e agora aparecem separadas.

**DPIN e Pró-Gestão não entram porque a API não os expõe**: `DPIN`,
`POLITICA_INVESTIMENTO`, `PRO_GESTAO` e variantes retornam 404, enquanto
endpoints conhecidos retornam 200 na mesma sondagem. O `DAIR_GOVERNANCA` traz a
certificação individual dos responsáveis (CPA-10 e afins, com validade), não a
certificação institucional do RPPS nem a estratégia-alvo. O teto por classe que
a API já declara é base melhor que as duas alternativas, e estava disponível
desde o começo.

## Militares

Só os Estados têm massa militar. Em 17/09/2026 ela aparecia em 26 dos 27
governos estaduais — Minas Gerais não entrega DRAA — e em nenhum dos 5.569
municípios. Onde existe, é de 14% (Tocantins) a 39% (Rio de Janeiro) da
população declarada, e a razão entre ativos e beneficiários não acompanha a
civil do mesmo ente: no Espírito Santo é 1,08 contra 0,61; no Ceará, 1,68 contra
0,61; no Rio Grande do Sul, 0,56 contra 0,43.

A separação obrigou a ler a fonte com mais cuidado do que "agrupar por tipo de
população". O CADPREV descreve as duas massas em campos diferentes:

| | papel do participante | carreira |
|---|---|---|
| Civil | `tp_populacao` (Servidores, Aposentados, Pensionistas) | `no_cat_populacao` |
| Militar | `no_cat_populacao` (ATIVOS, APOSENTADOS, PENSIONISTAS) | — |

No militar `tp_populacao` diz sempre "Militares". Agrupar as duas pelo mesmo
campo — que era o que o painel fazia — punha ativos, reserva e pensionistas
militares num balde único e os deixava fora tanto de ativos quanto de inativos:
para os 26 governos estaduais, um quinto a dois quintos da massa sumia da conta
que o painel mostrava. Hoje cada massa tem a sua tabela, os seus totais e a sua
razão, e o total do ente é a soma explícita das duas.

**Nomenclatura.** Militar não se aposenta: passa à reserva e depois à reforma. O
CADPREV grava o grupo como `MILITARES - APOSENTADOS`; o painel mostra "Reserva e
reforma" e registra o termo da fonte ao lado, porque uma substituição silenciosa
não se confere. É a única troca de termo do projeto, e ela é visível.

**Um fundo por massa.** A avaliação atuarial, o plano de amortização e o
comparativo de receita vêm separados por plano e por massa, e somá-los produzia
números que não existem em nenhum dos dois. Na aba Atuária isso juntava a
avaliação civil com a militar num único resultado atuarial, e somava os 14% do
custeio civil com os 10,5% do militar num plano de custeio que não é de ninguém. O Maranhão declara em 2026 dois planos de amortização — R$
39,5 bi civis e R$ 18,0 bi militares —, que o painel exibia como um saldo só. A
correção vale além dos militares: 51 entes tinham o ano repetido no plano de
amortização e 263 tinham o item de fluxo repetido no comparativo, quase todos
pela convivência entre plano Previdenciário e Financeiro.

**O fundo militar, onde ele existe.** O sistema de proteção social dos militares
não é plano de previdência: é de repartição, custeado pelo tesouro estadual, e
não tem contribuição patronal — o Estado recolhe a contribuição de ativos,
inativos e pensionistas (hoje 10,5% sobre o valor integral) e paga toda a
despesa. O DRAA confirma isso item a item. Dos 26 Estados com massa militar,
medidos no item 500000 (ativos garantidores dos compromissos do plano):

| | Estados | cobertura das provisões |
|---|---:|---|
| declaram **zero** ativo garantidor | 14 | 0% |
| declaram valor simbólico | 9 | abaixo de 1% — BA em 0,004%, SC em 0,02%, RJ em 0,05% |
| estão formando o fundo | 1 | RS, 5,1% |
| têm fundo constituído | 2 | AP, 31,5%; RR, 30,1% |

**Nenhum dos 26 omite o item.** Todos declaram um valor. É por isso que o zero
pode ser lido como zero sem violar a regra de que ausência não é zero: aqui não
existe ausência. O zero é a declaração de que não há fundo — e a tela escreve
isso, em vez de um travessão que sugeriria falta de informação. Quem não declara
o item aparece como "não declarado", um terceiro estado que não se confunde com
os outros dois.

A tela publica a **cobertura**, não um "tem fundo: sim ou não": o rótulo binário
poria a Bahia, com 0,004%, do mesmo lado do Amapá, com 31,5%. E não há cor nesses
números — zero aqui descreve o regime, não o desempenho. A tendência de novos
Estados constituírem fundos militares aparece sozinha: quando o ativo garantidor
deixar de ser zero, a cobertura sobe e a linha muda de leitura sem que nada
precise ser reprogramado.

**O que a fonte não separa, o painel não reparte.** O DAIR traz a carteira ativo
a ativo sem plano e sem massa: em 17/09/2026 o campo de plano vinha vazio nas
59.843 linhas da base nacional. Não existe patrimônio "do fundo militar" nessa
fonte — o que existe é o ativo garantidor declarado no DRAA, que é outra coisa e
aparece como tal. O SICONFI cobre parte do vão: o Anexo
04 do RREO tem um bloco militar próprio — contribuições, despesas com inativos e
pensionistas, e o resultado entre os dois. Dos 21 Estados cujo Anexo 04 estava
coletado em 17/09/2026, 20 traziam o bloco; o Rio Grande do Sul entregou o anexo
sem ele. A aba nomeia quem ficou sem a linha em vez de tratar a ausência como
zero — o SICONFI nomeia as contas com os erros de digitação dele
(`TotalDasContribucoesDosMilirares`), e o painel os repete, porque corrigi-los
seria deixar de encontrar a linha.

**A comparação.** Município não tem militar, então a comparação militar só cabe
entre Estados. Isso não precisou de exceção: o indicador vem indefinido para
quem não tem a massa, e a regra dos três declarantes que já regia todo o resto
mantém os grupos municipais sem mediana militar. No comparativo de um município
a linha nem aparece — indicador sem assunto não é indicador sem dado.

## Carteira detalhada, e a competência que os agregados escolhem

A aba Carteira responde "como está a carteira". A tela detalhada responde "o
que exatamente há nela": todos os ativos declarados, os totais de cada segmento
e de cada classe, e a posição de meses anteriores ao lado da atual. Vem em
arquivo próprio por ente, carregado só quando alguém a abre — um RPPS grande
declara centenas de ativos, e embutir isso na ficha faria toda visita pagar o
custo de uma tela que poucas visitas abrem.

Guardar mais de uma competência destapou um defeito latente: os agregados liam
`dair_carteira` inteira, sem filtrar mês. Com uma competência no banco isso
passava; com três, o patrimônio nacional seria quase o triplo do real e
cresceria a cada carga sem que um centavo tivesse sido aplicado. Hoje a ficha, o
agregado nacional e a amostra do RREO usam a competência mais recente, e a régua
de impossibilidade roda uma competência por vez — o consenso sobre o tamanho de
um fundo é de um mês.

## Certificação de quem responde pelos recursos

O `DAIR_GOVERNANCA` traz uma linha por pessoa **e por certificação**. Quem tem
duas aparece duas vezes, e é comum ter uma CPA vencida ao lado de uma vigente —
nesse caso o requisito de regularidade está atendido. Ler linha a linha
acusaria de irregular quem está em ordem, e por isso a leitura é por pessoa: o
alerta só aparece para quem **não tem nenhuma** certificação dentro da validade,
entre quem ainda está em exercício. Certificação vencida de quem já deixou o
colegiado não diz nada sobre a gestão de hoje.

## Provisão matemática: o atuário e o contador

O DRAA traz o compromisso avaliado pelo atuário. O Anexo I-AB da Declaração de
Contas Anuais, no SICONFI, traz o mesmo compromisso registrado no balanço do
ente — outro profissional, outra norma, outra data de corte. Os dois ficam lado
a lado na aba Atuária.

**O total vem da fonte, nunca da soma das partes.** As contas `2.2.7.2.2` são
redutoras e a API as publica com sinal positivo: em Vitória somam R$ 4,8 bi que
não entram no total de R$ 5,66 bi declarado em `2.2.7.2`. Somar componentes
daria um passivo que o balanço não reconhece.

**O confronto só acontece no par que descreve a mesma data.** O DRAA do
exercício N descreve a posição de 31/12 de N−1; o balanço do exercício N fecha
em 31/12 de N. O par correto é DRAA(N) com DCA(N−1) — fora dele os dois números
aparecem e a diferença não, porque subtrair avaliações de datas diferentes
mediria o tempo entre elas, não a divergência entre as apurações.

Nenhuma das duas corrige a outra. O comparativo entre RPPS usa a avaliação
atuarial, que é a apuração própria do regime; o balanço entra porque divergir
dele é informação sobre o cadastro.

## O que ainda falta

- **A API do CADPREV está fora do ar.** Desde pelo menos 17/09/2026 ela lista um
  único endpoint (`/RPPS_REGIME_PREVIDENCIARIO`), e mesmo esse responde 500 com
  "Falha na autenticação" da própria origem; os outros 38 retornam 404. O painel
  atravessa isso republicando o que já tem e dizendo na tela que a fonte não
  responde — mas nenhum dado novo do CADPREV entra enquanto durar. O SICONFI
  continua respondendo normalmente.
- **Endpoints sem mapa de campos.** Dezenove dos 39 têm mapa; `python -m cadprev
  endpoints` marca quais. Credenciamento, atas e notificações de retificação
  abririam telas novas.
- **Histórico.** A ingestão é por competência; comparar exercícios depende de
  ingerir cada um e de telas que ainda não existem.
- **Carteira por fundo (Nível A).** Só seria possível reconstruindo a posição a
  partir do histórico de aplicações e resgates, que carregam `no_fundo_constituido`.
  Frágil, e o resultado não poderia ser apresentado como posição declarada.

## Testes

```bash
python -m unittest discover -s tests
```

Cobrem a resolução de campos nas duas convenções, a conversão de tipos no formato
brasileiro, os dois níveis de decomposição por fundo, a classificação por grupos e o
pipeline inteiro sobre as amostras sintéticas.

## Documentação

- [`docs/api-cadprev.md`](docs/api-cadprev.md) — catálogo técnico da API: contrato,
  paginação, parâmetros e os 39 endpoints por família
- [`docs/anteprojeto-painel-cadprev.html`](docs/anteprojeto-painel-cadprev.html) —
  anteprojeto visual que originou o painel

## Como contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md). As frentes mais úteis hoje são confirmar os nomes
dos campos da API, ampliar a cobertura de endpoints e revisar a interpretação dos dados
por quem conhece o assunto de dentro.

## Agradecimento

À **Subsecretaria dos Regimes Próprios de Previdência Social** pela disponibilização dos
dados do CADPREV em formato aberto e sem exigência de credencial. É essa decisão que torna
possível qualquer leitura independente como esta — inclusive a que aponta problemas.

## Licença

[MIT](LICENSE).
