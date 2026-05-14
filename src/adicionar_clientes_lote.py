"""
Cadastro em lote a partir de arquivo texto.

Uso:
    python src/adicionar_clientes_lote.py clientes_para_adicionar.txt

Formato do arquivo (separador ; e linhas comentario com #):
    # Comentario
    CPF/CNPJ ; departamento ; nome_curto
    12345678000199 ; 2 ; empresa-alpha

Departamentos:
  1 = direito_privado
  2 = direito_imobiliario
  3 = direito_publico
  4 = direito_criminal

A ferramenta:
  - Le todas as linhas validas do arquivo
  - Para cada cadastro, faz:
      - Validacao de digitos (11 ou 14)
      - Busca no ADVBox via ?identification=
      - Deteccao de duplicata em config/clientes.json
      - Adicao em config/clientes.json
  - Imprime relatorio final por status:
      OK / DUPLICADO / NAO_ENCONTRADO /
      DIGITOS_INVALIDOS / DEPARTAMENTO_INVALIDO / ERRO_API
"""

import random
import re
import string
import sys
import pathlib
import unicodedata
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Reaproveitar funcoes do adicionar_cliente.py
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from adicionar_cliente import (
    limpar_digitos,
    slugify_nome,
    gerar_slug,
    carregar_clientes_json,
    salvar_clientes_json,
    DEPARTAMENTOS,
    DEPARTAMENTOS_LABEL,
)
from advbox_client import AdvboxClient, AdvboxError, AdvboxAuthError
from dotenv import load_dotenv

load_dotenv()


# slugify_nome do adicionar_cliente.py remove hifens. Para o lote, queremos
# preservar hifens em nome_curto (ex.: "mybroker-alphamall") para que apareca
# legivel no slug final. Estes helpers existem apenas no escopo do lote;
# adicionar_cliente.py (interativo) continua intocado.
def sanitizar_nome_curto_lote(texto):
    """Permite [a-z0-9-], colapsa hifens duplicados e trim. Max 40 chars."""
    nfkd = unicodedata.normalize('NFKD', str(texto or ''))
    sem_acento = ''.join(c for c in nfkd if not unicodedata.combining(c))
    limpo = re.sub(r'[^a-zA-Z0-9-]', '', sem_acento)
    limpo = re.sub(r'-+', '-', limpo).strip('-')
    return limpo.lower()[:40]


def gerar_slug_lote(nome_curto, ano=None):
    """Slug painel-{nome}-{ano}-{4hex} preservando hifens em nome_curto."""
    if ano is None:
        ano = datetime.now().year
    nome_norm = sanitizar_nome_curto_lote(nome_curto) or 'cliente'
    sufixo = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f'painel-{nome_norm}-{ano}-{sufixo}'


def parsear_arquivo(caminho_arquivo):
    """
    Le o arquivo e retorna lista de dicts
    {linha_num, ident_cru, dep_num, nome_curto}.
    Ignora linhas vazias e comecadas com #.
    """
    path = pathlib.Path(caminho_arquivo)
    try:
        f = path.open(encoding='utf-8')
    except FileNotFoundError:
        print(f'ERRO: arquivo nao encontrado: {caminho_arquivo}')
        sys.exit(1)

    entradas = []
    with f:
        for num, linha in enumerate(f, start=1):
            linha = linha.strip()
            if not linha or linha.startswith('#'):
                continue
            partes = [p.strip() for p in linha.split(';')]
            if len(partes) < 2:
                print(f'AVISO: linha {num} malformada (faltam campos): {linha}')
                continue
            ident = partes[0]
            dep = partes[1]
            nome_curto = partes[2] if len(partes) >= 3 and partes[2] else None
            entradas.append({
                'linha_num': num,
                'ident_cru': ident,
                'dep_num': dep,
                'nome_curto': nome_curto,
            })
    return entradas


def mascarar(digitos):
    if len(digitos) >= 6:
        return f'{digitos[:4]}{"*" * (len(digitos) - 6)}{digitos[-2:]}'
    return digitos


def processar_cliente(entrada, client, clientes_json):
    """Processa uma unica entrada. Retorna dict com status."""
    ident = entrada['ident_cru']
    digitos = limpar_digitos(ident)

    if len(digitos) not in (11, 14):
        return {
            'status': 'DIGITOS_INVALIDOS',
            'ident_cru': ident,
            'detalhe': f'{len(digitos)} digitos (esperado 11 ou 14)',
        }

    if entrada['dep_num'] not in DEPARTAMENTOS:
        return {
            'status': 'DEPARTAMENTO_INVALIDO',
            'ident_cru': ident,
            'detalhe': f'departamento "{entrada["dep_num"]}" nao existe',
        }
    departamento = DEPARTAMENTOS[entrada['dep_num']]

    try:
        resp = client._request(
            'customers',
            params={'identification': digitos, 'limit': 10, 'offset': 0},
        )
    except AdvboxAuthError:
        return {
            'status': 'ERRO_API',
            'ident_cru': ident,
            'detalhe': 'token invalido',
        }
    except AdvboxError as e:
        return {
            'status': 'ERRO_API',
            'ident_cru': ident,
            'detalhe': str(e),
        }

    data = resp.get('data', []) if isinstance(resp, dict) else []

    cliente_match = None
    for c in data:
        if isinstance(c, dict) and limpar_digitos(c.get('identification', '')) == digitos:
            cliente_match = c
            break

    if cliente_match is None:
        return {
            'status': 'NAO_ENCONTRADO',
            'ident_cru': ident,
            'detalhe': 'cliente ausente no ADVBox',
        }

    nome = cliente_match.get('name', '') or '(sem nome)'
    id_advbox = cliente_match.get('id')

    clientes_lista = clientes_json.get('clientes', [])
    for c_existente in clientes_lista:
        if c_existente.get('id_advbox') == id_advbox:
            return {
                'status': 'DUPLICADO',
                'ident_cru': ident,
                'nome': nome,
                'id_advbox': id_advbox,
                'detalhe': f'ja existe (slug {c_existente.get("slug_url")})',
            }

    default_curto = (slugify_nome(nome) or 'cliente')[:15]
    nome_curto_raw = entrada['nome_curto'] or default_curto
    nome_curto = sanitizar_nome_curto_lote(nome_curto_raw) or default_curto

    slugs_existentes = {c.get('slug_url') for c in clientes_lista}
    slug_url = gerar_slug_lote(nome_curto)
    while slug_url in slugs_existentes:
        slug_url = gerar_slug_lote(nome_curto)

    nova_entrada = {
        'id_advbox': id_advbox,
        'nome_curto': nome_curto,
        'departamento': departamento,
        'slug_url': slug_url,
        'ativo': True,
        'data_cadastro': datetime.now().strftime('%Y-%m-%d'),
    }
    clientes_lista.append(nova_entrada)
    clientes_json['clientes'] = clientes_lista

    return {
        'status': 'OK',
        'ident_cru': ident,
        'nome': nome,
        'id_advbox': id_advbox,
        'slug_url': slug_url,
        'nome_curto': nome_curto,
        'departamento': DEPARTAMENTOS_LABEL[departamento],
    }


def main():
    if len(sys.argv) < 2:
        print('Uso: python src/adicionar_clientes_lote.py <arquivo.txt>')
        sys.exit(1)

    caminho = sys.argv[1]
    entradas = parsear_arquivo(caminho)
    print()
    print(f'{len(entradas)} entradas encontradas em {caminho}')
    print()

    try:
        client = AdvboxClient()
    except AdvboxError as e:
        print(f'ERRO ao inicializar AdvboxClient: {e}')
        sys.exit(1)

    clientes_json = carregar_clientes_json()

    resultados = []
    icones = {
        'OK': 'OK',
        'DUPLICADO': 'DUP',
        'NAO_ENCONTRADO': 'NF ',
        'DIGITOS_INVALIDOS': 'INV',
        'DEPARTAMENTO_INVALIDO': 'DEP',
        'ERRO_API': 'ERR',
    }

    for i, entrada in enumerate(entradas, start=1):
        digitos = limpar_digitos(entrada['ident_cru'])
        ident_log = mascarar(digitos) if digitos else entrada['ident_cru']
        print(
            f'[{i:2d}/{len(entradas)}] Processando {ident_log}... ',
            end='',
            flush=True,
        )
        r = processar_cliente(entrada, client, clientes_json)
        resultados.append(r)
        marca = icones.get(r['status'], '?  ')
        print(f'[{marca}] {r["status"]}')

        # Salvar a cada cliente OK (defesa contra crash mid-loop)
        if r['status'] == 'OK':
            salvar_clientes_json(clientes_json)

    # Relatorio final
    print()
    print('=' * 60)
    print('RELATORIO FINAL')
    print('=' * 60)

    contagens = {}
    for r in resultados:
        contagens[r['status']] = contagens.get(r['status'], 0) + 1

    for status, n in sorted(contagens.items()):
        print(f'  {status:25s} : {n}')
    print(f'\n  TOTAL                     : {len(resultados)}')

    print()
    print('-' * 60)
    for r in resultados:
        s = r['status']
        if s == 'OK':
            print(f'  [OK]  {r["nome"][:40]:40s} -> {r["slug_url"]}')
        elif s == 'DUPLICADO':
            print(f'  [DUP] {r.get("nome", "")}: {r["detalhe"]}')
        else:
            print(f'  [ERR] {r["ident_cru"]}: {r["detalhe"]}')

    print()
    print('Proximos passos:')
    print('   1. python src/gerador_producao.py')
    print('   2. python src/gerador_interno.py')
    print('   3. git add -A && git commit + git push')


if __name__ == '__main__':
    main()
