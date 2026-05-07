"""
Gerador do painel-interno.html — hub do escritorio L Batista.

Diferente de gerador_producao.py:
  - Lista TODOS os clientes ativos do config/clientes.json
  - NAO agrupa por area (visao por cliente)
  - Agrega atividade 90d de todos os clientes (escritorio inteiro)
  - Saida: painel-interno.html na RAIZ do projeto
  - Visualizado APENAS pelos socios — nunca enviado a clientes

Reaproveita helpers de gerador_producao.py:
  - carregar_clientes_ativos, carregar_escritorio
  - mascarar_identification, normalizar_digitos
  - categoria_alerta
  - _baixar_posts_paginado, _categorizar_posts
  - calcular_atividade_90d (cache por cliente, TTL 24h)
  - construir_jinja_env (com filtro rotulo_departamento)
"""

import json
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
TEMPLATE_NAME = 'painel_interno.html'


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


def construir_atividade_global(clientes_resumo, client):
    """Re-categoriza posts globalmente unindo lawsuit_ids de TODOS os clientes."""
    todos_ids = set()
    for c in clientes_resumo:
        todos_ids.update(c.get('lawsuit_ids') or set())

    posts = _baixar_posts_paginado(client)
    limite_90d = datetime.now().date() - timedelta(days=90)
    return _categorizar_posts(posts, todos_ids, limite_90d)


def construir_contexto_global(clientes_resumo, atividade_global, escritorio):
    """KPIs agregados + meta para o template."""
    total_clientes = len(clientes_resumo)
    total_processos = sum(c['qtd_processos'] for c in clientes_resumo)
    total_alertas_criticos = sum(c['qtd_urgentes'] for c in clientes_resumo)
    total_tarefas_90d = sum(c['tarefas_90d'] for c in clientes_resumo)

    counts_por_dep = Counter(c['departamento'] for c in clientes_resumo)
    # Remove keys vazias
    counts_por_dep = {k: v for k, v in counts_por_dep.items() if k}

    return {
        'kpis': {
            'total_clientes': total_clientes,
            'total_processos': total_processos,
            'total_alertas_criticos': total_alertas_criticos,
            'total_tarefas_90d': total_tarefas_90d,
        },
        'atividade_global': atividade_global,
        'counts_por_departamento': counts_por_dep,
        'escritorio': escritorio,
        'data_geracao': datetime.now().strftime('%d/%m/%Y às %H:%M'),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('Gerador do painel interno — hub do escritorio')
    print()

    try:
        clientes_cfg = carregar_clientes_ativos()
    except (OSError, json.JSONDecodeError) as e:
        print(f'ERRO ao ler config/clientes.json: {e}')
        return 1

    if not clientes_cfg:
        print('Nenhum cliente ativo. Painel-interno nao sera gerado.')
        return 0

    print(f'Clientes ativos: {len(clientes_cfg)}')
    for c in clientes_cfg:
        print(f'  - {c["nome_curto"]} (id_advbox={c["id_advbox"]})')
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

    # Resumo por cliente
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

    # Atividade global agregada
    print()
    print('Calculando atividade global agregada...')
    atividade_global = construir_atividade_global(clientes_resumo, client)
    print(
        f'  Atividade global 90d: {atividade_global["total"]} tarefas, '
        f'ultima_data={atividade_global["ultima_data"]}'
    )

    # Contexto Jinja
    contexto = construir_contexto_global(
        clientes_resumo, atividade_global, escritorio
    )
    contexto['clientes'] = clientes_resumo

    # Renderizacao
    env = construir_jinja_env()
    template = env.get_template(TEMPLATE_NAME)
    html = template.render(**contexto)

    # Antes de gravar, remover o campo lawsuit_ids dos resumos (set nao
    # serializa em json e a gente nao precisa no front; ja foi consumido).
    # Isso ja foi consumido em runtime — o template nao usa.

    SAIDA_HTML.write_text(html, encoding='utf-8')

    print()
    print('=' * 64)
    print('PAINEL INTERNO GERADO')
    print('=' * 64)
    print(f'  Arquivo: {SAIDA_HTML.relative_to(RAIZ)}')
    print(f'  Tamanho: {SAIDA_HTML.stat().st_size / 1024:.1f} KB')
    print(f'  Clientes: {len(clientes_resumo)}')
    print(f'  Processos totais: {contexto["kpis"]["total_processos"]}')
    print(f'  Alertas criticos: {contexto["kpis"]["total_alertas_criticos"]}')
    print(f'  Tarefas 90d (soma por cliente): {contexto["kpis"]["total_tarefas_90d"]}')
    print(f'  Tarefas 90d (agregado global): {atividade_global["total"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
