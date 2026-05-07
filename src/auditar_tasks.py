"""
Auditoria das strings `task` que caem em "Outras" no bloco 90 dias.

Reproduz EXATAMENTE a categorizacao de calcular_atividade_90d e
coleta as strings que ficaram sem categoria mapeada. Ordena por
frequencia e sugere categoria heuristica para cada (apoiar decisao
de quais palavras-chave acrescentar ao mapping de producao).

REGRA DE OURO:
  Esta saida CONTEM strings cruas de `task` da API ADVBox (texto
  livre interno do escritorio). NAO deve ser commitada nem usada
  no template publico. Saida vai para tmp/auditoria_tasks_outras.txt
  (ja gitignored). Operador apaga depois de revisar.

So leitura. Nao modifica gerador, template ou cache de producao.
"""

import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advbox_client import AdvboxClient, AdvboxError

RAIZ = Path(__file__).resolve().parent.parent
DADOS_PUBLICOS = RAIZ / 'clientes' / 'painel-piloto-pj-2026-n4q8' / 'dados.json'
PASTA_TMP = RAIZ / 'tmp'
SAIDA = PASTA_TMP / 'auditoria_tasks_outras.txt'


# ---------------------------------------------------------------------------
# Categorizacao — REPLICA EXATA de calcular_atividade_90d em gerador_producao
# ---------------------------------------------------------------------------

def categorizar(task_lower):
    if any(p in task_lower for p in
           ('peticao', 'petição',
            'manifesta', 'contesta', 'recurso',
            'embargos', 'agravo',
            'apelacao', 'apelação',
            'impugna', 'memoriais')):
        return 'Pecas'
    if any(p in task_lower for p in ('audien', 'sessao', 'sessão')):
        return 'Audiencias'
    if any(p in task_lower for p in ('reuniao', 'reunião', 'atendimento')):
        return 'Reunioes'
    if any(p in task_lower for p in
           ('despacho', 'decisao', 'decisão', 'sentenca', 'sentença')):
        return 'Despachos'
    return 'Outras'


def sugerir_categoria(task_str):
    """Heuristica de mapeamento futuro para tasks que cairam em 'Outras'."""
    s = (task_str or '').lower()
    if any(k in s for k in ('publica', 'intima', 'djen')):
        return 'Diligencias_Externas'
    if 'diligenc' in s:
        return 'Diligencias_Externas'
    if 'prazo' in s:
        return 'Pecas (provavel)'
    if 'atendi' in s or 'client' in s:
        return 'Reunioes'
    if 'audien' in s:
        return 'Audiencias'
    if 'peticao' in s or 'petic' in s or 'petição' in s:
        return 'Pecas'
    if any(k in s for k in ('despacho', 'decis', 'sentenca', 'sentenc')):
        return 'Despachos'
    return '?'


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f'Auditoria de tasks em "Outras" — {datetime.now().isoformat(timespec="seconds")}')
    print()

    if not DADOS_PUBLICOS.exists():
        print(f'ERRO: {DADOS_PUBLICOS} nao existe — rode o gerador primeiro.')
        return 1

    d = json.loads(DADOS_PUBLICOS.read_text(encoding='utf-8'))
    ids_validos = set()
    for proc in d.get('processos', []):
        pid = proc.get('id')
        if pid is not None:
            try:
                ids_validos.add(int(pid))
            except (ValueError, TypeError):
                continue
    print(f'Lawsuits do piloto: {len(ids_validos)}')
    print()

    try:
        client = AdvboxClient()
    except AdvboxError as e:
        print(f'ERRO ao inicializar AdvboxClient: {e}')
        return 1

    hoje = datetime.now().date()
    limite_90d = hoje - timedelta(days=90)

    contagens = Counter()
    strings_outras = []  # vai conter texto LIVRE — nao expor no painel
    posts_processados = 0
    posts_do_cliente = 0
    posts_na_janela = 0
    paginas = 0

    offset = 0
    per_page = 100
    max_pages = 50

    print('Paginando /posts (sem filtro — filtro local depois)...')
    for _ in range(max_pages):
        try:
            resp = client._request('posts', params={'limit': per_page, 'offset': offset})
        except AdvboxError as e:
            print(f'  ERRO em /posts: {e}')
            break
        paginas += 1

        if not isinstance(resp, dict):
            break
        data = resp.get('data') or []
        if not isinstance(data, list) or not data:
            break

        for post in data:
            if not isinstance(post, dict):
                continue
            posts_processados += 1
            lid = post.get('lawsuits_id')
            if lid is None:
                continue
            try:
                lid_int = int(lid)
            except (ValueError, TypeError):
                continue
            if lid_int not in ids_validos:
                continue
            posts_do_cliente += 1

            created = post.get('created_at')
            if not created:
                continue
            try:
                dt = datetime.strptime(str(created)[:10], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                continue
            if dt < limite_90d:
                continue
            posts_na_janela += 1

            task_raw = post.get('task') or ''
            cat = categorizar(task_raw.lower())
            contagens[cat] += 1
            if cat == 'Outras':
                strings_outras.append(task_raw)

        if len(data) < per_page:
            break
        offset += per_page
        total_count = resp.get('totalCount')
        if total_count and offset >= total_count:
            break

    # Saida resumo no console
    print()
    print(f'Paginas requisitadas:        {paginas}')
    print(f'Posts globais examinados:    {posts_processados}')
    print(f'Posts do cliente piloto:     {posts_do_cliente}')
    print(f'Posts na janela 90d:         {posts_na_janela}')
    print()
    print('Distribuicao de categorias (deve bater com calcular_atividade_90d):')
    for cat in ('Pecas', 'Audiencias', 'Reunioes', 'Despachos', 'Outras'):
        print(f'  {cat:<14} : {contagens[cat]}')
    print()

    cont_outras = Counter(strings_outras)
    print(f"Strings DISTINTAS em 'Outras': {len(cont_outras)}")
    print(f"Total de ocorrencias 'Outras': {len(strings_outras)}")
    print()

    # Monta tabela completa para arquivo (top 50)
    linhas_relatorio = []
    linhas_relatorio.append(f'Auditoria de tasks em "Outras"')
    linhas_relatorio.append(f'Gerado em: {datetime.now().isoformat(timespec="seconds")}')
    linhas_relatorio.append(f'Cliente piloto: 13669008 (HOSPITAL AMPARO LTDA)')
    linhas_relatorio.append('')
    linhas_relatorio.append('AVISO: este arquivo contem strings cruas da API (texto livre')
    linhas_relatorio.append('interno do escritorio). NAO commitar. Apagar apos revisao.')
    linhas_relatorio.append('')
    linhas_relatorio.append(f'Paginas /posts requisitadas: {paginas}')
    linhas_relatorio.append(f'Posts processados:           {posts_processados}')
    linhas_relatorio.append(f'Posts do cliente:            {posts_do_cliente}')
    linhas_relatorio.append(f'Posts na janela 90d:         {posts_na_janela}')
    linhas_relatorio.append('')
    linhas_relatorio.append('Distribuicao por categoria atual:')
    for cat in ('Pecas', 'Audiencias', 'Reunioes', 'Despachos', 'Outras'):
        linhas_relatorio.append(f'  {cat:<14} : {contagens[cat]}')
    linhas_relatorio.append('')
    linhas_relatorio.append(f'Strings DISTINTAS em "Outras": {len(cont_outras)}')
    linhas_relatorio.append(f'Total ocorrencias "Outras":    {len(strings_outras)}')
    linhas_relatorio.append('')
    linhas_relatorio.append('TOP 50 strings em "Outras" (formato: [N]  "task"  ->  sugestao):')
    linhas_relatorio.append('')

    print('TOP 30 strings de "Outras" com sugestao heuristica:')
    print()
    top50 = cont_outras.most_common(50)
    for i, (texto, n) in enumerate(top50, 1):
        sug = sugerir_categoria(texto)
        linha = f'  [{n:>3}]  "{texto}"  ->  {sug}'
        linhas_relatorio.append(linha)
        if i <= 30:
            print(linha)

    # Salva em tmp/
    PASTA_TMP.mkdir(exist_ok=True)
    SAIDA.write_text('\n'.join(linhas_relatorio), encoding='utf-8')

    print()
    print(f'>>> Tabela completa (top 50) salva em: {SAIDA.relative_to(RAIZ)}')
    print('   (pasta tmp/ ja gitignored — operador deve apagar apos revisar)')

    return 0


if __name__ == '__main__':
    sys.exit(main())
