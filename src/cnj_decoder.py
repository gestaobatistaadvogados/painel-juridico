"""
Decodificador de Tribunal a partir do numero CNJ.

Estrutura padrao CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO (20 digitos uteis)
  N x 7 = sequencial
  D x 2 = digito verificador
  A x 4 = ano
  J x 1 = segmento da Justica
  T x 2 = codigo do tribunal
  O x 4 = origem (vara/comarca) — nao usada nesta etapa

Sem dependencias externas. Sem chamadas de rede.

Indices (zero-based) apos remover separadores:
  J  = digitos[13]
  TR = digitos[14:16]
"""


TRIBUNAIS = {
    "1": {  # Supremo Tribunal Federal
        "00": "STF",
    },
    "2": {  # Conselho Nacional de Justica
        "00": "CNJ",
    },
    "3": {  # Superior Tribunal de Justica
        "00": "STJ",
    },
    "4": {  # Justica Federal
        "01": "TRF1", "02": "TRF2", "03": "TRF3",
        "04": "TRF4", "05": "TRF5", "06": "TRF6",
    },
    "5": {  # Justica do Trabalho
        "00": "TST",
        "01": "TRT1",  "02": "TRT2",  "03": "TRT3",
        "04": "TRT4",  "05": "TRT5",  "06": "TRT6",
        "07": "TRT7",  "08": "TRT8",  "09": "TRT9",
        "10": "TRT10", "11": "TRT11", "12": "TRT12",
        "13": "TRT13", "14": "TRT14", "15": "TRT15",
        "16": "TRT16", "17": "TRT17", "18": "TRT18",
        "19": "TRT19", "20": "TRT20", "21": "TRT21",
        "22": "TRT22", "23": "TRT23", "24": "TRT24",
    },
    "6": {  # Justica Eleitoral
        "00": "TSE",
    },
    "7": {  # Justica Militar da Uniao
        "00": "STM",
    },
    "8": {  # Justica Estadual (TJs)
        "01": "TJAC", "02": "TJAL", "03": "TJAP",
        "04": "TJAM", "05": "TJBA", "06": "TJCE",
        "07": "TJDFT", "08": "TJES", "09": "TJGO",
        "10": "TJMA", "11": "TJMT", "12": "TJMS",
        "13": "TJMG", "14": "TJPA", "15": "TJPB",
        "16": "TJPR", "17": "TJPE", "18": "TJPI",
        "19": "TJRJ", "20": "TJRN", "21": "TJRS",
        "22": "TJRO", "23": "TJRR", "24": "TJSC",
        "25": "TJSE", "26": "TJSP", "27": "TJTO",
    },
    "9": {  # Justica Militar Estadual
        "13": "TJMMG", "21": "TJMRS", "26": "TJMSP",
    },
}

INDEFINIDO = "—"


def decodificar_tribunal(process_number):
    """Devolve a sigla do tribunal a partir do numero CNJ.

    Aceita formatos com ou sem separadores. Retorna '—' se:
      - input vazio/None
      - apos limpeza, nao tem 20 digitos
      - segmento (J) ou codigo (TR) nao reconhecidos
    Nao levanta excecao para entradas invalidas.
    """
    if not process_number:
        return INDEFINIDO
    digitos = ''.join(ch for ch in str(process_number) if ch.isdigit())
    if len(digitos) != 20:
        return INDEFINIDO
    j = digitos[13]
    tr = digitos[14:16]
    return TRIBUNAIS.get(j, {}).get(tr, INDEFINIDO)


def parse_segmento(numero_cnj):
    """Extrai o digito J (segmento) de um numero CNJ.

    Layout CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO  (20 digitos uteis)
    J fica no indice 13 do string de digitos.

    Retorna o digito como string ('1'..'9') ou None se invalido.
    """
    if not numero_cnj:
        return None
    digitos = ''.join(ch for ch in str(numero_cnj) if ch.isdigit())
    if len(digitos) != 20:
        return None
    return digitos[13]


def area_por_segmento(j_segmento):
    """Mapeia o digito J para uma chave canonica de area.

    Caminho C HIBRIDO: o gerador chama esta funcao primeiro. Se ela
    retorna uma chave (J=4/5/6/7/9/2), o CNJ vence sobre o group
    do ADVBox. Se retorna None (J=1/3/8 ou ausente), o gerador
    consulta o `group` cru.

    Mapeamento:
      J=1 STF                     -> None  (default seguro: usa group)
      J=2 CNJ                     -> ADMINISTRATIVO_FEDERAL
      J=3 STJ                     -> None  (recurso pode ser de qq area)
      J=4 Justica Federal         -> ADMINISTRATIVO_FEDERAL
      J=5 Justica do Trabalho     -> SOCIAL/PREV-TRAB
      J=6 Justica Eleitoral       -> ELEITORAL
      J=7 Justica Militar Uniao   -> MILITAR
      J=8 Justica Estadual        -> None  (group distingue civel/familia/etc)
      J=9 Justica Militar Estad   -> MILITAR
    """
    if j_segmento == '4' or j_segmento == '2':
        return 'ADMINISTRATIVO_FEDERAL'
    if j_segmento == '5':
        return 'SOCIAL/PREV-TRAB'
    if j_segmento == '6':
        return 'ELEITORAL'
    if j_segmento in ('7', '9'):
        return 'MILITAR'
    # J=1 (STF), J=3 (STJ), J=8 (Estadual), invalido/None: ambiguo
    return None


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    casos = [
        ("0031037-75.2019.8.19.0066", "TJRJ"),
        ("0801234-56.2024.8.09.0001", "TJGO"),
        ("0000553-98.2026.5.18.0005", "TRT18"),
        ("4000104-33.2026.8.26.0059", "TJSP"),
        ("INC-2025-001", "—"),
        ("", "—"),
        (None, "—"),
    ]
    falhas = 0
    for inp, esperado in casos:
        obtido = decodificar_tribunal(inp)
        ok = obtido == esperado
        if not ok:
            falhas += 1
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {inp!r:40s} -> {obtido} (esperado: {esperado})")
    print()
    print(f"  Total: {len(casos)} casos | Falhas: {falhas}")
    sys.exit(0 if falhas == 0 else 1)
