"""
Diagnostico estatistico de /customers (100 registros).

Imprime apenas contagens e percentuais — sem nomes, IDs, documentos
ou qualquer dado pessoal. Os valores categoricos exibidos (origin,
civil_status) sao classificacoes de schema, nao dados sensiveis.
"""

import re
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


def _extrair_lista(resposta):
    if isinstance(resposta, list):
        return resposta
    if isinstance(resposta, dict):
        for chave in ('data', 'customers', 'items', 'results'):
            valor = resposta.get(chave)
            if isinstance(valor, list):
                return valor
    return []


def _digitos(valor):
    if not valor:
        return ''
    return re.sub(r'\D', '', str(valor))


def _preenchido(valor):
    if valor is None:
        return False
    if isinstance(valor, str) and not valor.strip():
        return False
    return True


def _rotulo_categorico(valor):
    """Reduz origin/civil_status a uma string categorica."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return '(vazio)'
    if isinstance(valor, dict):
        for k in ('name', 'nome', 'description', 'label'):
            if valor.get(k):
                return str(valor[k])
        return f'(dict sem nome: chaves={sorted(valor.keys())})'
    return str(valor)


def _pct(parte, total):
    return f'{(100 * parte / total):.1f}%' if total else '-'


def main():
    print('Buscando 100 customers (page=1, per_page=100)...')
    try:
        cliente = AdvboxClient()
        resposta = cliente.get_customers(page=1, per_page=100)
    except AdvboxAuthError as e:
        print(f'Falha: {e}')
        return 1
    except AdvboxError as e:
        print(f'Falha: {e}')
        return 1

    lista = _extrair_lista(resposta)
    total = len(lista)
    print(f'Registros recebidos: {total}')
    if total == 0:
        return 1
    print()

    doc_11 = doc_14 = doc_outros = 0
    id_11 = id_14 = id_vazio = id_outros = 0
    sem_proc = com_proc = 0
    com_birthdate = com_occupation = 0
    origins = Counter()
    civis = Counter()

    for r in lista:
        if not isinstance(r, dict):
            continue

        d = _digitos(r.get('document'))
        if len(d) == 11:
            doc_11 += 1
        elif len(d) == 14:
            doc_14 += 1
        else:
            doc_outros += 1

        i = _digitos(r.get('identification'))
        if i == '':
            id_vazio += 1
        elif len(i) == 11:
            id_11 += 1
        elif len(i) == 14:
            id_14 += 1
        else:
            id_outros += 1

        lawsuits = r.get('lawsuits')
        if isinstance(lawsuits, list) and len(lawsuits) > 0:
            com_proc += 1
        else:
            sem_proc += 1

        if _preenchido(r.get('birthdate')):
            com_birthdate += 1
        if _preenchido(r.get('occupation')):
            com_occupation += 1

        origins[_rotulo_categorico(r.get('origin'))] += 1
        civis[_rotulo_categorico(r.get('civil_status'))] += 1

    print('=== document (CPF/CNPJ) ===')
    print(f'  11 digitos (provavel PF): {doc_11} ({_pct(doc_11, total)})')
    print(f'  14 digitos (provavel PJ): {doc_14} ({_pct(doc_14, total)})')
    print(f'  vazio/outros formatos:    {doc_outros} ({_pct(doc_outros, total)})')
    print()

    print('=== identification ===')
    print(f'  11 digitos:               {id_11} ({_pct(id_11, total)})')
    print(f'  14 digitos:               {id_14} ({_pct(id_14, total)})')
    print(f'  vazio:                    {id_vazio} ({_pct(id_vazio, total)})')
    print(f'  outros formatos:          {id_outros} ({_pct(id_outros, total)})')
    print()

    print('=== lawsuits (processos vinculados) ===')
    print(f'  sem processos:            {sem_proc} ({_pct(sem_proc, total)})')
    print(f'  com 1+ processos:         {com_proc} ({_pct(com_proc, total)})')
    print()

    print('=== campos PF preenchidos ===')
    print(f'  birthdate preenchido:     {com_birthdate} ({_pct(com_birthdate, total)})')
    print(f'  occupation preenchido:    {com_occupation} ({_pct(com_occupation, total)})')
    print()

    print('=== top 10 origins ===')
    for valor, qtd in origins.most_common(10):
        print(f'  {qtd:3d} ({_pct(qtd, total):>5}) | {valor}')
    print()

    print('=== top 10 civil_status ===')
    for valor, qtd in civis.most_common(10):
        print(f'  {qtd:3d} ({_pct(qtd, total):>5}) | {valor}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
