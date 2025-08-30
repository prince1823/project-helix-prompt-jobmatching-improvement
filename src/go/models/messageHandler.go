package models

import (
	"context"
	"encoding/json"
	"fmt"
	"gobot/whatsappbot/logger"
	"log/slog"
	"slices"
	"time"

	"github.com/google/uuid"
	"github.com/lithammer/shortuuid/v4"
	"github.com/segmentio/kafka-go"
	"go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	"google.golang.org/protobuf/proto"
)

// Associated Error codes
const (
	ErrorCodeSelfMessage       = "SELF_MESSAGE"
	ErrorCodeGroupMessage      = "GROUP_MESSAGE"
	ErrorCodeBlockedSender     = "BLOCKED_SENDER"
	ErrorCodeDisallowedMsgType = "DISALLOWED_MESSAGE_TYPE"
	ErrorCodeEmptyMessage      = "EMPTY_MESSAGE"
	ErrorRateLimitExceeded     = "EXCEEDED_MESSAGE_RATE_LIMIT"
	ErrorCodeUserNotEnabled    = "USER_NOT_ENABLED"
	InfoCodeAdminMessage       = "SELF_MESSAGE_ADMIN"
	InfoCodeRecruiterManual    = "RECRUITER_MANUAL_REACHOUT"
)

// NewMessageHandler creates a new global message handler
func NewMessageHandler(logger *slog.Logger, kafkaWriters map[string]*kafka.Writer) *MessageHandler {
	return &MessageHandler{
		Logger:       logger,
		KafkaWriters: kafkaWriters,
	}
}

// SendMessageToKafka marshals the given payload and writes it to both the main and raw Kafka writers.
func (mh *MessageHandler) SendMessageToKafka(payload interface{}, topicName string, kafkaKey string) error {
	const function = "SendMessageToKafka"
	mh.mu.Lock()
	defer mh.mu.Unlock()

	if mh.KafkaWriters[topicName] == nil {
		mh.Logger.Error("Kafka writer topic not initialized", "function", function, "Topic", topicName)
		return nil
	}

	jsonMsg, err := json.Marshal(payload)
	if err != nil {
		mh.Logger.Error("Error marshaling message", "function", function, "error", err)
		return err
	}

	err = mh.KafkaWriters[topicName].WriteMessages(context.Background(),
		kafka.Message{
			Key:   []byte(kafkaKey),
			Value: jsonMsg,
		},
	)
	if err != nil {
		mh.Logger.Error("Error sending message to Kafka", "function", function, "error", err, "Topic", topicName)
		return err
	}

	mh.Logger.Info(fmt.Sprintf("Message sent to [%s] Topic", topicName))
	return nil
}

// ReceiveMessage processes incoming WhatsApp messages, applies filtering rules, and forwards allowed messages via the MessageCallback.
func (wcm *WhatsAppClientManager) ReceiveMessage(evt any) {
	const function = "ReceiveMessage"
	isBlocked := false
	var payload WhatsAppMessage
	//  To receive user status we need to set ourself as avaliable
	err := wcm.WhatsAppClient.SendPresence(types.PresenceAvailable)
	if err != nil {
		wcm.Logger.Warn(" Error  Unable to set the SendPresence", "funciton ", "Connect")
	}
	var kafkaKey string
	switch v := evt.(type) {
	case *events.Message:
		var err error
		var chatID = v.Info.Chat.String()
		var senderID = v.Info.Sender.User
		var storeID = wcm.WhatsAppClient.Store.ID.User
		EventType := "Message"

		payload.EventType = EventType
		payload.TimeStamp = v.Info.Timestamp.UTC()
		payload.SenderID = senderID
		payload.ReceiverID = wcm.WhatsAppClient.Store.ID.User
		payload.ChatID = chatID
		payload.IsGroup = v.Info.IsGroup
		payload.MediaType = v.Info.MediaType
		payload.MessageID = shortuuid.New()

		// Key for kafka
		kafkaKey = string(payload.ReceiverID) + "_" + string(payload.SenderID)
		switch v.Info.Type {
		case "text":
			payload.MsgType = "text"
			msgToPayload := v.Message.GetExtendedTextMessage().GetText()
			if msgToPayload == "" {
				msgToPayload = v.Message.GetConversation()
			}
			if msgToPayload == "" {
				isBlocked = true
				wcm.Logger.Warn("Blocked: Empty message",
					"recruiter", wcm.RecruiterConfig.RecruiterNumber,
					"error_code", payload.ErrorCode,
				)
				return
			}
			payload.Content = msgToPayload

		case "media":
			data, err := wcm.WhatsAppClient.DownloadAny(context.Background(), v.Message)
			if err != nil {
				wcm.Logger.Error("Error downloading media", "function", function, "error", err)
				return
			}
			var mimeType string
			switch v.Info.MediaType {
			case "audio", "ptt":
				payload.MsgType = "audio"
				mimeType = *v.Message.AudioMessage.Mimetype
			case "image":
				payload.MsgType = "image"
				mimeType = *v.Message.ImageMessage.Mimetype
			case "document":
				payload.MsgType = "document"
				mimeType = *v.Message.DocumentMessage.Mimetype
			default:
				wcm.Logger.Warn("Unsupported media type", "mediaType", v.Info.MediaType)
				return
			}
			//Payload preperation
			payload.Content = data
			payload.MimeType = mimeType

		}
		// Self-message check
		if senderID == storeID {
			isBlocked = true
			if chatID == ConvertToJID(wcm.RecruiterConfig.RecruiterNumber) {
				err = wcm.MessageCallback(payload, "admin", kafkaKey)
				if err != nil {
					wcm.Logger.Error("Error sending message to admin topic ", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
					return
				}

				payload.ErrorCode = InfoCodeAdminMessage
				wcm.Logger.Info("[Redirect]: Reason: Self-message (Admin topic)",
					"recruiter", wcm.RecruiterConfig.RecruiterNumber,
					"senderID", senderID,
					"error_code", payload.ErrorCode,
				)
			} else {
				wcm.Logger.Debug("Extracted ph no", "ExtractPhoneNumber(chatID)", ExtractPhoneNumber(chatID))
				payload.ReceiverID = ExtractPhoneNumber(chatID)
				payload.ErrorCode = InfoCodeRecruiterManual
				wcm.Logger.Info("[Blocked]: Reason: Recruiter manual message to applicant",
					"recruiter", wcm.RecruiterConfig.RecruiterNumber,
					"senderID", senderID,
					"error_code", payload.ErrorCode,
				)
			}
		} else {
			configFromDb, err := GetRecruiterConfig(wcm.RecruiterConfig.RecruiterNumber, senderID, wcm.database) //Fetch values form DB
			if err != nil {
				wcm.Logger.Error("Issue while reading the GetRecruiterConfig", "fucnction", function, "err", err)
			}
			wcm.Logger.Debug("The result from the configFromDb", "configFromDb", configFromDb)

			if !configFromDb.Enabled {
				isBlocked = true
				payload.ErrorCode = ErrorCodeBlockedSender
				wcm.Logger.Warn("[Blocked]: Reason: Sender ID not allowed",
					"recruiter", wcm.RecruiterConfig.RecruiterNumber,
					"senderID", senderID,
					"error_code", payload.ErrorCode,
				)
			}

			if configFromDb.MessageCount >= wcm.RecruiterConfig.MessageRateLimit {
				isBlocked = true
				payload.ErrorCode = ErrorRateLimitExceeded
				wcm.Logger.Warn("[Blocked]: Reason: Messages to this chat have exceeded the rate limit",
					"recruiter", wcm.RecruiterConfig.RecruiterNumber,
					"senderID", senderID,
					"error_code", payload.ErrorCode,
				)
			}

			if v.Info.IsGroup {
				isBlocked = true
				payload.ErrorCode = ErrorCodeGroupMessage
				wcm.Logger.Warn("[Blocked]: Reason: Group message",
					"recruiter", wcm.RecruiterConfig.RecruiterNumber,
					"chatID", chatID,
				)
			}

			// Apply filtering rules
			// Allowed media type check
			if !((v.Info.Type == "media" && slices.Contains(wcm.RecruiterConfig.AllowedMediaTypes, v.Info.MediaType)) ||
				slices.Contains(wcm.RecruiterConfig.AllowedMediaTypes, v.Info.Type)) {
				isBlocked = true
				wcm.Logger.Warn("[Blocked]: Reason: Disallowed message type",
					"recruiter", wcm.RecruiterConfig.RecruiterNumber,
					"msgType", v.Info.Type,
					"mediaType", v.Info.MediaType,
				)
			}
		}
		wcm.Logger.Info("EVENT Recived",
			"EventType", EventType,
			"Timestamp", v.Info.Timestamp.UTC(),
			"SenderID", senderID,
			"ReceiverID", payload.ReceiverID,
			"ChatID", chatID,
			"Type", v.Info.Type,
			"MediaType", v.Info.MediaType)

		if !isBlocked && wcm.MessageCallback != nil {
			err = wcm.MessageCallback(payload, "ingest", kafkaKey)
			if err != nil {
				wcm.Logger.Error("Error sending message",
					"error", err,
					"recruiter", wcm.RecruiterConfig.RecruiterNumber)
				return
			}
			wcm.Logger.Info("Message sent to [Ingest] topic", "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		}

		err = wcm.MessageCallback(payload, "raw", kafkaKey)
		if err != nil {
			wcm.Logger.Error("Error sending message", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			return
		}
	case *events.CallAccept:

		EventType := "CallAccept"
		payload.EventType = EventType
		payload.TimeStamp = v.BasicCallMeta.Timestamp.UTC()
		payload.SenderID = v.From.User
		payload.ReceiverID = wcm.WhatsAppClient.Store.ID.User
		payload.ChatID = v.BasicCallMeta.CallID
		payload.MessageID = shortuuid.New()
		// Key for kafka
		kafkaKey = string(payload.ReceiverID) + "_" + string(payload.SenderID)
		err := wcm.MessageCallback(payload, "raw", kafkaKey)
		if err != nil {
			wcm.Logger.Error("Error sending message", "function", EventType, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			return
		}
	case *events.CallOffer:

		EventType := "CallOffer"

		payload.EventType = EventType
		payload.TimeStamp = v.BasicCallMeta.Timestamp.UTC()
		payload.SenderID = v.From.User
		payload.ReceiverID = wcm.WhatsAppClient.Store.ID.User
		payload.ChatID = v.BasicCallMeta.CallID
		payload.MessageID = shortuuid.New()

		// Key for kafka
		kafkaKey = string(payload.ReceiverID) + "_" + string(payload.SenderID)
		err := wcm.MessageCallback(payload, "raw", kafkaKey)
		if err != nil {
			wcm.Logger.Error("Error sending message", "function", EventType, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			return
		}
	case *events.CallReject:

		EventType := "CallReject"
		payload.EventType = EventType
		payload.TimeStamp = v.BasicCallMeta.Timestamp.UTC()
		payload.SenderID = v.From.User
		payload.ReceiverID = wcm.WhatsAppClient.Store.ID.User
		payload.ChatID = v.BasicCallMeta.CallID
		payload.MessageID = shortuuid.New()
		// Key for kafka
		kafkaKey = string(payload.ReceiverID) + "_" + string(payload.SenderID)
		err := wcm.MessageCallback(payload, "raw", kafkaKey)
		if err != nil {
			wcm.Logger.Error("Error sending message", "function", EventType, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			return
		}
	case *events.LoggedOut:

		EventType := "LoggedOut"

		payload.EventType = EventType
		payload.TimeStamp = time.Now().UTC()
		payload.SenderID = wcm.WhatsAppClient.Store.ID.User
		payload.ReceiverID = wcm.WhatsAppClient.Store.ID.User
		payload.ChatID = wcm.WhatsAppClient.Store.ID.User
		payload.ErrorCode = v.Reason.NumberString()
		payload.Content = v.Reason.String()
		payload.MessageID = shortuuid.New()

		// Key for kafka
		kafkaKey = string(payload.ReceiverID) + "_" + string(payload.SenderID)
		err := wcm.MessageCallback(payload, "failed", kafkaKey)
		if err != nil {
			wcm.Logger.Error("Error sending message", "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			return
		}
		wcm.Logger.Info("[Logout]: ", "Logout Code", v.Reason.NumberString(), "Reason for logout", v.Reason.String(), "OnConnect", v.OnConnect, "function", EventType, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		err = wcm.MessageCallback(payload, "raw", kafkaKey)
		if err != nil {
			wcm.Logger.Error("Error sending message", "function", EventType, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			return
		}
		wcm.LogoutEventHandler()
		wcm.Logger.Debug("[Logout Successfull]", "recruiter ", wcm.RecruiterConfig.RecruiterNumber)

	case *events.ChatPresence:

		EventType := "ChatPresence"
		wcm.Logger.Debug("Msg type", "v.Media", string(v.Media))

		var MsgType = string(v.Media) + "Presence"
		if v.Media == types.ChatPresenceMediaText {
			MsgType = "textPresence"
		}

		payload.EventType = EventType
		payload.TimeStamp = time.Now().UTC()
		payload.SenderID = v.Sender.User
		payload.ReceiverID = wcm.WhatsAppClient.Store.ID.User
		payload.ChatID = v.Chat.String()
		payload.MsgType = MsgType
		payload.Content = v.State
		payload.MessageID = shortuuid.New()

		// Key for kafka
		kafkaKey = string(payload.ReceiverID) + "_" + string(payload.SenderID)
		err := wcm.MessageCallback(payload, "raw", kafkaKey)
		if err != nil {
			wcm.Logger.Error("Error sending message", "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			return
		}
		err = wcm.MessageCallback(payload, "ingest", kafkaKey)
		if err != nil {
			wcm.Logger.Error("Error sending message", "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			return
		}
		wcm.Logger.Debug("[UserTyping] Received Typing indicator", "IsTypingStatus", v.State, "MsgType", payload.MsgType, "recruiter ", wcm.RecruiterConfig.RecruiterNumber, "Applicant", payload.SenderID, "function", function)

	case *events.TemporaryBan:
		EventType := "TemporaryBan"
		payload := WhatsAppMessage{
			EventType:  EventType,
			TimeStamp:  time.Now().UTC(),
			SenderID:   wcm.WhatsAppClient.Store.ID.User,
			ReceiverID: wcm.WhatsAppClient.Store.ID.User,
			ChatID:     wcm.WhatsAppClient.Store.ID.User,
			ErrorCode:  v.Code.String(),
			Content:    v.Expire.String(),
		}
		kafkaKey = string(payload.ReceiverID) + "_" + string(payload.SenderID)
		wcm.Logger.Info("[Temporary Ban]: ", "Temporary Ban Code", v.Code.String(), "Expiry Duration", v.Expire.String(), "function", EventType, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		err := wcm.MessageCallback(payload, "raw", kafkaKey)
		if err != nil {
			wcm.Logger.Error("Error sending message", "function", EventType, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			return
		}
		err = wcm.MessageCallback(payload, "failed", kafkaKey)

		if err != nil {
			wcm.Logger.Error("Error sending message", "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			return
		}

	}
}

// StartMessageSending starts a goroutine that continuously reads messages from the main Kafka reader,
// unmarshals them based on type, and routes them to the appropriate WhatsApp client manager for sending.
func (mcm *MainClientManager) StartMessageSending() {
	const function = "StartMessageSending"
	if mcm.KafkaReaders["output"] == nil {
		mcm.Logger.Error("Kafka reader not initialized")
		return
	}

	mcm.Logger.Info("Starting message sending goroutine")

	go func() {
		for {

			msg, err := mcm.KafkaReaders["output"].ReadMessage(mcm.ctx)
			if err != nil {
				if err.Error() == "fetching message: context canceled" {
					mcm.Logger.Info("Context is cancelled as shutdown is in progress")
					break
				}
				mcm.Logger.Error("Error reading message from Kafka", "function", function, "error", err)
				continue
			}

			mcm.Logger.Debug("Received Message", "msg.Value", string(msg.Value))

			// Write raw to kafka
			err = mcm.MessageHandler.KafkaWriters["raw"].WriteMessages(context.Background(),
				kafka.Message{
					Key:   []byte(uuid.New().String()),
					Value: msg.Value,
				},
			)
			if err != nil {
				mcm.Logger.Error("Error sending message to Kafka", "function", function, "error", err)
				return
			}
			var payload struct {
				EventType  string          `json:"event_type"`
				Timestamp  time.Time       `json:"timestamp"`
				SenderID   string          `json:"receiver_id"`
				ReceiverID string          `json:"sender_id"`
				ChatID     string          `json:"chat_id"`
				MessageID  string          `json:"mid"`
				MsgType    string          `json:"msg_type,omitempty"`
				MediaType  string          `json:"media_type,omitempty"`
				IsGroup    bool            `json:"is_group,omitempty"`
				Content    json.RawMessage `json:"content,omitempty"`
				MimeType   string          `json:"mime_type,omitempty"`
				ErrorCode  string          `json:"error_code,omitempty"`
			}
			if err := json.Unmarshal(msg.Value, &payload); err != nil {
				mcm.Logger.Error("Error unmarshaling payload", "function", function, "error", err)
				return
			}
			mcm.Logger.Debug("payload", "payload", payload)
			// Find the appropriate client manager based on receiver_id
			clientManager, exists := mcm.GetClientManager(payload.ReceiverID)
			if !exists {
				mcm.Logger.Error("Client manager not found for receiver", "function", function, "receiver", payload.ReceiverID)
				return
			}
			switch payload.MsgType {
			case "audio":
				var audioMsg *waE2E.AudioMessage
				if err := json.Unmarshal(payload.Content, &audioMsg); err == nil {
					if err := clientManager.SendAudioMessage(payload.ChatID, audioMsg); err != nil {
						mcm.Logger.Error("Failed to send audio message", "function", function, "error", err, "receiver", payload.ReceiverID)
					}
				}
			case "image":
				var imgMsg *waE2E.ImageMessage
				if err := json.Unmarshal(payload.Content, &imgMsg); err == nil {
					if err := clientManager.SendImageMessage(payload.ChatID, imgMsg); err != nil {
						mcm.Logger.Error("Failed to send image message", "function", function, "error", err, "receiver", payload.ReceiverID)
					}
				}
			case "document":
				var docMsg *waE2E.DocumentMessage
				if err := json.Unmarshal(payload.Content, &docMsg); err == nil {
					if err := clientManager.SendDocumentMessage(payload.ChatID, docMsg); err != nil {
						mcm.Logger.Error("Failed to send document message", "function", function, "error", err, "receiver", payload.ReceiverID)
					}
				}
			case "text":
				var textMsg string
				if err := json.Unmarshal(payload.Content, &textMsg); err == nil {
					if err := clientManager.SendTextMessage(payload.ChatID, textMsg); err != nil {
						mcm.Logger.Error("Failed to send text message", "function", function, "error", err, "receiver", payload.ReceiverID)
					}
				}
			case "typing":
				if err := clientManager.SendTypingIndicator(payload.ChatID); err != nil {
					mcm.Logger.Error("Failed to send typing indicator", "function", function, "error", err)
				}
			default:
				mcm.Logger.Error("Unsupported msg_type", "function", function, "msg_type", payload.MsgType)
				continue
			}

		}
	}()
}

// SendTextMessage sends a text message
func (wcm *WhatsAppClientManager) SendTextMessage(chatID string, text string) error {
	const function = "SendTextMessage"
	if !wcm.IsConnected {
		return fmt.Errorf("client not connected")
	}

	targetJID, err := types.ParseJID(chatID)
	if err != nil {
		wcm.Logger.Error("Error parsing JID", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return err
	}

	response := &waE2E.Message{
		Conversation: proto.String(text),
	}

	_, err = wcm.WhatsAppClient.SendMessage(context.Background(), targetJID, response)
	if err != nil {
		wcm.Logger.Error("Failed to send text message", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return err
	}

	wcm.Logger.Info("Text message sent successfully", "chat", chatID, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
	return nil
}

// SendAudioMessage sends an audio message
func (wcm *WhatsAppClientManager) SendAudioMessage(chatID string, audio *waE2E.AudioMessage) error {
	const function = "SendAudioMessage"
	if !wcm.IsConnected {
		return fmt.Errorf("client not connected")
	}

	targetJID, err := types.ParseJID(chatID)
	if err != nil {
		wcm.Logger.Error("Error parsing JID", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return err
	}

	response := &waE2E.Message{
		AudioMessage: audio,
	}

	_, err = wcm.WhatsAppClient.SendMessage(context.Background(), targetJID, response)
	if err != nil {
		wcm.Logger.Error("Failed to send audio message", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return err
	}

	wcm.Logger.Info("Audio message sent successfully", "chat", chatID, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
	return nil
}

// SendImageMessage sends an image message
func (wcm *WhatsAppClientManager) SendImageMessage(chatID string, img *waE2E.ImageMessage) error {
	const function = "SendImageMessage"
	if !wcm.IsConnected {
		return fmt.Errorf("client not connected")
	}

	targetJID, err := types.ParseJID(chatID)
	if err != nil {
		wcm.Logger.Error("Error parsing JID", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return err
	}

	response := &waE2E.Message{
		ImageMessage: img,
	}

	_, err = wcm.WhatsAppClient.SendMessage(context.Background(), targetJID, response)
	if err != nil {
		wcm.Logger.Error("Failed to send image message", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return err
	}

	wcm.Logger.Info("Image message sent successfully", "chat", chatID, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
	return nil
}

// SendDocumentMessage sends a document message

func (wcm *WhatsAppClientManager) SendDocumentMessage(chatID string, doc *waE2E.DocumentMessage) error {
	const function = "SendDocumentMessage"
	if !wcm.IsConnected {
		return fmt.Errorf("client not connected")
	}

	targetJID, err := types.ParseJID(chatID)
	if err != nil {
		wcm.Logger.Error("Error parsing JID", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return err
	}

	response := &waE2E.Message{
		DocumentMessage: doc,
	}

	_, err = wcm.WhatsAppClient.SendMessage(context.Background(), targetJID, response)
	if err != nil {
		wcm.Logger.Error("Failed to send document message", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return err
	}

	wcm.Logger.Info("Document message sent successfully", "chat", chatID, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
	return nil
}

// SendTypingIndicator sends a typing indicator
func (wcm *WhatsAppClientManager) SendTypingIndicator(chatID string) error {
	const function = "SendTypingIndicator"
	if !wcm.IsConnected {
		return fmt.Errorf("client not connected")
	}

	targetJID, err := types.ParseJID(chatID)
	if err != nil {
		wcm.Logger.Error("Error parsing JID", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return err
	}

	err = wcm.WhatsAppClient.SendChatPresence(targetJID, "composing", "")
	if err != nil {
		wcm.Logger.Error("Failed to send typing indicator", "function", function, "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return err
	}

	wcm.Logger.Info("Typing indicator sent successfully", "chat", chatID, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
	return nil
}

// Close closes all Kafka writers in the MessageHandler
func (mh *MessageHandler) Close() error {
	mh.mu.Lock()
	defer mh.mu.Unlock()

	var firstErr error

	for key, writer := range mh.KafkaWriters {
		if writer != nil {
			if err := writer.Close(); err != nil {
				// capture the first error, but keep closing others
				if firstErr == nil {
					firstErr = fmt.Errorf("error closing writer [%s]: %w", key, err)
				}
			}
		}
	}

	return firstErr
}

func GetRecruiterConfig(recruiterID string, senderID string, postgresDriver *PostgresRepository) (RecruiterConfigDB, error) {
	const function = "GetRecruiterConfig"
	query := `
		SELECT 
			recruiter_id,
			applicant_id,
			enabled,
			message_count
		FROM 
			configs
		WHERE 
			recruiter_id = $1 and
			applicant_id = $2
	`
	logger.L().Debug("Query executed", "function", function, "query", query, "recruiterID", recruiterID, "senderID", senderID)
	rows, err := postgresDriver.Db.Query(query, recruiterID, senderID)
	if err != nil {
		logger.L().Error("failed to execute query", "function", function, "error", err.Error())
		return RecruiterConfigDB{}, fmt.Errorf("failed to execute query: %w", err)
	}
	var configs RecruiterConfigDB
	defer rows.Close()
	rows.Next()
	err = rows.Scan(
		&configs.RecruiterID,
		&configs.ApplicantID,
		&configs.Enabled,
		&configs.MessageCount,
	)
	if err != nil {
		logger.L().Warn("No record found ", "error", err.Error())
		logger.L().Info("setting Default values for the recruiter and applicant")
		return RecruiterConfigDB{RecruiterID: recruiterID, ApplicantID: senderID, MessageCount: 0, Enabled: true}, nil
	}
	logger.L().Debug("Config from DB ", "GetRecruiterConfig", configs)
	return configs, nil
}
