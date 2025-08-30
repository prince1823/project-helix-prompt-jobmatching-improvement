package models

// import (
// 	"github.com/stretchr/testify/mock"
// )

// // MockClientManager is a mock implementation of WhatsAppClientManager
// type MockClientManager struct {
// 	mock.Mock
// }

// func (m *MockClientManager) Connect() error {
// 	args := m.Called()
// 	return args.Error(0)
// }

// func (m *MockClientManager) Disconnect() error {
// 	args := m.Called()
// 	return args.Error(0)
// }

// // MockDB is a mock implementation of our database interface
// type MockDB struct {
// 	mock.Mock
// }

// func (m *MockDB) GetRecruiterConfig(recruiterNumber string) (*RecruiterConfigDB, error) {
// 	args := m.Called(recruiterNumber)
// 	if args.Get(0) == nil {
// 		return nil, args.Error(1)
// 	}
// 	return args.Get(0).(*RecruiterConfigDB), args.Error(1)
// }

// func (m *MockDB) SaveRecruiterConfig(config *RecruiterConfigDB) error {
// 	args := m.Called(config)
// 	return args.Error(0)
// }

// // MockWhatsAppClient is a mock implementation of the WhatsApp client interface
// type MockWhatsAppClient struct {
// 	mock.Mock
// }

// func (m *MockWhatsAppClient) Connect() error {
// 	args := m.Called()
// 	return args.Error(0)
// }

// func (m *MockWhatsAppClient) Disconnect() {
// 	m.Called()
// }
