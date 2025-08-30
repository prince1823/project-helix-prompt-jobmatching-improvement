package models

import "github.com/stretchr/testify/mock"

// MockPostgresRepository moc
// ks the PostgresRepository
type MockPostgresRepository struct {
	mock.Mock
}

// GetRecruiters mocks the GetRecruiters method
func (m *MockPostgresRepository) GetRecruiters() ([]string, error) {
	args := m.Called()
	return args.Get(0).([]string), args.Error(1)
}

// GetRecruiterNumbers mocks the GetRecruiterNumbers method
func (m *MockPostgresRepository) GetRecruiterNumbers() ([]string, error) {
	args := m.Called()
	return args.Get(0).([]string), args.Error(1)
}

// IsRecruiterValid mocks the IsRecruiterValid method
func (m *MockPostgresRepository) IsRecruiterValid(recruiterNumber string) (bool, error) {
	args := m.Called(recruiterNumber)
	return args.Bool(0), args.Error(1)
}

// GetRecruiterByNumber mocks the GetRecruiterByNumber method
func (m *MockPostgresRepository) GetRecruiterByNumber(recruiterNumber string) (*RecruiterConfigDB, error) {
	args := m.Called(recruiterNumber)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	if recruiterNumber == "918496952149" {
		return &RecruiterConfigDB{
			RecruiterID:  "918496952149",
			ApplicantID:  "918050992006",
			Enabled:      true,
			MessageCount: 5,
		}, nil
	}
	return args.Get(0).(*RecruiterConfigDB), args.Error(1)
}
