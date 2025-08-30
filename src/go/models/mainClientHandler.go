package models

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/segmentio/kafka-go"
	"go.mau.fi/whatsmeow/store"
	"go.mau.fi/whatsmeow/store/sqlstore"
)

/*
NewMainClientManager creates and returns a new instance of MainClientManager.

Parameters:
- config: Application configuration.
- logger: slog.Logger instance for logging.
- container: SQL store container.
- database: PostgresDB which hods the connector.
- kafkaReader: Kafka reader for incoming messages.
- kafkaWriter: Kafka writer for processed messages.
- rawKafkaWriter: Kafka writer for raw messages.

Returns:
- *MainClientManager: A new MainClientManager instance.
*/
func NewMainClientManager(config Config, logger *slog.Logger, container *sqlstore.Container, database *PostgresRepository, kafkaReaders map[string]*kafka.Reader, kafkaWriters map[string]*kafka.Writer) *MainClientManager {
	ctx, cancel := context.WithCancel(context.Background())

	messageHandler := NewMessageHandler(logger, kafkaWriters)

	return &MainClientManager{
		Config:         config,
		Logger:         logger,
		Container:      container,
		ClientManagers: make(map[string]*WhatsAppClientManager),
		KafkaReaders:   kafkaReaders,
		MessageHandler: messageHandler,
		ctx:            ctx,
		cancel:         cancel,
		database:       database,
	}
}

/*
Start initializes all clients, starts the message sending routine,
and waits for an OS signal to gracefully shut down.

Returns:
- error: if client initialization fails.
*/
func (mcm *MainClientManager) Start() error {
	const function = "Start"

	mcm.Logger.Info("Starting MainClientManager", "function", function)

	err := mcm.InitializeAllClients()
	if err != nil {
		mcm.Logger.Error("Failed to initialize clients", "function", function, "error", err)
		return fmt.Errorf("failed to initialize clients: %v", err)
	}

	mcm.StartMessageSending()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	mcm.Logger.Info("MainClientManager started, waiting for shutdown signal", "function", function)

	<-sigChan

	mcm.Logger.Info("Shutdown signal received, cleaning up...", "function", function)

	mcm.cancel()
	mcm.DisconnectAllClients()

	mcm.Logger.Info("MainClientManager stopped successfully", "function", function)
	return nil
}

/*
InitializeAllClients initializes WhatsApp clients for all recruiters defined in the config.

Returns:
- error: If device fetching or any client initialization fails.
*/
func (mcm *MainClientManager) InitializeAllClients() error {
	const function = "InitializeAllClients"

	mcm.Logger.Info("Initializing all WhatsApp clients", "function", function, "recruiter_count", len(mcm.Config.WhatsApp))

	devicesInStore, err := mcm.Container.GetAllDevices(mcm.ctx)
	if err != nil {
		mcm.Logger.Error("Failed to get devices from store", "function", function, "error", err)
		return err
	}

	for _, recruiterConfig := range mcm.Config.WhatsApp {
		if recruiterConfig.Enable {
			err := mcm.InitializeClient(recruiterConfig, devicesInStore, mcm.database, mcm.Config)
			if err != nil {
				mcm.Logger.Error("Failed to initialize client",
					"function", function,
					"recruiter", recruiterConfig.RecruiterNumber,
					"error", err)
				return err
			}
		}

	}

	mcm.Logger.Info("All WhatsApp clients initialized successfully", "function", function)
	return nil
}

/*
InitializeClient initializes a WhatsApp client for a specific recruiter if not already present.

Parameters:
- recruiterConfig: Config for the recruiter.
- devicesInStore: List of existing devices from the store.

Returns:
- error: If client connection fails.
*/
func (mcm *MainClientManager) InitializeClient(recruiterConfig RecruiterConfig, devicesInStore []*store.Device, database *PostgresRepository, config Config) error {
	const function = "InitializeClient"

	mcm.mu.Lock()
	defer mcm.mu.Unlock()

	if _, exists := mcm.ClientManagers[recruiterConfig.RecruiterNumber]; exists {
		mcm.Logger.Info("Client already exists, skipping initialization", "function", function, "recruiter", recruiterConfig.RecruiterNumber)
		return nil
	}

	clientManager := NewWhatsAppClientManager(recruiterConfig, mcm.Logger, mcm.Container, mcm.MessageHandler.SendMessageToKafka, database, config)

	err := clientManager.Connect(mcm.ctx, devicesInStore)
	if err != nil {
		mcm.Logger.Error("Failed to connect client",
			"function", function,
			"recruiter", recruiterConfig.RecruiterNumber,
			"error", err)
		return err
	}
	mcm.ClientManagers[recruiterConfig.RecruiterNumber] = clientManager
	mcm.Logger.Info("Client initialized successfully", "function", function, "recruiter", recruiterConfig.RecruiterNumber)
	// Set the logout callback
	clientManager.OnLogout = func(recruiterID string) {
		mcm.mu.Lock()
		defer mcm.mu.Unlock()
		delete(mcm.ClientManagers, recruiterID)
		mcm.Logger.Info("[Mcm Reomved] Client removed from MainClientManager after logout", "recruiter", recruiterID)
	}
	return nil
}

/*
GetClientManager retrieves a WhatsAppClientManager for a specific recruiter.

Parameters:
- recruiterNumber: The recruiter's phone number.

Returns:
- *WhatsAppClientManager: Pointer to the client's manager.
- bool: true if exists, false otherwise.
*/
func (mcm *MainClientManager) GetClientManager(recruiterNumber string) (*WhatsAppClientManager, bool) {
	mcm.mu.RLock()
	defer mcm.mu.RUnlock()

	clientManager, exists := mcm.ClientManagers[recruiterNumber]
	return clientManager, exists
}

/*
GetAllClientManagers returns a copy of all client managers to avoid race conditions.

Returns:
- map[string]*WhatsAppClientManager: Map of recruiter numbers to client managers.
*/
func (mcm *MainClientManager) GetAllClientManagers() map[string]*WhatsAppClientManager {
	mcm.mu.RLock()
	defer mcm.mu.RUnlock()

	copyMap := make(map[string]*WhatsAppClientManager)
	for k, v := range mcm.ClientManagers {
		copyMap[k] = v
	}
	return copyMap
}

/*
DisconnectAllClients disconnects all active WhatsApp clients gracefully.

Returns: None.
*/
func (mcm *MainClientManager) DisconnectAllClients() {
	const function = "DisconnectAllClients"

	mcm.Logger.Info("Disconnecting all WhatsApp clients", "function", function)

	mcm.mu.Lock()
	defer mcm.mu.Unlock()

	for recruiterNumber, clientManager := range mcm.ClientManagers {
		clientManager.Disconnect()
		mcm.Logger.Info("Client disconnected", "function", function, "recruiter", recruiterNumber)
	}
}

/*
Stop gracefully stops the MainClientManager and its resources.

Returns: None.
*/
func (mcm *MainClientManager) Stop() {
	const function = "Stop"

	mcm.Logger.Info("Stopping MainClientManager", "function", function)
	mcm.cancel()
	mcm.DisconnectAllClients()

	if mcm.MessageHandler != nil {
		if err := mcm.MessageHandler.Close(); err != nil {
			mcm.Logger.Error("Error closing message handler", "function", function, "error", err)
		}
	}
}
