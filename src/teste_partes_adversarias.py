"""
Inspeciona como a API ADVBox entrega o array `customers` dentro de cada
lawsuit — vem com nome dos itens, ou so com IDs?

Usa o cache existente em `cache/lawsuits_customer_13669008.json` — sem
nova chamada a API.

Imprime APENAS estrutura (chaves por item, tipos, presenca de nome),
sem expor nomes reais das partes adversarias nem do cliente.
"""

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

RAIZ = Path(__file__).resolve().parent.parent
CACHE_LAWSUITS = RAIZ / 'cache' / 'lawsuits_customer_13669008.json'

CLIENTE_PILOTO_ID = 13669008
LAWSUITS_A_INSPECIONAR = 5  # quantos para amostragem


def main():
    if not CACHE_LAWSUITS.exists():
        print('ERRO: cache de lawsuits ausente. Rode o gerador para popular.')
        return 1

    with CACHE_LAWSUITS.open('r', encoding='utf-8') as f:
        envelope_cache = json.load(f)

    # cache.py grava em {'_cached_at': ..., 'data': <resp>}
    resp = envelope_cache.get('data') if isinstance(envelope_cache, dict) else None
    if not isinstance(resp, dict) or not isinstance(resp.get('data'), list):
        print('ERRO: estrutura do cache inesperada.')
        return 1

    lawsuits = resp['data']
    print(f'Total de lawsuits no cache: {len(lawsuits)}')
    print(f'Inspecionando os {LAWSUITS_A_INSPECIONAR} primeiros.')
    print()

    todas_chaves = set()
    contagem_por_qtd = {}
    com_name = 0
    com_id = 0
    com_ambos = 0
    cliente_aparece_no_array = 0

    for i, law in enumerate(lawsuits[:LAWSUITS_A_INSPECIONAR]):
        lid = law.get('id')
        custs = law.get('customers')
        print(f'[{i}] lawsuit id={lid}')

        if not isinstance(custs, list):
            print(f'    customers NAO eh list: tipo={type(custs).__name__}')
            print()
            continue

        print(f'    qtd customers: {len(custs)}')
        for j, c in enumerate(custs):
            if not isinstance(c, dict):
                print(f'      [{j}] tipo nao-dict: {type(c).__name__}')
                continue
            chaves = sorted(c.keys())
            todas_chaves.update(chaves)
            print(f'      [{j}] chaves: {chaves}')

            tem_name = 'name' in c and c.get('name')
            tem_id = 'id' in c and c.get('id') is not None

            tipo_id = type(c.get('id')).__name__
            tipo_name = type(c.get('name')).__name__ if 'name' in c else '(ausente)'
            len_name = len(c['name']) if isinstance(c.get('name'), str) else None

            print(f'           id      : tipo={tipo_id}, presente={tem_id}')
            print(f'           name    : tipo={tipo_name}, presente={bool(tem_name)}, len={len_name}')

            if tem_name and tem_id:
                com_ambos += 1
            if tem_name:
                com_name += 1
            if tem_id:
                com_id += 1

            if c.get('id') == CLIENTE_PILOTO_ID:
                cliente_aparece_no_array += 1
                print(f'           >> EH O CLIENTE PILOTO (id {CLIENTE_PILOTO_ID})')

        # contagem por qtd de customers no lawsuit
        contagem_por_qtd[len(custs)] = contagem_por_qtd.get(len(custs), 0) + 1
        print()

    # AMPLIACAO: contar cliente em todos os 132 (so id, sem expor nada)
    aparece_em = 0
    for law in lawsuits:
        custs = law.get('customers') or []
        if any(isinstance(c, dict) and c.get('id') == CLIENTE_PILOTO_ID for c in custs):
            aparece_em += 1

    print('=' * 64)
    print('RESUMO DA AMOSTRAGEM')
    print('=' * 64)
    print(f'  Chaves unicas vistas em customers[i]: {sorted(todas_chaves)}')
    print(f'  Customers totais inspecionados      : {com_id} ids, {com_name} names, {com_ambos} ambos')
    print(f'  Cliente piloto aparece no array (amostra) : {cliente_aparece_no_array}/{LAWSUITS_A_INSPECIONAR}')
    print(f'  Cliente piloto aparece em (TODOS 132 lawsuits): {aparece_em}/{len(lawsuits)}')
    print(f'  Distribuicao de tamanho do array (amostra): {contagem_por_qtd}')

    # Distribuicao em todos os 132
    print()
    print('Distribuicao da quantidade de customers por lawsuit (TODOS 132):')
    contagem_geral = {}
    for law in lawsuits:
        custs = law.get('customers') or []
        n = len(custs) if isinstance(custs, list) else -1
        contagem_geral[n] = contagem_geral.get(n, 0) + 1
    for n in sorted(contagem_geral.keys()):
        print(f'  {n} customer(s): {contagem_geral[n]} lawsuit(s)')

    return 0


if __name__ == '__main__':
    sys.exit(main())
