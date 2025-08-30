package models

import (
	"context"
	"log/slog"
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.mau.fi/whatsmeow"
)

// MockMessageCallback mocks the MessageCallback function
type MockMessageCallback struct {
	mock.Mock
}

func (m *MockMessageCallback) Call(payload interface{}, topicName string, kafkaKey string) error {
	args := m.Called(payload, topicName, kafkaKey)
	return args.Error(0)
}

func TestNewWhatsAppClientManager(t *testing.T) {
	// Setup
	logger := slog.Default()
	mockCallback := func(payload interface{}, topicName string, kafkaKey string) error {
		return nil
	}

	config := Config{
		Logger: LogConfig{
			FilePath: "test_logs",
		},
	}

	recruiterConfig := RecruiterConfig{
		RecruiterNumber:   "918496952149",
		HostClientType:    "Chrome",
		HostClientName:    "TestClient",
		AllowedMediaTypes: []string{"text", "audio", "typing"},
		MessageRateLimit:  10,
		Enable:            true,
	}

	// Execute
	wcm := NewWhatsAppClientManager(recruiterConfig, logger, nil, mockCallback, nil, config)

	// Assert
	assert.NotNil(t, wcm)
	assert.Equal(t, recruiterConfig, wcm.RecruiterConfig)
	assert.NotNil(t, wcm.Logger)
	assert.NotNil(t, wcm.ClientLog)
	assert.False(t, wcm.IsConnected)

	// Cleanup
	os.RemoveAll("test_logs")
}

func TestExtractPhoneNumber(t *testing.T) {
	tests := []struct {
		name     string
		jid      string
		expected string
	}{
		{
			name:     "Standard JID format",
			jid:      "918050992006@s.whatsapp.net",
			expected: "918050992006",
		},
		{
			name:     "Colon format",
			jid:      "918496952149:12",
			expected: "918496952149",
		},
		{
			name:     "Plain number",
			jid:      "918050992006",
			expected: "918050992006",
		},
		{
			name:     "Empty string",
			jid:      "",
			expected: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := ExtractPhoneNumber(tt.jid)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestConvertToJID(t *testing.T) {
	tests := []struct {
		name     string
		number   string
		expected string
	}{
		{
			name:     "Standard phone number",
			number:   "918050992006",
			expected: "918050992006@s.whatsapp.net",
		},
		{
			name:     "Empty string",
			number:   "",
			expected: "@s.whatsapp.net",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := ConvertToJID(tt.number)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestSetLogger(t *testing.T) {
	// Setup
	wcm := &WhatsAppClientManager{}
	newLogger := slog.Default()

	// Execute
	wcm.SetLogger(newLogger)

	// Assert
	assert.Equal(t, newLogger, wcm.Logger)
}

func TestPairPhone(t *testing.T) {
	tests := []struct {
		name        string
		phoneNumber string
		clientName  string
		config      RecruiterConfig
		expectError bool
	}{
		{
			name:        "Valid phone and client",
			phoneNumber: "918496952149",
			clientName:  "Chrome",
			config: RecruiterConfig{
				HostClientType: "Chrome",
			},
			expectError: true, // Will error because WhatsAppClient is nil
		},
		{
			name:        "Invalid phone number - too short",
			phoneNumber: "123",
			clientName:  "Chrome",
			config: RecruiterConfig{
				HostClientType: "Chrome",
			},
			expectError: true,
		},
		{
			name:        "Invalid client name",
			phoneNumber: "1234567890",
			clientName:  "Invalid",
			config: RecruiterConfig{
				HostClientType: "Chrome",
			},
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			wcm := &WhatsAppClientManager{
				RecruiterConfig: tt.config,
				Logger:          slog.Default(),
			}

			err := wcm.PairPhone(tt.phoneNumber, tt.clientName)
			if tt.expectError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestDisconnect(t *testing.T) {
	// Setup
	wcm := &WhatsAppClientManager{
		Logger: slog.Default(),
		RecruiterConfig: RecruiterConfig{
			RecruiterNumber: "1234567890",
		},
	}

	// Test when not connected
	wcm.IsConnected = false
	wcm.WhatsAppClient = nil
	wcm.Disconnect()
	assert.False(t, wcm.IsConnected)

	// Skip the connected test case as it requires a real whatsmeow client
	t.Skip("Skipping connected test case as it requires a real whatsmeow client")
}

func TestLogoutEventHandler(t *testing.T) {
	// Setup
	var logoutCalled bool
	onLogout := func(recruiterID string) {
		logoutCalled = true
		assert.Equal(t, "1234567890", recruiterID)
	}

	wcm := &WhatsAppClientManager{
		Logger: slog.Default(),
		RecruiterConfig: RecruiterConfig{
			RecruiterNumber: "1234567890",
		},
		IsConnected: true,
		OnLogout:    onLogout,
		WhatsAppClient: &whatsmeow.Client{
			BackgroundEventCtx: context.Background(),
		},
	}

	// Execute
	wcm.LogoutEventHandler()

	// Assert
	assert.False(t, wcm.IsConnected)
	assert.True(t, logoutCalled)
}

func TestCreateRecruiterLogger(t *testing.T) {
	// Setup
	mainLogger := slog.Default()
	config := Config{
		Logger: LogConfig{
			FilePath: "test_logs",
		},
	}

	// Execute
	logger := createRecruiterLogger("1234567890", mainLogger, config)

	// Assert
	assert.NotNil(t, logger)

	// Cleanup
	os.RemoveAll("test_logs")
}

func TestGenerateQRCodeInLog(t *testing.T) {
	// Setup
	wcm := &WhatsAppClientManager{
		Logger: slog.Default(),
		RecruiterConfig: RecruiterConfig{
			RecruiterNumber: "1234567890",
		},
		config: Config{
			Logger: LogConfig{
				FilePath: "test_logs",
			},
		},
	}

	// Execute
	wcm.generateQRCodeInLog("test-qr-code", "Test QR")

	// Assert
	qrPath := "test_logs/qr/qr-code-1234567890.log"
	_, err := os.Stat(qrPath)
	assert.NoError(t, err)

	// Cleanup
	os.RemoveAll("test_logs")
}

// Skipping tests that require actual WhatsApp connection
func TestConnect(t *testing.T) {
	t.Skip("Skipping as it requires actual WhatsApp connection")
}

func TestAsyncLogin(t *testing.T) {
	t.Skip("Skipping as it requires actual WhatsApp connection")
}

func TestGetOrCreateDeviceStore(t *testing.T) {
	t.Skip("Skipping as it requires actual WhatsApp connection")
}

func TestLoginEventHandler(t *testing.T) {
	t.Skip("Skipping as it requires actual WhatsApp connection")
}
