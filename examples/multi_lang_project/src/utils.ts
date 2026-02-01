/**
 * TypeScript utility functions
 */

export interface User {
    id: number;
    name: string;
    email: string;
}

export function formatDate(date: Date): string {
    return date.toISOString().split('T')[0];
}

export async function fetchUser(id: number): Promise<User> {
    const response = await fetch(`/api/users/${id}`);
    return response.json();
}

export class UserService {
    private baseUrl: string;

    constructor(baseUrl: string) {
        this.baseUrl = baseUrl;
    }

    async getUser(id: number): Promise<User> {
        const response = await fetch(`${this.baseUrl}/users/${id}`);
        return response.json();
    }

    async createUser(user: Omit<User, 'id'>): Promise<User> {
        const response = await fetch(`${this.baseUrl}/users`, {
            method: 'POST',
            body: JSON.stringify(user),
        });
        return response.json();
    }
}
