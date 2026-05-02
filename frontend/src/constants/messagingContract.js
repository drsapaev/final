// Canonical messaging contract for the frontend chat stack.

export const MESSAGE_EVENT_TYPES = Object.freeze({
  NEW_MESSAGE: 'new_message',
  MESSAGE_READ: 'message_read',
  MESSAGES_READ: 'messages_read',
  REACTION_UPDATE: 'reaction_update',
  MESSAGE_DELETED: 'message_deleted',
  TYPING: 'typing',
  GET_ONLINE_STATUS: 'get_online_status',
  ONLINE_STATUS: 'online_status',
  PING: 'ping',
  PONG: 'pong',
});

export const MESSAGE_STATUSES = Object.freeze([
  'pending',
  'sent',
  'delivered',
  'read',
  'failed',
]);

export const ATTACHMENT_STATUSES = Object.freeze([
  'uploading',
  'uploaded',
  'scanned',
  'available',
  'blocked',
]);

export const AI_CHAT_STATUSES = Object.freeze([
  'draft',
  'streaming',
  'completed',
  'failed',
  'cancelled',
]);

export const RELIABLE_MESSAGE_EVENTS = new Set([
  MESSAGE_EVENT_TYPES.NEW_MESSAGE,
  MESSAGE_EVENT_TYPES.MESSAGE_READ,
  MESSAGE_EVENT_TYPES.MESSAGES_READ,
  MESSAGE_EVENT_TYPES.REACTION_UPDATE,
  MESSAGE_EVENT_TYPES.MESSAGE_DELETED,
]);

export const EPHEMERAL_MESSAGE_EVENTS = new Set([
  MESSAGE_EVENT_TYPES.TYPING,
  MESSAGE_EVENT_TYPES.GET_ONLINE_STATUS,
  MESSAGE_EVENT_TYPES.ONLINE_STATUS,
  MESSAGE_EVENT_TYPES.PING,
  MESSAGE_EVENT_TYPES.PONG,
]);

export const MESSAGING_CONTRACT_VERSION = '2026-03';

export const isSupportedMessagingContractVersion = (contractVersion) => (
  contractVersion === MESSAGING_CONTRACT_VERSION
);
