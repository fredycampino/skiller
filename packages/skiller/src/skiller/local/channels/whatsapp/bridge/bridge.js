#!/usr/bin/env node

import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  useMultiFileAuthState,
} from '@whiskeysockets/baileys'
import express from 'express'
import pino from 'pino'
import qrcode from 'qrcode-terminal'
import { mkdirSync, writeFileSync } from 'fs'
import path from 'path'

const args = process.argv.slice(2)

function getArg(name, defaultValue = '') {
  const index = args.indexOf(`--${name}`)
  if (index === -1 || !args[index + 1]) {
    return defaultValue
  }
  return args[index + 1]
}

const SESSION_DIR = getArg(
  'session',
  path.join(process.env.HOME || '~', '.whatsapp', 'skiller-session'),
)
const RUNTIME_STATE_FILE = getArg('runtime-state-file', '')
const PORT = parseInt(getArg('port', '8002'), 10)
const CHANNEL_TARGET_BASE = getArg('channel-target-base', '').trim()
const CHANNEL_TOKEN = getArg('channel-token', '').trim()
const PAIR_ONLY = args.includes('--pair-only')
const SEND_MIN_DELAY_MS = parseInt(getArg('send-min-delay-ms', '1800'), 10)
const SEND_MAX_DELAY_MS = parseInt(getArg('send-max-delay-ms', '6500'), 10)
const SEND_CHAR_DELAY_MS = parseInt(getArg('send-char-delay-ms', '45'), 10)
const SEND_JITTER_MS = parseInt(getArg('send-jitter-ms', '1200'), 10)
const logger = pino({ level: 'silent' })

mkdirSync(SESSION_DIR, { recursive: true })

let activeSocket = null
let exiting = false
let qrCount = 0
let connectionState = 'starting'
const messageQueue = []
const MAX_QUEUE_SIZE = 100

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function unwrapMessageContent(message) {
  if (!message || typeof message !== 'object' || Array.isArray(message)) {
    return null
  }

  const wrappedCandidates = [
    message.ephemeralMessage?.message,
    message.viewOnceMessage?.message,
    message.viewOnceMessageV2?.message,
    message.viewOnceMessageV2Extension?.message,
    message.documentWithCaptionMessage?.message,
  ]

  for (const wrapped of wrappedCandidates) {
    const unwrapped = unwrapMessageContent(wrapped)
    if (unwrapped) {
      return unwrapped
    }
  }

  return message
}

function extractMessageText(message) {
  const content = unwrapMessageContent(message)
  if (!content) {
    return ''
  }

  if (content.conversation) {
    return String(content.conversation)
  }
  if (content.extendedTextMessage?.text) {
    return String(content.extendedTextMessage.text)
  }
  if (content.imageMessage?.caption) {
    return String(content.imageMessage.caption)
  }
  if (content.videoMessage?.caption) {
    return String(content.videoMessage.caption)
  }
  if (content.documentMessage?.caption) {
    return String(content.documentMessage.caption)
  }

  return ''
}

function bindMessagesUpsertHandler(socket) {
  const emitter = socket?.ev
  if (
    !emitter ||
    typeof emitter.emit !== 'function' ||
    emitter.__skillerMessagesUpsertBound === true
  ) {
    return
  }

  const originalEmit = emitter.emit.bind(emitter)
  emitter.emit = (eventName, ...emitArgs) => {
    if (eventName === 'messages.upsert') {
      void handleMessagesUpsert(emitArgs[0]).catch((error) => {
        const message = error instanceof Error ? error.message : String(error)
        console.error(`WhatsApp upsert handler error: ${message}`)
      })
    }
    return originalEmit(eventName, ...emitArgs)
  }
  emitter.__skillerMessagesUpsertBound = true
}

async function handleMessagesUpsert(event) {
  const { messages, type } = event || {}

  if (type !== 'notify' && type !== 'append') {
    return
  }

  for (const msg of messages || []) {
    const messageId = msg.key?.id || null
    const chatId = msg.key?.remoteJid || null
    const fromMe = msg.key?.fromMe === true

    if (!msg.message) {
      continue
    }
    if (fromMe) {
      continue
    }

    if (!chatId || chatId.endsWith('@g.us') || chatId.includes('status')) {
      continue
    }

    const text = extractMessageText(msg.message).trim()
    if (!text) {
      continue
    }

    const item = {
      messageId,
      chatId,
      senderId: msg.key.participant || chatId,
      senderName: msg.pushName || null,
      text,
      timestamp: msg.messageTimestamp,
    }
    const delivered = await deliverMessage(item)
    if (!delivered) {
      enqueueMessage(item)
    } else if (messageQueue.length > 0) {
      await flushQueuedMessages()
    }
  }
}

function computeSendDelayMs(text) {
  const normalizedText = String(text || '').trim()
  const jitter = Math.floor(Math.random() * Math.max(0, SEND_JITTER_MS + 1))
  const rawDelay = 900 + normalizedText.length * SEND_CHAR_DELAY_MS + jitter
  return Math.max(SEND_MIN_DELAY_MS, Math.min(SEND_MAX_DELAY_MS, rawDelay))
}

async function applyHumanSendDelay(socket, key, text) {
  const delayMs = computeSendDelayMs(text)

  try {
    await socket.presenceSubscribe(key)
  } catch {}

  try {
    await socket.sendPresenceUpdate('composing', key)
  } catch {}

  await sleep(delayMs)

  try {
    await socket.sendPresenceUpdate('paused', key)
  } catch {}
}

function enqueueMessage(item) {
  messageQueue.push(item)
  if (messageQueue.length > MAX_QUEUE_SIZE) {
    messageQueue.shift()
  }
}

function prependMessages(items) {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    messageQueue.unshift(items[index])
  }
  while (messageQueue.length > MAX_QUEUE_SIZE) {
    messageQueue.pop()
  }
}

async function deliverMessage(item) {
  if (!CHANNEL_TARGET_BASE || !CHANNEL_TOKEN) {
    return false
  }

  try {
    const encodedConversation = encodeURIComponent(item.chatId)
    const response = await fetch(`${CHANNEL_TARGET_BASE}/${encodedConversation}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Skiller-Channel-Token': CHANNEL_TOKEN,
      },
      body: JSON.stringify({
        external_id: item.messageId,
        dedup_key: item.messageId,
        payload: {
          channel: 'whatsapp',
          message_id: item.messageId,
          key: item.chatId,
          sender_id: item.senderId,
          sender_name: item.senderName,
          text: item.text,
          timestamp: item.timestamp,
        },
      }),
    })
    await response.text()
    return response.ok
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.error(`WhatsApp delivery error: ${message}`)
    return false
  }
}

async function flushQueuedMessages() {
  if (!CHANNEL_TARGET_BASE || !CHANNEL_TOKEN || messageQueue.length === 0) {
    return
  }

  const pending = messageQueue.splice(0, messageQueue.length)
  const undelivered = []

  for (const item of pending) {
    const delivered = await deliverMessage(item)
    if (!delivered) {
      undelivered.push(item)
    }
  }

  if (undelivered.length > 0) {
    prependMessages(undelivered)
  }
}

function writeRuntimeState(patch) {
  if (!RUNTIME_STATE_FILE) {
    return
  }
  try {
    const payload = {
      state: 'starting',
      qr_count: qrCount,
      paired: false,
      ...patch,
    }
    writeFileSync(RUNTIME_STATE_FILE, JSON.stringify(payload), 'utf8')
  } catch {}
}

async function startSocket() {
  const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR)
  const { version } = await fetchLatestBaileysVersion()

  const socket = makeWASocket({
    version,
    auth: state,
    logger,
    printQRInTerminal: false,
    browser: ['Skiller', 'Chrome', '120.0'],
    syncFullHistory: false,
    markOnlineOnConnect: false,
    getMessage: async () => ({ conversation: '' }),
  })

  activeSocket = socket
  bindMessagesUpsertHandler(socket)
  socket.ev.on('creds.update', saveCreds)

  socket.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update

    if (qr) {
      qrCount += 1
      const qrTimestamp = new Date().toISOString()
      connectionState = 'waiting_for_scan'
      writeRuntimeState({
        state: 'waiting_for_scan',
        qr_count: qrCount,
        paired: false,
      })
      console.log('')
      console.log(`=== WhatsApp QR #${qrCount} @ ${qrTimestamp} ===`)
      if (qrCount > 1) {
        console.log('Previous QR expired. Scan this new code.')
      } else {
        console.log('Scan this QR code with WhatsApp.')
      }
      qrcode.generate(qr, { small: true }, (renderedQr) => {
        console.log(renderedQr)
        console.log(`=== End QR #${qrCount} ===`)
        console.log('Waiting for pairing...')
      })
    }

    if (connection === 'open') {
      connectionState = 'connected'
      writeRuntimeState({
        state: 'paired',
        qr_count: qrCount,
        paired: true,
      })
      console.log('WhatsApp connected. Session saved.')
      if (PAIR_ONLY) {
        setTimeout(() => process.exit(0), 1500)
      }
      return
    }

    if (connection !== 'close' || exiting) {
      return
    }

    const reason = lastDisconnect?.error?.output?.statusCode
    connectionState = 'closed'
    if (reason === DisconnectReason.restartRequired) {
      console.log('Restart required after pairing. Reconnecting...')
      setTimeout(() => {
        void startSocket()
      }, 1000)
      return
    }

    if (reason === DisconnectReason.loggedOut) {
      writeRuntimeState({
        state: 'logged_out',
        qr_count: qrCount,
        paired: false,
      })
      console.error('WhatsApp session logged out. Delete session data and pair again.')
      process.exit(1)
    }

    writeRuntimeState({
      state: 'closed',
      qr_count: qrCount,
      paired: false,
    })
    console.error(`WhatsApp connection closed (reason: ${reason || 'unknown'})`)
    if (PAIR_ONLY) {
      process.exit(1)
    }
  })

}

const app = express()
app.use(express.json())

app.get('/health', (req, res) => {
  res.json({
    status: connectionState,
    paired: connectionState === 'connected',
    qrCount,
    queueLength: messageQueue.length,
  })
})

app.get('/messages', (req, res) => {
  const items = messageQueue.splice(0, messageQueue.length)
  res.json(items)
})

app.post('/messages', async (req, res) => {
  const payload = req.body
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return res.status(400).json({ accepted: false, error: 'payload must be an object' })
  }

  const channel = String(payload.channel || '').trim()
  const key = String(payload.key || '').trim()
  const text = String(payload.text || '').trim()

  if (channel !== 'whatsapp') {
    return res.status(400).json({ accepted: false, error: 'unsupported channel' })
  }
  if (!key) {
    return res.status(400).json({ accepted: false, error: 'key is required' })
  }
  if (!text) {
    return res.status(400).json({ accepted: false, error: 'text is required' })
  }
  if (!activeSocket || connectionState !== 'connected') {
    return res.status(409).json({ accepted: false, error: 'bridge is not connected' })
  }

  try {
    await applyHumanSendDelay(activeSocket, key, text)
    const result = await activeSocket.sendMessage(key, { text })
    const messageId = result?.key?.id || null
    return res.json({
      accepted: true,
      channel: 'whatsapp',
      key,
      message_id: messageId,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return res.status(500).json({
      accepted: false,
      error: message || 'bridge send failed',
    })
  }
})

process.on('SIGTERM', async () => {
  exiting = true
  void activeSocket
  process.exit(0)
})

process.on('SIGINT', async () => {
  exiting = true
  void activeSocket
  process.exit(0)
})

if (!PAIR_ONLY) {
  app.listen(PORT, '127.0.0.1', () => {
    console.log(`WhatsApp bridge listening on port ${PORT}`)
    void startSocket().catch((error) => {
      const message = error instanceof Error ? error.message : String(error)
      console.error(message)
      process.exit(1)
    })
    setInterval(() => {
      void flushQueuedMessages()
    }, 1000)
  })
} else {
  void startSocket().catch((error) => {
    const message = error instanceof Error ? error.message : String(error)
    console.error(message)
    process.exit(1)
  })
}
