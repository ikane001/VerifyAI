"""Python Flask application for multi-language project demo."""

from dataclasses import dataclass
from typing import Optional
from flask import Flask, jsonify, request


@dataclass
class User:
    """User model."""
    id: int
    name: str
    email: str


class UserRepository:
    """Repository for user data access."""

    def __init__(self):
        self._users: dict[int, User] = {}
        self._next_id = 1

    def create(self, name: str, email: str) -> User:
        """Create a new user."""
        user = User(id=self._next_id, name=name, email=email)
        self._users[self._next_id] = user
        self._next_id += 1
        return user

    def find_by_id(self, user_id: int) -> Optional[User]:
        """Find user by ID."""
        return self._users.get(user_id)

    def find_all(self) -> list[User]:
        """Get all users."""
        return list(self._users.values())

    def delete(self, user_id: int) -> bool:
        """Delete a user."""
        if user_id in self._users:
            del self._users[user_id]
            return True
        return False


def create_app() -> Flask:
    """Create Flask application."""
    app = Flask(__name__)
    repo = UserRepository()

    @app.route('/users', methods=['GET'])
    def get_users():
        users = repo.find_all()
        return jsonify([{'id': u.id, 'name': u.name, 'email': u.email} for u in users])

    @app.route('/users/<int:user_id>', methods=['GET'])
    def get_user(user_id: int):
        user = repo.find_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify({'id': user.id, 'name': user.name, 'email': user.email})

    @app.route('/users', methods=['POST'])
    def create_user():
        data = request.json
        user = repo.create(data['name'], data['email'])
        return jsonify({'id': user.id, 'name': user.name, 'email': user.email}), 201

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
