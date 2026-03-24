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
import fs from "fs";
import path from "path";

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

const FORCE_PAIR = process.argv.includes("--pair");

// ── Ensure directories exist ────────────────────────────────────────────

fs.mkdirSync(AUTH_DIR, { recursive: true });
fs.mkdirSync(OUTPUT_DIR, { recursive: true });

// ── Logger ──────────────────────────────────────────────────────────────

const logger = pino(
  { level: "info" },
  pino.destination({ dest: LOG_FILE, sync: false })
);

// ── Helpers ─────────────────────────────────────────────────────────────

function jidToPhone(jid) {
  if (!jid) return null;
  // Format: 48505441635@s.whatsapp.net or 48505441635-1234567890@g.us (group)
  return jid.split("@")[0].split(":")[0];
}

function isGroupJid(jid) {
  return jid && jid.endsWith("@g.us");
}

function appendMessage(record) {
  const line = JSON.stringify(record) + "\n";
  fs.appendFileSync(MESSAGES_FILE, line, "utf8");
}

// ── Main ────────────────────────────────────────────────────────────────

async function startListener() {
  if (FORCE_PAIR) {
    // Remove auth state to force new QR code
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
    printQRInTerminal: true,
    // Receive message history on connect (last 30 days)
    syncFullHistory: false,
    // Mark messages as received but don't send read receipts
    markOnlineOnConnect: false,
    generateHighQualityLinkPreview: false,
  });

  // ── Connection events ─────────────────────────────────────────────

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      console.log("\n========================================");
      console.log("  SCAN THIS QR CODE WITH WHATSAPP");
      console.log("  (Phone > Settings > Linked Devices)");
      console.log("========================================\n");
    }

    if (connection === "open") {
      console.log(`[${new Date().toISOString()}] Connected to WhatsApp Web`);
      logger.info("Connected to WhatsApp Web");
    }

    if (connection === "close") {
      const statusCode =
        lastDisconnect?.error instanceof Boom
          ? lastDisconnect.error.output.statusCode
          : null;

      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

      logger.info(
        { statusCode, shouldReconnect },
        "Connection closed"
      );
      console.log(
        `[${new Date().toISOString()}] Disconnected (status=${statusCode}). ${
          shouldReconnect ? "Reconnecting..." : "Logged out — run with --pair to re-link."
        }`
      );

      if (shouldReconnect) {
        // Reconnect after brief delay
        setTimeout(() => startListener(), 3000);
      } else {
        process.exit(1);
      }
    }
  });

  // ── Message events ────────────────────────────────────────────────

  // Cache for group metadata (chat names)
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
        // Skip status broadcasts
        if (msg.key.remoteJid === "status@broadcast") continue;

        // Extract message text from various message types
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
          // Skip reactions — they aren't real messages
          continue;
        } else if (m.protocolMessage || m.senderKeyDistributionMessage) {
          // Protocol/key distribution — skip
          continue;
        } else {
          // Unknown message type — log it but skip
          logger.debug({ messageTypes: Object.keys(m) }, "Unknown message type");
          continue;
        }

        if (!text) continue;

        const remoteJid = msg.key.remoteJid;
        const isGroup = isGroupJid(remoteJid);
        const fromMe = msg.key.fromMe || false;

        // Determine sender
        let senderJid;
        if (fromMe) {
          senderJid = sock.user?.id || "me";
        } else if (isGroup) {
          senderJid = msg.key.participant || remoteJid;
        } else {
          senderJid = remoteJid;
        }

        // Determine chat name
        let chatName;
        if (isGroup) {
          chatName = await getGroupName(remoteJid);
        } else {
          chatName = jidToPhone(remoteJid);
        }

        // Get push name (display name of sender)
        const pushName = msg.pushName || null;

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
          body: text,
          mediaType: mediaType || null,
          type: type, // "notify" = real-time, "append" = history sync
        };

        appendMessage(record);

        // Log to console for monitoring
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

  // ── Contacts & group updates for name resolution ──────────────────

  sock.ev.on("contacts.update", (updates) => {
    // We could cache contact names here for richer metadata
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
}

// ── Entry point ─────────────────────────────────────────────────────────

startListener().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
