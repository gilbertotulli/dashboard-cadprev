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
from typing import Any, List, Optional

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

        rreo = siconfi.ClienteRREO(fixtures=demo.DIR_DEMO, pausa=0)
        do_anexo = []
        for alvo in store.consultar(
                "SELECT cnpj_ente, cod_ibge, esfera_siconfi FROM siconfi_ente"):
            itens = rreo.anexo_rpps(alvo["cod_ibge"], alvo["esfera_siconfi"],
                                    demo.ANO, 3)
            for item in itens:
                item["cnpj_ente"] = alvo["cnpj_ente"]
            do_anexo.extend(itens)
        if do_anexo:
            resolucao = fieldmap.resolver("SICONFI_RREO", do_anexo[0].keys())
            linhas = store.gravar(
                "SICONFI_RREO",
                (fieldmap.aplicar(resolucao, l) for l in do_anexo),
                {"exercicio": demo.ANO, "periodo": 3})
            store.registrar_execucao("SICONFI_RREO",
                                     {"exercicio": demo.ANO, "periodo": 3},
                                     linhas, resolucao)
            print("  {:<28} {:>8} linhas".format("SICONFI_RREO", linhas))

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

    Quando a fonte não responde, cai para a competência que já está no banco.
    Não é a mesma coisa e a saída diz qual das duas é: ``origem=api`` ou
    ``origem=banco``. A diferença importa porque com a fonte fora do ar a
    publicação não traz dado novo — mas abortar o agendamento por causa disso
    deixaria o painel sem publicar e sem dizer por quê, que é pior do que
    republicar o que já se tem com a data antiga à vista.
    """
    from cadprev import competencia as comp
    erro, vistos = None, []
    try:
        cliente = Cliente(pausa=args.pausa)
        vistos = comp.volumes(cliente, uf=args.uf)
        achado = comp.escolher(vistos)
    except Exception as falha:  # rede, 404, 500, mudança de contrato
        achado, erro = None, falha

    # A medida ao lado da escolha: sem isso, uma competência errada no painel
    # não teria como ser diagnosticada pelo log da execução.
    for ano, mes, quantos in vistos:
        marca = " <-- escolhida" if achado == (ano, mes) else ""
        print("  {}-{:02d}: {} declarantes{}".format(ano, mes, quantos, marca),
              file=sys.stderr)

    if achado is None:
        do_banco = _competencia_do_banco(args.banco)
        if do_banco is not None:
            ano, mes = do_banco
            print("a fonte não respondeu ({}); usando a competência do banco"
                  .format(erro if erro else "sem competência com dados"),
                  file=sys.stderr)
            print("ano={}".format(ano))
            print("mes={}".format(mes))
            print("origem=banco")
            return 0
        if erro is not None:
            print("a fonte não respondeu e o banco não tem competência: {}"
                  .format(erro), file=sys.stderr)
        else:
            print("nenhuma competência do DAIR tem dados nos últimos {} meses"
                  .format(comp.MESES_PARA_TRAS), file=sys.stderr)
        return 1

    ano, mes = achado
    print("ano={}".format(ano))
    print("mes={}".format(mes))
    print("origem=api")
    return 0


def _competencia_do_banco(banco: str):
    """A competência mais recente que o banco local já guarda, se houver."""
    try:
        with store_mod.Store(banco) as store:
            if not store.tem_tabela("DAIR_CARTEIRA"):
                return None
            linha = store.consultar(
                "SELECT MAX(ano * 100 + mes) AS chave FROM dair_carteira "
                "WHERE ano IS NOT NULL AND mes IS NOT NULL")
    except Exception:
        return None
    chave = linha[0]["chave"] if linha else None
    if not chave:
        return None
    return int(chave) // 100, int(chave) % 100


def cmd_execucoes(args) -> int:
    """Quantas ingestões este banco já registrou — um número, e só.

    Serve ao agendamento para distinguir "os dados essenciais estão no banco"
    de "esta carga trouxe alguma coisa". Com o cache restaurado as duas coisas
    se confundem, e foi essa confusão que deixaria uma execução em que a API
    não respondeu a nada se carimbar como varredura bem-sucedida.
    """
    try:
        with store_mod.Store(args.banco) as store:
            linha = store.consultar("SELECT COUNT(*) AS n FROM execucao")
        print(linha[0]["n"] if linha else 0)
    except Exception:
        print(0)
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


def cmd_siconfi_rreo(args) -> int:
    """Traz o Anexo 04 do RREO — o demonstrativo previdenciário — ente a ente.

    A API do SICONFI exige `id_ente`: não há varredura em bloco, é uma
    requisição por ente e por competência. Por isso só os entes com RPPS entram,
    e não os 5.598 da federação.

    Ausência não é erro. Quem não entregou o demonstrativo simplesmente não
    aparece, e a contagem final diz quantos foram.
    """
    from cadprev import siconfi
    with store_mod.Store(args.banco) as store:
        if not store.tem_tabela("SICONFI_ENTE"):
            print("rode `python -m cadprev siconfi` antes: o Anexo 04 é "
                  "consultado por código IBGE, que vem da tabela de entes.",
                  file=sys.stderr)
            return 1
        sql = ("SELECT s.cnpj_ente, s.cod_ibge, s.esfera_siconfi, s.ente "
               "FROM siconfi_ente s WHERE s.cod_ibge IS NOT NULL")
        parametros: List[Any] = []
        if store.tem_tabela("DAIR_CARTEIRA"):
            sql += (" AND s.cnpj_ente IN "
                    "(SELECT DISTINCT cnpj_ente FROM dair_carteira)")
        if args.uf:
            sql += " AND s.uf = ?"
            parametros.append(args.uf.upper())
        sql += " ORDER BY s.cnpj_ente"
        alvos = [dict(l) for l in store.consultar(sql, tuple(parametros))]

    if args.limite:
        alvos = alvos[:args.limite]
    if not alvos:
        print("nenhum ente com RPPS e código IBGE no banco", file=sys.stderr)
        return 1

    cliente = siconfi.ClienteRREO(pausa=args.pausa, fixtures=args.fixtures)
    linhas: List[Dict[str, Any]] = []
    com, sem, falhas = 0, 0, 0
    for n, alvo in enumerate(alvos, 1):
        try:
            itens = cliente.anexo_rpps(alvo["cod_ibge"], alvo["esfera_siconfi"],
                                       args.exercicio, args.periodo)
        except Exception as erro:
            falhas += 1
            log.warning("%s (%s): %s", alvo["ente"], alvo["cod_ibge"], erro)
            continue
        if not itens:
            sem += 1
            continue
        com += 1
        for item in itens:
            item["cnpj_ente"] = alvo["cnpj_ente"]
        linhas.extend(itens)
        if n % 200 == 0:
            print("  {}/{} entes · {} com demonstrativo".format(n, len(alvos), com),
                  flush=True)

    if not linhas:
        print("nenhum ente entregou o Anexo 04 nesta competência", file=sys.stderr)
        return 1

    resolucao = fieldmap.resolver("SICONFI_RREO", linhas[0].keys())
    fieldmap.exigir(resolucao, list(linhas[0].keys()))
    traduzidas = [fieldmap.aplicar(resolucao, l) for l in linhas]
    escopo = {"exercicio": args.exercicio, "periodo": args.periodo}
    with store_mod.Store(args.banco) as store:
        gravadas = store.gravar("SICONFI_RREO", traduzidas, escopo)
        store.registrar_execucao("SICONFI_RREO", escopo, gravadas, resolucao)
        store.marcar_origem("demonstracao" if args.fixtures else "api")
    print("SICONFI_RREO {}º bimestre/{}: {} linhas · {} entes com "
          "demonstrativo, {} sem, {} falhas".format(
              args.periodo, args.exercicio, gravadas, com, sem, falhas))
    return 0


def cmd_marco(args) -> int:
    """Anota o carimbo de atualização da fonte, para medir o que muda.

    A API não deixa filtrar por data de alteração, mas publica um carimbo
    global. Registrar esse carimbo a cada carga é o que vai permitir, depois de
    algumas semanas de histórico, decidir com evidência se a varredura completa
    pode ser dispensada — em vez de cortar no escuro.
    """
    cliente = Cliente(pausa=args.pausa)
    falha = None
    try:
        pagina = cliente.pagina("DATA_ATUALIZACAO", offset=0)
        dados = pagina.get("data") or []
        bruto = dados[0].get("DTAtualizacao") if dados else None
    except Exception as erro:  # a medição não pode derrubar a carga
        print("não consegui ler DATA_ATUALIZACAO: {}".format(erro), file=sys.stderr)
        falha = erro

    # Registrar que a fonte respondeu — ou não — é tão informativo quanto o
    # carimbo dela. Sem isso o painel republica com a data antiga e não tem como
    # dizer que a fonte está fora do ar desde quando: o leitor veria um dado de
    # semanas atrás sem nenhuma indicação de que ele não envelheceu por
    # descuido, mas porque a origem parou de responder.
    with store_mod.Store(args.banco) as store:
        store.registrar_marco("fonte_alcancavel", "nao" if falha else "sim")
    if falha is not None:
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

    p = sub.add_parser("siconfi-rreo",
                       help="traz o Anexo 04 do RREO, ente a ente")
    p.add_argument("--exercicio", type=int, required=True)
    p.add_argument("--periodo", type=int, required=True,
                   help="bimestre, de 1 a 6")
    p.add_argument("--uf")
    p.add_argument("--limite", type=int)
    p.add_argument("--pausa", type=float, default=0.5)
    p.add_argument("--fixtures")
    p.set_defaults(func=cmd_siconfi_rreo)

    p = sub.add_parser("execucoes",
                       help="quantas ingestões o banco já registrou")
    p.set_defaults(func=cmd_execucoes)

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
