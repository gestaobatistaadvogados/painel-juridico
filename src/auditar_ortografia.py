"""
Auditoria ortografica nos artefatos do dashboard.

Procura palavras PT-BR comuns que tendem a perder acento no codigo:
"juridico", "ultima atualizacao", "relacao", "audiencia", etc.

Le como UTF-8 e usa regex \\bpalavra\\b case-insensitive.

EXCLUSOES por tipo de arquivo:
  .html  → skip matches dentro de aspas (atributos), dentro de
           <script>...</script>, dentro de Jinja {{...}}/{% %}
  .py    → SO flag matches dentro de string literais (entre aspas);
           skip se a string for chave de dict (seguida de ':')
  .json  → skip chaves (seguidas de ':'), so flag valores

Saida:
  - Relatorio no console
  - Mesmo relatorio em clientes/painel-piloto-pj-2026-n4q8/auditoria_ortografia.txt

Nao corrige nada — so reporta.
"""

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

RAIZ = Path(__file__).resolve().parent.parent
PASTA_PILOTO = RAIZ / 'clientes' / 'painel-piloto-pj-2026-n4q8'
RELATORIO = PASTA_PILOTO / 'auditoria_ortografia.txt'

ARQUIVOS_PRIORIDADE_1 = [PASTA_PILOTO / 'index.html']
ARQUIVOS_PRIORIDADE_2 = [
    RAIZ / 'src' / 'templates' / 'dashboard.html',
    RAIZ / 'src' / 'gerador_producao.py',
]
ARQUIVOS_PRIORIDADE_3 = [
    RAIZ / 'config' / 'escritorio.json',
    RAIZ / 'config' / 'areas_direito.json',
    RAIZ / 'config' / 'clientes.json',
]

# Pares (errado, correto). Apos deduplicar_pares(), so sobram pares onde
# errado != correto (case-insensitive) e palavra muito curta como "e" e
# excluida (geraria muitos falsos positivos).
PARES_BRUTOS = [
    ('juridico', 'jurídico'),
    ('area', 'área'),
    ('areas', 'áreas'),
    ('ultimo', 'último'),
    ('ultima', 'última'),
    ('ultimos', 'últimos'),
    ('ultimas', 'últimas'),
    ('decisao', 'decisão'),
    ('decisoes', 'decisões'),
    ('informacao', 'informação'),
    ('informacoes', 'informações'),
    ('acao', 'ação'),
    ('acoes', 'ações'),
    ('processuais', 'processuais'),
    ('seleciona', 'seleciona'),
    ('selecao', 'seleção'),
    ('relacao', 'relação'),
    ('relacoes', 'relações'),
    ('execucao', 'execução'),
    ('instrucao', 'instrução'),
    ('audiencia', 'audiência'),
    ('audiencias', 'audiências'),
    ('manifestacao', 'manifestação'),
    ('citacao', 'citação'),
    ('intimacao', 'intimação'),
    ('conciliacao', 'conciliação'),
    ('contestacao', 'contestação'),
    ('apelacao', 'apelação'),
    ('publicacao', 'publicação'),
    ('publico', 'público'),
    ('publica', 'pública'),
    ('publicos', 'públicos'),
    ('nao', 'não'),
    ('orgao', 'órgão'),
    ('orgaos', 'órgãos'),
    ('pratica', 'prática'),
    ('anexa', 'anexa'),
    ('numero', 'número'),
    ('numeros', 'números'),
    ('codigo', 'código'),
    ('relatorio', 'relatório'),
    ('indicios', 'indícios'),
    ('dia', 'dia'),
    ('estrategia', 'estratégia'),
    ('juiz', 'juiz'),
    ('juiza', 'juíza'),
    ('recursivo', 'recursivo'),
    ('recursal', 'recursal'),
    ('trafego', 'tráfego'),
    ('indices', 'índices'),
    ('relatorios', 'relatórios'),
    ('alertas', 'alertas'),
    ('favoravel', 'favorável'),
    ('favoraveis', 'favoráveis'),
    ('urgente', 'urgente'),
    ('atencao', 'atenção'),
    ('recebido', 'recebido'),
    ('ultima atualizacao', 'última atualização'),
    ('relacao de processos', 'relação de processos'),
    ('ate', 'até'),
    ('e', 'é'),
    ('varios', 'vários'),
    ('varias', 'várias'),
    ('regiao', 'região'),
    ('regioes', 'regiões'),
    ('tres', 'três'),
    ('ja', 'já'),
    ('voce', 'você'),
]

# Excluido por gerar muitos falsos positivos (conjuncao "e" do PT-BR
# tambem nao tem acento). Outras palavras curtas (ja, ate, tres, voce)
# sao mantidas — quase sempre indicam acento esquecido.
SKIP_PALAVRAS = {'e'}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def deduplicar_pares(pares):
    visto = set()
    out = []
    for errado, correto in pares:
        if errado.lower() == correto.lower():
            continue
        if errado.lower() in SKIP_PALAVRAS:
            continue
        if errado.lower() in visto:
            continue
        visto.add(errado.lower())
        out.append((errado, correto))
    # Ordena por len DESC: pares mais longos primeiro (evita
    # sobreposicao "ultima atualizacao" + "ultima").
    out.sort(key=lambda p: -len(p[0]))
    return out


def is_inside_quote(linha, pos):
    """Caminha pelos chars ate pos. True se aberta uma aspa (' ou ") sem fechar."""
    in_q = None
    for c in linha[:pos]:
        if in_q:
            if c == in_q:
                in_q = None
        elif c in '"\'':
            in_q = c
    return in_q is not None


def is_inside_jinja(linha, pos):
    """True se pos esta dentro de {{...}} ou {% %} na linha."""
    before = linha[:pos]
    last_open_var = before.rfind('{{')
    last_close_var = before.rfind('}}')
    last_open_blk = before.rfind('{%')
    last_close_blk = before.rfind('%}')
    in_var = last_open_var > last_close_var
    in_blk = last_open_blk > last_close_blk
    return in_var or in_blk


def is_json_key(linha, end):
    """True se logo apos `end` (passando pelo fechamento de aspas) vem ':'."""
    rest = linha[end:]
    m = re.search(r'["\']', rest)
    if not m:
        return False
    apos_aspas = rest[m.end():].lstrip()
    return apos_aspas.startswith(':')


def extrair_trecho(linha, start, end, raio=40):
    inicio = max(0, start - raio)
    fim = min(len(linha), end + raio)
    pref = '...' if inicio > 0 else ''
    suf = '...' if fim < len(linha) else ''
    return pref + linha[inicio:fim].strip() + suf


# ---------------------------------------------------------------------------
# Scanner principal
# ---------------------------------------------------------------------------

def escanear_arquivo(caminho, pares):
    if not caminho.exists():
        return None
    sufixo = caminho.suffix.lower()
    achados = []
    in_script = False

    with caminho.open('r', encoding='utf-8') as f:
        linhas = f.readlines()

    for linha_num, raw in enumerate(linhas, 1):
        linha = raw.rstrip('\r\n')

        # Estado de <script> em HTML — pula linhas inteiras dentro do bloco.
        if sufixo in ('.html', '.htm'):
            low = linha.lower()
            tem_open = '<script' in low
            tem_close = '</script>' in low
            if tem_open and tem_close:
                continue  # bloco inline na mesma linha — pula
            if tem_close:
                in_script = False
                continue
            if in_script:
                continue
            if tem_open:
                in_script = True
                continue

        ranges_cobertas = []
        for errado, correto in pares:
            pat = re.compile(r'\b' + re.escape(errado) + r'\b', re.IGNORECASE)
            for m in pat.finditer(linha):
                start, end = m.span()
                # Sobreposicao com match maior anterior?
                if any(start < e2 and end > s2 for s2, e2 in ranges_cobertas):
                    continue

                dentro_q = is_inside_quote(linha, start)

                if sufixo in ('.html', '.htm'):
                    # HTML: skip se em atributo (dentro de aspas) OU em Jinja
                    if dentro_q or is_inside_jinja(linha, start):
                        continue
                elif sufixo == '.py':
                    # Python: SO flag dentro de string. Skip se for chave dict.
                    if not dentro_q:
                        continue
                    if is_json_key(linha, end):
                        continue
                elif sufixo == '.json':
                    # JSON: matches sao todos dentro de aspas. Skip se chave.
                    if not dentro_q:
                        continue
                    if is_json_key(linha, end):
                        continue
                # Outros tipos: nao restringir

                ranges_cobertas.append((start, end))
                achados.append({
                    'linha': linha_num,
                    'palavra': m.group(),
                    'sugestao': correto,
                    'trecho': extrair_trecho(linha, start, end),
                })
    return achados


# ---------------------------------------------------------------------------
# Formatacao do relatorio
# ---------------------------------------------------------------------------

def formatar_arquivo(caminho_relativo, achados):
    out = [f'=== ARQUIVO: {caminho_relativo} ===']
    if not achados:
        out.append('  (nenhum erro encontrado)')
    else:
        for a in achados:
            out.append(f'  Linha {a["linha"]}: "{a["palavra"]}" → "{a["sugestao"]}"')
            out.append(f'    Trecho: {a["trecho"]}')
    out.append('')
    return out


def main():
    pares = deduplicar_pares(PARES_BRUTOS)

    saida = []
    saida.append('═' * 76)
    saida.append('  AUDITORIA ORTOGRAFICA — DASHBOARD CLIENTE PILOTO')
    saida.append('═' * 76)
    saida.append(f'  Pares verificados: {len(pares)} (apos deduplicacao + skip de "e")')
    saida.append(f'  Padrao: \\bpalavra\\b case-insensitive')
    saida.append(f'  Exclusoes: <script>, atributos HTML, {{{{...}}}} Jinja, chaves JSON/dict')
    saida.append('')

    secoes = [
        ('PRIORIDADE 1 — Saida final que o cliente ve', ARQUIVOS_PRIORIDADE_1),
        ('PRIORIDADE 2 — Templates e gerador', ARQUIVOS_PRIORIDADE_2),
        ('PRIORIDADE 3 — Configuracoes que aparecem no dashboard', ARQUIVOS_PRIORIDADE_3),
    ]

    total_erros = 0
    com_erros = []
    sem_erros = []
    ausentes = []

    for nome, lista in secoes:
        saida.append(f'─── {nome} ───')
        saida.append('')
        for caminho in lista:
            try:
                rel = caminho.relative_to(RAIZ)
            except ValueError:
                rel = caminho
            achados = escanear_arquivo(caminho, pares)
            if achados is None:
                saida.append(f'=== ARQUIVO: {rel} ===')
                saida.append('  (arquivo nao encontrado — pulando)')
                saida.append('')
                ausentes.append(str(rel))
                continue
            saida.extend(formatar_arquivo(rel, achados))
            if achados:
                total_erros += len(achados)
                com_erros.append((str(rel), len(achados)))
            else:
                sem_erros.append(str(rel))

    saida.append('═' * 76)
    saida.append('  RESUMO')
    saida.append('═' * 76)
    saida.append(f'  Total de erros: {total_erros} em {len(com_erros)} arquivo(s)')
    saida.append('')
    if com_erros:
        saida.append('  Arquivos COM erros:')
        for rel, n in com_erros:
            saida.append(f'    - {rel}: {n} erro(s)')
        saida.append('')
    if sem_erros:
        saida.append('  Arquivos SEM erros:')
        for rel in sem_erros:
            saida.append(f'    - {rel}')
        saida.append('')
    if ausentes:
        saida.append('  Arquivos AUSENTES:')
        for rel in ausentes:
            saida.append(f'    - {rel}')
        saida.append('')
    saida.append('═' * 76)

    texto = '\n'.join(saida)
    print(texto)

    PASTA_PILOTO.mkdir(parents=True, exist_ok=True)
    RELATORIO.write_text(texto, encoding='utf-8')
    print()
    print(f'>>> Relatorio salvo em: {RELATORIO.relative_to(RAIZ)}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
