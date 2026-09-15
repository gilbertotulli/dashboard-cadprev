# Como contribuir

Obrigado pelo interesse. Este projeto reapresenta dados públicos sobre previdência de
entes federativos reais, então o padrão aqui é conservador: **na dúvida entre estimar e
dizer que não se sabe, diz-se que não se sabe.**

## As frentes mais úteis hoje

### 1. Confirmar os nomes dos campos da API

É a contribuição de maior impacto e a mais fácil de fazer. Quem tem acesso de rede à API
resolve com um comando:

```bash
python -m cadprev inspect DAIR_CARTEIRA --uf ES --salvar --override
```

Isso grava o observado em `docs/schema-observado/` e imprime uma sugestão para
`fieldmap.local.json`. Se os nomes confirmados valem para todos, abra um PR alterando os
candidatos em `cadprev/fieldmap.py` e inclua o arquivo de `docs/schema-observado/` como
evidência.

**A pergunta em aberto de maior peso:** `DAIR_CARTEIRA` expõe o plano do ativo? Se sim,
o painel passa do Nível B para o Nível A e a carteira se decompõe entre capitalizado,
repartição simples e taxa de administração. Veja `cadprev/fundos.py`.

### 2. Revisar a interpretação dos dados

Quem trabalha com RPPS por dentro enxerga erro de leitura que nenhum teste pega. Se um
número da tela diverge do que o CADPREV mostra, abra uma issue com o CNPJ, a competência
e o valor esperado — isso vale mais do que qualquer refatoração.

### 3. Ampliar a cobertura

Dos 22 endpoints do catálogo, nem todos têm mapa de campos. `python -m cadprev endpoints`
marca com `·` os que já têm.

## Regras da casa

- **Sem dependências externas.** O pacote usa só a biblioteca padrão, e o painel não tem
  etapa de build. Quem clona roda. Uma dependência nova precisa de justificativa forte.
- **Nada de eixo duplo.** Séries na mesma unidade dividem a mesma escala; a distância
  entre as curvas é informação.
- **Não inventar número.** Se um recorte não pode ser derivado da API, a tela diz isso.
  Rateio sem base no dado não entra, nem com ressalva.
- **Nunca misturar origens.** O banco registra se foi preenchido com dados reais ou
  com o conjunto sintético, e a construção do painel **para** se encontrar as duas.
  Um painel carimbado como real exibindo números inventados é o erro mais caro que
  este projeto pode cometer.
- **Ausência não é zero.** Competência sem declaração vira nulo, não zero: uma diz
  "não informou", a outra diz "não gastou".
- **Falhar alto.** Campo obrigatório ausente interrompe a ingestão com as chaves reais na
  mensagem. Coluna de nulos descoberta semanas depois é pior do que erro na hora.
- **Procedência junto do número.** Todo cartão mostra o endpoint de origem; toda ingestão
  registra filtros e resolução de campos na tabela `execucao`.
- **Português no código.** Nomes, docstrings e commits em português, como o resto do
  projeto e o vocabulário do domínio.

## Antes de abrir o PR

```bash
python -m unittest discover -s tests
python -m cadprev demo          # o painel precisa continuar de pé
```

Se a mudança altera algo visível, diga na descrição do PR o que olhar na tela.

Correção de bug ganha teste de regressão. Os que já existem contam a história do
projeto, e vale lê-los antes de mexer na agregação:

- São Paulo e Rio de Janeiro caíam como RPPS estaduais, porque o nome do município
  coincide com o do estado.
- Todo CRP vencido era contado como regular, porque "VÁLIDO" e "VENCIDO" começam com
  a mesma letra.
- Metade das linhas do DIPR é base de cálculo, não dinheiro. Somá-las inflava o caixa
  de Vitória de R$ 464 milhões para R$ 1,4 bilhão.
- O código 109001 do fluxo atuarial é base de cálculo dentro da faixa das receitas.
  O teste que pega isso confere que a composição fecha com o total declarado pela
  própria API.
- Os campos `ds_situacao` e `tp_crp` estão trocados em relação à documentação da API,
  então a leitura classifica pelo valor e o teste cobre as duas ordens.

## Conduta

Seja direto e gentil. Discussão sobre dado público é discussão técnica, não disputa.
