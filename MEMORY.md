# MEMORY.md — Documento de Retomada (Fase 2)

**Ultima atualizacao:** 2026-05-07 (mapping de categorias 90d revisto — 5 categorias acentuadas + Outras catch-all; bug de matching com acento corrigido; 263 → 0 em Outras)
**Proxima sessao:** retomar a partir da secao "ESTADO ATUAL DA SESSAO E PROXIMOS PASSOS" no fim deste arquivo.

---

## DECISAO DE PRODUTO — VISAO DE STATUS, NAO HISTORICO COMPLETO

**Decisao registrada em 2026-05-07.**

O dashboard do cliente mostra apenas os **10 andamentos mais recentes** de cada processo, somados a fase, status e tipo. Nao tenta replicar historico completo do tribunal. Razao: o cliente quer entender o **status atual** ("como meu processo esta?"), nao ler 87 movimentacoes. **Beneficio colateral:** o teto de 25 itens da API ADVBox em /movements deixa de ser problema, ja que mostraremos no maximo 10.

**Confirmacao do socio:** o escritorio mantem atualizado o campo `stage` (fase) de cada processo no ADVBox quando ele evolui. Logo, `stage` e a fonte autoritativa de status do processo no painel.

**Implementacao:** ver `MAX_MOVIMENTOS_POR_LAWSUIT = 10` em `src/gerador_producao.py`. Ordenacao por `date` DESC antes do slice.

---

## ⚠️ REGRA CRITICA — SEPARACAO DE DADOS (LER ANTES DE QUALQUER ALTERACAO NO GERADOR)

**Decisao registrada em 2026-05-07. Nao alterar sem nova decisao explicita do socio.**

**Regra de Ouro:** NADA que seja comentario interno da equipe, anotacao estrategica, observacao sobre prazos, criticas processuais ou comunicacao interna pode aparecer no dashboard do cliente.

**Consequencias de violacao (gravissimas):**
- Quebra de sigilo profissional (EAOAB Art. 7, II)
- Possivel infracao etica (CED-OAB Art. 35-36)
- Risco de processo de responsabilidade civil
- Comprometimento da estrategia processual

### Decisao tecnica definitiva — fluxo de dados por painel

**Dashboard PUBLICO do cliente** (`clientes/painel-*/index.html`) recebe **APENAS**:
- `GET /customers/{id}` — dados basicos do cliente
- `GET /lawsuits?customer_id=` — lista de processos (campos publicos)
- `GET /movements/{lawsuit_id}` — movimentacoes oficiais do tribunal

**Dashboard PUBLICO do cliente NAO recebe (jamais):**
- `GET /history/{lawsuit_id}` — tarefas, comentarios internos, anotacoes da equipe
- `GET /posts` — tarefas e anotacoes da equipe
- Qualquer campo `comments`, `notes` ou similar de qualquer endpoint
- Qualquer texto livre interno

**Painel INTERNO do escritorio** (`painel-interno.html`, ja na raiz do projeto) recebe **TUDO**, inclusive `/history` e `/posts`. Visualizado **apenas** pelos socios e advogados — **nunca** enviado ao cliente.

### Regra defensiva no codigo
- Funcoes que geram conteudo para o painel do cliente devem usar uma **whitelist explicita** de endpoints e campos. Nada de "mandar tudo e esconder no template".
- Templates do painel publico nao podem importar/iterar variaveis vindas de `/history` ou `/posts`.
- Nomes de variaveis no gerador devem deixar isso obvio (ex: `dados_publicos_cliente` vs `dados_internos_escritorio`).

### REVISAO 2026-05-07 — partes adversarias por NOME sao permitidas

**Decisao do socio em 2026-05-07** (Etapa B v2): a Regra de Ouro NAO se aplica a **nomes objetivos das partes adversarias** de um processo. Esses nomes podem aparecer no dashboard publico do cliente.

**Justificativa juridica:**
- Informacao processual e PUBLICA (CF art. 5 LX, 93 IX — principio da publicidade).
- O proprio cliente sabe quem esta em juizo contra ele.
- Aparece no sistema CNJ aberto.
- Nao e dado interno do escritorio.

**Whitelist nova para `partes_adversarias`** (campo derivado por processo): cada item tem **apenas** o `name` da parte. **Continua bloqueado**: `identification` (CPF/CNPJ), `email`, `phone`/`cellphone`, `address`/`city`/`state`/`postalcode`, `notes`, qualquer outro campo do customer.

**Logica de derivacao:**
```
cliente_id_advbox = clientes.json[i].id_advbox
partes_adversarias = [
  {'name': c['name']}  # so o nome
  for c in lawsuit.customers
  if c.get('id') != cliente_id_advbox  # exclui o proprio cliente
]
```

Se a API entregar `name` vazio para alguma parte, usar `''` (nao quebrar). A lista pode ser vazia (caso o lawsuit nao tenha adversarios cadastrados).

**Defesa em profundidade (assert):** atualizar para PERMITIR a chave `partes_adversarias` e a chave `name` dentro dela. Continuar bloqueando todas as outras chaves do schema de customer (identification, email, phone, etc.).

---

## DECISOES DE PRODUTO PARA ETAPA B v2 (registradas em 2026-05-07)

### Estrutura de telas (mantida da v1)
- **Tela inicial:** "Selecione a Area para Acompanhamento" + cards de areas com processos do cliente. **Sem** cards desabilitados — so areas com processos reais.
- **Tela de area** (apos clicar): banner + KPIs (4 cards) + Alertas (3 colunas) + Grafico donut por fase + Timeline (max 15 andamentos recentes da area) + Relacao de processos (tabela).

### Areas — agrupamento por `group` da API
- Usar o campo `group` (string legivel: TRABALHISTA, CIVEL, EMPRESARIAL, ADMINISTRATIVO, TRIBUTARIO, LICITACOES, etc.) direto, sem mapping artificial.
- Se `group` vier vazio em algum processo, classificar como "OUTROS".
- Mostrar **so** as areas que tem processos do cliente.
- Para o piloto-pj o `group` ja foi observado: PRIVADO (128), SOCIAL/PREV-TRAB (3), FAMILIA (1) — areas se ajustam aos dados reais.

### Alertas — inferencia por `stage` + `status_closure`
| Categoria | Cor | Criterio |
|---|---|---|
| URGENTE | vermelho | `stage` contem (case-insensitive): `AUDIENCIA`, `PRAZO`, `URGENTE` E `status_closure` vazio |
| ATENCAO | amarelo | `stage` contem: `INSTRUCAO`, `MANIFESTACAO`, `AGUARDANDO`, `EM CURSO` E `status_closure` vazio E nao caiu em URGENTE |
| FAVORAVEL | verde | `status_closure` preenchido OU `stage` contem `ARQUIV`, `TRANSITADO`, `ENCERRA` |

Por categoria: max 5 itens visiveis com `process_number`, `type`, `stage` curto. Excedente vira "+N outros".

### Filtros chips da tabela — fase_grupo
| Chip | Criterio (case-insensitive em `stage`) |
|---|---|
| CONHECIMENTO | contem `INSTRUCAO`, `INICIAL`, `AUDIENCIA`, `MANIFESTACAO` (catch-all default) |
| EXECUCAO | contem `EXECUCAO`, `CUMPRIMENTO` |
| RECURSAL | contem `RECURSO`, `AGRAVO`, `APELACAO`, `TRT`, `TJ` |
| ARQUIVADOS | `status_closure` preenchido OU `stage` contem `ARQUIV`, `ENCERRA`, `TRANSITADO` |

INSTRUCAO entra como subgrupo (so mostrar chip se houver multiplos). `TODOS` reseta o filtro.

### Tabela "Relacao de Processos" — colunas FINAIS
1. **Nº CNJ** (`process_number`, fonte mono)
2. **Partes** (`cliente.name` vs `partes_adversarias[*].name`; se >2 adversarios, "...e N outros")
3. **Acao** (`type`)
4. **Fase** (`stage` como badge colorido por `fase_grupo`)
5. **Responsavel** (`responsible`)
6. **Ultimo Andamento** (`movements[0]`: data + descricao curta)

**REMOVIDAS** (nao temos dados confiaveis):
- Tribunal/Comarca (nao esta no schema; CNJ codifica mas exige tabela de tribunais)
- Valor (vetado pela whitelist financeira: `fees_*`, `contingency`)

### Estilo da tabela
- Cabecalho azul-marinho com texto branco/dourado.
- Borda dourada lateral nas linhas.
- Setas de ordenacao por coluna.
- Badges coloridos para fase (paleta da Fase 1 mock).
- Filtros chips no topo (TODOS, CONHECIMENTO, INSTRUCAO, EXECUCAO, RECURSAL, ARQUIVADOS) + busca a esquerda.
- Rodape "Mostrando X de Y processos da area".

### Pular na v1 da Etapa B
- Graficos adicionais alem do donut por fase (barras por tribunal/tipo).
- Modal de processo.
- Painel de produtividade no lado publico (continua so no painel-interno).

---

## SNAPSHOT CONSOLIDADO — FASE 2B (registrado em 2026-05-07)

> Esta secao concentra o estado entregue ao final da sessao Fase 2B para
> permitir retomada sem ambiguidade em qualquer sessao futura. Tudo abaixo
> e materializavel no codigo/arquivos do repositorio.

### Numeros do piloto (cliente real validado)

| Indicador | Valor |
|---|---|
| Cliente piloto (CNPJ) | 05.919.720/0001-79 (PJ) |
| ID ADVBox | 13669008 |
| Total de processos | 132 (cresceu de 131 entre sessoes — 1 novo cadastro) |
| Total de movimentos no JSON | 941 (cap de 10/processo aplicado; total real na API e maior) |
| Processos saturados no cap (== 10 movs) | 72 (54.5% — esses tinham mais que 10 antes do cap) |
| Adversarios extraidos no JSON | 206 nomes em 132 processos (media 1,56/processo) |
| Distribuicao da qtd de customers por lawsuit | 1×1, 2×104, 3×11, 4×3, 5×7, 6×1, 7×3, 9×1, 13×1 |
| Areas distintas observadas (campo `group`) | **3**: PRIVADO (128), SOCIAL/PREV-TRAB (3), FAMILIA (1) |
| Fase_grupo distintos no piloto | 4: conhecimento, execucao, recursal, arquivados |
| Tamanho final `dados.json` | ~311 KB |
| Tamanho final `index.html` | ~337 KB |

### Identificacao do cliente nos arrays customers (descoberta crucial)
- `customer_id` vem **sempre None** dentro do array `customers` de cada lawsuit. Inutil para filtrar.
- `identification` (CPF/CNPJ normalizado para digitos) eh o **unico campo confiavel** para distinguir o lado do cliente vs adversarios. **132/132 lawsuits** tem o cliente piloto presente via identification.
- `origin` falharia: cliente piloto sempre tem origin "MIGRAÇÃO", mas 48 dos 206 adversarios tambem.

### Codigo entregue (estado atual em 2026-05-07)

**`src/advbox_client.py`** (cliente HTTP)
- Bearer auth + User-Agent customizado contra Cloudflare WAF
- Throttle 2s entre chamadas (30 GET/min)
- Retry 3x com backoff em timeout/5xx
- **Tratamento de HTTP 204** (processo sem movimentos): devolve `{"data": []}` em vez de erro de parse JSON
- 8 metodos: `get_settings`, `get_customers`, `iter_customers`, `get_customer`, `get_lawsuits`, `get_movements`, `get_history`, `get_tasks`

**`src/cache.py`** (cache local)
- TTL 24h em arquivos JSON na pasta `cache/`
- API: `cache_get`, `cache_set`, `cache_invalidate`, `cache_clear`
- Convencao de chaves: `customers_<id>`, `lawsuits_customer_<id>`, `movements_<lawsuit_id>`, `history_<lawsuit_id>`

**`src/gerador_producao.py`** (gerador completo Etapas A + B v2)
- Whitelists explicitas: `CAMPOS_CLIENTE_PUBLICOS`, `CAMPOS_LAWSUIT_PUBLICOS`, `CAMPOS_MOVEMENT_PUBLICOS`, `CAMPOS_LAWSUIT_DERIVADOS = ['movements','partes_adversarias','fase_grupo']`, `CAMPOS_PARTE_ADVERSARIA = ['name']`
- Constantes: `MAX_MOVIMENTOS_POR_LAWSUIT=10`, `MAX_ALERTAS_VISIVEIS_POR_CATEGORIA=5`, `MAX_TIMELINE_POR_AREA=15`, `MAX_TIPOS_TAG_POR_CARD_AREA=3`, `CORES_FASE_GRUPO`
- Mascaramento de identification (PF: `***.***.***-NN`, PJ: `**.***.***/****-NN`)
- Defesa em profundidade: `WhitelistError` + `assert_sem_termos_proibidos` (token-split, vetar `comments`, `comment`, `notes`, `note`, `observation`, `observations`, `private`, `internal`, `internal_note`, `history`, `post`, `posts`)
- Derivacoes para o template:
  - `extrair_partes_adversarias(lawsuit, cliente_ident_digitos)` — filtra por identification, mantem so `name`
  - `fase_grupo(stage)` — mapping para chips (conhecimento/execucao/recursal/arquivados)
  - `categoria_alerta(processo)` — urgente/atencao/favoravel via stage + status_closure
  - `slugify_area(nome)`, `agrupar_em_areas(processos)`, `calcular_kpis_area`, `calcular_alertas_area`, `calcular_donut_area`, `calcular_timeline_area`, `calcular_top_tipos_area`
- Cache integrado por chamada (cache_get → fetch → cache_set)
- Loop principal com try/except por cliente (falha em 1 nao aborta lote)
- Renderiza HTML via Jinja2 (`construir_jinja_env` com filtros `format_date` e `stage_color_index`)
- Copia `config/logo.png` → `clientes/{slug}/logo.png`

**`src/auditar_json.py`** (auditor pos-geracao)
- Verifica top-level (meta/cliente/processos)
- Cliente: chaves dentro da whitelist + `identification_tipo`, mascaramento de identification
- Processos: chaves dentro da whitelist + derivados, cap de movements respeitado
- Partes adversarias: chaves UNICAMENTE `['name']`
- Fase_grupo: valores observados
- Defesa em profundidade recursiva contra TERMOS_PROIBIDOS
- Total de 9+ verificacoes

**`src/templates/dashboard.html`** (Jinja2, ~1100 linhas)
- Estrutura inspirada no mock aprovado (`clientes/painel-prefconceicaoalagoas-2026-r9b3/index.html`)
- Tipografia: Inter (corpo) + Cormorant Garamond (titulo) via Google Fonts
- Paleta: #0A1628 azul-marinho + #C9A84C dourado (config/escritorio.json)
- Tela inicial: `tela-areas` com cards de areas (icone + nome + contador + top-3 tags)
- Por area: KPIs (4 cards) + Alertas (3 colunas urgente/atencao/favoravel) + Donut SVG por fase (sem JS externo) + Timeline (max 15) + Tabela "Relacao de Processos"
- Tabela com 6 colunas: Nº CNJ, Partes (cliente vs adversarios), Acao, Fase (badge colorido), Responsavel, Ultimo Andamento
- Filtros: chips por fase_grupo (TODOS/CONHECIMENTO/EXECUCAO/RECURSAL/ARQUIVADOS) + busca textual + ordenacao por header
- JS minimo: `entrarArea`, `voltarAreas`, `aplicarFiltros`, `filtrarFase`, `ordenarTabela`, deep-link `#area-<slug>`
- Responsivo: breakpoints 900px e 600px

**`src/buscar_cliente.py`** (descoberta de ID por CNPJ)
- Filtro `?identification=<digitos>` em `/customers` — descoberta nova nesta fase
- Fallback de varredura paginada se filtro for ignorado pela API

**Scripts de investigacao criados na Fase 2B**
| Script | Funcao |
|---|---|
| `src/buscar_cliente.py` | Descobre ID ADVBox a partir do CNPJ |
| `src/teste_piloto.py` | Valida schemas /customers/{id} e /lawsuits |
| `src/teste_movements_history.py` | Valida schemas /movements e /history |
| `src/teste_truncamento.py` | Detecta truncamento de /movements |
| `src/teste_paginacao_movements.py` | 7 parametros testados, nenhum paginou |
| `src/teste_endpoint_alternativo.py` | `/lawsuits/{id}/movements` retorna 401 (dead end) |
| `src/teste_partes_adversarias.py` | Inspeciona estrutura de customers em lawsuit |
| `src/teste_partes_adversarias_v2.py` | Confirma identification como filtro |

### Auditorias estabelecidas

**Camada 1 — `dados.json` (auditar_json.py)** — 9 verificacoes:
1. Estrutura top-level: ✅
2. Cliente whitelist + identification_tipo: ✅
3. Cliente identification mascarado (so 2 digitos visiveis): ✅
4. Processo whitelist + derivados: ✅
5. Cap de movements respeitado (nenhum > 10): ✅
6. Movements whitelist (date/header/title): ✅
7. Partes adversarias com chave APENAS `['name']`: ✅
8. Fase_grupo so com valores esperados: ✅
9. Defesa em profundidade recursiva (token-split contra TERMOS_PROIBIDOS): ✅

**Camada 2 — HTML forense (grep)** contra palavras proibidas:
- Padrao: `contingency|fees_money|fees_expec|exit_execution|exit_production|notes|comments|comment|observation|private|internal|history|stages_id|steps_id|type_lawsuit_id|group_id|responsible_id` (case-insensitive, word boundaries)
- Resultado em `clientes/painel-piloto-pj-2026-n4q8/index.html`: **0 ocorrencias**

**Camada 3 — Estrutura visual** (counts no index.html final):
| Elemento | Esperado | Encontrado |
|---|---|---|
| `class="card-area"` | 3 | ✅ 3 |
| `class="area-detalhe"` | 3 | ✅ 3 |
| `class="card-kpi"` | 12 (4×3 areas) | ✅ 12 |
| `class="donut-svg"` | 3 | ✅ 3 |
| `<table class="tabela-relacao"` | 3 | ✅ 3 |
| `class="filtro-btn` | 15 (5×3) | ✅ 15 |
| `<tr data-fase-grupo` | 132 | ✅ 132 |
| `class="badge badge-fase-` | 132 | ✅ 132 |
| `class="cliente-side"` | 132 | ✅ 132 |
| `class="adv-side"` | 131 (1 sem adversarios) | ✅ 131 |
| `class="timeline-item"` | <=45 | 25 |
| `class="alerta-item"` | <=45 | 16 |

### Estrutura do projeto (snapshot 2026-05-07)
```
C:\Users\Felipe\Desktop\dashboards\
├── .env                              [token ADVBox valido — NAO commitar]
├── .gitignore                        [protege .env e cache/]
├── MEMORY.md                         [este arquivo — fonte de verdade da retomada]
├── README.md
├── MANUAL-*.md                       [3 manuais para o socio]
├── requirements.txt                  [requests + jinja2 + python-dotenv]
├── config/
│   ├── clientes.json                 [slot 1: piloto-pj 13669008 ativo; 2-6 inativos]
│   ├── escritorio.json               [identidade visual + contato]
│   ├── areas_direito.json
│   ├── logo.png + logo_dark.png
├── src/
│   ├── advbox_client.py              [User-Agent + 204 + 8 metodos]
│   ├── cache.py                      [TTL 24h]
│   ├── gerador_producao.py           [Etapas A + B v2 completos]
│   ├── auditar_json.py               [9+ verificacoes]
│   ├── buscar_cliente.py             [descoberta por CNPJ]
│   ├── teste_*.py                    [8 scripts de validacao]
│   └── templates/
│       └── dashboard.html            [Jinja2 ~1100 linhas, baseado no mock aprovado]
├── cache/                            [JSONs com TTL 24h, gitignored]
│   ├── customers_13669008.json
│   ├── lawsuits_customer_13669008.json
│   └── movements_<lawsuit_id>.json   [~131 arquivos]
├── clientes/
│   ├── painel-piloto-pj-2026-n4q8/   [SAIDA REAL]
│   │   ├── dados.json                [~311 KB, auditado]
│   │   ├── index.html                [~337 KB, auditado, aguarda validacao visual]
│   │   └── logo.png
│   └── painel-*-2026-*/              [pastas mock antigas — orfas, podem ser removidas]
├── painel-interno.html               [raiz, uso interno dos socios — separado]
└── mock_data/                        [preservado p/ testes offline]
```

---

## CONTEXTO DO PROJETO

- **Nome:** Dashboards Processuais L Batista Advogados Associados
- **Cliente:** Dr. Leonardo Batista — advogado em Goiania/GO, socio do escritorio, leigo em programacao
- **Linguagem padrao:** PT-BR formal tecnico-juridico
- **Trabalho conduzido por:** Claude.ai (consultor estrategico) ditando prompts -> Claude Code (executor) no PC do cliente
- **Plataforma de execucao:** Windows 11, PowerShell, Python 3 com `requests` + `python-dotenv` + `jinja2`

---

## HISTORICO DE MIGRACOES DO ESCRITORIO

- **Ha 2+ anos:** sistema antigo (nome esquecido) -> **Lises**
- **Ha 1-2 anos:** Lises -> **ADVBox** (sistema atual)

**Implicacao critica:** A categoria `origin = "MIGRAÇÃO"` no ADVBox (54.5% dos 5231 customers) reune cadastros importados em lote dessas duas migracoes — clientes legados, adversarios antigos e partes processuais misturados, sem reclassificacao posterior. Sinal forte de que um contato `MIGRAÇÃO` e cliente atual: ter `lawsuits` nao vazia (alguem precisou manter/cadastrar processos depois da migracao para o ADVBox).

---

## DESCOBERTAS TECNICAS CRITICAS DA FASE 2

### 1. WAF/Cloudflare bloqueava User-Agent padrao
- **Causa raiz** dos erros 403 iniciais — confundimos com problema de token/permissao por varios passos.
- O Cloudflare na frente do ADVBox bloqueava `python-requests/2.32.3` **antes** de a request chegar a aplicacao. Sintoma: resposta era HTML do nginx, `Content-Type: text/html`, sem header `WWW-Authenticate` nem `x-ratelimit-*`.
- **Solucao aplicada:** User-Agent customizado
  ```
  L-Batista-Dashboards/1.0 (+contato: gestaobatistaadvogados@gmail.com)
  ```
- Esta configurado como constante `USER_AGENT` em `src/advbox_client.py` e enviado em todas as chamadas.
- **Status confirmado:** `200 OK` com `Content-Type: application/json`, `x-ratelimit-limit: 30`, `x-ratelimit-remaining: 29` (bate com a doc).

### 2. Token regenerado
- O cliente clicou em "Gerar novo token" no painel ADVBox **apos** copiar o token anterior, invalidando o primeiro. Isso causou o segundo round de 403 (legitimo, antes do diagnostico do WAF).
- Token NOVO atualmente no `.env`, validado, 60 caracteres.
- `.env` esta protegido pelo `.gitignore` (regra `*.env` linha 4).
- O arquivo `.env` tambem contem `ADVBOX_API_URL=https://app.advbox.com.br/api/v1`.

### 3. Divergencias entre documentacao oficial e API real
| Topico | Documentacao | API Real |
|---|---|---|
| Tipos de processo em /settings | `type_lawsuits` | `lawsuit_types` (ordem invertida) |
| Paginacao em /customers | `page` / `per_page` | `limit` / `offset` (page/per_page sao **silenciosamente ignorados**) |
| Limite por chamada de /customers | (nao documentado) | Forcado em **1000**, mesmo se enviarmos valor menor |
| Formato da resposta de /customers | (nao detalhado) | `{"data": [...], "limit": 1000, "offset": 0, "query": {...}, "totalCount": N}` |
| Filtro `?identification=<digitos>` em /customers | nao mencionado | **Funciona!** Validado em 2026-05-07: `totalCount=1`, retorna o cliente exato. Substitui varredura completa em buscas por CPF/CNPJ. |
| Filtro `?customer_id=` em /posts | nao documentado | **Aceito mas SILENCIOSAMENTE IGNORADO** (totalCount nao muda; mesmos items retornados). Idem comportamento de page/per_page. Filtrar localmente. |
| Token granular | nao documentado | **Tokens podem ter escopo limitado** — nosso aceita /posts mas rejeita /tasks (HTTP 401). |

### DESCOBERTA #6 — TRUNCAMENTO SILENCIOSO em /movements/{id}

A API limita silenciosamente as respostas de `/movements/{id}` a **25 itens**. Nao retorna `totalCount`, nao avisa que truncou, nao documenta paginacao. **Detectado quando 4 processos do piloto retornaram exatamente 25 itens cada** durante a primeira execucao bem-sucedida do `gerador_producao.py` em 2026-05-07. Lawsuits afetados: 13006320, 13563110, 13566402, 14240636.

**Investigacao exaustiva feita em `src/teste_paginacao_movements.py` em 2026-05-07** com lawsuit 13006320 como cobaia. 7 parametros testados (todos retornaram exatos 25 itens identicos a base, hashes do 1o e 2o item iguais):

| Parametro | Status | Itens | Paginou? |
|---|---|---|---|
| (base sem params) | 200 | 25 | — |
| `?limit=100` | 200 | 25 | nao |
| `?per_page=100` | 200 | 25 | nao |
| `?page=2` | 200 | 25 | nao |
| `?offset=25` | 200 | 25 | nao |
| `?limit=100&offset=0` | 200 | 25 | nao |
| `?cursor=25` | 200 | 25 | nao |
| `?after=25` | 200 | 25 | nao |

**Conclusao:** `/movements/{id}` nao tem paginacao acessivel. Mesmo comportamento de `/customers` com `page`/`per_page` — parametros nao reconhecidos sao silenciosamente ignorados. Os movimentos alem dos 25 mais recentes nao sao recuperaveis via essa API.

**Endpoint alternativo testado e descartado em 2026-05-07** (`src/teste_endpoint_alternativo.py`):
- `GET /lawsuits/13006320/movements` retornou **HTTP 401 "Unauthenticated"** com o mesmo token Bearer que funciona em `/movements/13006320`. Provavel default do middleware de auth em rotas nao definidas. Nao e acessivel com nossa auth atual. Dead end. **Manter `/movements/{id}` no `get_movements` do client.**

**RESOLUCAO (2026-05-07):** problema **CONTORNADO via decisao de produto** — o dashboard mostra apenas 10 andamentos mais recentes por processo (ver "DECISAO DE PRODUTO — VISAO DE STATUS, NAO HISTORICO COMPLETO" no topo deste arquivo). Os 10 sempre cabem dentro dos 25 que a API entrega. Logo, o teto de 25 nao afeta o produto final. A descoberta fica registrada para referencia futura (ex: caso decidamos adicionar um portal interno com historico completo, esse limite vira a tona de novo).

### DESCOBERTA #7 — /posts e ESCOPO DO TOKEN ADVBOX

Diagnostico feito em 2026-05-07 (`src/diagnosticar_posts.py`) revelou tres comportamentos nao documentados da API ADVBox:

(a) **Token tem escopo granular:** o token Bearer atual aceita `/settings`, `/customers`, `/lawsuits`, `/movements` e `/posts` (HTTP 200), mas REJEITA `/tasks` com HTTP 401 "Unauthenticated". Provavelmente o painel ADVBox permite emitir tokens com permissoes limitadas; o nosso nao tem `tasks.read`. Implicacao: usar `/posts` como fonte de atividade do escritorio, nunca `/tasks`.

(b) **Filtro `customer_id` em `/posts` e silenciosamente ignorado:** chamar `GET /posts?customer_id=13669008` retorna o mesmo `totalCount` (3173) e mesmos itens que `GET /posts` sem filtro. Mesmo comportamento ja documentado para `page`/`per_page` em `/customers`. A unica forma de filtrar por cliente e localmente, cruzando `lawsuits_id` do post com os IDs dos lawsuits do cliente (obtidos previamente via `/lawsuits?customer_id=`).

(c) **Schema de `/posts`:** envelope com `data`/`limit`/`offset`/`query`/`totalCount`; itens com 11 chaves: `id`, `date`, `date_deadline`, `task`, `reward`, `notes`, `local`, `lawsuits_id`, `created_at`, `lawsuit`, `users`. **ATENCAO:** `notes` contem texto livre interno do escritorio (ex: nome de funcionario + URL de tarefa interna + comentario). Manter rigorosamente fora do painel publico — Regra de Ouro.

**Implementacao no gerador:** `calcular_atividade_90d(cliente_id, lawsuit_ids, client)` agora pagina `/posts` (ate ~32 chamadas para 3173 itens), filtra localmente por `lawsuits_id ∈ ids do cliente`, aplica janela de 90 dias por `created_at` e categoriza pelo campo `task` lowercased em 5 buckets (`Pecas`, `Audiencias`, `Reunioes`, `Despachos`, `Outras` — sem acento por decisao do socio). Cache em `posts_customer_<id>.json` com TTL 24h. Whitelist de saida limitada a `{'total','categorias','ultima_data'}` via `assert_atividade_90d_estruturada`.

**Volume observado** (cliente piloto 13669008, HOSPITAL AMPARO LTDA, snapshot 2026-05-07):
- /posts global: 3173 itens (atualmente coleta retorna ~2443 antes de fim natural)
- 25 paginas de 100 itens requisitadas no ultimo run
- 263 posts pertencem ao cliente (lawsuits_id ∈ 132 lawsuits do piloto)
- 263 posts dentro da janela de 90 dias (ou seja: TODOS os posts do cliente sao recentes — atividade alta)
- Distribuicao: Pecas=24, Audiencias=1, Reunioes=11, Despachos=0, Outras=227
- Ultima data: 2026-05-07 (mesmo dia da geracao)

A hipotese inicial de "integracao recente, ainda sem historico" foi descartada. O bloco zerado vinha do **endpoint errado** (`/tasks`, com escopo bloqueado) e do **cache stale** (`tasks_customer_13669008.json` com `{"data": []}` cacheado quando o token tinha sido recusado em sessao anterior).

**Defesa em profundidade ampliada nesta descoberta:**
- TERMOS_PROIBIDOS recebeu 4 novos: `task`, `reward`, `lawsuits_id`, `tasks_id`.
- `assert_sem_termos_proibidos` agora faz **dois matches**: chave inteira (lower) E cada token (split por `_`). Necessario porque tokens `id` ou `lawsuits` sozinhos nao seriam suficientes para barrar `lawsuits_id` (e `id` e legitimamente publico em outros contextos).
- `posts` (plural) NAO foi adicionado a TERMOS_PROIBIDOS por decisao explicita do socio — a chave de cache `posts_customer_<id>.json` continua usando esse prefixo internamente.

**ATUALIZACAO 2026-05-07 (mesma sessao):** mapping de categorizacao revisto apos auditoria `src/auditar_tasks.py`. As 5 categorias finais sao: **Peças, Audiências, Comunicações, Acompanhamento, Diligências** (mais Outras como catch-all).

Categoria antiga "Reuniões" foi renomeada para "Comunicações" (cobre lembrar/avisar cliente, que sao acoes assincronas, nao reunioes presenciais). Categoria antiga "Despachos" foi removida — score estrutural zero, pois despachos vem de `/movements` (tribunal), nao de `/posts` (interno do escritorio). Acrescidas duas categorias novas: "Acompanhamento" (leitura ata, protocolo, ciencia, comentario) e "Diligências" (notificar testemunhas, pagamento, agendamento).

Bug fix incluido: keyword `'audien'` nao casava com `'audiência'` por causa do ê (que quebra a sequencia entre `i` e `n`). Agora todas as palavras-chave incluem variante COM e SEM acento, e a categoria AUDIENCIAS e checada PRIMEIRO no fluxo de classificacao.

**Resultado real (cliente piloto, regenerado 2026-05-07):**
- Peças: 43 · Audiências: 43 · Comunicações: 67 · Acompanhamento: 84 · Diligências: 26 · Outras: **0**
- 263/263 posts categorizados (100% — versus 36/263 antes da revisao).
- Estimativa do socio era 12 em Outras; resultado real foi 0, melhor que o esperado.

UX adicionado no template: a categoria "Outras" so e renderizada se `> 0`. No piloto atual (Outras=0) ela fica oculta, deixando 5 mini-cards visiveis.

### 4. Encoding UTF-8 corrigido em todos os scripts
- Adicionado no topo de cada script de teste:
  ```python
  if hasattr(sys.stdout, 'reconfigure'):
      sys.stdout.reconfigure(encoding='utf-8')
  ```
- Resolve `RONDONÓPOLIS` virando `RONDON�POLIS` no PowerShell (que opera em CP-1252 enquanto a API responde em UTF-8).

---

## RAIO-X DO ESCRITORIO NO ADVBOX

> **Atencao:** sua mensagem foi cortada em "21 origen..." nesta secao. Completei abaixo com os numeros reais que coletamos via `/settings` e via varredura de 5231 customers. Revise e corrija se algo divergir do que voce queria documentar.

### Via `/settings` (1 chamada)
- **35** usuarios cadastrados
- **21** origens de leads (categorias do campo `origin`)
- **328** tipos de tarefa
- **84** fases processuais (`stages`)
- **639** tipos de processo (`lawsuit_types`)
- **9** contas bancarias
- **248** categorias financeiras
- **13** centros de custo
- **0** departamentos cadastrados em `financial.departments`

### Via varredura de `/customers` (6 chamadas com offset 0..5000)
- **Total real da base:** 5229 customers (campo `totalCount`); foram retornados 5231 registros na varredura (pode haver ate 2 duplicatas entre lotes — investigar futuramente se necessario).
- **Schema do customer (23 campos):** `birthdate`, `cellphone`, `city`, `civil_status`, `country`, `created_at`, `document`, `email`, `gender`, `id`, `identification`, `lawsuits`, `name`, `notes`, `number_cid`, `number_ctps`, `number_pis`, `occupation`, `origin`, `phone`, `postalcode`, `region`, `state`, `street`.
- **Inversao importante:** o campo `document` esta **100% vazio** na base. O CPF/CNPJ mora em `identification` (41.5% com 11 digitos = PF, 20.5% com 14 digitos = PJ, 38% vazio).
- **Distribuicao de `origin` (top 10 sobre 5231 registros):**

  | Quantidade | % | origin |
  |---|---|---|
  | 2852 | 54.5% | MIGRAÇÃO |
  | 2118 | 40.5% | PARTE CONTRÁRIA |
  | 189 | 3.6% | CLIENTE |
  | 18 | 0.3% | CORRÉU |
  | 15 | 0.3% | EMPRESAS |
  | 10 | 0.2% | COLABORADOR ESCRITÓRIO |
  | 9 | 0.2% | PRESTADORES DE SERVIÇO |
  | 6 | 0.1% | LEONARDO DE OLIVEIRA PEREIRA BATISTA |
  | 4 | 0.1% | LEONEL CARVALHO - PJ |
  | 3 | 0.1% | MY BROKER IMOBILIÁRIA LTDA |

- **Cruzamento `origin` x `lawsuits`:**
  - MIGRAÇÃO total: 2852 — com processo: 1238, sem processo: 1614
  - CLIENTE total: 189 — com processo: 160, sem processo: 29

---

## DECISAO DE PRODUTO TOMADA NESTA SESSAO

**Estrategia abandonada:** filtros heuristicos automaticos sobre os 5229 contatos para descobrir "quem e cliente real". As tres opcoes (A/B/C) ficaram inseguras dado o lixo de MIGRAÇÃO.

**Estrategia adotada:** **CURADORIA MANUAL** via `config/clientes.json`. O socio do escritorio escolhe quais clientes recebem dashboard. Vantagens:
- So clientes "vitrine" com cadastro completo
- Curadoria editorial pelo escritorio
- Cresce gradualmente (hoje 6 mock, amanha 30 reais, etc.)
- Nao precisa resolver a confusao de MIGRAÇÃO

---

## ESTADO ATUAL DOS ARQUIVOS

### `config/clientes.json` (atualizado em 2026-05-07)
**Slot 1 substituido pelo piloto real**, slots 2-6 desativados:

| id_advbox | nome_curto | departamento | slug_url | ativo |
|---|---|---|---|---|
| **13669008** | piloto-pj | direito_publico | painel-piloto-pj-2026-n4q8 | **true** |
| 9000002 | tec | direito_privado | painel-tec-2026-z8k4 | false |
| 9000003 | horizonte | direito_imobiliario | painel-horizonte-2026-m4p7 | false |
| 9000004 | ribeiro | direito_imobiliario | painel-ribeiro-2026-q5n8 | false |
| 9000005 | conceicao-alagoas | direito_publico | painel-prefconceicaoalagoas-2026-r9b3 | false |
| 9000006 | uberaba | direito_publico | painel-prefuberaba-2026-h3j9 | false |

Estrutura de cada cliente: `id_advbox` (int), `nome_curto` (str), `departamento` (str: direito_privado | direito_imobiliario | direito_publico), `slug_url` (str ofuscado), `ativo` (bool), `data_cadastro` (str opcional). O JSON tambem contem um bloco `departamentos` com `{id, nome, cor, descricao}` para os 3 setores.

**Convencao de slug:** `painel-{nome_curto}-{ano}-{4chars}`. Slug nunca pode mudar entre rodadas (URL ja distribuida ao cliente quebraria). Por isso fica gravado no JSON.

**IMPORTANTE:** os IDs `90000xx` continuam existindo no JSON apenas como template historico — todos `ativo: false`, nao sao processados. Quando um novo cliente real for cadastrado, substituir o slot ou adicionar uma nova entry.

### `src/advbox_client.py` (Fase 2, ja em producao)
Cliente HTTP para a API ADVBox com:
- Autenticacao Bearer + User-Agent customizado
- Throttle de 2s entre chamadas (= 30 GET/min)
- Retry de ate 3 tentativas com backoff em timeout/5xx
- Excecoes em portugues: `AdvboxError`, `AdvboxAuthError`

**Metodos publicos disponiveis:**
| Metodo | Endpoint |
|---|---|
| `get_settings()` | `GET /settings` |
| `get_customers(limit=1000, offset=0)` | `GET /customers?limit=&offset=` |
| `iter_customers(lote=1000)` | varre paginas ate `totalCount` |
| `get_customer(customer_id)` | `GET /customers/{id}` |
| `get_lawsuits(customer_id=None, limit=1000, offset=0)` | `GET /lawsuits` |
| `get_movements(lawsuit_id)` | `GET /movements/{id}` (corrigido — antes estava errado) |
| `get_history(lawsuit_id)` | `GET /history/{id}` |
| `get_tasks(customer_id=None, days=90)` | `GET /tasks` |

**Constantes:** `TIMEOUT=30`, `MAX_TENTATIVAS=3`, `INTERVALO_MIN_SEGUNDOS=2.0`, `USER_AGENT='L-Batista-Dashboards/1.0 (+contato: gestaobatistaadvogados@gmail.com)'`.

### `src/cache.py` (criado nesta sessao)
Cache local em arquivos JSON com TTL de 24h.

API:
- `cache_get(chave)` — retorna dados ou `None` se ausente/expirado/corrompido
- `cache_set(chave, dados)` — grava em `cache/<chave>.json` com timestamp
- `cache_invalidate(chave)` — remove uma entrada
- `cache_clear()` — limpa toda a pasta

Convencao de chaves combinada:
- `customers_<id>` — para `get_customer`
- `lawsuits_customer_<id>` — para `get_lawsuits(customer_id=id)`
- `movements_<lawsuit_id>` — para `get_movements`
- `history_<lawsuit_id>` — para `get_history`

A pasta `cache/` esta no `.gitignore` (linha 31).

### Scripts de teste/diagnostico criados na Fase 2 (em `src/`)
| Script | Funcao | Status |
|---|---|---|
| `teste_api.py` | testa GET /customers retornando 5 registros | OK (200, encoding ok) |
| `teste_settings.py` | conta usuarios/fases/tipos/etc do escritorio | OK (todas as 9 contagens) |
| `teste_diagnostico.py` | request crua p/ inspecionar status+headers+body | OK (foi como descobrimos o WAF) |
| `teste_paginacao.py` | inspecao de chaves da resposta de /customers | OK (descobriu limit/offset/totalCount) |
| `teste_estatisticas.py` | estatisticas de 1000 customers | OK |
| `teste_filtro.py` | varredura completa + opcoes A/B/C de filtro | OK (5231 varridos) |

`mock_data/` deve ser **mantido** como fallback (testes futuros sem onerar API, demonstracoes sem dados reais, desenvolvimento offline).

### `.env` (NUNCA commitar)
```
ADVBOX_API_TOKEN=<60 caracteres do token vigente>
ADVBOX_API_URL=https://app.advbox.com.br/api/v1
```

---

## SCHEMAS DE ENDPOINTS (validados em 2026-05-07 contra cliente piloto)

### `GET /customers/{id}` (cliente detalhado)
- Retorna dict simples (sem envelope `{"data": ...}`).
- **22 chaves no top-level** — uma a menos que a listagem (`/customers`). No piloto, faltaram `document` e `civil_status`. Possivel comportamento de omitir campos vazios; nao confirmamos contra outro cadastro.
- O campo `lawsuits` vem inline como list, mas com **schema STUB**: apenas 3 chaves por item — `lawsuit_id` (int), `process_number` (str), `protocol_number` (str ou None).
- Para dados ricos de processo, **e necessario** chamar `/lawsuits?customer_id=`.

### `GET /movements/{lawsuit_id}` (movimentacoes processuais EXTERNAS)
- Envelope simples: `{"data": [...], "query": {...}}` — **sem `totalCount`/`limit`/`offset`**.
- 7 chaves por item: `customers` (str pre-formatada — nao list!), `date` (YYYY-MM-DD), `header`, `title`, `lawsuit_id`, `process_number`, `protocol_number`.
- **Semantica:** publicacoes/andamentos do tribunal — visiveis ao cliente. Vai para o painel publico.
- Validado em 12944529 (15 itens) e 12944576 (24 itens).
- **204 No Content:** quando o processo nao tem nenhum andamento, a API retorna **HTTP 204 com body vazio** em vez de `{"data": []}`. O `_request` em `advbox_client.py` ja trata: se status==204 ou body vazio, devolve `{"data": []}`. Confirmado em 13058337.
- **TRUNCAMENTO DURO em 25 itens — sem paginacao.** Ver "DESCOBERTA #6" acima. Implementar deteccao no gerador (`len == 25` => `truncado: true`).

### `GET /history/{lawsuit_id}` (LOG INTERNO do escritorio)
- Envelope: `{"data": [...], "status": ...}` (note: `status`, nao `query` — divergencia entre os dois endpoints).
- 12 chaves por item: `author`, `responsible`, `task`, `comments` (texto livre, ate 191+ chars), `created_at`, `start`, `date_deadline`, `local`, `reward`, `customers` (str), `process_number`, `protocol_number`.
- **Semantica:** tarefas internas, audiencias agendadas, comentarios da equipe. NAO e movimento processual externo. **Nao expor no painel publico do cliente.** Destinado ao `painel-interno.html`.
- Validado em 12944529: 20 itens retornados, sem paginacao.

### Inconsistencias entre endpoints (catalogadas)
- `customers` em `/lawsuits` e **list de 2+ itens (dicts)**; em `/movements` e **str pre-formatada de 44 chars** ("AUTOR x REU"). Cada consumidor precisa tratar conforme o endpoint.
- Envelope: `/movements` traz `query`; `/history` traz `status`. Ambos sem `totalCount`.

### `GET /lawsuits?customer_id={id}` (processos do cliente)
- Resposta com envelope: `{"data": [...], "limit": N, "offset": N, "totalCount": N, "query": {...}}`.
- `customer_id` e parametro **aceito** pela API (ao contrario dos page/per_page).
- limit=1000 honrou. No piloto, totalCount=131 e todos vieram em 1 chamada.
- **24 chaves por lawsuit:**

  | Categoria | Campos |
  |---|---|
  | Identificacao | `id`, `process_number`, `protocol_number`, `folder` |
  | Classificacao (string + id) | `stage`/`stages_id`, `step`/`steps_id`, `type`/`type_lawsuit_id`, `group`/`group_id` |
  | Pessoas | `customers` (list de 2+ itens), `responsible`/`responsible_id` |
  | Status/datas | `status_closure`, `created_at`, `process_date` (pode vir None) |
  | Financeiro | `contingency`, `fees_expec`, `fees_money`, `exit_execution`, `exit_production` |
  | Outros | `notes` |

- **Achado importante para o gerador:** `stage`, `step`, `type` e `group` ja vem como **string legivel** alem do ID. **Dispensa lookup contra `/settings`** para esses campos no painel — resolve uma das duvidas pendentes da Fase 2.
- A divergencia do nome do campo `type_lawsuit_id` (singular, com underscore) confirma a inversao ja registrada em /settings (`lawsuit_types`).

---

## CLIENTE PILOTO (definido em 2026-05-07)

| Campo | Valor |
|---|---|
| ID ADVBox | **13669008** |
| Tipo | PJ (14 digitos em `identification`) |
| Origin | `MIGRAÇÃO` |
| Qtd. de lawsuits no array | **131** |

**Como foi descoberto:** `src/buscar_cliente.py` chamou `GET /customers?identification=05919720000179&limit=100&offset=0`. A API aceitou o filtro (totalCount=1) — descoberta nova, ja registrada na tabela de divergencias.

**Implicacao operacional:** 131 processos esta MUITO acima do range "3-10" originalmente planejado para piloto. Custo estimado ingenuo (sem cache):
- 1 `get_customer` + 1 `get_lawsuits` = 2 calls
- 131 `get_movements` + 131 `get_history` = 262 calls
- A 30 GET/min (throttle 2s) = ~9 minutos para varrer o piloto inteiro

Por isso `cache.py` precisa ser usado desde o primeiro teste e o gerador deve evitar refetch no mesmo dia.

---

## ESTADO ATUAL DA SESSAO E PROXIMOS PASSOS

**Onde paramos:** cliente piloto identificado (ID 13669008). Cliente HTTP testado em /customers (filtro `identification` aceito). Faltam validar /customers/{id}, /lawsuits, /movements/{id} e /history/{id}.

**Plano de execucao (atualizado em 2026-05-07 — fim da sessao Fase 2B):**
1. ✅ Achar ID do piloto via CNPJ — `src/buscar_cliente.py` (descoberta: filtro `?identification=` aceito pela API)
2. ✅ Validar `get_customer(13669008)` — schema OK
3. ✅ Validar `get_lawsuits(customer_id=13669008)` — schema OK; 132 processos (era 131; +1 entre sessoes)
4. ✅ Validar `get_movements(12944529)` e `get_history(12944529)` — schemas OK
5. ✅ `gerador_producao.py` Etapa A implementado e executado
6. ✅ Auditoria de `dados.json` (`src/auditar_json.py`): 9 verificacoes passaram
7. ✅ DESCOBERTA #6: `/movements/{id}` trunca em 25 (7 parametros testados, nenhum paginou; endpoint alternativo `/lawsuits/{id}/movements` retorna 401)
8. ✅ Decisao de produto: visao de status, cap 10 movs/processo (sort `date` DESC) — contorna o teto de 25
9. ✅ Etapa B v1 (template simples) — descartada por feedback visual do socio
10. ✅ Revisao da Regra de Ouro: `partes_adversarias` por nome PERMITIDAS (whitelist `['name']`)
11. ✅ Investigacao: `customer_id` sempre None; `identification` e o filtro confiavel
12. ✅ Etapa B v2: gerador estendido (`partes_adversarias`, `fase_grupo`, agrupamento por area, KPIs/alertas/donut/timeline por area)
13. ✅ Novo `dashboard.html` (Jinja2) baseado na estrutura do mock aprovado da conceicao das alagoas
14. ✅ Auditorias 3 camadas (JSON + HTML forense + estrutura visual) — todas passaram
15. ✅ Bloco 90 dias funcional via `/posts` paginado + filtro local por `lawsuits_id` (DESCOBERTA #7). Piloto: 263 diligencias agregadas. Cache `posts_customer_<id>.json` com TTL 24h. Defesa em profundidade ampliada (TERMOS_PROIBIDOS + match exato).
16. ✅ Mapping de categorias 90d revisto (5 categorias acentuadas + Outras catch-all): **Peças (43), Audiências (43), Comunicações (67), Acompanhamento (84), Diligências (26), Outras (0)**. Bug do acento em 'audien' corrigido. Template oculta "Outras" quando == 0.
17. 🔄 **PROXIMO PASSO IMEDIATO:** validacao visual final do bloco 90 dias preenchido + restante do painel. F3 (ajustes finos UX) na sequencia se necessario.
18. ⏸ F4 — refazer `painel-interno.html` no estilo RGP, com /history e /posts completos (uso restrito aos socios).
19. ⏸ Adicionar mais clientes ao `config/clientes.json` (alem do piloto-pj) quando o socio escolher os proximos.
20. ⏸ Limpar pastas orfas em `clientes/` (mock antigo: rgp, tec, horizonte, ribeiro, prefconceicaoalagoas, prefuberaba). Decisao: manter por enquanto como referencia visual.

**Decisoes pendentes (resolvidas)**
- ~~Cache embutido vs explicito~~ → **resolvido: explicito** (`gerador_producao` chama `cache_get`/`cache_set` antes/depois de cada API call)
- ~~Cliente com `ativo: false`~~ → **resolvido: filtra no carregamento** (`carregar_clientes_ativos` so retorna ativos)
- ~~Lookup de `lawsuit_types`/`stages`/`origins` em /settings~~ → **resolvido sem lookup**: a API ja entrega esses campos como string legivel em `/lawsuits`

**Decisoes ainda pendentes**
- ID em `config/clientes.json` que nao existe mais no ADVBox (404) — comportamento ainda nao testado em pratica. Plano atual: try/except ja captura `AdvboxError`, log + skip. Validar com um ID falso quando conveniente.
- Periodicidade de execucao do gerador (manual? agendado?) — ainda nao definida.
- Como o cliente final acessa o painel (URL hospedada onde? S3? servidor proprio? com autenticacao?). Pendente — Fase 3.

---

## REFERENCIAS RAPIDAS

- Dashboard de erros do ADVBox: nao temos. Diagnostico via `src/teste_diagnostico.py` (status + headers + body cru).
- Doc oficial da API ADVBox: o cliente tem o PDF/link mas **nao confiar 100%** — ja registramos 3 divergencias nesta sessao.
- Rate limit confirmado: 30 GET/min, 500 POST/dia, 500 PUT/dia.
- Estrutura de paginacao real: `{"data": [...], "limit": N, "offset": N, "totalCount": N, "query": {...}}`.

---

## ROADMAP FUTURO E LIMITES OPERACIONAIS

### [ROADMAP] Cadastro em lote de clientes

**Decisao:** nao implementar agora. Registrado pelo socio Dr. Caio Pureza em 2026-05-07.

**Funcionalidade desejada:** ferramenta que aceita lista de CPFs/CNPJs em arquivo de texto e cadastra todos de uma vez no `clientes.json`, sem comando individual.

**Formato sugerido do arquivo:**

    CPF/CNPJ ; Departamento (1/2/3) ; Nome Curto
    12.345.678/0001-99 ; 1 ; empresa-um
    98.765.432/0001-11 ; 3 ; prefeitura-x

**Comando previsto:**

    python src/adicionar_clientes_lote.py lista.txt

**Comportamento:**
- Le cada linha
- Busca cada CPF/CNPJ no ADVBox
- Adiciona todos no `clientes.json`
- Relatorio final: OK / falhas

**Tempo estimado de implementacao:** ~10-15 min.

**Status:** AGUARDANDO DECISAO DO SOCIO PARA IMPLEMENTAR.

---

### [ROADMAP] Agrupamento de paineis de grupos economicos

**Decisao:** nao implementar agora. Registrado pelo socio Dr. Caio Pureza em 2026-05-07.

**Caso de uso disparador:** cliente cadastrado em 2026-05-07 e um grupo economico com multiplas empresas vinculadas. O socio quer eventualmente uma forma de agrupar paineis de empresas do mesmo grupo em visao consolidada.

**Tres opcoes ja discutidas:**

**OPCAO A (RECOMENDADA pelo consultor) — Painel-mae + filhos individuais:**
- Cada empresa mantem painel proprio
- Adicional: painel consolidado do grupo
- URL grupo: `/clientes/painel-grupo-X-2026-xyz/`
- URLs filhos: `/clientes/painel-empresa1-2026-abc/`, `/clientes/painel-empresa2-2026-def/`
- Cliente pode ver agregado E drill-down
- Tempo estimado: ~2-3 horas

**OPCAO B — Painel unico agregado:**
- Apenas 1 painel para o grupo todo
- Sem visao por empresa individual
- Mais simples, menos informativo
- Tempo estimado: ~1 hora

**OPCAO C — Sistema de tags / pertencimento:**
- Cada empresa permanece independente
- Adiciona campo `grupo: "X"` no `clientes.json`
- Painel-interno agrupa empresas por tag
- Cliente recebe links separados OU consolidado
- Tempo estimado: ~3-4 horas

**Decisao do socio sobre qual opcao preferir:** PENDENTE.

**Perguntas relevantes para a decisao:**
- Quantas empresas tem cada grupo?
- O cliente final (CEO/Diretor) vai ver os paineis?
- As empresas tem independencia operacional?
- Apresentacao tem mais valor com drill-down (A) ou visao unica (B)?

**Status:** AGUARDANDO DEFINICAO DA OPCAO E DECISAO DO SOCIO PARA IMPLEMENTAR.

---

### [REFERENCIA] Limites operacionais de cadastro

**Consultado em 2026-05-07.**

**Diretriz fundamental:** filosofia de curadoria manual (Decisao D5). Qualidade > quantidade. Lotes grandes contradizem essa filosofia.

**Limites praticos de cadastro por lote:**

| Quantidade | Uso |
|---|---|
| 1–5 | Cadastros pontuais (recomendado no dia a dia) |
| 10–20 | Onboarding mensal de novos clientes |
| 30–50 | Migracao inicial de base (lote unico aceitavel) |
| 100 | Carga excepcional (com cautela — dividir em 2-3 commits) |
| 200+ | NAO recomendado — risco de timeout / bloqueio API |

**Tempos de cadastro (so adicionar ao `clientes.json`):**

| CPFs/CNPJs | Tempo |
|---|---|
| 5 | ~30 segundos |
| 20 | ~2 minutos |
| 50 | ~4 minutos |
| 100 | ~8 minutos |
| 200 | ~17 minutos |

**Tempos de geracao de painel (gargalo principal):**

| Clientes | Tempo |
|---|---|
| 5 (~30 processos cada) | ~15 min |
| 20 | ~1 hora |
| 50 | ~3-4 horas |
| 100 | ~7-8 horas |

**Limites tecnicos:**
- Token ADVBox: pode ter rate-limit nao documentado.
- GitHub Actions: 30 min por execucao (timeout); 2.000 min/mes no plano gratuito.
- Cache local: ~5 KB por cliente/dia — nao e problema.
- GitHub Pages: 1 GB de tamanho do repo — comporta ~2.000 paineis.

**Recomendacao estrategica:**
- Volume natural (5-15 clientes) — manual.
- Crescimento (15-50) — lote pequeno + robo das 5h BRT.
- Maduro (100+) — implementar paralelizacao no gerador.
