import os
import telebot
import requests
import json

TELEGRAM_BOT_TOKEN = ('7825591642:AAGh4zVMhLdOSnW-FV-FPaq5f5OVxiia3xw')
API_URL = os.getenv('BOOK_API_URL', 'https://www.api.staisenorituban.ac.id/search_books')
STATS_URL = os.getenv('BOOK_STATS_URL', 'https://www.api.staisenorituban.ac.id/stats')
DIRECT_LINK_URL = os.getenv('BOOK_DIRECT_LINK_URL', 'https://www.api.staisenorituban.ac.id/get_direct_link/')
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# State per user: user_id -> (last_query, last_results, page, bookmarks)
user_state = {}

RESULTS_PER_PAGE = 5

def fetch_books(query, page=1):
    resp = requests.get(API_URL, params={'q': query})
    if resp.status_code == 200:
        results = resp.json()
        # Pagination
        start = (page-1)*RESULTS_PER_PAGE
        end = start+RESULTS_PER_PAGE
        return results[start:end], len(results), results
    return [], 0, []

def fetch_stats():
    try:
        resp = requests.get(STATS_URL)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, (
        "Selamat datang di Bot Buku!\n"
        "Ketik judul/author/publisher buku yang ingin dicari.\n"
        "Contoh: sapiens\n"
        "Perintah lain:\n"
        "/search [kata kunci] - Cari buku\n"
        "/bookmark - Lihat daftar favorit\n"
        "/stats - Statistik database\n"
    ))

@bot.message_handler(commands=['search'])
def handle_search_cmd(message):
    query = message.text[len('/search'):].strip()
    if not query:
        bot.reply_to(message, "Masukkan kata kunci setelah /search")
        return
    show_search_results(message, query, page=1)

@bot.message_handler(commands=['bookmark'])
def handle_bookmark(message):
    bookmarks = user_state.get(message.from_user.id, {}).get('bookmarks', [])
    if not bookmarks:
        bot.reply_to(message, "Belum ada buku favorit. Balas hasil pencarian dengan /fav nomor untuk menambah.")
        return
    msg = "📚 <b>Daftar Favorit Anda:</b>\n"
    for idx, row in enumerate(bookmarks, 1):
        msg += (
            f"{idx}. <b>{row['title']}</b> - {row['author']} - {row['publisher']} [{row['extension']}]\n"
            f"🔗 <a href=\"{row['book_url']}\">Link Buku</a>\n"
        )
        if row.get('files_url_drive'):
            msg += f"🔗 <code>{row['files_url_drive']}</code>\n"
        msg += "\n"
    bot.send_message(message.chat.id, msg, parse_mode='HTML', disable_web_page_preview=False)

@bot.message_handler(commands=['stats'])
def handle_stats(message):
    stats = fetch_stats()
    if not stats:
        bot.reply_to(message, "Statistik tidak tersedia.")
        return
    msg = (
        f"📊 <b>Statistik Buku</b>\n"
        f"Total: <b>{stats.get('total', '-')}</b>\n"
        f"Uploaded: <b>{stats.get('uploaded', '-')}</b>\n"
        f"Cover: <b>{stats.get('cover', '-')}</b>\n"
        f"Downloaded: <b>{stats.get('downloaded', '-')}</b>\n"
        f"Failed: <b>{stats.get('failed', '-')}</b>\n"
    )
    bot.send_message(message.chat.id, msg, parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith('/fav'))
def handle_fav(message):
    # /fav 1,2,3
    state = user_state.get(message.from_user.id)
    if not state or not state.get('last_results'):
        bot.reply_to(message, "Cari buku dulu, lalu balas dengan /fav nomor.")
        return
    choices = message.text[len('/fav'):].replace(' ', '').split(',')
    bookmarks = user_state.get(message.from_user.id, {}).get('bookmarks', [])
    for c in choices:
        try:
            idx = int(c) - 1
            if 0 <= idx < len(state['last_results']):
                row = state['last_results'][idx]
                if row not in bookmarks:
                    bookmarks.append(row)
        except Exception:
            continue
    user_state[message.from_user.id]['bookmarks'] = bookmarks
    bot.reply_to(message, f"Ditambahkan ke favorit ({len(bookmarks)} buku).")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    # Jika user reply dengan angka, proses pilihan
    if message.from_user.id in user_state:
        state = user_state[message.from_user.id]
        if state.get('last_results'):
            if message.text.isdigit() or ',' in message.text:
                handle_choice(message)
                return
    # Jika bukan, anggap sebagai query baru
    show_search_results(message, message.text.strip(), page=1)

def show_search_results(message, query, page=1):
    results, total, all_results = fetch_books(query, page)
    if not results:
        bot.reply_to(message, "Tidak ada hasil ditemukan.")
        return
    user_state[message.from_user.id] = {
        'last_query': query,
        'last_results': results,
        'page': page,
        'bookmarks': user_state.get(message.from_user.id, {}).get('bookmarks', [])
    }
    for idx, row in enumerate(results, 1):
        msg = (
            f"{idx}. <b>{row['title']}</b> - {row['author']} - {row['publisher']} [{row['extension']}]"
        )
        keyboard = telebot.types.InlineKeyboardMarkup()
        if row.get('files_url_drive'):
            keyboard.add(telebot.types.InlineKeyboardButton(
                "Download", callback_data=f"download_{row['id']}"
            ))
        # Pagination tombol Next/Prev hanya di hasil terakhir
        if idx == len(results):
            if page > 1:
                keyboard.add(telebot.types.InlineKeyboardButton("⬅️ Prev", callback_data=f"prev_{query}_{page-1}"))
            if total > page*RESULTS_PER_PAGE:
                keyboard.add(telebot.types.InlineKeyboardButton("Next ➡️", callback_data=f"next_{query}_{page+1}"))
        bot.send_message(message.chat.id, msg, parse_mode='HTML', reply_markup=keyboard, disable_web_page_preview=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('next_') or call.data.startswith('prev_'))
def handle_pagination(call):
    _, query, page = call.data.split('_', 2)
    show_search_results(call.message, query, int(page))
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('download_'))
def handle_download(call):
    book_id = call.data.split('_', 1)[1]
    resp = requests.get(f"{DIRECT_LINK_URL}{book_id}")
    if resp.status_code == 200:
        data = resp.json()
        link = data.get('direct_link')
        if link:
            bot.send_message(call.message.chat.id, f"🔗 <a href=\"{link}\">Download File</a>", parse_mode='HTML')
        else:
            bot.send_message(call.message.chat.id, "Link download tidak tersedia.")
    else:
        bot.send_message(call.message.chat.id, "File tidak ditemukan.")
    bot.answer_callback_query(call.id)

def handle_choice(message):
    state = user_state.get(message.from_user.id)
    if not state or not state.get('last_results'):
        bot.reply_to(message, "Tidak ada hasil pencarian aktif. Cari dulu judul/author/publisher.")
        return
    choices = message.text.replace(' ', '').split(',')
    reply = ""
    for c in choices:
        try:
            idx = int(c) - 1
            if 0 <= idx < len(state['last_results']):
                row = state['last_results'][idx]
                status = "✅ Sudah di GDrive" if row.get('files_url_drive') else "❌ Belum di GDrive"
                reply += (
                    f"📚 <b>{row['title']}</b>\n"
                    f"👤 {row['author']}\n"
                    f"🏢 {row['publisher']}\n"
                    f"🔗 <a href=\"{row['book_url']}\">Link Buku</a>\n"
                    f"{status}\n"
                )
                if row.get('files_url_drive'):
                    reply += f"🔗 <code>{row['files_url_drive']}</code>\n"
                reply += "\n"
        except Exception:
            continue
    if reply:
        bot.send_message(message.chat.id, reply, parse_mode='HTML', disable_web_page_preview=False)
    else:
        bot.reply_to(message, "Nomor tidak valid. Balas dengan nomor dari hasil pencarian.")

if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling() 
