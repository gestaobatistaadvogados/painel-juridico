"""
Script gerador de dashboards (Etapa 3.3 — Completa)
Componentes:
- Cards de área refinados (ícone circular, tags, "explorar painel →")
- 5 KPIs por área
- Painel de alertas com descrições contextuais (prazos, bloqueios, andamentos)
- 4 gráficos: Fase, Tribunal, Tipo de Ação, Status
- Timeline com selo "PRAZO FUTURO" e CNJ em monoespaçada
- Tabela completa com busca, filtros, ordenação
- Modal de detalhes para cada processo
"""

import base64
import html as html_lib
import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


RAIZ = Path(__file__).parent.parent
CAMINHO_CONFIG = RAIZ / 'config'
CAMINHO_MOCK = RAIZ / 'mock_data'
CAMINHO_TEMPLATE = RAIZ / 'src' / 'templates'
CAMINHO_SAIDA = RAIZ / 'clientes'


# ============================================================
# ÍCONES SVG (14 áreas + fallback)
# ============================================================
ICONES_SVG = {
    'predio_publico': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18M5 21V10M19 21V10M3 10h18M3 10l9-7 9 7M9 14v4M12 14v4M15 14v4"/></svg>''',
    'folha': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19.2 2.8c.62 4.7.4 7.9-1 11.2-1.5 3.6-4.6 6-7.2 6z"/><path d="M2 21c0-3 1.85-5.36 5.08-6"/></svg>''',
    'balanca': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M16 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1zM2 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1zM7 21h10M12 3v18M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>''',
    'constituicao': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="14" y2="11"/></svg>''',
    'etiqueta': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>''',
    'escudo': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>''',
    'urna': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="6" width="16" height="14" rx="1"/><path d="M9 6V4a3 3 0 0 1 3-3h0a3 3 0 0 1 3 3v2"/><line x1="9" y1="11" x2="15" y2="11"/></svg>''',
    'maleta': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>''',
    'familia': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>''',
    'casa': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>''',
    'documento_martelo': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="14" x2="13" y2="18"/><line x1="15" y1="14" x2="11" y2="18"/></svg>''',
    'calendario': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>''',
    'ferramenta': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-6 6a1 1 0 0 0 1.4 1.4l6-6a4 4 0 0 0 5.4-5.4z"/><path d="M14.7 6.3l3 3"/></svg>''',
    'documento_fiscal': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>''',
    'documento_generico': '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>''',
}


# ============================================================
# UTILITÁRIOS GERAIS
# ============================================================
def carregar_json(caminho):
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)


def carregar_logo_base64(caminho_logo):
    if not caminho_logo.exists():
        return None
    with open(caminho_logo, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def normalizar_texto(texto):
    if not texto:
        return ''
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join([c for c in nfkd if not unicodedata.combining(c)]).lower()


def titulo_amigavel(texto):
    if not texto:
        return ''
    palavras_minusculas = {'de', 'da', 'do', 'das', 'dos', 'e'}
    palavras = texto.lower().split()
    resultado = []
    for i, palavra in enumerate(palavras):
        if i > 0 and palavra in palavras_minusculas:
            resultado.append(palavra)
        else:
            resultado.append(palavra.capitalize())
    return ' '.join(resultado)


def cor_clarear(hex_color, alpha=0.12):
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f'rgba({r}, {g}, {b}, {alpha})'


def formatar_real(valor):
    """Formata valor numérico em reais (padrão brasileiro)."""
    if valor is None or valor == 0:
        return 'R$ 0'
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return 'R$ 0'

    if abs(valor) >= 1_000_000:
        return f'R$ {valor/1_000_000:.2f}M'.replace('.', ',')
    if abs(valor) >= 10_000:
        return f'R$ {valor/1_000:.0f}k'.replace('.', ',')
    formatado = f'{valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {formatado}'


def formatar_real_completo(valor):
    """Formata sempre por extenso (R$ 113.936,40)."""
    if valor is None or valor == 0:
        return '—'
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return '—'
    formatado = f'{valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {formatado}'


def parse_valor_brl(valor_str):
    """Converte 'R$ 35.000,00' em 35000.00."""
    if not valor_str:
        return 0.0
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    txt = str(valor_str).replace('R$', '').replace(' ', '').strip()
    txt = txt.replace('.', '').replace(',', '.')
    try:
        return float(txt)
    except (ValueError, TypeError):
        return 0.0


def formatar_data_br(data_iso):
    """Converte 'YYYY-MM-DD' em 'DD/MM/AAAA'."""
    if not data_iso:
        return ''
    try:
        return datetime.strptime(data_iso[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return data_iso


def truncar(texto, max_caracteres):
    """Trunca texto preservando palavras."""
    if not texto:
        return ''
    if len(texto) <= max_caracteres:
        return texto
    return texto[:max_caracteres].rsplit(' ', 1)[0] + '…'


def slug_fase(stage):
    """Converte fase em slug para CSS class e filtro."""
    if not stage:
        return 'default'
    s = normalizar_texto(stage)
    if 'arquivado' in s or 'transitado' in s:
        return 'arquivado'
    if 'cumprimento' in s:
        return 'cumprimento'
    if 'execucao' in s:
        return 'execucao'
    if 'instrucao' in s:
        return 'instrucao'
    if 'recursal' in s or 'recurso' in s:
        return 'recursal'
    if 'sentenca' in s:
        return 'sentenca'
    if 'conhecimento' in s:
        return 'conhecimento'
    if 'planejamento' in s or 'pre-judicial' in s:
        return 'planejamento'
    return 'default'


# ============================================================
# CLASSIFICAÇÃO DE ÁREAS (HÍBRIDA)
# ============================================================
def classificar_area(processo, areas_config):
    grupo = processo.get('group') or ''
    tipo = processo.get('type') or ''
    folder = processo.get('folder') or ''
    notes = processo.get('notes') or ''
    texto_norm = normalizar_texto(f"{grupo} {tipo} {folder} {notes}")

    melhor_match = None
    melhor_score = 0

    for area in areas_config['areas']:
        if not area.get('ativa'):
            continue
        score = 0
        for palavra in area['palavras_chave_advbox']:
            palavra_norm = normalizar_texto(palavra)
            if palavra_norm in texto_norm:
                score += len(palavra_norm)
        if score > melhor_score:
            melhor_score = score
            melhor_match = area['id']

    if melhor_match:
        return melhor_match
    if grupo:
        return f"_auto_{normalizar_texto(grupo).replace(' ', '_')}"
    return "_auto_outros"


def montar_areas_dinamicas(processos_cliente, areas_config):
    fallback = areas_config.get('area_padrao_fallback', {})
    areas_pre = {a['id']: a for a in areas_config['areas'] if a.get('ativa')}

    contagem = {}
    for p in processos_cliente:
        aid = p['_area_id']
        contagem[aid] = contagem.get(aid, 0) + 1

    areas_exibir = []
    for area_id in contagem:
        if area_id in areas_pre:
            a = areas_pre[area_id]
            areas_exibir.append({
                'id': area_id, 'nome': a['nome'], 'cor': a['cor'],
                'icone': a['icone'], 'ordem': a.get('ordem_exibicao', 99),
                'detectada_auto': False,
            })
        elif area_id.startswith('_auto_'):
            nome_extraido = area_id.replace('_auto_', '').replace('_', ' ').title()
            areas_exibir.append({
                'id': area_id, 'nome': nome_extraido or 'Outros',
                'cor': fallback.get('cor', '#6B7280'),
                'icone': fallback.get('icone', 'documento_generico'),
                'ordem': 100, 'detectada_auto': True,
            })

    areas_exibir.sort(key=lambda x: x['ordem'])
    return areas_exibir


# ============================================================
# CLASSIFICAÇÃO DE ALERTAS (URGENTE / ATENÇÃO / FAVORÁVEL)
# ============================================================
def fase_eh_encerrada(stage):
    fases = ['ARQUIVADO', 'TRANSITADO EM JULGADO', 'ENCERRADO']
    return any(f in (stage or '').upper() for f in fases)


def fase_eh_favoravel(processo):
    stage = (processo.get('stage') or '').upper()
    notes = (processo.get('notes') or '').upper()
    if 'TRANSITADO EM JULGADO' in stage:
        return True
    if 'ARQUIVADO DEFINITIVAMENTE' in notes or 'ACORDO HOMOLOGADO' in notes:
        return True
    if 'EXTINTO' in notes and ('FAVORAV' in notes or 'INEPCIA' in notes):
        return True
    return False


def categorizar_alerta(processo):
    notes = (processo.get('notes') or '').upper()
    stage = (processo.get('stage') or '').upper()
    notes_orig = processo.get('notes') or ''

    # Favorável (mesmo encerrado)
    if fase_eh_favoravel(processo):
        return ('favoravel', notes_orig)

    if fase_eh_encerrada(stage):
        return ('normal', '')

    # Urgente: bloqueios
    if 'SISBAJUD' in notes or 'BLOQUEIO' in notes:
        return ('urgente', notes_orig)
    if 'PENHORA' in notes:
        return ('urgente', notes_orig)
    # Urgente: prazo aberto explícito
    if 'PRAZO' in notes and ('15 DIAS' in notes or 'CONTESTAR' in notes):
        return ('urgente', notes_orig)
    # Urgente: audiências marcadas
    if 'AUDIÊNCIA' in notes and re.search(r'\d{2}/\d{2}/\d{4}', notes):
        return ('urgente', notes_orig)
    if 'CITAÇÃO NÃO COMPROVADA' in notes:
        return ('urgente', notes_orig)

    # Atenção: instrução, audiências sem prazo iminente, conclusos
    if 'AUDIÊNCIA' in notes:
        return ('atencao', notes_orig)
    if 'INSTRUÇÃO' in stage:
        return ('atencao', notes_orig)
    if 'AGUARDANDO SENTENÇA' in stage or 'CONCLUSO' in notes:
        return ('atencao', notes_orig)
    if 'CUMPRIMENTO' in stage:
        return ('atencao', notes_orig)
    if 'EXECUÇÃO' in stage:
        return ('atencao', notes_orig)

    return ('normal', '')


def gerar_alerta_descricao_html(processo, categoria):
    """Gera descrição HTML rica do alerta com prazos destacados."""
    notes = processo.get('notes') or ''
    stage = (processo.get('stage') or '')
    notes_upper = notes.upper()

    # Bloqueio SISBAJUD
    if 'SISBAJUD' in notes_upper or 'BLOQUEIO' in notes_upper:
        valor_match = re.search(r'R\$\s*[\d.,]+', notes)
        if valor_match:
            return f'<strong>💰 Bloqueio SISBAJUD ativo</strong> — {html_lib.escape(valor_match.group(0))}'
        return '<strong>💰 Bloqueio SISBAJUD ativo</strong>'

    # Audiência com data
    aud_match = re.search(r'audi[eê]ncia.*?(\d{2}/\d{2}/\d{4}\s*(?:[àaà]s\s*)?\d{0,2}[h:]?\d{0,2})', notes, re.IGNORECASE)
    if aud_match:
        return f'<strong>📅 {html_lib.escape(aud_match.group(1))}</strong> — Audiência designada'

    # Prazo aberto
    if 'CONTESTAR' in notes_upper or '15 DIAS' in notes_upper:
        return '<strong>⏰ Prazo aberto</strong> — ' + html_lib.escape(truncar(notes, 100))

    # Cumprimento de sentença
    if 'CUMPRIMENTO' in stage.upper():
        return 'Em cumprimento de sentença'

    # Recuperação judicial
    if 'RECUPERAÇÃO JUDICIAL' in notes_upper:
        return 'Em recuperação judicial — habilitação de crédito'

    # Acordo
    if 'ACORDO' in notes_upper and 'HOMOLOGADO' in notes_upper:
        return 'Acordo homologado — processo arquivado'

    # Arquivamento
    if 'ARQUIVADO' in stage.upper():
        return 'Processo arquivado definitivamente'

    # Trânsito em julgado
    if 'TRANSITADO' in stage.upper():
        return 'Trânsito em julgado'

    # Padrão: trecho do andamento
    return html_lib.escape(truncar(notes, 130))


# ============================================================
# DADOS PARA OS GRÁFICOS
# ============================================================
def agrupar_por_fase(processos):
    """Distribuição por fase processual."""
    contagem = {}
    for p in processos:
        fase = p.get('stage') or 'NÃO INFORMADA'
        fase_amigavel = titulo_amigavel(fase)
        contagem[fase_amigavel] = contagem.get(fase_amigavel, 0) + 1
    items = sorted(contagem.items(), key=lambda x: -x[1])
    return {
        'labels': [item[0] for item in items],
        'valores': [item[1] for item in items],
    }


def agrupar_por_tribunal(processos, limite=8):
    """Distribuição por tribunal/comarca."""
    contagem = {}
    for p in processos:
        tribunal = p.get('tribunal') or '?'
        comarca = p.get('county') or ''
        if comarca and tribunal != '?':
            chave = f"{tribunal} — {titulo_amigavel(comarca)}"
        elif tribunal != '?':
            chave = tribunal
        else:
            chave = 'Não informado'
        contagem[chave] = contagem.get(chave, 0) + 1
    items = sorted(contagem.items(), key=lambda x: -x[1])[:limite]
    return {
        'labels': [item[0] for item in items],
        'valores': [item[1] for item in items],
    }


def agrupar_por_tipo_acao(processos, limite=8):
    """Distribuição por tipo de ação."""
    contagem = {}
    for p in processos:
        tipo = p.get('type') or 'NÃO INFORMADO'
        tipo_amigavel = titulo_amigavel(tipo)
        contagem[tipo_amigavel] = contagem.get(tipo_amigavel, 0) + 1
    items = sorted(contagem.items(), key=lambda x: -x[1])[:limite]
    return {
        'labels': [item[0] for item in items],
        'valores': [item[1] for item in items],
    }


def agrupar_por_status(processos):
    """Distribuição Ativos × Arquivados."""
    ativos = sum(1 for p in processos if not p['_encerrado'])
    arquivados = sum(1 for p in processos if p['_encerrado'])
    labels = []
    valores = []
    if ativos > 0:
        labels.append('Ativos')
        valores.append(ativos)
    if arquivados > 0:
        labels.append('Arquivados')
        valores.append(arquivados)
    return {'labels': labels, 'valores': valores}


# ============================================================
# TIMELINE COM PRAZOS FUTUROS
# ============================================================
def montar_timeline_area(processos_area, movements_data, dias=30):
    """Monta timeline incluindo andamentos passados E prazos futuros."""
    hoje = datetime.now()
    data_corte_passado = hoje - timedelta(days=dias)

    eventos = []
    for proc in processos_area:
        proc_id_str = str(proc['id'])
        andamentos = movements_data.get(proc_id_str, [])

        # Identificador do processo (CNJ ou folder)
        referencia = (proc.get('process_number')
                     or proc.get('protocol_number')
                     or titulo_amigavel(proc.get('folder', 'Sem identificação')))

        for andamento in andamentos:
            try:
                data_andamento = datetime.strptime(andamento['date'], '%Y-%m-%d')
            except (ValueError, KeyError, TypeError):
                continue

            # Inclui passado próximo + futuro (prazos)
            if data_andamento < data_corte_passado:
                continue

            prazo_futuro = data_andamento > hoje

            eventos.append({
                'data_iso': andamento['date'],
                'data_obj': data_andamento,
                'data_formatada': data_andamento.strftime('%d/%m/%Y'),
                'title': andamento.get('title', 'Andamento'),
                'description': andamento.get('description', ''),
                'processo_referencia': referencia,
                'prazo_futuro': prazo_futuro,
            })

        # Adicionar prazos extraídos das notas (audiências futuras detectadas)
        notes = proc.get('notes') or ''
        for match in re.finditer(r'(\d{2}/\d{2}/\d{4})(?:\s*[àaà]?s?\s*(\d{1,2}[h:]\d{0,2}))?\s*[-–—]?\s*(audi[eê]ncia[^.]*)', notes, re.IGNORECASE):
            data_str = match.group(1)
            hora_str = match.group(2) or ''
            descricao = match.group(3)
            try:
                data_evt = datetime.strptime(data_str, '%d/%m/%Y')
                if data_evt > hoje:
                    desc_completa = f"{descricao}"
                    if hora_str:
                        desc_completa = f"{descricao} às {hora_str}"
                    # Evitar duplicar se já existe
                    ja_existe = any(e['data_iso'] == data_evt.strftime('%Y-%m-%d') and 'audi' in e['title'].lower()
                                    for e in eventos if e['processo_referencia'] == referencia)
                    if not ja_existe:
                        eventos.append({
                            'data_iso': data_evt.strftime('%Y-%m-%d'),
                            'data_obj': data_evt,
                            'data_formatada': data_str,
                            'title': 'Audiência designada',
                            'description': desc_completa.strip(),
                            'processo_referencia': referencia,
                            'prazo_futuro': True,
                        })
            except (ValueError, TypeError):
                continue

    # Ordenar: futuros primeiro (do mais próximo), depois passados (mais recentes)
    eventos.sort(key=lambda x: (not x['prazo_futuro'], x['data_obj'] if not x['prazo_futuro'] else -x['data_obj'].timestamp()))
    # Inverter para futuros do mais próximo, passados do mais recente
    futuros = sorted([e for e in eventos if e['prazo_futuro']], key=lambda x: x['data_obj'])
    passados = sorted([e for e in eventos if not e['prazo_futuro']], key=lambda x: x['data_obj'], reverse=True)
    return (futuros + passados)[:15]


# ============================================================
# DADOS DA TABELA DE PROCESSOS
# ============================================================
def montar_dados_tabela(processos_area):
    """Prepara cada processo com os campos que a tabela exige."""
    resultado = []
    for proc in processos_area:
        partes_array = proc.get('customers', [])
        cliente_principal = partes_array[0]['name'] if partes_array else ''
        cliente_curto = truncar(titulo_amigavel(cliente_principal), 40)

        # Folder serve como contraparte/descrição alternativa
        folder = proc.get('folder', '')
        contraparte = truncar(titulo_amigavel(folder), 60) if folder else 'Não informado'

        valor_num = parse_valor_brl(proc.get('value', 0))
        valor_alt = proc.get('contingency', 0) or 0
        valor_efetivo = valor_num if valor_num > 0 else valor_alt

        notes = proc.get('notes') or ''
        ultimo_andamento = truncar(notes, 150) if notes else 'Sem andamento registrado'

        # Detectar prazo de destaque
        prazo_destaque = ''
        match_prazo = re.search(r'(\d{2}/\d{2}/\d{4}\s*[àaà]?s?\s*\d{0,2}[h:]?\d{0,2})\s*[-–—]?\s*(Audi[eê]ncia[^.]*)', notes, re.IGNORECASE)
        if match_prazo:
            try:
                data_str = re.search(r'\d{2}/\d{2}/\d{4}', match_prazo.group(1)).group(0)
                data_evt = datetime.strptime(data_str, '%d/%m/%Y')
                if data_evt > datetime.now():
                    prazo_destaque = match_prazo.group(0).strip()
            except (ValueError, AttributeError, TypeError):
                pass

        # Texto de busca (lowercase, normalizado)
        texto_busca_partes = [
            proc.get('process_number') or '',
            proc.get('protocol_number') or '',
            cliente_principal,
            folder,
            proc.get('tribunal') or '',
            proc.get('county') or '',
            proc.get('type') or '',
            proc.get('stage') or '',
            notes,
        ]
        texto_busca = normalizar_texto(' '.join(texto_busca_partes))

        proc_tabela = dict(proc)
        proc_tabela.update({
            'fase_slug': slug_fase(proc.get('stage')),
            'texto_busca': texto_busca,
            'partes_texto': cliente_principal,
            'parte_principal_curta': cliente_curto or 'Cliente do escritório',
            'contraparte_curta': f'vs. {contraparte}',
            'county_titulo': titulo_amigavel(proc.get('county') or ''),
            'court_titulo': titulo_amigavel(proc.get('court') or ''),
            'valor_numerico': valor_efetivo,
            'valor_formatado': formatar_real_completo(valor_efetivo),
            'ultimo_andamento_curto': ultimo_andamento,
            'prazo_destaque': prazo_destaque,
        })
        resultado.append(proc_tabela)
    return resultado


def gerar_resumo_area(area_dados):
    """Gera texto descritivo curto sobre a área."""
    if area_dados['total'] == 0:
        return 'Nenhum processo nesta área.'
    if area_dados['ativos'] == 0:
        return 'Todos os processos desta área estão arquivados.'
    return (
        f"{area_dados['ativos']} processo{'s' if area_dados['ativos'] != 1 else ''} ativo{'s' if area_dados['ativos'] != 1 else ''} "
        f"e {area_dados['encerrados']} arquivado{'s' if area_dados['encerrados'] != 1 else ''}."
    )


# ============================================================
# DADOS DO MODAL DE DETALHES
# ============================================================
def gerar_dados_modal(processo):
    """Gera HTML do conteúdo do modal para um processo específico."""
    partes_array = processo.get('customers', [])
    cliente_principal = partes_array[0]['name'] if partes_array else 'Não informado'
    folder = processo.get('folder', '')

    # Título do modal
    titulo = f"{titulo_amigavel(cliente_principal)}"
    if folder:
        titulo += f" — {titulo_amigavel(folder)}"

    identificador = processo.get('process_number') or processo.get('protocol_number') or 'Sem identificação'

    valor_num = parse_valor_brl(processo.get('value', 0))
    valor_alt = processo.get('contingency', 0) or 0
    valor_efetivo = valor_num if valor_num > 0 else valor_alt

    fase_slug = slug_fase(processo.get('stage'))
    fase_titulo = titulo_amigavel(processo.get('stage') or '—')

    notes = processo.get('notes') or 'Sem observações registradas.'
    data_distribuicao = formatar_data_br(processo.get('process_date', ''))
    responsavel = titulo_amigavel(processo.get('responsible') or '—')

    html_corpo = f"""
        <div class="modal-grid">
            <div class="modal-secao">
                <h4>Tribunal</h4>
                <p>{html_lib.escape(processo.get('tribunal') or '—')}</p>
            </div>
            <div class="modal-secao">
                <h4>Comarca / Vara</h4>
                <p>{html_lib.escape(titulo_amigavel(processo.get('county') or ''))} — {html_lib.escape(titulo_amigavel(processo.get('court') or '—'))}</p>
            </div>
            <div class="modal-secao">
                <h4>Tipo de Ação</h4>
                <p>{html_lib.escape(titulo_amigavel(processo.get('type') or '—'))}</p>
            </div>
            <div class="modal-secao">
                <h4>Fase Atual</h4>
                <p><span class="badge badge-fase-{fase_slug}">{html_lib.escape(fase_titulo)}</span></p>
            </div>
            <div class="modal-secao">
                <h4>Valor da Causa</h4>
                <p style="font-weight:700;">{formatar_real_completo(valor_efetivo)}</p>
            </div>
            <div class="modal-secao">
                <h4>Data de Distribuição</h4>
                <p>{data_distribuicao or '—'}</p>
            </div>
            <div class="modal-secao">
                <h4>Cliente</h4>
                <p>{html_lib.escape(titulo_amigavel(cliente_principal))}</p>
            </div>
            <div class="modal-secao">
                <h4>Responsável</h4>
                <p>{html_lib.escape(responsavel)}</p>
            </div>
            <div class="modal-secao modal-secao-larga">
                <h4>Pasta / Descrição</h4>
                <p>{html_lib.escape(titulo_amigavel(folder) or '—')}</p>
            </div>
            <div class="modal-secao modal-secao-larga">
                <h4>Observações e Último Andamento</h4>
                <p>{html_lib.escape(notes)}</p>
            </div>
        </div>
    """

    return {
        'titulo_modal': titulo,
        'identificador': identificador,
        'html_corpo': html_corpo,
    }


# ============================================================
# GERADOR DE DASHBOARD
# ============================================================
def gerar_dashboard(cliente_id, escritorio, areas_config, customers_data, lawsuits_data, movements_data, diligencias_data=None):
    cliente = next((c for c in customers_data['data'] if c['id'] == cliente_id), None)
    if not cliente:
        return None

    documento_limpo = ''.join(c for c in cliente['identification'] if c.isdigit())
    tipo_pessoa = 'PJ' if len(documento_limpo) == 14 else 'PF'
    tipo_pessoa_extenso = 'Pessoa Jurídica' if tipo_pessoa == 'PJ' else 'Pessoa Física'

    # Coletar processos do cliente
    processos = []
    for vinculo in cliente.get('lawsuits', []):
        proc = lawsuits_data.get(str(vinculo['lawsuit_id']))
        if proc:
            proc = dict(proc)
            cat, _desc = categorizar_alerta(proc)
            proc['_alerta'] = cat
            proc['alerta_descricao_html'] = gerar_alerta_descricao_html(proc, cat)
            proc['_area_id'] = classificar_area(proc, areas_config)
            proc['_encerrado'] = fase_eh_encerrada(proc.get('stage'))
            processos.append(proc)

    # Construir áreas
    areas_base = montar_areas_dinamicas(processos, areas_config)

    # Dados globais para o modal
    dados_processos = {}

    areas_processadas = []
    for area in areas_base:
        proc_area = [p for p in processos if p['_area_id'] == area['id']]
        ativos = [p for p in proc_area if not p['_encerrado']]
        encerrados = [p for p in proc_area if p['_encerrado']]

        alertas = {
            'urgente': [p for p in proc_area if p['_alerta'] == 'urgente'],
            'atencao': [p for p in proc_area if p['_alerta'] == 'atencao'],
            'favoravel': [p for p in proc_area if p['_alerta'] == 'favoravel'],
        }

        valor_total = sum(parse_valor_brl(p.get('value', 0)) or (p.get('contingency') or 0)
                          for p in ativos)

        dados_graficos = {
            'fases': agrupar_por_fase(proc_area),
            'tribunais': agrupar_por_tribunal(proc_area),
            'tipos': agrupar_por_tipo_acao(proc_area),
            'status': agrupar_por_status(proc_area),
        }

        timeline = montar_timeline_area(proc_area, movements_data, dias=30)
        processos_tabela = montar_dados_tabela(proc_area)

        # Adicionar todos os processos ao dicionário global do modal
        for p_tab in processos_tabela:
            dados_processos[str(p_tab['id'])] = gerar_dados_modal(p_tab)

        area_dict = {
            'id': area['id'],
            'nome': area['nome'],
            'cor': area['cor'],
            'cor_fundo': cor_clarear(area['cor'], 0.10),
            'icone_svg': ICONES_SVG.get(area['icone'], ICONES_SVG['documento_generico']),
            'detectada_auto': area['detectada_auto'],
            'total': len(proc_area),
            'ativos': len(ativos),
            'encerrados': len(encerrados),
            'alerta_critico': len(alertas['urgente']),
            'alerta_atencao': len(alertas['atencao']),
            'valor_disputa_formatado': formatar_real(valor_total),
            'alertas': alertas,
            'dados_graficos_json': json.dumps(dados_graficos, ensure_ascii=False),
            'timeline': timeline,
            'processos_tabela': processos_tabela,
        }
        area_dict['resumo_texto'] = gerar_resumo_area(area_dict)
        areas_processadas.append(area_dict)

    # ===== PAINEL DE PRODUTIVIDADE DO ESCRITÓRIO =====
    # Quando integrar com a API ADVBox real (Fase 2), substituir esta leitura
    # pelo endpoint /tasks ou /history filtrado por customer_id e período de 90 dias.
    produtividade = None
    if diligencias_data:
        dados_cli = diligencias_data.get(str(cliente_id))
        if dados_cli:
            produtividade = {
                'total': dados_cli.get('total', 0),
                'pecas': dados_cli.get('pecas', 0),
                'audiencias': dados_cli.get('audiencias', 0),
                'reunioes': dados_cli.get('reunioes', 0),
                'despachos': dados_cli.get('despachos', 0),
                'outros': dados_cli.get('outros', 0),
            }
            # Última atividade
            ult = dados_cli.get('ultima_atividade')
            if ult:
                produtividade['ultima_atividade'] = {
                    'data_formatada': formatar_data_br(ult.get('data', '')),
                    'tipo': ult.get('tipo', ''),
                    'descricao': ult.get('descricao', ''),
                }

    contexto = {
        'escritorio': escritorio,
        'cliente': {
            'nome_completo': cliente['name'],
            'tipo_pessoa': tipo_pessoa,
            'tipo_pessoa_extenso': tipo_pessoa_extenso,
            'documento_formatado': cliente['identification'],
        },
        'areas_ativas': areas_processadas,
        'data_atualizacao': datetime.now().strftime('%d/%m/%Y às %H:%M'),
        'total_processos': sum(a['ativos'] for a in areas_processadas),
        'dados_processos_json': json.dumps(dados_processos, ensure_ascii=False),
        'produtividade': produtividade,
    }

    env = Environment(loader=FileSystemLoader(str(CAMINHO_TEMPLATE)))
    env.filters['titulo_amigavel'] = titulo_amigavel
    template = env.get_template('dashboard.html')
    return template.render(**contexto)


# ============================================================
# CÁLCULO DE INDICADORES POR CLIENTE (para o painel interno)
# ============================================================
def calcular_indicadores_cliente(cliente_advbox, lawsuits_data):
    """Calcula totais de processos, alertas e valor para um cliente específico."""
    total_processos = 0
    processos_ativos = 0
    alertas_criticos = 0
    alertas_atencao = 0
    valor_em_disputa = 0.0

    for vinculo in cliente_advbox.get('lawsuits', []):
        proc = lawsuits_data.get(str(vinculo['lawsuit_id']))
        if not proc:
            continue

        total_processos += 1
        encerrado = fase_eh_encerrada(proc.get('stage'))
        if not encerrado:
            processos_ativos += 1
            valor = parse_valor_brl(proc.get('value', 0))
            if valor == 0:
                valor = proc.get('contingency', 0) or 0
            valor_em_disputa += valor

        cat, _ = categorizar_alerta(proc)
        if cat == 'urgente':
            alertas_criticos += 1
        elif cat == 'atencao':
            alertas_atencao += 1

    return {
        'total_processos': total_processos,
        'processos_ativos': processos_ativos,
        'alertas_criticos': alertas_criticos,
        'alertas_atencao': alertas_atencao,
        'valor_em_disputa': valor_em_disputa,
    }


def gerar_painel_interno(escritorio, clientes_config, customers_data, lawsuits_data, base_url=''):
    """Gera o HTML do painel interno do escritório."""

    # Mapa de departamentos
    deps = {d['id']: d for d in clientes_config.get('departamentos', [])}
    contagem_deps = {d_id: 0 for d_id in deps}

    # Agregadores globais
    total_clientes = 0
    clientes_ativos = 0
    total_processos = 0
    processos_ativos = 0
    alertas_criticos_global = 0
    valor_global = 0.0

    clientes_processados = []

    for cli_cfg in clientes_config.get('clientes', []):
        # Buscar dados completos no customers
        cli_advbox = next((c for c in customers_data['data'] if c['id'] == cli_cfg['id_advbox']), None)
        if not cli_advbox:
            continue

        total_clientes += 1
        if cli_cfg.get('ativo', True):
            clientes_ativos += 1

        contagem_deps[cli_cfg['departamento']] = contagem_deps.get(cli_cfg['departamento'], 0) + 1

        # Calcular indicadores
        indicadores = calcular_indicadores_cliente(cli_advbox, lawsuits_data)
        total_processos += indicadores['total_processos']
        processos_ativos += indicadores['processos_ativos']
        alertas_criticos_global += indicadores['alertas_criticos']
        valor_global += indicadores['valor_em_disputa']

        # Documento e tipo
        doc_limpo = ''.join(c for c in cli_advbox['identification'] if c.isdigit())
        tipo_pessoa = 'PJ' if len(doc_limpo) == 14 else 'PF'

        # Dep info
        dep_info = deps.get(cli_cfg['departamento'], {})

        # Texto de busca
        texto_busca_partes = [
            cli_advbox['name'],
            cli_advbox['identification'],
            cli_advbox.get('city') or '',
            cli_advbox.get('state') or '',
            cli_cfg.get('nome_curto', ''),
        ]
        texto_busca = normalizar_texto(' '.join(texto_busca_partes))

        # URL relativa (para abrir do painel interno - depende do contexto)
        # URL relativa: aponta para index.html explicitamente para funcionar tanto local
        # quanto em servidor (GitHub Pages aceita ambos os formatos)
        url_relativa = f"./clientes/{cli_cfg['slug_url']}/index.html"
        url_completa = f"{base_url.rstrip('/')}/{cli_cfg['slug_url']}/" if base_url else url_relativa

        clientes_processados.append({
            'id_advbox': cli_cfg['id_advbox'],
            'nome_completo': cli_advbox['name'],
            'documento_formatado': cli_advbox['identification'],
            'tipo_pessoa': tipo_pessoa,
            'departamento_id': cli_cfg['departamento'],
            'departamento_nome': dep_info.get('nome', '?'),
            'cor_departamento': dep_info.get('cor', '#0A1628'),
            'slug_url': cli_cfg['slug_url'],
            'url_relativa': url_relativa,
            'url_completa': url_completa,
            'ativo': cli_cfg.get('ativo', True),
            'texto_busca': texto_busca,
            'total_processos': indicadores['total_processos'],
            'processos_ativos': indicadores['processos_ativos'],
            'alertas_criticos': indicadores['alertas_criticos'],
            'alertas_atencao': indicadores['alertas_atencao'],
            'valor_em_disputa': indicadores['valor_em_disputa'],
        })

    # Ordenar: alertas críticos primeiro, depois por nome
    clientes_processados.sort(
        key=lambda x: (-x['alertas_criticos'], -x['alertas_atencao'], x['nome_completo'])
    )

    # Lista de departamentos com contagem
    deps_lista = []
    for d_id, d_info in deps.items():
        deps_lista.append({
            'id': d_id,
            'nome': d_info['nome'],
            'cor': d_info['cor'],
            'contagem': contagem_deps.get(d_id, 0),
        })

    contexto = {
        'escritorio': escritorio,
        'clientes': clientes_processados,
        'departamentos': deps_lista,
        'kpis_globais': {
            'total_clientes': total_clientes,
            'clientes_ativos': clientes_ativos,
            'total_processos': total_processos,
            'processos_ativos': processos_ativos,
            'alertas_criticos': alertas_criticos_global,
            'valor_disputa_formatado': formatar_real(valor_global),
        },
        'data_atualizacao': datetime.now().strftime('%d/%m/%Y às %H:%M'),
    }

    env = Environment(loader=FileSystemLoader(str(CAMINHO_TEMPLATE)))
    env.filters['titulo_amigavel'] = titulo_amigavel
    template = env.get_template('painel_interno.html')
    return template.render(**contexto)


# ============================================================
# MAIN
# ============================================================
def main():
    print('🔧 Fase 1.5 — Painel Interno + Dashboards Multi-Cliente\n')

    escritorio = carregar_json(CAMINHO_CONFIG / 'escritorio.json')
    areas_config = carregar_json(CAMINHO_CONFIG / 'areas_direito.json')
    clientes_config = carregar_json(CAMINHO_CONFIG / 'clientes.json')

    logo_base64 = carregar_logo_base64(CAMINHO_CONFIG / 'logo.png')
    if logo_base64:
        escritorio['logo_base64'] = logo_base64
        print('✅ Logo oficial embutido em base64')

    customers_data = carregar_json(CAMINHO_MOCK / 'customers_mock.json')
    lawsuits_data = carregar_json(CAMINHO_MOCK / 'lawsuits_mock.json')
    movements_data = carregar_json(CAMINHO_MOCK / 'movements_mock.json')

    # Diligências (painel de produtividade)
    arquivo_diligencias = CAMINHO_MOCK / 'diligencias_mock.json'
    diligencias_data = carregar_json(arquivo_diligencias) if arquivo_diligencias.exists() else None
    if diligencias_data:
        n_dilig = sum(v.get('total', 0) for k, v in diligencias_data.items() if not k.startswith('_'))
        print(f'✅ Diligências carregadas: {n_dilig} totais nos últimos 90 dias')

    print(f'✅ {len([a for a in areas_config["areas"] if a["ativa"]])} áreas pré-cadastradas')
    n_proc = len([k for k in lawsuits_data if not k.startswith("_")])
    n_mov = len([k for k in movements_data if not k.startswith("_")])
    n_clientes_cfg = len(clientes_config.get('clientes', []))
    print(f'✅ {customers_data["totalCount"]} clientes (ADVBox) / {n_clientes_cfg} clientes cadastrados / {n_proc} processos / {n_mov} com andamentos\n')

    CAMINHO_SAIDA.mkdir(exist_ok=True)

    # Gerar dashboards individuais
    for cli_cfg in clientes_config.get('clientes', []):
        if not cli_cfg.get('ativo', True):
            continue

        cli_advbox = next((c for c in customers_data['data'] if c['id'] == cli_cfg['id_advbox']), None)
        if not cli_advbox:
            print(f'⚠️  Cliente {cli_cfg["id_advbox"]} cadastrado mas não encontrado no ADVBox.')
            continue

        nome_friendly = titulo_amigavel(cli_advbox['name'])
        print(f'📄 Gerando dashboard: {nome_friendly[:50]}')

        html = gerar_dashboard(
            cliente_id=cli_cfg['id_advbox'],
            escritorio=escritorio,
            areas_config=areas_config,
            customers_data=customers_data,
            lawsuits_data=lawsuits_data,
            movements_data=movements_data,
            diligencias_data=diligencias_data,
        )
        if html:
            pasta = CAMINHO_SAIDA / cli_cfg['slug_url']
            pasta.mkdir(exist_ok=True)
            (pasta / 'index.html').write_text(html, encoding='utf-8')
            print(f'   ✅ {pasta.relative_to(RAIZ)}/index.html  ({len(html):,} bytes)')

    # Gerar painel interno
    print(f'\n🔐 Gerando painel interno...')
    html_painel = gerar_painel_interno(
        escritorio=escritorio,
        clientes_config=clientes_config,
        customers_data=customers_data,
        lawsuits_data=lawsuits_data,
    )
    arquivo_painel = RAIZ / 'painel-interno.html'
    arquivo_painel.write_text(html_painel, encoding='utf-8')
    print(f'   ✅ {arquivo_painel.relative_to(RAIZ)}  ({len(html_painel):,} bytes)')

    print('\n🎉 Geração concluída!')


if __name__ == '__main__':
    main()
