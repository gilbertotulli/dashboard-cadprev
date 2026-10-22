/* Exportar uma tabela do painel para CSV ou XLSX, no navegador.
 *
 * Sem biblioteca externa — a regra do projeto (CONTRIBUTING.md) é a mesma que
 * vale para os gráficos em charts.js: o pacote não tem etapa de build, quem
 * clona roda, e uma dependência nova precisa de justificativa forte. Um
 * leitor de planilha de verdade (SheetJS e afins) pesa uma ordem de grandeza
 * a mais do que este arquivo inteiro para fazer uma coisa que o formato
 * permite escrever à mão: um .xlsx é um .zip com alguns XML dentro, e o
 * .zip aceita entradas sem compressão (`STORED`), que dispensa qualquer
 * algoritmo de deflate.
 *
 * O que este arquivo escreve é deliberadamente mínimo: uma pasta de trabalho,
 * uma aba, texto inline (sem tabela de strings compartilhadas) e meia dúzia
 * de estilos fixos. O resultado abre no Excel, no LibreOffice e no Google
 * Planilhas — testado abrindo com `openpyxl` do outro lado, que é um leitor
 * independente e rigoroso com a especificação OOXML.
 */
(function (global) {
  "use strict";

  // ------------------------------------------------------------ CSV

  /* Separador ";" e decimal "," — convenção do projeto para arquivo que abre
   * no Excel em português, já usada em ferramentas/letras-financeiras. Um
   * número escrito com ponto decimal, aberto num Excel configurado em
   * pt-BR, vira texto em vez de número; com vírgula, o Excel reconhece.
   *
   * `linhas` é uma lista de listas de células. Uma célula é string, número,
   * null/undefined (vira vazio) ou um objeto {v, casas} para controlar as
   * casas decimais de um número (quantidade de cotas pede mais que valor em
   * reais).
   */
  function csvDeLinhas(linhas) {
    var fora = linhas.map(function (linha) {
      return linha.map(celulaCsv).join(";");
    });
    // BOM UTF-8: sem ele o Excel em Windows lê acento como lixo.
    return "﻿" + fora.join("\r\n") + "\r\n";
  }

  function celulaCsv(c) {
    var v = (c && typeof c === "object" && "v" in c) ? c.v : c;
    var casas = (c && typeof c === "object" && c.casas !== undefined) ? c.casas : null;
    if (v === null || v === undefined) return "";
    if (typeof v === "number") {
      if (!isFinite(v)) return "";
      var texto = casas === null ? String(v) : v.toFixed(casas);
      return texto.replace(".", ",");
    }
    var s = String(v);
    // Aspas só quando a célula tem algo que o separador ou a quebra de linha
    // confundiriam — citar tudo sempre funciona, mas deixa o arquivo mais
    // feio para quem abre num editor de texto para conferir.
    if (/[;"\n\r]/.test(s)) s = '"' + s.replace(/"/g, '""') + '"';
    return s;
  }

  // ------------------------------------------------------------ ZIP

  /* CRC-32, tabela calculada uma vez. Testado contra o vetor conhecido
   * crc32("123456789") === 0xcbf43926 (ver tests/planilha.node.mjs). */
  var TABELA_CRC = (function () {
    var t = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
      t[n] = c >>> 0;
    }
    return t;
  })();

  function crc32(bytes) {
    var c = 0xffffffff;
    for (var i = 0; i < bytes.length; i++) {
      c = TABELA_CRC[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    }
    return (c ^ 0xffffffff) >>> 0;
  }

  function paraUtf8(texto) {
    return new TextEncoder().encode(texto);
  }

  /* Um .zip sem compressão: cada entrada guarda os bytes como são. O formato
   * permite — `STORED`, método 0 — e para os tamanhos que este painel produz
   * (uma carteira de poucas centenas de ativos) o arquivo sem compactar ainda
   * fica na casa dos poucos KB. O que se ganha é não precisar de deflate. */
  function zipDeArquivos(arquivos) {
    var DATA_FIXA = { hora: 0, data: 0x21 }; // 1980-01-01, data mínima válida do formato
    var locais = [], centrais = [], offset = 0;

    arquivos.forEach(function (arq) {
      var nome = paraUtf8(arq.nome);
      var dados = arq.bytes;
      var crc = crc32(dados);
      var cabecalhoLocal = construirCabecalhoLocal(nome, dados.length, crc, DATA_FIXA);
      locais.push(cabecalhoLocal, nome, dados);
      centrais.push(construirCabecalhoCentral(nome, dados.length, crc, DATA_FIXA, offset));
      offset += cabecalhoLocal.length + nome.length + dados.length;
    });

    var inicioCentral = offset;
    var central = concatenar(centrais.reduce(function (a, c) { return a.concat(c); }, []));
    var fim = construirFimDoCentral(arquivos.length, central.length, inicioCentral);

    return concatenar([].concat(locais, [central, fim]));
  }

  function construirCabecalhoLocal(nomeBytes, tamanho, crc, dt) {
    var b = new ArrayBuffer(30);
    var v = new DataView(b);
    v.setUint32(0, 0x04034b50, true);
    v.setUint16(4, 20, true);          // versão mínima
    v.setUint16(6, 0, true);           // flags
    v.setUint16(8, 0, true);           // método: sem compressão
    v.setUint16(10, dt.hora, true);
    v.setUint16(12, dt.data, true);
    v.setUint32(14, crc, true);
    v.setUint32(18, tamanho, true);    // tamanho comprimido = tamanho real
    v.setUint32(22, tamanho, true);
    v.setUint16(26, nomeBytes.length, true);
    v.setUint16(28, 0, true);          // campo extra
    return new Uint8Array(b);
  }

  function construirCabecalhoCentral(nomeBytes, tamanho, crc, dt, offsetLocal) {
    var b = new ArrayBuffer(46);
    var v = new DataView(b);
    v.setUint32(0, 0x02014b50, true);
    v.setUint16(4, 20, true);          // versão que gravou
    v.setUint16(6, 20, true);          // versão mínima
    v.setUint16(8, 0, true);
    v.setUint16(10, 0, true);
    v.setUint16(12, dt.hora, true);
    v.setUint16(14, dt.data, true);
    v.setUint32(16, crc, true);
    v.setUint32(20, tamanho, true);
    v.setUint32(24, tamanho, true);
    v.setUint16(28, nomeBytes.length, true);
    v.setUint16(30, 0, true);          // extra
    v.setUint16(32, 0, true);          // comentário
    v.setUint16(34, 0, true);          // disco inicial
    v.setUint16(36, 0, true);          // atributos internos
    v.setUint32(38, 0, true);          // atributos externos
    v.setUint32(42, offsetLocal, true);
    return [new Uint8Array(b), nomeBytes];
  }

  function construirFimDoCentral(quantos, tamanhoCentral, offsetCentral) {
    var b = new ArrayBuffer(22);
    var v = new DataView(b);
    v.setUint32(0, 0x06054b50, true);
    v.setUint16(4, 0, true);
    v.setUint16(6, 0, true);
    v.setUint16(8, quantos, true);
    v.setUint16(10, quantos, true);
    v.setUint32(12, tamanhoCentral, true);
    v.setUint32(16, offsetCentral, true);
    v.setUint16(20, 0, true);          // sem comentário
    return new Uint8Array(b);
  }

  function concatenar(partes) {
    var total = partes.reduce(function (n, p) { return n + p.length; }, 0);
    var saida = new Uint8Array(total);
    var pos = 0;
    partes.forEach(function (p) { saida.set(p, pos); pos += p.length; });
    return saida;
  }

  // ------------------------------------------------------------ XLSX

  function escaparXml(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&apos;")
      // Caracteres de controle que o XML não aceita nem escapados (exceto
      // tab/LF/CR) — uma descrição de ativo corrompida no DAIR já trouxe
      // bytes assim, e sem isso o arquivo some com "repair" no Excel.
      .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, "");
  }

  function letraDaColuna(indiceZero) {
    var n = indiceZero + 1, s = "";
    while (n > 0) {
      var r = (n - 1) % 26;
      s = String.fromCharCode(65 + r) + s;
      n = Math.floor((n - 1) / 26);
    }
    return s;
  }

  /* Índice de estilo em cellXfs — ver xlsxEstilos() logo abaixo. Nomeado para
   * o chamador não precisar saber a ordem em que os estilos foram montados. */
  var ESTILO = { geral: 0, qtd: 1, dinheiro: 2, inteiro: 3, cabecalho: 4, pct: 5 };

  function construirSheetXml(aba) {
    var larguras = aba.larguras || [];
    var cols = larguras.length ? ("<cols>" + larguras.map(function (w, i) {
      return '<col min="' + (i + 1) + '" max="' + (i + 1) + '" width="' + w + '" customWidth="1"/>';
    }).join("") + "</cols>") : "";

    var maxColunas = aba.linhas.reduce(function (n, linha) {
      return Math.max(n, linha.length);
    }, 0);
    var dimensao = maxColunas && aba.linhas.length ?
      '<dimension ref="A1:' + letraDaColuna(maxColunas - 1) + aba.linhas.length + '"/>' : "";

    var linhasXml = aba.linhas.map(function (linha, r) {
      var celulas = linha.map(function (c, i) {
        return construirCelulaXml(letraDaColuna(i) + (r + 1), c);
      }).join("");
      return '<row r="' + (r + 1) + '">' + celulas + "</row>";
    }).join("");

    /* `linhaCongelada` é a última linha fixa (1-indexado) — não precisa ser
     * a primeira: esta planilha tem um bloco de título antes do cabeçalho
     * de verdade, e congelar a linha 1 prenderia só o título na tela. */
    var sheetViews = aba.linhaCongelada ? '<sheetViews><sheetView workbookViewId="0">' +
      '<pane ySplit="' + aba.linhaCongelada + '" topLeftCell="A' +
      (aba.linhaCongelada + 1) + '" activePane="bottomLeft" state="frozen"/>' +
      "</sheetView></sheetViews>" : "";

    // Ordem exigida pelo schema do OOXML para <worksheet> (CT_Worksheet):
    // sheetPr?, dimension?, sheetViews?, sheetFormatPr?, cols*, sheetData, ...
    // O Excel de verdade valida essa ordem na abertura; leitores tolerantes
    // como openpyxl e LibreOffice não — por isso um arquivo com a ordem
    // errada passava nos testes e ainda assim chegava "com erro" no Excel.
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
      dimensao + sheetViews + cols + "<sheetData>" + linhasXml + "</sheetData>" +
      "</worksheet>";
  }

  function construirCelulaXml(ref, c) {
    var v = (c && typeof c === "object" && "v" in c) ? c.v : c;
    var estilo = (c && typeof c === "object" && c.s !== undefined) ? ESTILO[c.s] : undefined;
    var sAttr = estilo !== undefined ? ' s="' + estilo + '"' : "";
    if (v === null || v === undefined || v === "") {
      return estilo !== undefined ? '<c r="' + ref + '"' + sAttr + "/>" : "";
    }
    if (typeof v === "number") {
      if (!isFinite(v)) return "";
      return '<c r="' + ref + '"' + sAttr + "><v>" + v + "</v></c>";
    }
    return '<c r="' + ref + '" t="inlineStr"' + sAttr + "><is><t xml:space=\"preserve\">" +
      escaparXml(v) + "</t></is></c>";
  }

  /* Seis estilos fixos, nessa ordem — tem de bater com o mapa ESTILO acima.
   * numFmtId 164/165 são customizados (qualquer id ≥ 164 é livre pela
   * especificação); 1, 3 e 9 são embutidos do Excel e não precisam de
   * declaração em <numFmts>. */
  function xlsxEstilos() {
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
      '<numFmts count="2">' +
      '<numFmt numFmtId="164" formatCode="0.000000"/>' +
      '<numFmt numFmtId="165" formatCode="#,##0.00"/>' +
      "</numFmts>" +
      '<fonts count="2">' +
      '<font><sz val="10"/><name val="Calibri"/></font>' +
      '<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>' +
      "</fonts>" +
      '<fills count="3">' +
      '<fill><patternFill patternType="none"/></fill>' +
      '<fill><patternFill patternType="gray125"/></fill>' +
      '<fill><patternFill patternType="solid"><fgColor rgb="FF2A6F77"/>' +
      '<bgColor indexed="64"/></patternFill></fill>' +
      "</fills>" +
      '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +
      '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
      '<cellXfs count="6">' +
      '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>' +                               // 0 geral
      '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>' +        // 1 qtd
      '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>' +        // 2 dinheiro
      '<xf numFmtId="1" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>' +          // 3 inteiro
      '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>' +    // 4 cabeçalho
      '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>' +        // 5 percentual (número puro, não "%" do Excel — ver nota em app.js)
      "</cellXfs>" +
      // Sem isto o openpyxl avisa "Workbook contains no default style" e
      // aplica um por conta própria — e algumas versões do Excel de
      // verdade recusam abrir sem reparar. O schema exige a ordem exata:
      // numFmts, fonts, fills, borders, cellStyleXfs, cellXfs, cellStyles.
      '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>' +
      "</styleSheet>";
  }

  function xlsxConteudoTipos(quantasAbas) {
    var overrides = [];
    for (var i = 1; i <= quantasAbas; i++) {
      overrides.push('<Override PartName="/xl/worksheets/sheet' + i + '.xml" ' +
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>');
    }
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
      '<Default Extension="xml" ContentType="application/xml"/>' +
      '<Override PartName="/xl/workbook.xml" ' +
      'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
      '<Override PartName="/xl/styles.xml" ' +
      'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +
      overrides.join("") + "</Types>";
  }

  function xlsxRelsRaiz() {
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      '<Relationship Id="rId1" ' +
      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" ' +
      'Target="xl/workbook.xml"/></Relationships>';
  }

  function xlsxWorkbook(abas) {
    var sheets = abas.map(function (aba, i) {
      return '<sheet name="' + escaparXml(aba.nome) + '" sheetId="' + (i + 1) +
        '" r:id="rId' + (i + 1) + '"/>';
    }).join("");
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ' +
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
      "<sheets>" + sheets + "</sheets></workbook>";
  }

  function xlsxWorkbookRels(abas) {
    var rels = abas.map(function (_aba, i) {
      return '<Relationship Id="rId' + (i + 1) + '" ' +
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" ' +
        'Target="worksheets/sheet' + (i + 1) + '.xml"/>';
    }).join("");
    var idEstilos = "rId" + (abas.length + 1);
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      rels + '<Relationship Id="' + idEstilos + '" ' +
      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" ' +
      'Target="styles.xml"/></Relationships>';
  }

  /* `abas`: lista de { nome, larguras: [number,...], congelarCabecalho,
   * linhas: [[celula, ...], ...] }. Uma célula é string, número, ou
   * {v, s} com `s` em 'qtd'|'dinheiro'|'inteiro'|'cabecalho'|'pct'. */
  function xlsxDeAbas(abas) {
    var arquivos = [
      { nome: "[Content_Types].xml", bytes: paraUtf8(xlsxConteudoTipos(abas.length)) },
      { nome: "_rels/.rels", bytes: paraUtf8(xlsxRelsRaiz()) },
      { nome: "xl/workbook.xml", bytes: paraUtf8(xlsxWorkbook(abas)) },
      { nome: "xl/_rels/workbook.xml.rels", bytes: paraUtf8(xlsxWorkbookRels(abas)) },
      { nome: "xl/styles.xml", bytes: paraUtf8(xlsxEstilos()) }
    ];
    abas.forEach(function (aba, i) {
      arquivos.push({ nome: "xl/worksheets/sheet" + (i + 1) + ".xml",
                      bytes: paraUtf8(construirSheetXml(aba)) });
    });
    return zipDeArquivos(arquivos);
  }

  // ------------------------------------------------------------ gatilho de download

  /* As duas únicas funções daqui que tocam o DOM. Separadas das que montam o
   * conteúdo para que a lógica de formato possa ser testada fora do
   * navegador (ver tests/planilha.node.mjs), sem precisar simular Blob,
   * URL.createObjectURL ou um elemento <a>. */
  function baixar(nome, blob) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = nome;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Adiado: revogar a URL antes do navegador terminar de iniciar o download
    // (alguns disparam a gravação de forma assíncrona) perderia o arquivo.
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function baixarCsv(nome, linhas) {
    baixar(nome, new Blob([csvDeLinhas(linhas)], { type: "text/csv;charset=utf-8" }));
  }

  function baixarXlsx(nome, abas) {
    var bytes = xlsxDeAbas(abas);
    baixar(nome, new Blob([bytes], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }));
  }

  global.Planilha = {
    csvDeLinhas: csvDeLinhas, xlsxDeAbas: xlsxDeAbas, crc32: crc32,
    baixarCsv: baixarCsv, baixarXlsx: baixarXlsx
  };
})(typeof window !== "undefined" ? window : global);
