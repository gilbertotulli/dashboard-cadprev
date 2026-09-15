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

## O que ainda falta

- **A projeção atuarial ano a ano.** `DRAA_FLUXO_ATUARIAL` não é série temporal —
  dá totais projetados, não a curva. A curva está nos arquivos de dados abertos da
  SPREV. Há, porém, uma série temporal ainda não consumida na API:
  `DRAA_PLANO_AMORTIZACAO`, com saldo e amortização ano a ano.
- **Endpoints sem mapa de campos.** Onze dos 39 têm mapa; `python -m cadprev
  endpoints` marca quais. Governança, credenciamento e notificações do DAIR e do
  DRAA abririam telas novas.
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
