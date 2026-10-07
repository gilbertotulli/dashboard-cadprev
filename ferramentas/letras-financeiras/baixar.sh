#!/bin/sh
# Baixa o que a planilha de Letras Financeiras consome. Um argumento: a pasta
# de trabalho. Dois meses da CDA porque a evidência de compra depende da
# comparação com o mês anterior.
#
#   sh baixar.sh /tmp/lf 202405 202404
set -e
BASE="${1:?pasta de trabalho}"
MES="${2:?competência, aaaamm}"
ANTERIOR="${3:?mês anterior, aaaamm}"
mkdir -p "$BASE/cda"
for m in "$MES" "$ANTERIOR"; do
  echo "CDA $m"
  curl -sS --fail -o "$BASE/cda/cda_$m.zip" \
    "https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/cda_fi_$m.zip"
done
echo "cadastro de fundos (anterior à RCVM 175)"
curl -sS --fail -o "$BASE/cda/cad_fi.csv" \
  "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv"
echo "registro de fundos e classes (RCVM 175)"
curl -sS --fail -o "$BASE/cda/reg.zip" \
  "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"
echo "pronto em $BASE"
