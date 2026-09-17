"""Linha de comando do projeto.

    python -m cadprev demo                    monta o painel com dados sintéticos
    python -m cadprev inspect DAIR_CARTEIRA   descobre os campos reais da API
    python -m cadprev ingest --tudo --uf ES   traz dados para o banco local
    python -m cadprev build                   gera os JSON do painel
    python -m cadprev status                  o que já foi ingerido
    python -m cadprev serve                   abre o painel em http://localhost:8000
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import List, Optional

from . import build, demo, endpoints, fieldmap, ingest, store as store_mod
from .client import Cliente

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_WEB = os.path.join(RAIZ, "web")

PADRAO_PAINEL = (
    "RPPS_REGIME_PREVIDENCIARIO", "RPPS_CRP", "RPPS_ALIQUOTA", "DIPR",
    "DAIR_CARTEIRA", "DRAA_ESTATISTICA", "DRAA_SEGREGACAO_MASSA",
    "DRAA_FLUXO_ATUARIAL", "DRAA_VALORES_COMPROMISSOS",
    "DRAA_HIPOTESE_ATUARIAL", "DRAA_PLANO_CUSTEIO",
)


def _cliente(args) -> Cliente:
    return Cliente(base_url=args.base_url, pausa=args.pausa,
                   fixtures=getattr(args, "fixtures", None))


# --------------------------------------------------------------------------

def cmd_inspect(args) -> int:
    """Uma página de cada endpoint, para fixar os nomes de campo."""
    cliente = _cliente(args)
    filtros = {k: v for k, v in (("sg_uf", args.uf), ("dt_ano", args.ano),
                                 ("dt_exercicio", args.exercicio)) if v}
    saiu_incompleto = False

    for nome in args.endpoints:
        filtros_validos = ingest._filtrar_aplicaveis(nome, filtros)
        relatorio = ingest.inspecionar(cliente, nome, salvar=args.salvar,
                                       **filtros_validos)
        print("\n=== {} ===".format(nome))
        if not relatorio["registros"]:
            print("  a API não devolveu registros para", filtros_validos or "(sem filtro)")
            continue

        print("  {} registros na primeira página".format(relatorio["registros"]))
        print("  chaves: " + ", ".join(relatorio["chaves"]))
        resolucao = relatorio["resolucao"]
        print("  " + resolucao.resumo().replace("\n", "\n  "))
        if resolucao.faltando_obrigatorios:
            saiu_incompleto = True
        if args.salvar:
            print("  salvo em", relatorio["salvo_em"])
        if args.override:
            print("  sugestão para fieldmap.local.json:")
            print("  " + json.dumps({nome: relatorio["sugestao_override"]},
                                    ensure_ascii=False, indent=2).replace("\n", "\n  "))

    if saiu_incompleto:
        print("\nHá campos obrigatórios não resolvidos. Aponte o nome real em "
              "fieldmap.local.json antes de ingerir.", file=sys.stderr)
        return 1
    return 0


def cmd_ingest(args) -> int:
    nomes: List[str] = list(PADRAO_PAINEL) if args.tudo else args.endpoints
    if not nomes:
        print("informe endpoints ou use --tudo", file=sys.stderr)
        return 2

    filtros = {k: v for k, v in (
        ("sg_uf", args.uf), ("nr_cnpj_entidade", args.cnpj),
        ("dt_ano", args.ano), ("dt_mes", args.mes),
        ("dt_mes_bimestre", args.mes), ("dt_exercicio", args.exercicio),
    ) if v}
    escopo = {k: v for k, v in (("ano", args.ano), ("exercicio", args.exercicio))
              if v} or None

    with store_mod.Store(args.banco) as store:
        resultado = ingest.ingerir_varios(_cliente(args), store, nomes,
                                          escopo=escopo, **filtros)

    for item in resultado["ok"]:
        marca = " · nível {}".format(item["nivel"]) if item["nivel"] else ""
        print("  {:<28} {:>8} linhas{}".format(item["endpoint"], item["linhas"], marca))
    for item in resultado["erros"]:
        print("  {:<28} ERRO: {}".format(item["endpoint"], item["erro"]),
              file=sys.stderr)
    return 1 if resultado["erros"] else 0


def cmd_build(args) -> int:
    with store_mod.Store(args.banco) as store:
        if not store.tabelas() or store.tabelas() == ["execucao"]:
            print("banco vazio — rode `python -m cadprev ingest` ou "
                  "`python -m cadprev demo` antes.", file=sys.stderr)
            return 1
        resultado = build.construir(store, dir_saida=args.saida, origem=args.origem,
                                    limite_entes=args.limite_entes)
    meta = resultado["meta"]
    print("  {} arquivos em {}".format(resultado["arquivos"], args.saida))
    print("  {} entes · nível de fundo {} · origem {}".format(
        meta["entes"], meta["nivel_fundo"] or "—", meta["origem"]))
    return 0


def cmd_demo(args) -> int:
    """Gera dados sintéticos, ingere e constrói — o painel de pé em um comando."""
    contagem = demo.escrever(nivel_a=args.nivel_a)
    print("  amostras geradas: {} registros em {} endpoints".format(
        sum(contagem.values()), len(contagem)))

    banco = args.banco
    if os.path.exists(banco):
        os.remove(banco)
    cliente = Cliente(fixtures=demo.DIR_DEMO, pausa=0)
    with store_mod.Store(banco) as store:
        resultado = ingest.ingerir_varios(cliente, store, sorted(contagem))
        for item in resultado["ok"]:
            print("  {:<28} {:>8} linhas".format(item["endpoint"], item["linhas"]))
        for item in resultado["erros"]:
            print("  {:<28} ERRO: {}".format(item["endpoint"], item["erro"]),
                  file=sys.stderr)

        # A tabela de entes do SICONFI vem da outra API e por isso não entra no
        # laço acima. Sem ela o demo classificaria a esfera por dedução, que é
        # justamente o caminho que o painel deixou de usar.
        from cadprev import siconfi
        brutos = siconfi.Cliente(fixtures=demo.DIR_DEMO, pausa=0).entes()
        resolucao = fieldmap.resolver("SICONFI_ENTE", brutos[0].keys())
        linhas = store.gravar(
            "SICONFI_ENTE",
            (fieldmap.aplicar(resolucao, b) for b in brutos))
        store.registrar_execucao("SICONFI_ENTE", {}, linhas, resolucao)
        print("  {:<28} {:>8} linhas".format("SICONFI_ENTE", linhas))

        saida = build.construir(store, dir_saida=args.saida, origem="demonstracao")

    print("\n  painel pronto em {} (origem: demonstracao)".format(args.saida))
    print("  veja com: python -m cadprev serve")
    return 1 if resultado["erros"] else 0


def cmd_status(args) -> int:
    if not os.path.exists(args.banco):
        print("nenhum banco em", args.banco)
        return 0
    with store_mod.Store(args.banco) as store:
        linhas = store.resumo()
    if not linhas:
        print("banco criado, nada ingerido ainda.")
        return 0
    print("  {:<28} {:>9}  {:<20} {}".format("ENDPOINT", "LINHAS", "QUANDO", "FILTROS"))
    for linha in linhas:
        print("  {:<28} {:>9}  {:<20} {}".format(
            linha["endpoint"], linha["linhas"], (linha["quando"] or "—")[:19],
            json.dumps(linha["filtros"], ensure_ascii=False) if linha["filtros"] else "—"))
    return 0


def cmd_competencia(args) -> int:
    """Descobre na fonte qual competência do DAIR já está fechada.

    Existe para que o agendamento não precise adivinhar por calendário. A saída
    sai em ``chave=valor``, pronta para alimentar o ``$GITHUB_OUTPUT``.
    """
    from cadprev import competencia as comp
    cliente = Cliente(pausa=args.pausa)
    achado = comp.mais_recente_fechada(cliente, uf=args.uf)
    if achado is None:
        print("nenhuma competência do DAIR tem dados nos últimos {} meses"
              .format(comp.MESES_PARA_TRAS), file=sys.stderr)
        return 1
    ano, mes = achado
    print("ano={}".format(ano))
    print("mes={}".format(mes))
    return 0


def cmd_siconfi(args) -> int:
    """Traz a tabela de entes da federação do SICONFI.

    Uma requisição para o país inteiro. Dá população e marca de capital
    autoritativas, no lugar da dedução por nome que já classificou São Paulo e
    Rio de Janeiro como estaduais.
    """
    from cadprev import siconfi
    cliente = siconfi.Cliente(pausa=args.pausa, fixtures=args.fixtures)
    brutos = cliente.entes()
    if not brutos:
        print("o SICONFI não devolveu entes", file=sys.stderr)
        return 1
    resolucao = fieldmap.resolver("SICONFI_ENTE", brutos[0].keys())
    fieldmap.exigir(resolucao, list(brutos[0].keys()))
    registros = [fieldmap.aplicar(resolucao, b) for b in brutos]
    registros = [r for r in registros if r.get("cnpj_ente")]
    with store_mod.Store(args.banco) as store:
        linhas = store.gravar("SICONFI_ENTE", registros)
        store.registrar_execucao("SICONFI_ENTE", {}, linhas, resolucao)
        store.marcar_origem("demonstracao" if args.fixtures else "api")
    capitais = sum(1 for r in registros if r.get("capital"))
    print("SICONFI_ENTE: {} entes ({} capitais)".format(linhas, capitais))
    return 0


def cmd_marco(args) -> int:
    """Anota o carimbo de atualização da fonte, para medir o que muda.

    A API não deixa filtrar por data de alteração, mas publica um carimbo
    global. Registrar esse carimbo a cada carga é o que vai permitir, depois de
    algumas semanas de histórico, decidir com evidência se a varredura completa
    pode ser dispensada — em vez de cortar no escuro.
    """
    cliente = Cliente(pausa=args.pausa)
    try:
        pagina = cliente.pagina("DATA_ATUALIZACAO", offset=0)
        dados = pagina.get("data") or []
        bruto = dados[0].get("DTAtualizacao") if dados else None
    except Exception as erro:  # a medição não pode derrubar a carga
        print("não consegui ler DATA_ATUALIZACAO: {}".format(erro), file=sys.stderr)
        return 0

    valor = None
    if bruto is not None:
        try:
            valor = datetime.fromtimestamp(
                int(bruto) / 1000, tz=timezone.utc).isoformat(timespec="seconds")
        except (TypeError, ValueError):
            valor = str(bruto)

    with store_mod.Store(args.banco) as store:
        mudou = store.registrar_marco("data_atualizacao", valor)
        historico = store.marcos("data_atualizacao")
    print("fonte atualizada em: {}".format(valor or "—"))
    print("mudou desde a última carga: {}".format("sim" if mudou else "não"))
    print("mudanças registradas até agora: {}".format(len(historico)))
    return 0


def cmd_serve(args) -> int:
    import http.server
    import socketserver

    os.chdir(DIR_WEB)
    manipulador = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", args.porta), manipulador) as servidor:
        print("painel em http://localhost:{}  (Ctrl+C para parar)".format(args.porta))
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print()
    return 0


def cmd_endpoints(args) -> int:
    for familia, rotulo in endpoints.FAMILIAS.items():
        print("\n{}".format(rotulo))
        for alvo in endpoints.CATALOGO:
            if alvo.familia != familia:
                continue
            mapeado = "·" if alvo.nome in fieldmap.endpoints_mapeados() else " "
            print("  {} {:<30} {}".format(mapeado, alvo.nome, alvo.descricao[:64]))
    print("\n· = tem mapa de campos em cadprev/fieldmap.py")
    return 0


# --------------------------------------------------------------------------

def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cadprev", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--banco", default=store_mod.CAMINHO_PADRAO,
                        help="arquivo SQLite (padrão: cadprev.sqlite3)")
    parser.add_argument("--base-url", default=endpoints.BASE_URL)
    parser.add_argument("--pausa", type=float, default=1.0,
                        help="segundos entre requisições (padrão: 1)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("inspect", help="descobre os campos reais de um endpoint")
    p.add_argument("endpoints", nargs="+")
    p.add_argument("--uf")
    p.add_argument("--ano", type=int)
    p.add_argument("--exercicio", type=int)
    p.add_argument("--salvar", action="store_true",
                   help="grava o observado em docs/schema-observado/")
    p.add_argument("--override", action="store_true",
                   help="imprime sugestão de fieldmap.local.json")
    p.add_argument("--fixtures")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("ingest", help="traz dados da API para o banco local")
    p.add_argument("endpoints", nargs="*")
    p.add_argument("--tudo", action="store_true",
                   help="os endpoints que o painel usa")
    p.add_argument("--uf")
    p.add_argument("--cnpj")
    p.add_argument("--ano", type=int)
    p.add_argument("--mes", type=int)
    p.add_argument("--exercicio", type=int)
    p.add_argument("--fixtures")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("build", help="gera os JSON que o painel lê")
    p.add_argument("--saida", default=build.DIR_SAIDA)
    p.add_argument("--origem", default="api", choices=("api", "demonstracao"))
    p.add_argument("--limite-entes", type=int)
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("demo", help="painel de pé com dados sintéticos")
    p.add_argument("--saida", default=build.DIR_SAIDA)
    p.add_argument("--nivel-a", action="store_true",
                   help="gera o campo de plano do ativo, ainda não confirmado na API")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("status", help="o que já foi ingerido")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("siconfi",
                       help="traz a tabela de entes da federação do SICONFI")
    p.add_argument("--pausa", type=float, default=0.5)
    p.add_argument("--fixtures")
    p.set_defaults(func=cmd_siconfi)

    p = sub.add_parser("marco",
                       help="anota o carimbo de atualização da fonte")
    p.add_argument("--pausa", type=float, default=1.0)
    p.set_defaults(func=cmd_marco)

    p = sub.add_parser("competencia",
                       help="pergunta à API qual competência do DAIR já fechou")
    p.add_argument("--uf")
    p.add_argument("--pausa", type=float, default=1.0)
    p.set_defaults(func=cmd_competencia)

    p = sub.add_parser("serve", help="serve o painel localmente")
    p.add_argument("--porta", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("endpoints", help="lista o catálogo da API")
    p.set_defaults(func=cmd_endpoints)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = construir_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
