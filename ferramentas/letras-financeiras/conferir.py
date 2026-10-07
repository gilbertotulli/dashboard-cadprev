# -*- coding: utf-8 -*-
"""Confere a planilha sem LibreOffice.

O LibreOffice deste contêiner não carrega arquivo nenhum — nem um CSV de duas
linhas —, então recalc.py não roda. O risco que ele pegaria é fórmula que não
avalia; o risco real aqui é outro: intervalo errado. Uma soma de bloco que
começa uma linha cedo soma o emissor anterior junto, avalia limpo e dá o número
errado. Isto refaz cada fórmula lendo as células que ela aponta.
"""
import re
import sys

import openpyxl

ARQ = sys.argv[1]
INTERVALO = re.compile(r"^=SUM\('([^']+)'!([A-Z]+)(\d+):([A-Z]+)(\d+)\)$")
LOCAL = re.compile(r"^=SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)$")

wb = openpyxl.load_workbook(ARQ)
valores = {}
for ws in wb.worksheets:
    valores[ws.title] = {
        (c.column_letter, c.row): c.value
        for linha in ws.iter_rows() for c in linha
        if isinstance(c.value, (int, float))}

erros = []
somas = {}
conferidas = 0
cobertura = {}

for ws in wb.worksheets:
    for linha in ws.iter_rows():
        for c in linha:
            v = c.value
            if not isinstance(v, str) or not v.startswith("="):
                continue
            m = INTERVALO.match(v)
            alvo, col = None, None
            if m:
                alvo, col, ini, _c2, fim = m.group(1), m.group(2), int(m.group(3)), m.group(4), int(m.group(5))
                if m.group(2) != m.group(4):
                    erros.append((ws.title, c.coordinate, "colunas diferentes", v))
                    continue
            else:
                m2 = LOCAL.match(v)
                if not m2:
                    if not v.startswith("=IF("):
                        erros.append((ws.title, c.coordinate, "fórmula não reconhecida", v))
                    continue
                alvo, col, ini, fim = ws.title, m2.group(1), int(m2.group(2)), int(m2.group(4))
                if m2.group(1) != m2.group(3):
                    erros.append((ws.title, c.coordinate, "colunas diferentes", v))
                    continue
            if alvo not in valores:
                erros.append((ws.title, c.coordinate, "aba inexistente: " + alvo, v))
                continue
            soma = sum(valores[alvo].get((col, r), 0) or 0 for r in range(ini, fim + 1))
            conferidas += 1
            cobertura.setdefault((alvo, col), set()).update(range(ini, fim + 1))
            somas[(ws.title, c.coordinate)] = soma

# As somas de bloco do resumo têm de cobrir cada linha da aba de posições
# exatamente uma vez. Sobreposição somaria um emissor duas vezes; buraco
# deixaria um de fora, e o TOTAL ainda fecharia se os dois erros se anulassem.
resumo = wb["Resumo por emissor"]
pos = wb["Posicoes 31-05-2024"]
ultima_pos = pos.max_row - 3   # 2 linhas de folga + a linha de TOTAL
blocos = []
for n in range(2, resumo.max_row + 1):
    f = resumo.cell(row=n, column=4).value
    if isinstance(f, str):
        m = INTERVALO.match(f)
        if m:
            blocos.append((int(m.group(3)), int(m.group(5))))
blocos.sort()
print("blocos no resumo:", len(blocos))
anterior = 1
for ini, fim in blocos:
    if ini != anterior + 1:
        erros.append(("Resumo", "", "buraco ou sobreposição em %d (esperado %d)"
                      % (ini, anterior + 1), ""))
    anterior = fim
if blocos:
    print("cobrem as linhas %d a %d da aba de posições" % (blocos[0][0], anterior))
    if blocos[0][0] != 2:
        erros.append(("Resumo", "", "o primeiro bloco não começa na linha 2", ""))
    if anterior != ultima_pos:
        erros.append(("Resumo", "", "o último bloco termina em %d, não em %d"
                      % (anterior, ultima_pos), ""))

# Cada CNPJ do resumo tem de bater com o CNPJ de todas as linhas do seu bloco.
col_cnpj = None
for i, c in enumerate(pos[1], start=1):
    if c.value == "Emissor_CNPJ":
        col_cnpj = i
for n in range(2, resumo.max_row + 1):
    f = resumo.cell(row=n, column=4).value
    cnpj = resumo.cell(row=n, column=2).value
    if not isinstance(f, str):
        continue
    m = INTERVALO.match(f)
    if not m:
        continue
    for r in (int(m.group(3)), int(m.group(5))):
        na_aba = pos.cell(row=r, column=col_cnpj).value
        if na_aba != cnpj:
            erros.append(("Resumo", "linha %d" % n,
                          "bloco aponta para %s, linha diz %s" % (cnpj, na_aba), f))

print("fórmulas conferidas:", conferidas)
if erros:
    print("\nERROS (%d):" % len(erros))
    for e in erros[:20]:
        print("  ", e)
    sys.exit(1)
print("\nnenhum erro: toda soma aponta para o intervalo certo, os blocos cobrem")
print("as posições uma única vez, e cada bloco contém só o seu emissor.")
