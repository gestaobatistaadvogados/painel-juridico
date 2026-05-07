"""
Diagnostico de filtro sobre a base completa de /customers (5229 esperados).

Imprime apenas contagens — sem nomes, IDs ou dados pessoais.
"""

import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from src.advbox_client import AdvboxClient, AdvboxAuthError, AdvboxError
except ImportError:
    from advbox_client import AdvboxClient, AdvboxAuthError, AdvboxError


EXCLUIR = {'PARTE CONTRÁRIA', 'CORRÉU'}


def _origin_str(valor):
    if valor is None:
        return ''
    if isinstance(valor, dict):
        for k in ('name', 'nome', 'description', 'label'):
            if valor.get(k):
                return str(valor[k]).strip()
        return ''
    return str(valor).strip()


def _tem_processo(r):
    lawsuits = r.get('lawsuits')
    return isinstance(lawsuits, list) and len(lawsuits) > 0


def main():
    print('Varrendo /customers em lotes de 1000 (limit/offset)...')
    try:
        cliente = AdvboxClient()
    except AdvboxError as e:
        print(f'Falha: {e}')
        return 1

    origins = Counter()
    migracao_total = migracao_com_proc = migracao_sem_proc = 0
    cliente_total = cliente_com_proc = cliente_sem_proc = 0
    opc_a = opc_b = opc_c = 0
    total = 0

    try:
        for r in cliente.iter_customers(lote=1000):
            if not isinstance(r, dict):
                continue
            total += 1

            origin = _origin_str(r.get('origin')).upper()
            origins[origin or '(vazio)'] += 1
            com_proc = _tem_processo(r)

            if origin == 'MIGRAÇÃO':
                migracao_total += 1
                if com_proc:
                    migracao_com_proc += 1
                else:
                    migracao_sem_proc += 1

            if origin == 'CLIENTE':
                cliente_total += 1
                if com_proc:
                    cliente_com_proc += 1
                else:
                    cliente_sem_proc += 1

            if origin == 'CLIENTE':
                opc_a += 1
            if origin not in EXCLUIR:
                opc_b += 1
            if origin == 'CLIENTE' or (origin == 'MIGRAÇÃO' and com_proc):
                opc_c += 1

            if total % 1000 == 0:
                print(f'  ... {total} processados')
    except (AdvboxAuthError, AdvboxError) as e:
        print(f'Falha durante varredura: {e}')
        return 1

    print(f'Total varrido: {total}')
    print()

    def pct(p):
        return f'{(100*p/total):.1f}%' if total else '-'

    print('=== Distribuicao de origin ===')
    for valor, qtd in origins.most_common():
        print(f'  {qtd:5d} ({pct(qtd):>6}) | {valor}')
    print()

    print('=== origin == "MIGRAÇÃO" ===')
    print(f'  Total:                  {migracao_total} ({pct(migracao_total)})')
    print(f'  Com lawsuits NAO vazia: {migracao_com_proc}')
    print(f'  Com lawsuits vazia:     {migracao_sem_proc}')
    print()

    print('=== origin == "CLIENTE" ===')
    print(f'  Total:                  {cliente_total} ({pct(cliente_total)})')
    print(f'  Com lawsuits NAO vazia: {cliente_com_proc}')
    print(f'  Com lawsuits vazia:     {cliente_sem_proc}')
    print()

    print('=== Resumo das opcoes de filtro ===')
    print(f'  Opcao A (origin == CLIENTE):                          {opc_a} ({pct(opc_a)})')
    print(f'  Opcao B (origin not in {{PARTE CONTRARIA, CORREU}}):    {opc_b} ({pct(opc_b)})')
    print(f'  Opcao C (CLIENTE OU MIGRACAO+lawsuits):               {opc_c} ({pct(opc_c)})')

    return 0


if __name__ == '__main__':
    sys.exit(main())
