package com.example.demo;

import java.util.List;
import java.util.ArrayList;
import java.util.Optional;

/**
 * User entity class
 */
public class User {
    private Long id;
    private String name;
    private String email;

    public User(Long id, String name, String email) {
        this.id = id;
        this.name = name;
        this.email = email;
    }

    public Long getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getEmail() {
        return email;
    }

    public void setName(String name) {
        this.name = name;
    }

    public void setEmail(String email) {
        this.email = email;
    }
}

/**
 * User service for business logic
 */
class UserService {
    private List<User> users = new ArrayList<>();
    private Long nextId = 1L;

    public User createUser(String name, String email) {
        User user = new User(nextId++, name, email);
        users.add(user);
        return user;
    }

    public Optional<User> findById(Long id) {
        return users.stream()
            .filter(u -> u.getId().equals(id))
            .findFirst();
    }

    public List<User> findAll() {
        return new ArrayList<>(users);
    }

    public void deleteUser(Long id) {
        users.removeIf(u -> u.getId().equals(id));
    }
}

/**
 * REST Controller for user operations
 */
class UserController {
    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    public List<User> getAllUsers() {
        return userService.findAll();
    }

    public User getUser(Long id) {
        return userService.findById(id)
            .orElseThrow(() -> new RuntimeException("User not found"));
    }

    public User createUser(String name, String email) {
        return userService.createUser(name, email);
    }

    public void deleteUser(Long id) {
        userService.deleteUser(id);
    }
}
