"""
Auditoria de presenca e qualidade dos campos financeiros nos processos
do cliente piloto.

Le:
  - clientes/painel-piloto-pj-2026-n4q8/dados.json   (pos-whitelist)
  - cache/lawsuits_customer_13669008.json            (resposta crua da API)

Avalia 5 campos financeiros:
  contingency, fees_money, fees_expec, exit_execution, exit_production

Foco principal: `contingency` — saber se vale incluir "Valor da Causa"
no dashboard publico.

Saida:
  - Relatorio formatado em texto no console
  - Mesma saida em clientes/painel-piloto-pj-2026-n4q8/auditoria_financeiro.txt

Nao modifica gerador, whitelist, nem regera dados.
"""

import json
import statistics
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_DADOS = RAIZ / 'clientes' / 'painel-piloto-pj-2026-n4q8' / 'dados.json'
CAMINHO_CACHE = RAIZ / 'cache' / 'lawsuits_customer_13669008.json'
CAMINHO_RELATORIO = RAIZ / 'clientes' / 'painel-piloto-pj-2026-n4q8' / 'auditoria_financeiro.txt'

CAMPOS_FINANCEIROS = [
    'contingency',
    'fees_money',
    'fees_expec',
    'exit_execution',
    'exit_production',
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classificar_valor(v):
    """Retorna ('vazio', 'invalido', 'zerado', 'preenchido', valor_numerico_ou_None)."""
    if v is None:
        return 'vazio', None
    if isinstance(v, str) and v.strip() == '':
        return 'vazio', None
    try:
        n = float(str(v).replace(',', '.'))
    except (ValueError, TypeError):
        return 'invalido', None
    if n == 0:
        return 'zerado', 0.0
    return 'preenchido', n


def fmt_brl(valor):
    """Formata um numero como BRL: R$ 1.234,56"""
    if valor is None:
        return '—'
    s = f'{valor:,.2f}'
    # 1,234.56 -> 1.234,56
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {s}'


def linha_separadora(c='─', tam=72):
    return c * tam


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def carregar_dados_publico():
    if not CAMINHO_DADOS.exists():
        return None
    with CAMINHO_DADOS.open('r', encoding='utf-8') as f:
        return json.load(f)


def carregar_cache_lawsuits():
    if not CAMINHO_CACHE.exists():
        return None
    with CAMINHO_CACHE.open('r', encoding='utf-8') as f:
        envelope = json.load(f)
    api = envelope.get('data') if isinstance(envelope, dict) else None
    if isinstance(api, dict) and isinstance(api.get('data'), list):
        return api['data']
    return None


# ---------------------------------------------------------------------------
# Analise por campo
# ---------------------------------------------------------------------------

def analisar_campo(lawsuits, campo):
    total = len(lawsuits)
    contagem = {'vazio': 0, 'invalido': 0, 'zerado': 0, 'preenchido': 0}
    valores_preenchidos = []  # tuplas (valor, process_number, lawsuit_id)

    for law in lawsuits:
        v = law.get(campo)
        cat, num = classificar_valor(v)
        contagem[cat] += 1
        if cat == 'preenchido':
            valores_preenchidos.append((num, law.get('process_number') or '(sem numero)', law.get('id')))

    perc_util = 100.0 * contagem['preenchido'] / total if total else 0.0
    return {
        'total': total,
        'contagem': contagem,
        'valores_preenchidos': valores_preenchidos,
        'perc_util': perc_util,
    }


def relatorio_geral(saida, lawsuits):
    saida.append('')
    saida.append(linha_separadora('═'))
    saida.append('  AUDITORIA DE CAMPOS FINANCEIROS — CLIENTE PILOTO 13669008')
    saida.append(linha_separadora('═'))
    saida.append(f'  Fonte 1 (cru):    {CAMINHO_CACHE.relative_to(RAIZ)}')
    saida.append(f'  Fonte 2 (filtrado): {CAMINHO_DADOS.relative_to(RAIZ)}')
    saida.append(f'  Total de processos analisados: {len(lawsuits)}')
    saida.append('')


def relatorio_dados_publicos(saida, dados):
    saida.append(linha_separadora('═'))
    saida.append('  CHECAGEM 1 — Esses campos vazaram para o dados.json publico?')
    saida.append(linha_separadora('═'))
    if dados is None:
        saida.append('  (dados.json nao encontrado — pulando)')
        saida.append('')
        return
    processos = dados.get('processos') or []
    saida.append(f'  Processos no dados.json: {len(processos)}')
    saida.append('')
    encontrou_algum = False
    for campo in CAMPOS_FINANCEIROS:
        achou = sum(1 for p in processos if campo in p)
        if achou > 0:
            saida.append(f'  ⚠️  VAZAMENTO: campo "{campo}" presente em {achou} processos')
            encontrou_algum = True
        else:
            saida.append(f'  ✅ campo "{campo}" ausente do JSON publico (whitelist funcionando)')
    if not encontrou_algum:
        saida.append('')
        saida.append('  CONCLUSAO: nenhum campo financeiro vazou para o painel publico.')
        saida.append('  A whitelist em CAMPOS_LAWSUIT_PUBLICOS esta filtrando corretamente.')
    saida.append('')


def relatorio_resumo_por_campo(saida, lawsuits):
    saida.append(linha_separadora('═'))
    saida.append('  CHECAGEM 2 — Preenchimento dos 5 campos no cache cru da API')
    saida.append(linha_separadora('═'))
    saida.append('')
    cab = f'  {"Campo":<20} {"Total":>6} {"Preench.":>10} {"Zerado":>8} {"Vazio":>8} {"Inv.":>6} {"% util":>8}'
    saida.append(cab)
    saida.append('  ' + linha_separadora('─', 70))
    resumos = {}
    for campo in CAMPOS_FINANCEIROS:
        r = analisar_campo(lawsuits, campo)
        resumos[campo] = r
        c = r['contagem']
        linha = (
            f'  {campo:<20} '
            f'{r["total"]:>6} '
            f'{c["preenchido"]:>10} '
            f'{c["zerado"]:>8} '
            f'{c["vazio"]:>8} '
            f'{c["invalido"]:>6} '
            f'{r["perc_util"]:>7.1f}%'
        )
        saida.append(linha)
    saida.append('')
    return resumos


def relatorio_contingency(saida, resumo_contingency):
    saida.append(linha_separadora('═'))
    saida.append('  CHECAGEM 3 — Analise especifica de contingency (Valor da Causa)')
    saida.append(linha_separadora('═'))
    saida.append('')

    valores = resumo_contingency['valores_preenchidos']
    if not valores:
        saida.append('  Nenhum processo com contingency preenchido (>0).')
        saida.append('  CONCLUSAO: NAO ha dados para alimentar a coluna "Valor da Causa".')
        saida.append('')
        return

    nums = [v[0] for v in valores]
    n = len(nums)
    minimo = min(nums)
    maximo = max(nums)
    media = sum(nums) / n
    mediana = statistics.median(nums)
    soma = sum(nums)
    relevantes = sum(1 for x in nums if x >= 1000)

    saida.append(f'  Processos com contingency > 0:   {n} de {resumo_contingency["total"]}')
    saida.append(f'  Soma total acumulada:            {fmt_brl(soma)}')
    saida.append(f'  Minimo (nao-zero):               {fmt_brl(minimo)}')
    saida.append(f'  Maximo:                          {fmt_brl(maximo)}')
    saida.append(f'  Media:                           {fmt_brl(media)}')
    saida.append(f'  Mediana:                         {fmt_brl(mediana)}')
    saida.append(f'  Processos com contingency >= R$ 1.000: {relevantes}')
    saida.append('')

    # Top 5 e bottom 5
    valores_ord = sorted(valores, key=lambda x: x[0])
    top5 = valores_ord[-5:][::-1]   # 5 maiores em ordem decrescente
    bot5 = valores_ord[:5]          # 5 menores em ordem crescente

    saida.append('  -- 5 MAIORES VALORES --')
    for valor, pn, lid in top5:
        saida.append(f'    {fmt_brl(valor):>20}   processo {pn}   (id {lid})')
    saida.append('')

    saida.append('  -- 5 MENORES VALORES (nao-zero) --')
    for valor, pn, lid in bot5:
        saida.append(f'    {fmt_brl(valor):>20}   processo {pn}   (id {lid})')
    saida.append('')


def relatorio_recomendacao(saida, resumos):
    saida.append(linha_separadora('═'))
    saida.append('  RECOMENDACAO PARA O DASHBOARD')
    saida.append(linha_separadora('═'))
    saida.append('')

    rc = resumos.get('contingency')
    if rc is None:
        saida.append('  Nao foi possivel avaliar contingency.')
        saida.append('')
        return

    perc = rc['perc_util']
    n_uteis = rc['contagem']['preenchido']
    n_relevantes = sum(1 for v, _, _ in rc['valores_preenchidos'] if v >= 1000)

    saida.append(f'  contingency util: {n_uteis}/{rc["total"]} ({perc:.1f}%)')
    saida.append(f'  contingency relevante (>= R$ 1.000): {n_relevantes}/{rc["total"]} ({100.0*n_relevantes/rc["total"]:.1f}%)')
    saida.append('')

    if perc < 30:
        saida.append('  >>> Cobertura BAIXA. Incluir "Valor da Causa" no painel publico')
        saida.append('      mostraria "—" na maioria dos processos. Recomendo PULAR por')
        saida.append('      enquanto, ate que o escritorio normalize esse campo no ADVBox.')
    elif perc < 60:
        saida.append('  >>> Cobertura MEDIANA. Incluir e possivel mas requer fallback')
        saida.append('      visual claro para os processos sem valor (ex: "Nao informado").')
        saida.append('      Decisao: discutir com o socio.')
    else:
        saida.append('  >>> Cobertura BOA. Incluir "Valor da Causa" agrega informacao util.')
        saida.append('      Lembrete: a Regra de Ouro hoje veta `fees_*` e `contingency`.')
        saida.append('      Para incluir, sera necessario uma REVISAO documentada da')
        saida.append('      whitelist (analoga a revisao de partes_adversarias em 2026-05-07).')
    saida.append('')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    lawsuits = carregar_cache_lawsuits()
    if lawsuits is None:
        print(f'ERRO: nao consegui ler {CAMINHO_CACHE}')
        return 1

    dados_publico = carregar_dados_publico()

    saida = []
    relatorio_geral(saida, lawsuits)
    relatorio_dados_publicos(saida, dados_publico)
    resumos = relatorio_resumo_por_campo(saida, lawsuits)
    relatorio_contingency(saida, resumos['contingency'])
    relatorio_recomendacao(saida, resumos)
    saida.append(linha_separadora('═'))
    saida.append('  Fim do relatorio.')
    saida.append(linha_separadora('═'))

    texto = '\n'.join(saida)

    # Imprime no console
    print(texto)

    # Salva em arquivo
    CAMINHO_RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_RELATORIO.write_text(texto, encoding='utf-8')
    print()
    print(f'>>> Relatorio salvo em: {CAMINHO_RELATORIO.relative_to(RAIZ)}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
