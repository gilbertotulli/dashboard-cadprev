/* A estatística que o navegador calcula tem de bater com a do Python.
 *
 * O comparativo deixa escolher um conjunto qualquer de RPPS, e a mediana desse
 * conjunto só pode ser calculada no navegador — não há como pré-computar a
 * mediana de uma seleção arbitrária. É a única aritmética do projeto que existe
 * dos dois lados, e duas implementações da mesma conta divergem sozinhas com o
 * tempo.
 *
 * Este teste fecha a porta: monta em JavaScript os mesmos grupos que o Python
 * pré-calculou e exige igualdade exata, até o centésimo. As funções são
 * extraídas do próprio web/app.js — copiá-las aqui testaria a cópia.
 *
 * Rode depois de construir o painel:
 *
 *     python -m cadprev demo && node tests/estatistica-do-navegador.mjs
 */

import fs from 'fs';
const R = new URL('..', import.meta.url).pathname;
const src = fs.readFileSync(R+'web/app.js','utf8');

// Extrai do próprio app.js as funções de estatística — copiá-las aqui
// derrotaria o propósito de conferir o que é servido.
function extrair(nome){
  const i = src.indexOf('function '+nome+'(');
  if (i<0) throw new Error('não achei '+nome);
  let n=0, j=src.indexOf('{', i);
  for (let k=j;k<src.length;k++){
    if (src[k]==='{') n++;
    else if (src[k]==='}'){ n--; if(!n) return src.slice(i,k+1); }
  }
}
const codigo = ['percentilJS','arredondar','resumirJS','medianaJS']
  .map(extrair).join('\n');
const fns = new Function(codigo + '; return {resumirJS, medianaJS};')();

const b = JSON.parse(fs.readFileSync(R+'web/data/benchmark.json','utf8'));
const entes = JSON.parse(fs.readFileSync(R+'web/data/entes.json','utf8'));
const filtros = JSON.parse(fs.readFileSync(R+'web/data/filtros.json','utf8'));
const padrao = filtros.padrao;
const fora = new Set(entes.filter(e=>!e.tem_rpps).map(e=>e.cnpj));
const grupos = b.grupos.variantes[padrao];

let testes=0, falhas=0;
for (const [regiao, g] of Object.entries(grupos.regiao)){
  const membros = Object.entries(b.rpps)
    .filter(([c,d]) => !fora.has(c) && d.regiao===regiao)
    .map(([,d])=>d);
  if (membros.length !== g.rpps){
    console.log(`MEMBROS DIVERGEM em ${regiao}: js=${membros.length} py=${g.rpps}`);
    falhas++;
  }
  for (const ind of b.indicadores){
    const py = g.estatisticas[ind.chave];
    const js = fns.resumirJS(membros.map(m=>m.valores[ind.chave]));
    testes++;
    if (!py && !js) continue;
    if (!py || !js || JSON.stringify(py)!==JSON.stringify(js)){
      falhas++;
      console.log(`DIVERGE ${regiao}/${ind.chave}\n  py=${JSON.stringify(py)}\n  js=${JSON.stringify(js)}`);
    }
  }
  for (const seg of b.segmentos){
    const comCarteira = membros.filter(m=>m.alocacao && Object.keys(m.alocacao).length);
    const py = g.alocacao[seg];
    const js = fns.resumirJS(comCarteira.map(m=>m.alocacao[seg]===undefined?0:m.alocacao[seg]));
    testes++;
    if (!py && !js) continue;
    if (!py || !js || JSON.stringify(py)!==JSON.stringify(js)){
      falhas++;
      console.log(`DIVERGE alocação ${regiao}/${seg}\n  py=${JSON.stringify(py)}\n  js=${JSON.stringify(js)}`);
    }
  }
}
console.log(`\n${testes} comparações · ${falhas} divergências`);
process.exit(falhas?1:0);
