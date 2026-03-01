# openclaw-config.md — Como configurar o OpenClaw com este projeto

## 1. Instalar e lançar o OpenClaw

```bash
ollama launch openclaw
```

Siga o assistente de onboarding:
- Selecione o modelo: `qwen2.5:7b` (local) OU `minimax-m2.5:cloud` (nuvem, mais rápido)
- O gateway iniciará automaticamente em background

## 2. Conectar o Telegram

```bash
openclaw configure --section channels
```

- Selecione **Telegram**
- Cole seu **Bot Token** (obtenha em @BotFather no Telegram)
- Siga as instruções para autorizar o bot

## 3. Registrar as ferramentas Python

Após o servidor FastAPI estar rodando (`docker-compose up`), configure o OpenClaw
para usar o servidor de ferramentas local:

```bash
# Verifique se o servidor está saudável
curl http://localhost:8000/health

# Veja as definições de ferramentas disponíveis
curl http://localhost:8000/tools/schema
```

### System prompt sugerido para o OpenClaw:

Configure no OpenClaw TUI como system prompt do agente:

```
Você é um assistente pessoal de finanças chamado NF-e Bot.

Você tem acesso a duas ferramentas:

1. **process_nfe_qr** — Quando o usuário enviar uma foto de nota fiscal ou cupom fiscal,
   use esta ferramenta para processar o QR code e salvar os dados de compra.

2. **query_purchases** — Quando o usuário fizer perguntas sobre gastos, compras,
   itens mais comprados, totais mensais, etc., use esta ferramenta para consultar
   o banco de dados e responder.

Sempre responda em português brasileiro. Seja simpático e útil.
Exemplos de perguntas que você deve saber responder:
- "Quanto gastei esse mês?"
- "Quais são os itens que mais compro?"
- "Compare meus gastos de janeiro com fevereiro"
- "Quanto economizei em descontos?"
- "Em qual loja gasto mais?"
```

## 4. Criar Bot no Telegram (se ainda não tiver)

1. Abra o Telegram e procure por **@BotFather**
2. Digite `/newbot`
3. Escolha um nome: ex. `Meu expenses-bot`
4. Escolha um username: ex. `expenses_bot`
5. Copie o **token** fornecido (formato: `123456789:ABCdef...`)
6. Use este token no passo 2 acima

## 5. Verificar se tudo funciona

Envie uma foto do cupom fiscal para o seu bot no Telegram.
O OpenClaw vai:
1. Receber a imagem
2. Chamar o tool `process_nfe_qr` → FastAPI server → decode QR → SEFAZ → PostgreSQL
3. Responder com o resumo da compra

Depois, pergunte: "Quanto gastei hoje?"
O OpenClaw vai:
1. Chamar o tool `query_purchases`
2. FastAPI → Ollama (NL→SQL) → PostgreSQL
3. Responder com o total
