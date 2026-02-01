"""User service module for demonstration."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import re


@dataclass
class User:
    """User data model."""

    id: int
    username: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


class ValidationError(Exception):
    """Validation error."""
    pass


class UserNotFoundError(Exception):
    """User not found error."""
    pass


def validate_email(email: str) -> bool:
    """Validate email format.

    Args:
        email: Email address to validate

    Returns:
        True if email is valid

    Raises:
        ValidationError: If email format is invalid
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email format: {email}")
    return True


def validate_username(username: str) -> bool:
    """Validate username.

    Args:
        username: Username to validate

    Returns:
        True if username is valid

    Raises:
        ValidationError: If username is invalid
    """
    if len(username) < 3:
        raise ValidationError("Username must be at least 3 characters")
    if len(username) > 50:
        raise ValidationError("Username must be at most 50 characters")
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        raise ValidationError("Username can only contain letters, numbers, and underscores")
    return True


class UserService:
    """Service for managing users."""

    def __init__(self):
        """Initialize user service."""
        self._users: dict[int, User] = {}
        self._next_id = 1

    def create_user(self, username: str, email: str) -> User:
        """Create a new user.

        Args:
            username: User's username
            email: User's email address

        Returns:
            Created user

        Raises:
            ValidationError: If username or email is invalid
        """
        validate_username(username)
        validate_email(email)

        # Check for duplicate username or email
        for user in self._users.values():
            if user.username == username:
                raise ValidationError(f"Username already exists: {username}")
            if user.email == email:
                raise ValidationError(f"Email already exists: {email}")

        user = User(
            id=self._next_id,
            username=username,
            email=email,
        )
        self._users[user.id] = user
        self._next_id += 1
        return user

    def get_user(self, user_id: int) -> User:
        """Get user by ID.

        Args:
            user_id: User's ID

        Returns:
            User with the given ID

        Raises:
            UserNotFoundError: If user is not found
        """
        if user_id not in self._users:
            raise UserNotFoundError(f"User not found: {user_id}")
        return self._users[user_id]

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username.

        Args:
            username: User's username

        Returns:
            User with the given username, or None if not found
        """
        for user in self._users.values():
            if user.username == username:
                return user
        return None

    def update_user(self, user_id: int, username: str | None = None, email: str | None = None) -> User:
        """Update user information.

        Args:
            user_id: User's ID
            username: New username (optional)
            email: New email (optional)

        Returns:
            Updated user

        Raises:
            UserNotFoundError: If user is not found
            ValidationError: If username or email is invalid
        """
        user = self.get_user(user_id)

        if username is not None:
            validate_username(username)
            # Check for duplicate
            existing = self.get_user_by_username(username)
            if existing and existing.id != user_id:
                raise ValidationError(f"Username already exists: {username}")
            user.username = username

        if email is not None:
            validate_email(email)
            # Check for duplicate
            for u in self._users.values():
                if u.email == email and u.id != user_id:
                    raise ValidationError(f"Email already exists: {email}")
            user.email = email

        return user

    def delete_user(self, user_id: int) -> bool:
        """Delete a user.

        Args:
            user_id: User's ID

        Returns:
            True if user was deleted

        Raises:
            UserNotFoundError: If user is not found
        """
        if user_id not in self._users:
            raise UserNotFoundError(f"User not found: {user_id}")
        del self._users[user_id]
        return True

    def list_users(self, active_only: bool = False) -> list[User]:
        """List all users.

        Args:
            active_only: If True, only return active users

        Returns:
            List of users
        """
        users = list(self._users.values())
        if active_only:
            users = [u for u in users if u.is_active]
        return users

    def deactivate_user(self, user_id: int) -> User:
        """Deactivate a user.

        Args:
            user_id: User's ID

        Returns:
            Deactivated user

        Raises:
            UserNotFoundError: If user is not found
        """
        user = self.get_user(user_id)
        user.is_active = False
        return user
