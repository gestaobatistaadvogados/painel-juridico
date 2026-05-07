"""
Teste isolado da conexao com a API ADVBox.

Faz uma chamada minima a get_customers(page=1, per_page=5) e imprime
apenas ID, nome e tipo (PF/PJ) — sem dados pessoais sensiveis.
"""

import sys
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
    """Aceita varias formas comuns de resposta paginada."""
    if isinstance(resposta, list):
        return resposta
    if isinstance(resposta, dict):
        for chave in ('data', 'customers', 'items', 'results'):
            valor = resposta.get(chave)
            if isinstance(valor, list):
                return valor
    return []


def _detectar_nome(cliente):
    for campo in ('name', 'nome', 'name_complete', 'razao_social', 'company_name'):
        valor = cliente.get(campo)
        if valor:
            return str(valor)
    return '(sem nome)'


def _detectar_tipo(cliente):
    """Tenta inferir PF/PJ a partir de campos conhecidos."""
    for campo in ('type_customer', 'kind', 'person_type', 'type'):
        valor = cliente.get(campo)
        if valor is None:
            continue
        s = str(valor).strip().upper()
        if s in ('PF', 'F', 'FISICA', 'PESSOA FISICA', '1'):
            return 'PF'
        if s in ('PJ', 'J', 'JURIDICA', 'PESSOA JURIDICA', '2'):
            return 'PJ'
        return s
    return '?'


def main():
    print('Testando conexao com API ADVBox...')
    try:
        cliente_api = AdvboxClient()
        resposta = cliente_api.get_customers(page=1, per_page=5)
    except AdvboxAuthError as e:
        print(f'Falha no teste: {e}')
        print('Sugestao: verifique se ADVBOX_API_TOKEN no .env esta correto e ativo.')
        return 1
    except AdvboxError as e:
        print(f'Falha no teste: {e}')
        return 1
    except Exception as e:
        print(f'Falha no teste: erro inesperado ({type(e).__name__}): {e}')
        return 1

    lista = _extrair_lista(resposta)[:5]
    print(f'Registros retornados nesta pagina: {len(lista)}')

    if lista and isinstance(lista[0], dict):
        print()
        print('Chaves do primeiro registro:', sorted(lista[0].keys()))
        print()
        candidatos = (
            'type', 'kind', 'type_customer', 'customer_type', 'person_type',
            'is_client', 'client', 'relation', 'relation_type', 'role',
            'category', 'cpf_cnpj_type', 'document_type',
        )
        for campo in candidatos:
            if any(campo in r for r in lista if isinstance(r, dict)):
                amostra = [r.get(campo) for r in lista if isinstance(r, dict)]
                print(f'  Campo "{campo}" presente. Valores nos 5 registros: {amostra}')
        print()

    for i, c in enumerate(lista, 1):
        if not isinstance(c, dict):
            print(f'  [{i}] formato inesperado: {type(c).__name__}')
            continue
        cid = c.get('id', '?')
        nome = _detectar_nome(c)
        tipo = _detectar_tipo(c)
        print(f'  [{i}] ID={cid} | Tipo={tipo} | Nome={nome}')

    print('Teste concluido com sucesso!')
    return 0


if __name__ == '__main__':
    sys.exit(main())
