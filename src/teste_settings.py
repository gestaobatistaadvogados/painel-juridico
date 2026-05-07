"""
Teste do endpoint /settings da API ADVBox.

Imprime apenas contagens (usuarios, fases, tipos de processo, categorias
financeiras) — nunca nomes, IDs, e-mails ou dados sensiveis.
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


def _contar_lista(obj, *caminho):
    """Navega por chaves aninhadas e retorna o tamanho da lista no caminho.

    Ex: _contar_lista(resp, 'financial', 'categories') ->
        len(resp['financial']['categories']).
    """
    atual = obj
    for chave in caminho:
        if not isinstance(atual, dict):
            return None
        atual = atual.get(chave)
    return len(atual) if isinstance(atual, list) else None


def _formatar(qtd):
    return str(qtd) if qtd is not None else 'nao encontrado na resposta'


def main():
    print('Testando endpoint /settings da API ADVBox...')
    try:
        cliente = AdvboxClient()
        resposta = cliente.get_settings()
    except AdvboxAuthError as e:
        if '401' in str(e):
            print(f'Falha no teste: {e}')
            print('Sugestao: token invalido ou expirado. Gere um novo token no painel ADVBox.')
        else:
            print(f'Falha no teste: {e}')
            print('Sugestao: token autenticou mas nao tem permissao para /settings.')
        return 1
    except AdvboxError as e:
        print(f'Falha no teste: {e}')
        return 1
    except Exception as e:
        print(f'Falha no teste: erro inesperado ({type(e).__name__}): {e}')
        return 1

    print('Conexao OK!')

    if isinstance(resposta, dict):
        print('Chaves de primeiro nivel:', sorted(resposta.keys()))
        financial = resposta.get('financial')
        if isinstance(financial, dict):
            print('Chaves de financial:', sorted(financial.keys()))
    else:
        print(f'Aviso: resposta nao e dict, e {type(resposta).__name__}')

    contagens = [
        ('Usuarios',                _contar_lista(resposta, 'users')),
        ('Origens de leads',        _contar_lista(resposta, 'origins')),
        ('Tipos de tarefa',         _contar_lista(resposta, 'tasks')),
        ('Fases processuais (stages)', _contar_lista(resposta, 'stages')),
        ('Tipos de processo',       _contar_lista(resposta, 'lawsuit_types')),
        ('Contas bancarias',        _contar_lista(resposta, 'financial', 'banks')),
        ('Categorias financeiras',  _contar_lista(resposta, 'financial', 'categories')),
        ('Centros de custo',        _contar_lista(resposta, 'financial', 'cost_centers')),
        ('Departamentos',           _contar_lista(resposta, 'financial', 'departments')),
    ]
    for rotulo, qtd in contagens:
        print(f'  {rotulo}: {_formatar(qtd)}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
