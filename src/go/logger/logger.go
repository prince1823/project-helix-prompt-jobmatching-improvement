package logger

import (
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"

	"gopkg.in/natefinch/lumberjack.v2"
)

var l *slog.Logger

// LogConfig represents logging configuration
type LogConfig struct {
	FilePath     string
	UseLocalTime bool
	FileMaxSize  int
	FileMaxAge   int
	LogLevel     int
}

func L() *slog.Logger {
	return l
}

func New(cfg LogConfig, opt *slog.HandlerOptions, writeInConsole bool) *slog.Logger {
	dirMainLogger := cfg.FilePath
	file_path := filepath.Join(dirMainLogger, fmt.Sprintf("%s-%s-%s%s", "whatsapp", "bot", "go", ".log"))
	fileWriter := &lumberjack.Logger{
		Filename:  file_path,
		LocalTime: cfg.UseLocalTime,
		MaxSize:   cfg.FileMaxSize,
		MaxAge:    cfg.FileMaxAge,
	}

	if writeInConsole {
		return slog.New(slog.NewJSONHandler(io.MultiWriter(fileWriter, os.Stdout), opt))
	}

	return slog.New(slog.NewJSONHandler(fileWriter, opt))
}

func SetLogger(logger *slog.Logger) {
	l = logger
}
