"""
app/telegram_bot.py — NF-e Tracker bot with full multi-user support
"""
import os
import io
import re
import logging
from dotenv import load_dotenv
load_dotenv()

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes,
)

from .qr_decoder import decode_qr_from_bytes
from .sefaz import fetch_and_parse
from .db import (
    get_user_by_telegram_id, get_user_by_email,
    create_user, update_user_telegram,
    save_purchase, run_query,
)
from .nl_query import question_to_sql, format_answer

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN not set in .env")

# ConversationHandler state
WAITING_EMAIL = 1


# ── Registration flow ─────────────────────────────────────────────────────────

async def _get_or_prompt_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Returns the user dict if registered, otherwise sends registration prompt
    and returns None.
    """
    uid = update.effective_user.id
    user = get_user_by_telegram_id(uid)
    if user:
        return user

    context.user_data["pending_action"] = "register"
    await update.message.reply_text(
        "👋 Olá! Antes de começar, preciso do seu *e-mail* para criar sua conta.\n\n"
        "Isso garante que seus dados ficam associados apenas a você, "
        "mesmo que você troque de dispositivo.\n\n"
        "📧 Por favor, digite seu e-mail:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return None


async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called when user sends a message while in WAITING_EMAIL state."""
    email = update.message.text.strip().lower()
    uid   = update.effective_user.id
    tg    = update.effective_user

    # Basic email validation
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        await update.message.reply_text(
            "❌ E-mail inválido. Por favor, digite um e-mail válido:"
        )
        return WAITING_EMAIL

    # Check if email already exists → link to this Telegram ID
    existing = get_user_by_email(email)
    if existing:
        if existing["telegram_user_id"] != uid:
            # Email registered from another Telegram account → re-link
            update_user_telegram(existing["internal_id"], uid)
            user = get_user_by_telegram_id(uid)
            await update.message.reply_text(
                f"✅ Conta vinculada com sucesso!\n"
                f"Bem-vindo de volta, *{user['first_name'] or email}*! 🎉",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"✅ Você já possui conta com este e-mail.\n"
                f"Bem-vindo de volta! 🎉"
            )
    else:
        # New user
        create_user(
            telegram_user_id=uid,
            email=email,
            first_name=tg.first_name,
            username=tg.username,
        )
        await update.message.reply_text(
            f"✅ *Conta criada com sucesso!*\n\n"
            f"📧 E-mail: `{email}`\n\n"
            f"Agora você pode:\n"
            f"📸 Enviar fotos de cupons fiscais para registrar compras\n"
            f"💬 Fazer perguntas sobre seus gastos\n\n"
            f"Experimente enviar uma foto de um cupom fiscal! 🛒",
            parse_mode="Markdown",
        )

    return ConversationHandler.END


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_prompt_user(update, context)
    if not user:
        return WAITING_EMAIL

    await update.message.reply_text(
        f"👋 Olá, *{user['first_name'] or user['email']}*!\n\n"
        "📸 Envie uma *foto do cupom fiscal* para registrar uma compra.\n\n"
        "💬 Ou me pergunte sobre seus gastos:\n"
        "• _Quanto gastei esse mês?_\n"
        "• _Quais itens compro mais?_\n"
        "• _Total de fevereiro_\n"
        "• _Em qual loja gasto mais?_",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Comandos disponíveis:*\n\n"
        "/start — Boas-vindas\n"
        "/help — Esta ajuda\n"
        "/minha_conta — Ver seus dados cadastrados\n"
        "/resumo — Resumo do mês atual\n"
        "/top — Top 10 produtos mais comprados\n"
        "/ultimas — Últimas 5 compras\n\n"
        "📸 Envie uma *foto de cupom fiscal* para registrar uma compra.\n"
        "💡 Envie como *arquivo* para melhor leitura do QR.",
        parse_mode="Markdown",
    )


async def cmd_minha_conta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_prompt_user(update, context)
    if not user:
        return WAITING_EMAIL

    await update.message.reply_text(
        f"👤 *Sua conta:*\n\n"
        f"📧 E-mail: `{user['email']}`\n"
        f"🆔 ID interno: `{str(user['internal_id'])[:8]}...`\n"
        f"📅 Cadastrado em: {str(user['created_at'])[:10]}",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cmd_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_prompt_user(update, context)
    if not user:
        return WAITING_EMAIL
    await _answer_question(update, "Qual é o resumo de gastos do mês atual?", user["internal_id"])
    return ConversationHandler.END


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_prompt_user(update, context)
    if not user:
        return WAITING_EMAIL
    await _answer_question(update, "Quais são os 10 produtos que mais compro?", user["internal_id"])
    return ConversationHandler.END


async def cmd_ultimas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_prompt_user(update, context)
    if not user:
        return WAITING_EMAIL
    await _answer_question(update, "Me lista as últimas 5 compras com data e valor total", user["internal_id"])
    return ConversationHandler.END


# ── Image handlers ────────────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_prompt_user(update, context)
    if not user:
        return WAITING_EMAIL

    await update.message.reply_text(
        "🔍 Processando sua nota fiscal...\n"
        "💡 _Dica: envie como arquivo para melhor qualidade do QR._",
        parse_mode="Markdown",
    )
    photo = update.message.photo[-1]
    file  = await context.bot.get_file(photo.file_id)
    buf   = io.BytesIO()
    await file.download_to_memory(buf)
    await _process_image_bytes(update, buf.getvalue(), user)
    return ConversationHandler.END


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_prompt_user(update, context)
    if not user:
        return WAITING_EMAIL

    doc = update.message.document
    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        await update.message.reply_text("❌ Por favor envie uma imagem (jpg, png).")
        return ConversationHandler.END

    await update.message.reply_text("🔍 Processando sua nota fiscal...")
    file = await context.bot.get_file(doc.file_id)
    buf  = io.BytesIO()
    await file.download_to_memory(buf)
    await _process_image_bytes(update, buf.getvalue(), user)
    return ConversationHandler.END


async def _process_image_bytes(update: Update, image_bytes: bytes, user: dict):
    internal_user_id = str(user["internal_id"])

    url = decode_qr_from_bytes(image_bytes)
    if not url:
        await update.message.reply_text(
            "❌ Não consegui encontrar o QR code.\n\n"
            "*Dicas:*\n"
            "• Boa iluminação, sem reflexo\n"
            "• QR centralizado e nítido\n"
            "• Envie como *arquivo* para evitar compressão",
            parse_mode="Markdown",
        )
        return

    if "fazenda" not in url and "nfce" not in url.lower():
        await update.message.reply_text(
            f"⚠️ QR decodificado mas não parece ser NF-e SEFAZ.\nURL: `{url}`",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text("✅ QR decodificado! Buscando dados na SEFAZ...")

    try:
        invoice = fetch_and_parse(url)
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao acessar SEFAZ:\n`{e}`", parse_mode="Markdown")
        return

    try:
        purchase_id, already_exists = save_purchase(invoice, internal_user_id=internal_user_id)
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao salvar:\n`{e}`", parse_mode="Markdown")
        return

    if already_exists:
        await update.message.reply_text(f"⚠️ Nota fiscal já registrada (ID #{purchase_id}).")
        return

    items_text = "\n".join(
        f"  • {i['name']} × {i['quantity']} — R$ {i['total_price']:.2f}"
        for i in invoice.get("items", [])
    )

    msg = (
        f"✅ *Compra registrada!*\n\n"
        f"🏪 *Loja:* {invoice['store_name']}\n"
        f"📅 *Data:* {invoice.get('purchase_date', 'N/A')}\n\n"
        f"🛒 *Itens ({len(invoice.get('items', []))}):\n*{items_text}\n\n"
        f"💰 *Subtotal:* R$ {invoice.get('total_gross', 0):.2f}\n"
        f"🏷️ *Desconto:* R$ {invoice.get('total_discount', 0):.2f}\n"
        f"✅ *Total pago:* R$ {invoice.get('total_net', 0):.2f}\n"
        f"💳 *Pagamento:* {invoice.get('payment_method', 'N/A')}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ── Text handler ──────────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_prompt_user(update, context)
    if not user:
        return WAITING_EMAIL

    question = update.message.text.strip()
    if len(question) < 5:
        await update.message.reply_text(
            "💬 Me faça uma pergunta sobre seus gastos ou envie uma foto de cupom fiscal."
        )
        return ConversationHandler.END

    await update.message.reply_text("🤔 Consultando...")
    await _answer_question(update, question, user["internal_id"])
    return ConversationHandler.END


async def _answer_question(update: Update, question: str, internal_user_id: str):
    try:
        sql    = question_to_sql(question, internal_user_id)
        rows   = run_query(sql)
        answer = format_answer(question, rows)
    except Exception as e:
        logger.error(f"Query error: {e}")
        answer = f"❌ Erro ao consultar: {e}"
    await update.message.reply_text(answer, parse_mode="Markdown")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TOKEN).build()

    # ConversationHandler wraps ALL interactions so email collection
    # can interrupt any action and resume after registration
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start",        cmd_start),
            CommandHandler("help",         cmd_help),
            CommandHandler("minha_conta",  cmd_minha_conta),
            CommandHandler("resumo",       cmd_resumo),
            CommandHandler("top",          cmd_top),
            CommandHandler("ultimas",      cmd_ultimas),
            MessageHandler(filters.PHOTO,          handle_photo),
            MessageHandler(filters.Document.IMAGE, handle_document),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
        ],
        states={
            WAITING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)
            ],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        per_user=True,
        per_chat=True,
    )

    app.add_handler(conv)

    logger.info("🤖 NF-e Bot started (multi-user).")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()