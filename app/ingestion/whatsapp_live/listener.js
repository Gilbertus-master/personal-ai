/**
 * WhatsApp message listener for Gilbertus Albans.
 *
 * Connects to WhatsApp Web as a SEPARATE linked device (does NOT interfere
 * with the existing OpenClaw connection) and writes ALL incoming messages
 * to a JSONL file that the Python importer picks up.
 *
 * First run: displays QR code in terminal for pairing.
 * Subsequent runs: reconnects using saved auth state.
 *
 * Auth state: ~/.gilbertus/whatsapp_listener/auth/
 * Output:     ~/.gilbertus/whatsapp_listener/messages.jsonl
 *
 * Features:
 * - Exponential backoff on reconnect (3s -> 6s -> 12s -> ... max 300s)
 * - Health check endpoint on :9393 (GET /health)
 * - JSONL file rotation at 50MB
 * - PID file for supervisor scripts
 *
 * Usage:
 *   node listener.js          # run listener (shows QR on first run)
 *   node listener.js --pair   # force re-pair (new QR code)
 */

import {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import pino from "pino";
import qrcode from "qrcode-terminal";
import fs from "fs";
import path from "path";
import http from "http";

// ── Config ──────────────────────────────────────────────────────────────

const AUTH_DIR = path.join(
  process.env.HOME,
  ".gilbertus",
  "whatsapp_listener",
  "auth"
);
const OUTPUT_DIR = path.join(
  process.env.HOME,
  ".gilbertus",
  "whatsapp_listener"
);
const MESSAGES_FILE = path.join(OUTPUT_DIR, "messages.jsonl");
const LOG_FILE = path.join(OUTPUT_DIR, "listener.log");
const PID_FILE = path.join(OUTPUT_DIR, "listener.pid");

const QR_FILE = path.join(OUTPUT_DIR, "qr_pending.json");
const NEEDS_REPAIR_FLAG = path.join(OUTPUT_DIR, "needs_repair.flag");

const FORCE_PAIR = process.argv.includes("--pair");
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB rotation threshold
const HEALTH_PORT = 9393;

// ── Ensure directories exist ────────────────────────────────────────────

fs.mkdirSync(AUTH_DIR, { recursive: true });
fs.mkdirSync(OUTPUT_DIR, { recursive: true });

// ── PID file ────────────────────────────────────────────────────────────

fs.writeFileSync(PID_FILE, process.pid.toString(), "utf8");
process.on("exit", () => {
  try { fs.unlinkSync(PID_FILE); } catch { /* ignore */ }
});
process.on("SIGINT", () => process.exit(0));
process.on("SIGTERM", () => process.exit(0));

// ── Logger ──────────────────────────────────────────────────────────────

const logger = pino(
  { level: "info" },
  pino.destination({ dest: LOG_FILE, sync: false })
);

// ── State ───────────────────────────────────────────────────────────────

let isConnected = false;
let qrPending = false;
let lastMsgAt = null;
let msgCountSinceStart = 0;
let reconnectAttempt = 0;

// ── Helpers ─────────────────────────────────────────────────────────────

function jidToPhone(jid) {
  if (!jid) return null;
  return jid.split("@")[0].split(":")[0];
}

function isGroupJid(jid) {
  return jid && jid.endsWith("@g.us");
}

function rotateFileIfNeeded() {
  try {
    const stat = fs.statSync(MESSAGES_FILE);
    if (stat.size >= MAX_FILE_SIZE) {
      const rotated = MESSAGES_FILE + ".1";
      if (fs.existsSync(rotated)) {
        fs.unlinkSync(rotated);
      }
      fs.renameSync(MESSAGES_FILE, rotated);
      logger.info({ oldSize: stat.size }, "Rotated messages.jsonl");
      console.log(`[${new Date().toISOString()}] Rotated messages.jsonl (${(stat.size / 1024 / 1024).toFixed(1)}MB)`);
    }
  } catch (err) {
    if (err.code !== "ENOENT") {
      logger.error({ err }, "Error checking file rotation");
    }
  }
}

function appendMessage(record) {
  rotateFileIfNeeded();
  const line = JSON.stringify(record) + "\n";
  fs.appendFileSync(MESSAGES_FILE, line, "utf8");
}

// ── Exponential backoff ─────────────────────────────────────────────────

function getReconnectDelay() {
  const baseDelay = 3000;
  const maxDelay = 300000; // 5 minutes
  const delay = Math.min(baseDelay * Math.pow(2, reconnectAttempt), maxDelay);
  const jitter = delay * 0.2 * (Math.random() * 2 - 1);
  return Math.round(delay + jitter);
}

// ── Health check server ─────────────────────────────────────────────────

const healthServer = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    const status = qrPending ? "qr_pending" : isConnected ? "ok" : "disconnected";
    const body = JSON.stringify({
      status,
      connected: isConnected,
      qr_pending: qrPending,
      last_msg_at: lastMsgAt,
      messages_since_start: msgCountSinceStart,
      pid: process.pid,
      uptime_seconds: Math.floor(process.uptime()),
    });
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(body);
  } else {
    res.writeHead(404);
    res.end("Not found");
  }
});

healthServer.listen(HEALTH_PORT, "127.0.0.1", () => {
  console.log(`[${new Date().toISOString()}] Health check listening on http://127.0.0.1:${HEALTH_PORT}/health`);
});

healthServer.on("error", (err) => {
  if (err.code === "EADDRINUSE") {
    console.log(`[${new Date().toISOString()}] Health port ${HEALTH_PORT} already in use, skipping`);
  } else {
    logger.error({ err }, "Health server error");
  }
});

// ── Reconnect state ─────────────────────────────────────────────────────

let qrAttempts = 0;
const MAX_QR_ATTEMPTS = 3;

// ── Main ────────────────────────────────────────────────────────────────

async function startListener({ clearAuth = false } = {}) {
  if (clearAuth) {
    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
    fs.mkdirSync(AUTH_DIR, { recursive: true });
    console.log("Auth state cleared. Will show new QR code for pairing.");
  }

  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    logger,
    qrTimeout: 60_000,
    syncFullHistory: false,
    markOnlineOnConnect: false,
    generateHighQualityLinkPreview: false,
  });

  // ── Connection events ─────────────────────────────────────────────

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      qrAttempts++;
      qrPending = true;

      // Save QR data to file for external monitor/alerting
      try {
        fs.writeFileSync(QR_FILE, JSON.stringify({
          qr_data: qr,
          generated_at: Date.now(),
          attempt: qrAttempts,
          max_attempts: MAX_QR_ATTEMPTS,
          listener_pid: process.pid,
        }), "utf8");
        logger.info({ qrAttempts }, "QR data saved to qr_pending.json");
      } catch (err) {
        logger.error({ err }, "Failed to write QR file");
      }

      if (qrAttempts > MAX_QR_ATTEMPTS) {
        console.log(
          `\n[${new Date().toISOString()}] QR code shown ${MAX_QR_ATTEMPTS} times without successful scan.`
        );
        console.log("Stopping. Please try again later with: node listener.js --pair");
        logger.warn({ qrAttempts }, "Max QR attempts reached, giving up");
        process.exit(1);
      }

      console.log("\n========================================");
      console.log("  SCAN THIS QR CODE WITH WHATSAPP");
      console.log("  (Phone > Settings > Linked Devices)");
      console.log(`  Attempt ${qrAttempts}/${MAX_QR_ATTEMPTS} - you have 60 seconds`);
      console.log("========================================\n");
      qrcode.generate(qr, { small: true });
      console.log("\n========================================\n");
    }

    if (connection === "open") {
      qrAttempts = 0;
      reconnectAttempt = 0;
      isConnected = true;
      qrPending = false;

      // Clean up QR and repair files after successful connection
      try { if (fs.existsSync(QR_FILE)) fs.unlinkSync(QR_FILE); } catch { /* ignore */ }
      try { if (fs.existsSync(NEEDS_REPAIR_FLAG)) fs.unlinkSync(NEEDS_REPAIR_FLAG); } catch { /* ignore */ }

      console.log(`[${new Date().toISOString()}] Connected to WhatsApp Web`);
      logger.info("Connected to WhatsApp Web");
    }

    if (connection === "close") {
      isConnected = false;
      qrPending = false;
      const statusCode =
        lastDisconnect?.error instanceof Boom
          ? lastDisconnect.error.output.statusCode
          : null;

      const errorMessage = lastDisconnect?.error?.message || "";
      const isBadMac = errorMessage.toLowerCase().includes("bad mac")
        || errorMessage.toLowerCase().includes("hmac validation failed");
      const isLoggedOut = statusCode === DisconnectReason.loggedOut;
      const shouldReconnect = !isLoggedOut && !isBadMac;

      logger.info(
        { statusCode, shouldReconnect, reconnectAttempt, isBadMac, isLoggedOut },
        "Connection closed"
      );
      console.log(
        `[${new Date().toISOString()}] Disconnected (status=${statusCode}, badMac=${isBadMac}). ${
          shouldReconnect ? "Reconnecting..." : "Needs re-pair — writing needs_repair.flag."
        }`
      );

      if (!shouldReconnect) {
        // Write repair flag so external monitor can trigger re-pair
        try {
          fs.writeFileSync(NEEDS_REPAIR_FLAG, JSON.stringify({
            reason: isBadMac ? "bad_mac" : "logged_out",
            status_code: statusCode,
            error_message: errorMessage,
            timestamp: new Date().toISOString(),
            pid: process.pid,
          }), "utf8");
          logger.info({ isBadMac, isLoggedOut }, "Wrote needs_repair.flag");
        } catch (err) {
          logger.error({ err }, "Failed to write needs_repair.flag");
        }
        process.exit(2);
      }

      if (statusCode === 408) {
        console.log("QR scan timed out. Retrying in 30 seconds...");
        setTimeout(() => startListener(), 30_000);
        return;
      }

      // Exponential backoff for all reconnectable disconnects
      reconnectAttempt++;
      const delay = getReconnectDelay();
      console.log(`[${new Date().toISOString()}] Reconnect attempt ${reconnectAttempt} in ${(delay / 1000).toFixed(1)}s`);
      setTimeout(() => startListener(), delay);
    }
  });

  // ── Message events ────────────────────────────────────────────────

  const groupCache = new Map();

  async function getGroupName(jid) {
    if (groupCache.has(jid)) return groupCache.get(jid);
    try {
      const meta = await sock.groupMetadata(jid);
      const name = meta.subject || jid;
      groupCache.set(jid, name);
      return name;
    } catch {
      return jid;
    }
  }

  sock.ev.on("messages.upsert", async ({ messages: msgs, type }) => {
    for (const msg of msgs) {
      try {
        if (msg.key.remoteJid === "status@broadcast") continue;

        const m = msg.message;
        if (!m) continue;

        let text = null;
        let mediaType = null;

        if (m.conversation) {
          text = m.conversation;
        } else if (m.extendedTextMessage?.text) {
          text = m.extendedTextMessage.text;
        } else if (m.imageMessage?.caption) {
          text = m.imageMessage.caption;
          mediaType = "image";
        } else if (m.videoMessage?.caption) {
          text = m.videoMessage.caption;
          mediaType = "video";
        } else if (m.documentMessage?.caption) {
          text = m.documentMessage.caption;
          mediaType = "document";
        } else if (m.imageMessage) {
          text = "[image]";
          mediaType = "image";
        } else if (m.videoMessage) {
          text = "[video]";
          mediaType = "video";
        } else if (m.audioMessage) {
          text = "[audio]";
          mediaType = "audio";
        } else if (m.stickerMessage) {
          text = "[sticker]";
          mediaType = "sticker";
        } else if (m.documentMessage) {
          text = `[document: ${m.documentMessage.fileName || "file"}]`;
          mediaType = "document";
        } else if (m.contactMessage) {
          text = `[contact: ${m.contactMessage.displayName || ""}]`;
        } else if (m.locationMessage) {
          text = `[location: ${m.locationMessage.degreesLatitude},${m.locationMessage.degreesLongitude}]`;
        } else if (m.liveLocationMessage) {
          text = "[live location]";
        } else if (m.reactionMessage) {
          continue;
        } else if (m.protocolMessage || m.senderKeyDistributionMessage) {
          continue;
        } else {
          logger.debug({ messageTypes: Object.keys(m) }, "Unknown message type");
          continue;
        }

        if (!text) continue;

        const remoteJid = msg.key.remoteJid;
        const isGroup = isGroupJid(remoteJid);
        const fromMe = msg.key.fromMe || false;

        let senderJid;
        if (fromMe) {
          senderJid = sock.user?.id || "me";
        } else if (isGroup) {
          senderJid = msg.key.participant || remoteJid;
        } else {
          senderJid = remoteJid;
        }

        let chatName;
        if (isGroup) {
          chatName = await getGroupName(remoteJid);
        } else {
          chatName = jidToPhone(remoteJid);
        }

        const pushName = msg.pushName || null;

        // Extract phone-based JID when available (for entity linking)
        // @s.whatsapp.net JIDs contain the phone number; @lid JIDs do not
        const phoneJid = remoteJid && remoteJid.endsWith("@s.whatsapp.net")
          ? remoteJid
          : null;

        const record = {
          id: msg.key.id,
          timestamp: msg.messageTimestamp
            ? typeof msg.messageTimestamp === "number"
              ? msg.messageTimestamp
              : parseInt(msg.messageTimestamp.toString())
            : Math.floor(Date.now() / 1000),
          chatJid: remoteJid,
          chatName,
          isGroup,
          fromMe,
          senderJid: jidToPhone(senderJid),
          senderName: pushName,
          phoneJid: phoneJid,
          body: text,
          mediaType: mediaType || null,
          type: type,
        };

        appendMessage(record);

        lastMsgAt = new Date().toISOString();
        msgCountSinceStart++;

        const direction = fromMe ? ">>>" : "<<<";
        const preview = text.length > 80 ? text.substring(0, 80) + "..." : text;
        console.log(
          `[${new Date().toISOString()}] ${direction} [${chatName}] ${pushName || senderJid}: ${preview}`
        );
      } catch (err) {
        logger.error({ err, msgKey: msg.key }, "Error processing message");
      }
    }
  });

  // ── Contacts & group updates ──────────────────────────────────────

  sock.ev.on("contacts.update", (updates) => {
    logger.debug({ count: updates.length }, "Contacts updated");
  });

  sock.ev.on("groups.update", (updates) => {
    for (const update of updates) {
      if (update.id && update.subject) {
        groupCache.set(update.id, update.subject);
      }
    }
  });

  console.log(`[${new Date().toISOString()}] WhatsApp listener starting...`);
  console.log(`Auth dir:     ${AUTH_DIR}`);
  console.log(`Messages out: ${MESSAGES_FILE}`);
  console.log(`PID file:     ${PID_FILE}`);
  console.log(`Health check: http://127.0.0.1:${HEALTH_PORT}/health`);
}

// ── Entry point ─────────────────────────────────────────────────────────

startListener({ clearAuth: FORCE_PAIR }).catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
