/* A planilha exportada tem de abrir de verdade, não só "gerar sem erro".
 *
 * web/planilha.js escreve XLSX à mão — ZIP sem compressão por cima de um CRC-32
 * hand-rolled, sem biblioteca nenhuma (ver o cabeçalho do arquivo para o
 * porquê). É exatamente o tipo de código que passa limpo e produz um arquivo
 * corrompido: um offset errado no diretório central não dá exceção em lugar
 * nenhum, só um Excel dizendo "não é possível abrir".
 *
 * A prova aqui é cruzada: o arquivo que este teste gera é lido de volta por
 * `openpyxl`, um leitor independente e rigoroso com a especificação OOXML —
 * não a mesma lógica que escreveu, então um erro simétrico (escrever errado
 * e ler errado do mesmo jeito) não escapa como passaria num teste só em JS.
 *
 * As funções são extraídas do próprio web/planilha.js por `(0, eval)`, não
 * copiadas: testar uma cópia testaria a cópia.
 *
 * Rode com:
 *
 *     node tests/planilha.node.mjs
 */
import fs from "fs";
import os from "os";
import path from "path";
import { execFileSync } from "child_process";

const R = new URL("..", import.meta.url).pathname;
const src = fs.readFileSync(R + "web/planilha.js", "utf8");
// planilha.js termina com `(typeof window !== "undefined" ? window : global)`
// — sem `window`, o módulo se pendura em `global.Planilha` sozinho.
(0, eval)(src);
const P = global.Planilha;

let falhas = 0;
function afirmar(cond, mensagem) {
  if (!cond) { falhas++; console.error("FALHOU: " + mensagem); }
}

// --- CRC-32 contra o vetor de teste conhecido do padrão -------------------
{
  const bytes = new TextEncoder().encode("123456789");
  afirmar(P.crc32(bytes) === 0xcbf43926,
    "crc32('123456789') devia ser 0xcbf43926, deu " + P.crc32(bytes).toString(16));
}

// --- CSV: separador, decimal com vírgula, aspas só quando precisa --------
{
  const csv = P.csvDeLinhas([
    ["Ativo", "Valor total", "Quantidade"],
    ["NTN-B 15/08/2060", { v: 1234567.891, casas: 2 }, { v: 48636436.878686, casas: 6 }],
    ['Fundo "Especial"; Ltda', 0, null]
  ]);
  afirmar(csv.charCodeAt(0) === 0xfeff, "CSV tem de abrir com o BOM UTF-8");
  const linhas = csv.slice(1).split("\r\n");
  afirmar(linhas[0] === "Ativo;Valor total;Quantidade", "cabeçalho com ; : " + linhas[0]);
  afirmar(linhas[1] === "NTN-B 15/08/2060;1234567,89;48636436,878686",
    "decimal com vírgula e casas corretas: " + linhas[1]);
  afirmar(linhas[2] === '"Fundo ""Especial""; Ltda";0;',
    "aspas duplicadas e célula vazia para null: " + linhas[2]);
}

// --- XLSX: o arquivo abre no openpyxl e os valores batem -----------------
{
  const abas = [{
    nome: "Todos os ativos",
    larguras: [30, 14, 12],
    linhaCongelada: 1,
    linhas: [
      [{ v: "Ativo", s: "cabecalho" }, { v: "Valor total", s: "cabecalho" },
       { v: "Quantidade", s: "cabecalho" }],
      ["NTN-B 15/08/2060 & Cia <especial>", { v: 1234567.89, s: "dinheiro" },
       { v: 48636436.878686, s: "qtd" }],
      ["Texto com 'aspas' e \"mais aspas\"", { v: 0, s: "dinheiro" }, { v: 3, s: "inteiro" }]
    ]
  }];
  const bytes = P.xlsxDeAbas(abas);
  afirmar(bytes instanceof Uint8Array && bytes.length > 0, "xlsxDeAbas devolve bytes não vazios");
  // Assinatura de .zip: "PK\x03\x04" no início do primeiro arquivo local.
  afirmar(bytes[0] === 0x50 && bytes[1] === 0x4b, "começa com a assinatura de ZIP (PK)");

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "planilha-teste-"));
  const arquivo = path.join(tmp, "teste.xlsx");
  fs.writeFileSync(arquivo, Buffer.from(bytes));

  const script = `
import json, sys, openpyxl
wb = openpyxl.load_workbook(sys.argv[1])
ws = wb["Todos os ativos"]
linhas = [[c.value for c in linha] for linha in ws.iter_rows()]
print(json.dumps({"titulo": wb.sheetnames, "linhas": linhas,
                  "freeze": ws.freeze_panes,
                  "larguras": [ws.column_dimensions[l].width for l in ("A","B","C")]}))
`;
  let saida;
  try {
    saida = execFileSync("python3.13", ["-I", "-c", script, arquivo], { encoding: "utf8" });
  } catch (e) {
    falhas++;
    console.error("FALHOU: openpyxl não conseguiu abrir o .xlsx gerado");
    console.error((e.stdout || "") + (e.stderr || ""));
    saida = null;
  }
  if (saida) {
    const lido = JSON.parse(saida);
    afirmar(JSON.stringify(lido.titulo) === JSON.stringify(["Todos os ativos"]),
      "nome da aba preservado: " + lido.titulo);
    afirmar(lido.linhas[0][0] === "Ativo", "cabeçalho lido de volta: " + lido.linhas[0][0]);
    afirmar(lido.linhas[1][0] === "NTN-B 15/08/2060 & Cia <especial>",
      "texto com & < > sobrevive ao escape XML: " + lido.linhas[1][0]);
    afirmar(lido.linhas[1][1] === 1234567.89, "valor em dinheiro preservado: " + lido.linhas[1][1]);
    afirmar(Math.abs(lido.linhas[1][2] - 48636436.878686) < 1e-6,
      "quantidade com seis casas preservada: " + lido.linhas[1][2]);
    afirmar(lido.linhas[2][0] === "Texto com 'aspas' e \"mais aspas\"",
      "aspas simples e duplas sobrevivem: " + lido.linhas[2][0]);
    afirmar(lido.freeze === "A2", "cabeçalho congelado: " + lido.freeze);
    afirmar(lido.larguras[0] === 30, "largura da coluna A: " + lido.larguras[0]);
  }
  fs.rmSync(tmp, { recursive: true, force: true });
}

// --- XLSX: várias abas, cada uma com seu próprio r:id ----------------------
{
  const abas = [
    { nome: "Agrupado", linhas: [["a"]] },
    { nome: "Lista", linhas: [["b"]] }
  ];
  const bytes = P.xlsxDeAbas(abas);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "planilha-teste-"));
  const arquivo = path.join(tmp, "duas-abas.xlsx");
  fs.writeFileSync(arquivo, Buffer.from(bytes));
  try {
    const saida = execFileSync("python3.13", ["-I", "-c",
      "import openpyxl,sys; print(openpyxl.load_workbook(sys.argv[1]).sheetnames)",
      arquivo], { encoding: "utf8" });
    afirmar(saida.trim() === "['Agrupado', 'Lista']", "duas abas na ordem certa: " + saida);
  } catch (e) {
    falhas++;
    console.error("FALHOU: xlsx de duas abas não abriu: " + ((e.stdout || "") + (e.stderr || "")));
  }
  fs.rmSync(tmp, { recursive: true, force: true });
}

if (falhas) {
  console.error("\n" + falhas + " falha(s)");
  process.exit(1);
}
console.log("planilha.js: todas as verificações passaram (CRC-32, CSV, XLSX via openpyxl)");
