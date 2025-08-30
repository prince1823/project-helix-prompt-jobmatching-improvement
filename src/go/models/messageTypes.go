package models

import "time"

type WhatsAppMessage struct {
	EventType  string          `json:"event_type"`
	TimeStamp  time.Time       `json:"timestamp"`
	SenderID   string          `json:"sender_id"`
	ReceiverID string          `json:"receiver_id"`
	ChatID     string          `json:"chat_id"`
	MessageID  string          `json:"mid"`
	MsgType    string          `json:"msg_type,omitempty"`
	MediaType  string          `json:"media_type,omitempty"`
	IsGroup    bool            `json:"is_group,omitempty"`
	Content    WhatsAppContent `json:"content,omitempty"`
	MimeType   string          `json:"mime_type,omitempty"`
	ErrorCode  string          `json:"error_code,omitempty"`
}

type WhatsAppContent interface{}
