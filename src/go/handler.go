package main

import (
	"context"
	"database/sql"
	"fmt"
	"gobot/whatsappbot/logger"

	models "gobot/whatsappbot/models"
	"log/slog"
	"os"
	"path/filepath"
	"time"

	"github.com/segmentio/kafka-go"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"gopkg.in/yaml.v2"

	_ "github.com/jackc/pgx/v5/stdlib" // PostgreSQL driver
	_ "github.com/lib/pq"
	waLog "go.mau.fi/whatsmeow/util/log"
)

var (
	kafkaReaders   map[string]*kafka.Reader
	kafkaWriters   map[string]*kafka.Writer
	whatsappClient *whatsmeow.Client
	appConfig      models.Config
)

// LoadConfig loads application configuration from the YAML file located at ../../data/config.yaml.
// Returns an error if reading or parsing the file fails.
func LoadConfig() error {

	data, err := os.ReadFile("../../config/app/config.yaml")
	if err != nil {

		return fmt.Errorf("error reading config file: %v", err)
	}

	err = yaml.Unmarshal(data, &appConfig)
	if err != nil {

		return fmt.Errorf("error parsing config file: %v", err)
	}

	return nil
}

// InitKafka initializes Kafka readers and writers based on the loaded configuration.
// Returns an error if initialization fails.
func InitKafka() error {

	kafkaReaders = make(map[string]*kafka.Reader)
	kafkaReaders["output"] = kafka.NewReader(kafka.ReaderConfig{
		Brokers: appConfig.Kafka.Brokers,
		Topic:   appConfig.Kafka.Output.Topic,
		GroupID: appConfig.Kafka.Output.GroupID,
	})

	kafkaWriters = make(map[string]*kafka.Writer)
	kafkaWriters["ingest"] = kafka.NewWriter(kafka.WriterConfig{
		Brokers: appConfig.Kafka.Brokers,
		Topic:   appConfig.Kafka.Ingest.Topic,
	})

	kafkaWriters["raw"] = kafka.NewWriter(kafka.WriterConfig{
		Brokers: appConfig.Kafka.Brokers,
		Topic:   appConfig.Kafka.Raw.Topic,
	})
	kafkaWriters["failed"] = kafka.NewWriter(kafka.WriterConfig{
		Brokers: appConfig.Kafka.Brokers,
		Topic:   appConfig.Kafka.Failed.Topic,
	})
	kafkaWriters["admin"] = kafka.NewWriter(kafka.WriterConfig{
		Brokers: appConfig.Kafka.Brokers,
		Topic:   appConfig.Kafka.Admin.Topic,
	})

	return nil
}

// CleanupKafka closes all Kafka readers and writers gracefully.
// Logs errors encountered during closure.
func CleanupKafka() {

	for _, reader := range kafkaReaders {
		if err := reader.Close(); err != nil {
			logger.L().Error("Issue Wile closing kafkaReaders")
		} else {
			logger.L().Info("kafkaReaders cleanup successfull")
		}
	}

	for _, writer := range kafkaWriters {
		if err := writer.Close(); err != nil {
			logger.L().Error("Issue Wile closing kafkaWriters")
		} else {
			logger.L().Info("kafkaWriters cleanup successfull")
		}
	}
}

// Cleanup performs the overall resource cleanup including logs, Kafka resources, and WhatsApp clients.
// Ensures no lingering resources are left open.
func Cleanup() {

	clearLogsDir(appConfig.Logger.FilePath + "/qr")
	CleanupKafka()
	// mainClientManager.database.DB.Close()

	if mainClientManager != nil {

		mainClientManager.Stop()
	}

	if whatsappClient != nil {

		whatsappClient.Disconnect()
	}

}

// initializeLogger sets up the structured logger (slog) for the application.
// Applies default values if not provided in the config.
// Returns an error if logger setup fails.
func initializeLogger() error {

	if appConfig.Logger.FilePath == "" {
		appConfig.Logger.FilePath = "../../config/logs/"
	}
	if appConfig.Logger.FileMaxSize == 0 {
		appConfig.Logger.FileMaxSize = 100
	}
	if appConfig.Logger.FileMaxAge == 0 {
		appConfig.Logger.FileMaxAge = 30
	}

	logConfig := logger.LogConfig{
		FilePath:     appConfig.Logger.FilePath,
		UseLocalTime: appConfig.Logger.UseLocalTime,
		FileMaxSize:  appConfig.Logger.FileMaxSize,
		FileMaxAge:   appConfig.Logger.FileMaxAge,
		LogLevel:     appConfig.Logger.Level,
	}

	opts := &slog.HandlerOptions{
		Level: slog.Level(logConfig.LogLevel),
	}

	log := logger.New(logConfig, opts, true)
	logger.SetLogger(log)

	return nil
}

// initializeDatabase initializes and returns the WhatsApp SQL store container using PostgreSQL connection details from the config.
// Returns the SQL store container and an error if the initialization fails.
func initializeDatabase() (*sqlstore.Container, *models.PostgresRepository, error) {

	dbLog := waLog.Stdout("Database", "DEBUG", true)
	ctx := context.Background()

	dbPath := fmt.Sprintf("postgres://%s:%s@%s:%d/%s?sslmode=disable",
		appConfig.Postgres.User,
		appConfig.Postgres.Password,
		appConfig.Postgres.Host,
		appConfig.Postgres.Port,
		appConfig.Postgres.Database,
	)

	container, err := sqlstore.New(ctx, "postgres", dbPath, dbLog)
	if err != nil {

		return nil, nil, fmt.Errorf("failed to create database container: %v", err)
	}

	// Connect to the PostgreSQL database using the provided URL.
	pConnector, err := sql.Open("pgx", dbPath)
	if err != nil {
		logger.L().Error("Failed to open database connection with Postgres", "error", err)
		return nil, nil, fmt.Errorf("failed to open database connection: %w", err)
	}

	// Ping the database to verify the connection.
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := pConnector.PingContext(ctx); err != nil {
		pConnector.Close() // Close the connection if ping fails.
		logger.L().Error("Failed to ping database", "dbpath", dbPath, "error", err)
		return nil, nil, fmt.Errorf("failed to ping database: %w", err)
	}
	// Configure connection pool settings.
	pConnector.SetMaxOpenConns(appConfig.Postgres.MaxOpenConnection)                                     // Maximum number of open connections to the database.
	pConnector.SetMaxIdleConns(appConfig.Postgres.MaxIdleConnection)                                     // Maximum number of connections in the idle connection pool.
	pConnector.SetConnMaxLifetime(time.Duration(appConfig.Postgres.ConnectionMaxLifeTime) * time.Minute) // Maximum amount of time a connection may be reused.

	// Create repository instance using a constructor.
	database := &models.PostgresRepository{Db: pConnector}
	logger.L().Info("PostgreSQL repository initialized successfully")

	return container, database, nil
}

// clearLogsDir removes all files and subdirectories inside the specified logs directory.
// Logs each file removal and errors encountered, if any.
//
// Parameters:
// - path: The path to the logs directory.
//
// Returns: None.
func clearLogsDir(path string) {

	entries, err := os.ReadDir(path)
	if err != nil {

		return
	}

	for _, entry := range entries {
		entryPath := filepath.Join(path, entry.Name())
		err := os.RemoveAll(entryPath)
		if err != nil {

		} else {

		}
	}
}
