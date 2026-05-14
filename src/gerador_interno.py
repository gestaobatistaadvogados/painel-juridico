"""
Gerador dos paineis internos do escritorio L Batista:
  - painel-interno.html (+ index.html): hub com TODOS os clientes ativos
  - 4 paineis-gestor (Decisao D12): um por departamento, mesmo template,
    filtrado para os clientes daquele departamento

Diferente de gerador_producao.py:
  - Lista TODOS os clientes ativos do config/clientes.json
  - NAO agrupa por area (visao por cliente)
  - Agrega atividade 90d de todos os clientes (escritorio inteiro)
  - Saida: painel-interno.html + index.html na RAIZ; paineis-gestor em
    clientes/painel-gestor-<depto>-<ano>-<4hex>/index.html
  - Visualizado APENAS pelos socios e gestores — nunca enviado a clientes

Reaproveita helpers de gerador_producao.py:
  - carregar_clientes_ativos, carregar_escritorio
  - mascarar_identification, normalizar_digitos
  - categoria_alerta
  - _baixar_posts_paginado, _categorizar_posts
  - calcular_atividade_90d (cache por cliente, TTL 24h)
  - construir_jinja_env (com filtro rotulo_departamento)
"""

import json
import secrets
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advbox_client import AdvboxClient, AdvboxError
from cache import cache_get, cache_set
from gerador_producao import (
    RAIZ,
    FUSO_BRT,
    carregar_clientes_ativos,
    carregar_escritorio,
    mascarar_identification,
    normalizar_digitos,
    categoria_alerta,
    calcular_atividade_90d,
    construir_jinja_env,
    _baixar_posts_paginado,
    _categorizar_posts,
)


SAIDA_HTML = RAIZ / 'painel-interno.html'
# index.html identico ao painel-interno, na raiz, servir como pagina
# inicial do GitHub Pages (a URL https://...github.io/painel-juridico/
# por default procura index.html). Mantemos ambos os arquivos:
#  - painel-interno.html: para uso local (`start painel-interno.html`)
#  - index.html:          para a URL publica do GitHub Pages
SAIDA_HTML_INDEX = RAIZ / 'index.html'
TEMPLATE_NAME = 'painel_interno.html'

# === DECISAO D12 — PAINEIS-GESTOR POR DEPARTAMENTO ===
# Um painel-gestor por departamento, mesmo template do painel-interno,
# filtrado para os clientes daquele departamento. Slugs gerados UMA vez
# e persistidos em config/paineis_gestor.json (nunca regerados).
CONFIG_PAINEIS_GESTOR = RAIZ / 'config' / 'paineis_gestor.json'

# (chave snake_case, rotulo de exibicao). Ordem fixa para o JSON/relatorio.
DEPARTAMENTOS_GESTOR = [
    ('direito_privado', 'Direito Privado'),
    ('direito_imobiliario', 'Direito Imobiliário'),
    ('direito_publico', 'Direito Público'),
    ('direito_criminal', 'Direito Criminal'),
]


# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------

def _strip_acentos(texto):
    """Remove acentos para a busca textual case-insensitive."""
    if not texto:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFKD', str(texto).lower())
        if not unicodedata.combining(c)
    )


def _coletar_customer_cached(client, cid):
    chave = f'customers_{cid}'
    dados = cache_get(chave)
    if dados is None:
        dados = client.get_customer(cid)
        cache_set(chave, dados)
    return dados


def _coletar_lawsuits_cached(client, cid):
    """Devolve lista de lawsuits brutos (envelope desempacotado)."""
    chave = f'lawsuits_customer_{cid}'
    envelope = cache_get(chave)
    if envelope is None:
        envelope = client.get_lawsuits(customer_id=cid, limit=1000, offset=0)
        cache_set(chave, envelope)
    if isinstance(envelope, dict) and isinstance(envelope.get('data'), list):
        return envelope['data']
    if isinstance(envelope, list):
        return envelope
    return []


# ---------------------------------------------------------------------------
# Config dos paineis-gestor (Decisao D12)
# ---------------------------------------------------------------------------

def _slugs_existentes_clientes():
    """Set de todos os slug_url ja registrados em config/clientes.json.

    Usado para garantir que um slug de painel-gestor recem-gerado nao colida
    com nenhum slug de painel-cliente.
    """
    try:
        with (RAIZ / 'config' / 'clientes.json').open(encoding='utf-8') as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return set()
    return {c.get('slug_url') for c in cfg.get('clientes', []) if c.get('slug_url')}


def carregar_ou_criar_paineis_gestor():
    """Le config/paineis_gestor.json; cria na primeira execucao e persiste.

    Decisao D12 (restricao): os slugs sao gerados UMA unica vez. Se o arquivo
    ja existe, os slugs sao reaproveitados — nunca regerados. Cada slug usa
    `secrets.token_hex(2)` (4 chars hex) e e verificado contra os slugs ja
    presentes em config/clientes.json antes de ser persistido.
    """
    if CONFIG_PAINEIS_GESTOR.exists():
        with CONFIG_PAINEIS_GESTOR.open(encoding='utf-8') as f:
            return json.load(f)

    ocupados = _slugs_existentes_clientes()
    ano = datetime.now(FUSO_BRT).year
    criado_em = datetime.now(FUSO_BRT).isoformat(timespec='seconds')

    paineis = []
    for dep_key, dep_label in DEPARTAMENTOS_GESTOR:
        depto_curto = dep_key.replace('direito_', '')
        while True:
            slug = f'painel-gestor-{depto_curto}-{ano}-{secrets.token_hex(2)}'
            if slug not in ocupados:
                ocupados.add(slug)
                break
        paineis.append({
            'departamento': dep_key,
            'departamento_label': dep_label,
            'slug': slug,
            'ativo': True,
            'criado_em': criado_em,
        })

    dados = {
        '_comentario': (
            'Decisao D12 — slugs dos paineis-gestor por departamento. '
            'Gerados uma unica vez e persistidos; o gerador reaproveita este '
            'arquivo e NUNCA regenera os slugs.'
        ),
        'paineis': paineis,
    }
    CONFIG_PAINEIS_GESTOR.write_text(
        json.dumps(dados, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
    )
    return dados


# ---------------------------------------------------------------------------
# Construcao do contexto
# ---------------------------------------------------------------------------

def construir_resumo_cliente(cliente_cfg, client):
    """Resumo de UM cliente para card no hub. Reaproveita cache existente.

    Retorna dict com:
      id_advbox, nome, identification (mascarado), tipo_pessoa,
      departamento, slug_url, qtd_processos, qtd_urgentes,
      qtd_atencao, qtd_arquivados, tarefas_90d, busca_normalizada,
      lawsuit_ids (set, para o agregador global)
    """
    cid = cliente_cfg['id_advbox']

    customer_bruto = _coletar_customer_cached(client, cid)
    lawsuits = _coletar_lawsuits_cached(client, cid)

    # Contagem de alertas usando categoria_alerta (so stage + status_closure,
    # nao precisa baixar movements — economia de chamadas).
    n_urgentes = 0
    n_atencao = 0
    n_arquivados = 0
    lawsuit_ids = set()
    for law in lawsuits:
        if not isinstance(law, dict):
            continue
        lid = law.get('id')
        if lid is not None:
            try:
                lawsuit_ids.add(int(lid))
            except (ValueError, TypeError):
                pass
        cat = categoria_alerta(law)
        if cat == 'urgente':
            n_urgentes += 1
        elif cat == 'atencao':
            n_atencao += 1
        elif cat == 'favoravel':
            n_arquivados += 1

    # Atividade 90d desse cliente (cache por cliente — chave posts_customer_<id>)
    atividade = calcular_atividade_90d(cid, lawsuit_ids, client)

    # Mascaramento e tipo
    ident_raw = customer_bruto.get('identification') or ''
    digitos = normalizar_digitos(ident_raw)
    tipo_pessoa = 'PJ' if len(digitos) == 14 else ('PF' if len(digitos) == 11 else '—')
    ident_mascarado = mascarar_identification(ident_raw)

    nome = (customer_bruto.get('name') or cliente_cfg.get('nome_curto') or '').strip()
    cidade = (customer_bruto.get('city') or '').strip()
    busca_norm = _strip_acentos(' '.join((nome, cidade, digitos)))

    return {
        'id_advbox': cid,
        'nome': nome,
        'identification': ident_mascarado,
        'tipo_pessoa': tipo_pessoa,
        'departamento': cliente_cfg.get('departamento', ''),
        'slug_url': cliente_cfg['slug_url'],
        'qtd_processos': len(lawsuits),
        'qtd_urgentes': n_urgentes,
        'qtd_atencao': n_atencao,
        'qtd_arquivados': n_arquivados,
        'tarefas_90d': atividade['total'],
        'busca_normalizada': busca_norm,
        'lawsuit_ids': lawsuit_ids,
    }


def montar_dados_painel(clientes_resumo, posts_brutos, escritorio,
                        cabecalho_titulo, escopo='completo'):
    """Monta o dict de contexto Jinja de UM painel (interno ou gestor).

    Funcao reutilizavel — base da Decisao D12. Recebe a lista de clientes JA
    filtrada para o escopo desejado e recalcula TUDO sobre esse subconjunto:
      - KPIs (total clientes/processos/criticos/tarefas 90d)
      - counts por departamento
      - bloco "Tarefas Realizadas 90 dias": cruza `posts_brutos` apenas com os
        `lawsuit_ids` dos clientes do escopo — nenhum processo de cliente fora
        do escopo entra no bloco (filtragem estrita por departamento).

    escopo='completo' -> painel-interno (todos os clientes ativos).
    escopo='gestor'   -> painel-gestor (clientes ja filtrados por departamento).

    `posts_brutos` e baixado UMA vez pelo chamador e reaproveitado por todos
    os paineis.
    """
    # Bloco 90d: cruza posts globais com os lawsuit_ids SO deste escopo.
    ids_do_escopo = set()
    for c in clientes_resumo:
        ids_do_escopo.update(c.get('lawsuit_ids') or set())
    limite_90d = datetime.now().date() - timedelta(days=90)
    atividade = _categorizar_posts(posts_brutos, ids_do_escopo, limite_90d)

    total_clientes = len(clientes_resumo)
    total_processos = sum(c['qtd_processos'] for c in clientes_resumo)
    total_alertas_criticos = sum(c['qtd_urgentes'] for c in clientes_resumo)
    total_tarefas_90d = sum(c['tarefas_90d'] for c in clientes_resumo)

    counts_por_dep = Counter(c['departamento'] for c in clientes_resumo)
    counts_por_dep = {k: v for k, v in counts_por_dep.items() if k}

    # Caminhos relativos: o painel-interno fica na RAIZ; os paineis-gestor
    # ficam em clientes/<slug>/. Logo e links de cliente precisam de prefixo
    # distinto para resolver a partir de cada localizacao.
    if escopo == 'gestor':
        logo_src = '../../config/logo.png'
        caminho_cliente_base = '../'
    else:
        logo_src = 'config/logo.png'
        caminho_cliente_base = './clientes/'

    return {
        'cabecalho_titulo': cabecalho_titulo,
        'escopo': escopo,
        'logo_src': logo_src,
        'caminho_cliente_base': caminho_cliente_base,
        'kpis': {
            'total_clientes': total_clientes,
            'total_processos': total_processos,
            'total_alertas_criticos': total_alertas_criticos,
            'total_tarefas_90d': total_tarefas_90d,
        },
        'atividade_global': atividade,
        'counts_por_departamento': counts_por_dep,
        'escritorio': escritorio,
        'data_geracao': datetime.now(FUSO_BRT).strftime('%d/%m/%Y às %H:%M'),
        'clientes': clientes_resumo,
    }


def gerar_painel_interno(clientes_resumo, posts_brutos, escritorio, env):
    """Painel-interno: TODOS os clientes ativos. Escrito na raiz em
    painel-interno.html + index.html (pagina default do GitHub Pages).
    Comportamento original — inalterado pela Decisao D12.
    """
    dados = montar_dados_painel(
        clientes_resumo, posts_brutos, escritorio,
        cabecalho_titulo='Painel Interno', escopo='completo',
    )
    html = env.get_template(TEMPLATE_NAME).render(**dados)
    SAIDA_HTML.write_text(html, encoding='utf-8')
    SAIDA_HTML_INDEX.write_text(html, encoding='utf-8')
    return dados


def gerar_paineis_gestor(clientes_resumo, posts_brutos, escritorio, env):
    """Decisao D12: um painel-gestor por departamento, mesmo template do
    painel-interno, filtrado ESTRITAMENTE por cliente['departamento'].

    Cada painel e escrito em clientes/<slug>/index.html, com o slug
    persistido em config/paineis_gestor.json. Retorna lista de
    (painel_cfg, qtd_clientes) para o relatorio final.
    """
    paineis_cfg = carregar_ou_criar_paineis_gestor()
    template = env.get_template(TEMPLATE_NAME)
    resultados = []
    for painel in paineis_cfg.get('paineis', []):
        if not painel.get('ativo'):
            continue
        dep = painel['departamento']
        filtrados = [c for c in clientes_resumo if c.get('departamento') == dep]
        dados = montar_dados_painel(
            filtrados, posts_brutos, escritorio,
            cabecalho_titulo=f"Painel do Gestor — {painel['departamento_label']}",
            escopo='gestor',
        )
        html = template.render(**dados)
        pasta = RAIZ / 'clientes' / painel['slug']
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / 'index.html').write_text(html, encoding='utf-8')
        resultados.append((painel, len(filtrados)))
    return resultados


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('Gerador de paineis internos — hub + paineis-gestor (D12)')
    print()

    try:
        clientes_cfg = carregar_clientes_ativos()
    except (OSError, json.JSONDecodeError) as e:
        print(f'ERRO ao ler config/clientes.json: {e}')
        return 1

    if not clientes_cfg:
        print('Nenhum cliente ativo. Paineis nao serao gerados.')
        return 0

    print(f'Clientes ativos: {len(clientes_cfg)}')
    print()

    try:
        escritorio = carregar_escritorio()
    except (OSError, json.JSONDecodeError) as e:
        print(f'ERRO ao ler config/escritorio.json: {e}')
        return 1

    try:
        client = AdvboxClient()
    except AdvboxError as e:
        print(f'ERRO ao inicializar AdvboxClient: {e}')
        return 1

    # Resumo por cliente (cache local; sem refetch no mesmo dia)
    clientes_resumo = []
    for cli_cfg in clientes_cfg:
        try:
            resumo = construir_resumo_cliente(cli_cfg, client)
            clientes_resumo.append(resumo)
            print(
                f'   OK {resumo["nome"]} '
                f'({resumo["qtd_processos"]} processos, '
                f'{resumo["qtd_urgentes"]} criticos, '
                f'{resumo["tarefas_90d"]} tarefas 90d)'
            )
        except AdvboxError as e:
            print(f'   FALHA cliente {cli_cfg["id_advbox"]}: {e}')
        except Exception as e:
            print(f'   FALHA cliente {cli_cfg["id_advbox"]} ({type(e).__name__}): {e}')

    if not clientes_resumo:
        print('Nenhum resumo de cliente gerado. Abortando.')
        return 1

    # Posts brutos globais — baixados UMA vez e reaproveitados por todos os
    # paineis (interno + 4 gestor). Cache TTL 24h via _baixar_posts_paginado.
    print()
    print('Baixando posts globais (atividade 90d)...')
    posts_brutos = _baixar_posts_paginado(client)

    env = construir_jinja_env()

    # 1) Painel-interno (todos os clientes ativos) — comportamento original
    dados_interno = gerar_painel_interno(
        clientes_resumo, posts_brutos, escritorio, env
    )

    # 2) Paineis-gestor (Decisao D12) — um por departamento, filtrados
    resultados_gestor = gerar_paineis_gestor(
        clientes_resumo, posts_brutos, escritorio, env
    )

    # Relatorio
    print()
    print('=' * 64)
    print('PAINEIS GERADOS')
    print('=' * 64)
    print(f'  [interno] {SAIDA_HTML.relative_to(RAIZ)} '
          f'({SAIDA_HTML.stat().st_size / 1024:.1f} KB)')
    print(f'            {SAIDA_HTML_INDEX.relative_to(RAIZ)} — para GitHub Pages')
    print(f'            {dados_interno["kpis"]["total_clientes"]} clientes, '
          f'{dados_interno["kpis"]["total_processos"]} processos, '
          f'{dados_interno["atividade_global"]["total"]} tarefas 90d')
    print()
    soma_gestor = 0
    for painel, qtd in resultados_gestor:
        soma_gestor += qtd
        print(f'  [gestor]  clientes/{painel["slug"]}/index.html')
        print(f'            {painel["departamento_label"]}: {qtd} cliente(s)')
    print()
    total_interno = dados_interno['kpis']['total_clientes']
    print(f'  Soma de clientes nos {len(resultados_gestor)} paineis-gestor: {soma_gestor}')
    print(f'  Total de clientes no painel-interno          : {total_interno}')
    if soma_gestor == total_interno:
        print('  Validacao OK: soma dos gestores == total do interno.')
    else:
        print('  AVISO: soma dos gestores != total do interno '
              '(cliente ativo sem departamento valido?).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
