# Entregas

Resultados prontos, versionados para quem só quer o arquivo. São gerados: cada
um pode ser refeito da fonte pelos scripts em `ferramentas/`.

## Letras Financeiras — maio/2024

| Arquivo | O quê |
| --- | --- |
| `letras_financeiras_maio_2024.xlsx` | quatro abas: movimento do mês, posições completas, resumo por emissor, e as fontes com seus limites |
| `lf-negociadas-maio-2024.csv` | só as 3.130 linhas com movimento, separador `;`, UTF-8 com BOM — o GitHub mostra como tabela, sem baixar nada |
| `lf-rpps-exposicao-maio-2024.csv` | as 2.669 LF que algum RPPS alcança, direta ou indiretamente |

Fonte: CVM, Dados Abertos, CDA (Composição e Diversificação das Aplicações),
bloco 5, competências 2024-05 e 2024-04. Gestor e administrador: o registro de
fundos e classes da RCVM 175 mais o cadastro anterior. Extraído em 07/10/2026.

**Leia antes de usar:** só 17,5% dos fundos preenchem as colunas de compra e
venda da CDA. A coluna `Evidencia_da_Negociacao` diz, linha a linha, se a
compra foi declarada pelo fundo (499 linhas) ou se é uma posição que apareceu
(2.284) ou cresceu (347) entre 30/04 e 31/05. A aba "Fontes e limites" do xlsx
detalha coluna por coluna, e `ferramentas/letras-financeiras/LEIA-ME.md`
registra o que não existe publicamente — data exata da compra, ISIN, e taxas da
ANBIMA para meses passados.

## Que LF os RPPS alcançam

A aba "RPPS - exposicao a LF" responde por qual fundo cada RPPS chega a cada
LF. **R$ 17,5 bilhões de exposição, 1.509 RPPS, 2.669 LF.**

| Via | LF | Exposição |
| --- | --- | --- |
| Direta — o RPPS declarou a LF no DAIR | 84 | R$ 1,37 bi |
| Por um ou dois fundos | 2.585 | R$ 16,17 bi |

Dois avisos que mudam a leitura, e que a própria aba repete no topo:

1. **As datas não casam.** A LF é da CDA de maio/2024; a carteira dos RPPS é do
   último DAIR de cada um, competência 2026-06 — a API do CADPREV está fora do
   ar desde 22/09/2026. São dois anos de distância.
2. **Exposição não é compra.** O RPPS comprou cotas de um fundo que tinha
   aquela LF; quem decidiu comprar a LF foi o gestor do fundo. O valor é
   rateado pelo patrimônio, nunca somado.

Refazer para outro mês:

```sh
sh ferramentas/letras-financeiras/baixar.sh /tmp/lf 202410 202409
python3 ferramentas/letras-financeiras/planilha.py /tmp/lf \
        ferramentas/letras-financeiras /tmp/lf/lf-outubro.xlsx 202410
python3 ferramentas/letras-financeiras/conferir.py /tmp/lf/lf-outubro.xlsx
```
