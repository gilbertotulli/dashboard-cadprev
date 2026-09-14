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
  var estado = { meta: null, entes: [], cnpj: null, aba: "panorama", cache: {} };
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

  function tabela(colunas, linhas) {
    var thead = h("thead", {}, [h("tr", {}, colunas.map(function (c) {
      return h("th", { class: c.n ? "n" : "", texto: c.t });
    }))]);
    var tbody = h("tbody", {}, linhas);
    return h("div", { class: "rolar" }, [h("table", { class: "dados" }, [thead, tbody])]);
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
    return buscar("panorama.json").then(function (p) {
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
    return buscar("carteira-nacional.json").then(function (c) {
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
    var hoje = new Date().toISOString().slice(0, 10);
    var valido = crp.validade && crp.validade >= hoje;
    var selo = crp.numero_crp
      ? h("span", { class: "selo " + (valido ? "ok" : "crit") },
        [valido ? "✓ CRP válido até " + data(crp.validade)
          : "✕ CRP vencido em " + data(crp.validade)])
      : h("span", { class: "selo neutro", texto: "sem registro de CRP" });

    return h("div", { class: "ficha-topo" }, [
      h("div", {}, [
        h("div", { class: "nm", texto: e.ente || "—" }),
        h("div", {
          class: "id", texto: "CNPJ " + cnpjFormatado(e.cnpj) + " · " + (e.uf || "—") +
            " · " + rotuloEsfera(e.esfera) + " · " + (e.regiao || "—")
        })
      ]),
      selo
    ]);
  }

  function rotuloEsfera(chave) {
    return { estadual: "RPPS estadual", capital: "RPPS de capital", municipal: "RPPS municipal" }[chave] || "—";
  }

  function abaFicha() {
    if (!estado.cnpj) return Promise.resolve([semEnte("Ficha do RPPS")]);
    return carregarEnte().then(function (e) {
      var crp = e.crp || {};
      var est = e.estatistica || {};
      var seg = e.segregacao || {};
      var vigentes = (e.aliquotas || []).filter(function (a) { return !a.fim_vigencia; });
      var razao = (est.aposentados || est.pensionistas)
        ? (est.ativos || 0) / ((est.aposentados || 0) + (est.pensionistas || 0)) : null;

      return [
        h("h2", { class: "secao", texto: "Ficha do RPPS" }),
        cabecalhoEnte(e),
        h("div", { class: "campos", style: "margin-bottom:22px" }, [
          campo("Nº do CRP", crp.numero_crp || "—"),
          campo("Emissão", data(crp.emissao)),
          campo("Validade", data(crp.validade)),
          campo("Via judicial", crp.judicial === null || crp.judicial === undefined
            ? "—" : (crp.judicial ? "Sim" : "Não")),
          campo("Segregação da massa", seg.possui_segregacao === null ||
            seg.possui_segregacao === undefined ? "—"
            : (seg.possui_segregacao ? "Sim" + (seg.data_segregacao ?
              " — " + data(seg.data_segregacao) : "") : "Não")),
          campo("Exercício do DRAA", est.exercicio || "—")
        ]),
        h("div", { class: "grade duas" }, [
          cartao("Alíquotas vigentes", "RPPS_ALIQUOTA",
            vigentes.length ? "Sem data de término de vigência" : "Nenhuma alíquota vigente no banco",
            tabela([{ t: "Sujeito passivo" }, { t: "Plano" }, { t: "Alíquota", n: true }],
              vigentes.map(function (a) {
                return h("tr", {}, [
                  h("td", { texto: a.sujeito_passivo || "—" }),
                  h("td", { texto: a.plano || "—" }),
                  h("td", { class: "n", texto: pct(a.aliquota, 2) })
                ]);
              }))),
          cartao("Massa de participantes", "DRAA_ESTATISTICA",
            est.exercicio ? "Exercício " + est.exercicio : "Sem DRAA no banco",
            tabela([{ t: "Grupo" }, { t: "Pessoas", n: true }], [
              linhaSimples("Servidores ativos", num(est.ativos, 0)),
              linhaSimples("Aposentados", num(est.aposentados, 0)),
              linhaSimples("Pensionistas", num(est.pensionistas, 0)),
              linhaSimples("Dependentes", num(est.dependentes, 0)),
              linhaSimples("Razão ativos / inativos", razao === null ? "—" : num(razao, 2))
            ]))
        ])
      ];
    });
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
            serie.length + " competências", c.resultado >= 0 ? "bom" : "ruim"),
          kpi("Beneficiários na folha", num(c.beneficiarios, 0), "aposentados e pensionistas")
        ]),
        cartao("Ingressos e dispêndios, competência a competência", "DIPR · blocos 10–12",
          "Em milhões de reais, na mesma escala — a distância entre as linhas é o resultado",
          [alvo, legenda([
            { cor: "var(--s1)", rotulo: "Ingressos", linha: true },
            { cor: "var(--s2)", rotulo: "Dispêndios", linha: true }
          ])])
      ].concat(depoisDeMontar(function () {
        Charts.desenhar(alvo, "linhas", {
          rotulos: rotulos, cada: serie.length > 14 ? 3 : 1, dec: 1, altura: 260,
          delta: "resultado", unidade: "/" + (serie[0] && serie[0].ano || ""),
          series: [
            { nome: "Ingressos", cor: "var(--s1)", dados: serie.map(function (p) { return p.receita / escalaMi; }) },
            { nome: "Dispêndios", cor: "var(--s2)", dados: serie.map(function (p) { return p.despesa / escalaMi; }) }
          ],
          descricao: "Ingressos e dispêndios mensais"
        });
      }) || []);
    });
  }

  function abaCarteiraEnte() {
    if (!estado.cnpj) return abaCarteiraNacional();
    return carregarEnte().then(function (e) {
      var c = e.carteira || {};
      if (!c.disponivel) return [cabecalhoEnte(e), semDado("carteira", "DAIR_CARTEIRA")];

      var alocacao = c.segmentos.filter(function (s) { return s.alocacao; });
      var alvo = grafico(Math.max(150, alocacao.length * 42));

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
            })))
      ].concat(depoisDeMontar(function () {
        Charts.desenhar(alvo, "comLimite", {
          linhas: alocacao, altura: Math.max(150, alocacao.length * 42),
          descricao: "Alocação por segmento contra o limite da Resolução CMN 3.922/10"
        });
      }) || []);
    });
  }

  function abaAtuaria() {
    if (!estado.cnpj) return Promise.resolve([semEnte("Atuária")]);
    return carregarEnte().then(function (e) {
      var a = e.atuaria || {};
      if (!a.disponivel) return [cabecalhoEnte(e), semDado("atuária", "DRAA_*")];

      var fluxo = a.fluxo || [];
      var alvo = grafico(266);
      var escalaMi = 1e6;
      var cruzamentoIndice = null;
      fluxo.forEach(function (p, i) {
        if (cruzamentoIndice === null && p.ano_projecao === a.cruzamento) cruzamentoIndice = i;
      });

      var custeio = a.custeio || {};
      var deficit = (a.compromissos || []).reduce(function (soma, c) {
        return soma + (c.geracao_atual || 0);
      }, 0);

      return [
        h("h2", { class: "secao", texto: "Situação atuarial" }),
        cabecalhoEnte(e),
        h("div", { class: "kpis" }, [
          kpi("Resultado atuarial", reais(deficit),
            deficit > 0 ? "déficit — provisões a cobrir" : "superávit",
            deficit > 0 ? "ruim" : "bom"),
          kpi("Custo normal", pct(custeio.custo_normal, 2), "da folha de ativos"),
          kpi("Custo suplementar", pct(custeio.custo_suplementar, 2), "amortização do déficit"),
          kpi("Cruzamento das curvas", a.cruzamento || "—",
            a.cruzamento ? "despesas passam as receitas" : "não ocorre no horizonte projetado")
        ]),
        fluxo.length ? cartao("Fluxo atuarial projetado", "DRAA_FLUXO_ATUARIAL",
          "Em milhões de reais por ano — o cruzamento é lido da série, não vem pronto da API",
          [alvo, legenda([
            { cor: "var(--s1)", rotulo: "Receitas projetadas", linha: true },
            { cor: "var(--s2)", rotulo: "Despesas projetadas", linha: true }
          ])]) : null,
        h("div", { class: "grade duas" }, [
          cartao("Hipóteses da avaliação", "DRAA_HIPOTESE_ATUARIAL",
            "O que sustenta a projeção ao lado",
            h("div", { class: "campos" }, (a.hipoteses || []).map(function (hp) {
              return campo(hp.descricao || "—", hp.valor || "—");
            }))),
          cartao("Compromissos por geração", "DRAA_VALORES_COMPROMISSOS",
            "Valor presente",
            tabela([{ t: "Componente" }, { t: "Atual", n: true }, { t: "Futura", n: true }],
              (a.compromissos || []).map(function (c) {
                return h("tr", {}, [
                  h("td", { texto: c.descricao || "—" }),
                  h("td", { class: "n", texto: reais(c.geracao_atual) }),
                  h("td", { class: "n", texto: c.geracao_futura ? reais(c.geracao_futura) : "—" })
                ]);
              })))
        ])
      ].concat(fluxo.length ? (depoisDeMontar(function () {
        Charts.desenhar(alvo, "linhas", {
          rotulos: fluxo.map(function (p) { return String(p.ano_projecao); }),
          cada: Math.max(1, Math.round(fluxo.length / 5)), dec: 0, altura: 266,
          delta: "saldo",
          anotacao: cruzamentoIndice === null ? null
            : { em: cruzamentoIndice, texto: String(a.cruzamento) },
          series: [
            { nome: "Receitas", cor: "var(--s1)", dados: fluxo.map(function (p) { return (p.receitas || 0) / escalaMi; }) },
            { nome: "Despesas", cor: "var(--s2)", dados: fluxo.map(function (p) { return (p.despesas || 0) / escalaMi; }) }
          ],
          descricao: "Projeção anual de receitas e despesas"
        });
      }) || []) : []);
    });
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

  var ABAS = {
    panorama: abaPanorama, ficha: abaFicha, caixa: abaCaixa,
    carteira: abaCarteiraEnte, atuaria: abaAtuaria, ajuda: abaAjuda
  };

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

    document.querySelectorAll("nav.abas a").forEach(function (a) {
      if (a.dataset.aba === estado.aba) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    document.title = "Painel CADPREV — " + estado.aba;
  }

  function lerRota() {
    var partes = (location.hash || "#/panorama").replace(/^#\/?/, "").split("/");
    if (partes[0] === "ente" && partes[1]) {
      estado.cnpj = partes[1];
      estado.aba = partes[2] || "ficha";
    } else {
      estado.aba = partes[0] || "panorama";
      if (partes[1] === "todos") estado.cnpj = null;
    }
    if (!ABAS[estado.aba]) estado.aba = "panorama";
  }

  function irParaEnte(cnpj) {
    var aba = ["ficha", "caixa", "carteira", "atuaria"].indexOf(estado.aba) >= 0
      ? estado.aba : "ficha";
    location.hash = "#/ente/" + cnpj + "/" + aba;
  }

  function irParaAba(aba, cnpj) {
    location.hash = cnpj === null && ["ficha", "caixa", "carteira", "atuaria"].indexOf(aba) >= 0
      ? "#/" + aba + "/todos" : (estado.cnpj ? "#/ente/" + estado.cnpj + "/" + aba : "#/" + aba);
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

    function fechar() { caixa.hidden = true; caixa.textContent = ""; }

    campo.addEventListener("input", function () {
      var termo = campo.value.trim().toLowerCase();
      var somenteDigitos = termo.replace(/\D/g, "");
      if (termo.length < 2) return fechar();

      var achados = estado.entes.filter(function (e) {
        return (e.ente || "").toLowerCase().indexOf(termo) >= 0 ||
          (somenteDigitos.length >= 3 && (e.cnpj || "").indexOf(somenteDigitos) >= 0);
      }).slice(0, 12);

      caixa.textContent = "";
      if (!achados.length) {
        caixa.appendChild(h("div", { class: "vazio", texto: "Nenhum RPPS com esse nome no banco local." }));
      } else {
        achados.forEach(function (e) {
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
    });

    campo.addEventListener("keydown", function (ev) { if (ev.key === "Escape") fechar(); });
    document.addEventListener("click", function (ev) {
      if (!caixa.contains(ev.target) && ev.target !== campo) fechar();
    });
  }

  function montarTema() {
    var btn = document.getElementById("btn-tema");
    var guardado = null;
    try { guardado = localStorage.getItem("cadprev-tema"); } catch (e) { /* sem storage */ }
    if (guardado) document.documentElement.setAttribute("data-tema", guardado);

    btn.addEventListener("click", function () {
      var atual = document.documentElement.getAttribute("data-tema");
      var escuroAgora = atual
        ? atual === "escuro"
        : window.matchMedia("(prefers-color-scheme: dark)").matches;
      var novo = escuroAgora ? "claro" : "escuro";
      document.documentElement.setAttribute("data-tema", novo);
      try { localStorage.setItem("cadprev-tema", novo); } catch (e) { /* sem storage */ }
    });
  }

  // ------------------------------------------------------------- início

  function iniciar() {
    montarTema();
    montarBusca();
    lerRota();

    Promise.all([
      buscar("meta.json").catch(function () { return null; }),
      buscar("entes.json").catch(function () { return []; })
    ]).then(function (r) {
      estado.meta = r[0];
      estado.entes = r[1] || [];

      if (estado.meta && estado.meta.origem === "demonstracao") {
        document.getElementById("banner").hidden = false;
      }
      var origem = document.getElementById("rodape-origem");
      if (estado.meta) {
        origem.textContent = "Dados ingeridos em " + data(estado.meta.gerado_em) +
          " · " + num(estado.meta.entes, 0) + " RPPS no banco local · origem: " +
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
