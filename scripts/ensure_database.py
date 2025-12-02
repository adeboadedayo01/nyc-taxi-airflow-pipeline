#!/usr/bin/env python3
"""
Script to ensure ny_taxi database exists.
Can be run multiple times safely.
"""
import psycopg2
import sys
import os

def ensure_database():
    """Create ny_taxi database if it doesn't exist."""
    # Connection parameters
    db_params = {
        'host': os.getenv('POSTGRES_HOST', 'postgres'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'user': os.getenv('POSTGRES_USER', 'airflow'),
        'password': os.getenv('POSTGRES_PASSWORD', 'airflow'),
        'database': 'postgres'  # Connect to default database first
    }
    
    try:
        # Connect to PostgreSQL server
        conn = psycopg2.connect(**db_params)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'ny_taxi'"
        )
        exists = cursor.fetchone()
        
        if not exists:
            # Create database
            cursor.execute('CREATE DATABASE ny_taxi')
            print("Database 'ny_taxi' created successfully")
        else:
            print("Database 'ny_taxi' already exists")
        
        cursor.close()
        conn.close()
        return 0
        
    except Exception as e:
        print(f"Error ensuring database exists: {e}", file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(ensure_database())

