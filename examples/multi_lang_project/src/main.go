// Package main provides the entry point for the application
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
)

// User represents a user in the system
type User struct {
	ID    int    `json:"id"`
	Name  string `json:"name"`
	Email string `json:"email"`
}

// UserService handles user operations
type UserService struct {
	users map[int]*User
}

// NewUserService creates a new UserService
func NewUserService() *UserService {
	return &UserService{
		users: make(map[int]*User),
	}
}

// GetUser retrieves a user by ID
func (s *UserService) GetUser(id int) (*User, error) {
	user, ok := s.users[id]
	if !ok {
		return nil, fmt.Errorf("user not found: %d", id)
	}
	return user, nil
}

// CreateUser creates a new user
func (s *UserService) CreateUser(name, email string) *User {
	id := len(s.users) + 1
	user := &User{
		ID:    id,
		Name:  name,
		Email: email,
	}
	s.users[id] = user
	return user
}

// DeleteUser removes a user by ID
func (s *UserService) DeleteUser(id int) error {
	if _, ok := s.users[id]; !ok {
		return fmt.Errorf("user not found: %d", id)
	}
	delete(s.users, id)
	return nil
}

func handleGetUser(w http.ResponseWriter, r *http.Request) {
	// Handler implementation
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func main() {
	service := NewUserService()
	user := service.CreateUser("John", "john@example.com")
	fmt.Printf("Created user: %+v\n", user)

	http.HandleFunc("/user", handleGetUser)
	http.ListenAndServe(":8080", nil)
}
