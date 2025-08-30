package models

import (
	"context"
	"log/slog"
	"testing"
	"time"

	"github.com/segmentio/kafka-go"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.mau.fi/whatsmeow/store/sqlstore"
)

// MockContainer is a mock for sqlstore.Container
type MockContainer struct {
	mock.Mock
	*sqlstore.Container
}

// NewMockContainer creates a new mock container
func NewMockContainer() *MockContainer {
	return &MockContainer{
		Container: &sqlstore.Container{},
	}
}

// MockKafkaReader is a mock for kafka.Reader
type MockKafkaReader struct {
	mock.Mock
}

func (m *MockKafkaReader) ReadMessage(ctx context.Context) (kafka.Message, error) {
	args := m.Called(ctx)
	return args.Get(0).(kafka.Message), args.Error(1)
}

func (m *MockKafkaReader) Close() error {
	args := m.Called()
	return args.Error(0)
}

// MockKafkaWriter is a mock for kafka.Writer
type MockKafkaWriter struct {
	mock.Mock
}

func (m *MockKafkaWriter) WriteMessages(ctx context.Context, msgs ...kafka.Message) error {
	args := m.Called(ctx, msgs)
	return args.Error(0)
}

func (m *MockKafkaWriter) Close() error {
	args := m.Called()
	return args.Error(0)
}

func TestNewMainClientManager(t *testing.T) {
	// Setup
	logger := slog.Default()
	mockContainer := NewMockContainer()

	kafkaReaders := make(map[string]*kafka.Reader)
	kafkaWriters := make(map[string]*kafka.Writer)

	config := Config{
		WhatsApp: []RecruiterConfig{
			{
				RecruiterNumber:   "918496952149",
				Enable:            true,
				AllowedMediaTypes: []string{"text", "audio", "typing"},
				MessageRateLimit:  10,
				HostClientType:    "Chrome",
				HostClientName:    "TestClient",
			},
		},
	}

	// Execute
	mcm := NewMainClientManager(config, logger, mockContainer.Container, &PostgresRepository{}, kafkaReaders, kafkaWriters)

	// Assert
	assert.NotNil(t, mcm)
	assert.Equal(t, config, mcm.Config)
	assert.NotNil(t, mcm.ClientManagers)
	assert.NotNil(t, mcm.MessageHandler)
	assert.NotNil(t, mcm.ctx)
	assert.NotNil(t, mcm.cancel)
}

func TestInitializeAllClients(t *testing.T) {
	t.Skip("Skipping test as it requires actual device connection")
}

func TestGetClientManager(t *testing.T) {
	// Setup
	logger := slog.Default()
	mockContainer := NewMockContainer()

	mcm := NewMainClientManager(Config{}, logger, mockContainer.Container, &PostgresRepository{}, nil, nil)

	// Add a test client manager
	testRecruiter := "1234567890"
	mcm.ClientManagers[testRecruiter] = &WhatsAppClientManager{}

	// Test existing client
	manager, exists := mcm.GetClientManager(testRecruiter)
	assert.True(t, exists)
	assert.NotNil(t, manager)

	// Test non-existing client
	manager, exists = mcm.GetClientManager("nonexistent")
	assert.False(t, exists)
	assert.Nil(t, manager)
}

func TestGetAllClientManagers(t *testing.T) {
	// Setup
	logger := slog.Default()
	mockContainer := NewMockContainer()

	mcm := NewMainClientManager(Config{}, logger, mockContainer.Container, &PostgresRepository{}, nil, nil)

	// Add test client managers
	mcm.ClientManagers["test1"] = &WhatsAppClientManager{}
	mcm.ClientManagers["test2"] = &WhatsAppClientManager{}

	// Get copy of managers
	managers := mcm.GetAllClientManagers()

	// Verify the copy contains all managers
	assert.Equal(t, len(mcm.ClientManagers), len(managers))
	assert.NotNil(t, managers["test1"])
	assert.NotNil(t, managers["test2"])

	// Verify it's a deep copy
	delete(managers, "test1")
	assert.NotNil(t, mcm.ClientManagers["test1"])
}

func TestStop(t *testing.T) {
	// Setup
	logger := slog.Default()
	mockContainer := NewMockContainer()

	mcm := NewMainClientManager(Config{}, logger, mockContainer.Container, &PostgresRepository{}, nil, nil)

	// Add a test client manager with mock
	mockClientManager := &WhatsAppClientManager{}
	mcm.ClientManagers["test1"] = mockClientManager

	// Execute Stop
	mcm.Stop()

	// Verify the context is cancelled
	select {
	case <-mcm.ctx.Done():
		// Context was cancelled as expected
	case <-time.After(time.Second):
		t.Error("Context was not cancelled")
	}
}
