"""
Ferramenta interativa para adicionar cliente novo ao
config/clientes.json a partir de CPF ou CNPJ.

Uso:
    python src/adicionar_cliente.py 12345678000199
    python src/adicionar_cliente.py 12345678909
    python src/adicionar_cliente.py 12.345.678/0001-99

A ferramenta:
  - Detecta tipo (PF/PJ) pelo numero de digitos (11 ou 14)
  - Busca no ADVBox via GET /customers?identification=<digitos>
  - Mostra dados encontrados (nome, ID, origin, qtd processos)
  - Detecta cliente duplicado (e oferece reativar)
  - Pede nome curto + departamento
  - Gera slug ofuscado (painel-{nome}-{ano}-{4hex})
  - Adiciona em config/clientes.json com ativo=true
  - Sugere proximos passos

So lê e escreve config/clientes.json. Nao toca em outros arquivos
do projeto.
"""

import json
import random
import re
import string
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Adiciona src/ ao path (mesmo padrao dos demais scripts)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from advbox_client import AdvboxClient, AdvboxError, AdvboxAuthError


RAIZ = Path(__file__).resolve().parent.parent
CONFIG_CLIENTES = RAIZ / 'config' / 'clientes.json'

DEPARTAMENTOS = {
    '1': 'direito_privado',
    '2': 'direito_imobiliario',
    '3': 'direito_publico',
    '4': 'direito_criminal',
}
DEPARTAMENTOS_LABEL = {
    'direito_privado': 'Direito Privado',
    'direito_imobiliario': 'Direito Imobiliario',
    'direito_publico': 'Direito Publico',
    'direito_criminal': 'Direito Criminal',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def limpar_digitos(texto):
    return re.sub(r'\D', '', str(texto or ''))


def slugify_nome(nome):
    """Tira acentos, mantem so [a-z0-9], retorna max 25 chars lower."""
    nfkd = unicodedata.normalize('NFKD', str(nome or ''))
    sem_acento = ''.join(c for c in nfkd if not unicodedata.combining(c))
    limpo = re.sub(r'[^a-zA-Z0-9]', '', sem_acento)
    return limpo.lower()[:25]


def gerar_slug(nome_curto, ano=None):
    """Slug no padrao painel-{nome}-{ano}-{4hex random}."""
    if ano is None:
        ano = datetime.now().year
    nome_norm = slugify_nome(nome_curto) or 'cliente'
    sufixo = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f'painel-{nome_norm}-{ano}-{sufixo}'


def carregar_clientes_json():
    if not CONFIG_CLIENTES.exists():
        raise FileNotFoundError(f'{CONFIG_CLIENTES} nao encontrado')
    return json.loads(CONFIG_CLIENTES.read_text(encoding='utf-8'))


def salvar_clientes_json(dados):
    CONFIG_CLIENTES.write_text(
        json.dumps(dados, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )


def perguntar(prompt, validador=None):
    """input() com validacao opcional. Retorna string limpa."""
    while True:
        try:
            resposta = input(prompt).strip()
        except EOFError:
            print('\n(stdin fechado — cancelando)')
            sys.exit(0)
        if validador is None:
            return resposta
        ok, msg = validador(resposta)
        if ok:
            return resposta
        print(f'  AVISO: {msg}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # 1) Argumento da linha de comando
    if len(sys.argv) < 2:
        print('Uso: python src/adicionar_cliente.py <CPF ou CNPJ>')
        print('Exemplo: python src/adicionar_cliente.py 12345678000199')
        return 1

    ident_raw = sys.argv[1]
    digitos = limpar_digitos(ident_raw)

    # 2) Validar tipo
    if len(digitos) == 11:
        tipo_pessoa = 'PF'
        tipo_label = 'Pessoa Fisica (CPF)'
    elif len(digitos) == 14:
        tipo_pessoa = 'PJ'
        tipo_label = 'Pessoa Juridica (CNPJ)'
    else:
        print(f'ERRO: numero de digitos invalido: {len(digitos)}')
        print('   Esperado: 11 (CPF) ou 14 (CNPJ).')
        return 1

    # Mascara para nao logar identification crua no console
    ident_mascarado = (
        f'{digitos[:4]}{"*" * (len(digitos) - 6)}{digitos[-2:]}'
        if len(digitos) >= 6 else digitos
    )
    print()
    print(f'Buscando {tipo_label} {ident_mascarado} no ADVBox...')
    print()

    # 3) Buscar via ADVBox (filtro `?identification=` ja validado em F2)
    try:
        client = AdvboxClient()
    except AdvboxError as e:
        print(f'ERRO ao inicializar AdvboxClient: {e}')
        return 1

    try:
        resp = client._request(
            'customers',
            params={'identification': digitos, 'limit': 10, 'offset': 0},
        )
    except AdvboxAuthError as e:
        print(f'ERRO de autenticacao: {e}')
        print('   Verifique ADVBOX_API_TOKEN no arquivo .env.')
        return 1
    except AdvboxError as e:
        print(f'ERRO ao consultar ADVBox: {e}')
        return 1

    data = resp.get('data') if isinstance(resp, dict) else None
    if not isinstance(data, list) or not data:
        print('ERRO: cliente nao encontrado no ADVBox.')
        print('   Verifique se o cadastro existe e se o token tem permissao.')
        return 1

    # Casa exato (caso a API retorne resultado nao-filtrado por garantia)
    cliente_match = None
    for c in data:
        if isinstance(c, dict) and limpar_digitos(c.get('identification')) == digitos:
            cliente_match = c
            break
    if cliente_match is None:
        cliente_match = data[0]
        print('AVISO: API retornou resultado nao-exato. Usando primeiro item.')

    nome = cliente_match.get('name') or '(sem nome)'
    id_advbox = cliente_match.get('id')
    origin = cliente_match.get('origin') or '?'
    n_lawsuits = (
        len(cliente_match.get('lawsuits') or [])
        if isinstance(cliente_match.get('lawsuits'), list)
        else 0
    )

    # 4) Mostrar dados encontrados
    print('Cliente encontrado:')
    print()
    print(f'   Nome:            {nome}')
    print(f'   ID ADVBox:       {id_advbox}')
    print(f'   Tipo:            {tipo_label}')
    print(f'   Origem (ADVBox): {origin}')
    print(f'   Processos:       {n_lawsuits}')
    print()

    # 5) Carregar clientes.json e detectar duplicata
    clientes_json = carregar_clientes_json()
    clientes_lista = clientes_json.get('clientes', [])

    for c_existente in clientes_lista:
        if c_existente.get('id_advbox') == id_advbox:
            print('AVISO: este cliente JA EXISTE em config/clientes.json:')
            print(f'    nome_curto: {c_existente.get("nome_curto")}')
            print(f'    slug_url:   {c_existente.get("slug_url")}')
            print(f'    ativo:      {c_existente.get("ativo")}')
            print()
            resp_acao = perguntar(
                'Deseja apenas REATIVAR (s) ou cancelar (n)? [s/n]: '
            )
            if resp_acao.lower() == 's':
                if c_existente.get('ativo'):
                    print('Cliente ja esta ativo. Nada a fazer.')
                    return 0
                c_existente['ativo'] = True
                salvar_clientes_json(clientes_json)
                print()
                print('Cliente REATIVADO em config/clientes.json')
                print()
                print('Proximo passo: gerar painel deste cliente:')
                print('   python src/gerador_producao.py')
                return 0
            else:
                print('Cancelado.')
                return 0

    # 6) Pedir nome curto
    nome_curto_default = (slugify_nome(nome).split()[0:1] or [''])[0][:15] or 'cliente'
    print(f'Sugira um "nome curto" para usar na URL.')
    print(f'Exemplos: "amparo", "rgp", "prefuberaba".')
    nome_curto = perguntar(f'Nome curto [{nome_curto_default}]: ')
    if not nome_curto:
        nome_curto = nome_curto_default
    nome_curto = slugify_nome(nome_curto) or nome_curto_default

    # 7) Pedir departamento
    print()
    print('Departamentos disponiveis:')
    print('  1 = Direito Privado')
    print('  2 = Direito Imobiliario')
    print('  3 = Direito Publico')
    print('  4 = Direito Criminal')
    dep_num = perguntar(
        'Departamento (1/2/3/4): ',
        validador=lambda r: (
            (True, '') if r in DEPARTAMENTOS
            else (False, 'Digite 1, 2, 3 ou 4.')
        ),
    )
    departamento = DEPARTAMENTOS[dep_num]

    # 8) Gerar slug
    slug_url = gerar_slug(nome_curto)
    # Defesa: garantir slug nao colide com existente
    slugs_existentes = {c.get('slug_url') for c in clientes_lista}
    while slug_url in slugs_existentes:
        slug_url = gerar_slug(nome_curto)

    # 9) Resumo final + confirmacao
    print()
    print('RESUMO PARA CONFIRMACAO:')
    print()
    print(f'   Nome completo:   {nome}')
    print(f'   Nome curto:      {nome_curto}')
    print(f'   ID ADVBox:       {id_advbox}')
    print(f'   Departamento:    {DEPARTAMENTOS_LABEL[departamento]}')
    print(f'   Slug (URL):      {slug_url}')
    print(f'   Ativo:           true')
    print()

    resp_conf = perguntar('Confirma adicionar este cliente? [s/n]: ')
    if resp_conf.lower() != 's':
        print('Cancelado. Nada foi salvo.')
        return 0

    # 10) Adicionar e salvar
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
    salvar_clientes_json(clientes_json)

    print()
    print('Cliente adicionado com sucesso a config/clientes.json')
    print()
    print('Proximos passos:')
    print('   1. Gerar o painel deste cliente:')
    print('      python src/gerador_producao.py')
    print('   2. Regenerar painel-interno (para listar este cliente):')
    print('      python src/gerador_interno.py')
    print('   3. Conferir visualmente:')
    print(f'      start clientes\\{slug_url}\\index.html')
    return 0


if __name__ == '__main__':
    sys.exit(main())
