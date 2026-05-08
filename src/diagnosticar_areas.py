"""
Diagnostico read-only: por que processos trabalhistas (J=5 no CNJ)
estao caindo em "Civel e Empresarial" no painel do piloto-pj?

Le APENAS o cache local cache/lawsuits_customer_13669008.json.
Sem chamadas a API. Sem modificar gerador. Sem commit.

Saida no console:
  1. Lista de cada lawsuit com (id, J inferido, tribunal, group)
  2. Tabela cruzada J × group
  3. Tipos de processo unicos para J=5
  4. Conteudo de config/areas_direito.json
  5. Diagnostico final + recomendacao
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / 'cache' / 'lawsuits_customer_13669008.json'
AREAS_JSON = RAIZ / 'config' / 'areas_direito.json'

NOMES_J = {
    '1': 'STF',
    '2': 'CNJ',
    '3': 'STJ',
    '4': 'Justica Federal',
    '5': 'Justica do Trabalho',
    '6': 'Justica Eleitoral',
    '7': 'Justica Militar da Uniao',
    '8': 'Justica Estadual',
    '9': 'Justica Militar Estadual',
}


def parse_cnj(numero):
    """Extrai (J, TR) do numero CNJ. Retorna (None, None) se invalido."""
    if not numero:
        return None, None
    digitos = ''.join(c for c in str(numero) if c.isdigit())
    if len(digitos) != 20:
        return None, None
    return digitos[13], digitos[14:16]


def main():
    if not CACHE.exists():
        print(f'ERRO: cache nao encontrado em {CACHE.relative_to(RAIZ)}')
        print('Rode `python src/gerador_producao.py` antes deste diagnostico.')
        return 1

    envelope = json.loads(CACHE.read_text(encoding='utf-8'))
    api = envelope.get('data') if isinstance(envelope, dict) else None
    lawsuits = (api or {}).get('data') if isinstance(api, dict) else None
    if not isinstance(lawsuits, list):
        print('ERRO: estrutura do cache inesperada.')
        return 1

    print(f'Cache: {CACHE.relative_to(RAIZ)}')
    print(f'Total de lawsuits no cache: {len(lawsuits)}')
    print()

    # ---------------------------------------------------------------
    # TAREFA 1 — listagem por lawsuit
    # ---------------------------------------------------------------
    print('=' * 84)
    print('  TAREFA 1 — Listagem por lawsuit (id | CNJ_J | tribunal_inferido | group)')
    print('=' * 84)
    print(f'  {"id":<10} {"J":<3} {"Tribunal":<14} {"group_ADVBox":<46}')
    print('  ' + '-' * 80)

    pares_j_group = []  # (J, group) por lawsuit, para o pivot
    tipos_por_j = defaultdict(Counter)

    for law in lawsuits:
        if not isinstance(law, dict):
            continue
        lid = law.get('id')
        numero = law.get('process_number')
        grp = (law.get('group') or '').strip() or '(vazio)'
        tipo = (law.get('type') or '').strip() or '(sem type)'
        j, tr = parse_cnj(numero)

        if j == '5':
            tribunal = f'TRT-{int(tr):d}' if tr and tr.isdigit() and tr != '00' else 'TST'
        elif j == '8':
            tribunal = f'TJ ({tr})'
        elif j == '4':
            tribunal = f'TRF-{int(tr):d}' if tr and tr.isdigit() else 'TRF'
        elif j is None:
            tribunal = '(CNJ invalido)'
        else:
            tribunal = NOMES_J.get(j, f'?J={j}')

        print(f'  {str(lid):<10} {(j or "-"):<3} {tribunal:<14} {grp:<46}')
        pares_j_group.append((j or '-', grp))
        tipos_por_j[j or '-'][tipo] += 1

    print()

    # ---------------------------------------------------------------
    # TAREFA 2 — pivot J × group
    # ---------------------------------------------------------------
    print('=' * 84)
    print('  TAREFA 2 — Tabela cruzada J × group')
    print('=' * 84)

    # Coletar todos os groups distintos para colunas
    groups_set = sorted({g for _, g in pares_j_group})
    js_set = sorted({j for j, _ in pares_j_group})

    cont = Counter(pares_j_group)

    # Largura das colunas
    largura_grp = max(12, max((len(g) for g in groups_set), default=0) + 2)

    # Cabecalho
    cab = f'  {"J":<5} {"Justica":<27}'
    for g in groups_set:
        cab += f' {g[:largura_grp]:<{largura_grp}}'
    cab += ' TOTAL'
    print(cab)
    print('  ' + '-' * (len(cab) - 2))

    # Linhas
    totais_col = Counter()
    for j in js_set:
        nome_j = NOMES_J.get(j, '(sem CNJ)')
        linha = f'  {j:<5} {nome_j:<27}'
        total_linha = 0
        for g in groups_set:
            n = cont.get((j, g), 0)
            linha += f' {n:<{largura_grp}}'
            total_linha += n
            totais_col[g] += n
        linha += f' {total_linha}'
        print(linha)

    # Linha de totais
    linha_total = f'  {"TOT":<5} {"":<27}'
    grand_total = 0
    for g in groups_set:
        n = totais_col[g]
        linha_total += f' {n:<{largura_grp}}'
        grand_total += n
    linha_total += f' {grand_total}'
    print(linha_total)
    print()

    # ---------------------------------------------------------------
    # TAREFA 3 — tipos de processo para J=5 (trabalhistas)
    # ---------------------------------------------------------------
    print('=' * 84)
    print('  TAREFA 3 — Tipos de processo (campo `type`) por J')
    print('=' * 84)

    if '5' in tipos_por_j and tipos_por_j['5']:
        print('  J=5 (Justica do Trabalho):')
        for tipo, n in tipos_por_j['5'].most_common():
            print(f'    [{n:>3}]  {tipo}')
        print()
    else:
        print('  J=5 sem casos.')
        print()

    if '8' in tipos_por_j and tipos_por_j['8']:
        print('  J=8 (Justica Estadual) — top 8:')
        for tipo, n in tipos_por_j['8'].most_common(8):
            print(f'    [{n:>3}]  {tipo}')
        print()

    if '4' in tipos_por_j and tipos_por_j['4']:
        print('  J=4 (Justica Federal):')
        for tipo, n in tipos_por_j['4'].most_common():
            print(f'    [{n:>3}]  {tipo}')
        print()

    if '-' in tipos_por_j and tipos_por_j['-']:
        print('  CNJ invalido / sem numero — top 5:')
        for tipo, n in tipos_por_j['-'].most_common(5):
            print(f'    [{n:>3}]  {tipo}')
        print()

    # ---------------------------------------------------------------
    # TAREFA 4 — areas_direito.json + funcao do gerador
    # ---------------------------------------------------------------
    print('=' * 84)
    print('  TAREFA 4 — config/areas_direito.json')
    print('=' * 84)
    if AREAS_JSON.exists():
        print(AREAS_JSON.read_text(encoding='utf-8'))
    else:
        print('  ARQUIVO AUSENTE.')
    print()

    # ---------------------------------------------------------------
    # TAREFA 5 — diagnostico final
    # ---------------------------------------------------------------
    print('=' * 84)
    print('  TAREFA 5 — Diagnostico')
    print('=' * 84)

    n_j5 = sum(1 for j, _ in pares_j_group if j == '5')
    n_j5_privado = sum(1 for j, g in pares_j_group if j == '5' and g.upper() == 'PRIVADO')
    n_j5_social = sum(
        1 for j, g in pares_j_group
        if j == '5' and ('SOCIAL' in g.upper() or 'TRABALH' in g.upper())
    )
    n_j5_outros = n_j5 - n_j5_privado - n_j5_social

    print(f'  Trabalhistas (J=5) total                  : {n_j5}')
    print(f'  Trabalhistas com group=PRIVADO            : {n_j5_privado}')
    print(f'  Trabalhistas com group=SOCIAL/TRABALHISTA : {n_j5_social}')
    print(f'  Trabalhistas com outros groups            : {n_j5_outros}')
    print()

    if n_j5_privado > 0:
        print('  >>> EVIDENCIA: ha lawsuits trabalhistas (J=5) com group=PRIVADO no')
        print('      ADVBox. O gerador segue o que vem da API — nao infere area pelo')
        print('      CNJ. Por isso esses processos caem em "Civel e Empresarial".')
        print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
