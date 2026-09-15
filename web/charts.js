/* Gráficos do painel CADPREV.
 *
 * Sem biblioteca externa: SVG desenhado na medida real do contêiner, redesenhado
 * quando ele muda de tamanho. As cores saem de variáveis CSS (`var(--s1)` etc.),
 * então o tema claro/escuro troca sozinho, sem redesenho.
 *
 * Regras que valem para todos os gráficos daqui:
 *  - séries na mesma unidade dividem a mesma escala; não existe eixo duplo;
 *  - todo rótulo nomeia um valor que o gráfico alcança;
 *  - cor nunca é o único canal: sempre há legenda, rótulo direto ou tabela.
 */
(function (global) {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";
  var dica = null;

  function S(tag, attrs) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) if (attrs[k] !== null && attrs[k] !== undefined) e.setAttribute(k, attrs[k]);
    return e;
  }

  function txt(x, y, s, o) {
    o = o || {};
    var t = S("text", {
      x: x, y: y, fill: o.fill || "var(--muted)", "font-size": o.size || 11,
      "text-anchor": o.anchor || "start", "font-weight": o.weight || 400,
      "dominant-baseline": o.baseline || "auto"
    });
    if (o.tabular) t.setAttribute("style", "font-variant-numeric:tabular-nums");
    if (o.style) t.setAttribute("style", (t.getAttribute("style") || "") + ";" + o.style);
    t.textContent = s;
    return t;
  }

  function rrect(x, y, w, h, rl, rr) {
    w = Math.max(w, 0.5);
    rl = Math.min(rl, w / 2, h / 2); rr = Math.min(rr, w / 2, h / 2);
    return "M" + (x + rl) + "," + y +
      "H" + (x + w - rr) + (rr ? "a" + rr + "," + rr + " 0 0 1 " + rr + "," + rr : "") +
      "V" + (y + h - rr) + (rr ? "a" + rr + "," + rr + " 0 0 1 " + (-rr) + "," + rr : "") +
      "H" + (x + rl) + (rl ? "a" + rl + "," + rl + " 0 0 1 " + (-rl) + "," + (-rl) : "") +
      "V" + (y + rl) + (rl ? "a" + rl + "," + rl + " 0 0 1 " + rl + "," + (-rl) : "") + "Z";
  }

  function escala(max) {
    var passos = [1, 2, 2.5, 5, 10], mag = Math.pow(10, Math.floor(Math.log10(max / 4 || 1)));
    for (var i = 0; i < passos.length; i++) {
      var p = passos[i] * mag;
      if (Math.ceil(max / p) <= 5) return { passo: p, topo: Math.ceil(max / p) * p };
    }
    return { passo: mag * 10, topo: Math.ceil(max / (mag * 10)) * mag * 10 };
  }

  function num(v, d) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    return v.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  /* Reais em escala legível: um total nacional em unidades cheias não se lê. */
  function reais(v) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    var abs = Math.abs(v), sinal = v < 0 ? "\u2212" : "";
    if (abs >= 1e12) return sinal + "R$ " + num(abs / 1e12, 2) + " tri";
    if (abs >= 1e9) return sinal + "R$ " + num(abs / 1e9, 2) + " bi";
    if (abs >= 1e6) return sinal + "R$ " + num(abs / 1e6, 1) + " mi";
    if (abs >= 1e3) return sinal + "R$ " + num(abs / 1e3, 1) + " mil";
    return sinal + "R$ " + num(abs, 2);
  }

  function garantirDica() {
    if (dica) return dica;
    dica = document.createElement("div");
    dica.className = "tip";
    dica.setAttribute("role", "status");
    dica.setAttribute("aria-live", "polite");
    document.body.appendChild(dica);
    return dica;
  }

  function mostrar(html, ev) {
    var d = garantirDica();
    d.innerHTML = html;
    d.style.opacity = 1;
    var r = d.getBoundingClientRect();
    var x = ev.clientX + 14, y = ev.clientY - r.height - 12;
    if (x + r.width > window.innerWidth - 8) x = ev.clientX - r.width - 14;
    if (y < 8) y = ev.clientY + 18;
    d.style.left = x + "px";
    d.style.top = y + "px";
  }

  function esconder() { if (dica) dica.style.opacity = 0; }

  function linha(cor, rotulo, valor) {
    return '<span class="r"><i style="background:' + cor + '"></i>' + rotulo +
      '<b style="margin-left:auto;padding-left:12px">' + valor + "</b></span>";
  }

  function titulo(t) { return '<span class="tt">' + t + "</span>"; }

  function ligar(el, aoEntrar) {
    el.addEventListener("mousemove", aoEntrar);
    el.addEventListener("mouseleave", esconder);
  }

  // ---------------------------------------------------------------- formas

  /** Barras horizontais empilhadas, uma linha por categoria. */
  function empilhadas(svg, W, H, cfg) {
    var linhas = cfg.linhas, padL = cfg.padL || 96, padR = cfg.padR || 46;
    var alturaLinha = H / linhas.length, bh = Math.min(20, alturaLinha - 14);
    var plotW = W - padL - padR, maxTotal = 0;
    linhas.forEach(function (l) {
      maxTotal = Math.max(maxTotal, l.partes.reduce(function (a, p) { return a + p.valor; }, 0));
    });
    if (!maxTotal) maxTotal = 1;

    linhas.forEach(function (l, i) {
      var y = i * alturaLinha + (alturaLinha - bh) / 2, acc = 0;
      var total = l.partes.reduce(function (a, p) { return a + p.valor; }, 0);
      svg.appendChild(txt(0, y + bh / 2, l.rotulo,
        { fill: "var(--ink-2)", size: 11.5, baseline: "middle" }));
      l.partes.forEach(function (p, j) {
        var w = p.valor / maxTotal * plotW;
        if (w <= 0) { return; }
        var seg = S("path", {
          d: rrect(padL + acc, y, w - 2, bh, j === 0 ? 4 : 0,
            j === l.partes.length - 1 ? 4 : 0), fill: p.cor
        });
        ligar(seg, function (ev) {
          mostrar(titulo(l.rotulo) + linha(p.cor, p.rotulo, num(p.valor, 0)) +
            '<span class="r sub">' + num(total ? p.valor / total * 100 : 0, 1) +
            "% da linha</span>", ev);
        });
        svg.appendChild(seg);
        acc += w;
      });
      svg.appendChild(txt(W, y + bh / 2, num(total, 0), {
        fill: "var(--ink)", size: 11.5, anchor: "end", baseline: "middle",
        tabular: true, weight: 500
      }));
    });
  }

  /** Uma única barra empilhada: composição de um todo. */
  function barraUnica(svg, W, H, cfg) {
    var partes = cfg.partes.filter(function (p) { return p.valor > 0; });
    var total = partes.reduce(function (a, p) { return a + p.valor; }, 0) || 1;
    var bh = cfg.alturaBarra || 36, acc = 0;
    partes.forEach(function (p, i) {
      var w = p.valor / total * W;
      var seg = S("path", {
        d: rrect(acc, 0, w - 2, bh, i === 0 ? 4 : 0, i === partes.length - 1 ? 4 : 0),
        fill: p.cor
      });
      ligar(seg, function (ev) {
        mostrar(titulo(cfg.titulo || "") +
          linha(p.cor, p.rotulo, num(p.valor / total * 100, 1) + "% · " + reais(p.valor)), ev);
      });
      svg.appendChild(seg);

      var largoBastante = w >= 110, ultimo = i === partes.length - 1;
      if (largoBastante || ultimo) {
        var t = txt(largoBastante ? acc : W, bh + 19, "", {
          fill: "var(--ink)", size: 12.5, weight: 500,
          anchor: largoBastante ? "start" : "end", tabular: true
        });
        var a = S("tspan", {}); a.textContent = num(p.valor / total * 100, 1) + "%";
        var b = S("tspan", { fill: "var(--muted)", "font-weight": 400 });
        b.textContent = "  " + reais(p.valor);
        t.appendChild(a); t.appendChild(b);
        svg.appendChild(t);
      }
      acc += w;
    });
  }

  /** Séries temporais na mesma escala, com crosshair. */
  function linhas(svg, W, H, cfg) {
    var padL = 44, padR = 56, padT = 14, padB = 28;
    var pw = W - padL - padR, ph = H - padT - padB, max = 0;
    cfg.series.forEach(function (s) {
      s.dados.forEach(function (v) {
        if (v !== null && v !== undefined) max = Math.max(max, v);
      });
    });
    var sc = escala(max || 1);
    var X = function (i) { return padL + (pw * i / Math.max(1, cfg.rotulos.length - 1)); };
    var Y = function (v) { return padT + ph - (v / sc.topo * ph); };

    for (var t = 0; t <= sc.topo + 1e-9; t += sc.passo) {
      var y = Y(t);
      svg.appendChild(S("line", {
        x1: padL, x2: padL + pw, y1: y, y2: y,
        stroke: t === 0 ? "var(--rule-strong)" : "var(--rule)", "stroke-width": 1
      }));
      svg.appendChild(txt(padL - 8, y, num(t, 0),
        { anchor: "end", baseline: "middle", size: 10.5, tabular: true }));
    }
    cfg.rotulos.forEach(function (l, i) {
      if (i % cfg.cada === 0 || i === cfg.rotulos.length - 1)
        svg.appendChild(txt(X(i), H - 9, l, { anchor: "middle", size: 10.5 }));
    });

    if (cfg.anotacao) {
      var ax = X(cfg.anotacao.em);
      svg.appendChild(S("line", {
        x1: ax, x2: ax, y1: padT, y2: padT + ph, stroke: "var(--ink-2)",
        "stroke-width": 1, "stroke-dasharray": "3 3", opacity: 0.55
      }));
      svg.appendChild(txt(ax - 7, padT + 11, cfg.anotacao.texto,
        { anchor: "end", size: 10.5, fill: "var(--ink-2)" }));
    }

    cfg.series.forEach(function (s) {
      // Ponto nulo é competência sem declaração, não valor zero: a linha se
      // interrompe ali em vez de descer até o eixo e sugerir que nada entrou.
      var d = "", abrindo = true, ultimo = -1;
      s.dados.forEach(function (v, i) {
        if (v === null || v === undefined) { abrindo = true; return; }
        d += (abrindo ? "M" : "L") + X(i) + "," + Y(v);
        abrindo = false;
        ultimo = i;
      });
      if (!d) return;
      svg.appendChild(S("path", {
        d: d, fill: "none", stroke: s.cor, "stroke-width": 2,
        "stroke-linejoin": "round", "stroke-linecap": "round"
      }));
      // Um ponto cercado de ausências não vira segmento: marca-se sozinho.
      s.dados.forEach(function (v, i) {
        if (v === null || v === undefined) return;
        var antes = s.dados[i - 1], depois = s.dados[i + 1];
        if ((antes === null || antes === undefined) &&
            (depois === null || depois === undefined)) {
          svg.appendChild(S("circle", { cx: X(i), cy: Y(v), r: 3, fill: s.cor }));
        }
      });
      svg.appendChild(S("circle", {
        cx: X(ultimo), cy: Y(s.dados[ultimo]), r: 4.5, fill: s.cor,
        stroke: "var(--surface)", "stroke-width": 2
      }));
      svg.appendChild(txt(X(ultimo) + 9, Y(s.dados[ultimo]),
        num(s.dados[ultimo], cfg.dec), {
          fill: "var(--ink)", size: 11, weight: 500, baseline: "middle", tabular: true
        }));
    });

    var cruz = S("line", {
      x1: 0, x2: 0, y1: padT, y2: padT + ph, stroke: "var(--ink-2)",
      "stroke-width": 1, opacity: 0
    });
    svg.appendChild(cruz);
    var pontos = cfg.series.map(function (s) {
      var c = S("circle", {
        r: 4.5, fill: s.cor, stroke: "var(--surface)", "stroke-width": 2, opacity: 0
      });
      svg.appendChild(c); return c;
    });
    var alvo = S("rect", { x: padL - 6, y: padT, width: pw + 12, height: ph, fill: "transparent" });
    alvo.addEventListener("mousemove", function (ev) {
      var bb = svg.getBoundingClientRect();
      var rel = (ev.clientX - bb.left - padL) / pw * (cfg.rotulos.length - 1);
      var i = Math.max(0, Math.min(cfg.rotulos.length - 1, Math.round(rel)));
      cruz.setAttribute("x1", X(i)); cruz.setAttribute("x2", X(i));
      cruz.setAttribute("opacity", 0.45);
      var html = titulo(cfg.rotulos[i] + (cfg.unidade || ""));
      var completo = true;
      cfg.series.forEach(function (s, j) {
        var v = s.dados[i];
        if (v === null || v === undefined) {
          pontos[j].setAttribute("opacity", 0);
          completo = false;
          html += linha(s.cor, s.nome, cfg.rotuloAusente || "não declarado");
          return;
        }
        pontos[j].setAttribute("cx", X(i));
        pontos[j].setAttribute("cy", Y(v));
        pontos[j].setAttribute("opacity", 1);
        html += linha(s.cor, s.nome, num(v, cfg.dec));
      });
      if (cfg.delta && cfg.series.length === 2 && completo) {
        var d0 = cfg.series[0].dados[i] - cfg.series[1].dados[i];
        html += '<span class="r sub">' + cfg.delta + " " +
          (d0 >= 0 ? "+" : "−") + num(Math.abs(d0), cfg.dec) + "</span>";
      }
      mostrar(html, ev);
    });
    alvo.addEventListener("mouseleave", function () {
      esconder(); cruz.setAttribute("opacity", 0);
      pontos.forEach(function (c) { c.setAttribute("opacity", 0); });
    });
    svg.appendChild(alvo);
  }

  /** Barras horizontais com a marca do limite legal no mesmo eixo. */
  function comLimite(svg, W, H, cfg) {
    // Em tela estreita o nome do segmento não cabe ao lado da barra e invade a
    // área do gráfico. Abaixo de 420px o rótulo sobe para cima da barra, que é
    // onde há largura sobrando.
    var acima = W < 420;
    var padL = acima ? 0 : Math.min(112, W * 0.3), padR = acima ? 46 : 58, padB = 22;
    var linhasCfg = cfg.linhas, alturaLinha = (H - padB) / linhasCfg.length;
    var bh = acima ? 13 : 16;
    var pw = W - padL - padR;
    var X = function (p) { return padL + p / 100 * pw; };

    [0, 25, 50, 75, 100].forEach(function (t) {
      svg.appendChild(S("line", {
        x1: X(t), x2: X(t), y1: 0, y2: H - padB,
        stroke: t === 0 ? "var(--rule-strong)" : "var(--rule)", "stroke-width": 1
      }));
      svg.appendChild(txt(X(t), H - 7, t + "%", { anchor: "middle", size: 10.5 }));
    });

    linhasCfg.forEach(function (l, i) {
      var topo = i * alturaLinha;
      var y = acima ? topo + 18 : topo + (alturaLinha - bh) / 2;
      svg.appendChild(acima
        ? txt(0, topo + 11, l.rotulo, { fill: "var(--ink-2)", size: 11 })
        : txt(0, y + bh / 2, l.rotulo,
          { fill: "var(--ink-2)", size: 11.5, baseline: "middle" }));
      var cor = l.excede ? "var(--crit)" : "var(--s1)";
      var barra = S("path", { d: rrect(padL, y, X(l.perc) - padL, bh, 0, 4), fill: cor });
      ligar(barra, function (ev) {
        var html = titulo(l.rotulo) + linha(cor, "Posição",
          num(l.perc, 1) + "% · " + reais(l.valor));
        if (l.limite) html += '<span class="r sub">Limite CMN ' + num(l.limite, 0) +
          "% — usa " + num(l.perc / l.limite * 100, 0) + "%</span>";
        else html += '<span class="r sub">sem limite na fonte</span>';
        mostrar(html, ev);
      });
      svg.appendChild(barra);

      var lx = l.limite ? X(l.limite) : null;
      var vx = (lx !== null && lx - X(l.perc) < 48) ? lx + 9 : X(l.perc) + 7;
      svg.appendChild(txt(vx, y + bh / 2, num(l.perc, 1) + "%", {
        fill: "var(--ink)", size: 11, weight: 500, baseline: "middle", tabular: true
      }));
      if (lx !== null) {
        svg.appendChild(S("line", {
          x1: lx, x2: lx, y1: y - 5, y2: y + bh + 5, stroke: "var(--ink-2)",
          "stroke-width": 2, "stroke-linecap": "round"
        }));
        // Em tela estreita o rótulo do limite disputa espaço com o nome do
        // segmento, que importa mais. A marca permanece — é ela que carrega a
        // posição do teto — e o número fica na dica.
        if (!acima && pw >= 260) {
          svg.appendChild(txt(lx, y - 9, "lim " + num(l.limite, 0) + "%",
            { anchor: l.limite > 92 ? "end" : "middle", size: 9.5, fill: "var(--muted)" }));
        }
      }
    });
  }

  /** Barras horizontais ranqueadas, com cabeçalhos opcionais. */
  function ranqueadas(svg, W, H, cfg) {
    var linhasCfg = cfg.linhas;
    var cabecalhos = linhasCfg.filter(function (l) { return l.cabecalho; }).length;
    var barras = linhasCfg.length - cabecalhos || 1;
    var acima = cfg.rotuloAcima;
    var padL = acima ? 0 : Math.min(118, W * 0.36), padR = 52;
    var alturaLinha = (H - cabecalhos * 20) / barras;
    var bh = acima ? 12 : Math.min(16, alturaLinha - 9);
    var pw = W - padL - padR, max = 0, y = 0;
    linhasCfg.forEach(function (l) { if (!l.cabecalho) max = Math.max(max, l.perc); });
    if (!max) max = 1;

    linhasCfg.forEach(function (l) {
      if (l.cabecalho) {
        svg.appendChild(txt(0, y + 13, l.cabecalho, {
          size: 9.5, fill: "var(--muted)", weight: 500,
          style: "letter-spacing:.11em;text-transform:uppercase"
        }));
        y += 20;
        return;
      }
      var by = acima ? y + 16 : y + (alturaLinha - bh) / 2;
      svg.appendChild(acima
        ? txt(0, y + 9, l.rotulo, { fill: "var(--ink-2)", size: 11 })
        : txt(0, by + bh / 2, l.rotulo,
          { fill: "var(--ink-2)", size: 11, baseline: "middle" }));

      var w = l.perc / max * pw;
      var barra = S("path", { d: rrect(padL, by, w, bh, 0, 4), fill: "var(--s1)" });
      ligar(barra, function (ev) {
        mostrar(titulo(cfg.titulo || "") +
          linha("var(--s1)", l.rotulo, num(l.perc, 1) + "%") +
          '<span class="r sub">' + reais(l.valor) + "</span>", ev);
      });
      svg.appendChild(barra);
      svg.appendChild(txt(padL + w + 7, by + bh / 2, num(l.perc, 1) + "%", {
        fill: "var(--ink)", size: 11, weight: 500, baseline: "middle", tabular: true
      }));
      y += alturaLinha;
    });
  }

  var FORMAS = {
    empilhadas: empilhadas, barraUnica: barraUnica, linhas: linhas,
    comLimite: comLimite, ranqueadas: ranqueadas
  };

  var observador = null;
  var registrados = [];

  /** Desenha `forma` dentro de `el`, redesenhando quando o contêiner muda. */
  function desenhar(el, forma, cfg) {
    if (!el) return;
    el.__grafico = { forma: forma, cfg: cfg };
    render(el);
    if (!observador && global.ResizeObserver) {
      var pendente;
      observador = new ResizeObserver(function (entradas) {
        clearTimeout(pendente);
        pendente = setTimeout(function () {
          entradas.forEach(function (e) { render(e.target); });
        }, 120);
      });
    }
    if (observador && registrados.indexOf(el) === -1) {
      registrados.push(el);
      observador.observe(el);
    }
  }

  function render(el) {
    var g = el.__grafico;
    if (!g) return;
    var W = Math.max(240, Math.round(el.clientWidth));
    var H = g.cfg.altura || +el.dataset.altura || 220;
    el.textContent = "";
    var svg = S("svg", {
      class: "chart", width: W, height: H, viewBox: "0 0 " + W + " " + H,
      role: "img", "aria-label": g.cfg.descricao || ""
    });
    FORMAS[g.forma](svg, W, H, g.cfg);
    el.appendChild(svg);
  }

  global.Charts = {
    desenhar: desenhar, num: num, reais: reais,
    esconderDica: esconder
  };
})(window);
