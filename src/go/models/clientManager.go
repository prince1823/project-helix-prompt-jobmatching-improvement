package models

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"strings"

	"github.com/mdp/qrterminal/v3"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/store"
	"go.mau.fi/whatsmeow/store/sqlstore"
	waLog "go.mau.fi/whatsmeow/util/log"
	"google.golang.org/protobuf/proto"
	"gopkg.in/natefinch/lumberjack.v2"
)

/*
NewWhatsAppClientManager creates a new instance of WhatsAppClientManager with dedicated logger and client log.

Parameters:
- recruiterConfig: Configuration for the recruiter.
- mainLogger: Main logger instance.
- container: SQL store container.
- messageCallback: Callback function for incoming messages.

Returns:
- Pointer to WhatsAppClientManager.
*/
func NewWhatsAppClientManager(recruiterConfig RecruiterConfig, mainLogger *slog.Logger, container *sqlstore.Container, messageCallback MessageCallback, database *PostgresRepository, config Config) *WhatsAppClientManager {
	clientLog := waLog.Stdout(fmt.Sprintf("Client-%s", recruiterConfig.RecruiterNumber), "DEBUG", true)
	recruiterLogger := createRecruiterLogger(recruiterConfig.RecruiterNumber, mainLogger, config)

	return &WhatsAppClientManager{
		RecruiterConfig: recruiterConfig,
		Logger:          recruiterLogger,
		ClientLog:       clientLog,
		Container:       container,
		IsConnected:     false,
		MessageCallback: messageCallback,
		database:        database,
		config:          config,
	}
}

/*
createRecruiterLogger sets up a dedicated logger for a specific recruiter.

Parameters:
- recruiterNumber: Phone number of the recruiter.
- mainLogger: Main logger to fallback if directory creation fails.

Returns:
- Pointer to new slog.Logger.
*/
func createRecruiterLogger(recruiterNumber string, mainLogger *slog.Logger, config Config) *slog.Logger {
	logDir := config.Logger.FilePath + "/recruiterLogs/"
	if err := os.MkdirAll(logDir, 0755); err != nil {
		mainLogger.Error("Failed to create recruiter log directory", "error", err, "function", "createRecruiterLogger", "recruiter", recruiterNumber)
		return mainLogger
	}

	logFilePath := filepath.Join(logDir, fmt.Sprintf("whatsapp-bot-%s.log", recruiterNumber))
	fileWriter := &lumberjack.Logger{
		Filename:  logFilePath,
		LocalTime: true,
		MaxSize:   100,
		MaxAge:    30,
	}

	handler := slog.NewJSONHandler(io.MultiWriter(fileWriter, os.Stdout), &slog.HandlerOptions{
		Level: slog.LevelDebug,
	})

	return slog.New(handler)
}

/*
Connect initializes and connects the WhatsApp client for this manager.

Parameters:
- ctx: Context for managing cancellation.
- devicesInStore: List of devices already present in store.

Returns:
- error: If connection fails or WhatsApp client cannot be created.
*/
func (wcm *WhatsAppClientManager) Connect(ctx context.Context, devicesInStore []*store.Device) error {
	if wcm.IsConnected {
		wcm.Logger.Info("Client already connected", "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return nil
	}

	deviceStore, err := wcm.getOrCreateDeviceStore(ctx, devicesInStore)
	if err != nil {
		wcm.Logger.Error("Failed to get or create device store", "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return err
	}

	err = wcm.LoginEventHandler(ctx, deviceStore)
	if err != nil {
		return err
	}
	return nil
}

/*
asyncLogin handles the WhatsApp QR code-based login process asynchronously.

Parameters:
- ctx: Context for managing cancellation.

Returns: None.
*/
func (wcm *WhatsAppClientManager) asyncLogin(ctx context.Context) {
	go func() {
		wcm.Logger.Info("Starting authentication process", "recruiter", wcm.RecruiterConfig.RecruiterNumber)

		qrChan, _ := wcm.WhatsAppClient.GetQRChannel(ctx)
		err := wcm.WhatsAppClient.Connect()
		if err != nil {
			wcm.Logger.Error("Failed to connect WhatsApp client", "error", err, "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			panic(err)
		}

		evt := <-qrChan
		if evt.Event == "code" {
			phoneNumber := wcm.RecruiterConfig.RecruiterNumber
			clientName := "Chrome (Ubuntu)"

			if len(phoneNumber) < 10 || len(phoneNumber) > 15 {
				wcm.Logger.Error("Invalid phone number format", "phone", phoneNumber)
			}

			validClient := false
			allowed := wcm.RecruiterConfig.HostClientType
			if strings.EqualFold(clientName, allowed) {
				clientName = allowed
				validClient = true
			}

			if !validClient {
				wcm.Logger.Error("Invalid client name", "client", clientName, "allowed_clients", wcm.RecruiterConfig.HostClientType)
			}

			// wcm.RecruiterConfig.BlockedSenderIDs = append(wcm.RecruiterConfig.BlockedSenderIDs, phoneNumber)
			// wcm.Logger.Info("Updated blocked sender IDs", "blocked_senders", wcm.RecruiterConfig.BlockedSenderIDs)

			wcm.generateQRCodeInLog(evt.Code, "Initial QR Code")

			loginCode, loginErr := wcm.WhatsAppClient.PairPhone(ctx, phoneNumber, true, whatsmeow.PairClientChrome, clientName)

			if loginErr != nil {
				wcm.Logger.Error("Phone pairing failed, falling back to QR", "error", loginErr)
				for evt := range qrChan {
					if evt.Event == "code" {
						wcm.generateQRCodeInLog(evt.Code, "QR Code Retry")
					} else if evt.Event == "success" {
						wcm.Logger.Info("Login successful via QR")
						break
					} else if evt.Event == "timeout" {
						wcm.Logger.Error("QR login timeout")
						break
					}
				}
			} else {
				wcm.Logger.Info("Phone pairing successful", "login_code", loginCode)
				for evt := range qrChan {
					if evt.Event == "success" {
						wcm.Logger.Info("Login success via phone pairing")
						break
					} else if evt.Event == "timeout" {
						wcm.Logger.Error("Phone pairing timeout")
						break
					}
				}
			}
		}
	}()
}

/*
generateQRCodeInLog generates and logs the QR code for WhatsApp login.

Parameters:
- qrCode: The QR code string.
- description: Description for the QR code event.

Returns: None.
*/
func (wcm *WhatsAppClientManager) generateQRCodeInLog(qrCode string, description string) {
	logDir := wcm.config.Logger.FilePath + "/qr/"
	if err := os.MkdirAll(logDir, 0755); err != nil {
		wcm.Logger.Error("Failed to create logs directory", "function", "GenerateQRCodeInLog", "error", err)
		return
	}

	qrLogPath := filepath.Join(logDir, fmt.Sprintf("qr-code-%s.log", wcm.RecruiterConfig.RecruiterNumber))
	qrLogFile, err := os.OpenFile(qrLogPath, os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		wcm.Logger.Error("Failed to open QR log file", "function", "GenerateQRCodeInLog", "error", err)
		return
	}
	defer qrLogFile.Close()

	timestamp := fmt.Sprintf("\n=== %s - %s ===\n", description, wcm.RecruiterConfig.RecruiterNumber)
	qrLogFile.WriteString(timestamp)
	qrterminal.GenerateHalfBlock(qrCode, qrterminal.L, qrLogFile)

	wcm.Logger.Info("QR code generated", "description", description, "qr_file", qrLogPath)
}

/*
Disconnect disconnects the WhatsApp client.

Returns: None.
*/
func (wcm *WhatsAppClientManager) Disconnect() {
	if wcm.WhatsAppClient != nil && wcm.IsConnected {
		wcm.WhatsAppClient.Disconnect()
		wcm.IsConnected = false
		wcm.Logger.Info("WhatsApp client disconnected", "recruiter", wcm.RecruiterConfig.RecruiterNumber)
	}
}

/*
getOrCreateDeviceStore retrieves an existing device or creates a new one.

Parameters:
- ctx: Context.
- devices: Slice of existing devices.

Returns:
- *store.Device: Retrieved or newly created device.
- error: If device retrieval fails.
*/
func (wcm *WhatsAppClientManager) getOrCreateDeviceStore(ctx context.Context, devices []*store.Device) (*store.Device, error) {
	// wcm.Logger.Debug("Checking all devices", "devices", devices)

	for _, device := range devices {
		extractedNumber := ExtractPhoneNumber(device.ID.User)
		if device.ID != nil && extractedNumber == wcm.RecruiterConfig.RecruiterNumber {
			wcm.Logger.Info("Found existing device", "recruiter", wcm.RecruiterConfig.RecruiterNumber)
			wcm.IsConnected = true
			return wcm.Container.GetDevice(ctx, *device.ID)
		}
	}

	wcm.Logger.Info("No existing device found, creating new one", "recruiter", wcm.RecruiterConfig.RecruiterNumber)
	wcm.IsConnected = true
	return wcm.Container.NewDevice(), nil
}

/*
SetLogger sets the custom logger for WhatsAppClientManager.

Parameters:
- logger: slog.Logger instance.

Returns: None.
*/
func (wcm *WhatsAppClientManager) SetLogger(logger *slog.Logger) {
	wcm.Logger = logger
}

/*
PairPhone pairs the phone number with WhatsApp account.

Parameters:
- phoneNumber: The recruiter's phone number.
- clientName: WhatsApp client name.

Returns:
- error: If pairing fails or validations fail.
*/
func (wcm *WhatsAppClientManager) PairPhone(phoneNumber, clientName string) error {
	if wcm.WhatsAppClient == nil {
		return fmt.Errorf("WhatsApp client not initialized")
	}
	if len(phoneNumber) < 10 || len(phoneNumber) > 15 {
		return fmt.Errorf("invalid phone number format")
	}

	validClient := false
	allowed := wcm.RecruiterConfig.HostClientType
	if allowed == clientName {
		validClient = true
	}
	if !validClient {
		return fmt.Errorf("invalid client name; allowed: %v", wcm.RecruiterConfig.HostClientType)
	}

	wcm.Logger.Info("Pairing phone number", "phone", phoneNumber, "client", clientName)

	// wcm.RecruiterConfig.BlockedSenderIDs = append(wcm.RecruiterConfig.BlockedSenderIDs, phoneNumber)

	loginCode, err := wcm.WhatsAppClient.PairPhone(context.Background(), phoneNumber, true, whatsmeow.PairClientChrome, clientName)
	if err != nil {
		wcm.Logger.Error("Phone pairing failed", "error", err)
		return err
	}

	wcm.Logger.Info("Phone pairing successful", "loginCode", loginCode)
	return nil
}

/*
ExtractPhoneNumber extracts the phone number from a WhatsApp JID string.

Parameters:
- jid: JID string (format: "phone@s.whatsapp.net").

Returns:
- string: Extracted phone number.
*/
func ExtractPhoneNumber(jid string) string {
	var delimiter string
	if strings.Contains(jid, "@") {
		delimiter = "@"
	} else {
		delimiter = ":"
	}
	parts := strings.Split(jid, delimiter)
	if len(parts) > 0 {
		return parts[0]
	}
	return ""
}

// convert from 91XXXXXXXXX to JID formate 91XXXXXXXXX@s.whatsapp.net
func ConvertToJID(number string) string {
	return number + "@s.whatsapp.net"
}

func (wcm *WhatsAppClientManager) LoginEventHandler(ctx context.Context, deviceStore *store.Device) error {
	if deviceStore != nil {
		wcm.DeviceStore = deviceStore
	} else {
		wcm.DeviceStore = wcm.Container.NewDevice()
	}
	wcm.WhatsAppClient = whatsmeow.NewClient(wcm.DeviceStore, wcm.ClientLog)

	if wcm.WhatsAppClient == nil {
		wcm.Logger.Error("Failed to create WhatsApp client", "recruiter", wcm.RecruiterConfig.RecruiterNumber)
		return fmt.Errorf("failed to create WhatsApp client")
	}
	wcm.WhatsAppClient.AddEventHandler(wcm.ReceiveMessage)
	store.DeviceProps.Os = proto.String(wcm.RecruiterConfig.HostClientName)
	wcm.asyncLogin(ctx)
	wcm.IsConnected = true
	wcm.Logger.Info("WhatsApp client connected successfully", "recruiter", wcm.RecruiterConfig.RecruiterNumber)
	return nil
}

func (wcm *WhatsAppClientManager) LogoutEventHandler() {
	ctx := wcm.WhatsAppClient.BackgroundEventCtx
	if wcm.WhatsAppClient != nil && wcm.IsConnected {
		wcm.IsConnected = false
		wcm.WhatsAppClient.Logout(ctx)
		wcm.Logger.Debug("disconnecting wcm.WhatsAppClient.Logout() ")
		wcm.Logger.Info("WhatsApp client disconnected", "recruiter", wcm.RecruiterConfig.RecruiterNumber)
	}
	// Trigger the OnLogout callback
	if wcm.OnLogout != nil {
		wcm.OnLogout(wcm.RecruiterConfig.RecruiterNumber)
	}
}
