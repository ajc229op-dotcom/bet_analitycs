from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import requests
import sqlite3
from datetime import datetime, timezone
import hashlib
from flask import Flask
from threading import Thread

TOKEN = '8430071882:AAE04HZHhyb1Prg4K-kp_-EknNaK2yf6nbg'
ADMIN_ID = 6360623194
ODDS_API_KEY = '487a6ad1861a7d422de0d02daf747a03'
USUARIO_ENZONA = '55512345'
DIRECCION_USDT = '0x01fFC04c400d0811DEc106E56Bfb5a95576AF18f'

def init_db():
    conn = sqlite3.connect('bet_analitycs.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS usuarios (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0, referido_por INTEGER, fecha_registro TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS apuestas (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, partido TEXT, apuesta TEXT, monto REAL, cuota REAL, estado TEXT DEFAULT 'activa', fecha TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS depositos (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, monto REAL, metodo TEXT, comprobante TEXT, estado TEXT DEFAULT 'pendiente', fecha TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS retiros (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, monto REAL, metodo TEXT, destino TEXT, estado TEXT DEFAULT 'pendiente', fecha TEXT)")
    conn.commit()
    conn.close()

def short_id(text):
    return hashlib.md5(text.encode()).hexdigest()[:6]

def registrar_usuario(user_id, username, referido_por=None):
    conn = sqlite3.connect('bet_analitycs.db')
    cursor = conn.cursor()
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT OR IGNORE INTO usuarios (user_id, username, balance, referido_por, fecha_registro) VALUES (?,?, 0,?,?)', (user_id, username, referido_por, fecha))
    conn.commit()
    conn.close()

def obtener_balance(user_id):
    conn = sqlite3.connect('bet_analitycs.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM usuarios WHERE user_id =?', (user_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else 0

def teclado_principal():
    keyboard = [
        [KeyboardButton('🔴 EN VIVO'), KeyboardButton('🎰 Apostar')],
        [KeyboardButton('💵 Mi Dinero'), KeyboardButton('💳 Depositar')],
        [KeyboardButton('💸 Retirar'), KeyboardButton('👥 Referidos')]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref = None
    if context.args and context.args[0].isdigit():
        ref = int(context.args[0])
        if ref == user.id:
            ref = None
    registrar_usuario(user.id, user.username, ref)
    texto = '🎉 ¡Hola ' + user.first_name + '!\n\n💰 *Bet Analitycs* 💰\n\nTu ID: `' + str(user.id) + '`'
    if user.id == ADMIN_ID:
        texto = texto + '\n\n⚙️ *ERES ADMIN*'
    await update.message.reply_text(texto, parse_mode='Markdown', reply_markup=teclado_principal())

async def cuotas_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('⏳ Buscando partidos EN VIVO...')
    deportes = ['soccer_epl', 'soccer_spain_la_liga', 'soccer_uefa_champs_league', 'soccer_usa_mls']
    partidos_encontrados = 0
    if 'partidos' not in context.bot_data:
        context.bot_data['partidos'] = {}
    hoy = datetime.utcnow().strftime('%Y-%m-%d')
    for deporte in deportes:
        if partidos_encontrados >= 5: break
        try:
            url = 'https://api.the-odds-api.com/v4/sports/' + deporte + '/odds/?apiKey=' + ODDS_API_KEY + '&regions=eu&markets=h2h&commenceTimeFrom=' + hoy + 'T00:00:00Z&commenceTimeTo=' + hoy + 'T23:59:59Z'
            r = requests.get(url, timeout=10)
            if r.status_code!= 200: continue
            respuesta = r.json()
            if not respuesta: continue
            for p in respuesta:
                if partidos_encontrados >= 5: break
                commence_time = p.get('commence_time', '')
                if not commence_time: continue
                ahora = datetime.now(timezone.utc)
                inicio = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
                if inicio > ahora: continue
                local = p['home_team']
                visita = p['away_team']
                score = p.get('scores', [])
                if score and len(score) > 0:
                    marcador = str(score[0].get('score', '0')) + '-' + str(score[1].get('score', '0'))
                else:
                    marcador = 'EN VIVO'
                if not p.get('bookmakers'): continue
                try:
                    datos = p['bookmakers'][0]['markets'][0]['outcomes']
                    c1 = datos[0]['price']
                    cX = datos[1]['price']
                    c2 = datos[2]['price']
                except:
                    continue
                partido_key = local + ' vs ' + visita
                sid = short_id(partido_key)
                context.bot_data['partidos'][sid] = partido_key
                texto = '🔴 ' + local + ' vs ' + visita + ' | ' + marcador
                btn1 = InlineKeyboardButton('1 @' + str(c1), callback_data='ap_1_' + str(c1) + '_' + sid)
                btnX = InlineKeyboardButton('X @' + str(cX), callback_data='ap_X_' + str(cX) + '_' + sid)
                btn2 = InlineKeyboardButton('2 @' + str(c2), callback_data='ap_2_' + str(c2) + '_' + sid)
                keyboard = [[btn1, btnX, btn2]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(texto, parse_mode='Markdown', reply_markup=reply_markup)
                partidos_encontrados += 1
        except Exception as e:
            print('Error:', str(e))
            continue
    if partidos_encontrados == 0:
        await update.message.reply_text('❌ No hay partidos EN VIVO ahora mismo\nPrueba más tarde')

async def mi_dinero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balance = obtener_balance(update.effective_user.id)
    await update.message.reply_text('💰 *MI DINERO* 💰\n\nBalance: `' + str(balance) + ' USD`', parse_mode='Markdown')

async def depositar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn1 = InlineKeyboardButton('📱 EnZona', callback_data='dep_enzona')
    btn2 = InlineKeyboardButton('🇨🇺 USDT BEP20', callback_data='dep_usdt')
    keyboard = [[btn1, btn2]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    texto = '💳 *DEPOSITAR* 💳\n\nMínimo: 5 USD\n\n1. Elige método\n2. Envía dinero\n3. Manda FOTO aquí\n4. Escribe `/comprobante 25`'
    await update.message.reply_text(texto, parse_mode='Markdown', reply_markup=reply_markup)

async def retirar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balance = obtener_balance(update.effective_user.id)
    if balance < 5:
        await update.message.reply_text('❌ Mínimo: 5 USD\nTu balance: ' + str(balance))
        return
    await update.message.reply_text('💸 *RETIRAR* 💸\n\nUsa: `/retirar 20 55551234`\nO `/retirar 50 0xABC...`', parse_mode='Markdown')

async def referidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_info = await context.bot.get_me()
    link = 'https://t.me/' + bot_info.username + '?start=' + str(user_id)
    conn = sqlite3.connect('bet_analitycs.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM usuarios WHERE referido_por=?', (user_id,))
    total_refs = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(monto) FROM depositos WHERE user_id IN (SELECT user_id FROM usuarios WHERE referido_por=?) AND estado='aprobado'", (user_id,))
    total_dep_refs = cursor.fetchone()[0] or 0
    ganancia = total_dep_refs * 0.05
    conn.close()
    texto = '👥 *REFERIDOS* 👥\n\nTu link:\n`' + link + '`\n\nReferidos: ' + str(total_refs) + '\nGanado: ' + str(round(ganancia,2)) + ' USD'
    await update.message.reply_text(texto, parse_mode='Markdown')

async def manejar_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ultima_foto'] = update.message.photo[-1].file_id
    await update.message.reply_text('📸 *Foto recibida*\n\nAhora escribe: `/comprobante 25`', parse_mode='Markdown')

async def comprobante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or 'Sin_username'
    if not context.args:
        await update.message.reply_text('❌ Uso: `/comprobante 25`')
        return
    try:
        monto = float(context.args[0])
    except:
        await update.message.reply_text('❌ Monto inválido')
        return
    if monto < 5:
        await update.message.reply_text('❌ Mínimo: 5 USD')
        return
    file_id = context.user_data.get('ultima_foto')
    if not file_id:
        await update.message.reply_text('❌ *PRIMERO MANDA LA FOTO*')
        return
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect('bet_analitycs.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO depositos (user_id,monto,metodo,comprobante,fecha) VALUES (?,?,?,?,?)', (user_id, monto, 'manual', file_id, fecha))
    dep_id = cursor.lastrowid
    conn.commit()
    conn.close()
    context.user_data['ultima_foto'] = None
    await update.message.reply_text('✅ *COMPROBANTE ENVIADO* #' + str(dep_id), parse_mode='Markdown')
    btn_aprobar = InlineKeyboardButton('✅ APROBAR', callback_data='dok_' + str(dep_id))
    btn_rechazar = InlineKeyboardButton('❌ RECHAZAR', callback_data='dno_' + str(dep_id))
    keyboard = [[btn_aprobar, btn_rechazar]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    texto_admin = '🔔 NUEVO DEPOSITO #' + str(dep_id) + '\n\nUser: @' + username + '\nID: ' + str(user_id) + '\nMonto: ' + str(monto) + ' USD'
    try:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=texto_admin, reply_markup=reply_markup)
    except Exception as e:
        await update.message.reply_text('❌ Error: ' + str(e))

async def apostar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    datos = context.user_data.get('apostando')
    if not datos:
        await update.message.reply_text('❌ Primero toca una cuota en 🔴 EN VIVO')
        return
    if not context.args:
        await update.message.reply_text('❌ Uso: `/apostar 10`', parse_mode='Markdown')
        return
    try:
        monto = float(context.args[0])
    except:
        await update.message.reply_text('❌ Monto inválido')
        return
    balance = obtener_balance(user_id)
    if monto < 1:
        await update.message.reply_text('❌ Mínimo: 1 USD')
        return
    if monto > balance:
        await update.message.reply_text('❌ No tienes saldo. Balance: ' + str(balance) + ' USD')
        return
    conn = sqlite3.connect('bet_analitycs.db')
    cursor = conn.cursor()
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('UPDATE usuarios SET balance = balance -? WHERE user_id=?', (monto, user_id))
    cursor.execute('INSERT INTO apuestas (user_id, partido, apuesta, monto, cuota, fecha) VALUES (?,?,?,?,?,?)', (user_id, datos['partido'], datos['tipo'], monto, datos['cuota'], fecha))
    ap_id = cursor.lastrowid
    conn.commit()
    conn.close()
    posible_ganancia = round(monto * datos['cuota'], 2)
    context.user_data['apostando'] = None
    texto = '✅ *APUESTA CONFIRMADA* #' + str(ap_id) + '\n\n⚽ ' + datos['partido'] + '\n🎯 Apostaste: *' + datos['tipo'] + '* @ `' + str(datos['cuota']) + '`\n💵 Monto: `' + str(monto) + ' USD`\n\n💰 Posible ganancia: `' + str(posible_ganancia) + ' USD`'
    await update.message.reply_text(texto, parse_mode='Markdown')

async def retirar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = obtener_balance(user_id)
    if balance < 5:
        await update.message.reply_text('❌ Mínimo: 5 USD')
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text('❌ Uso: `/retirar 20 55551234`', parse_mode='Markdown')
        return
    try:
        monto = float(context.args[0])
        destino = context.args[1]
    except:
        await update.message.reply_text('❌ Monto inválido')
        return
    if monto < 5 or monto > balance:
        await update.message.reply_text('❌ Monto inválido')
        return
    metodo = 'USDT' if destino.startswith('0x') else 'EnZona'
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect('bet_analitycs.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET balance = balance -? WHERE user_id=?', (monto, user_id))
    cursor.execute('INSERT INTO retiros (user_id,monto,metodo,destino,fecha) VALUES (?,?,?,?,?)', (user_id, monto, metodo, destino, fecha))
    ret_id = cursor.lastrowid
    conn.commit()
    conn.close()
    btn_pagar = InlineKeyboardButton('✅ PAGADO', callback_data='rpago_' + str(ret_id))
    btn_rech = InlineKeyboardButton('❌ RECHAZAR', callback_data='rno_' + str(ret_id))
    keyboard = [[btn_pagar, btn_rech]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    texto_admin = '💸 *NUEVO RETIRO* #' + str(ret_id) + '\n\nUser: ' + str(user_id) + '\nMonto: `' + str(monto) + ' USD`\nDestino: `' + destino + '`'
    await update.message.reply_text('✅ *RETIRO SOLICITADO* #' + str(ret_id), parse_mode='Markdown')
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=texto_admin, parse_mode='Markdown', reply_markup=reply_markup)
    except:
        pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    if data.startswith('ap_'):
        partes = data.split('_')
        tipo = partes[1]
        cuota = float(partes[2])
        sid = partes[3]
        partido = context.bot_data.get('partidos', {}).get(sid, 'Partido desconocido')
        context.user_data['apostando'] = {'partido': partido, 'tipo': tipo, 'cuota': cuota, 'sid': sid}
        texto = '🎯 *APOSTANDO* 🎯\n\nPartido: *' + partido + '*\nApuesta: *' + tipo + '* @ `' + str(cuota) + '`\n\n💵 Escribe el monto:\nEjemplo: `/apostar 10`'
        await query.edit_message_text(texto, parse_mode='Markdown')
        return
    if data == 'dep_enzona':
        texto = '📱 *ENZONA*\n\nEnvía a: `' + USUARIO_ENZONA + '`\nEn nota pon ID: `' + str(user_id) + '`\n\nLuego manda FOTO + `/comprobante 25`'
        await query.edit_message_text(texto, parse_mode='Markdown')
    elif data == 'dep_usdt':
        texto = '🇨🇺 *USDT BEP20*\n\nDirección:\n`' + DIRECCION_USDT + '`\n\nLuego manda FOTO + `/comprobante 25`'
        await query.edit_message_text(texto, parse_mode='Markdown')
    elif data.startswith('dok_'):
        if user_id!= ADMIN_ID: return
        dep_id = int(data.split('_')[1])
        conn = sqlite3.connect('bet_analitycs.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, monto FROM depositos WHERE id=? AND estado="pendiente"', (dep_id,))
        dep = cursor.fetchone()
        if not dep:
            await query.edit_message_caption('❌ Ya procesado')
            conn.close()
            return
        user_dep, monto = dep
        cursor.execute('UPDATE depositos SET estado="aprobado" WHERE id=?', (dep_id,))
        cursor.execute('UPDATE usuarios SET balance = balance +? WHERE user_id=?', (monto, user_dep))
        cursor.execute('SELECT referido_por FROM usuarios WHERE user_id=?', (user_dep,))
        ref = cursor.fetchone()
        if ref and ref[0]:
            comision = monto * 0.05
            cursor.execute('UPDATE usuarios SET balance = balance +? WHERE user_id=?', (comision, ref[0]))
            try:
                await context.bot.send_message(chat_id=ref[0], text='💰 *COMISIÓN*\n\n+' + str(round(comision,2)) + ' USD', parse_mode='Markdown')
            except:
                pass
        conn.commit()
        conn.close()
        await query.edit_message_caption('✅ Depósito #' + str(dep_id) + ' APROBADO\n+' + str(monto) + ' USD')
        try:
            await context.bot.send_message(chat_id=user_dep, text='✅ *DEPÓSITO APROBADO*\n\n+' + str(round(monto, 2)) + ' USD', parse_mode='Markdown')
        except:
            pass
    elif data.startswith('dno_'):
        if user_id!= ADMIN_ID: return
        dep_id = int(data.split('_')[1])
        conn = sqlite3.connect('bet_analitycs.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM depositos WHERE id=?', (dep_id,))
        user_dep = cursor.fetchone()[0]
        cursor.execute('UPDATE depositos SET estado="rechazado" WHERE id=?', (dep_id,))
        conn.commit()
        conn.close()
        await query.edit_message_caption('❌ Depósito #' + str(dep_id) + ' RECHAZADO')
        try:
            await context.bot.send_message(chat_id=user_dep, text='❌ *DEPÓSITO RECHAZADO*', parse_mode='Markdown')
        except:
            pass

async def manejar_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if texto == '🔴 EN VIVO' or texto == '🎰 Apostar':
        await cuotas_live(update, context)
    elif texto == '💵 Mi Dinero':
        await mi_dinero(update, context)
    elif texto == '💳 Depositar':
        await depositar(update, context)
    elif texto == '💸 Retirar':
        await retirar(update, context)
    elif texto == '👥 Referidos':
        await referidos(update, context)

web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot Bet Analitycs vivo"

def run_web():
    web_app.run(host='0.0.0.0', port=8080)

if __name__ == '__main__':
    init_db()
    Thread(target=run_web).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('live', cuotas_live))
    app.add_handler(CommandHandler('dinero', mi_dinero))
    app.add_handler(CommandHandler('depositar', depositar))
    app.add_handler(CommandHandler('retirar', retirar_cmd))
    app.add_handler(CommandHandler('comprobante', comprobante))
    app.add_handler(CommandHandler('referidos', referidos))
    app.add_handler(CommandHandler('apostar', apostar_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, manejar_foto))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_botones))
    print('BOT INICIADO')
    app.run_polling()
