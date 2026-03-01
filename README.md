# 🧾 Expenses Tracker

Rastreador de compras via nota fiscal eletrônica brasileira (NF-e / NFC-e).
Envie uma foto do cupom fiscal para o Telegram → o bot decodifica o QR, busca os dados
na SEFAZ SP, salva no PostgreSQL e responde perguntas sobre seus gastos em linguagem natural.

```
Telegram → OpenClaw → Ollama (qwen2.5:7b) → FastAPI Tools → PostgreSQL
```

---

## 🗂️ Estrutura do projeto

```
nfe-tracker/
├── app/
│   ├── main.py          # FastAPI — servidor de ferramentas
│   ├── sefaz.py         # Parser HTML da SEFAZ SP (BeautifulSoup)
│   ├── qr_decoder.py    # Decodificador de QR code (pyzbar)
│   ├── nl_query.py      # Perguntas em linguagem natural → SQL (Ollama)
│   └── db.py            # Conexão e queries PostgreSQL
├── schema.sql           # Schema do banco de dados
├── docker-compose.yml   # PostgreSQL + App
├── Dockerfile
├── requirements.txt
├── .env.example
└── openclaw-config.md   # Como configurar o OpenClaw + Telegram
```

---

## 🚀 Setup rápido

### Pré-requisitos

- [Docker + Docker Compose](https://docs.docker.com/get-docker/)
- [Ollama](https://ollama.com/download) instalado na máquina host
- Bot do Telegram criado via @BotFather

### 1. Clone e configure

```bash
git clone https://github.com/xxxxxxPyro/cube-ocr.git
cd expenses-tracker
```

### 2. Baixe o modelo Ollama

```bash
# Opção A: local (recomendado, ~5GB)
ollama pull qwen2.5:7b

# Opção B: cloud (mais rápido, requer conta)
# use minimax-m2.5:cloud no .env
```

### 3. Suba o banco e o servidor

```bash
#build to build the image
docker-compose -f deployments/docker-compose.yml up -d
```

Verifique:
```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

### 4. Configure o OpenClaw + Telegram

Siga as instruções em [`openclaw-config.md`](./openclaw-config.md)

---

## 💬 O que você pode perguntar ao bot

| Pergunta | Resposta |
|---|---|
| `[foto do cupom]` | Salva a compra e exibe resumo |
| "Quanto gastei esse mês?" | Total do mês atual |
| "Quais itens eu mais compro?" | Top 10 produtos |
| "Compare janeiro com fevereiro" | Gastos lado a lado |
| "Quanto economizei em descontos?" | Total de descontos |
| "Em qual loja gasto mais?" | Ranking por estabelecimento |
| "Me lista as últimas 5 compras" | Histórico recente |

---

## 🔧 Endpoints da API

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/health` | Status do servidor |
| `POST` | `/tools/process-qr` | Processa imagem com QR de NF-e |
| `POST` | `/tools/query` | Pergunta em linguagem natural |
| `GET` | `/tools/schema` | Definições de tools para Ollama |
| `GET` | `/docs` | Swagger UI interativo |

---

## Makefile
```
make help          # show all commands

make build         # rebuild everything
make restart-bot   # restart bot + show last 10 log lines
make logs-bot      # tail bot logs live

make db-users      # see registered users
make db-purchases  # see latest purchases
make psql          # open DB shell directly

make gw-stop       # kill OpenClaw gateway
make health        # ping the API
```

## 🗄️ Schema do banco

```sql
purchases  — uma linha por nota fiscal
items      — uma linha por item da nota
monthly_summary  — view: resumo mensal
top_items        — view: itens mais comprados
```

---

## 🔮 Próximos passos (roadmap)

- [ ] Suporte a outros estados (SEFAZ RJ, MG, etc.)
- [ ] Gráficos mensais enviados pelo bot
- [ ] Alertas de orçamento (`/alerta 500 supermercado`)
- [ ] Exportar para Excel/CSV
- [ ] Categorização automática de produtos com Ollama
- [ ] Suporte multi-usuário (CPF por chat ID)

---

## 🐛 Problemas comuns

**QR não decodificado:** Foto muito escura ou borrada. Tente com boa iluminação
e o QR centralizado. O bot tenta 3 estratégias de decodificação automaticamente.

**SEFAZ inacessível:** A SEFAZ SP às vezes fica lenta. O bot tentará novamente.
Você também pode consultar manualmente em https://www.nfce.fazenda.sp.gov.br/consulta

**Ollama não responde:** Verifique se o Ollama está rodando:
```bash
ollama list
curl http://localhost:11434/api/tags
```