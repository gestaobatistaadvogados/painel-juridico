# Manual de Instalação — Primeira Configuração

Este manual conduz o senhor pelo procedimento inicial de instalação do sistema de dashboards no seu PC. Ele deve ser seguido **uma única vez**. Após esta configuração, o uso diário é descrito em `MANUAL-USO-DIARIO.md`.

---

## 📋 Pré-requisitos

Antes de começar, confira se o senhor possui o seguinte instalado no seu PC:

| Item | Como verificar | Status esperado |
|---|---|---|
| **Python 3.11+** | No PowerShell, digite: `python --version` | Deve mostrar "Python 3.11.x" ou superior |
| **Git** | No PowerShell, digite: `git --version` | Deve mostrar "git version 2.x" |
| **Node.js** | No PowerShell, digite: `node --version` | Deve mostrar "v20.x" ou superior |
| **Claude Code** | No PowerShell, digite: `claude --version` | Deve mostrar "claude 2.x" |
| **Conta GitHub** | Já criada: `dirprivadoleonardobatista-ai` | ✅ Confirmado |

> **Se algum item faltar:** parar a instalação e instalar os faltantes antes de prosseguir. Cada um tem instaladores oficiais facilmente encontrados em busca.

---

## 🗂️ Etapa 1 — Descompactar o projeto

1. Localize o arquivo `Dashboards-Batista.zip` recebido.
2. Clique com o botão direito → **Extrair tudo...**
3. Escolha o destino: `C:\Users\Felipe\Desktop\`
4. Confirme. Será criada a pasta `Dashboards-Batista` com toda a estrutura do projeto.

> **Verificação:** abra a pasta `C:\Users\Felipe\Desktop\Dashboards-Batista`. Deve haver subpastas `config`, `mock_data`, `src`, `clientes` e arquivos como `painel-interno.html`, `README.md`, etc.

---

## 🐍 Etapa 2 — Instalar dependências Python

1. **Abra o PowerShell como administrador** (clique no Iniciar → digite "PowerShell" → clique com botão direito → "Executar como administrador")
2. Navegue até a pasta do projeto:
   ```powershell
   cd C:\Users\Felipe\Desktop\Dashboards-Batista
   ```
3. Instale as dependências:
   ```powershell
   pip install -r requirements.txt
   ```
4. Aguarde a instalação. Você deve ver mensagens "Successfully installed jinja2 requests python-dotenv".

> **Se der erro de "pip não reconhecido":** use `python -m pip install -r requirements.txt`

---

## 🧪 Etapa 3 — Testar geração local com dados mock

Antes de conectar à API real, vamos validar que o gerador funciona localmente:

1. Continue no PowerShell, na pasta do projeto:
   ```powershell
   python src\gerador_teste.py
   ```
2. Aguarde a execução (deve levar 3-5 segundos). Você verá:
   ```
   🔧 Fase 1.5 — Painel Interno + Dashboards Multi-Cliente
   ✅ Logo oficial embutido em base64
   ✅ 14 áreas pré-cadastradas
   ✅ 6 clientes (ADVBox) / 6 clientes cadastrados / 49 processos / 48 com andamentos

   📄 Gerando dashboard: Robson Gorito Portes
      ✅ clientes/painel-rgp-2026-x9k7/index.html  (243,xxx bytes)
   ... (e assim por diante para os 6 clientes)

   🔐 Gerando painel interno...
      ✅ painel-interno.html

   🎉 Geração concluída!
   ```
3. **Validação visual:** dê duplo-clique no arquivo `painel-interno.html` no Explorador de Arquivos. Deve abrir o painel com 6 clientes e os botões funcionando.

---

## 🌐 Etapa 4 — Configurar Git e GitHub

### 4.1 — Configurar identidade no Git (se ainda não fez)

```powershell
git config --global user.email "dirprivado.leonardobatista@gmail.com"
git config --global user.name "L Batista Advogados Associados"
```

### 4.2 — Inicializar o repositório local

Estando na pasta do projeto:

```powershell
git init
git add .
git commit -m "Versão inicial do projeto - Fase 1.5"
```

### 4.3 — Conectar ao repositório do GitHub

O repositório piloto já existe: `painel-rgp-2026-x9k7`. Mas como agora o projeto é multi-cliente, vamos criar um repositório novo, mais adequado.

**Pelo navegador:**
1. Acesse https://github.com/new (estando logado na conta `dirprivadoleonardobatista-ai`)
2. Nome do repositório: **`dashboards-batista`** (sem maiúsculas, sem acentos)
3. Marque como **Private** (privado) — apenas o senhor e quem o senhor convidar acessa
4. **NÃO** marque nenhuma das opções (README, .gitignore, license) — já temos esses arquivos
5. Clique em **Create repository**

**No PowerShell, conecte os dois:**

```powershell
git remote add origin https://github.com/dirprivadoleonardobatista-ai/dashboards-batista.git
git branch -M main
git push -u origin main
```

> Será solicitado autenticação. Use seu usuário e o **token de acesso pessoal** do GitHub (não a senha — o GitHub não aceita senha para git via HTTPS desde 2021).

---

## 🌍 Etapa 5 — Ativar GitHub Pages

1. Acesse https://github.com/dirprivadoleonardobatista-ai/dashboards-batista/settings/pages
2. Em **Source**, selecione: **Deploy from a branch**
3. Em **Branch**, selecione: **main** + pasta **/ (root)**
4. Clique em **Save**

Após 1-2 minutos, o site estará no ar em:
**`https://dirprivadoleonardobatista-ai.github.io/dashboards-batista/`**

> **Importante:** o painel interno NÃO deveria ficar online publicamente neste momento. Como é um repositório privado, o GitHub Pages só permite acesso a quem tem login com permissão. Mesmo assim, na Fase 4 vamos adicionar senha à página.

---

## ✅ Etapa 6 — Validação final

Acesse pelo navegador:

```
https://dirprivadoleonardobatista-ai.github.io/dashboards-batista/painel-interno.html
```

Você deve ver o painel interno funcional. Os links "ABRIR PAINEL" agora funcionam **online** — sem precisar do PC do senhor estar ligado.

---

## 🔚 Conclusão da Instalação

O senhor concluiu a instalação básica. Neste momento:

✅ Projeto está no seu PC
✅ Projeto está no GitHub do escritório
✅ Painel interno está acessível online (com login do GitHub)
✅ Dashboards individuais estão acessíveis pelos links únicos
🔲 Sistema ainda usa dados **mock** — falta integrar a API ADVBox (Fase 2)
🔲 Sistema ainda **não atualiza automaticamente** — falta GitHub Actions (Fase 3)

**Próximo passo:** seguir o `MANUAL-CLAUDE-CODE.md` para conduzir as Fases 2 e 3.

---

## 🆘 Solução de problemas comuns

### "Python não é reconhecido como comando"
- Reinstalar Python e marcar a opção **"Add Python to PATH"** durante a instalação.

### "Permission denied (publickey)" ao fazer push
- O GitHub mudou a autenticação em 2021. Use um **Personal Access Token (PAT)**:
  1. https://github.com/settings/tokens → Generate new token (classic)
  2. Marque escopos: `repo` (todos)
  3. Copie o token e use como senha quando o Git pedir
- Ou configure SSH (mais avançado, opcional)

### Gerador roda mas painel-interno.html não abre os dashboards
- Confirme que existe a pasta `clientes/` ao lado do `painel-interno.html`
- Os links apontam para `./clientes/painel-xxx/index.html` — a estrutura precisa estar preservada

### Quero recomeçar do zero
- Apague a pasta `Dashboards-Batista` e descompacte o ZIP novamente
- Os arquivos de configuração (`config/`) preservam suas customizações
