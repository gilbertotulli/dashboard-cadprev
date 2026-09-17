/* Painel CADPREV — interface.
 *
 * Estático de propósito: os JSON em data/ são pré-agregados pela ingestão
 * (`python -m cadprev build`). A API não é consultada daqui, porque ela pagina
 * de 5.000 em 5.000 e não filtra por data de alteração — somar 170 mil linhas
 * no navegador a cada clique não é opção, e martelar um serviço público
 * gratuito, menos ainda.
 */
(function () {
  "use strict";

  var D = "data/";
  var estado = { meta: null, entes: [], cnpj: null, aba: "panorama", cache: {},
                 referencia: "brasil", selecao: [], selecaoUf: "",
                 selecaoAberta: false,
                 filtros: null, chaves: null };
  var conteudo = document.getElementById("conteudo");

  // ------------------------------------------------------------ utilidades

  function h(tag, attrs, filhos) {
    var el = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "texto") el.textContent = attrs[k];
      else if (k === "html") el.innerHTML = attrs[k];
      else if (k === "onclick") el.addEventListener("click", attrs[k]);
      else if (attrs[k] !== null && attrs[k] !== undefined) el.setAttribute(k, attrs[k]);
    });
    (filhos || []).forEach(function (f) {
      if (f) el.appendChild(typeof f === "string" ? document.createTextNode(f) : f);
    });
    return el;
  }

  var num = Charts.num, reais = Charts.reais;

  /* Sem abreviar. Nos achados de qualidade o algarismo é a prova: "R$ 36,6 mi"
   * esconde justamente que a cota foi digitada como 36.640.481,00. */
  function reaisExatos(v) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    return (v < 0 ? "\u2212" : "") + "R$ " + num(Math.abs(v), 2);
  }

  /* Busca por nome sem exigir acento: "vitoria" acha "Vitória", "sao" acha
   * "São". Normalizar na digitação e no alvo é o mesmo trabalho, e sem isso
   * metade dos municípios brasileiros só aparece para quem sabe onde fica o
   * til. NFD separa a letra do acento; a faixa \u0300-\u036f é o acento. */
  function semAcento(texto) {
    return String(texto || "").normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  /* Índice montado uma vez: normalizar 5.596 nomes a cada tecla digitada é
   * trabalho repetido à toa. */
  var indiceBusca = null;
  function paraBusca() {
    if (!indiceBusca) {
      indiceBusca = estado.entes.map(function (e) {
        return { e: e, nome: semAcento(e.ente), cnpj: e.cnpj || "" };
      });
    }
    return indiceBusca;
  }

  function filtrarEntes(termo, uf, limite) {
    var alvo = semAcento(termo).trim();
    var digitos = termo.replace(/\D/g, "");
    var achados = [];
    var todos = paraBusca();
    for (var i = 0; i < todos.length; i++) {
      var r = todos[i];
      if (uf && r.e.uf !== uf) continue;
      if (alvo.length >= 2 && r.nome.indexOf(alvo) < 0 &&
          !(digitos.length >= 3 && r.cnpj.indexOf(digitos) >= 0)) continue;
      if (alvo.length < 2 && digitos.length < 3 && !uf) continue;
      achados.push(r.e);
    }
    return { total: achados.length, itens: achados.slice(0, limite || 12) };
  }

  function ufsConhecidas() {
    var vistas = {};
    estado.entes.forEach(function (e) { if (e.uf) vistas[e.uf] = true; });
    return Object.keys(vistas).sort();
  }

  function diasEntre(inicio, fim) {
    if (!inicio || !fim) return 0;
    var a = Date.parse(String(inicio).slice(0, 10));
    var b = Date.parse(String(fim).slice(0, 10));
    if (isNaN(a) || isNaN(b)) return 0;
    return Math.max(0, Math.round((b - a) / 86400000));
  }

  function pct(v, casas) { return v === null || v === undefined ? "—" : num(v, casas === undefined ? 1 : casas) + "%"; }

  function data(iso) {
    if (!iso) return "—";
    var p = String(iso).slice(0, 10).split("-");
    return p.length === 3 ? p[2] + "/" + p[1] + "/" + p[0] : iso;
  }

  function cnpjFormatado(c) {
    if (!c || c.length !== 14) return c || "—";
    return c.slice(0, 2) + "." + c.slice(2, 5) + "." + c.slice(5, 8) + "/" +
      c.slice(8, 12) + "-" + c.slice(12);
  }

  var MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez"];

  /* Os agregados nacionais vêm pré-calculados numa variante por combinação de
   * chaves. Refazer as somas aqui duplicaria em JavaScript a aritmética que o
   * Python já faz sob teste — e é assim que duas telas passam a discordar. */
  function nacional(caminho) {
    return buscar(caminho).then(function (j) {
      var v = j.variantes || {};
      return v[estado.filtros] || v[(estado.chaves && estado.chaves.padrao)] ||
        v[Object.keys(v)[0]] || {};
    });
  }

  /* O índice por RPPS é único; só as estatísticas de grupo mudam com as chaves,
   * porque filtrar quem entra na mediana é diferente de filtrar quem pode ser
   * selecionado. A cópia rasa evita mexer no que está em cache. */
  function comparativos() {
    return buscar("benchmark.json").then(function (b) {
      var v = (b.grupos && b.grupos.variantes) || {};
      var escolhido = v[estado.filtros] ||
        v[(estado.chaves && estado.chaves.padrao)] || v[Object.keys(v)[0]];
      var copia = {};
      Object.keys(b).forEach(function (k) { copia[k] = b[k]; });
      copia.grupos = escolhido || b.grupos;
      return copia;
    });
  }

  function buscar(caminho) {
    if (estado.cache[caminho]) return Promise.resolve(estado.cache[caminho]);
    return fetch(D + caminho).then(function (r) {
      if (!r.ok) throw new Error(caminho + ": " + r.status);
      return r.json();
    }).then(function (j) { estado.cache[caminho] = j; return j; });
  }

  function kpi(rotulo, valor, sub, classe) {
    return h("div", { class: "kpi " + (classe || "") }, [
      h("div", { class: "lbl", texto: rotulo }),
      h("div", { class: "val", html: valor }),
      sub ? h("div", { class: "sub", texto: sub }) : null
    ]);
  }

  function cartao(titulo, fonte, sub, corpo) {
    var filhos = [
      h("div", { class: "cartao-h" }, [
        h("h3", { texto: titulo }),
        fonte ? h("span", { class: "fonte", texto: fonte }) : null
      ])
    ];
    if (sub) filhos.push(h("p", { class: "sub", texto: sub }));
    (Array.isArray(corpo) ? corpo : [corpo]).forEach(function (c) { if (c) filhos.push(c); });
    return h("div", { class: "cartao" }, filhos);
  }

  function grafico(altura) {
    return h("div", { class: "grafico", "data-altura": altura });
  }

  function legenda(itens) {
    return h("div", { class: "legenda" }, itens.map(function (i) {
      return h("span", {}, [
        h("i", { class: i.linha ? "linha" : "", style: "background:" + i.cor }),
        i.rotulo
      ]);
    }));
  }

  function tabela(colunas, linhas, larga) {
    var thead = h("thead", {}, [h("tr", {}, colunas.map(function (c) {
      return h("th", { class: (c.n ? "n" : "") + (c.classe ? " " + c.classe : ""),
                       texto: c.t });
    }))]);
    var tbody = h("tbody", {}, linhas);
    return h("div", { class: "rolar" },
      [h("table", { class: "dados" + (larga ? " larga" : "") }, [thead, tbody])]);
  }

  function vazio(titulo, texto, extra) {
    return h("div", { class: "vazio" }, [
      h("h3", { texto: titulo }), h("p", { html: texto }), extra
    ]);
  }

  function semEnte(oQue) {
    return vazio("Escolha um RPPS",
      "A aba <strong>" + oQue + "</strong> mostra os dados de um regime específico. " +
      "Use a busca no topo para escolher um ente pelo nome ou pelo CNPJ.");
  }

  function semDado(oQue, endpoint) {
    return vazio("Sem dados de " + oQue,
      "Este RPPS não tem registros de <code>" + endpoint + "</code> no banco local. " +
      "Pode ser que ele não tenha declarado no período ingerido, ou que a ingestão " +
      "ainda não tenha coberto esse endpoint.");
  }

  // ------------------------------------------------------------- aba 1

  function abaPanorama() {
    return nacional("panorama.json").then(function (p) {
      if (!p.disponivel) {
        return [vazio("Panorama indisponível",
          "Falta ingerir <code>RPPS_CRP</code>. Rode " +
          "<code>python -m cadprev ingest RPPS_CRP</code>.")];
      }
      var k = p.kpis;
      var cores = { valido: "var(--ok)", judicial: "var(--warn)", vencido: "var(--crit)" };
      var linhas = p.por_regiao.map(function (r) {
        return {
          rotulo: r.regiao, partes: [
            { chave: "valido", rotulo: "✓ Válido", valor: r.valido, cor: cores.valido },
            { chave: "judicial", rotulo: "§ Judicial", valor: r.judicial, cor: cores.judicial },
            { chave: "vencido", rotulo: "✕ Vencido", valor: r.vencido, cor: cores.vencido }
          ]
        };
      });

      var alvoBarras = grafico(Math.max(160, linhas.length * 42));
      var tabelaVencidos = tabela(
        [{ t: "Ente" }, { t: "Dias", n: true }],
        p.vencidos_ha_mais_tempo.map(function (v) {
          return linhaClicavel(v.cnpj, [
            h("td", {}, [v.ente || "—", h("span", { class: "uf", texto: v.uf || "" })]),
            h("td", { class: "n", texto: num(v.dias, 0) })
          ]);
        }));

      var no = [
        h("h2", { class: "secao", texto: "Panorama nacional" }),
        h("p", {
          class: "intro",
          texto: "Quantos RPPS estão no banco local, quantos mantêm o certificado " +
            "de regularidade vigente e onde a irregularidade se concentra."
        }),
        h("div", { class: "contexto" }, [
          h("span", { class: "pilula" }, ["Referência ", h("b", { texto: data(p.referencia) })])
        ]),
        h("div", { class: "kpis" }, [
          kpi("RPPS no banco local", num(k.entes, 0), "com registro de CRP"),
          kpi("CRP válido", num(k.perc_valido, 1) + "<small>%</small>",
            num(Math.round(k.entes * k.perc_valido / 100), 0) + " entes"),
          kpi("CRP por via judicial", num(k.judicial, 0),
            pct(k.perc_judicial) + " dos certificados"),
          kpi("Sem certificado vigente",
            num(k.entes - Math.round(k.entes * k.perc_valido / 100), 0),
            "CRP vencido na data de referência", "ruim")
        ]),
        h("div", { class: "grade larga" }, [
          cartao("Situação do CRP por região", "RPPS_CRP",
            "Entes com RPPS, por situação do certificado",
            [alvoBarras, legenda([
              { cor: cores.valido, rotulo: "✓ Válido" },
              { cor: cores.judicial, rotulo: "§ Judicial" },
              { cor: cores.vencido, rotulo: "✕ Vencido" }
            ])]),
          cartao("Vencidos há mais tempo", "RPPS_CRP",
            "Dias desde o fim da validade · clique para abrir a ficha",
            tabelaVencidos)
        ])
      ];

      depoisDeMontar(function () {
        Charts.desenhar(alvoBarras, "empilhadas", {
          linhas: linhas, altura: Math.max(160, linhas.length * 42),
          descricao: "Situação do CRP por região"
        });
      });
      return no;
    });
  }

  function linhaClicavel(cnpj, celulas) {
    var tr = h("tr", { class: "clicavel" }, celulas.concat([
      h("td", { class: "ir", texto: "abrir →" })
    ]));
    tr.addEventListener("click", function () { irParaEnte(cnpj); });
    return tr;
  }

  // ------------------------------------------------------------- aba 4 nacional

  function abaCarteiraNacional() {
    return nacional("carteira-nacional.json").then(function (c) {
      if (!c.disponivel) {
        return [vazio("Carteira indisponível",
          "Falta ingerir <code>DAIR_CARTEIRA</code>. Rode " +
          "<code>python -m cadprev ingest DAIR_CARTEIRA --ano 2026 --mes 8</code>.")];
      }
      var alvoFundo = grafico(96);
      var alvoSeg = grafico(Math.max(140, c.por_segmento.length * 34));
      var alvoGrupos = grafico(Math.max(160, (c.por_esfera.length + c.por_regiao.length) * 26 + 40));

      var capitalizado = (c.por_fundo.find(function (f) {
        return f.categoria === "capitalizado";
      }) || {}).perc || 0;

      var linhasGrupos = [{ cabecalho: "Por esfera" }]
        .concat(c.por_esfera.map(function (e) {
          return { rotulo: e.rotulo, perc: e.perc, valor: e.valor };
        }))
        .concat([{ cabecalho: "Por região" }])
        .concat(c.por_regiao.map(function (r) {
          return { rotulo: r.rotulo, perc: r.perc, valor: r.valor };
        }));

      var CORES_FUNDO = {
        capitalizado: "var(--s1)", reparticao: "var(--s2)",
        taxa_administracao: "var(--s3)", nao_decomposto: "var(--muted)"
      };
      var partesFundo = c.por_fundo.map(function (f) {
        return { rotulo: f.rotulo, valor: f.valor, cor: CORES_FUNDO[f.categoria] || "var(--s4)" };
      });

      var no = [
        h("h2", { class: "secao", texto: "Carteira de investimentos" }),
        h("p", {
          class: "intro",
          texto: "O agregado de todos os RPPS ingeridos. Escolha um ente na busca " +
            "para ver a carteira dele, com a marca do limite legal em cada segmento."
        }),
        h("div", { class: "contexto" }, [
          h("span", { class: "pilula" }, ["Ente ", h("b", { texto: "Todos os RPPS" })]),
          h("span", { class: "pilula nivel", title: c.nivel_descricao },
            ["Decomposição por fundo ", h("b", { texto: "Nível " + c.nivel })]),
          c.excluidos_do_ranking_menores
            ? h("span", { class: "pilula aviso", texto: c.excluidos_do_ranking_menores +
                " RPPS declararam zero e ficam fora do ranking dos menores" })
            : null
        ]),
        h("div", { class: "kpis" }, [
          kpi("Patrimônio investido", reais(c.total),
            num(c.rpps_com_dair, 0) + " RPPS com DAIR na competência"),
          kpi("Em regimes integralmente capitalizados", num(capitalizado, 1) + "<small>%</small>",
            "classificação de " + (c.nivel === "A" ? "cada ativo" : "cada RPPS")),
          kpi("Maior patrimônio", c.maiores.length ? reais(c.maiores[0].valor) : "—",
            c.maiores.length ? c.maiores[0].ente : ""),
          kpi("Segmentos distintos", num(c.por_segmento.length, 0),
            "inclui disponibilidades financeiras")
        ]),
        cartao("Distribuição por fundo", "DAIR_CARTEIRA + DRAA_SEGREGACAO_MASSA",
          c.nivel_descricao, [alvoFundo, legenda(partesFundo.map(function (p) {
            return { cor: p.cor, rotulo: p.rotulo };
          }))]),
        h("div", { class: "grade duas" }, [
          cartao("Por segmento de alocação", "DAIR_CARTEIRA",
            "Todos os RPPS · % do patrimônio", alvoSeg),
          cartao("Por esfera e por região", "DAIR_CARTEIRA · sg_uf · no_ente",
            "Dois cortes independentes, cada um somando 100%", alvoGrupos)
        ]),
        h("div", { class: "grade duas" }, [
          cartao("Maiores patrimônios", "DAIR_CARTEIRA",
            "Clique na linha para abrir a carteira do RPPS",
            tabela([{ t: "RPPS" }, { t: "Patrimônio", n: true }],
              c.maiores.map(function (m) {
                return linhaClicavel(m.cnpj, [
                  h("td", {}, [m.ente, h("span", { class: "uf", texto: m.uf || "" })]),
                  h("td", { class: "n", texto: reais(m.valor) })
                ]);
              }))),
          cartao("Menores patrimônios", "DAIR_CARTEIRA", c.regra_menores,
            tabela([{ t: "RPPS" }, { t: "Patrimônio", n: true }],
              c.menores.map(function (m) {
                return linhaClicavel(m.cnpj, [
                  h("td", {}, [m.ente, h("span", { class: "uf", texto: m.uf || "" })]),
                  h("td", { class: "n", texto: reais(m.valor) })
                ]);
              })))
        ])
      ];

      depoisDeMontar(function () {
        Charts.desenhar(alvoFundo, "barraUnica", {
          partes: partesFundo, altura: 96, alturaBarra: 38,
          titulo: "Distribuição por fundo",
          descricao: "Patrimônio investido por natureza do fundo"
        });
        Charts.desenhar(alvoSeg, "ranqueadas", {
          linhas: c.por_segmento.map(function (s) {
            return { rotulo: s.rotulo, perc: s.perc, valor: s.valor };
          }),
          rotuloAcima: true, altura: Math.max(140, c.por_segmento.length * 34),
          titulo: "Segmento · todos os RPPS"
        });
        Charts.desenhar(alvoGrupos, "ranqueadas", {
          linhas: linhasGrupos,
          altura: Math.max(160, (c.por_esfera.length + c.por_regiao.length) * 26 + 40),
          titulo: "Grupo · % do patrimônio"
        });
      });
      return no;
    });
  }

  // ------------------------------------------------------- abas do ente

  function carregarEnte() {
    return buscar("ente/" + estado.cnpj + ".json");
  }

  function cabecalhoEnte(e) {
    var crp = e.crp || {};
    var valido = crp.valido;
    var selo = crp.numero_crp
      ? h("span", { class: "selo " + (valido ? "ok" : "crit") },
        [(valido ? "✓ CRP válido até " : "✕ CRP vencido em ") + data(crp.validade) +
         (crp.judicial ? " · judicial" : "")])
      : h("span", { class: "selo neutro", texto: "sem registro de CRP" });

    return h("div", { class: "ficha-topo" }, [
      h("div", {}, [
        h("div", { class: "nm" },
          [e.ente || "—"].concat(marcasDoEnte(e.cnpj))),
        h("div", {
          class: "id", texto: "CNPJ " + cnpjFormatado(e.cnpj) + " · " + (e.uf || "—") +
            " · " + rotuloEsfera(e.esfera) + " · " + (e.regiao || "—")
        })
      ]),
      selo
    ]);
  }

  /* Rótulos curtos para as marcas de qualidade deste ente. Ficam ao lado do
   * nome, e não num rodapé de página, porque quem abre uma ficha precisa saber
   * antes de ler os números — não depois. */
  var ROTULO_MARCA = {
    posicao_impossivel: { texto: "lançamento impossível", grave: true },
    dair_defasado: { texto: "DAIR defasado", grave: false },
    crp_nao_valido: { texto: "CRP não-válido há meses", grave: false }
  };

  function marcasDoEnte(cnpj) {
    var registro = null;
    for (var i = 0; i < estado.entes.length; i++) {
      if (estado.entes[i].cnpj === cnpj) { registro = estado.entes[i]; break; }
    }
    if (!registro || !registro.marcas || !registro.marcas.length) return [];
    return registro.marcas.map(function (m) {
      var r = ROTULO_MARCA[m];
      if (!r) return null;
      var no = h("a", {
        class: "marca-ente" + (r.grave ? " grave" : ""),
        href: "#/qualidade", texto: r.texto,
        title: "O que isso significa está na aba Qualidade."
      });
      return no;
    }).filter(Boolean);
  }

  function rotuloEsfera(chave) {
    return { estadual: "RPPS estadual", capital: "RPPS de capital", municipal: "RPPS municipal" }[chave] || "—";
  }

  /* Civil e militar não somam. O militar não se aposenta — passa à reserva e
   * depois à reforma —, tem avaliação atuarial própria e só existe nos Estados.
   * Uma tabela para cada, e o termo da fonte ao lado do termo do regime sempre
   * que o painel troca um pelo outro. */
  function blocosDaMassa(est) {
    var muitas = (est.massas || []).length > 1;
    var nos = [];
    (est.massas || []).forEach(function (b) {
      if (muitas) {
        nos.push(h("p", { class: "rotulo-massa", texto: b.rotulo }));
      }
      nos.push(tabela(
        [{ t: "Grupo" }, { t: "Pessoas", n: true }, { t: "Folha mensal", n: true }],
        (b.grupos || []).map(function (g) {
          return h("tr", {}, [
            h("td", { texto: g.rotulo,
                      title: g.fonte ? "No CADPREV: " + g.fonte : "" }),
            h("td", { class: "n", texto: num(g.pessoas, 0) }),
            h("td", { class: "n", texto: g.folha ? reais(g.folha) : "—" })
          ]);
        }).concat([
          h("tr", { class: "somatorio" }, [
            h("td", { texto: "Razão ativos / beneficiários" }),
            h("td", { class: "n", texto: b.razao_ativos_inativos === null ||
                      b.razao_ativos_inativos === undefined
                        ? "—" : num(b.razao_ativos_inativos, 2) }),
            h("td", {})
          ])
        ])));
    });
    if (est.nota_nomenclatura) {
      nos.push(h("p", { class: "nota", texto: est.nota_nomenclatura }));
    }
    return nos;
  }

  function abaFicha() {
    if (!estado.cnpj) return Promise.resolve([semEnte("Ficha do RPPS")]);
    return carregarEnte().then(function (e) {
      var crp = e.crp || {};
      var est = e.estatistica || {};
      var seg = e.segregacao || {};
      var vigentes = (e.aliquotas || []).filter(function (a) {
        return a.vigente ? /VIGENTE/i.test(a.vigente) && !/NÃO|NAO/i.test(a.vigente)
                         : !a.fim_vigencia;
      });

      return [
        h("h2", { class: "secao", texto: "Ficha do RPPS" }),
        cabecalhoEnte(e),
        h("div", { class: "campos", style: "margin-bottom:22px" }, [
          campo("Nº do CRP", crp.numero_crp || "—"),
          campo("Emissão", data(crp.emissao)),
          campo("Validade", data(crp.validade)),
          campo("Forma de emissão", crp.judicial === undefined ? "—"
            : (crp.judicial ? "Judicial" : "Administrativa")),
          campo("Segregação da massa", seg.segregacao || "—"),
          campo("Exercício do DRAA", est.exercicio || "—")
        ]),
        h("div", { class: "grade duas" }, [
          cartao("Alíquotas vigentes", "RPPS_ALIQUOTA",
            vigentes.length ? "Declaradas como vigentes na fonte"
                            : "Nenhuma alíquota vigente no banco",
            tabela([{ t: "Sujeito passivo" }, { t: "Plano" }, { t: "Alíquota", n: true }],
              vigentes.map(function (a) {
                return h("tr", {}, [
                  h("td", { texto: a.sujeito_passivo || "—" }),
                  h("td", { texto: a.plano || "—" }),
                  h("td", { class: "n", texto: pct(a.aliquota, 2) })
                ]);
              }))),
          cartao("Massa de participantes", "DRAA_ESTATISTICA",
            est.disponivel
              ? "Exercício " + est.exercicio +
                (est.tem_militar ? " · civis e militares são massas separadas"
                                 : "")
              : "Sem DRAA no banco",
            est.disponivel ? blocosDaMassa(est)
                           : h("p", { class: "sub", texto: "—" }))
        ])
      ];
    });
  }

  function tabelaComposicao(itens) {
    if (!itens || !itens.length) return h("p", { class: "sub", texto: "Sem rubricas no período." });
    return tabela([{ t: "Rubrica" }, { t: "Valor", n: true }, { t: "%", n: true }],
      itens.slice(0, 7).map(function (i) {
        return h("tr", {}, [
          h("td", { texto: i.rotulo }),
          h("td", { class: "n", texto: reais(i.valor) }),
          h("td", { class: "n", texto: num(i.perc, 1) })
        ]);
      }));
  }

  function campo(k, v) {
    return h("div", { class: "campo" }, [
      h("div", { class: "k", texto: k }), h("div", { class: "v", texto: String(v) })
    ]);
  }

  function linhaSimples(rotulo, valor, classe) {
    return h("tr", {}, [
      h("td", { texto: rotulo }),
      h("td", { class: "n " + (classe || ""), texto: valor })
    ]);
  }

  function abaCaixa() {
    if (!estado.cnpj) return Promise.resolve([semEnte("Caixa")]);
    return carregarEnte().then(function (e) {
      var c = e.caixa || {};
      if (!c.disponivel) return [cabecalhoEnte(e), semDado("caixa", "DIPR")];

      var serie = c.serie;
      var escalaMi = 1e6;
      var rotulos = serie.map(function (p) {
        return (MESES[(p.mes || 1) - 1] || "?") + (serie.length > 12 ? "/" + String(p.ano).slice(2) : "");
      });
      var alvo = grafico(260);

      return [
        h("h2", { class: "secao", texto: "Caixa previdenciário" }),
        cabecalhoEnte(e),
        h("div", { class: "kpis" }, [
          kpi("Ingressos no período", reais(c.total_receita), "bloco 10 do DIPR"),
          kpi("Dispêndios no período", reais(c.total_despesa), "bloco 11 do DIPR"),
          kpi("Resultado", (c.resultado >= 0 ? "+" : "−") + reais(Math.abs(c.resultado)),
            c.meses_declarados + " de " + serie.length + " competências completas",
            c.resultado >= 0 ? "bom" : "ruim"),
          kpi("Beneficiários na folha",
            (e.estatistica && e.estatistica.disponivel)
              ? num(e.estatistica.inativos, 0) : "—",
            "aposentados e pensionistas · DRAA")
        ]),
        cartao("Ingressos e dispêndios, competência a competência", "DIPR",
          "Em milhões de reais, na mesma escala · a linha se interrompe onde a " +
          "competência não foi declarada" +
          ((c.meses_sem_despesa || c.meses_sem_receita)
            ? " — " + (c.meses_sem_despesa || 0) + " sem dispêndio e " +
              (c.meses_sem_receita || 0) + " sem ingresso"
            : ""),
          [alvo, legenda([
            { cor: "var(--s1)", rotulo: "Ingressos", linha: true },
            { cor: "var(--s2)", rotulo: "Dispêndios", linha: true }
          ])]),
        h("div", { class: "grade duas" }, [
          cartao("De onde vem o dinheiro", "DIPR · rubricas de ingresso",
            "Soma das rubricas do período · bases de cálculo não entram",
            tabelaComposicao(c.origem)),
          cartao("Para onde vai", "DIPR · rubricas UT-",
            "Soma das rubricas de utilização de recursos",
            tabelaComposicao(c.destino))
        ])
      ].concat(depoisDeMontar(function () {
        Charts.desenhar(alvo, "linhas", {
          rotulos: rotulos, cada: serie.length > 14 ? 3 : 1, dec: 1, altura: 260,
          delta: "resultado", unidade: "/" + (serie[0] && serie[0].ano || ""),
          rotuloAusente: "não declarado",
          series: [
            { nome: "Ingressos", cor: "var(--s1)", dados: serie.map(function (p) {
              return p.receita === null ? null : p.receita / escalaMi; }) },
            { nome: "Dispêndios", cor: "var(--s2)", dados: serie.map(function (p) {
              return p.despesa === null ? null : p.despesa / escalaMi; }) }
          ],
          descricao: "Ingressos e dispêndios mensais"
        });
      }) || []);
    });
  }

  function abaCarteiraEnte() {
    if (!estado.cnpj) return abaCarteiraNacional();
    return Promise.all([
      carregarEnte(),
      buscar("qualidade.json").catch(function () { return null; })
    ]).then(function (r) {
      var e = r[0];
      var c = e.carteira || {};
      if (!c.disponivel) return [cabecalhoEnte(e), semDado("carteira", "DAIR_CARTEIRA")];

      var alocacao = c.segmentos.filter(function (s) { return s.alocacao; });
      var alvo = grafico(Math.max(160, alocacao.length * 46 + 22));

      return [
        h("h2", { class: "secao", texto: "Carteira de investimentos" }),
        cabecalhoEnte(e),
        h("div", { class: "contexto" }, [
          h("span", { class: "pilula" }, ["Ente ", h("b", { texto: e.ente })]),
          h("button", {
            class: "link limpar", texto: "ver o agregado nacional",
            onclick: function () { irParaAba("carteira", null); }
          })
        ]),
        c.excluidas ? h("div", { class: "aviso-linha" }, [
          h("span", { class: "ico", texto: "⚠" }),
          h("span", { html:
            "Este patrimônio não inclui " + num(c.excluidas, 0) +
            (c.excluidas > 1 ? " lançamentos que a própria base contradiz"
                             : " lançamento que a própria base contradiz") +
            ", no valor declarado de " + reaisExatos(c.valor_excluido) + ". " +
            "<a href=\"#/qualidade\">Ver a evidência</a>." })
        ]) : null,
        h("div", { class: "kpis" }, [
          kpi("Patrimônio da carteira", reais(c.total), c.ativos + " ativos declarados"),
          kpi("Segmentos fora do limite", num(c.fora_do_limite, 0),
            "Resolução CMN 3.922/10", c.fora_do_limite ? "ruim" : "bom"),
          kpi("Maior posição isolada", pct(c.maior_posicao), "de um único ativo"),
          kpi("Fundos em que o RPPS passa de 10% do PL", num(c.concentracao_pl, 0),
            "risco de liquidez na saída", c.concentracao_pl ? "ruim" : "bom")
        ]),
        cartao("Alocação por segmento contra o limite legal", "DAIR_CARTEIRA",
          "Barra = posição atual · marca vertical = limite da Resolução CMN 3.922/10",
          alvo),
        cartao("Maiores posições", "DAIR_CARTEIRA",
          "Ordenadas por valor · a última coluna sinaliza concentração no fundo",
          tabela([{ t: "Ativo" }, { t: "Segmento" }, { t: "Valor", n: true },
            { t: "% da carteira", n: true }, { t: "% do PL do fundo", n: true }],
            c.posicoes.map(function (p) {
              return h("tr", {}, [
                h("td", { texto: p.nome }),
                h("td", { texto: p.segmento || "—" }),
                h("td", { class: "n", texto: reais(p.valor) }),
                h("td", { class: "n", texto: pct(p.perc_carteira) }),
                h("td", {
                  class: "n " + ((p.perc_pl_fundo || 0) > 10 ? "alerta" : ""),
                  texto: pct(p.perc_pl_fundo)
                })
              ]);
            }), true))
      ].concat(depoisDeMontar(function () {
        Charts.desenhar(alvo, "comLimite", {
          linhas: alocacao, altura: Math.max(160, alocacao.length * 46 + 22),
          descricao: "Alocação por segmento contra o limite da Resolução CMN 3.922/10"
        });
      }) || []).concat(cartoesContabeis(e));
    });
  }

  function abaAtuaria() {
    if (!estado.cnpj) return Promise.resolve([semEnte("Atuária")]);
    return carregarEnte().then(function (e) {
      var a = e.atuaria || {};
      // Amortização e comparativo vêm de endpoints próprios e existem mesmo
      // quando o resultado atuarial falta. Um retorno cedo os escondia.
      if (!a.disponivel) {
        var soltos = cartoesDeAmortizacao(e).concat(cartaoProjetadoExecutado(e));
        return [h("h2", { class: "secao", texto: "Situação atuarial" }),
                cabecalhoEnte(e),
                semDado("resultado atuarial", "DRAA_VALORES_COMPROMISSOS")
               ].concat(soltos);
      }

      var r = a.resultado || {};
      var f = a.fluxo || {};
      var deficit = r.deficit || 0, superavit = r.superavit || 0;
      var alvo = f.disponivel ? grafico(118) : null;

      var nos = [
        h("h2", { class: "secao", texto: "Situação atuarial" }),
        cabecalhoEnte(e),
        h("div", { class: "contexto" }, [
          h("span", { class: "pilula" }, ["Exercício ", h("b", { texto: String(a.exercicio || "—") })])
        ]),
        h("div", { class: "kpis" }, [
          kpi("Resultado atuarial",
            reais(deficit > 0 ? deficit : superavit),
            deficit > 0 ? "déficit — provisões a cobrir"
              : superavit > 0 ? "superávit" : "equilíbrio",
            deficit > 0 ? "ruim" : superavit > 0 ? "bom" : ""),
          kpi("Ativos garantidores", reais(r.ativos_garantidores),
            "recursos que lastreiam o plano"),
          kpi("Receitas projetadas", reais(f.receitas), "total do fluxo atuarial"),
          kpi("Despesas projetadas", reais(f.despesas), "total do fluxo atuarial",
            (f.saldo || 0) < 0 ? "ruim" : "bom")
        ])
      ];

      if (f.disponivel) {
        nos.push(cartao("Fluxo atuarial projetado", "DRAA_FLUXO_ATUARIAL",
          "Totais projetados do plano — a API não devolve a projeção ano a ano, " +
          "então não há curva de cruzamento aqui",
          [alvo, legenda([
            { cor: "var(--s1)", rotulo: "Receitas projetadas" },
            { cor: "var(--s2)", rotulo: "Despesas projetadas" }
          ])]));
        nos.push(h("div", { class: "grade duas" }, [
          cartao("Composição das receitas", "DRAA_FLUXO_ATUARIAL",
            "Maiores itens projetados", tabelaItens(f.itens_receita)),
          cartao("Composição das despesas", "DRAA_FLUXO_ATUARIAL",
            "Maiores itens projetados", tabelaItens(f.itens_despesa))
        ]));
      }

      nos.push(h("div", { class: "grade duas" }, [
        cartao("Hipóteses da avaliação", "DRAA_HIPOTESE_ATUARIAL",
          "O que sustenta os números acima",
          (a.hipoteses || []).length
            ? h("div", { class: "campos" }, a.hipoteses.map(function (hp) {
                return campo(hp.descricao, hp.valor === null || hp.valor === undefined
                  ? "—" : String(hp.valor));
              }))
            : h("p", { class: "sub", texto: "Sem hipóteses no banco." })),
        cartao("Plano de custeio", "DRAA_PLANO_CUSTEIO",
          "Alíquota definida na avaliação atuarial",
          (a.custeio || []).length
            ? tabela([{ t: "Contribuição" }, { t: "Alíquota", n: true },
                { t: "Valor definido", n: true }],
              a.custeio.map(function (cu) {
                return h("tr", {}, [
                  h("td", { texto: cu.rotulo || "—" }),
                  h("td", { class: "n", texto: pct(cu.aliquota, 2) }),
                  h("td", { class: "n", texto: cu.contribuicao ? reais(cu.contribuicao) : "—" })
                ]);
              }))
            : h("p", { class: "sub", texto: "Sem plano de custeio no banco." }))
      ]));

      if ((a.compromissos || []).length) {
        nos.push(cartao("Compromissos do plano", "DRAA_VALORES_COMPROMISSOS",
          "Valor presente, por geração",
          tabela([{ t: "Item" }, { t: "Plano" }, { t: "Geração atual", n: true },
            { t: "Geração futura", n: true }],
            a.compromissos.map(function (co) {
              return h("tr", {}, [
                h("td", { texto: co.descricao || "—" }),
                h("td", { texto: co.plano || "—" }),
                h("td", { class: "n", texto: co.geracao_atual ? reais(co.geracao_atual) : "—" }),
                h("td", { class: "n", texto: co.geracao_futura ? reais(co.geracao_futura) : "—" })
              ]);
            }), true)));
      }

      nos = nos.concat(cartoesDeAmortizacao(e));
      nos = nos.concat(cartaoProjetadoExecutado(e));

      if (f.disponivel) {
        depoisDeMontar(function () {
          Charts.desenhar(alvo, "barraUnica", {
            altura: 118, alturaBarra: 30, titulo: "Fluxo atuarial projetado",
            partes: [
              { rotulo: "Receitas projetadas", valor: f.receitas || 0, cor: "var(--s1)" },
              { rotulo: "Despesas projetadas", valor: f.despesas || 0, cor: "var(--s2)" }
            ],
            descricao: "Receitas e despesas projetadas do plano"
          });
        });
      }
      return nos;
    });
  }

  function tabelaItens(itens) {
    if (!itens || !itens.length) return h("p", { class: "sub", texto: "Sem itens no banco." });
    return tabela([{ t: "Item" }, { t: "Valor", n: true }],
      itens.map(function (i) {
        return h("tr", {}, [
          h("td", { texto: i.descricao || "—" }),
          h("td", { class: "n", texto: reais(i.valor) })
        ]);
      }));
  }

  // ------------------------------------------------------------- aba comparativo

  var FORMATADORES = {
    percentual: function (v) { return num(v, 1) + "%"; },
    reais: reais,
    razao: function (v) { return num(v, 2); }
  };

  function abaComparativo() {
    if (!estado.cnpj) return Promise.resolve([semEnte("Comparativo")]);
    return Promise.all([carregarEnte(), comparativos()])
      .then(function (r) {
        var e = r[0], b = r[1];
        var meu = b.rpps[estado.cnpj];
        if (!meu) {
          return [cabecalhoEnte(e), vazio("Sem indicadores para este RPPS",
            "O comparativo depende de dados de carteira, caixa e atuária. " +
            "Este ente não tem o suficiente no banco local.")];
        }

        var ref = resolverReferencia(b, meu);
        var visiveis = indicadoresVisiveis(b, meu);
        var alvo = grafico(visiveis.length * 54);

        var linhasRegua = visiveis.map(function (ind) {
          var brasil = b.grupos.brasil.estatisticas[ind.chave];
          var grupo = ref.estatisticas ? ref.estatisticas[ind.chave] : null;
          var valor = meu.valores[ind.chave];
          var referencia = ref.valores ? ref.valores[ind.chave]
                                       : (grupo ? grupo.mediana : null);
          var minimo = brasil ? brasil.min : null;
          var maximo = brasil ? brasil.max : null;
          // A escala precisa conter os dois pontos, mesmo que um deles seja
          // extremo — senão o losango encosta na borda sem dizer o quanto passou.
          [valor, referencia].forEach(function (v) {
            if (v === null || v === undefined) return;
            if (minimo === null || v < minimo) minimo = v;
            if (maximo === null || v > maximo) maximo = v;
          });
          return {
            rotulo: ind.rotulo, valor: valor, referencia: referencia,
            p25: grupo ? grupo.p25 : null, p75: grupo ? grupo.p75 : null,
            min: minimo === null ? 0 : minimo, max: maximo === null ? 1 : maximo,
            posicao: grupo ? posicaoNoGrupo(valor, grupo) : null,
            formatar: FORMATADORES[ind.unidade] || FORMATADORES.razao
          };
        });

        var nos = [
          h("h2", { class: "secao", texto: "Comparativo" }),
          cabecalhoEnte(e),
          h("p", {
            class: "intro",
            texto: "Indicadores normalizados por tamanho — comparar o patrimônio " +
              "de um estado com o de um município de cinco mil habitantes mediria " +
              "porte, não gestão. A referência de grupo é a mediana, não a média: " +
              "uns poucos RPPS estaduais concentram a maior parte do patrimônio e " +
              "puxariam qualquer média para longe do RPPS típico."
          }),
          seletorReferencia(b, meu),
          avisoCobertura(ref),
          cartao("Posição em cada indicador", "vários endpoints",
            "A régua é a distribuição nacional inteira · a faixa é onde está a " +
            "metade do meio do grupo escolhido",
            [alvo, h("div", { class: "legenda" }, [
              h("span", {}, [h("i", { class: "losango", style: "background:var(--s2)" }),
                e.ente || "Selecionado"]),
              h("span", {}, [h("i", { class: "linha", style: "background:var(--s1)" }),
                ref.rotulo]),
              h("span", {}, [h("i", { style: "background:var(--s1);opacity:.32" }),
                ref.ente ? "metade do meio de todos os RPPS"
                         : "metade do meio do grupo"])
            ])]),
          cardAlocacao(b, meu, ref, e),
          tabelaComparativo(b, meu, ref)
        ];

        depoisDeMontar(function () {
          Charts.desenhar(alvo, "reguas", {
            linhas: linhasRegua, altura: visiveis.length * 54,
            nomeRpps: e.ente, nomeReferencia: ref.rotulo,
            descricao: "Posição do RPPS em cada indicador"
          });
        });
        return nos;
      });
  }

  function avisoCobertura(ref) {
    if (!ref.ente) return null;
    if (ref.disponiveis === ref.total) return null;
    var faltam = ref.total - ref.disponiveis;
    return h("div", { class: "aviso-linha" }, [
      h("span", { class: "ico", texto: "⚠" }),
      h("span", {
        texto: ref.rotulo + " tem " + ref.disponiveis + " dos " + ref.total +
          " indicadores no banco local — " + faltam +
          (faltam === 1 ? " fica" : " ficam") + " sem comparação. " +
          "Pode ser que este RPPS não tenha declarado no período ingerido."
      })
    ]);
  }

  function cardAlocacao(b, meu, ref, e) {
    var temCarteira = meu.alocacao && Object.keys(meu.alocacao).length;
    if (!temCarteira) {
      return cartao("Perfil da carteira", "DAIR_CARTEIRA",
        "Sem carteira no banco para este RPPS", null);
    }
    var perfilRef = ref.ente ? ref.ente.alocacao
                             : (ref.alocacao || b.grupos.brasil.alocacao);
    var refTemCarteira = ref.ente
      ? Object.keys(ref.ente.alocacao || {}).length > 0 : true;
    var linhas = b.segmentos.map(function (seg) {
      var referencia = ref.ente
        ? (perfilRef[seg] === undefined ? null : perfilRef[seg])
        : (perfilRef[seg] ? perfilRef[seg].mediana : null);
      return {
        rotulo: seg,
        valor: meu.alocacao[seg] === undefined ? 0 : meu.alocacao[seg],
        referencia: referencia
      };
    }).filter(function (l) { return l.valor > 0 || (l.referencia || 0) > 0; });

    var alvo = grafico(linhas.length * 34 + 8);
    depoisDeMontar(function () {
      Charts.desenhar(alvo, "barrasPareadas", {
        linhas: linhas, altura: linhas.length * 34 + 8,
        nomeRpps: e.ente, nomeReferencia: ref.rotulo,
        descricao: "Alocação por segmento comparada"
      });
    });
    return cartao("Perfil da carteira por segmento", "DAIR_CARTEIRA",
      refTemCarteira
        ? "Percentual do patrimônio em cada segmento — a comparação que " +
          "independe do porte do RPPS"
        : ref.rotulo + " não tem carteira no banco local; só o perfil deste " +
          "RPPS aparece abaixo",
      [alvo, h("div", { class: "legenda" }, [
        h("span", {}, [h("i", { style: "background:var(--s2)" }), e.ente || "Selecionado"]),
        h("span", {}, [h("i", { style: "background:var(--s1)" }), ref.rotulo])
      ])]);
  }

  function posicaoNoGrupo(valor, grupo) {
    if (valor === null || valor === undefined || !grupo) return null;
    // Aproximação a partir dos quartis: o suficiente para dizer em que parte da
    // distribuição o RPPS está, sem carregar a série inteira para o navegador.
    if (valor <= grupo.min) return 0;
    if (valor >= grupo.max) return 100;
    if (valor < grupo.p25) return Math.round(25 * (valor - grupo.min) / ((grupo.p25 - grupo.min) || 1));
    if (valor < grupo.mediana) return Math.round(25 + 25 * (valor - grupo.p25) / ((grupo.mediana - grupo.p25) || 1));
    if (valor < grupo.p75) return Math.round(50 + 25 * (valor - grupo.mediana) / ((grupo.p75 - grupo.mediana) || 1));
    return Math.round(75 + 25 * (valor - grupo.p75) / ((grupo.max - grupo.p75) || 1));
  }

  /* Estatística de um conjunto escolhido a dedo.
   *
   * Espelha cadprev/benchmark.py: mesmo percentil por interpolação linear,
   * mesma recusa de resumir menos de três valores. É a única aritmética do
   * projeto que existe nos dois lados, e existe porque o conjunto é montado
   * aqui — não há como pré-calcular a mediana de uma seleção arbitrária.
   * Conferida contra os grupos pré-calculados: selecionar todos os RPPS de uma
   * região tem de reproduzir exatamente a mediana daquela região.
   */
  function percentilJS(ordenados, p) {
    if (!ordenados.length) return null;
    if (ordenados.length === 1) return ordenados[0];
    var posicao = (ordenados.length - 1) * p;
    var baixo = Math.floor(posicao);
    var alto = Math.min(baixo + 1, ordenados.length - 1);
    var peso = posicao - baixo;
    return ordenados[baixo] * (1 - peso) + ordenados[alto] * peso;
  }

  /* O arredondamento do round() do Python, replicado.
   *
   * Duas armadilhas, e as duas apareceram na conferência contra os grupos
   * pré-calculados. Math.round(v * 100) / 100 erra porque multiplicar por cem
   * introduz erro de ponto flutuante: 4,215 vira 421.50000000000006 e sobe para
   * 4,22, quando o Python devolve 4,21. E toFixed(2) sozinho erra no empate
   * exato: 4,625 é representável em binário, o Python manda para o par (4,62) e
   * o toFixed sobe (4,63).
   *
   * Por isso se olha a expansão decimal e se decide na mão: acima do meio sobe,
   * abaixo desce, e no empate exato vai para o centésimo par.
   */
  function arredondar(v) {
    if (v === null || v === undefined) return null;
    if (typeof v !== "number" || !isFinite(v) || Math.abs(v) >= 1e15) return v;
    var negativo = v < 0;
    var texto = Math.abs(v).toFixed(20);
    var ponto = texto.indexOf(".");
    var centesimos = Number(texto.slice(0, ponto) + texto.slice(ponto + 1, ponto + 3));
    var sobra = texto.slice(ponto + 3);
    var primeiro = sobra.charCodeAt(0) - 48;
    var sobe;
    if (primeiro > 5) sobe = true;
    else if (primeiro < 5) sobe = false;
    else sobe = /[1-9]/.test(sobra.slice(1)) ? true : centesimos % 2 === 1;
    var resultado = (centesimos + (sobe ? 1 : 0)) / 100;
    return negativo ? -resultado : resultado;
  }

  function resumirJS(valores) {
    var limpos = valores.filter(function (v) {
      return v !== null && v !== undefined;
    }).sort(function (a, z) { return a - z; });
    if (limpos.length < 3) return null;
    return {
      n: limpos.length,
      min: arredondar(limpos[0]),
      p25: arredondar(percentilJS(limpos, 0.25)),
      mediana: arredondar(percentilJS(limpos, 0.50)),
      p75: arredondar(percentilJS(limpos, 0.75)),
      max: arredondar(limpos[limpos.length - 1])
    };
  }

  function medianaJS(valores) {
    var limpos = valores.filter(function (v) {
      return v !== null && v !== undefined;
    }).sort(function (a, z) { return a - z; });
    return limpos.length ? arredondar(percentilJS(limpos, 0.50)) : null;
  }

  function grupoDaSelecao(b, cnpjs) {
    var membros = cnpjs.map(function (c) { return b.rpps[c]; })
      .filter(Boolean);
    var estatisticas = {}, medianas = {};
    b.indicadores.forEach(function (ind) {
      var valores = membros.map(function (m) { return m.valores[ind.chave]; });
      var resumo = resumirJS(valores);
      if (resumo) estatisticas[ind.chave] = resumo;
      medianas[ind.chave] = medianaJS(valores);
    });
    // Um RPPS sem carteira fica de fora do perfil; um com carteira e sem aquele
    // segmento conta como zero, que é o valor verdadeiro. Mesma regra do Python.
    var comCarteira = membros.filter(function (m) {
      return m.alocacao && Object.keys(m.alocacao).length;
    });
    var alocacao = {};
    b.segmentos.forEach(function (seg) {
      var valores = comCarteira.map(function (m) {
        return m.alocacao[seg] === undefined ? 0 : m.alocacao[seg];
      });
      var resumo = resumirJS(valores);
      if (resumo) alocacao[seg] = resumo;
      else if (valores.length) alocacao[seg] = { mediana: medianaJS(valores) };
    });
    return { rpps: membros.length, com_carteira: comCarteira.length,
             estatisticas: estatisticas, medianas: medianas, alocacao: alocacao };
  }

  function resolverReferencia(b, meu) {
    if (estado.referencia === "regiao") {
      var g = b.grupos.regiao[meu.regiao];
      return g ? { rotulo: "Mediana · " + meu.regiao, estatisticas: g.estatisticas,
                   alocacao: g.alocacao, rpps: g.rpps }
               : { rotulo: "Região sem grupo", estatisticas: null, rpps: 0 };
    }
    if (estado.referencia === "porte") {
      var p = b.grupos.porte[meu.porte];
      var nome = b.rotulos_porte[meu.porte] || meu.porte;
      return p ? { rotulo: "Mediana · " + nome, estatisticas: p.estatisticas,
                   alocacao: p.alocacao, rpps: p.rpps }
               : { rotulo: "Porte sem grupo", estatisticas: null, rpps: 0 };
    }
    if (estado.referencia === "selecao" && estado.selecao.length) {
      var escolhidos = estado.selecao.filter(function (c) { return b.rpps[c]; });
      if (escolhidos.length === 1) {
        var outro = b.rpps[escolhidos[0]];
        var disponiveis = b.indicadores.filter(function (i) {
          var v = outro.valores[i.chave];
          return v !== null && v !== undefined;
        }).length;
        return { rotulo: outro.ente, valores: outro.valores,
                 estatisticas: b.grupos.brasil.estatisticas,
                 alocacao: b.grupos.brasil.alocacao,
                 rpps: 1, ente: outro, disponiveis: disponiveis,
                 total: b.indicadores.length };
      }
      if (escolhidos.length > 1) {
        var g = grupoDaSelecao(b, escolhidos);
        return { rotulo: "Mediana · " + escolhidos.length + " selecionados",
                 valores: g.medianas, estatisticas: g.estatisticas,
                 alocacao: g.alocacao, rpps: g.rpps,
                 poucos: escolhidos.length < 3 };
      }
    }
    return { rotulo: "Mediana · todos os RPPS",
             estatisticas: b.grupos.brasil.estatisticas,
             alocacao: b.grupos.brasil.alocacao,
             rpps: b.grupos.brasil.rpps };
  }

  function seletorReferencia(b, meu) {
    var opcoes = [
      { chave: "brasil", rotulo: "Todos os RPPS",
        nota: b.grupos.brasil.rpps + " no banco" },
      { chave: "regiao", rotulo: meu.regiao || "Região",
        nota: (b.grupos.regiao[meu.regiao] || {}).rpps
          ? b.grupos.regiao[meu.regiao].rpps + " RPPS" : "sem grupo" },
      { chave: "porte", rotulo: b.rotulos_porte[meu.porte] || "Porte",
        nota: (b.grupos.porte[meu.porte] || {}).rpps
          ? b.grupos.porte[meu.porte].rpps + " RPPS" : "sem grupo" },
      { chave: "selecao", rotulo: "Seleção",
        nota: estado.selecao.length
          ? estado.selecao.length + (estado.selecao.length > 1 ? " escolhidos" : " escolhido")
          : "escolher RPPS" }
    ];

    var botoes = opcoes.map(function (o) {
      var b2 = h("button", {
        type: "button", class: "opcao" + (estado.referencia === o.chave ? " on" : ""),
        "aria-pressed": estado.referencia === o.chave ? "true" : "false"
      }, [
        h("span", { class: "t", texto: o.rotulo }),
        h("span", { class: "n", texto: o.nota })
      ]);
      b2.addEventListener("click", function () {
        estado.referencia = o.chave;
        if (o.chave !== "selecao") {
          estado.selecao = []; estado.selecaoUf = ""; estado.selecaoAberta = false;
        }
        render();
      });
      return b2;
    });

    var filhos = [
      h("div", { class: "rotulo-grupo", texto: "Comparar com" }),
      h("div", { class: "opcoes" }, botoes)
    ];

    if (estado.referencia === "selecao") filhos.push(escolhaDeRpps(b));
    return h("div", { class: "referencia" }, filhos);
  }

  /* Um combobox com 5.596 opções é uma lista para rolar, não para escolher — e
   * não deixa comparar com mais de um. Aqui a busca é a mesma do topo (sem
   * exigir acento), a UF restringe, e o que foi escolhido vira ficha removível.
   * Com a UF marcada dá para levar o estado inteiro de uma vez, que é a
   * comparação que motivou isto: o meu RPPS contra os vizinhos. */
  function escolhaDeRpps(b) {
    var elegiveis = Object.keys(b.rpps).filter(function (c) {
      return c !== estado.cnpj;
    });
    var porCnpj = {};
    elegiveis.forEach(function (c) { porCnpj[c] = b.rpps[c]; });

    var campo = h("input", { type: "search", class: "busca-ref",
      autocomplete: "off", placeholder: "Buscar RPPS para comparar…" });
    var seletor = h("select", { class: "uf-filtro" },
      [h("option", { value: "", texto: "UF" })].concat(
        ufsConhecidas().map(function (uf) {
          var op = h("option", { value: uf, texto: uf });
          if (uf === estado.selecaoUf) op.setAttribute("selected", "selected");
          return op;
        })));
    var achados = h("div", { class: "achados-ref" });

    function daUf(uf) {
      return elegiveis.filter(function (c) { return porCnpj[c].uf === uf; });
    }

    function acrescentar(cnpjs) {
      cnpjs.forEach(function (c) {
        if (estado.selecao.indexOf(c) < 0) estado.selecao.push(c);
      });
      render();
    }

    function listar() {
      var uf = seletor.value || null;
      var alvo = semAcento(campo.value).trim();
      achados.textContent = "";
      if (!alvo && !uf) return;
      // Já escolhidos saem da lista: oferecê-los de novo é ruído, e contá-los
      // no "e mais N" faria o número prometer resultados que não existem.
      var lista = elegiveis.filter(function (c) {
        if (estado.selecao.indexOf(c) >= 0) return false;
        if (uf && porCnpj[c].uf !== uf) return false;
        if (alvo.length < 2) return true;
        return semAcento(porCnpj[c].ente).indexOf(alvo) >= 0;
      });
      if (uf) {
        var faltam = daUf(uf).filter(function (c) {
          return estado.selecao.indexOf(c) < 0;
        });
        if (faltam.length) {
          achados.appendChild(h("button", {
            type: "button", class: "todos-uf",
            texto: "+ todos os " + faltam.length + " RPPS de " + uf,
            onclick: function () { acrescentar(faltam); }
          }));
        }
      }
      lista.slice(0, 40).forEach(function (c) {
        achados.appendChild(h("button", {
          type: "button",
          onclick: function () { acrescentar([c]); }
        }, [porCnpj[c].ente,
            h("span", { class: "uf", texto: porCnpj[c].uf || "" })]));
      });
      if (lista.length > 40) {
        achados.appendChild(h("span", { class: "mais",
          texto: "e mais " + num(lista.length - 40, 0) + " — refine o nome" }));
      }
    }

    campo.addEventListener("input", listar);
    seletor.addEventListener("change", function () {
      estado.selecaoUf = seletor.value;
      listar();
    });

    function ficha(c) {
      var r = porCnpj[c];
      return h("span", { class: "ficha-ref" }, [
        document.createTextNode((r ? r.ente : c) + (r && r.uf ? " · " + r.uf : "")),
        h("button", {
          type: "button", "aria-label": "Remover " + (r ? r.ente : c), texto: "×",
          onclick: function () {
            estado.selecao = estado.selecao.filter(function (x) { return x !== c; });
            render();
          }
        })
      ]);
    }

    /* Somar um estado inteiro produz oitenta fichas, e oitenta fichas empurram
     * a comparação — que é o objeto da tela — para fora da primeira dobra. A
     * lista fica dobrada por padrão; quem quiser conferir item a item abre. */
    var LIMITE_DOBRA = 8;
    var caixaFichas = h("div", { class: "fichas-ref" });

    function desenharFichas() {
      caixaFichas.textContent = "";
      if (!estado.selecao.length) return;
      var dobrar = estado.selecao.length > LIMITE_DOBRA && !estado.selecaoAberta;
      var visiveis = dobrar ? estado.selecao.slice(0, LIMITE_DOBRA) : estado.selecao;
      visiveis.forEach(function (c) { caixaFichas.appendChild(ficha(c)); });
      if (estado.selecao.length > LIMITE_DOBRA) {
        caixaFichas.appendChild(h("button", {
          type: "button", class: "link limpar",
          texto: dobrar ? "+ " + (estado.selecao.length - LIMITE_DOBRA) + " outros"
                        : "mostrar menos",
          onclick: function () {
            estado.selecaoAberta = !estado.selecaoAberta;
            desenharFichas();
          }
        }));
      }
      caixaFichas.appendChild(h("button", {
        type: "button", class: "link limpar", texto: "limpar seleção",
        onclick: function () {
          estado.selecao = []; estado.selecaoAberta = false; render();
        }
      }));
    }
    desenharFichas();

    var partes = [h("div", { class: "linha-busca" }, [campo, seletor]), achados];
    if (estado.selecao.length) {
      partes.push(h("p", { class: "resumo-selecao", texto:
        estado.selecao.length + " RPPS na comparação" +
        (estado.selecaoUf ? " · filtrando " + estado.selecaoUf : "") }));
      partes.push(caixaFichas);
    }
    if (estado.selecao.length === 2) {
      partes.push(h("p", { class: "nota", texto:
        "Com dois selecionados a linha de referência é a mediana dos dois, mas " +
        "não há faixa interquartil: quartis sobre dois pontos são aritmética, " +
        "não informação. A partir de três a faixa aparece." }));
    }
    var caixa = h("div", { class: "escolha-rpps" }, partes);
    depoisDeMontar(listar);
    return caixa;
  }

  /* Indicador que não tem assunto para este RPPS não é indicador sem dado: é
   * indicador que não se aplica. Município não tem militar — mostrar a linha
   * com um travessão sugeriria que falta declaração, quando o que falta é a
   * própria massa. */
  function indicadoresVisiveis(b, meu) {
    return b.indicadores.filter(function (ind) {
      if (ind.chave !== "razao_militar") return true;
      var v = meu.valores[ind.chave];
      return v !== null && v !== undefined;
    });
  }

  function tabelaComparativo(b, meu, ref) {
    var linhas = indicadoresVisiveis(b, meu).map(function (ind) {
      var fmt = FORMATADORES[ind.unidade] || FORMATADORES.razao;
      var valor = meu.valores[ind.chave];
      var grupo = ref.estatisticas ? ref.estatisticas[ind.chave] : null;
      var referencia = ref.valores ? ref.valores[ind.chave]
                                   : (grupo ? grupo.mediana : null);
      var classe = "";
      if (ind.direcao && valor !== null && referencia !== null &&
          valor !== undefined && referencia !== undefined) {
        var acima = valor > referencia;
        classe = (ind.direcao === "maior") === acima ? "bom" : "ruim";
      }
      return h("tr", {}, [
        h("td", {}, [
          h("div", { texto: ind.rotulo }),
          h("div", { class: "nota", texto: ind.nota })
        ]),
        h("td", { class: "n " + classe,
          texto: valor === null || valor === undefined ? "—" : fmt(valor) }),
        h("td", { class: "n",
          texto: referencia === null || referencia === undefined ? "—" : fmt(referencia) }),
        h("td", { class: "fonte-col mono", texto: ind.fonte })
      ]);
    });
    return cartao("Indicadores lado a lado", null,
      "Verde e vermelho só nos indicadores de direção inequívoca — quanto mais " +
      "renda fixa ou quanto maior a alíquota não é melhor nem pior por si",
      tabela([{ t: "Indicador" }, { t: "Este RPPS", n: true },
        { t: ref.rotulo, n: true }, { t: "Fonte", classe: "fonte-col" }],
        linhas, true));
  }

  // ------------------------------------------------------------- aba ajuda

  function abaAjuda() {
    var m = estado.meta || {};
    return Promise.resolve([
      h("h2", { class: "secao", texto: "Ajuda" }),
      h("p", {
        class: "intro",
        texto: "De onde vêm os dados, o que eles não cobrem e quem responde pelo quê."
      }),
      h("div", { class: "ajuda" }, [
        cartao("O que é este painel", null, null,
          h("p", {
            texto: "Uma leitura visual dos dados públicos do CADPREV sobre os Regimes " +
              "Próprios de Previdência Social. Consome a API aberta da Subsecretaria dos " +
              "Regimes Próprios de Previdência Social e reorganiza o que já é público em " +
              "telas que respondem a perguntas diretas: o regime está regular, arrecada " +
              "mais do que paga, onde investe e se as promessas fecham no longo prazo."
          })),
        cartao("Pontos relevantes", null, null,
          h("ul", {}, [
            "Nenhum dado é produzido aqui. Tudo vem da API do CADPREV, sem ajuste editorial.",
            "Cada cartão mostra o endpoint de origem — dá para conferir na fonte.",
            "Séries na mesma unidade dividem a mesma escala. Não há eixo duplo em lugar nenhum.",
            "Quando um recorte não pode ser derivado da API, a tela diz isso em vez de estimar.",
            "Os números são pré-agregados na ingestão; a API não é consultada a cada clique."
          ].map(function (t) { return h("li", { texto: t }); }))),
        cartao("As chaves do topo e o que elas recortam", null, null, [
          h("p", {
            texto: "As estatísticas nacionais dependem de quem entra na conta, " +
              "e essa escolha é sua. As chaves no topo das telas nacionais " +
              "recortam o universo; a URL carrega o recorte, então um link " +
              "compartilhado mostra ao destinatário exatamente o que você viu."
          }),
          h("p", {
            texto: "A primeira chave já vem ligada, e é a única assim. O CRP é " +
              "emitido ao ente federativo, não ao fundo, então a base cobre os " +
              "5.596 entes do país — e só cerca de 2.100 mantêm RPPS. Contar " +
              "todos como RPPS não é um recorte possível: é um erro de " +
              "denominador, e por isso o padrão o corrige."
          }),
          h("p", {
            texto: "As outras três desligadas medem a atualidade do dado, não a " +
              "sua correção. Um RPPS que entregou o último DAIR há cinco meses " +
              "não errou nada: apenas descreve uma situação mais antiga. Se " +
              "isso desqualifica o número depende da pergunta que você está " +
              "fazendo, e quem decide é quem pergunta."
          })
        ]),
        cartao("Militares, e por que eles ficam à parte", null, null, [
          h("p", {
            texto: "Só os Estados têm massa militar — em 17/09/2026, 26 dos 27 " +
              "governos estaduais e nenhum dos 5.569 municípios. Onde existe, " +
              "é de 14% a 39% da população declarada, e a razão entre ativos e " +
              "beneficiários não acompanha a civil do mesmo ente."
          }),
          h("p", {
            texto: "Militar não se aposenta: passa à reserva e depois à " +
              "reforma. O CADPREV grava o grupo como \u201cMILITARES - " +
              "APOSENTADOS\u201d; o painel mostra o termo do regime e registra " +
              "o da fonte ao lado. É a única troca de termo do projeto, e ela " +
              "fica visível para poder ser conferida."
          }),
          h("p", {
            texto: "O DAIR não separa a carteira por massa, então o patrimônio " +
              "de um Estado é o do RPPS inteiro, civil e militar juntos. O " +
              "painel diz isso em vez de repartir o número por um critério que " +
              "nenhuma fonte declara."
          })
        ]),
        cartao("Erros de cadastro e o que o painel faz com eles", null, null, [
          h("p", {
            texto: "A fonte tem erros de digitação, e um só deles chegou a " +
              "responder por 88% do patrimônio nacional: uma cota lançada a R$ " +
              "36.640.481,00 quando vale R$ 36,64. Nenhum corte estatístico " +
              "separa isso de um RPPS grande — o maior do país é legitimamente " +
              "milhares de vezes maior que o menor."
          }),
          h("p", {
            texto: "A régua, então, não é estatística: é aritmética. Cada linha " +
              "da carteira traz a posição do RPPS e o patrimônio do fundo em que " +
              "ela está aplicada, e o mesmo fundo aparece na carteira de " +
              "centenas de RPPS. Quando uma posição excede em mais de dez vezes " +
              "a maior declaração já feita para aquele fundo, ela é impossível, " +
              "e sai de todas as somas — inclusive da ficha do próprio ente."
          }),
          h("p", {
            texto: "O valor não é corrigido. Dividir por um milhão daria o " +
              "número certo e seria inventá-lo: o painel reapresenta o que a " +
              "fonte diz, e quando não pode reapresentar, omite e explica. Cada " +
              "exclusão aparece nomeada na aba Qualidade, com a evidência ao " +
              "lado, para que quem pode corrigir na fonte corrija."
          }),
          h("p", { class: "nota",
            texto: "A margem de dez vezes é grosseira de propósito. Entre uma " +
              "vez e mil vezes ela devolve exatamente as mesmas linhas, o que " +
              "mostra que o resultado não vem do parâmetro escolhido." })
        ]),
        cartao("A segunda fonte, e o que fazer quando elas discordam", null, null, [
          h("p", {
            texto: "O SICONFI, do Tesouro Nacional, é a contabilidade do ente " +
              "federativo. O que casa as duas bases é o CNPJ, e ele casa em " +
              "5.594 dos 5.596 entes que o CADPREV conhece — igualdade de " +
              "chave, sem correspondência aproximada."
          }),
          h("p", {
            texto: "Dele vem a separação dos recursos entre fundo em " +
              "capitalização, fundo em repartição e taxa de administração. O " +
              "CADPREV traz a carteira ativo a ativo, mas sem o plano de cada " +
              "ativo, e por isso esta decomposição estava fora do alcance do " +
              "painel até agora."
          }),
          h("p", {
            texto: "Quando as duas fontes discordam sobre o mesmo patrimônio, " +
              "as duas aparecem. Não há como escolher entre elas sem esconder " +
              "o achado: são apurações independentes, com datas de posição e " +
              "critérios distintos, e a distância entre elas é informação sobre " +
              "o cadastro. Em Vitória, na competência de junho de 2026, elas " +
              "diferem em 0,18%."
          }),
          h("p", { class: "nota",
            texto: "Municípios com menos de cinquenta mil habitantes entregam " +
              "o RREO Simplificado, sob outro nome de demonstrativo. Consultar " +
              "só o comum faz 45% dos RPPS parecerem ausentes — foi o que " +
              "aconteceu na primeira medição deste projeto, que concluiu 53% " +
              "de cobertura onde há 96%." })
        ]),
        cartao("Como o comparativo funciona", null, null, [
          h("p", {
            texto: "Os indicadores são normalizados por tamanho — percentuais e " +
              "razões. Comparar o patrimônio de um estado com o de um município " +
              "de cinco mil habitantes mediria porte, não gestão."
          }),
          h("p", {
            texto: "A referência de grupo é a mediana, não a média: uns poucos " +
              "RPPS estaduais concentram a maior parte do patrimônio e puxariam " +
              "qualquer média para longe do RPPS típico. A faixa no gráfico é o " +
              "intervalo entre o primeiro e o terceiro quartil — onde está a " +
              "metade do meio do grupo."
          }),
          h("p", {
            texto: "A referência também pode ser um conjunto montado à mão: " +
              "busque pelo nome, filtre por UF, e some quantos RPPS quiser. " +
              "Com a UF marcada dá para levar o estado inteiro de uma vez — o " +
              "seu RPPS contra os vizinhos. Com um só escolhido, a comparação " +
              "é direta; com vários, a referência passa a ser a mediana deles."
          }),
          h("p", { class: "nota",
            texto: "A mediana de uma seleção é calculada no navegador, porque " +
              "não há como pré-computar a mediana de um conjunto montado na " +
              "hora. É a única conta do projeto que existe nos dois lados, e um " +
              "teste do repositório exige que ela reproduza os grupos " +
              "pré-calculados até o último centésimo." }),
          h("p", {
            texto: "Grupos com menos de três RPPS não geram estatística: quartis " +
              "sobre dois pontos são aritmética, não informação. E verde e " +
              "vermelho aparecem só nos indicadores de direção inequívoca; mais " +
              "renda fixa ou alíquota maior não é melhor nem pior por si."
          })
        ]),
        cartao("Limitações", null, null,
          h("ul", {}, [
            "Os dados dependem do que cada RPPS declarou. Declaração ausente, atrasada ou " +
            "incorreta aparece aqui como ausência ou erro — não há como distinguir.",
            "Quem não enviou o demonstrativo na competência fica fora dos totais.",
            "ISP, MSC, parcelamentos e enquadramento de fundos não têm endpoint na API.",
            "A separação da carteira por fundo depende de um campo ainda não confirmado; " +
            "o nível em vigor aparece na aba Carteira.",
            "A marcação de capitais depende de uma tabela auxiliar mantida no repositório, " +
            "não da API.",
            "O comparativo só enxerga os RPPS ingeridos. Com uma UF só no banco, " +
            "\u0022todos os RPPS\u0022 quer dizer todos os daquela UF.",
            "Há defasagem entre o fato e a publicação. O painel não é fonte para prazo legal."
          ].map(function (t) { return h("li", { texto: t }); }))),
        h("div", { class: "cartao isencao" }, [
          h("div", { class: "cartao-h" }, [h("h3", { texto: "Responsabilidade" })]),
          h("p", {
            texto: "Este é um projeto independente, sem vínculo com o Ministério da " +
              "Previdência Social, com a Subsecretaria dos Regimes Próprios de Previdência " +
              "Social ou com qualquer RPPS."
          }),
          h("p", {
            html: "Os dados são reapresentados no estado em que foram obtidos. O " +
              "desenvolvedor não garante exatidão, completude ou atualidade, e <strong>não " +
              "se responsabiliza por decisões tomadas com base nestas telas</strong>. Para " +
              "qualquer uso oficial, fiscal ou jurídico, a fonte é o CADPREV."
          })
        ]),
        cartao("Contato e colaboração", null, null, [
          h("p", {
            texto: "O projeto é aberto e as contribuições são bem-vindas — correções de " +
              "interpretação dos dados, novos recortes, relatos de divergência com a fonte."
          }),
          h("ul", { class: "contato" }, [
            h("li", {}, [
              h("span", { class: "ck", texto: "Código e issues" }),
              h("a", {
                href: "https://github.com/gilbertotulli/dashboard-cadprev",
                texto: "github.com/gilbertotulli/dashboard-cadprev"
              })
            ]),
            h("li", {}, [
              h("span", { class: "ck", texto: "Contato direto" }),
              h("a", {
                href: "mailto:gilberto.tulli@ipajm.es.gov.br",
                texto: "gilberto.tulli@ipajm.es.gov.br"
              })
            ])
          ])
        ]),
        h("div", { class: "cartao agradece" }, [
          h("div", { class: "cartao-h" }, [h("h3", { texto: "Agradecimento" })]),
          h("p", {
            html: "À <strong>Subsecretaria dos Regimes Próprios de Previdência Social</strong> " +
              "pela disponibilização dos dados do CADPREV em formato aberto e sem exigência " +
              "de credencial. É essa decisão que torna possível qualquer leitura independente " +
              "como esta — inclusive a que aponta problemas."
          })
        ]),
        cartao("Esta cópia", null, null,
          h("div", { class: "campos" }, [
            campo("Origem dos dados", m.origem === "demonstracao" ? "Demonstração (sintéticos)" : "API do CADPREV"),
            campo("Gerado em", data(m.gerado_em)),
            campo("RPPS no banco", num(m.entes, 0)),
            campo("Nível de decomposição", m.nivel_fundo ? "Nível " + m.nivel_fundo : "—"),
            campo("Capitais conhecidas", num(m.capitais_conhecidas, 0) + " de 27")
          ]))
      ])
    ]);
  }

  // ------------------------------------------------------------- roteamento

  /* O plano de amortização é a única série ano a ano que a API entrega. O
   * DRAA_FLUXO_ATUARIAL dá totais projetados; aqui há a curva, e com ela a
   * pergunta que interessa: o saldo devedor chega a zero, e quando. */
  function cartoesDeAmortizacao(e) {
    var a = e.amortizacao || {};
    var blocos = (a.blocos || []).filter(function (b) {
      return (b.anos || []).length;
    });
    if (!a.disponivel || !blocos.length) return [];

    var nos = [h("h3", { class: "secao", texto: "Plano de amortização" })];
    if (blocos.length > 1) {
      nos.push(h("p", { class: "nota", texto:
        "A fonte declara " + blocos.length + " planos separados — um por fundo e " +
        "por massa. Cada um tem o seu saldo e o seu ano de quitação; somá-los " +
        "produziria um saldo que não existe em nenhum deles." }));
    }
    blocos.forEach(function (b) {
      nos = nos.concat(umPlanoDeAmortizacao(b, a.exercicio, blocos.length > 1));
    });
    return nos;
  }

  function umPlanoDeAmortizacao(a, exercicio, nomear) {
    /* Milhões sempre, mesmo quando o saldo passa do bilhão: em bilhões um
     * saldo de 1,04 bi rende marcas de eixo "1, 1, 1, 0, 0" — resolução de
     * menos para uma curva cujo assunto é justamente descer até zero. */
    var escala = 1e6, sufixo = " mi";

    var alvo = grafico(260);
    depoisDeMontar(function () {
      Charts.desenhar(alvo, "linhas", {
        altura: 260, dec: 1,
        cada: a.anos.length > 20 ? 4 : 2,
        unidade: sufixo,
        rotulos: a.anos.map(function (x) { return String(x.ano); }),
        series: [{
          nome: "Saldo devedor", cor: a.militar ? "var(--s2)" : "var(--s1)",
          dados: a.anos.map(function (x) {
            return x.saldo_final === null || x.saldo_final === undefined
              ? null : x.saldo_final / escala;
          })
        }],
        descricao: "Saldo devedor projetado ano a ano" +
          (nomear ? " — " + a.rotulo : "")
      });
    });

    // Quando a amortização do ano é negativa, o pagamento não cobre os juros e
    // o saldo cresce. É o oposto do que um plano de amortização promete, e não
    // aparece em nenhum total — só na curva.
    var crescendo = a.anos.filter(function (x) {
      return (x.amortizacao || 0) < 0;
    }).length;

    var nos = [];
    if (nomear) nos.push(h("p", { class: "rotulo-massa", texto: a.rotulo }));
    nos.push(h("div", { class: "kpis" }, [
      kpi("Saldo a amortizar", reais(a.saldo_inicial),
        "em " + (a.primeiro_ano || "—")),
      kpi("Quitação prevista", a.ano_quitacao ? String(a.ano_quitacao) : "não zera",
        a.ano_quitacao ? "pelo plano vigente" : "o plano não chega a zero",
        a.ano_quitacao ? "bom" : "ruim"),
      kpi("Juros até a quitação", reais(a.total_juros),
        (a.taxa_juros ? "taxa de " + pct(a.taxa_juros, 2) : "taxa não declarada")),
      kpi("Aportes previstos", reais(a.total_aporte),
        "além das contribuições")
    ]));
    if (crescendo) {
      nos.push(h("div", { class: "aviso-linha" }, [
        h("span", { class: "ico", texto: "\u26a0" }),
        h("span", { texto:
          "Em " + crescendo + (crescendo > 1 ? " anos" : " ano") +
          " a amortização é negativa: o pagamento previsto não cobre os juros " +
          "do período e o saldo devedor cresce." })
      ]));
    }
    nos.push(cartao("Saldo devedor projetado" + (nomear ? " · " + a.rotulo : ""),
      "DRAA_PLANO_AMORTIZACAO",
      "Avaliação de " + (exercicio || "—") + " · " + a.anos.length +
      " anos, de " + a.primeiro_ano + " a " + a.ultimo_ano,
      alvo));
    nos.push(cartao("Primeiros anos do plano" + (nomear ? " · " + a.rotulo : ""),
      "DRAA_PLANO_AMORTIZACAO",
      "Juros e amortização de cada exercício",
      tabela([{ t: "Ano", n: true }, { t: "Saldo inicial", n: true },
              { t: "Juros", n: true }, { t: "Amortização", n: true },
              { t: "Saldo final", n: true }],
        a.anos.slice(0, 12).map(function (x) {
          return h("tr", {}, [
            h("td", { class: "n", texto: String(x.ano) }),
            h("td", { class: "n", texto: reais(x.saldo_inicial) }),
            h("td", { class: "n", texto: reais(x.juros) }),
            h("td", { class: "n" + ((x.amortizacao || 0) < 0 ? " ruim" : ""),
                      texto: reais(x.amortizacao) }),
            h("td", { class: "n", texto: reais(x.saldo_final) })
          ]);
        }), true)));
    return nos;
  }

  /* Projetado contra executado. Sem verde e vermelho: a lista mistura receitas
   * e despesas, e executar menos que o projetado é ruim numa e bom na outra. */
  function cartaoProjetadoExecutado(e) {
    var pe = e.projetado_executado || {};
    var blocos = (pe.blocos || []).filter(function (b) {
      return (b.itens || []).length;
    });
    if (!pe.disponivel || !blocos.length) return [];
    var nos = [];
    if (pe.conferencia_falhou) {
      nos.push(h("div", { class: "aviso-linha" }, [
        h("span", { class: "ico", texto: "\u26a0" }),
        h("span", { texto:
          pe.conferencia_falhou + " item(ns) em que a diferença publicada não " +
          "é o projetado menos o executado. O painel mostra o que a fonte diz, " +
          "sem recalcular." })
      ]));
    }
    var nomear = blocos.length > 1;
    if (nomear) {
      nos.push(h("p", { class: "nota", texto:
        "Uma tabela por fundo e por massa: o mesmo item de fluxo é declarado " +
        "uma vez em cada, com valores de avaliações diferentes." }));
    }
    blocos.forEach(function (b) {
      nos.push(cartao(
        "Projetado contra executado" + (nomear ? " · " + b.rotulo : ""),
        "DRAA_COMPARATIVO_RECEITA",
        "Avaliação de " + (pe.exercicio || "—") +
        " · maiores diferenças em valor · a diferença é o projetado menos o executado",
        tabela([{ t: "Item de fluxo" }, { t: "Projetado", n: true },
                { t: "Executado", n: true }, { t: "Diferença", n: true },
                { t: "Desvio", n: true }],
          b.itens.map(function (i) {
            return h("tr", {}, [
              h("td", { texto: i.fluxo || "—" }),
              h("td", { class: "n", texto: reais(i.projetado) }),
              h("td", { class: "n", texto: reais(i.executado) }),
              h("td", { class: "n", texto: reais(i.diferenca) }),
              h("td", { class: "n", texto: i.desvio === null ||
                        i.desvio === undefined ? "—" : pct(i.desvio, 1) })
            ]);
          }), true)));
    });
    return nos;
  }

  /* A decomposição por fundo, que o CADPREV não entrega e a contabilidade do
   * ente sim. E o confronto entre as duas apurações do mesmo patrimônio —
   * mostrado, não resolvido: quando duas fontes públicas discordam, publicar um
   * número só esconde o achado mais interessante do cruzamento. */
  var COR_DO_FUNDO = {
    capitalizado: "var(--s1)", reparticao: "var(--s2)",
    administracao: "var(--s3)"
  };

  /* Uma divergência isolada não diz nada sem a distribuição ao lado: 4% parece
   * muito até se saber quantos RPPS ficam abaixo de cinco. */
  function reguaNacionalDaDivergencia() {
    var dv = (estado.cache["qualidade.json"] || {}).divergencia_entre_fontes;
    if (!dv || !dv.disponivel) return "";
    return " Para referência, a divergência típica no país é de " +
      pct(dv.mediana, 2) + ", e " + pct(dv.perc_ate_5, 0) + " dos RPPS " +
      "confrontáveis ficam dentro de 5%.";
  }

  function cartoesContabeis(e) {
    var c = e.contabil || {};
    if (!c.disponivel || !(c.fundos || []).length) return [];

    /* Sem saldo declarado não há composição a desenhar. Um de cada seis entes
     * entrega o Anexo 04 com receitas e despesas e sem o saldo das aplicações,
     * e desenhar uma barra zerada afirmaria um patrimônio que a fonte não
     * declarou. As receitas e despesas continuam valendo. */
    var alvo = c.com_saldo ? grafico(118) : null;
    if (alvo) {
      depoisDeMontar(function () {
        Charts.desenhar(alvo, "barraUnica", {
          altura: 118, alturaBarra: 30, titulo: "Recursos por fundo",
          partes: c.fundos.filter(function (f) { return f.recursos !== null; })
            .map(function (f) {
              return { rotulo: f.rotulo, cor: COR_DO_FUNDO[f.chave] || "var(--s4)",
                       valor: f.recursos };
            }),
          descricao: "Recursos separados entre os três fundos do RPPS"
        });
      });
    }

    var nos = [
      h("h3", { class: "secao", texto: "Composição contábil por fundo" }),
      h("p", { class: "nota", texto:
        "Do RREO Anexo 04 do SICONFI — " + (c.demonstrativo || "RREO") + ", " +
        c.periodo + "º bimestre de " + c.exercicio + ". É a separação entre " +
        "capitalização, repartição e taxa de administração que o CADPREV não " +
        "expõe: a carteira dele vem ativo a ativo, sem o plano de cada ativo." }),
      c.com_saldo
        ? cartao("Recursos por fundo", "SICONFI · RREO-Anexo 04",
            "Investimentos e disponibilidades somados",
            [alvo, legenda(c.fundos.filter(function (f) {
              return f.recursos !== null;
            }).map(function (f) {
              return { cor: COR_DO_FUNDO[f.chave] || "var(--s4)", rotulo: f.rotulo };
            }))])
        : h("div", { class: "aviso-linha" }, [
            h("span", { class: "ico", texto: "\u26a0" }),
            h("span", { texto:
              "Este ente entregou o Anexo 04 com receitas e despesas, mas sem o " +
              "saldo das aplicações. A composição por fundo não pode ser " +
              "mostrada — e tratar a ausência como zero afirmaria um patrimônio " +
              "que a fonte não declarou." })
          ]),
      cartao("Receitas, despesas e resultado de cada fundo",
        "SICONFI · RREO-Anexo 04",
        "Realizado até o " + c.periodo + "º bimestre",
        tabela([{ t: "Fundo" }, { t: "Recursos", n: true },
                { t: "Receitas", n: true }, { t: "Despesas", n: true },
                { t: "Resultado", n: true }],
          c.fundos.map(function (f) {
            var res = f.resultado;
            return h("tr", {}, [
              h("td", {}, [
                h("div", { texto: f.rotulo }),
                h("div", { class: "nota", texto: f.perc === null ||
                           f.perc === undefined ? "saldo não declarado"
                           : pct(f.perc, 1) + " dos recursos" })
              ]),
              h("td", { class: "n", texto: reais(f.recursos) }),
              h("td", { class: "n", texto: reais(f.receitas) }),
              h("td", { class: "n", texto: reais(f.despesas) }),
              h("td", { class: "n" + (res === null || res === undefined ? ""
                                      : (res < 0 ? " ruim" : " bom")),
                        texto: reais(res) })
            ]);
          }), true))
    ];

    if (!c.confronto && c.com_saldo && !c.saldo_completo) {
      nos.push(h("div", { class: "aviso-linha" }, [
        h("span", { class: "ico", texto: "\u26a0" }),
        h("span", { texto:
          "Um dos fundos movimenta receita sem declarar saldo, então a soma do " +
          "SICONFI está incompleta e não pode ser confrontada com a carteira do " +
          "CADPREV. Comparar um fragmento com o total produziria uma " +
          "divergência que não existe." })
      ]));
    }

    if (c.confronto) {
      var d = c.confronto;
      var grande = Math.abs(d.perc) > 5;
      nos.push(cartao("As duas fontes, lado a lado", "DAIR_CARTEIRA · SICONFI",
        "Mesmo patrimônio, duas apurações independentes",
        [
          h("div", { class: "kpis" }, [
            kpi("CADPREV · declarado pelo RPPS", reais(d.cadprev),
              "carteira ativo a ativo"),
            kpi("SICONFI · contabilidade do ente", reais(d.siconfi),
              "investimentos e disponibilidades"),
            kpi("Diferença", pct(d.perc, 2), reais(d.diferenca),
              grande ? "ruim" : "bom")
          ]),
          h("p", { class: "nota", texto: (grande
            ? "Diferença acima de 5%. As duas apurações têm datas de posição e " +
              "critérios distintos, então alguma diferença é esperada — mas " +
              "desta ordem vale conferir na fonte. O painel mostra as duas e " +
              "não escolhe entre elas."
            : "As duas apurações convergem. O painel mostra ambas em vez de " +
              "escolher uma: a discordância entre fontes públicas é, ela " +
              "própria, informação.") + reguaNacionalDaDivergencia() })
        ]));
    }
    return nos;
  }

  // ------------------------------------------------ aba: conformidade

  var ROTULO_ESTADO = {
    irregular: "irregular", em_curso: "em curso", encerrado: "encerrado"
  };

  function seloEstado(estado) {
    return h("span", {
      class: "selo-estado " + estado,
      texto: ROTULO_ESTADO[estado] || estado
    });
  }

  function abaConformidade() {
    if (estado.cnpj) return conformidadeDoEnte();
    return nacional("conformidade.json").then(function (c) {
      if (!c.disponivel) {
        return [vazio("Conformidade indisponível",
          "Falta ingerir <code>DRAA_NOTIFICACAO</code>. Rode " +
          "<code>python -m cadprev ingest DRAA_NOTIFICACAO</code>.")];
      }
      /* Tabela, e não barra empilhada: os sete rótulos têm quarenta a cinquenta
       * caracteres, e num gráfico só caberiam truncados. Nome cortado não
       * comunica melhor que número inteiro. */
      var porItem = tabela(
        [{ t: "Item de análise" }, { t: "Irregular", n: true },
         { t: "Em curso", n: true }, { t: "Encerrado", n: true },
         { t: "Total", n: true }],
        c.por_item.map(function (i) {
          return h("tr", {}, [
            h("td", { texto: i.rotulo }),
            h("td", { class: "n" + (i.irregular ? " ruim" : ""),
                      texto: num(i.irregular, 0) }),
            h("td", { class: "n", texto: num(i.em_curso, 0) }),
            h("td", { class: "n", texto: num(i.encerrado, 0) }),
            h("td", { class: "n", texto: num(i.total, 0) })
          ]);
        }), true);

      return [
        h("h2", { class: "secao", texto: "Conformidade" }),
        h("p", { class: "intro", texto:
          "O que a Subsecretaria registrou sobre os demonstrativos — não o que " +
          "este painel achou. A classificação usa as palavras da própria fonte: " +
          "ela escreve \u201cSituacao irregular\u201d quando é o caso." }),
        h("div", { class: "aviso-linha" }, [
          h("span", { class: "ico", texto: "\u26a0" }),
          h("span", { texto:
            "Leia com o escopo em mente: " + c.escopo + " Não é um retrato da " +
            "conformidade geral dos RPPS." })
        ]),
        h("div", { class: "kpis" }, [
          kpi("RPPS notificados", num(c.entes_notificados, 0),
            "de " + num(c.com_encaminhamento, 0) + " que já enviaram DRAA"),
          kpi("Com item irregular", num(c.entes_com_irregular, 0),
            "situação declarada pela SPREV",
            c.entes_com_irregular ? "ruim" : "bom"),
          kpi("Itens de análise", num(c.itens, 0), "no histórico inteiro"),
          kpi("Entregaram o DRAA " + (c.ultimo_exercicio_entregue || "—"),
            num(c.entregaram_ultimo, 0),
            "de " + num(c.com_encaminhamento, 0) + " entes")
        ]),
        cartao("Itens de análise por situação", "DRAA_NOTIFICACAO",
          "Cada linha é um tema examinado pela SPREV", porItem),
        c.com_irregular.length
          ? cartao("RPPS com item irregular", "DRAA_NOTIFICACAO",
              "Clique na linha para abrir o ente",
              tabela([{ t: "RPPS" }, { t: "Itens", n: true }],
                c.com_irregular.map(function (e) {
                  return linhaClicavel(e.cnpj, [
                    h("td", {}, [e.ente, h("span", { class: "uf", texto: e.uf || "" })]),
                    h("td", { class: "n", texto: num(e.itens, 0) })
                  ]);
                })))
          : null
      ];
    });
  }

  function conformidadeDoEnte() {
    return carregarEnte().then(function (e) {
      var c = e.conformidade || {};
      var nos = [
        h("h2", { class: "secao", texto: "Conformidade" }),
        cabecalhoEnte(e),
        h("div", { class: "contexto" }, [
          h("span", { class: "pilula" }, ["Ente ", h("b", { texto: e.ente })]),
          h("button", {
            class: "link limpar", texto: "ver o agregado nacional",
            onclick: function () { irParaAba("conformidade", null); }
          })
        ])
      ];
      if (!c.disponivel) {
        nos.push(semDado("conformidade", "DRAA_NOTIFICACAO"));
        return nos;
      }
      nos.push(h("div", { class: "kpis" }, [
        kpi("Itens irregulares", num(c.irregular || 0, 0),
          "situação declarada pela SPREV", c.irregular ? "ruim" : "bom"),
        kpi("Em curso", num(c.em_curso || 0, 0), "respondidos ou aguardando"),
        kpi("Encerrados", num(c.encerrado || 0, 0), "sem pendência ou cancelados"),
        kpi("Envios de DRAA", num((c.entregas || []).length, 0),
          "histórico de encaminhamento")
      ]));

      nos.push(c.total
        ? cartao("Notificações da SPREV", "DRAA_NOTIFICACAO",
            "Ordenadas da mais recente para a mais antiga",
            tabela([{ t: "Item de análise" }, { t: "Situação" },
                    { t: "Notificada" }, { t: "Preclusão" }],
              c.itens.map(function (i) {
                return h("tr", {}, [
                  h("td", {}, [
                    h("div", { texto: i.item || "—" }),
                    h("div", { class: "nota", texto: i.numero || "" })
                  ]),
                  h("td", {}, [seloEstado(i.estado),
                    h("div", { class: "nota", texto: i.situacao || "" })]),
                  h("td", { texto: data(i.notificacao) }),
                  h("td", { texto: data(i.preclusao) })
                ]);
              }), true))
        : vazio("Sem notificações registradas",
            "A SPREV não registrou item de análise para este ente. " +
            "O conjunto cobre apenas segregação de massa."));

      if ((c.entregas || []).length) {
        nos.push(cartao("Histórico de envio do DRAA", "DRAA_ENCAMINHAMENTO",
          "Cada linha é uma submissão; a mais recente é a que vale",
          tabela([{ t: "Exercício" }, { t: "Envio" }, { t: "Situação" }],
            c.entregas.map(function (x) {
              return h("tr", {}, [
                h("td", { texto: String(x.exercicio || "—") }),
                h("td", { texto: data(x.envio) }),
                h("td", { texto: x.situacao || "—" })
              ]);
            }))));
      }
      return nos;
    });
  }

  // -------------------------------------------------- aba: qualidade

  function abaQualidade() {
    return Promise.all([buscar("qualidade.json"), buscar("filtros.json")])
      .then(function (r) {
        var q = r[0], f = r[1];
        var nos = [
          h("h2", { texto: "Qualidade do cadastro" }),
          h("p", { class: "intro", html:
            "O que está nesta página não é opinião sobre gestão: é o que a " +
            "própria base do CADPREV contradiz. Está aqui para que quem pode " +
            "corrigir na fonte encontre o caso com a evidência ao lado — e " +
            "para que ninguém leia um número sem saber o que ele carrega." })
        ];

        nos.push(h("h3", { texto: "Lançamentos impossíveis" }));
        nos.push(h("p", { class: "nota", html:
          "Uma posição não pode ser maior que o fundo em que está aplicada. " +
          "Quando a linha excede em mais de dez vezes a maior declaração já " +
          "feita para aquele fundo, ela sai de <b>todas</b> as somas do " +
          "painel — inclusive com as chaves desligadas. O valor não é " +
          "corrigido: dividir por um milhão daria o número certo e seria " +
          "inventá-lo." }));

        if (!q.achados.length) {
          nos.push(vazio("Nenhum lançamento impossível",
            "Nesta carga, nenhuma posição excede o fundo em que está aplicada."));
        }
        q.achados.forEach(function (a) {
          nos.push(h("div", { class: "achado" }, [
            h("h4", {}, [
              document.createTextNode((a.ente || a.cnpj) + " · " + (a.uf || "—")),
              h("span", { class: "marca-ente grave", texto: "excluído da soma" })
            ]),
            h("p", { class: "onde", texto: a.fundo || "fundo não identificado" }),
            h("dl", {}, [
              h("dt", { texto: "Posição declarada" }),
              h("dd", { class: "forte", texto: reaisExatos(a.posicao) }),
              h("dt", { texto: "Maior patrimônio já declarado para o fundo" }),
              h("dd", { texto: reaisExatos(a.maior_pl_declarado) }),
              h("dt", { texto: "Quantas vezes o fundo inteiro" }),
              h("dd", { class: "forte", texto: num(a.vezes, 1) + "×" }),
              h("dt", { texto: "Valor da cota, como declarado" }),
              h("dd", { class: "forte", texto: reaisExatos(a.valor_unitario) }),
              h("dt", { texto: "Quantidade de cotas" }),
              h("dd", { texto: num(a.quantidade_cotas, 4) })
            ])
          ]));
        });

        var dv = q.divergencia_entre_fontes || {};
        if (dv.disponivel) {
          nos.push(h("h3", { texto: "As duas fontes sobre o mesmo patrimônio" }));
          nos.push(h("p", { class: "nota", html:
            "O CADPREV traz a carteira declarada pelo RPPS; o SICONFI, a " +
            "contabilidade do ente. São apurações independentes, e a distância " +
            "entre elas é informação sobre o cadastro. Nenhuma das duas é " +
            "corrigida pela outra." }));
          nos.push(h("div", { class: "kpis" }, [
            kpi("Divergência típica", pct(dv.mediana, 2),
              "mediana entre os " + num(dv.confrontados, 0) + " confrontáveis"),
            kpi("Dentro de 5%", num(dv.ate_5, 0),
              pct(dv.perc_ate_5, 0) + " dos confrontáveis",
              dv.perc_ate_5 >= 50 ? "bom" : ""),
            kpi("Acima de 5%", num(dv.acima_5, 0), "vale conferir na fonte",
              dv.acima_5 ? "ruim" : "bom"),
            kpi("Sem confronto possível", num(dv.sem_saldo + dv.saldo_parcial, 0),
              "de " + num(dv.com_anexo, 0) + " com Anexo 04")
          ]));
          nos.push(tabela([{ t: "Situação" }, { t: "Entes", n: true }], [
            ["Entregaram o Anexo 04 sem o saldo das aplicações", dv.sem_saldo],
            ["Declararam saldo de um fundo e omitiram o de outro", dv.saldo_parcial],
            ["Confrontáveis com a carteira do CADPREV", dv.confrontados]
          ].map(function (l) {
            return h("tr", {}, [
              h("td", { texto: l[0] }),
              h("td", { class: "n", texto: num(l[1], 0) })
            ]);
          }), true));
          nos.push(h("p", { class: "nota", texto:
            "Ausência de saldo não é saldo zero, e soma parcial não é soma. Os " +
            "dois casos saem do confronto em vez de virar divergência: tratá-los " +
            "como zero acusaria um em cada seis RPPS de uma diferença que a " +
            "fonte nunca declarou." }));
        }

        nos.push(h("h3", { texto: "Atualidade do dado" }));
        nos.push(h("p", { class: "nota", html:
          "Estes não são erros: são juízos sobre o quanto o dado ainda " +
          "descreve a situação de hoje. Por isso viram chave no topo da " +
          "página, ligada por quem lê, e não exclusão automática." }));

        var linhas = f.filtros.map(function (x) {
          return { rotulo: x.situacao || x.rotulo, valor: f.atingidos[x.chave] };
        });
        nos.push(tabela([{ t: "Situação" }, { t: "Entes", n: true }],
          linhas.map(function (l) {
            return h("tr", {}, [
              h("td", { texto: l.rotulo }),
              h("td", { class: "n", texto: num(l.valor, 0) })
            ]);
          })));

        // Procedência por endpoint. A gravação é transacional: um endpoint que
        // falha na atualização mantém o que já estava lá, o que é melhor que
        // perder o dado — mas deixa a tela misturando safras. Sem esta tabela a
        // mistura seria invisível.
        var exec = (estado.meta && estado.meta.execucoes) || [];
        if (exec.length) {
          var recente = exec.reduce(function (a, e) {
            return e.quando && e.quando > a ? e.quando : a;
          }, "");
          var atrasados = 0;
          var linhasExec = exec.slice().sort(function (a, b) {
            return (a.endpoint || "").localeCompare(b.endpoint || "");
          }).map(function (e) {
            var dias = diasEntre(e.quando, recente);
            if (dias >= 1) atrasados += 1;
            return h("tr", {}, [
              h("td", {}, [h("code", { texto: e.endpoint })]),
              h("td", { class: "n", texto: num(e.linhas, 0) }),
              h("td", { texto: data(e.quando) }),
              h("td", { class: dias >= 1 ? "n ruim" : "n",
                        texto: dias >= 1 ? "−" + num(dias, 0) + " d" : "em dia" })
            ]);
          });
          nos.push(h("h3", { texto: "Procedência de cada endpoint" }));
          nos.push(h("p", { class: "nota", texto:
            atrasados
              ? "A gravação é transacional: um endpoint que falha na atualização " +
                "mantém o que já estava no banco, em vez de ficar pela metade. " +
                "O preço é que a tela pode misturar safras — " + atrasados +
                (atrasados > 1 ? " endpoints estão" : " endpoint está") +
                " mais antigo que o resto desta carga."
              : "Todos os endpoints vieram da mesma carga. Quando um falha, o " +
                "anterior é preservado e passa a aparecer aqui com a diferença " +
                "de dias, para que a mistura de safras não fique invisível." }));
          nos.push(tabela([{ t: "Endpoint" }, { t: "Linhas", n: true },
                           { t: "Ingerido em" }, { t: "Defasagem", n: true }],
                          linhasExec, true));
        }

        /* O carimbo da fonte. Em 17/09/2026 ele marcava 15/08 e não se movia
         * havia um mês — cada carga semanal rebaixava um milhão de linhas
         * idênticas. Está aqui para medir isso com histórico em vez de
         * suposição; o corte da varredura só vem depois da evidência. */
        var m = estado.meta || {};
        if (m.fonte_atualizada_em) {
          var mudancas = m.mudancas_da_fonte || [];
          nos.push(h("h3", { texto: "Atualização da fonte" }));
          nos.push(h("p", { class: "nota", texto:
            "A API publica um carimbo de quando os dados dela mudaram pela " +
            "última vez. O painel registra esse carimbo a cada carga: é o que " +
            "vai permitir decidir, com histórico, se a varredura completa " +
            "semanal se justifica." }));
          nos.push(h("div", { class: "kpis" }, [
            kpi("Fonte atualizada em", data(m.fonte_atualizada_em),
              "carimbo publicado pela API"),
            kpi("Cargas desde então",
              m.gerado_em ? num(diasEntre(m.fonte_atualizada_em, m.gerado_em), 0) +
                " dias" : "—",
              "entre o carimbo e esta construção"),
            kpi("Mudanças registradas", num(mudancas.length, 0),
              "desde que a medição começou")
          ]));
          if (mudancas.length > 1) {
            nos.push(tabela([{ t: "Fonte mudou para" }, { t: "Detectado em" }],
              mudancas.map(function (x) {
                return h("tr", {}, [
                  h("td", { texto: data(x.valor) }),
                  h("td", { texto: data(x.quando) })
                ]);
              })));
          }
        }

        nos.push(h("p", { class: "nota", texto:
          "Situação apurada em " + data(q.referencia) + "." }));
        return nos;
      });
  }

  /* ---------------------------------------------- militares
   *
   * Uma aba só porque a massa militar não cabe nas outras: só os Estados a têm,
   * a avaliação atuarial é própria, o fundo é próprio e o militar não se
   * aposenta — vai para a reserva e depois para a reforma. Comparar um Estado
   * com um município aqui não seria uma comparação difícil: seria uma
   * comparação sem termo, porque município não tem militar.
   */
  function abaMilitares() {
    return nacional("militar.json").then(function (m) {
      if (!m.disponivel) {
        return [vazio("Militares indisponível",
          "Falta ingerir <code>DRAA_ESTATISTICA</code>. Rode " +
          "<code>python -m cadprev ingest DRAA_ESTATISTICA</code>.")];
      }
      var comPessoas = (m.entes || []).filter(function (e) { return e.pessoas; });
      var r = m.resumo_razao;

      /* Ordenado pela razão, não pelo tamanho: o assunto é a relação entre
       * quem contribui e quem recebe, e ela não acompanha a população —
       * Roraima, com 3 mil militares, está no extremo. As duas massas do mesmo
       * ente lado a lado porque é isso que a separação revela: em quase todos
       * os Estados a razão militar e a civil não se parecem. */
      var ordenados = comPessoas.filter(function (e) {
        return e.razao_ativos_inativos !== null &&
               e.razao_ativos_inativos !== undefined;
      }).slice().sort(function (a, b) {
        return b.razao_ativos_inativos - a.razao_ativos_inativos;
      });
      var altura = Math.max(200, ordenados.length * 21);
      var alvo = grafico(altura);
      depoisDeMontar(function () {
        Charts.desenhar(alvo, "barrasPareadas", {
          altura: altura, unidade: "", dec: 2,
          nomeRpps: "Militar", nomeReferencia: "Civil",
          linhas: ordenados.map(function (e) {
            return { rotulo: (e.uf || "?") + " · " +
                       (e.ente || "").replace(/^Governo d[aeo] (Estado d[aeo] )?/, ""),
                     valor: e.razao_ativos_inativos,
                     referencia: e.razao_civil };
          }),
          descricao: "Ativos por beneficiário, na massa militar e na civil de " +
            "cada Estado"
        });
      });

      var linhas = comPessoas.map(function (e) {
        return linhaClicavel(e.cnpj, [
          h("td", { class: "nome-ente" },
            [e.ente, h("span", { class: "uf", texto: e.uf || "" })]),
          h("td", { class: "n", texto: num(e.ativos, 0) }),
          h("td", { class: "n", texto: num(e.inativos, 0) }),
          h("td", { class: "n", texto: num(e.pensionistas, 0) }),
          h("td", { class: "n", texto: e.razao_ativos_inativos === null ||
                    e.razao_ativos_inativos === undefined
                      ? "—" : num(e.razao_ativos_inativos, 2) }),
          h("td", { class: "n", texto: e.razao_civil === null ||
                    e.razao_civil === undefined
                      ? "—" : num(e.razao_civil, 2) }),
          h("td", { class: "n", texto: e.participacao === null ||
                    e.participacao === undefined
                      ? "—" : pct(e.participacao, 1) })
        ]);
      });

      /* Execução orçamentária ao lado de avaliação atuarial: são perguntas
       * diferentes sobre a mesma massa, de fontes diferentes, com referências
       * temporais diferentes — e por isso cada uma leva a sua data na coluna,
       * em vez de se dissolverem num total só. */
      var comOrcamento = comPessoas.filter(function (e) {
        return e.contribuicoes !== null && e.contribuicoes !== undefined;
      });
      var orcamento = comOrcamento.length ? cartao(
        "Contribuições e despesas dos militares", "SICONFI · RREO Anexo 04",
        "Execução orçamentária do exercício, acumulada até o bimestre " +
        "declarado — outra fonte e outra referência temporal que a avaliação " +
        "atuarial acima",
        tabela([{ t: "Estado" }, { t: "Bim.", n: true },
                { t: "Contribuições", n: true }, { t: "Despesas", n: true },
                { t: "Resultado", n: true }],
          comOrcamento.slice().sort(function (a, b) {
            return (b.despesas || 0) - (a.despesas || 0);
          }).map(function (e) {
            return linhaClicavel(e.cnpj, [
              h("td", { class: "nome-ente" },
                [e.ente, h("span", { class: "uf", texto: e.uf || "" })]),
              h("td", { class: "n", texto: e.periodo_rreo || "—" }),
              h("td", { class: "n", texto: reais(e.contribuicoes) }),
              h("td", { class: "n", texto: reais(e.despesas) }),
              h("td", { class: "n" + ((e.resultado || 0) < 0 ? " ruim" : ""),
                        texto: reais(e.resultado) })
            ]);
          }), true)) : null;

      var nos = [
        h("h2", { class: "secao", texto: "Militares" }),
        h("p", { class: "intro", texto:
          "Militar não se aposenta: passa à reserva e depois à reforma. A " +
          "avaliação atuarial é própria e a massa é própria. " + m.escopo }),
        h("div", { class: "kpis" }, [
          kpi("Estados com massa militar", num(m.estados_com_pessoas, 0),
            m.estados_sem_massa.length
              ? "sem DRAA: " + m.estados_sem_massa.join(", ")
              : "todos os Estados declaram"),
          kpi("Militares na ativa", num(m.ativos, 0), "declarados no DRAA"),
          kpi("Na reserva, reformados e pensionistas",
            num(m.inativos + m.pensionistas, 0),
            num(m.inativos, 0) + " na reserva ou reforma e " +
            num(m.pensionistas, 0) + " pensionistas"),
          kpi("Ativos por beneficiário",
            m.razao_ativos_inativos === null ? "—"
              : num(m.razao_ativos_inativos, 2),
            r ? "mediana por Estado de " + num(r.mediana, 2) +
                " · de " + num(r.min, 2) + " a " + num(r.max, 2)
              : "sem grupo para mediana",
            (m.razao_ativos_inativos || 0) >= 1 ? "bom" : "ruim")
        ]),
        cartao("Ativos por beneficiário, Estado a Estado", "DRAA_ESTATISTICA",
          "Militares na ativa para cada militar na reserva, reformado ou " +
          "pensionista — e, ao lado, a mesma razão na massa civil do mesmo ente",
          [alvo, legenda([
            { cor: "var(--s2)", rotulo: "Militar" },
            { cor: "var(--s1)", rotulo: "Civil" }
          ])]),
        cartao("Massa militar de cada Estado", "DRAA_ESTATISTICA",
          "Clique na linha para abrir o ente · a razão civil ao lado mostra " +
          "que as duas massas não se comportam igual no mesmo ente",
          tabela([{ t: "Estado" }, { t: "Ativos", n: true },
                  { t: "Reserva e reforma", n: true },
                  { t: "Pensionistas", n: true },
                  { t: "Razão militar", n: true },
                  { t: "Razão civil", n: true },
                  { t: "% da massa", n: true }], linhas, true))
      ];
      if (orcamento) nos.push(orcamento);
      if (m.sem_rreo && m.sem_rreo.length) {
        nos.push(h("p", { class: "nota", texto:
          "Sem o bloco militar no Anexo 04 do RREO coletado: " +
          m.sem_rreo.join(", ") + ". Ausência de linha não é ausência de " +
          "despesa — é ausência de declaração nessa fonte." }));
      }
      nos.push(h("p", { class: "nota", texto: m.nota_carteira }));
      nos.push(h("p", { class: "nota", texto: m.nota_nomenclatura }));
      return nos;
    });
  }

  var ABAS = {
    panorama: abaPanorama, ficha: abaFicha, caixa: abaCaixa,
    carteira: abaCarteiraEnte, atuaria: abaAtuaria,
    comparativo: abaComparativo, conformidade: abaConformidade,
    militares: abaMilitares, qualidade: abaQualidade,
    ajuda: abaAjuda
  };

  // ------------------------------------------------- chaves do universo

  /* As chaves só valem para as telas que somam o país. Na ficha de um RPPS não
   * há universo a recortar: deixá-las visíveis e inertes convidaria a clicar e
   * a não entender por que nada mudou. */
  function abaEhNacional() {
    if (estado.aba === "panorama") return true;
    if (estado.aba === "carteira" && !estado.cnpj) return true;
    if (estado.aba === "conformidade" && !estado.cnpj) return true;
    if (estado.aba === "militares") return true;
    return estado.aba === "comparativo" && !!estado.cnpj;
  }

  function montarChaves() {
    var caixa = document.getElementById("chaves");
    if (!caixa || !estado.chaves) return;
    caixa.textContent = "";
    estado.chaves.filtros.forEach(function (f, i) {
      var atingidos = estado.chaves.atingidos[f.chave];
      var entrada = h("input", { type: "checkbox" });
      entrada.checked = estado.filtros.charAt(i) === "1";
      entrada.disabled = f.disponivel === false;
      entrada.addEventListener("change", function () {
        var bits = estado.filtros.split("");
        bits[i] = entrada.checked ? "1" : "0";
        estado.filtros = bits.join("");
        guardarFiltros();
        atualizarEfeito();
        render();
      });
      /* Sem a fonte no banco, "−0" afirmaria que ninguém está atrasado quando o
       * que houve foi não ter como saber. A chave fica inerte e diz o porquê. */
      var sem = f.disponivel === false;
      caixa.appendChild(h("label", {
        class: "chave" + (sem ? " inerte" : ""),
        title: sem ? "Depende de " + f.fonte + ", que não está no banco local."
                   : f.nota
      }, [
        entrada,
        document.createTextNode(f.rotulo),
        h("span", { class: "quantos",
                    texto: sem ? "sem dado" : "−" + num(atingidos || 0, 0) })
      ]));
    });
  }

  function atualizarEfeito() {
    var alvo = document.getElementById("efeito-filtros");
    if (!alvo || !estado.chaves) return;
    var ligadas = estado.chaves.filtros.filter(function (f, i) {
      return estado.filtros.charAt(i) === "1";
    });
    var texto = ligadas.length
      ? "Fora das estatísticas: " + ligadas.map(function (f) {
          return f.situacao || f.rotulo;
        }).join("; ") + "."
      : "Nenhum recorte: todos os entes da base entram nas estatísticas.";
    alvo.textContent = "";
    alvo.appendChild(h("span", { html:
      texto + " Os lançamentos que a própria base contradiz saem sempre — " +
      "<a href=\"#/qualidade\">ver quais</a>." }));
  }

  function atualizarBarraFiltros() {
    var barra = document.getElementById("filtros");
    if (barra) barra.hidden = !(estado.chaves && abaEhNacional());
  }

  var GUARDA = "cadprev:filtros";

  function guardarFiltros() {
    try { localStorage.setItem(GUARDA, estado.filtros); } catch (e) { /* modo privado */ }
    var base = (location.hash || "").split("?")[0] || "#/panorama";
    var alvo = base + (estado.filtros === estado.chaves.padrao
      ? "" : "?f=" + estado.filtros);
    if (alvo !== location.hash) {
      history.replaceState(null, "", alvo);
    }
  }

  function filtrosIniciais(chaves) {
    var daUrl = (location.hash || "").split("?")[1];
    var m = daUrl && daUrl.match(/f=([01]+)/);
    var guardado = null;
    try { guardado = localStorage.getItem(GUARDA); } catch (e) { /* modo privado */ }
    var candidato = (m && m[1]) || guardado || chaves.padrao;
    if (candidato.length !== chaves.padrao.length || !/^[01]+$/.test(candidato)) {
      candidato = chaves.padrao;
    }
    return candidato.split("").map(function (bit, i) {
      return chaves.filtros[i] && chaves.filtros[i].disponivel === false ? "0" : bit;
    }).join("");
  }

  var pendentes = [];
  function depoisDeMontar(fn) { pendentes.push(fn); return null; }

  function render() {
    var fn = ABAS[estado.aba] || abaPanorama;
    pendentes = [];
    conteudo.textContent = "";
    conteudo.appendChild(h("p", { class: "carregando", texto: "Carregando…" }));

    fn().then(function (nos) {
      conteudo.textContent = "";
      (nos || []).forEach(function (n) { if (n) conteudo.appendChild(n); });
      pendentes.forEach(function (f) { f(); });
      pendentes = [];
      Charts.esconderDica();
    }).catch(function (erro) {
      conteudo.textContent = "";
      conteudo.appendChild(vazio("Não consegui carregar os dados",
        "Falhou ao ler <code>" + String(erro.message || erro) + "</code>. " +
        "Se o painel nunca foi construído, rode <code>python -m cadprev demo</code> " +
        "e recarregue a página."));
    });

    atualizarBarraFiltros();
    document.querySelectorAll("nav.abas a").forEach(function (a) {
      if (a.dataset.aba === estado.aba) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    document.title = "Painel CADPREV — " + estado.aba;
  }

  function lerRota() {
    var bruto = (location.hash || "#/panorama").split("?")[0];
    var partes = bruto.replace(/^#\/?/, "").split("/");
    if (partes[0] === "ente" && partes[1]) {
      estado.cnpj = partes[1];
      estado.aba = partes[2] || "ficha";
    } else {
      estado.aba = partes[0] || "panorama";
      if (partes[1] === "todos") estado.cnpj = null;
    }
    if (!ABAS[estado.aba]) estado.aba = "panorama";
  }

  /* As chaves viajam na URL para que um link compartilhado mostre ao
   * destinatário exatamente o recorte de quem mandou. */
  function comChaves(hash) {
    return estado.chaves && estado.filtros !== estado.chaves.padrao
      ? hash + "?f=" + estado.filtros : hash;
  }

  function irParaEnte(cnpj) {
    var aba = ["ficha", "caixa", "carteira", "atuaria", "comparativo"].indexOf(estado.aba) >= 0
      ? estado.aba : "ficha";
    location.hash = comChaves("#/ente/" + cnpj + "/" + aba);
  }

  function irParaAba(aba, cnpj) {
    location.hash = comChaves(
      cnpj === null && ["ficha", "caixa", "carteira", "atuaria", "comparativo"].indexOf(aba) >= 0
        ? "#/" + aba + "/todos"
        : (estado.cnpj ? "#/ente/" + estado.cnpj + "/" + aba : "#/" + aba));
  }

  document.querySelectorAll("nav.abas a").forEach(function (a) {
    a.addEventListener("click", function (ev) {
      ev.preventDefault();
      irParaAba(a.dataset.aba, estado.cnpj);
    });
  });

  window.addEventListener("hashchange", function () { lerRota(); render(); });

  // ------------------------------------------------------------- busca

  function montarBusca() {
    var campo = document.getElementById("busca");
    var caixa = document.getElementById("sugestoes");
    var seletorUf = document.getElementById("busca-uf");

    function fechar() { caixa.hidden = true; caixa.textContent = ""; }

    /* Com UF escolhida a lista aparece sem digitar nada: o caso de uso é
     * "quero ver quem tem no meu estado", e exigir que se digite alguma coisa
     * para isso seria pedir que a pessoa já saiba a resposta. */
    function sugerir() {
      var uf = seletorUf.value || null;
      var r = filtrarEntes(campo.value, uf, 30);
      caixa.textContent = "";

      if (!campo.value.trim() && !uf) return fechar();

      if (!r.itens.length) {
        caixa.appendChild(h("div", { class: "vazio", texto:
          uf ? "Nenhum RPPS com esse nome em " + uf + "."
             : "Nenhum RPPS com esse nome no banco local." }));
      } else {
        if (r.total > r.itens.length) {
          caixa.appendChild(h("div", { class: "cabeca", texto:
            "mostrando " + r.itens.length + " de " + num(r.total, 0) +
            " — refine o nome" }));
        }
        r.itens.forEach(function (e) {
          var b = h("button", { type: "button" }, [
            e.ente || e.cnpj, h("span", { class: "uf", texto: e.uf || "" })
          ]);
          b.addEventListener("click", function () {
            campo.value = "";
            fechar();
            irParaEnte(e.cnpj);
          });
          caixa.appendChild(b);
        });
      }
      caixa.hidden = false;
    }

    campo.addEventListener("input", sugerir);
    campo.addEventListener("focus", sugerir);
    seletorUf.addEventListener("change", function () {
      sugerir();
      campo.focus();
    });

    campo.addEventListener("keydown", function (ev) { if (ev.key === "Escape") fechar(); });
    document.addEventListener("click", function (ev) {
      if (!caixa.contains(ev.target) && ev.target !== campo &&
          ev.target !== seletorUf) fechar();
    });
  }

  /* O índice de entes chega depois do primeiro desenho, então as UF só podem
   * ser listadas quando ele chega — antes disso o seletor ficaria vazio. */
  function preencherUfs() {
    var seletorUf = document.getElementById("busca-uf");
    if (!seletorUf || seletorUf.options.length > 1) return;
    ufsConhecidas().forEach(function (uf) {
      seletorUf.appendChild(h("option", { value: uf, texto: uf }));
    });
  }

  function montarTema() {
    var btn = document.getElementById("btn-tema");
    var guardado = null;
    try { guardado = localStorage.getItem("cadprev-tema"); } catch (e) { /* sem storage */ }
    if (guardado) document.documentElement.setAttribute("data-tema", guardado);

    /* O rótulo anuncia o destino, não o estado atual: um botão escrito "Tema"
     * não diz o que o clique faz, e um escrito "Escuro" no escuro é ambíguo
     * entre "você está aqui" e "vá para lá". */
    function escuroAgora() {
      var atual = document.documentElement.getAttribute("data-tema");
      return atual ? atual === "escuro"
                   : window.matchMedia("(prefers-color-scheme: dark)").matches;
    }

    function rotular() {
      var vai = escuroAgora() ? "claro" : "escuro";
      btn.textContent = "";
      btn.appendChild(h("span", { class: "ico", "aria-hidden": "true",
                                  texto: vai === "escuro" ? "\u263e" : "\u2600" }));
      btn.appendChild(document.createTextNode(
        "Tema " + (vai === "escuro" ? "escuro" : "claro")));
      btn.setAttribute("aria-label",
        "Mudar para o tema " + vai + ". Tema atual: " +
        (escuroAgora() ? "escuro" : "claro") + ".");
      btn.setAttribute("title", btn.getAttribute("aria-label"));
    }

    rotular();
    if (window.matchMedia) {
      var consulta = window.matchMedia("(prefers-color-scheme: dark)");
      var aoMudar = function () {
        if (!document.documentElement.getAttribute("data-tema")) rotular();
      };
      if (consulta.addEventListener) consulta.addEventListener("change", aoMudar);
    }

    btn.addEventListener("click", function () {
      var novo = escuroAgora() ? "claro" : "escuro";
      document.documentElement.setAttribute("data-tema", novo);
      try { localStorage.setItem("cadprev-tema", novo); } catch (e) { /* sem storage */ }
      rotular();
    });
  }

  // ------------------------------------------------------------- início

  function iniciar() {
    montarTema();
    montarBusca();
    lerRota();

    Promise.all([
      buscar("meta.json").catch(function () { return null; }),
      buscar("entes.json").catch(function () { return []; }),
      buscar("filtros.json").catch(function () { return null; })
    ]).then(function (r) {
      estado.meta = r[0];
      estado.entes = r[1] || [];
      estado.chaves = r[2];
      indiceBusca = null;
      preencherUfs();
      if (estado.chaves) {
        estado.filtros = filtrosIniciais(estado.chaves);
        montarChaves();
        atualizarEfeito();
      }

      if (estado.meta && estado.meta.origem === "demonstracao") {
        document.getElementById("banner").hidden = false;
      }
      var origem = document.getElementById("rodape-origem");
      if (estado.meta) {
        var comRpps = estado.meta.com_rpps;
        origem.textContent = "Dados ingeridos em " + data(estado.meta.gerado_em) +
          " · " + num(estado.meta.entes, 0) + " entes federativos na base" +
          (comRpps ? ", " + num(comRpps, 0) + " com RPPS vigente" : "") +
          " · origem: " +
          (estado.meta.origem === "demonstracao" ? "conjunto de demonstração" : "API do CADPREV") + ".";
      } else {
        origem.textContent = "Nenhum conjunto de dados construído ainda.";
      }
      render();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
