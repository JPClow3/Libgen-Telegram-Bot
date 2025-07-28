import logging
import os
import tempfile
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Carregue as variáveis de ambiente de um arquivo .env para desenvolvimento local
# Em produção (Heroku), defina estas variáveis diretamente nas configurações do app
from dotenv import load_dotenv

load_dotenv()

from BookInfo import BookInfoProvider

# Habilitar logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# Função para o comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envia uma mensagem de boas-vindas quando o comando /start é emitido."""
    await update.message.reply_html(
        "Olá! Envie-me o título de um livro e eu tentarei encontrá-lo no Libgen."
    )


# Função para pesquisar livros
async def search_books(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pesquisa por livros com base no texto do usuário e mostra os resultados."""
    search_query = update.message.text
    await update.message.reply_text("Buscando... Por favor, aguarde.")

    try:
        provider = BookInfoProvider()
        books = provider.load_book_list(search_query, 'title')

        if not books:
            await update.message.reply_text("Desculpe, nenhum livro encontrado com esse título. Tente outro.")
            return

        # Armazena os resultados no contexto do usuário para uso posterior no callback
        context.user_data['search_results'] = books

        # Formata a lista de livros em uma única mensagem
        message_text = "Encontrei os seguintes livros:\n\n"
        keyboard = []
        for i, book in enumerate(books):
            message_text += f"{i + 1}. <b>{book.title}</b>\n"
            message_text += f"   Autor: {book.authors}\n"
            message_text += f"   Formato: {book.format}, Tamanho: {book.size}\n\n"
            # Adiciona um botão para cada livro com seu índice como callback_data
            keyboard.append([InlineKeyboardButton(f"Baixar Livro {i + 1}", callback_data=str(i))])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Ocorreu um erro durante a busca: {e}")
        await update.message.reply_text("Ocorreu um erro. Por favor, tente novamente mais tarde.")


# Função de callback para o botão de download
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa o clique no botão de download."""
    query = update.callback_query
    await query.answer()

    try:
        book_index = int(query.data)
        books = context.user_data.get('search_results')

        if not books or book_index >= len(books):
            await query.edit_message_text(text="Erro: resultados da pesquisa expiraram. Por favor, pesquise novamente.")
            return

        selected_book = books[book_index]
        download_link = selected_book.download_links[0]

        await query.edit_message_text(text=f"Baixando '{selected_book.title}'... Isso pode levar um momento.")

        # Baixa o arquivo
        response = requests.get(download_link, stream=True)
        response.raise_for_status()  # Gera um erro para respostas ruins (4xx ou 5xx)

        # Usa um arquivo temporário para salvar o livro
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{selected_book.format}") as temp_file:
            temp_file.write(response.content)
            temp_path = temp_file.name

        # Envia o arquivo para o usuário
        with open(temp_path, 'rb') as document:
            await context.bot.send_document(chat_id=query.message.chat_id, document=document,
                                            filename=f"{selected_book.title}.{selected_book.format}")

        # Limpa o arquivo temporário
        os.remove(temp_path)

    except Exception as e:
        logger.error(f"Falha no download ou envio: {e}")
        await query.message.reply_text("Desculpe, falha ao baixar o livro.")


def main() -> None:
    """Inicia o bot."""
    # Pega o token da variável de ambiente
    TOKEN = os.getenv("TELEGRAM_ACCESS_TOKEN")
    if not TOKEN:
        raise ValueError("Nenhum TELEGRAM_ACCESS_TOKEN encontrado nas variáveis de ambiente")

    # Cria a Aplicação
    application = Application.builder().token(TOKEN).build()

    # Adiciona os handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_books))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Inicia o bot (modo polling)
    application.run_polling()


if __name__ == "__main__":
    main()