package models

import "time"

// TestData contains all the test data constants used across test files
var TestData = struct {
	// Phone numbers
	RecruiterNumber string
	ApplicantNumber string

	// Message IDs
	MessageID string

	// Chat IDs
	ApplicantChatID string

	// Message content
	TextMessageContent  string
	AdminMessageContent string

	// Timestamps
	MessageTimestamp time.Time

	// Config related
	DefaultRateLimit     int
	DefaultAllowedTypes  []string
	ExtendedAllowedTypes []string

	// Client config
	HostClientType string
	HostClientName string

	// Test file paths
	LogFilePath string
	QRFilePath  string
}{
	// Phone numbers
	RecruiterNumber: "918496952149",
	ApplicantNumber: "918050992006",

	// Message IDs
	MessageID: "JrJEGx3skp9RQXMwgqVmLh",

	// Chat IDs
	ApplicantChatID: "918050992006@s.whatsapp.net",

	// Message content
	TextMessageContent:  "hi",
	AdminMessageContent: "Hi! Could you please share your name, email, age, and gender so I can assist you better?",

	// Timestamps
	MessageTimestamp: time.Date(2025, 7, 25, 9, 56, 7, 258691000, time.UTC),

	// Config related
	DefaultRateLimit:     10,
	DefaultAllowedTypes:  []string{"text", "image"},
	ExtendedAllowedTypes: []string{"text", "audio", "typing"},

	// Client config
	HostClientType: "Chrome",
	HostClientName: "TestClient",

	// Test file paths
	LogFilePath: "test_logs",
	QRFilePath:  "test_logs/qr",
}

// GetTestRecruiterConfig returns a RecruiterConfig with test data
func GetTestRecruiterConfig(extended bool) RecruiterConfig {
	allowedTypes := TestData.DefaultAllowedTypes
	if extended {
		allowedTypes = TestData.ExtendedAllowedTypes
	}

	return RecruiterConfig{
		RecruiterNumber:   TestData.RecruiterNumber,
		HostClientType:    TestData.HostClientType,
		HostClientName:    TestData.HostClientName,
		AllowedMediaTypes: allowedTypes,
		MessageRateLimit:  TestData.DefaultRateLimit,
		Enable:            true,
	}
}

// GetTestWhatsAppMessage returns a WhatsAppMessage with test data
func GetTestWhatsAppMessage(eventType string) WhatsAppMessage {
	return WhatsAppMessage{
		EventType:  eventType,
		TimeStamp:  TestData.MessageTimestamp,
		SenderID:   TestData.ApplicantNumber,
		ReceiverID: TestData.RecruiterNumber,
		ChatID:     TestData.ApplicantChatID,
		MessageID:  TestData.MessageID,
		MsgType:    "text",
		Content:    TestData.TextMessageContent,
	}
}

// GetTestRecruiterConfigDB returns a RecruiterConfigDB with test data
func GetTestRecruiterConfigDB() RecruiterConfigDB {
	return RecruiterConfigDB{
		RecruiterID:  TestData.RecruiterNumber,
		ApplicantID:  TestData.ApplicantNumber,
		Enabled:      true,
		MessageCount: 5,
	}
}
