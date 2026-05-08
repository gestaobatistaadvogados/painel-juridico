"""
Gerador de paineis processuais publicos do escritorio L Batista.

Le config/clientes.json e, para cada cliente ATIVO, gera
clientes/{slug_url}/dados.json com os dados publicos filtrados.

ETAPA A: este script grava APENAS JSON. A renderizacao HTML
sera adicionada em Etapa B (apos validacao do JSON).

REGRA CRITICA — separacao publico vs interno:
ver MEMORY.md > "REGRA CRITICA - SEPARACAO DE DADOS".

Endpoints consumidos (apenas estes — whitelist explicita):
  - GET /customers/{id}
  - GET /lawsuits?customer_id={id}
  - GET /movements/{lawsuit_id}

Endpoints PROIBIDOS no painel publico (jamais usados aqui):
  - /history, /posts, qualquer fonte de texto interno da equipe
"""

import hashlib
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


# Fuso fixo para timestamps EXIBIDOS nos paineis (gerado_em, data_geracao
# etc.). Em runners do GitHub Actions, datetime.now() devolve UTC; com
# este fuso o relogio mostrado bate com o relogio do Brasil.
#
# Tentamos `ZoneInfo('America/Sao_Paulo')` primeiro (semantica IANA);
# se a base tzdata nao estiver disponivel (caso comum no Windows sem
# o pacote `tzdata`), caimos em `timezone(timedelta(hours=-3))`. Brasil
# nao usa horario de verao desde 2019, entao UTC-3 fixo e correto o ano
# todo. Sem dependencia nova em requirements.txt.
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        FUSO_BRT = ZoneInfo('America/Sao_Paulo')
    except ZoneInfoNotFoundError:
        FUSO_BRT = timezone(timedelta(hours=-3), name='BRT')
except ImportError:
    FUSO_BRT = timezone(timedelta(hours=-3), name='BRT')

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advbox_client import AdvboxClient, AdvboxError
from cache import cache_get, cache_set
from cnj_decoder import decodificar_tribunal, parse_segmento, area_por_segmento

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


# === CAMINHOS ===
RAIZ = Path(__file__).resolve().parent.parent
CONFIG_CLIENTES = RAIZ / 'config' / 'clientes.json'
CONFIG_ESCRITORIO = RAIZ / 'config' / 'escritorio.json'
CONFIG_AREAS = RAIZ / 'config' / 'areas_direito.json'
LOGO_SRC = RAIZ / 'config' / 'logo.png'
DIR_SAIDA = RAIZ / 'clientes'
DIR_TEMPLATES = RAIZ / 'src' / 'templates'
TEMPLATE_DASHBOARD = 'dashboard.html'


# === WHITELISTS DE CAMPOS PUBLICOS ===
# NAO ALTERAR sem revisao da Regra de Ouro do MEMORY.md.
CAMPOS_CLIENTE_PUBLICOS = ['name', 'identification', 'city', 'state']

CAMPOS_LAWSUIT_PUBLICOS = [
    'id', 'process_number', 'protocol_number', 'folder',
    'stage', 'step', 'type', 'group',
    'status_closure', 'created_at', 'process_date',
    'responsible',
]

CAMPOS_MOVEMENT_PUBLICOS = ['date', 'header', 'title']

# Campos derivados que o gerador adiciona ao processo (alem da whitelist).
# Mantidos como constante para o auditor (auditar_json.py) saber esperar.
CAMPOS_LAWSUIT_DERIVADOS = ['movements', 'partes_adversarias', 'fase_grupo', 'tribunal']

# Whitelist DENTRO de cada item de partes_adversarias.
# Ver MEMORY.md > "REVISAO 2026-05-07 — partes adversarias por NOME sao permitidas".
CAMPOS_PARTE_ADVERSARIA = ['name']

# Whitelist EXATA do bloco atividade_90d (Versao B sanitizada — D4).
# Apenas contagens e a data da ultima atividade. NUNCA texto livre dos posts.
# Categorias COM ACENTO (revisao 2026-05-07 apos auditoria src/auditar_tasks.py):
# - 'Reunioes' renomeada para 'Comunicações' (cobre lembrar/avisar cliente,
#   acoes assincronas e nao reunioes presenciais).
# - 'Despachos' removida (score estrutural zero — vem de /movements).
# - 'Acompanhamento' adicionada (leitura ata, protocolo, ciencia, comentario).
# - 'Diligências' adicionada (notificar testemunhas, pagamento, agendamento).
# - 'Outras' mantida como catch-all implicito (oculto no template quando == 0).
CAMPOS_ATIVIDADE_90D = {'total', 'categorias', 'ultima_data'}
CATEGORIAS_ATIVIDADE_90D = [
    'Peças',
    'Audiências',
    'Comunicações',
    'Acompanhamento',
    'Diligências',
    'Outras',
]

# Limite de produto: dashboard mostra apenas os N andamentos mais recentes
# por processo. Ver MEMORY.md > "DECISAO DE PRODUTO — VISAO DE STATUS".
# Coincidentemente, sempre cabe dentro do teto de 25 da API.
MAX_MOVIMENTOS_POR_LAWSUIT = 10
# Andamentos exibidos no modal de processo (sub-conjunto dos MAX_MOVIMENTOS_POR_LAWSUIT).
MAX_MOVIMENTOS_NO_MODAL = 5

# Limites do template (computados em runtime, nao gravados em dados.json).
MAX_ALERTAS_VISIVEIS_POR_CATEGORIA = 5
MAX_TIMELINE_POR_AREA = 15
MAX_TIPOS_TAG_POR_CARD_AREA = 3
MAX_FATIAS_GRAFICO_BARRAS = 6  # top-N + bucket "Outros"


# === DEFESA EM PROFUNDIDADE ===
# Termos vetados em qualquer chave do JSON final, mesmo apos a whitelist.
# Match e por TOKEN (split em '_'), nao substring, para evitar falsos positivos
# em palavras compostas legitimas (ex: 'postalcode' nao casa com 'post').
TERMOS_PROIBIDOS = {
    'comments', 'comment', 'notes', 'note',
    'observation', 'observations', 'private',
    'internal', 'internal_note',
    'history', 'post', 'posts',
    # Adicionados em 2026-05-07 (DESCOBERTA #7): campos do schema de /posts
    # que NUNCA podem aparecer no JSON publico do cliente.
    'task',         # descricao livre da tarefa interna
    'reward',       # pontuacao interna do funcionario
    'lawsuits_id',  # chave da relacao posts <-> lawsuit (interno)
    'tasks_id',     # id de tarefa interna
}

# Numeros que disparam alerta de possivel truncamento silencioso em /movements.
NUMEROS_REDONDOS_SUSPEITOS = {25, 50, 100, 200, 250, 500, 1000}


# ---------------------------------------------------------------------------
# UTILITARIOS
# ---------------------------------------------------------------------------

def filtrar(dado, whitelist):
    """Devolve novo dict com apenas as chaves da whitelist (preserva None)."""
    if not isinstance(dado, dict):
        return {}
    return {k: dado[k] for k in whitelist if k in dado}


def normalizar_digitos(valor):
    """Mantem apenas digitos de uma string. None -> ''."""
    if valor is None:
        return ''
    return ''.join(c for c in str(valor) if c.isdigit())


def extrair_partes_adversarias(lawsuit_bruto, cliente_ident_digitos):
    """Devolve lista de {'name': ...} dos adversarios do processo.

    Identifica o proprio cliente comparando `identification` (so digitos) —
    e o unico campo confiavel: `customer_id` vem sempre None na API.
    Excluidos: o proprio cliente; itens com `name` vazio.
    Whitelist por item: apenas `name`. Demais campos
    (identification, origin, customer_id) sao descartados.
    """
    adversarios = []
    custs = lawsuit_bruto.get('customers') or []
    for c in custs:
        if not isinstance(c, dict):
            continue
        if normalizar_digitos(c.get('identification')) == cliente_ident_digitos:
            continue  # eh o proprio cliente — nao incluir
        nome = c.get('name') or ''
        if not nome.strip():
            continue  # exclui sem nome (decisao do socio em 2026-05-07)
        # construcao explicita do dict garante whitelist
        adversarios.append({'name': nome})
    return adversarios


def fase_grupo(stage):
    """Mapeia stage textual para um chip de filtro fixo.

    Ver MEMORY.md > "Filtros chips da tabela — fase_grupo".
    Casos nao reconhecidos vao para 'conhecimento' (default).
    """
    s = (stage or '').upper()
    if not s:
        return 'conhecimento'
    if 'ARQUIV' in s or 'ENCERRA' in s or 'TRANSITADO' in s:
        return 'arquivados'
    if 'RECURSO' in s or 'AGRAVO' in s or 'APELACAO' in s or 'TRT' in s or 'TJ' in s:
        return 'recursal'
    if 'EXECUCAO' in s or 'EXECUÇÃO' in s or 'CUMPRIMENTO' in s:
        return 'execucao'
    return 'conhecimento'


def categoria_alerta(processo):
    """Classifica o processo em 'urgente'/'atencao'/'favoravel'/None.

    Ver MEMORY.md > "Alertas — inferencia por stage + status_closure".
    Ordem importa: favoravel > urgente > atencao (status_closure preenchido
    domina; stage urgente vem antes de atencao).
    """
    stage_up = (processo.get('stage') or '').upper()
    fechado = bool(processo.get('status_closure'))
    if fechado or any(k in stage_up for k in ['ARQUIV', 'TRANSITADO', 'ENCERRA']):
        return 'favoravel'
    if any(k in stage_up for k in ['AUDIENCIA', 'AUDIÊNCIA', 'PRAZO', 'URGENTE']):
        return 'urgente'
    if any(k in stage_up for k in ['INSTRUCAO', 'INSTRUÇÃO', 'MANIFESTACAO',
                                    'MANIFESTAÇÃO', 'AGUARDANDO', 'EM CURSO']):
        return 'atencao'
    return None


def slugify_area(nome):
    """Slug ASCII-only para usar em HTML id/data-attr."""
    import unicodedata
    base = unicodedata.normalize('NFKD', str(nome or '')).encode('ascii', 'ignore').decode('ascii')
    base = ''.join(c if c.isalnum() else '-' for c in base.lower())
    base = '-'.join(filter(None, base.split('-')))
    return base or 'sem-area'


def mascarar_identification(ident):
    """Mascara CPF/CNPJ deixando so os 2 ultimos digitos visiveis.

    PJ (14d): **.***.***/****-NN
    PF (11d): ***.***.***-NN
    Outro:   '' (nao tentar mostrar nada se formato e desconhecido)
    """
    digitos = normalizar_digitos(ident)
    if len(digitos) == 14:
        return f'**.***.***/****-{digitos[-2:]}'
    if len(digitos) == 11:
        return f'***.***.***-{digitos[-2:]}'
    return ''


def tipo_identification(ident):
    """Retorna 'PF', 'PJ' ou ''."""
    n = len(normalizar_digitos(ident))
    if n == 14:
        return 'PJ'
    if n == 11:
        return 'PF'
    return ''


class WhitelistError(Exception):
    """Levantada quando um campo proibido vaza para o JSON publico do cliente."""


def assert_sem_termos_proibidos(obj, caminho='root'):
    """Percorre obj recursivamente; falha se alguma chave casar com termos vetados.

    Dois criterios de match para cobrir compostos:
      1. Chave inteira (lowercased) == termo proibido — pega `lawsuits_id`,
         `tasks_id`, `internal_note` como nomes compostos.
      2. Cada token apos split('_') == termo proibido — pega `internal`
         dentro de `internal_note`, `note` dentro de `note_global`, etc.
    Match por substring ainda e EVITADO (assim `postalcode` nao casa com
    `post`).
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in TERMOS_PROIBIDOS:
                raise WhitelistError(
                    f'Defesa em profundidade: chave proibida "{k}" '
                    f'(match exato) encontrada em {caminho}'
                )
            for t in kl.split('_'):
                if t in TERMOS_PROIBIDOS:
                    raise WhitelistError(
                        f'Defesa em profundidade: chave proibida "{k}" '
                        f'(token "{t}") encontrada em {caminho}'
                    )
            assert_sem_termos_proibidos(v, f'{caminho}.{k}')
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            assert_sem_termos_proibidos(item, f'{caminho}[{i}]')


# ---------------------------------------------------------------------------
# COLETA (com cache 24h)
# ---------------------------------------------------------------------------

def coletar_customer(client, customer_id):
    chave = f'customers_{customer_id}'
    dados = cache_get(chave)
    if dados is None:
        dados = client.get_customer(customer_id)
        cache_set(chave, dados)
    return dados


def coletar_lawsuits(client, customer_id):
    chave = f'lawsuits_customer_{customer_id}'
    envelope = cache_get(chave)
    if envelope is None:
        envelope = client.get_lawsuits(customer_id=customer_id, limit=1000, offset=0)
        cache_set(chave, envelope)
    if isinstance(envelope, dict) and isinstance(envelope.get('data'), list):
        return envelope['data']
    return []


def coletar_movements(client, lawsuit_id, avisos):
    chave = f'movements_{lawsuit_id}'
    envelope = cache_get(chave)
    if envelope is None:
        envelope = client.get_movements(lawsuit_id)
        cache_set(chave, envelope)

    if isinstance(envelope, dict) and isinstance(envelope.get('data'), list):
        data = envelope['data']
    else:
        data = []

    if len(data) in NUMEROS_REDONDOS_SUSPEITOS:
        avisos.append(
            f'lawsuit {lawsuit_id}: /movements retornou exatamente {len(data)} '
            f'itens (numero classico de teto silencioso). Investigar truncamento.'
        )
    return data


# ---------------------------------------------------------------------------
# MONTAGEM DOS DADOS PUBLICOS
# ---------------------------------------------------------------------------

def montar_cliente_publico(customer_bruto):
    """Aplica whitelist + mascara identification + adiciona tipo derivado."""
    pub = filtrar(customer_bruto, CAMPOS_CLIENTE_PUBLICOS)
    ident_original = pub.get('identification')
    pub['identification'] = mascarar_identification(ident_original)
    pub['identification_tipo'] = tipo_identification(ident_original)
    return pub


def montar_lawsuit_publico(lawsuit_bruto, movements_brutos, cliente_ident_digitos):
    """Aplica whitelist no processo e nos movements + adiciona derivados publicos.

    Movements sao ordenados por `date` DESC e cortados aos
    MAX_MOVIMENTOS_POR_LAWSUIT mais recentes.

    Derivados adicionados (CAMPOS_LAWSUIT_DERIVADOS):
      - movements          : list filtrada e cortada
      - partes_adversarias : list de {'name': ...} (so name, ver Regra v2)
      - fase_grupo         : str em {'conhecimento','execucao','recursal','arquivados'}
    """
    pub = filtrar(lawsuit_bruto, CAMPOS_LAWSUIT_PUBLICOS)
    movs_filtrados = [filtrar(m, CAMPOS_MOVEMENT_PUBLICOS) for m in movements_brutos]
    movs_ordenados = sorted(
        movs_filtrados,
        key=lambda m: m.get('date') or '',
        reverse=True,
    )
    pub['movements'] = movs_ordenados[:MAX_MOVIMENTOS_POR_LAWSUIT]
    pub['partes_adversarias'] = extrair_partes_adversarias(lawsuit_bruto, cliente_ident_digitos)
    pub['fase_grupo'] = fase_grupo(pub.get('stage'))
    pub['tribunal'] = decodificar_tribunal(pub.get('process_number'))
    return pub


def montar_dados_publicos(cliente_config, customer_bruto, lawsuits_brutos,
                          movements_por_lawsuit):
    """Monta o dict final que vai para dados.json. UNICO objeto que vai a disco.

    Avisos operacionais (truncamento etc.) nao entram no JSON — ficam apenas
    no log de execucao do gerador. JSON e voltado ao cliente.

    `cliente_ident_digitos` e extraido aqui (antes do mascaramento) e usado
    apenas internamente para identificar o proprio cliente no array
    `customers` de cada lawsuit. Nao vai para o JSON.
    """
    agora = datetime.now(FUSO_BRT)
    cliente_ident_digitos = normalizar_digitos(customer_bruto.get('identification'))
    return {
        'meta': {
            'gerado_em': agora.isoformat(timespec='seconds'),
            'gerado_em_humano': agora.strftime('%d/%m/%Y %H:%M'),
            'slug_url': cliente_config['slug_url'],
            'departamento': cliente_config['departamento'],
        },
        'cliente': montar_cliente_publico(customer_bruto),
        'processos': [
            montar_lawsuit_publico(
                law,
                movements_por_lawsuit.get(law.get('id'), []),
                cliente_ident_digitos,
            )
            for law in lawsuits_brutos
        ],
    }


# ---------------------------------------------------------------------------
# JINJA / RENDER HTML
# ---------------------------------------------------------------------------

def filtro_format_date(valor):
    """Formata YYYY-MM-DD ou ISO datetime como DD/MM/YYYY. Vazio -> '—'."""
    if not valor:
        return '—'
    s = str(valor)
    try:
        dt = datetime.fromisoformat(s) if 'T' in s else datetime.strptime(s, '%Y-%m-%d')
        return dt.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return s


def filtro_stage_color_index(stage):
    """Mapeia uma fase para 'c0'..'c7' deterministicamente (mesma fase, mesma cor)."""
    if not stage:
        return 'c7'
    h = hashlib.md5(str(stage).encode('utf-8')).digest()
    return f'c{h[0] % 8}'


_ROTULOS_DEPARTAMENTO = {
    'direito_privado': 'Direito Privado',
    'direito_imobiliario': 'Direito Imobiliário',
    'direito_publico': 'Direito Público',
}


def filtro_rotulo_departamento(slug):
    """Mapeia slug interno do departamento para nome de exibicao em PT-BR."""
    if not slug:
        return 'Geral'
    return _ROTULOS_DEPARTAMENTO.get(str(slug), str(slug).replace('_', ' ').title())


def construir_jinja_env():
    env = Environment(
        loader=FileSystemLoader(str(DIR_TEMPLATES)),
        autoescape=select_autoescape(['html', 'xml']),
    )
    env.filters['format_date'] = filtro_format_date
    env.filters['stage_color_index'] = filtro_stage_color_index
    env.filters['rotulo_departamento'] = filtro_rotulo_departamento
    return env


def calcular_kpis(processos):
    """KPIs globais do cliente (4 indicadores)."""
    total = len(processos)
    em_andamento = sum(1 for p in processos if not p.get('status_closure'))
    aguardando_audiencia = sum(
        1 for p in processos
        if (p.get('stage') or '').upper().find('AUDI') >= 0 and not p.get('status_closure')
    )
    return {
        'total': total,
        'em_andamento': em_andamento,
        'aguardando_audiencia': aguardando_audiencia,
        'encerrados': total - em_andamento,
    }


def calcular_kpis_area(processos):
    """Mesmos KPIs mas restritos aos processos da area."""
    return calcular_kpis(processos)


def calcular_alertas_area(processos):
    """Devolve dict {urgente: {visiveis, restantes}, atencao: ..., favoravel: ...}.

    Cada item visivel tem {id, process_number, type, stage}. Limite por
    categoria: MAX_ALERTAS_VISIVEIS_POR_CATEGORIA.
    """
    buckets = {'urgente': [], 'atencao': [], 'favoravel': []}
    for p in processos:
        cat = categoria_alerta(p)
        if cat in buckets:
            buckets[cat].append({
                'id': p.get('id'),
                'process_number': p.get('process_number') or '',
                'type': p.get('type') or '',
                'stage': p.get('stage') or '',
            })
    resultado = {}
    for cat, itens in buckets.items():
        resultado[cat] = {
            'visiveis': itens[:MAX_ALERTAS_VISIVEIS_POR_CATEGORIA],
            'restantes': max(0, len(itens) - MAX_ALERTAS_VISIVEIS_POR_CATEGORIA),
            'total': len(itens),
        }
    return resultado


def calcular_timeline_area(processos):
    """Junta movements de todos os processos da area, ordena DESC, corta em N.

    Cada item: {date, header, title, process_number}.
    """
    eventos = []
    for p in processos:
        pn = p.get('process_number') or ''
        for m in (p.get('movements') or []):
            eventos.append({
                'date': m.get('date') or '',
                'header': m.get('header') or '',
                'title': m.get('title') or '',
                'process_number': pn,
            })
    eventos.sort(key=lambda e: e['date'], reverse=True)
    return eventos[:MAX_TIMELINE_POR_AREA]


# Cores estaveis para o donut por fase_grupo. Mantidas em sintonia com
# os badges da tabela (paleta da Fase 1 mock validada pelo socio).
CORES_FASE_GRUPO = {
    'conhecimento': '#2874a6',
    'execucao':     '#d68910',
    'recursal':     '#884ea0',
    'arquivados':   '#6c3483',
}


def calcular_donut_area(processos):
    """Pre-computa fatias de um donut SVG por fase_grupo.

    Retorna dict com slices ja calculados (arc, rest, offset) para o template
    so consumir diretamente no SVG (sem JS de chart externo).
    """
    import math
    from collections import Counter

    cont = Counter(p.get('fase_grupo') or 'conhecimento' for p in processos)
    total = sum(cont.values()) or 1
    raio = 40
    circ = 2 * math.pi * raio

    slices = []
    acumulado = 0.0
    for fg, n in cont.most_common():
        frac = n / total
        arc = frac * circ
        slices.append({
            'fase_grupo': fg,
            'count': n,
            'percent': round(100 * frac, 1),
            'cor': CORES_FASE_GRUPO.get(fg, '#9ca3af'),
            'arc': round(arc, 3),
            'rest': round(circ - arc, 3),
            'offset': round(-acumulado, 3),
        })
        acumulado += arc

    return {
        'slices': slices,
        'total': total,
        'raio': raio,
        'circ': round(circ, 3),
    }


def calcular_top_tipos_area(processos):
    """Top N tipos (acoes) mais frequentes da area, para tags do card-area."""
    from collections import Counter
    cont = Counter((p.get('type') or '').strip() for p in processos if p.get('type'))
    return [t for t, _ in cont.most_common(MAX_TIPOS_TAG_POR_CARD_AREA)]


# Paleta para os 4 graficos por area. Tons quentes/dourados para combinar
# com a identidade visual; vermelho-vinho reservado para fases sensiveis.
PALETA_GRAFICOS = [
    '#0A1628',  # azul-marinho primario
    '#C9A84C',  # dourado
    '#2874a6',  # azul medio
    '#8B4513',  # marrom-vinho
    '#1F6E5C',  # verde profundo
    '#8B6F47',  # ocre
    '#5D3A8A',  # roxo discreto
    '#9ca3af',  # cinza (default/Outros)
]


def _agregar_top_n(contador, max_fatias):
    """Recebe Counter e retorna (labels, data) com top-N + bucket 'Outros'."""
    if not contador:
        return [], []
    items = contador.most_common()
    if len(items) <= max_fatias:
        labels = [k for k, _ in items]
        data = [v for _, v in items]
        return labels, data
    top = items[:max_fatias - 1]
    resto = sum(v for _, v in items[max_fatias - 1:])
    labels = [k for k, _ in top] + ['Outros']
    data = [v for _, v in top] + [resto]
    return labels, data


def calcular_charts_area(processos):
    """Pre-computa dados dos 4 graficos por area, em formato Chart.js-friendly.

    Retorna dict:
      {
        'fase':      {labels, data, colors},   # donut por fase_grupo
        'tribunal':  {labels, data},            # barras horizontais
        'tipo_acao': {labels, data},            # barras horizontais
        'status':    {labels, data, colors},    # donut binario ativos vs arquivados
      }
    """
    from collections import Counter

    # 1. Por fase (donut)
    cont_fase = Counter((p.get('fase_grupo') or 'conhecimento') for p in processos)
    fase_ordem = ['conhecimento', 'execucao', 'recursal', 'arquivados']
    cores_fase = {
        'conhecimento': CORES_FASE_GRUPO['conhecimento'],
        'execucao':     CORES_FASE_GRUPO['execucao'],
        'recursal':     CORES_FASE_GRUPO['recursal'],
        'arquivados':   CORES_FASE_GRUPO['arquivados'],
    }
    nomes_legiveis = {
        'conhecimento': 'Conhecimento',
        'execucao': 'Execução',
        'recursal': 'Recursal',
        'arquivados': 'Arquivados',
    }
    fase_labels = [nomes_legiveis[k] for k in fase_ordem if cont_fase.get(k, 0) > 0]
    fase_data = [cont_fase[k] for k in fase_ordem if cont_fase.get(k, 0) > 0]
    fase_colors = [cores_fase[k] for k in fase_ordem if cont_fase.get(k, 0) > 0]

    # 2. Por tribunal (barras)
    cont_trib = Counter((p.get('tribunal') or '—') for p in processos)
    trib_labels, trib_data = _agregar_top_n(cont_trib, MAX_FATIAS_GRAFICO_BARRAS)

    # 3. Por tipo de acao (barras)
    cont_tipo = Counter(
        ((p.get('type') or '').strip().title() or 'Sem tipo')
        for p in processos
    )
    tipo_labels, tipo_data = _agregar_top_n(cont_tipo, MAX_FATIAS_GRAFICO_BARRAS)

    # 4. Status processual (donut binario)
    ativos = sum(1 for p in processos if not p.get('status_closure'))
    arquivados = len(processos) - ativos
    status_labels = ['Ativos', 'Arquivados']
    status_data = [ativos, arquivados]
    status_colors = ['#C9A84C', '#9ca3af']

    return {
        'fase': {
            'labels': fase_labels,
            'data': fase_data,
            'colors': fase_colors,
        },
        'tribunal': {
            'labels': trib_labels,
            'data': trib_data,
        },
        'tipo_acao': {
            'labels': tipo_labels,
            'data': tipo_data,
        },
        'status': {
            'labels': status_labels,
            'data': status_data,
            'colors': status_colors,
        },
    }


# ---------------------------------------------------------------------------
# Atividade 90 dias (Versao B sanitizada — D4)
# ---------------------------------------------------------------------------

def classificar_task(task_str):
    """Mapeia o campo `task` da API para uma das 5 categorias do bloco 90d.

    Chaves de busca em lower(task), tudo case-insensitive e tolerante a
    acentos (a API ADVBox pode entregar com ou sem). Default 'Outras'.
    """
    s = (task_str or '').lower()
    if not s:
        return 'Outras'
    if any(k in s for k in ('peticao', 'petição', 'manifesta', 'contesta',
                             'recurso', 'embargos', 'agravo')):
        return 'Peças'
    if any(k in s for k in ('audien', 'sessao', 'sessão')):
        return 'Audiências'
    if any(k in s for k in ('reuniao', 'reunião', 'atendimento')):
        return 'Reuniões'
    if any(k in s for k in ('despacho', 'decisao', 'decisão',
                             'sentenca', 'sentença')):
        return 'Despachos'
    return 'Outras'


def _baixar_posts_paginado(client, max_pages=50, per_page=100):
    """Pagina /posts globalmente e devolve a lista crua de dicts.

    Usa cache compartilhado `posts_brutos_global` (TTL 24h via cache_set).
    Importante para evitar 25 chamadas duplicadas quando gerador_producao
    e gerador_interno rodam no mesmo dia.

    SIGILO: o cache contem texto livre (notes, task, users) e NUNCA pode
    ser exposto no painel publico. .gitignore ja cobre cache/.
    """
    cached = cache_get('posts_brutos_global')
    if cached is not None and isinstance(cached, list):
        return cached

    posts = []
    offset = 0
    paginas = 0
    try:
        for _ in range(max_pages):
            resp = client._request(
                'posts',
                params={'limit': per_page, 'offset': offset},
            )
            paginas += 1
            if not isinstance(resp, dict):
                break
            data = resp.get('data') or []
            if not isinstance(data, list) or not data:
                break
            posts.extend(data)
            if len(data) < per_page:
                break
            offset += per_page
            total_count = resp.get('totalCount')
            if total_count and offset >= total_count:
                break
    except AdvboxError as e:
        print(f'   AVISO: /posts falhou no offset {offset}: {e}')
        # devolve o que ja temos; nao cacheia para tentar de novo na proxima

    print(f'   /posts paginado: {paginas} pagina(s), {len(posts)} posts brutos.')
    if posts:
        cache_set('posts_brutos_global', posts)
    return posts


def _categorizar_posts(posts_brutos, ids_validos, limite_data):
    """Filtra + categoriza posts. Retorna dict {total, categorias, ultima_data}.

    Args:
        posts_brutos (list[dict]): posts crus da API ADVBox.
        ids_validos (set[int]): lawsuit_ids permitidos. Posts fora deste
            conjunto sao descartados (filtro local — necessario porque
            `?customer_id=` em /posts e silenciosamente ignorado).
        limite_data (date): janela 90d. Posts com `created_at` anterior
            a esta data sao descartados.

    NUNCA retorna texto livre — apenas contagens agregadas.
    """
    from datetime import datetime

    contagens = {cat: 0 for cat in CATEGORIAS_ATIVIDADE_90D}
    ultima_data_obj = None

    for post in posts_brutos:
        if not isinstance(post, dict):
            continue
        lid = post.get('lawsuits_id')
        if lid is None:
            continue
        try:
            lid_int = int(lid)
        except (ValueError, TypeError):
            continue
        if lid_int not in ids_validos:
            continue

        created = post.get('created_at')
        if not created:
            continue
        try:
            dt = datetime.strptime(str(created)[:10], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            continue
        if dt < limite_data:
            continue

        if ultima_data_obj is None or dt > ultima_data_obj:
            ultima_data_obj = dt

        task_lower = (post.get('task') or '').lower()
        # AUDIENCIAS — checar PRIMEIRO. Variantes COM e SEM acento
        # porque 'audien' nao casa com 'audiência' (o ê quebra a sequencia).
        if any(kw in task_lower for kw in
               ('audien', 'audiên',
                'audiencia', 'audiência',
                'sessao', 'sessão')):
            contagens['Audiências'] += 1
        elif any(kw in task_lower for kw in
                 ('avisar cliente', 'lembrar cliente',
                  'avisar o cliente', 'lembrar o cliente',
                  'comunicar cliente', 'comunicar o cliente',
                  'reuniao', 'reunião', 'atendimento')):
            contagens['Comunicações'] += 1
        elif any(kw in task_lower for kw in
                 ('leitura', 'leitura da ata', 'ler ata',
                  'verificar protocolo', 'protocolo',
                  'ciencia', 'ciência',
                  'comentario', 'comentário',
                  'acompanhamento', 'acompanhar')):
            contagens['Acompanhamento'] += 1
        elif any(kw in task_lower for kw in
                 ('notificar testemunha', 'testemunha',
                  'pagamento',
                  'agendamento', 'agendar',
                  'diligencia', 'diligência')):
            contagens['Diligências'] += 1
        elif any(kw in task_lower for kw in
                 ('peticao', 'petição', 'petic',
                  'manifesta', 'contesta', 'recurso',
                  'embargos', 'agravo',
                  'apelacao', 'apelação',
                  'impugna', 'memoriais',
                  'alegacoes', 'alegações',
                  'contrarrazoes', 'contrarrazões',
                  'juntar', 'juntada',
                  'rol de testemunha',
                  'carta de preposicao', 'carta de preposição',
                  'especificar provas',
                  'especificacao de provas',
                  'relatorio processual', 'relatório processual',
                  'acordo trabalhista', 'acordo extrajudicial',
                  'acordo')):
            contagens['Peças'] += 1
        else:
            contagens['Outras'] += 1

    return {
        'total': sum(contagens.values()),
        'categorias': contagens,
        'ultima_data': ultima_data_obj.isoformat() if ultima_data_obj else None,
    }


def calcular_atividade_90d(cliente_id_advbox, lawsuit_ids_do_cliente, client):
    """Bloco 90 dias — fonte: GET /posts paginado + filtro local.

    Ver MEMORY.md > "DESCOBERTA #7 — /posts e ESCOPO DO TOKEN ADVBOX".

    Args:
        cliente_id_advbox (int): id do cliente — usado para a key de cache
            (`posts_customer_<id>`).
        lawsuit_ids_do_cliente (Iterable[int]): ids dos lawsuits do cliente.
            Filtra localmente os posts cujo `lawsuits_id` cai nesse conjunto.
        client (AdvboxClient): cliente HTTP ja autenticado.

    Returns:
        dict com 3 chaves: total, categorias, ultima_data.
        Validado por assert_atividade_90d_estruturada.
    """
    from datetime import datetime, timedelta

    cache_key = f'posts_customer_{cliente_id_advbox}'
    cached = cache_get(cache_key)
    if cached is not None and isinstance(cached, dict) \
            and all(k in cached for k in ('total', 'categorias', 'ultima_data')):
        return cached

    posts = _baixar_posts_paginado(client)
    limite_90d = datetime.now().date() - timedelta(days=90)
    ids_validos = set(int(x) for x in lawsuit_ids_do_cliente if x is not None)
    resultado = _categorizar_posts(posts, ids_validos, limite_90d)

    print(
        f'   atividade_90d (cliente {cliente_id_advbox}): '
        f'{len(posts)} posts examinados, '
        f'{resultado["total"]} categorizados na janela 90d.'
    )

    assert_atividade_90d_estruturada(resultado)
    cache_set(cache_key, resultado)
    return resultado


def assert_atividade_90d_estruturada(d):
    """Defesa em profundidade — garante schema fixo do bloco 90d.

    Chaves permitidas: 'total','categorias','ultima_data'.
    Categorias permitidas: CATEGORIAS_ATIVIDADE_90D.
    Tipos: total int, categorias[*] int, ultima_data str ou None.
    """
    CHAVES_PERMITIDAS = CAMPOS_ATIVIDADE_90D
    CATEGORIAS_PERMITIDAS = set(CATEGORIAS_ATIVIDADE_90D)

    if not isinstance(d, dict):
        raise WhitelistError(
            f'atividade_90d deve ser dict, recebido {type(d).__name__}'
        )
    chaves = set(d.keys())
    extras = chaves - CHAVES_PERMITIDAS
    if extras:
        raise WhitelistError(
            f'atividade_90d tem chaves nao permitidas: {sorted(extras)}'
        )
    if 'total' not in d or not isinstance(d['total'], int):
        raise WhitelistError('atividade_90d.total deve ser int')
    if 'categorias' not in d or not isinstance(d['categorias'], dict):
        raise WhitelistError('atividade_90d.categorias deve ser dict')
    cat_extras = set(d['categorias'].keys()) - CATEGORIAS_PERMITIDAS
    if cat_extras:
        raise WhitelistError(
            f'atividade_90d.categorias tem chaves nao permitidas: {sorted(cat_extras)}'
        )
    for k, v in d['categorias'].items():
        if not isinstance(v, int):
            raise WhitelistError(
                f'atividade_90d.categorias.{k} deve ser int, '
                f'recebido {type(v).__name__}'
            )
    if 'ultima_data' not in d:
        raise WhitelistError('atividade_90d.ultima_data ausente')
    if d['ultima_data'] is not None and not isinstance(d['ultima_data'], str):
        raise WhitelistError(
            f'atividade_90d.ultima_data deve ser str ou None, '
            f'recebido {type(d["ultima_data"]).__name__}'
        )


def agrupar_em_areas(processos):
    """Agrupa processos por `group` da API normalizado via MAPEAMENTO_AREAS.

    Retorna lista ordenada (descendente por contagem) de dicts:
      {slug, nome_exibicao, icone_id, total, qtd_processos, qtd_ativos,
       qtd_arquivados, urgentes, atencao_count, processos, kpis,
       alertas, donut, charts, timeline, top_tipos}
    """
    bucket = {}
    for p in processos:
        # Caminho C hibrido: CNJ J vence quando inequivoco; group e fallback.
        nome = determinar_area_lawsuit(p)
        slug = slugify_area(nome)
        if slug not in bucket:
            bucket[slug] = {
                'slug': slug,
                'nome_exibicao': nome,
                'icone_id': icone_id_de_area(nome),
                'processos': [],
            }
        bucket[slug]['processos'].append(p)

    areas = sorted(bucket.values(), key=lambda a: -len(a['processos']))
    for a in areas:
        procs = a['processos']
        a['total'] = len(procs)
        a['qtd_processos'] = len(procs)
        a['qtd_ativos'] = sum(1 for p in procs if not p.get('status_closure'))
        a['qtd_arquivados'] = a['total'] - a['qtd_ativos']
        a['kpis'] = calcular_kpis_area(procs)
        a['alertas'] = calcular_alertas_area(procs)
        a['urgentes'] = a['alertas']['urgente']['total']
        a['atencao_count'] = a['alertas']['atencao']['total']
        a['charts'] = calcular_charts_area(procs)  # Chart.js: fase/tribunal/tipo_acao/status
        a['timeline'] = calcular_timeline_area(procs)
        a['top_tipos'] = calcular_top_tipos_area(procs)
    return areas


def listar_fases(processos):
    return sorted({p['stage'] for p in processos if p.get('stage')})


def carregar_escritorio():
    with CONFIG_ESCRITORIO.open('r', encoding='utf-8') as f:
        return json.load(f)


def carregar_mapeamento_areas():
    """Le config/areas_direito.json. Retorna (mapeamento, icones_svg)."""
    with CONFIG_AREAS.open('r', encoding='utf-8') as f:
        dados = json.load(f)
    return dados.get('mapeamento', {}), dados.get('icones_svg', {})


# Carregado uma vez na importacao do modulo. O gerador roda como processo
# unico — recarregar a cada cliente seria desperdicio.
MAPEAMENTO_AREAS, ICONES_AREAS = carregar_mapeamento_areas()


def normalizar_nome_area(group_raw):
    """Mapeia o `group` cru da API ADVBox para nome legivel em PT-BR.

    Se a chave nao estiver no mapeamento, retorna o valor original
    com .capitalize() (em vez do "Outros" generico anterior).
    """
    if not group_raw:
        return 'Outros'
    bruto = str(group_raw).strip()
    if not bruto:
        return 'Outros'
    if bruto in MAPEAMENTO_AREAS:
        return MAPEAMENTO_AREAS[bruto]
    return bruto.capitalize()


def icone_id_de_area(nome_exibicao):
    """Lookup do identificador do SVG inline para o nome da area."""
    return ICONES_AREAS.get(nome_exibicao) or ICONES_AREAS.get('_default') or 'pasta'


def determinar_area_lawsuit(processo):
    """Caminho C HIBRIDO (Forte): CNJ vence quando inequivoco; group e fallback.

    Logica:
      1. Parsear J do CNJ. Se area_por_segmento(J) retorna chave canonica
         (J=2/4/5/6/7/9), usa essa chave — CNJ e fonte autoritativa.
      2. Se J e ambigua (J=1/3/8) ou CNJ invalido, usa o `group` cru do ADVBox.
      3. Se group tambem ausente, classifica como 'Outras'.

    Motivacao: 101 de 104 processos trabalhistas (J=5) do piloto-pj estao
    cadastrados com group=PRIVADO no ADVBox por heranca de migracao Lises.
    Confiar so no group leva a erro grosseiro. CNJ e padrao oficial e mais
    confiavel para distinguir esfera (Trabalhista, Federal, Eleitoral, Militar).
    Para Justica Estadual (J=8), o `group` ainda e necessario porque distingue
    Civel/Familia/Empresarial dentro do mesmo segmento.
    """
    chave_canonica = area_por_segmento(parse_segmento(processo.get('process_number')))
    if chave_canonica is not None:
        # CNJ disse algo inequivoco
        return MAPEAMENTO_AREAS.get(chave_canonica) or normalizar_nome_area(chave_canonica)
    # Fallback: group do ADVBox
    return normalizar_nome_area(processo.get('group'))


# ---------------------------------------------------------------------------
# PERSISTENCIA DA SAIDA
# ---------------------------------------------------------------------------

def gravar_dados_json(dados_publicos_cliente, slug_url):
    """Cria clientes/{slug}/ se nao existir e grava dados.json."""
    pasta = DIR_SAIDA / slug_url
    pasta.mkdir(parents=True, exist_ok=True)
    saida = pasta / 'dados.json'
    with saida.open('w', encoding='utf-8') as f:
        json.dump(dados_publicos_cliente, f, ensure_ascii=False, indent=2)
    return saida


def montar_dados_processos_modal(processos, cliente_nome):
    """Monta dict {id_string: dados_para_modal} consumido pelo JS.

    Cada entrada tem APENAS campos publicos ja existentes — nada novo,
    apenas reorganizados para acesso O(1) no front.
    """
    dados = {}
    for p in processos:
        pid = p.get('id')
        if pid is None:
            continue
        movs_top5 = (p.get('movements') or [])[:MAX_MOVIMENTOS_NO_MODAL]
        dados[str(pid)] = {
            'process_number': p.get('process_number') or '—',
            'tribunal': p.get('tribunal') or '—',
            'type': p.get('type') or '—',
            'stage': p.get('stage') or '—',
            'fase_grupo': p.get('fase_grupo') or 'conhecimento',
            'process_date': p.get('process_date'),
            'created_at': p.get('created_at'),
            'responsible': p.get('responsible') or '—',
            'folder': p.get('folder') or '',
            'status_closure': p.get('status_closure') or '',
            'cliente_name': cliente_nome,
            'partes_adversarias': [a.get('name', '') for a in (p.get('partes_adversarias') or [])],
            'movements_top5': movs_top5,
        }
    return dados


def renderizar_html(env, dados_publicos_cliente, escritorio, atividade_90d, slug_url):
    """Renderiza o template Jinja2 com os dados publicos e grava em index.html.

    Areas, alertas, donut, timeline e charts sao computados em runtime
    aqui — nao entram no dados.json (que continua focado em dados crus
    filtrados). atividade_90d ja vem montado e validado em gerar_para.
    """
    template = env.get_template(TEMPLATE_DASHBOARD)
    processos = dados_publicos_cliente['processos']
    cliente = dados_publicos_cliente['cliente']
    areas = agrupar_em_areas(processos)
    dados_processos_modal = montar_dados_processos_modal(processos, cliente.get('name', ''))

    kpis_globais = calcular_kpis(processos)
    total_ativos = kpis_globais['em_andamento']

    html = template.render(
        meta=dados_publicos_cliente['meta'],
        cliente=cliente,
        processos=processos,
        areas=areas,
        escritorio=escritorio,
        kpis=kpis_globais,
        atividade_90d=atividade_90d,
        dados_processos_modal=dados_processos_modal,
        total_ativos=total_ativos,
        MAX_TIMELINE=MAX_TIMELINE_POR_AREA,
    )
    pasta = DIR_SAIDA / slug_url
    pasta.mkdir(parents=True, exist_ok=True)
    saida = pasta / 'index.html'
    saida.write_text(html, encoding='utf-8')
    return saida


def copiar_logo(slug_url):
    """Copia config/logo.png para clientes/{slug}/logo.png (caminho relativo no HTML)."""
    pasta = DIR_SAIDA / slug_url
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / 'logo.png'
    if LOGO_SRC.exists():
        shutil.copy2(LOGO_SRC, destino)
        return destino
    return None


# ---------------------------------------------------------------------------
# PIPELINE DE 1 CLIENTE
# ---------------------------------------------------------------------------

def gerar_para(cliente_config, client, jinja_env, escritorio):
    """Pipeline completo de UM cliente.

    Retorna (ok, mensagem, avisos, caminhos) onde caminhos e dict
    {'json': Path, 'html': Path, 'logo': Path|None}.
    """
    customer_id = cliente_config['id_advbox']
    slug = cliente_config['slug_url']
    avisos = []

    customer_bruto = coletar_customer(client, customer_id)
    lawsuits_brutos = coletar_lawsuits(client, customer_id)

    movements_por_lawsuit = {}
    for law in lawsuits_brutos:
        lid = law.get('id')
        if lid is None:
            continue
        movements_por_lawsuit[lid] = coletar_movements(client, lid, avisos)

    dados_publicos_cliente = montar_dados_publicos(
        cliente_config, customer_bruto, lawsuits_brutos,
        movements_por_lawsuit,
    )

    # Bloco 90 dias (Versao B sanitizada — DESCOBERTA #7).
    # Pagina /posts globalmente e filtra localmente por lawsuits_id ∈
    # ids dos lawsuits do cliente. Computado ANTES da defesa em
    # profundidade para que tambem seja varrido pelo assert.
    lawsuit_ids = [law.get('id') for law in lawsuits_brutos if law.get('id') is not None]
    atividade_90d = calcular_atividade_90d(customer_id, lawsuit_ids, client)
    assert_atividade_90d_estruturada(atividade_90d)
    dados_publicos_cliente['atividade_90d'] = atividade_90d

    # Defesa em profundidade: revalida o dict final (incluindo atividade_90d)
    # antes de gravar.
    assert_sem_termos_proibidos(dados_publicos_cliente)

    caminho_json = gravar_dados_json(dados_publicos_cliente, slug)
    caminho_html = renderizar_html(
        jinja_env, dados_publicos_cliente, escritorio, atividade_90d, slug
    )
    caminho_logo = copiar_logo(slug)

    qtd_proc = len(dados_publicos_cliente['processos'])
    qtd_movs = sum(len(p['movements']) for p in dados_publicos_cliente['processos'])
    msg = f'{qtd_proc} processos, {qtd_movs} movimentos'
    caminhos = {'json': caminho_json, 'html': caminho_html, 'logo': caminho_logo}
    return True, msg, avisos, caminhos


# ---------------------------------------------------------------------------
# CARGA DE CONFIGURACAO E LOOP PRINCIPAL
# ---------------------------------------------------------------------------

def carregar_clientes_ativos():
    with CONFIG_CLIENTES.open('r', encoding='utf-8') as f:
        cfg = json.load(f)
    return [c for c in cfg.get('clientes', []) if c.get('ativo')]


def imprimir_relatorio(relatorio, total_avisos):
    print()
    print('=' * 64)
    print('RELATORIO FINAL')
    print('=' * 64)
    print(f'  Sucesso : {len(relatorio["ok"])} cliente(s)')
    for nome, msg, caminhos in relatorio['ok']:
        html_rel = caminhos['html'].relative_to(RAIZ)
        json_rel = caminhos['json'].relative_to(RAIZ)
        print(f'    [OK]  {nome:<20} {msg}')
        print(f'           html: {html_rel}')
        print(f'           json: {json_rel}')
        if caminhos.get('logo'):
            print(f'           logo: {caminhos["logo"].relative_to(RAIZ)}')
    print(f'  Falha   : {len(relatorio["falha"])} cliente(s)')
    for nome, msg in relatorio['falha']:
        print(f'    [ERR] {nome:<20} {msg}')
    if total_avisos:
        print()
        print(f'  Avisos coletados durante a execucao: {total_avisos}')
        for nome, aviso in relatorio['avisos']:
            print(f'    ! {nome}: {aviso}')


def main():
    print('Gerador de paineis publicos — Etapa A (saida JSON)')
    print(f'Config: {CONFIG_CLIENTES.relative_to(RAIZ)}')
    print()

    try:
        clientes = carregar_clientes_ativos()
    except (json.JSONDecodeError, OSError) as e:
        print(f'ERRO ao ler {CONFIG_CLIENTES}: {e}')
        return 1

    if not clientes:
        print('Nenhum cliente ativo em config/clientes.json. Nada a gerar.')
        return 0

    print(f'Clientes ativos a processar: {len(clientes)}')
    for c in clientes:
        print(f'  - {c["nome_curto"]} (id_advbox={c["id_advbox"]}, slug={c["slug_url"]})')
    print()

    try:
        client = AdvboxClient()
    except AdvboxError as e:
        print(f'ERRO ao inicializar AdvboxClient: {e}')
        return 1

    try:
        escritorio = carregar_escritorio()
    except (OSError, json.JSONDecodeError) as e:
        print(f'ERRO ao ler {CONFIG_ESCRITORIO}: {e}')
        return 1
    jinja_env = construir_jinja_env()

    relatorio = {'ok': [], 'falha': [], 'avisos': []}

    for cliente_config in clientes:
        nome = cliente_config['nome_curto']
        print(f'>> Processando: {nome} (id_advbox={cliente_config["id_advbox"]})')
        try:
            ok, msg, avisos, caminhos = gerar_para(cliente_config, client, jinja_env, escritorio)
        except WhitelistError as e:
            print(f'   FALHA (defesa em profundidade): {e}')
            relatorio['falha'].append((nome, f'whitelist: {e}'))
            continue
        except AdvboxError as e:
            print(f'   FALHA (API): {e}')
            relatorio['falha'].append((nome, f'API: {e}'))
            continue
        except (OSError, json.JSONDecodeError) as e:
            print(f'   FALHA (I/O): {e}')
            relatorio['falha'].append((nome, f'I/O: {e}'))
            continue

        relatorio['ok'].append((nome, msg, caminhos))
        for a in avisos:
            relatorio['avisos'].append((nome, a))
        print(f'   OK: {msg}')
        print(f'   html : {caminhos["html"].relative_to(RAIZ)}')
        print(f'   json : {caminhos["json"].relative_to(RAIZ)}')
        if caminhos.get('logo'):
            print(f'   logo : {caminhos["logo"].relative_to(RAIZ)}')
        if avisos:
            for a in avisos:
                print(f'   AVISO: {a}')

    imprimir_relatorio(relatorio, sum(1 for _ in relatorio['avisos']))

    return 0 if not relatorio['falha'] else 2


if __name__ == '__main__':
    sys.exit(main())
