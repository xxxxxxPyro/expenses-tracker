# 🧾 Expenses Tracker

Rastreador de compras via cupom fiscal eletrônico brasileiro (NFC-e).  
Envie uma foto do cupom para o bot do Telegram → ele decodifica o QR, busca os dados na SEFAZ SP, salva no PostgreSQL e responde perguntas sobre seus gastos.

```
Foto do cupom → Bot Telegram → QR Code → API SEFAZ SP → PostgreSQL
```

---

## 🗂️ Estrutura do projeto

```
expenses-tracker/
├── app/
│   ├── __init__.py        # Pacote Python
│   ├── telegram_bot.py    # Bot do Telegram (handlers, registro de usuários)
│   ├── sefaz.py           # Parser HTML da SEFAZ SP (BeautifulSoup)
│   ├── qr_decoder.py      # Decodificador de QR code (pyzbar)
│   ├── nl_query.py        # Perguntas em linguagem natural → SQL (Ollama)
│   ├── db.py              # Conexão e queries PostgreSQL
│   ├── main.py            # FastAPI — servidor auxiliar
│   └── debug.py           # Script de diagnóstico
├── deployments/
│   ├── schema.sql         # Schema do banco de dados
│   ├── docker-compose.yml # PostgreSQL + App + Bot
│   └── Dockerfile         # Imagem Docker da aplicação
├── requirements.txt       # Dependências Python
├── .env.example           # Exemplo de variáveis de ambiente
├── .gitignore
├── Makefile               # Comandos úteis
└── LICENSE
```

---

## 🚀 Setup

### Pré-requisitos

- [Docker + Docker Compose](https://docs.docker.com/get-docker/)
- Bot do Telegram criado via [@BotFather](https://t.me/BotFather)

### 1. Clone e configure

```bash
git clone https://github.com/xxxxxxPyro/expenses-tracker.git
cd expenses-tracker
cp .env.example .env
# Edite .env e adicione seu TELEGRAM_TOKEN
```

### 2. Suba os containers

```bash
make build
```

### 3. Aplique o schema do banco

```bash
docker exec -i expenses_db psql -U expenses -d expenses_tracker < deployments/schema.sql
```

### 4. Verifique

```bash
make ps        # containers rodando
make logs-bot  # logs do bot em tempo real
```

Abra o Telegram, envie `/start` ao seu bot e cadastre seu e-mail.

---

## 💬 Como usar

### Registrar uma compra
Envie uma **foto do cupom fiscal** (ou como arquivo para melhor qualidade do QR).  
O bot irá:
1. Decodificar o QR code
2. Consultar a API da SEFAZ SP
3. Extrair todos os dados (loja, itens, valores, descontos)
4. Salvar no banco de dados
5. Exibir o resumo da compra

### Consultar gastos
Digite perguntas em linguagem natural:

| Pergunta | O que retorna |
|---|---|
| `Quanto gastei esse mês?` | Total do mês atual |
| `Quais itens eu mais compro?` | Top 10 produtos |
| `Em qual loja gasto mais?` | Ranking por estabelecimento |
| `Quanto economizei em descontos?` | Total de descontos acumulados |
| `Me lista as últimas 5 compras` | Histórico recente |

### Comandos disponíveis

| Comando | Descrição |
|---|---|
| `/start` | Boas-vindas e registro |
| `/help` | Lista de comandos |
| `/minha_conta` | Seus dados cadastrados |
| `/resumo` | Resumo do mês atual |
| `/top` | Top 10 produtos mais comprados |
| `/ultimas` | Últimas 5 compras |

---

## 🗄️ Schema do banco

```
users      — usuários registrados (email + telegram_user_id + internal UUID)
purchases  — uma linha por nota fiscal
items      — uma linha por item da nota
monthly_summary  — view: resumo mensal por usuário
top_items        — view: itens mais comprados por usuário
```

Cada usuário tem isolamento completo dos dados via `internal_user_id` (UUID).

---

## 🛠️ Makefile — comandos disponíveis

```bash
make help           # lista todos os comandos

# Docker
make build          # rebuild completo
make up             # subir containers
make down           # parar containers
make restart        # reiniciar tudo
make restart-bot    # reiniciar só o bot
make ps             # status dos containers

# Logs
make logs           # todos os containers
make logs-bot       # logs do bot
make logs-db        # logs do banco

# Banco de dados
make psql           # abrir shell psql
make db-tables      # listar tabelas
make db-users       # ver usuários registrados
make db-purchases   # ver últimas compras
make db-reset       # ⚠️ apagar todos os dados

# Diagnóstico
make health         # checar API auxiliar
make shell-bot      # shell dentro do container do bot
```

---

## 🐛 Problemas comuns

**QR não decodificado**  
Foto muito escura ou borrada. Tente com boa iluminação e o QR centralizado. Envie como **arquivo** (não foto) para evitar compressão. O bot tenta 3 estratégias de decodificação automaticamente.

**SEFAZ inacessível**  
A SEFAZ SP às vezes fica lenta. Consulte manualmente em https://www.nfce.fazenda.sp.gov.br/consulta

**`relation "users" does not exist`**  
O schema não foi aplicado. Execute:
```bash
docker exec -i expenses_db psql -U expenses -d expenses_tracker < deployments/schema.sql
```

**Bot não responde**  
Verifique se não há outro processo usando o mesmo token:
```bash
make gw-stop   # para o OpenClaw se estiver rodando
make restart-bot
```

---

## 🔮 Roadmap

- [ ] Suporte a outros estados (SEFAZ RJ, MG, RS, etc.)
- [ ] Gráficos mensais enviados pelo bot
- [ ] Alertas de orçamento (`/alerta 500 supermercado`)
- [ ] Exportar para Excel/CSV
- [ ] Categorização automática de produtos
- [ ] Dashboard web

---

## Licença

MIT
