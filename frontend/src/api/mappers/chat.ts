/**
 * Mappers: chat transport shapes → domain chat types.
 *
 * Used by api/messages.ts to convert raw /messages/* responses into the
 * canonical ChatMessage / ChatConversation / ChatAvailableUser shapes
 * defined in types/domain/chat.ts. ChatContext.tsx then consumes the
 * domain types directly (no `as` casts at the boundary).
 */

import type {
  ChatMessage,
  ChatConversation,
  ChatAvailableUser,
  ChatConversationsResponse,
  ChatConversationResponse,
  ChatUnreadCountResponse,
  ChatAvailableUsersResponse,
} from '../../types/domain/chat';

type ChatDtoLike = Record<string, unknown>;

export function mapChatMessageDto(dto: ChatDtoLike): ChatMessage {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapChatMessageDto] expected object, got ' + typeof dto);
  }
  const id = dto.id as number | undefined;
  if (id == null) {
    throw new Error('[mapChatMessageDto] missing required field `id`');
  }
  return {
    id,
    sender_id: dto.sender_id as number,
    recipient_id: dto.recipient_id as number,
    sender_name: dto.sender_name as string | undefined,
    content: dto.content as string | undefined,
    is_read: dto.is_read as boolean | undefined,
    reactions: dto.reactions as ChatMessage['reactions'],
    created_at: dto.created_at as string | undefined,
    type: dto.type as ChatMessage['type'],
    attachment_url: dto.attachment_url as string | undefined,
    attachment_name: dto.attachment_name as string | undefined,
    ...dto,
  };
}

export function mapChatConversationDto(dto: ChatDtoLike): ChatConversation {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapChatConversationDto] expected object, got ' + typeof dto);
  }
  const userId = dto.user_id as number | undefined;
  if (userId == null) {
    throw new Error('[mapChatConversationDto] missing required field `user_id`');
  }
  return { ...(dto as ChatConversation) };
}

export function mapChatAvailableUserDto(dto: ChatDtoLike): ChatAvailableUser {
  if (dto == null || typeof dto !== 'object') {
    throw new Error('[mapChatAvailableUserDto] expected object, got ' + typeof dto);
  }
  const id = dto.id as number | undefined;
  if (id == null) {
    throw new Error('[mapChatAvailableUserDto] missing required field `id`');
  }
  return { ...(dto as ChatAvailableUser) };
}

export function mapChatAvailableUserDtos(dtos: unknown): ChatAvailableUser[] {
  if (!Array.isArray(dtos)) return [];
  const out: ChatAvailableUser[] = [];
  for (const dto of dtos) {
    try {
      out.push(mapChatAvailableUserDto(dto as ChatDtoLike));
    } catch {
      // skip malformed
    }
  }
  return out;
}

export function mapConversationsResponseDto(dto: ChatDtoLike): ChatConversationsResponse {
  if (dto == null || typeof dto !== 'object') {
    return { conversations: [] };
  }
  return { ...(dto as ChatConversationsResponse) };
}

export function mapConversationResponseDto(dto: ChatDtoLike): ChatConversationResponse {
  if (dto == null || typeof dto !== 'object') {
    return { messages: [] };
  }
  return { ...(dto as ChatConversationResponse) };
}

export function mapUnreadCountResponseDto(dto: ChatDtoLike): ChatUnreadCountResponse {
  if (dto == null || typeof dto !== 'object') {
    return { count: 0 };
  }
  return { ...(dto as ChatUnreadCountResponse) };
}

export function mapAvailableUsersResponseDto(dto: ChatDtoLike): ChatAvailableUsersResponse {
  if (dto == null || typeof dto !== 'object') {
    return { users: [] };
  }
  return { ...(dto as ChatAvailableUsersResponse) };
}
