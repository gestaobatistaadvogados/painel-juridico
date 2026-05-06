# Sistema de Dashboards Processuais — L Batista Advogados Associados

Sistema interno do escritório para geração e publicação automatizada de dashboards processuais personalizados por cliente.

---

## 📋 O que este sistema faz

Este sistema substitui a produção manual de relatórios processuais. Em vez de preparar manualmente, a cada solicitação, um documento descritivo dos processos de cada cliente, o escritório passa a oferecer:

1. **Dashboards individuais** — cada cliente recebe um link único e exclusivo para acompanhar seus processos em tempo real, com:
   - Visão geral por área do direito
   - Indicadores numéricos (KPIs)
   - Painel de alertas (urgentes / atenção / favoráveis)
   - Gráficos de distribuição
   - Linha do tempo de andamentos
   - Tabela completa com busca, filtros e ordenação

2. **Painel Interno do escritório** — instrumento de gestão para uso restrito dos sócios e equipe interna, contendo:
   - Lista consolidada de todos os clientes
   - Indicadores agregados do escritório (total de processos, alertas críticos, valor em disputa)
   - Filtros por departamento (Direito Privado / Imobiliário / Público)
   - Busca por nome, documento ou cidade
   - Botões de ação para abrir cada dashboard ou copiar o link de envio

---

## 🏗️ Arquitetura

```
                              ┌─────────────────────────┐
                              │  ADVBox (1 conta única) │
                              │   Fonte dos dados       │
                              └────────────┬────────────┘
                                           │ API REST
                                           ▼
                  ┌────────────────────────────────────────┐
                  │  GitHub Actions (executor automático)  │
                  │  - Roda diariamente às 5h              │
                  │  - Lê o token guardado em GitHub       │
                  │    Secrets (criptografado)             │
                  │  - Gera os arquivos HTML               │
                  │  - Publica no GitHub Pages             │
                  └────────────────────┬───────────────────┘
                                       │
                                       ▼
                  ┌────────────────────────────────────────┐
                  │  GitHub Pages (sites estáticos)        │
                  └─┬──────────┬───────────┬───────────────┘
                    │          │           │
                    ▼          ▼           ▼
              ┌─────────┐  ┌─────────┐  ┌─────────┐
              │ Cliente │  │ Cliente │  │ Painel  │
              │   A     │  │   B     │  │ Interno │
              └─────────┘  └─────────┘  └─────────┘
              (link único) (link único) (acesso sócios)
```

---

## 📁 Estrutura de Pastas

```
Dashboards-Batista/
│
├── config/                          ← CONFIGURAÇÕES (o senhor mexe aqui)
│   ├── escritorio.json              ← Dados institucionais (nome, contatos, cores)
│   ├── clientes.json                ← Cadastro centralizado dos clientes
│   ├── areas_direito.json           ← 14 áreas do direito pré-cadastradas
│   ├── logo.png                     ← Logo do escritório (versão dark transparente)
│   └── token_advbox.txt             ← Token da API ADVBox (NUNCA subir ao GitHub)
│
├── mock_data/                       ← DADOS SIMULADOS (para testes)
│   ├── customers_mock.json          ← Clientes fictícios
│   ├── lawsuits_mock.json           ← Processos fictícios
│   ├── movements_mock.json          ← Andamentos fictícios
│   └── diligencias_mock.json        ← Diligências dos últimos 90 dias (painel de produtividade)
│
├── src/                             ← CÓDIGO (não mexer)
│   ├── gerador_teste.py             ← Gerador atual (usa dados mock)
│   ├── gerador_producao.py          ← Gerador de produção (usa API ADVBox) [Fase 2]
│   └── templates/
│       ├── dashboard.html           ← Template do dashboard de cliente
│       └── painel_interno.html      ← Template do painel interno
│
├── clientes/                        ← SAÍDA: dashboards gerados
│   ├── painel-rgp-2026-x9k7/
│   │   └── index.html
│   ├── painel-tec-2026-z8k4/
│   │   └── index.html
│   └── ... (1 pasta por cliente)
│
├── painel-interno.html              ← SAÍDA: painel interno do escritório
│
├── .github/
│   └── workflows/
│       └── atualizar-dashboards.yml ← GitHub Actions [Fase 3]
│
├── .gitignore                       ← Lista do que NÃO subir ao GitHub
├── requirements.txt                 ← Dependências Python
│
└── (manuais)
    ├── README.md                    ← Este arquivo (visão geral)
    ├── MANUAL-INSTALACAO.md         ← Como instalar pela primeira vez
    ├── MANUAL-USO-DIARIO.md         ← Como usar no dia-a-dia
    └── MANUAL-CLAUDE-CODE.md        ← Como conduzir Fases 2 e 3 com Claude Code
```

---

## 🛤️ Roadmap (estado do projeto)

### ✅ Fase 1 — Frontend completo (concluída)
- Estrutura modular do projeto
- Identidade visual do escritório
- Sistema híbrido de áreas (14 pré-cadastradas + detecção automática)
- Dashboards individuais com 5 seções (galeria, KPIs, alertas, gráficos, timeline, tabela, modal)
- **Painel de Produtividade do Escritório** (diligências dos últimos 90 dias por cliente)
- Painel Interno com filtros e ações
- Multi-cliente (testado com 6 clientes mock)

### 🔲 Fase 2 — Integração API ADVBox (próxima)
- Substituir mock por chamadas reais à API
- Tratamento de rate limits e cache
- Mapeamento de campos ADVBox → estrutura interna

### 🔲 Fase 3 — Automação GitHub Actions
- Token guardado em GitHub Secrets (criptografado)
- Agendamento diário às 5h
- Botão de execução manual no GitHub
- Notificação por e-mail em caso de falha

### 🔲 Fase 4 — Segurança LGPD (evolução futura)
- Senha individual por dashboard de cliente
- Painel interno publicado online com login dos sócios
- Logs de acesso auditáveis

---

## 📜 Bases legais aplicáveis

- **LGPD (Lei nº 13.709/2018)** — proteção de dados pessoais dos clientes
- **Estatuto da OAB (Lei nº 8.906/1994)** — sigilo profissional
- **CPC/2015** — disposições sobre processo eletrônico
- **Lei 14.133/2021** — para casos de Direito Público (licitações e contratos)
- **LRF — LC 101/2000** — para clientes municipais

---

## 🔐 Compromisso com a confidencialidade

Os dashboards são gerados com URL ofuscada (sufixo aleatório no link). Em sua versão atual, a segurança baseia-se em:

1. **URL secreta por obscuridade** (sufixo aleatório de 4 caracteres)
2. **Token da API** mantido em GitHub Secrets (criptografado, jamais exposto no código)
3. **Operação somente leitura** (cláusula 7.2 dos Termos da API ADVBox)
4. **Aviso "noindex, nofollow"** nos HTMLs (não aparecem em mecanismos de busca)

A camada adicional de senha por cliente está prevista para a Fase 4.

---

## 🛠️ Tecnologias utilizadas

- **Python 3.11+** — geração dos HTMLs
- **Jinja2** — sistema de templates
- **Requests** — chamadas à API ADVBox
- **Chart.js** (CDN) — gráficos interativos
- **GitHub Actions** — automação
- **GitHub Pages** — hospedagem gratuita

Custo total de operação: **R$ 0,00/mês** (até o limite gratuito do GitHub).

---

## 📚 Documentação adicional

- **`MANUAL-INSTALACAO.md`** — passo-a-passo para a primeira instalação
- **`MANUAL-USO-DIARIO.md`** — operação no dia-a-dia
- **`MANUAL-CLAUDE-CODE.md`** — condução das Fases 2 e 3 via Claude Code

---

**Projeto preparado em maio de 2026 — Versão da Fase 1.5 (Painel Interno).**
