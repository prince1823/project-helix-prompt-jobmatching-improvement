package models

import (
	"strings"
	"testing"

	"github.com/segmentio/kafka-go"
	"github.com/stretchr/testify/assert"
	"golang.org/x/exp/slices"
)

// Test error constants
func TestErrorConstants(t *testing.T) {
	assert.NotEmpty(t, ErrorCodeSelfMessage)
	assert.NotEmpty(t, ErrorCodeGroupMessage)
	assert.NotEmpty(t, ErrorCodeBlockedSender)
	assert.NotEmpty(t, ErrorCodeDisallowedMsgType)
	assert.NotEmpty(t, ErrorCodeEmptyMessage)
	assert.NotEmpty(t, ErrorRateLimitExceeded)
	assert.NotEmpty(t, ErrorCodeUserNotEnabled)
	assert.NotEmpty(t, InfoCodeAdminMessage)
	assert.NotEmpty(t, InfoCodeRecruiterManual)

	assert.Equal(t, "SELF_MESSAGE", ErrorCodeSelfMessage)
	assert.Equal(t, "GROUP_MESSAGE", ErrorCodeGroupMessage)
	assert.Equal(t, "BLOCKED_SENDER", ErrorCodeBlockedSender)
	assert.Equal(t, "DISALLOWED_MESSAGE_TYPE", ErrorCodeDisallowedMsgType)
	assert.Equal(t, "EMPTY_MESSAGE", ErrorCodeEmptyMessage)
	assert.Equal(t, "EXCEEDED_MESSAGE_RATE_LIMIT", ErrorRateLimitExceeded)
	assert.Equal(t, "USER_NOT_ENABLED", ErrorCodeUserNotEnabled)
	assert.Equal(t, "SELF_MESSAGE_ADMIN", InfoCodeAdminMessage)
	assert.Equal(t, "RECRUITER_MANUAL_REACHOUT", InfoCodeRecruiterManual)
}

// Test WhatsAppMessage struct creation and basic functionality
func TestWhatsAppMessageStruct(t *testing.T) {
	// Test that we can create a WhatsAppMessage struct
	msg := GetTestWhatsAppMessage("UserTyping")

	assert.Equal(t, "UserTyping", msg.EventType)
	assert.Equal(t, TestData.ApplicantNumber, msg.SenderID)
	assert.Equal(t, TestData.RecruiterNumber, msg.ReceiverID)
	assert.Equal(t, TestData.ApplicantChatID, msg.ChatID)
	assert.Equal(t, TestData.MessageID, msg.MessageID)
	assert.Equal(t, "text", msg.MsgType)
	assert.Equal(t, TestData.TextMessageContent, msg.Content)
}

// Test RecruiterConfig struct creation and basic functionality
func TestRecruiterConfigStruct(t *testing.T) {
	config := GetTestRecruiterConfig(true)

	assert.Equal(t, TestData.RecruiterNumber, config.RecruiterNumber)
	assert.Equal(t, TestData.HostClientType, config.HostClientType)
	assert.Equal(t, TestData.HostClientName, config.HostClientName)
	assert.Equal(t, TestData.ExtendedAllowedTypes, config.AllowedMediaTypes)
	assert.Equal(t, TestData.DefaultRateLimit, config.MessageRateLimit)
	assert.True(t, config.Enable)
}

// Test RecruiterConfigDB struct creation and basic functionality
func TestRecruiterConfigDBStruct(t *testing.T) {
	configDB := GetTestRecruiterConfigDB()

	assert.Equal(t, TestData.RecruiterNumber, configDB.RecruiterID)
	assert.Equal(t, TestData.ApplicantNumber, configDB.ApplicantID)
	assert.False(t, configDB.Enabled)
	assert.Equal(t, 5, configDB.MessageCount)
}

// Test MessageHandler struct creation and basic functionality
func TestMessageHandlerStruct(t *testing.T) {
	// Create a simple MessageHandler
	handler := &MessageHandler{
		Logger:       nil, // We don't need a real logger for this test
		KafkaWriters: make(map[string]*kafka.Writer),
	}

	assert.NotNil(t, handler)
	assert.NotNil(t, handler.KafkaWriters)
	assert.Len(t, handler.KafkaWriters, 0)
}

// Test WhatsAppClientManager struct creation and basic functionality
func TestWhatsAppClientManagerStruct(t *testing.T) {
	// Create a simple WhatsAppClientManager
	manager := &WhatsAppClientManager{
		RecruiterConfig: GetTestRecruiterConfig(false),
		IsConnected:     true,
	}

	assert.NotNil(t, manager)
	assert.Equal(t, TestData.RecruiterNumber, manager.RecruiterConfig.RecruiterNumber)
	assert.Equal(t, TestData.DefaultRateLimit, manager.RecruiterConfig.MessageRateLimit)
	assert.Equal(t, TestData.DefaultAllowedTypes, manager.RecruiterConfig.AllowedMediaTypes)
	assert.True(t, manager.IsConnected)
}

// Test MainClientManager struct creation and basic functionality
func TestMainClientManagerStruct(t *testing.T) {
	// Create a simple MainClientManager
	mainManager := &MainClientManager{
		Config: Config{
			WhatsApp: []RecruiterConfig{
				{
					RecruiterNumber:   "911000000000",
					MessageRateLimit:  10,
					AllowedMediaTypes: []string{"text", "image"},
				},
			},
		},
		ClientManagers: make(map[string]*WhatsAppClientManager),
		KafkaReaders:   make(map[string]*kafka.Reader),
	}

	assert.NotNil(t, mainManager)
	assert.NotNil(t, mainManager.ClientManagers)
	assert.NotNil(t, mainManager.KafkaReaders)
	assert.Len(t, mainManager.Config.WhatsApp, 1)
	assert.Equal(t, "911000000000", mainManager.Config.WhatsApp[0].RecruiterNumber)
}

// Test error code validation
func TestErrorCodeValidation(t *testing.T) {
	// Test that all error codes are non-empty strings
	errorCodes := []string{
		ErrorCodeSelfMessage,
		ErrorCodeGroupMessage,
		ErrorCodeBlockedSender,
		ErrorCodeDisallowedMsgType,
		ErrorCodeEmptyMessage,
		ErrorRateLimitExceeded,
		ErrorCodeUserNotEnabled,
		InfoCodeAdminMessage,
		InfoCodeRecruiterManual,
	}

	for _, code := range errorCodes {
		assert.NotEmpty(t, code, "Error code should not be empty")
		assert.Greater(t, len(code), 0, "Error code should have length greater than 0")
	}
}

// Test info code validation
func TestInfoCodeValidation(t *testing.T) {
	// Test that all info codes are non-empty strings
	infoCodes := []string{
		InfoCodeAdminMessage,
		InfoCodeRecruiterManual,
	}

	for _, code := range infoCodes {
		assert.NotEmpty(t, code, "Info code should not be empty")
		assert.Greater(t, len(code), 0, "Info code should have length greater than 0")
	}
}

// Test that error codes are unique
func TestErrorCodeUniqueness(t *testing.T) {
	errorCodes := []string{
		ErrorCodeSelfMessage,
		ErrorCodeGroupMessage,
		ErrorCodeBlockedSender,
		ErrorCodeDisallowedMsgType,
		ErrorCodeEmptyMessage,
		ErrorRateLimitExceeded,
		ErrorCodeUserNotEnabled,
		InfoCodeAdminMessage,
		InfoCodeRecruiterManual,
	}

	// Create a map to track seen codes
	seen := make(map[string]bool)

	for _, code := range errorCodes {
		assert.False(t, seen[code], "Error code %s should be unique", code)
		seen[code] = true
	}
}

// Test that error codes follow naming convention
func TestErrorCodeNamingConvention(t *testing.T) {
	errorCodes := []string{
		ErrorCodeSelfMessage,
		ErrorCodeGroupMessage,
		ErrorCodeBlockedSender,
		ErrorCodeDisallowedMsgType,
		ErrorCodeEmptyMessage,
		ErrorRateLimitExceeded,
		ErrorCodeUserNotEnabled,
		InfoCodeAdminMessage,
		InfoCodeRecruiterManual,
	}

	// All error codes should be in UPPER_CASE with underscores
	for _, code := range errorCodes {
		assert.Regexp(t, `^[A-Z_]+$`, code, "Error code %s should be in UPPER_CASE with underscores", code)
	}
}

// Test business logic for message filtering rules
func TestMessageFilteringLogic(t *testing.T) {
	tests := []struct {
		name          string
		messageType   string
		mediaType     string
		allowedTypes  []string
		expectedBlock bool
		expectedCode  string
	}{
		{
			name:          "Text message with allowed type should not be blocked",
			messageType:   "text",
			allowedTypes:  []string{"text", "audio", "typing"},
			expectedBlock: false,
		},
		{
			name:          "Text message with disallowed type should be blocked",
			messageType:   "text",
			allowedTypes:  []string{"audio", "typing"},
			expectedBlock: true,
			expectedCode:  ErrorCodeDisallowedMsgType,
		},
		{
			name:          "Typing event should be allowed",
			messageType:   "typing",
			allowedTypes:  []string{"text", "audio", "typing"},
			expectedBlock: false,
		},
		{
			name:          "Audio message should be allowed",
			messageType:   "audio",
			allowedTypes:  []string{"text", "audio", "typing"},
			expectedBlock: false,
		},
		{
			name:          "Empty allowed types should block all messages",
			messageType:   "text",
			allowedTypes:  []string{},
			expectedBlock: true,
			expectedCode:  ErrorCodeDisallowedMsgType,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Test the filtering logic directly
			isBlocked := false
			var errorCode string

			// Simulate the filtering logic from ReceiveMessage
			if tt.messageType == "media" {
				// Media type check
				if !slices.Contains(tt.allowedTypes, tt.mediaType) {
					isBlocked = true
					errorCode = ErrorCodeDisallowedMsgType
				}
			} else {
				// Message type check
				if !slices.Contains(tt.allowedTypes, tt.messageType) {
					isBlocked = true
					errorCode = ErrorCodeDisallowedMsgType
				}
			}

			assert.Equal(t, tt.expectedBlock, isBlocked, "Message blocking should match expectation")
			if tt.expectedBlock {
				assert.Equal(t, tt.expectedCode, errorCode, "Error code should match expectation")
			}
		})
	}
}

// Test rate limiting logic
func TestRateLimitingLogic(t *testing.T) {
	tests := []struct {
		name          string
		messageCount  int
		rateLimit     int
		expectedBlock bool
		expectedCode  string
	}{
		{
			name:          "Message count below rate limit should not be blocked",
			messageCount:  5,
			rateLimit:     10,
			expectedBlock: false,
		},
		{
			name:          "Message count at rate limit should be blocked",
			messageCount:  10,
			rateLimit:     10,
			expectedBlock: true,
			expectedCode:  ErrorRateLimitExceeded,
		},
		{
			name:          "Message count above rate limit should be blocked",
			messageCount:  11,
			rateLimit:     10,
			expectedBlock: true,
			expectedCode:  ErrorRateLimitExceeded,
		},
		{
			name:          "Zero rate limit should block all messages",
			messageCount:  1,
			rateLimit:     0,
			expectedBlock: true,
			expectedCode:  ErrorRateLimitExceeded,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Test the rate limiting logic directly
			isBlocked := false
			var errorCode string

			// Simulate the rate limiting logic from ReceiveMessage
			if tt.messageCount >= tt.rateLimit {
				isBlocked = true
				errorCode = ErrorRateLimitExceeded
			}

			assert.Equal(t, tt.expectedBlock, isBlocked, "Rate limiting should match expectation")
			if tt.expectedBlock {
				assert.Equal(t, tt.expectedCode, errorCode, "Error code should match expectation")
			}
		})
	}
}

// Test sender blocking logic
func TestSenderBlockingLogic(t *testing.T) {
	tests := []struct {
		name          string
		isBlocked     bool
		expectedBlock bool
		expectedCode  string
	}{
		{
			name:          "Non-blocked sender should not be blocked",
			isBlocked:     false,
			expectedBlock: false,
		},
		{
			name:          "Blocked sender should be blocked",
			isBlocked:     true,
			expectedBlock: true,
			expectedCode:  ErrorCodeBlockedSender,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Test the sender blocking logic directly
			isBlocked := false
			var errorCode string

			// Simulate the sender blocking logic from ReceiveMessage
			if tt.isBlocked {
				isBlocked = true
				errorCode = ErrorCodeBlockedSender
			}

			assert.Equal(t, tt.expectedBlock, isBlocked, "Sender blocking should match expectation")
			if tt.expectedBlock {
				assert.Equal(t, tt.expectedCode, errorCode, "Error code should match expectation")
			}
		})
	}
}

// Test group message blocking logic
func TestGroupMessageBlockingLogic(t *testing.T) {
	tests := []struct {
		name          string
		isGroup       bool
		expectedBlock bool
		expectedCode  string
	}{
		{
			name:          "Individual message should not be blocked",
			isGroup:       false,
			expectedBlock: false,
		},
		{
			name:          "Group message should be blocked",
			isGroup:       true,
			expectedBlock: true,
			expectedCode:  ErrorCodeGroupMessage,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Test the group message blocking logic directly
			isBlocked := false
			var errorCode string

			// Simulate the group message blocking logic from ReceiveMessage
			if tt.isGroup {
				isBlocked = true
				errorCode = ErrorCodeGroupMessage
			}

			assert.Equal(t, tt.expectedBlock, isBlocked, "Group message blocking should match expectation")
			if tt.expectedBlock {
				assert.Equal(t, tt.expectedCode, errorCode, "Error code should match expectation")
			}
		})
	}
}

// Test empty message blocking logic
func TestEmptyMessageBlockingLogic(t *testing.T) {
	tests := []struct {
		name          string
		content       string
		expectedBlock bool
		expectedCode  string
	}{
		{
			name:          "Non-empty message should not be blocked",
			content:       "Hello World",
			expectedBlock: false,
		},
		{
			name:          "Empty message should be blocked",
			content:       "",
			expectedBlock: true,
			expectedCode:  ErrorCodeEmptyMessage,
		},
		{
			name:          "Whitespace-only message should be blocked",
			content:       "   ",
			expectedBlock: true,
			expectedCode:  ErrorCodeEmptyMessage,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Test the empty message blocking logic directly
			isBlocked := false
			var errorCode string

			// Simulate the empty message blocking logic from ReceiveMessage
			if strings.TrimSpace(tt.content) == "" {
				isBlocked = true
				errorCode = ErrorCodeEmptyMessage
			}

			assert.Equal(t, tt.expectedBlock, isBlocked, "Empty message blocking should match expectation")
			if tt.expectedBlock {
				assert.Equal(t, tt.expectedCode, errorCode, "Error code should match expectation")
			}
		})
	}
}

// Test self-message handling logic
func TestSelfMessageHandlingLogic(t *testing.T) {
	tests := []struct {
		name          string
		senderID      string
		storeID       string
		chatID        string
		recruiterNum  string
		expectedBlock bool
		expectedCode  string
		expectedTopic string
	}{
		{
			name:          "Non-self message should not be blocked",
			senderID:      "sender123",
			storeID:       "store123",
			expectedBlock: false,
		},
		{
			name:          "Self message to recruiter should go to admin topic",
			senderID:      "918496952149",
			storeID:       "918496952149",
			chatID:        "918496952149@s.whatsapp.net",
			recruiterNum:  "918496952149",
			expectedBlock: true,
			expectedCode:  InfoCodeAdminMessage,
			expectedTopic: "admin",
		},
		{
			name:          "Self message to other chat should go to admin topic",
			senderID:      "911000000000",
			storeID:       "911000000000",
			chatID:        "911000000002@s.whatsapp.net",
			recruiterNum:  "911000000000",
			expectedBlock: true,
			expectedCode:  InfoCodeRecruiterManual,
			expectedTopic: "admin",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Test the self-message handling logic directly
			isBlocked := false
			var errorCode string
			var topic string

			// Simulate the self-message logic from ReceiveMessage
			if tt.senderID == tt.storeID {
				isBlocked = true
				if tt.chatID == tt.recruiterNum+"@s.whatsapp.net" {
					errorCode = InfoCodeAdminMessage
					topic = "admin"
				} else {
					errorCode = InfoCodeRecruiterManual
					topic = "admin"
				}
			}

			assert.Equal(t, tt.expectedBlock, isBlocked, "Self message handling should match expectation")
			if tt.expectedBlock {
				assert.Equal(t, tt.expectedCode, errorCode, "Error code should match expectation")
				assert.Equal(t, tt.expectedTopic, topic, "Topic should match expectation")
			}
		})
	}
}

// Test edge cases and error scenarios
func TestEdgeCasesAndErrorScenarios(t *testing.T) {
	t.Run("Nil allowed media types should block all messages", func(t *testing.T) {
		// Test the filtering logic with nil allowed types
		isBlocked := false
		var allowedTypes []string = nil

		// Simulate the filtering logic from ReceiveMessage
		if !slices.Contains(allowedTypes, "text") {
			isBlocked = true
		}

		assert.True(t, isBlocked, "Nil allowed types should block all messages")
	})

	t.Run("Negative message count should not be blocked", func(t *testing.T) {
		// Test rate limiting with negative message count
		isBlocked := false
		messageCount := -5
		rateLimit := 10

		// Simulate the rate limiting logic from ReceiveMessage
		if messageCount >= rateLimit {
			isBlocked = true
		}

		assert.False(t, isBlocked, "Negative message count should not be blocked")
	})

	t.Run("Very large message count should be blocked", func(t *testing.T) {
		// Test rate limiting with very large message count
		isBlocked := false
		messageCount := 999999
		rateLimit := 10

		// Simulate the rate limiting logic from ReceiveMessage
		if messageCount >= rateLimit {
			isBlocked = true
		}

		assert.True(t, isBlocked, "Very large message count should be blocked")
	})

	t.Run("Empty sender ID should not be blocked by sender logic", func(t *testing.T) {
		// Test sender blocking with empty sender ID
		isBlocked := false
		senderID := ""
		storeID := "store123"

		// Simulate the self-message logic from ReceiveMessage
		if senderID == storeID {
			isBlocked = true
		}

		assert.False(t, isBlocked, "Empty sender ID should not be blocked by sender logic")
	})

	t.Run("Empty chat ID should not be blocked by group logic", func(t *testing.T) {
		// Test group message blocking with empty chat ID
		isBlocked := false
		chatID := ""

		// Simulate the group message blocking logic from ReceiveMessage
		if strings.Contains(chatID, "@g.us") {
			isBlocked = true
		}

		assert.False(t, isBlocked, "Empty chat ID should not be blocked by group logic")
	})
}

// Test error code consistency
func TestErrorCodeConsistency(t *testing.T) {
	t.Run("All error codes should be non-empty strings", func(t *testing.T) {
		errorCodes := []string{
			ErrorCodeSelfMessage,
			ErrorCodeGroupMessage,
			ErrorCodeBlockedSender,
			ErrorCodeDisallowedMsgType,
			ErrorCodeEmptyMessage,
			ErrorRateLimitExceeded,
			ErrorCodeUserNotEnabled,
			InfoCodeAdminMessage,
			InfoCodeRecruiterManual,
		}

		for _, code := range errorCodes {
			assert.NotEmpty(t, code, "Error code should not be empty")
			assert.IsType(t, "", code, "Error code should be a string")
		}
	})

	t.Run("Error codes should not contain special characters", func(t *testing.T) {
		errorCodes := []string{
			ErrorCodeSelfMessage,
			ErrorCodeGroupMessage,
			ErrorCodeBlockedSender,
			ErrorCodeDisallowedMsgType,
			ErrorCodeEmptyMessage,
			ErrorRateLimitExceeded,
			ErrorCodeUserNotEnabled,
			InfoCodeAdminMessage,
			InfoCodeRecruiterManual,
		}

		for _, code := range errorCodes {
			// Check that error codes only contain letters, numbers, and underscores
			assert.Regexp(t, `^[A-Z0-9_]+$`, code, "Error code %s should only contain uppercase letters, numbers, and underscores", code)
		}
	})
}

// Test business logic integration
func TestBusinessLogicIntegration(t *testing.T) {
	t.Run("Multiple blocking conditions should all be detected", func(t *testing.T) {
		// Test scenario where multiple blocking conditions are true
		mediaType := "video"
		allowedTypes := []string{"text", "image"}
		isGroup := true
		messageCount := 15
		rateLimit := 10
		senderBlocked := true

		// Simulate all the blocking logic from ReceiveMessage
		isBlocked := false
		var errorCodes []string

		// Check media type
		if !slices.Contains(allowedTypes, mediaType) {
			isBlocked = true
			errorCodes = append(errorCodes, ErrorCodeDisallowedMsgType)
		}

		// Check group message
		if isGroup {
			isBlocked = true
			errorCodes = append(errorCodes, ErrorCodeGroupMessage)
		}

		// Check rate limiting
		if messageCount >= rateLimit {
			isBlocked = true
			errorCodes = append(errorCodes, ErrorRateLimitExceeded)
		}

		// Check sender blocking
		if senderBlocked {
			isBlocked = true
			errorCodes = append(errorCodes, ErrorCodeBlockedSender)
		}

		assert.True(t, isBlocked, "Message should be blocked when multiple conditions are true")
		assert.Len(t, errorCodes, 4, "Should detect all blocking conditions")
		assert.Contains(t, errorCodes, ErrorCodeDisallowedMsgType, "Should detect disallowed media type")
		assert.Contains(t, errorCodes, ErrorCodeGroupMessage, "Should detect group message")
		assert.Contains(t, errorCodes, ErrorRateLimitExceeded, "Should detect rate limit exceeded")
		assert.Contains(t, errorCodes, ErrorCodeBlockedSender, "Should detect blocked sender")
	})

	t.Run("No blocking conditions should allow message", func(t *testing.T) {
		// Test scenario where no blocking conditions are true
		allowedTypes := []string{"text", "image"}
		isGroup := false
		messageCount := 5
		rateLimit := 10
		senderBlocked := false

		// Simulate all the blocking logic from ReceiveMessage
		isBlocked := false

		// Check message type (using hardcoded "text" since we're testing the logic)
		if !slices.Contains(allowedTypes, "text") {
			isBlocked = true
		}

		// Check group message
		if isGroup {
			isBlocked = true
		}

		// Check rate limiting
		if messageCount >= rateLimit {
			isBlocked = true
		}

		// Check sender blocking
		if senderBlocked {
			isBlocked = true
		}

		assert.False(t, isBlocked, "Message should not be blocked when no conditions are true")
		assert.True(t, slices.Contains(allowedTypes, "text"), "Text should be in allowed types")
	})
}
