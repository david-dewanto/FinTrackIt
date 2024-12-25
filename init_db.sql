-- init_db.sql

-- Create the database if it doesn't exist
CREATE DATABASE auth_service;

-- Connect to the database
\c auth_service

-- Create extension for UUID generation if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create API keys table with extended information
CREATE TABLE api_keys (
    key_hash VARCHAR(255) PRIMARY KEY,  -- Stores the hashed API key
    
    -- User Information
    application_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20),
    organization_name VARCHAR(255),
    
    -- System Fields
    is_internal BOOLEAN DEFAULT FALSE,   -- Distinguishes between internal and external keys
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP WITH TIME ZONE,  -- Tracks the last usage of the key
    description TEXT,                    -- Optional description of what the key is used for
    status VARCHAR(50) DEFAULT 'active',  -- Key status (active, revoked, expired)
    request_count BIGINT DEFAULT 0       -- Track number of requests made
);

-- Create indexes for faster queries
CREATE INDEX idx_api_keys_is_internal ON api_keys(is_internal);
CREATE INDEX idx_api_keys_status ON api_keys(status);
CREATE INDEX idx_api_keys_email ON api_keys(email);
CREATE INDEX idx_api_keys_application ON api_keys(application_name);
CREATE INDEX idx_api_keys_organization ON api_keys(organization_name);

-- Create audit log table for key usage (keeping existing structure)
CREATE TABLE key_usage_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    key_hash VARCHAR(255) REFERENCES api_keys(key_hash),
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),  -- Supports both IPv4 and IPv6
    endpoint VARCHAR(255),   -- The endpoint that was accessed
    success BOOLEAN         -- Whether the authentication was successful
);

-- Create index for faster log queries
CREATE INDEX idx_key_usage_logs_key_hash ON key_usage_logs(key_hash);
CREATE INDEX idx_key_usage_logs_accessed_at ON key_usage_logs(accessed_at);