package models

import (
	"context"
	"database/sql"
	"log/slog"
	"sync"

	"github.com/segmentio/kafka-go"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/store"
	"go.mau.fi/whatsmeow/store/sqlstore"
	waLog "go.mau.fi/whatsmeow/util/log"
)

type Config struct {
	Kafka    KafkaConfig       `yaml:"kafka"`
	WhatsApp []RecruiterConfig `yaml:"whatsapp"`
	Postgres PostgresConfig    `yaml:"postgres"`
	Logger   LogConfig         `yaml:"logger"`
}

type KafkaConfig struct {
	Brokers []string    `yaml:"brokers"`
	Raw     TopicConfig `yaml:"raw"`
	Ingest  TopicConfig `yaml:"ingest"`
	Output  TopicConfig `yaml:"output"`
	Failed  TopicConfig `yaml:"failed"`
	Admin   TopicConfig `yaml:"admin"`
}

type TopicConfig struct {
	Topic   string `yaml:"topic"`
	GroupID string `yaml:"group_id"`
}

type RecruiterConfig struct {
	RecruiterNumber   string   `yaml:"recruiter_id"`
	HostClientType    string   `yaml:"host_client_type"`
	HostClientName    string   `yaml:"host_client_name"`
	AllowedMediaTypes []string `yaml:"allowed_media_types"`
	MessageRateLimit  int      `yaml:"message_rate_limit"`
	Enable            bool     `yaml:"enable"`
}

type PostgresConfig struct {
	Host                  string `yaml:"host"`
	Port                  int    `yaml:"port"`
	Database              string `yaml:"database"`
	User                  string `yaml:"user"`
	Password              string `yaml:"password"`
	MaxOpenConnection     int    `yaml:"max_open_connection"`
	MaxIdleConnection     int    `yaml:"max_idle_connection"`
	ConnectionMaxLifeTime int    `yaml:"connection_max_life_time"`
}

type LogConfig struct {
	FilePath     string `yaml:"file_path"`
	Level        int    `yaml:"level"`
	UseLocalTime bool   `yaml:"use_local_time"`
	FileMaxSize  int    `yaml:"file_max_size"`
	FileMaxAge   int    `yaml:"file_max_age"`
}

// MainClientManager manages multiple WhatsApp client managers
type MainClientManager struct {
	Config         Config
	Logger         *slog.Logger
	Container      *sqlstore.Container
	ClientManagers map[string]*WhatsAppClientManager
	KafkaReaders   map[string]*kafka.Reader
	MessageHandler *MessageHandler
	mu             sync.RWMutex
	ctx            context.Context
	cancel         context.CancelFunc
	database       *PostgresRepository
}

// MessageCallback is a function type for handling messages
type MessageCallback func(payload interface{}, topicName string, kafkaKey string) error

// WhatsAppClientManager manages a single WhatsApp client instance
type WhatsAppClientManager struct {
	RecruiterConfig RecruiterConfig
	Logger          *slog.Logger
	ClientLog       waLog.Logger
	WhatsAppClient  *whatsmeow.Client
	DeviceStore     *store.Device
	Container       *sqlstore.Container
	IsConnected     bool
	MessageCallback MessageCallback
	database        *PostgresRepository
	config          Config
	OnLogout        func(recruiterID string)
}

// MessageHandler manages all Kafka operations centrally
type MessageHandler struct {
	Logger       *slog.Logger
	KafkaWriters map[string]*kafka.Writer
	mu           sync.RWMutex
}

type PostgresRepository struct {
	Db *sql.DB // db holds the database connection pool.

}

type RecruiterConfigDB struct {
	RecruiterID  string `json:"recruiter_id"`
	ApplicantID  string `json:"applicant_id"`
	Enabled      bool   `json:"enabled"`
	MessageCount int    `json:"message_count"`
}
