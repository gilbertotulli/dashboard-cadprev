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
| `endpoints` | o catálogo dos 22 recursos da API |

## Como está montado

```
cadprev/        ingestão e agregação (Python, sem dependências)
  endpoints.py    catálogo dos 22 recursos da API
  fieldmap.py     ⚠ mapeamento campo lógico → chave real da API
  client.py       GET paginado, com repetição e modo offline
  store.py        SQLite + procedência de cada ingestão
  fundos.py       separação por natureza do fundo (Níveis A e B)
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

## A pendência aberta: os nomes dos campos

O levantamento que originou o projeto foi feito **sem acesso de rede** aos domínios
`*.gov.br`. O contrato da API (caminhos, filtros, envelope `{data, count, limit}`,
paginação por `offset`) veio do cliente R [`marcosfs2006/ADPrev`](https://github.com/marcosfs2006/ADPrev)
e dos conjuntos de dados abertos equivalentes. **Os nomes exatos dos campos de resposta
não foram confirmados.**

Em vez de espalhar palpites pelo código, a incerteza está isolada em
[`cadprev/fieldmap.py`](cadprev/fieldmap.py). Cada campo lógico declara candidatos nas
duas convenções observadas nos artefatos da SPREV, a resolução acontece contra o primeiro
registro de cada ingestão, e falta de campo obrigatório **falha alto, listando as chaves
que a API devolveu** — em vez de gravar uma coluna de nulos que ninguém percebe.

Quem tiver acesso de rede fecha isso com um comando:

```bash
python -m cadprev inspect DAIR_CARTEIRA --uf ES --salvar --override
```

A correção vai para `fieldmap.local.json` (ignorado pelo git) ou, quando valer para todos,
para `cadprev/fieldmap.py`. **Contribuições aqui são as mais valiosas do projeto.**

## A separação por natureza do fundo

Investigada especificamente, com resultado misto:

- **Confirmado.** A dimensão de plano existe e é nomeada `FINANCEIRO` (repartição simples)
  e `PREVIDENCIÁRIO` (capitalização), em `DIPR.plano_segreg`,
  `RPPS_ALIQUOTA.plano_segregacao` e `DRAA_SEGREGACAO_MASSA`. Caixa e atuária já se
  separam entre capitalizado e não capitalizado.
- **Não confirmado.** O arquivo de dados abertos da carteira do DAIR tem 15 colunas e
  nenhuma identifica plano ou fundo. A informação existe na origem — os DAIR em PDF do
  CADPREV mostram os recursos vinculados aos planos e à taxa de administração, e a
  Portaria MTP nº 1.467/2022 exige que a taxa de administração seja mantida segregada —
  mas não se sabe se o endpoint `DAIR_CARTEIRA` a expõe.

O painel opera em dois níveis, escolhidos pelo que a API de fato entregou e **declarados
na tela**:

| Nível | Quando | O que mostra |
| --- | --- | --- |
| **A** | o endpoint expõe o plano do ativo | decomposição de três vias: capitalizado, repartição simples e taxa de administração |
| **B** | não expõe (o que se sabe hoje) | classifica o **RPPS**, não o ativo: sem segregação de massa a carteira inteira é capitalizada; com segregação, fica *não decomposta* |

No Nível B o projeto **não rateia** a carteira entre planos. Não há base no dado para
isso, e o número resultante sairia daqui para dentro de um ofício.

## O que não vem pela API

ISP (Indicador de Situação Previdenciária), MSC (Matriz de Saldos Contábeis), acordos de
parcelamento de débitos e o enquadramento de fundos existem como planilha em dados
abertos, não como endpoint. A marcação de capitais também não vem da API: depende de
[`data/capitais.csv`](data/capitais.csv), mantido aqui.

## O que ainda falta

Registrado aqui para não virar ausência silenciosa:

- **Decomposição do DIPR por origem e destino.** O anteprojeto prevê as tabelas
  "de onde vem o dinheiro" e "para onde vai", que abrem os blocos 10 e 11 do DIPR.
  Elas não entraram porque isso exigiria mapear dezenas de campos (`ing_*`, `desp_*`)
  cujos nomes reais não estão confirmados — seriam dezenas de palpites de uma vez. A
  aba Caixa mostra hoje os totais e o resultado, que vêm de campos únicos. Assim que o
  `inspect` rodar contra a API, essas tabelas são a primeira ampliação natural.
- **Endpoints sem mapa de campos.** Onze dos 22 têm mapa; `python -m cadprev endpoints`
  marca quais.
- **Histórico.** A ingestão é por competência; comparar exercícios ainda depende de
  ingerir cada um e de telas que ainda não existem.

## Testes

```bash
python -m unittest discover -s tests
```

Cobrem a resolução de campos nas duas convenções, a conversão de tipos no formato
brasileiro, os dois níveis de decomposição por fundo, a classificação por grupos e o
pipeline inteiro sobre as amostras sintéticas.

## Documentação

- [`docs/api-cadprev.md`](docs/api-cadprev.md) — catálogo técnico da API: contrato,
  paginação, parâmetros e os 22 endpoints por família
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
