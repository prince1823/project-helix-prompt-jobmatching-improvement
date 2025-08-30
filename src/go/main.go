package main

import (
	"fmt"
	"gobot/whatsappbot/logger"
	models "gobot/whatsappbot/models"

	_ "github.com/lib/pq"
)

var (
	mainClientManager *models.MainClientManager
)

func main() {
	// Load configuration
	if err := LoadConfig(); err != nil {
		panic(fmt.Sprintf("Failed to load config: %v", err))
	}

	// Initialize logger
	if err := initializeLogger(); err != nil {
		panic(fmt.Sprintf("Failed to initialize logger: %v", err))
	}

	// Initialize Kafka
	if err := InitKafka(); err != nil {
		panic(fmt.Sprintf("Failed to initialize Kafka: %v", err))
	}

	// Initialize database connection
	container, database, err := initializeDatabase()
	if err != nil {
		panic(fmt.Sprintf("Failed to initialize database: %v", err))
	}

	// Create main client manager with Kafka components
	mainClientManager = models.NewMainClientManager(appConfig, logger.L(), container, database, kafkaReaders, kafkaWriters)

	// Set up cleanup on exit
	defer func() {
		logger.L().Info("Shutting down application...")
		Cleanup()
	}()

	// Start the main client manager
	if err := mainClientManager.Start(); err != nil {
		panic(fmt.Sprintf("Failed to start main client manager: %v", err))
	}
}
