// -*- coding: utf-8 -*-
/**
 * Servidor de WhatsApp 24/7 para Diagnóstico Citopatológico INLE, C.A.
 * Utiliza @whiskeysockets/baileys (Ilimitado y 100% Gratis)
 * Dra. Aramís Romero - Maturín, Monagas
 */

const express = require('express');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const pino = require('pino');
const QRCode = require('qrcode');
const qrcodeTerminal = require('qrcode-terminal');
const { exec, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const cron = require('node-cron');
const { Pool } = require('pg');

const app = express();
const PORT = process.env.PORT || 3000;

// Configuración de PostgreSQL (Supabase) para persistencia permanente de sesión
let pool = null;
if (process.env.DATABASE_URL) {
    try {
        pool = new Pool({
            connectionString: process.env.DATABASE_URL,
            ssl: { rejectUnauthorized: false }
        });
        console.log('[PostgreSQL] Conexión configurada con Supabase.');
    } catch (err) {
        console.error('[PostgreSQL Error]:', err.message);
    }
}

// Prevención de caídas por errores no controlados o desconexiones de socket
process.on('uncaughtException', (err) => {
    console.error('[UNCAUGHT EXCEPTION PREVENIDA]:', err.message || err);
});
process.on('unhandledRejection', (reason) => {
    console.error('[UNHANDLED REJECTION PREVENIDA]:', reason);
});

// Normalizar barras dobles que envía el proxy reverso de nginx (ej. //api/... -> /api/...)
app.use((req, res, next) => {
    req.url = req.url.replace(/\/+/g, '/');
    next();
});

app.use(express.json());

let sock = null;
let lastQR = null;
let connectionStatus = 'desconectado'; // 'desconectado', 'esperando_qr', 'conectado'
let connectedPhone = '';

// Captions para los 3 estados oficiales de WhatsApp
const CAPTIONS = {
    "01_TASA_BCV_HOY.png": "Tasa Oficial B.C.V. de hoy. Aceptamos transferencias y Pago Móvil. Diagnóstico Citopatológico INLE, C.A.",
    "02_SEDE_Y_RECEPCION_OFICIAL.png": "Estamos ubicados en Av. Bicentenario, Edif. Multicentro Profesional Bicentenario, Piso Mezzanina Local 03 (frente a la escalera), cerca del Hospital Manuel Núñez Tovar, al lado de COBY y MRW.",
    "03_SERVICIOS_ESPECIALIZADOS.png": "Estamos a su servicio. Citologías, Biopsias, PAAF, Tipificación VPH e Inmunohistoquímica con criterio de especialista. Tel: (0426) 960.18.58."
};

// ==============================================================================
// GESTOR DE CONTACTOS (Requerido para publicar estados en WhatsApp multi-dispositivo)
// ==============================================================================
const contactsPath = path.join(__dirname, 'contactos_guardados.json');
let knownContacts = new Set();
try {
    if (fs.existsSync(contactsPath)) {
        const arr = JSON.parse(fs.readFileSync(contactsPath, 'utf8'));
        if (Array.isArray(arr)) knownContacts = new Set(arr);
    }
} catch (e) {
    console.error('[Aviso contactos]:', e.message);
}

function guardarContacto(jid) {
    if (!jid || jid.includes('@g.us') || jid.includes('broadcast')) return;
    const cleanJid = jid.split(':')[0] + '@s.whatsapp.net';
    if (!knownContacts.has(cleanJid)) {
        knownContacts.add(cleanJid);
        try {
            fs.writeFileSync(contactsPath, JSON.stringify(Array.from(knownContacts), null, 2), 'utf8');
        } catch (e) {}
    }
}

// ==============================================================================
// GESTOR DE PAUSAS DEL BOT (Atención Humana / Handoff a la Dra. Aramís o Recepción)
// Cuando un paciente solicita atención humana, el bot se silencia por 24 horas
// para que el personal pueda conversar libremente sin interrupciones automáticas.
// ==============================================================================
const pausasPath = path.join(__dirname, 'pausas_bot.json');
let pausasBot = {};

function cargarPausas() {
    try {
        if (fs.existsSync(pausasPath)) {
            pausasBot = JSON.parse(fs.readFileSync(pausasPath, 'utf8')) || {};
            // Limpiar pausas vencidas
            const now = Date.now();
            let modificado = false;
            for (const [tel, expira] of Object.entries(pausasBot)) {
                if (now > expira) {
                    delete pausasBot[tel];
                    modificado = true;
                }
            }
            if (modificado) guardarPausas();
        }
    } catch (e) {
        console.error('[Aviso pausas bot]:', e.message);
        pausasBot = {};
    }
}

function guardarPausas() {
    try {
        fs.writeFileSync(pausasPath, JSON.stringify(pausasBot, null, 2), 'utf8');
    } catch (e) {
        console.error('[Error guardando pausas_bot.json]:', e.message);
    }
}

function estaEnPausa(jid) {
    if (!jid) return false;
    const cleanId = jid.split(':')[0].replace(/[^0-9]/g, '');
    const expira = pausasBot[cleanId];
    if (!expira) return false;
    if (Date.now() > expira) {
        delete pausasBot[cleanId];
        guardarPausas();
        return false;
    }
    return true;
}

function pausarBot(jid, horas = 24) {
    if (!jid) return;
    const cleanId = jid.split(':')[0].replace(/[^0-9]/g, '');
    const expira = Date.now() + (horas * 60 * 60 * 1000);
    pausasBot[cleanId] = expira;
    guardarPausas();
    const fechaExpira = new Date(expira).toLocaleString('es-VE', { timeZone: 'America/Caracas' });
    console.log(`🔇 [PAUSA DE BOT ACTIVADA] Paciente +${cleanId} silenciado por ${horas}h (hasta ${fechaExpira}).`);
}

function despausarBot(jid) {
    if (!jid) return;
    const cleanId = jid.split(':')[0].replace(/[^0-9]/g, '');
    if (pausasBot[cleanId]) {
        delete pausasBot[cleanId];
        guardarPausas();
        console.log(`🔊 [PAUSA DE BOT REMOVIDA] Bot reactivado para paciente +${cleanId}.`);
    }
}

function cargarRespuestas() {
    try {
        const respPath = path.join(__dirname, 'respuestas.json');
        if (fs.existsSync(respPath)) {
            return JSON.parse(fs.readFileSync(respPath, 'utf8'));
        }
    } catch (e) {
        console.error('[Error leyendo respuestas.json]:', e.message);
    }
    return {};
}

cargarPausas();

/**
 * Llama al motor en Python (bot_motor.py) de forma asíncrona, concurrente y resistente a fallos.
 */
function consultarBotPython(texto) {
    return new Promise((resolve) => {
        let resuelto = false;

        const temporizador = setTimeout(() => {
            if (!resuelto) {
                resuelto = true;
                resolve("Estimado paciente, en breve un especialista de *Diagnóstico Citopatológico INLE, C.A.* se pondrá en contacto con usted.");
            }
        }, 4000);

        try {
            const py = spawn('python3', [
                '-c',
                `import bot_motor, sys; sys.stdout.reconfigure(encoding='utf-8'); print(bot_motor.responder_mensaje(sys.stdin.read()))`
            ], { cwd: __dirname });

            let salida = '';
            py.stdout.on('data', (data) => {
                salida += data.toString('utf-8');
            });

            py.stderr.on('data', (err) => {
                console.error('[Error Python Bot]:', err.toString());
            });

            py.on('close', () => {
                clearTimeout(temporizador);
                if (!resuelto) {
                    resuelto = true;
                    if (salida.trim()) {
                        resolve(salida.trim());
                    } else {
                        resolve("Estimado paciente, en breve un especialista de *Diagnóstico Citopatológico INLE, C.A.* se pondrá en contacto con usted.");
                    }
                }
            });

            py.on('error', (err) => {
                clearTimeout(temporizador);
                console.error('[Error spawn python]:', err);
                if (!resuelto) {
                    resuelto = true;
                    resolve("Estimado paciente, en breve un especialista de *Diagnóstico Citopatológico INLE, C.A.* se pondrá en contacto con usted.");
                }
            });

            py.stdin.write(texto || "");
            py.stdin.end();

        } catch (e) {
            clearTimeout(temporizador);
            console.error('[Excepción consultarBotPython]:', e);
            if (!resuelto) {
                resuelto = true;
                resolve("Estimado paciente, en breve un especialista de *Diagnóstico Citopatológico INLE, C.A.* se pondrá en contacto con usted.");
            }
        }
    });
}

// ==============================================================================
// PERSISTENCIA DE SESIÓN EN SUPABASE (Evita tener que reescanear el QR en Render)
// ==============================================================================
async function initSessionTable() {
    if (!pool) return;
    try {
        await pool.query(`
            CREATE TABLE IF NOT EXISTS whatsapp_session (
                id VARCHAR(255) PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        `);
        console.log('[Supabase Auth] Tabla whatsapp_session verificada en Supabase.');
    } catch (e) {
        console.error('[Error initSessionTable]:', e.message);
    }
}

async function restoreSessionFromDB(authDir) {
    if (!pool) return;
    try {
        if (!fs.existsSync(authDir)) {
            fs.mkdirSync(authDir, { recursive: true });
        }
        const res = await pool.query('SELECT id, data FROM whatsapp_session');
        if (res.rows && res.rows.length > 0) {
            console.log(`[Supabase Auth] 📥 Restaurando ${res.rows.length} archivos de sesión desde Supabase...`);
            for (const row of res.rows) {
                const filePath = path.join(authDir, row.id);
                fs.writeFileSync(filePath, row.data, 'utf-8');
            }
            console.log('[Supabase Auth] ✅ Sesión de WhatsApp restaurada con éxito desde la nube.');
        } else {
            console.log('[Supabase Auth] No hay sesión previa en Supabase. Esperando primer escaneo de QR.');
        }
    } catch (e) {
        console.error('[Error restoreSessionFromDB]:', e.message);
    }
}

async function syncAllSessionFilesToDB(authDir) {
    if (!pool) return;
    try {
        if (!fs.existsSync(authDir)) return;
        const files = fs.readdirSync(authDir);
        for (const fileName of files) {
            const filePath = path.join(authDir, fileName);
            if (fs.statSync(filePath).isFile()) {
                const fileData = fs.readFileSync(filePath, 'utf-8');
                await pool.query(`
                    INSERT INTO whatsapp_session (id, data, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW();
                `, [fileName, fileData]);
            }
        }
        console.log(`[Supabase Auth] 💾 ${files.length} archivos de sesión respaldados en Supabase.`);
    } catch (e) {
        console.error('[Error syncAllSessionFilesToDB]:', e.message);
    }
}

/**
 * Inicia la conexión de WhatsApp con Baileys.
 */
async function conectarWhatsApp() {
    const authDir = path.join(__dirname, 'auth_info_baileys');
    await initSessionTable();
    await restoreSessionFromDB(authDir);

    const { state, saveCreds } = await useMultiFileAuthState(authDir);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
        version,
        logger: pino({ level: 'silent' }),
        auth: state,
        printQRInTerminal: false,
        browser: ['INLE Laboratorio', 'Chrome', '1.0.0']
    });

    sock.ev.on('creds.update', async () => {
        await saveCreds();
        syncAllSessionFilesToDB(authDir).catch(() => {});
    });

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            lastQR = qr;
            connectionStatus = 'esperando_qr';
            console.log('\n=============================================================');
            console.log(' 📲 ESCANEE ESTE CÓDIGO QR CON EL WHATSAPP DE LA DOCTORA:');
            console.log(' (O abra https://inle.duckdns.org/whatsapp en su navegador)');
            console.log('=============================================================\n');
            qrcodeTerminal.generate(qr, { small: true });
        }

        if (connection === 'open') {
            connectionStatus = 'conectado';
            lastQR = null;
            connectedPhone = sock.user?.id ? sock.user.id.split(':')[0] : 'Conectado';
            console.log(`\n[OK] WhatsApp Conectado exitosamente. Teléfono: +${connectedPhone}`);
            if (sock.user?.id) guardarContacto(sock.user.id);
            syncAllSessionFilesToDB(authDir).catch(() => {});
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            connectionStatus = 'desconectado';
            console.log(`[Aviso] Conexión cerrada (${statusCode}). Reconectando: ${shouldReconnect}`);

            if (shouldReconnect) {
                setTimeout(conectarWhatsApp, 3000);
            } else {
                console.log('[Aviso] Sesión cerrada. Limpiando credenciales para nuevo QR...');
                try {
                    fs.rmSync(authDir, { recursive: true, force: true });
                    if (pool) pool.query('DELETE FROM whatsapp_session').catch(() => {});
                } catch (e) {}
                setTimeout(conectarWhatsApp, 2000);
            }
        }
    });

    // Registrar contactos cuando se sincronicen
    sock.ev.on('contacts.upsert', (contacts) => {
        if (Array.isArray(contacts)) {
            for (const c of contacts) {
                if (c && c.id) guardarContacto(c.id);
            }
        }
    });

    // Sincronizar libreta de contactos y chats del teléfono para difusión de estados
    sock.ev.on('contacts.upsert', (contacts) => {
        if (!contacts) return;
        for (const c of contacts) {
            if (c.id && !c.id.includes('@g.us') && !c.id.includes('broadcast')) {
                guardarContacto(c.id);
            }
        }
    });

    sock.ev.on('contacts.update', (updates) => {
        if (!updates) return;
        for (const u of updates) {
            if (u.id && !u.id.includes('@g.us') && !u.id.includes('broadcast')) {
                guardarContacto(u.id);
            }
        }
    });

    sock.ev.on('messaging-history.set', ({ contacts, chats }) => {
        let count = 0;
        if (contacts) {
            for (const c of contacts) {
                if (c.id && !c.id.includes('@g.us') && !c.id.includes('broadcast')) {
                    guardarContacto(c.id);
                    count++;
                }
            }
        }
        if (chats) {
            for (const ch of chats) {
                if (ch.id && !ch.id.includes('@g.us') && !ch.id.includes('broadcast')) {
                    guardarContacto(ch.id);
                    count++;
                }
            }
        }
        console.log(`[Contactos sincronizados]: Guardados ${count} contactos para audiencia de estados.`);
    });

    // Escuchar mensajes entrantes de pacientes
    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify') return;

        for (const msg of messages) {
            if (!msg.message || msg.key.fromMe) continue;

            const from = msg.key.remoteJid;
            if (!from || from.endsWith('@g.us') || from.includes('broadcast')) continue;

            guardarContacto(from);

            const esImagen = !!(msg.message.imageMessage || msg.message.documentMessage);
            const caption = (msg.message.imageMessage?.caption || msg.message.documentMessage?.caption || '').trim();
            const texto = (msg.message.conversation ||
                          msg.message.extendedTextMessage?.text ||
                          caption ||
                          '').trim();

            const remitente = from.split('@')[0];
            const nombre = msg.pushName || 'Paciente';

            // CASO 0: Paciente en atención personalizada / humana activa (Bot silenciado por 24 horas)
            if (estaEnPausa(from)) {
                const cleanId = remitente.replace(/[^0-9]/g, '');
                const expiraObj = new Date(pausasBot[cleanId]);
                const expiraStr = expiraObj.toLocaleString('es-VE', { timeZone: 'America/Caracas' });
                console.log(`🔇 [BOT SILENCIADO] Mensaje de ${nombre} (+${remitente}) no respondido: atención humana activa hasta ${expiraStr}.`);
                continue;
            }

            // CASO 1: Paciente envió una foto o muestra sin caption
            if (esImagen && !caption) {
                console.log(`\n📸 [FOTO / MUESTRA RECIBIDA DE ${nombre} (+${remitente})]`);
                try {
                    const respuestas = cargarRespuestas();
                    const respFoto = respuestas.recepcion_foto_muestra ||
                        "📸 *¡Hemos recibido la foto de su orden médica / muestra! Muchas gracias.*\n\nNuestro equipo médico y la Dra. Aramís la evaluarán para indicarle el estudio exacto, presupuesto en divisas / bolívares (tasa BCV) y los requerimientos de entrega.\n\nPor favor, indíquenos también el nombre y cédula del paciente si no se aprecian en la foto.";
                    await sock.sendMessage(from, { text: respFoto }, { quoted: msg });
                } catch (err) {
                    console.error('[Error respondiendo a foto]:', err);
                }
                continue;
            }

            if (!texto) continue;

            console.log(`\n📩 [MENSAJE DE ${nombre} (+${remitente})]: "${texto}"${esImagen ? ' (con imagen adjunta)' : ''}`);

            try {
                // Si viene con imagen adjunta, consultar pasando el texto
                const consulta = esImagen ? `${texto} foto muestra` : texto;
                const respuesta = await consultarBotPython(consulta);
                console.log(`🤖 [RESPUESTA INLE]:\n${respuesta.substring(0, 100)}...\n`);
                await sock.sendMessage(from, { text: respuesta }, { quoted: msg });

                // Si la respuesta corresponde a atención humana / transferencia médica o el usuario eligió '8':
                // Pausar automáticamente el bot para este paciente por 24 horas (1 día completo)
                const esAtencionHumana = respuesta.includes("ATENCIÓN PERSONALIZADA") || 
                                         respuesta.includes("Hemos registrado su solicitud para hablar con nuestro equipo") ||
                                         texto.trim() === '8';

                if (esAtencionHumana) {
                    pausarBot(from, 24);
                    console.log(`👤 [TRANSFERENCIA A HUMANO] Bot silenciado 24h para +${remitente}. El personal del laboratorio puede conversar sin interferencias.`);
                }
            } catch (err) {
                console.error('[Error respondiendo mensaje]:', err);
            }
        }
    });
}

/**
 * Publica los 3 estados oficiales en WhatsApp Status.
 */
async function publicarEstadosHoy() {
    if (connectionStatus !== 'conectado' || !sock) {
        console.log('[Alerta] No se pueden publicar estados: WhatsApp no está conectado.');
        return { ok: false, error: "WhatsApp no está vinculado. Escanee el código QR primero." };
    }

    console.log('\n[PUBLICANDO ESTADOS DE HOY EN WHATSAPP STATUS]...');
    const estadosDir = path.join(__dirname, 'estados_hoy');

    // 1. Ejecutar el generador de estados en Python para actualizar la tasa BCV
    const genRes = await new Promise((resolve) => {
        exec('python3 generador_estados.py', { cwd: __dirname }, (error, stdout, stderr) => {
            if (error) {
                console.error('[Error generando estados]:', error.message || error);
                if (stderr) console.error('[Detalle stderr]:', stderr);
                resolve({ ok: false, error: error.message });
            } else {
                console.log(stdout.trim());
                resolve({ ok: true });
            }
        });
    });

    if (!genRes.ok) {
        return { ok: false, error: "Error al generar las imágenes de estados. Revise los registros del servidor." };
    }

    if (!fs.existsSync(estadosDir)) {
        console.log('[Error] No existe la carpeta estados_hoy.');
        return { ok: false, error: "No existe la carpeta con las imágenes de estados." };
    }

    const archivos = fs.readdirSync(estadosDir).filter(f => f.endsWith('.png')).sort();
    if (archivos.length === 0) {
        return { ok: false, error: "No se encontraron imágenes en la carpeta de estados." };
    }

    // Preparar lista de destinatarios (en multi-device se requiere statusJidList)
    const myJid = sock.user?.id ? (sock.user.id.split(':')[0] + '@s.whatsapp.net') : null;
    const recipients = Array.from(knownContacts);
    if (myJid && !recipients.includes(myJid)) {
        recipients.push(myJid);
    }
    // Si la lista solo tiene 1 persona (el remitente), no usamos statusJidList restrictivo
    const sendOptions = recipients.length > 1 ? { statusJidList: recipients } : {};

    let subidos = 0;
    for (const archivo of archivos) {
        const rutaImg = path.join(estadosDir, archivo);
        const caption = CAPTIONS[archivo] || "Diagnóstico Citopatológico INLE, C.A.";
        console.log(` -> Subiendo estado: ${archivo}... (Audiencia: ${recipients.length} contactos)`);

        try {
            const buffer = fs.readFileSync(rutaImg);
            await sock.sendMessage('status@broadcast', {
                image: buffer,
                caption: caption
            }, sendOptions);
            subidos++;
            console.log(`    [OK] Estado '${archivo}' publicado exitosamente.`);
            await new Promise(r => setTimeout(r, 2000));
        } catch (e) {
            console.error(`    [Error subiendo ${archivo}]:`, e.message || e);
        }
    }

    console.log(`[FIN] Proceso completado. Subidos ${subidos}/${archivos.length} estados.\n`);
    return { ok: subidos > 0, subidos, total: archivos.length };
}

// Programador Cron: Todos los días a las 00:00 (Medianoche hora Venezuela)
cron.schedule('0 0 * * *', () => {
    console.log('\n[00:00 DETECTADO] Iniciando ciclo automático diario de estados...');
    publicarEstadosHoy();
}, {
    timezone: "America/Caracas"
});

// ==============================================================================
// RUTAS Y PANEL WEB (Accesible en /whatsapp)
// ==============================================================================

app.get(['/api/ping', '/whatsapp/api/ping'], (req, res) => {
    res.json({ status: 'ok', service: 'inle-whatsapp-bot', connection: connectionStatus, time: new Date().toISOString() });
});

app.get(['/', '/whatsapp'], async (req, res) => {
    let qrImageHtml = '';

    if (connectionStatus === 'esperando_qr' && lastQR) {
        const qrDataUrl = await QRCode.toDataURL(lastQR, { width: 320, margin: 2 });
        qrImageHtml = `
            <div class="bg-white p-6 rounded-2xl shadow-xl inline-block border-2 border-slate-200">
                <img src="${qrDataUrl}" alt="Código QR WhatsApp" class="mx-auto rounded-lg" />
                <p class="mt-4 text-sm font-semibold text-slate-700">Abra WhatsApp en el celular &rarr; Dispositivos vinculados &rarr; Vincular dispositivo</p>
            </div>
            <div class="mt-5">
                <button onclick="cerrarBotAhora()" class="px-4 py-2 bg-slate-700 hover:bg-slate-600 active:scale-95 text-slate-300 font-semibold text-xs rounded-xl shadow transition-all">
                    🔄 Reiniciar / Generar nuevo QR
                </button>
            </div>
        `;
    } else if (connectionStatus === 'conectado') {
        qrImageHtml = `
            <div class="bg-emerald-50 border-2 border-emerald-500 p-8 rounded-2xl shadow-lg max-w-md mx-auto">
                <div class="w-16 h-16 bg-emerald-500 rounded-full flex items-center justify-center mx-auto text-white text-3xl font-bold shadow">✓</div>
                <h3 class="text-xl font-bold text-emerald-800 mt-4">¡WhatsApp Vinculado con Éxito!</h3>
                <p class="text-emerald-700 text-sm mt-2">El bot está activo y atendiendo pacientes 24 horas al día.</p>
                <div class="mt-4 inline-block bg-white px-4 py-2 rounded-full border border-emerald-300 text-xs font-bold text-emerald-800">
                    Número en línea: +${connectedPhone}
                </div>
            </div>
            <div class="mt-6 flex flex-col sm:flex-row items-center justify-center gap-3">
                <button onclick="publicarEstadosAhora()" class="w-full sm:w-auto px-6 py-3 bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white font-bold text-sm rounded-xl shadow-lg transition-all flex items-center justify-center gap-2">
                    📲 Publicar los 3 Estados en WhatsApp Ahora
                </button>
                <button onclick="cerrarBotAhora()" class="w-full sm:w-auto px-6 py-3 bg-rose-600 hover:bg-rose-500 active:scale-95 text-white font-bold text-sm rounded-xl shadow-lg transition-all flex items-center justify-center gap-2">
                    🔴 Cerrar Bot / Desconectar
                </button>
            </div>
        `;
    } else {
        qrImageHtml = `
            <div class="bg-slate-100 p-8 rounded-2xl text-slate-500">
                <div class="animate-spin w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto mb-3"></div>
                <p class="text-sm font-medium">Iniciando pasarela de WhatsApp... espere un momento.</p>
            </div>
        `;
    }

    const html = `
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Panel de WhatsApp - Diagnóstico Citopatológico INLE, C.A.</title>
        <script src="https://cdn.tailwindcss.com"></script>
        ${connectionStatus !== 'conectado' ? '<meta http-equiv="refresh" content="5">' : ''}
    </head>
    <body class="bg-slate-900 text-slate-100 min-h-screen flex flex-col items-center justify-center p-4">
        <div class="max-w-xl w-full bg-slate-800 border border-slate-700 rounded-3xl p-6 sm:p-8 text-center shadow-2xl">
            <h1 class="text-2xl font-bold text-white tracking-wide">Diagnóstico Citopatológico INLE, C.A.</h1>
            <p class="text-emerald-400 text-sm font-medium mt-1">Pasarela Oficial de WhatsApp 24/7 • Dra. Aramís Romero</p>
            
            <div class="my-6">
                ${qrImageHtml}
            </div>

            <div id="status-msg" class="text-xs text-slate-400 min-h-[1.5rem] mt-3"></div>
        </div>

        <script>
            function getApiUrl(endpoint) {
                return '/whatsapp' + endpoint;
            }

            async function publicarEstadosAhora() {
                const msg = document.getElementById('status-msg');
                msg.innerText = '⏳ Consultando tasa BCV y subiendo los 3 estados a WhatsApp...';
                msg.className = 'text-xs text-emerald-300 mt-3 font-semibold animate-pulse';
                try {
                    let res = await fetch(getApiUrl('/api/publicar-estados'), { method: 'POST' });
                    if (!res.ok) {
                        res = await fetch('/api/publicar-estados', { method: 'POST' });
                    }
                    const data = await res.json();
                    if (data.ok) {
                        msg.innerText = '✅ ' + data.mensaje;
                        msg.className = 'text-xs text-emerald-400 mt-3 font-semibold';
                    } else {
                        msg.innerText = '⚠️ ' + (data.mensaje || 'No se pudieron publicar.');
                        msg.className = 'text-xs text-amber-400 mt-3 font-semibold';
                    }
                } catch(e) {
                    msg.innerText = '⚠️ Error comunicando con el servidor en la nube.';
                    msg.className = 'text-xs text-rose-400 mt-3 font-semibold';
                }
            }

            async function cerrarBotAhora() {
                if (!confirm('¿Confirma que desea cerrar el bot y desconectar WhatsApp? Para volverlo a encender requerirá escanear el código QR.')) {
                    return;
                }
                const msg = document.getElementById('status-msg');
                msg.innerText = '⏳ Cerrando sesión de WhatsApp y limpiando conexión...';
                msg.className = 'text-xs text-amber-300 mt-3 font-semibold animate-pulse';
                try {
                    let res = await fetch(getApiUrl('/api/cerrar-bot'), { method: 'POST' });
                    if (!res.ok) {
                        res = await fetch('/api/cerrar-bot', { method: 'POST' });
                    }
                    const data = await res.json();
                    if (data.ok) {
                        msg.innerText = '✅ Bot cerrado y desconectado con éxito. Recargando para nuevo QR...';
                        msg.className = 'text-xs text-emerald-400 mt-3 font-semibold';
                        setTimeout(() => window.location.reload(), 2000);
                    } else {
                        msg.innerText = '⚠️ ' + data.mensaje;
                        msg.className = 'text-xs text-amber-400 mt-3 font-semibold';
                    }
                } catch(e) {
                    msg.innerText = '⚠️ Error enviando solicitud de cierre al servidor.';
                    msg.className = 'text-xs text-rose-400 mt-3 font-semibold';
                }
            }
        </script>
    </body>
    </html>
    `;
    res.send(html);
});

// Endpoint para publicar estados
app.post(['/api/publicar-estados', '/whatsapp/api/publicar-estados'], async (req, res) => {
    try {
        const resultado = await publicarEstadosHoy();
        if (resultado.ok) {
            res.json({ ok: true, mensaje: `¡Los ${resultado.subidos} estados se publicaron exitosamente en WhatsApp!` });
        } else {
            res.json({ ok: false, mensaje: resultado.error || "No se pudieron publicar los estados." });
        }
    } catch (e) {
        res.status(500).json({ ok: false, mensaje: e.toString() });
    }
});

// Endpoint para cerrar sesión y desconectar el bot
app.post(['/api/cerrar-bot', '/whatsapp/api/cerrar-bot', '/api/desconectar'], async (req, res) => {
    try {
        console.log('\n[SOLICITUD DE USUARIO] Cerrando bot y sesión de WhatsApp...');
        connectionStatus = 'desconectado';
        lastQR = null;
        connectedPhone = '';

        if (sock) {
            try {
                await sock.logout();
                console.log('[OK] Sesión desvinculada en WhatsApp.');
            } catch (err) {
                console.log('[Aviso logout]:', err.message);
            }
            try {
                sock.end(undefined);
            } catch (err) {}
            sock = null;
        }

        const authDir = path.join(__dirname, 'auth_info_baileys');
        if (fs.existsSync(authDir)) {
            fs.rmSync(authDir, { recursive: true, force: true });
            console.log('[OK] Credenciales locales eliminadas.');
        }
        if (pool) {
            await pool.query('DELETE FROM whatsapp_session').catch(() => {});
            console.log('[OK] Sesión eliminada de Supabase.');
        }

        setTimeout(() => {
            conectarWhatsApp();
        }, 1500);

        res.json({ ok: true, mensaje: "Sesión cerrada correctamente. El bot se ha desconectado." });
    } catch (e) {
        console.error('[Error al cerrar bot]:', e);
        res.status(500).json({ ok: false, mensaje: e.message });
    }
});

// Endpoint para enviar documentos e informes firmados digitalmente a pacientes
app.post(['/api/enviar-documento', '/whatsapp/api/enviar-documento'], async (req, res) => {
    try {
        if (connectionStatus !== 'conectado' || !sock) {
            return res.status(400).json({ ok: false, error: "El bot de WhatsApp no está vinculado actualmente. Escanee el código QR en el panel." });
        }
        const { telefono, filePath, fileName, caption } = req.body;
        if (!telefono) {
            return res.status(400).json({ ok: false, error: "Falta el número de teléfono del paciente." });
        }
        if (!filePath || !fs.existsSync(filePath)) {
            return res.status(400).json({ ok: false, error: `El archivo de informe no existe: ${filePath}` });
        }

        const numLimpio = telefono.replace(/\D/g, '');
        const waNumber = numLimpio.startsWith('0') ? ('58' + numLimpio.substring(1)) : (numLimpio.startsWith('58') ? numLimpio : ('58' + numLimpio));
        const jid = `${waNumber}@s.whatsapp.net`;

        guardarContacto(jid);

        const fileBuffer = fs.readFileSync(filePath);
        const mime = filePath.endsWith('.pdf') ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

        await sock.sendMessage(jid, {
            document: fileBuffer,
            mimetype: mime,
            fileName: fileName || path.basename(filePath),
            caption: caption || "Informe Médico - Diagnóstico Citopatológico INLE, C.A."
        });

        console.log(`[OK] Informe '${fileName}' enviado exitosamente a +${waNumber}`);
        res.json({ ok: true, mensaje: `Informe enviado con éxito a +${waNumber}` });
    } catch (e) {
        console.error('[Error enviando documento por WhatsApp]:', e);
        res.status(500).json({ ok: false, error: e.message });
    }
});

// Endpoint para enviar mensaje de texto a un paciente
app.post(['/api/enviar-mensaje', '/whatsapp/api/enviar-mensaje'], async (req, res) => {
    try {
        if (connectionStatus !== 'conectado' || !sock) {
            return res.status(400).json({ ok: false, error: "El bot de WhatsApp no está vinculado actualmente." });
        }
        const { telefono, mensaje } = req.body;
        if (!telefono || !mensaje) {
            return res.status(400).json({ ok: false, error: "Faltan parámetros (teléfono o mensaje)." });
        }

        const numLimpio = telefono.replace(/\D/g, '');
        const waNumber = numLimpio.startsWith('0') ? ('58' + numLimpio.substring(1)) : (numLimpio.startsWith('58') ? numLimpio : ('58' + numLimpio));
        const jid = `${waNumber}@s.whatsapp.net`;

        guardarContacto(jid);

        await sock.sendMessage(jid, { text: mensaje });
        res.json({ ok: true, mensaje: `Mensaje enviado a +${waNumber}` });
    } catch (e) {
        res.status(500).json({ ok: false, error: e.message });
    }
});

// Endpoint para consultar las pausas activas del bot (atención personalizada)
app.get(['/api/pausas-bot', '/whatsapp/api/pausas-bot'], (req, res) => {
    cargarPausas();
    res.json({ ok: true, pausas: pausasBot });
});

// Endpoint para pausar manualmente el bot para un número
app.post(['/api/pausar-bot', '/whatsapp/api/pausar-bot'], (req, res) => {
    const { telefono, horas } = req.body;
    if (!telefono) {
        return res.status(400).json({ ok: false, error: "Indique el número de teléfono." });
    }
    const h = horas ? parseInt(horas) : 24;
    pausarBot(telefono, h);
    res.json({ ok: true, mensaje: `Bot silenciado para ${telefono} por ${h} horas (atención humana).` });
});

// Endpoint para reactivar el bot antes de que expiren las 24 horas
app.post(['/api/despausar-bot', '/whatsapp/api/despausar-bot'], (req, res) => {
    const { telefono } = req.body;
    if (!telefono) {
        return res.status(400).json({ ok: false, error: "Indique el número de teléfono." });
    }
    despausarBot(telefono);
    res.json({ ok: true, mensaje: `Bot reactivado exitosamente para ${telefono}.` });
});

app.listen(PORT, () => {
    console.log(`\n=============================================================`);
    console.log(` SERVIDOR WHATSAPP INLE ESCUCHANDO EN PUERTO ${PORT}`);
    console.log(` Panel web: http://localhost:${PORT}`);
    console.log(`=============================================================\n`);
    conectarWhatsApp();
});
