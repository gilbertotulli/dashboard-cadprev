# Letras Financeiras, a partir dos dados abertos da CVM

Ferramenta avulsa, fora do painel. Monta uma planilha com as Letras Financeiras
que os fundos de investimento brasileiros negociaram num mês: emissor,
comprador, taxa contratada, vencimento, quantidade e valor.

Está aqui porque RPPS investem em LF e a pergunta tende a voltar. Não é parte
do pipeline do CADPREV e nada no painel depende dela.

## Rodar

```sh
sh baixar.sh /tmp/lf 202405 202404          # ~50 MB
python3 planilha.py /tmp/lf . /tmp/lf/letras_financeiras.xlsx
python3 conferir.py /tmp/lf/letras_financeiras.xlsx
```

Dois meses: a evidência de compra depende da comparação com o anterior.
`planilha.py` precisa de `openpyxl`.

## A fonte, e onde ela para

A LF está no **bloco 5** da CDA (`cda_fi_BLC_5_AAAAMM.csv`), em "Depósitos a
prazo e outros títulos de IF" — não no bloco 4, de títulos privados, que é onde
se procuraria. O bloco 5 traz emissor com CNPJ, vencimento, indexador,
percentual do índice, cupom, taxa prefixada, posição final e, para parte dos
fundos, as aquisições e vendas **do próprio mês**.

**Só 17,5% dos fundos preenchem as colunas de negociação.** Em maio/2024 foram
499 linhas com aquisição declarada. Por isso cada linha recebe uma evidência:

| Evidência | Maio/2024 |
| --- | --- |
| Aquisição declarada pelo fundo | 499 |
| Posição nova (não existia no mês anterior) | 2.284 |
| Posição aumentada no mês | 347 |

As duas medidas concordam onde ambas existem: das 497 aquisições declaradas
comparáveis, 474 (95%) também aparecem como posição nova.

## O que não existe publicamente

- **Data exata da compra.** A CDA é mensal; a data da operação está no registro
  da B3/CETIP, que não é público.
- **Código do papel e ISIN.** A CVM só os publica no bloco 4. Sem eles não há
  como casar papel a papel com as taxas da ANBIMA.
- **LF sênior × subordinada.** A CDA diz só "Letra Financeira"; `TP_APLIC` é
  idêntico nas 43.949 linhas.
- **Registro de oferta na CVM.** Verificado: LF não aparece em
  `oferta_distribuicao.csv` (48.944 linhas) nem em `oferta_resolucao_160.csv`
  (14.772). LF é captação bancária registrada na B3/CETIP.
- **Taxas indicativas da ANBIMA para meses passados.** A ANBIMA Data mostra uma
  janela de cerca de cinco dias; o histórico fica no ANBIMA Feed, por
  assinatura. A API (`data-api.prd.anbima.com.br/web-bff/v1/letras-financeiras`)
  exige token. E as taxas são por classe e faixa de prazo, não por papel.

## Duas armadilhas dos dados

**O nome do emissor é texto livre.** O CNPJ do Bradesco aparece como
"BRADESCO" (2.467×), "BANCO BRADESCO S.A." (2.074×), "BCO BRADESCO SA" (225×)
e mais cinco grafias, uma delas `BANCO_BRADESCO_SA________`. A chave é o CNPJ.
A grafia consolidada sai de `nomes_de_emissor`: entre as grafias que cobrem 60%
das ocorrências, vence a mais completa que passe num teste de nome limpo. Nem a
mais frequente (dá "BANCO BTG PACTU", cortado em quinze caracteres) nem a mais
longa (dá o lixo com sublinhados) servem sozinhas. A coluna
`Emissor_Como_Declarado` guarda o que o fundo escreveu.

**O gestor exige dois cadastros.** A Resolução CVM 175 partiu o fundo em fundo
e classe, e a CDA usa o CNPJ da *classe*. O `cad_fi.csv` sozinho alcança 7,3%
dos fundos; com o `registro_fundo_classe.zip`, 86,8%.

## Conferência

`conferir.py` refaz cada fórmula lendo as células que ela aponta e checa que os
blocos por emissor cobrem as posições exatamente uma vez, sem buraco nem
sobreposição, cada um com um CNPJ só. O resumo soma intervalos exatos em vez de
`SUMIF` sobre a coluna inteira: com 102 emissores e 43.949 linhas, o `SUMIF`
faria dezenas de milhões de comparações de texto.

Em maio/2024 as somas reproduzem o CSV cru: R$ 457.323.138.853,90 contra
R$ 457.323.138.853,91 — um centavo de arredondamento de ponto flutuante.
