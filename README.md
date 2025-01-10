# Final Task (Teknologi Sistem Terintegrasi)


# 📈 Stock Market Analysis & Portfolio Management API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=flat&logo=Python&logoColor=white)](https://www.python.org)
[![Firebase](https://img.shields.io/badge/Firebase-FFCA28.svg?style=flat&logo=Firebase&logoColor=black)](https://firebase.google.com)
[![Docker](https://img.shields.io/badge/Docker-2496ED.svg?style=flat&logo=Docker&logoColor=white)](https://www.docker.com)

A robust FastAPI-based backend service for stock market analysis and portfolio management, featuring real-time stock data, portfolio optimization, and automated alerts.

## 🌟 Features

- **Real-time Stock Data**: Access current and historical IDX (Indonesia Stock Exchange) stock prices
- **Portfolio Management**: Track and analyze investment portfolios
- **Advanced Analytics**: 
  - Sharpe ratio calculations
  - Portfolio optimization using Modern Portfolio Theory
  - Time-weighted (TWR) and Money-weighted (MWR) returns
- **Automated Alerts**: Price-based notifications for stocks
- **Secure Authentication**: Firebase integration with multiple auth methods
- **Email Notifications**: Automated alerts and notifications

## 📋 Table of Contents

- [Installation](#-installation)
- [Environment Setup](#-environment-setup)
- [Docker Deployment](#-docker-deployment)
- [API Documentation](#-api-documentation)
- [Architecture](#-architecture)
- [Development Guide](#-development-guide)

## 🚀 Installation

1. Clone the repository:
```bash
git clone [your-repository-url]
cd [repository-name]
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables (see [Environment Setup](#-environment-setup))

5. Run the application:
```bash
uvicorn app.main:app --reload
```

## 🔧 Environment Setup

Create a `.env` file in the root directory with the following variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `FIREBASE_CREDENTIALS` | Path to Firebase service account JSON | `./config/firebase-service-account.json` |
| `DATABASE_URL` | SQLAlchemy database URL | `postgresql://user:password@localhost/dbname` |
| `JWT_SECRET_KEY` | Secret key for JWT tokens | `your-secret-key` |
| `SMTP_HOST` | SMTP server host | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USERNAME` | SMTP authentication username | `your-email@gmail.com` |
| `SMTP_PASSWORD` | SMTP authentication password | `your-app-password` |

## 🐳 Docker Deployment

1. Build the Docker image:
```bash
docker build -t stock-market-api .
```

2. Run with Docker Compose:
```bash
docker-compose up -d
```

## 📚 API Documentation

### Public Routes (/api/public)

<details>
<summary><b>GET /api/public/companies/symbols</b> - Get all IDX stock symbols</summary>

#### Response
```json
{
  "symbols": ["BBCA", "TLKM", ...],
  "count": 750
}
```
</details>

<details>
<summary><b>GET /api/public/companies/{symbol}</b> - Get company information</summary>

#### Parameters
- `symbol`: Stock symbol (e.g., "BBCA")

#### Response
```json
{
  "symbol": "BBCA",
  "company_name": "Bank Central Asia Tbk",
  "sector": "Financial Services",
  "industry": "Banking",
  "market_cap": 1234567890,
  "description": "Company description..."
}
```
</details>

### Secure Routes (/api/secure)

<details>
<summary><b>GET /api/secure/stock-price/{stock_code}/{date_range}</b> - Get historical stock prices</summary>

#### Parameters
- `stock_code`: Stock symbol
- `date_range`: Date range in format "YYYY-MM-DD_YYYY-MM-DD"

#### Response
```json
{
  "symbol": "BBCA.JK",
  "prices": [
    {
      "date": "2024-01-10",
      "closing_price": 9450,
      "volume_thousands": 15678
    },
    ...
  ]
}
```
</details>

<details>
<summary><b>GET /api/secure/sharpe-ratio/{stock_code}</b> - Calculate Sharpe ratio</summary>

#### Parameters
- `stock_code`: Stock symbol

#### Response
```json
{
  "stock_code": "BBCA",
  "sharpe_ratio": 1.234,
  "avg_annual_return": 0.156,
  "return_volatility": 0.089,
  "risk_free_rate": 0.055
}
```
</details>

<details>
<summary><b>POST /api/secure/optimize-portfolio</b> - Optimize portfolio weights</summary>

#### Request
```json
{
  "stock_codes": ["BBCA", "TLKM", "UNVR"],
  "target_return": 0.15
}
```

#### Response
```json
{
  "allocations": [
    {
      "stock_code": "BBCA",
      "weight": 0.4
    },
    ...
  ],
  "expected_return": 0.15,
  "expected_volatility": 0.12,
  "sharpe_ratio": 1.45
}
```
</details>

<details>
<summary><b>POST /api/secure/send-email</b> - Send email notification</summary>

#### Request
```json
{
  "recipient_email": "user@example.com",
  "subject": "Stock Alert",
  "body": "Your stock alert message..."
}
```

#### Response
```json
{
  "success": true,
  "message": "Email sent successfully"
}
```
</details>

### Internal Routes (/api/internal)

<details>
<summary><b>POST /api/internal/generate-api-key</b> - Generate API key</summary>

#### Request
```json
{
  "full_name": "John Doe",
  "application_name": "Trading App",
  "organization": "Example Corp",
  "email": "john@example.com",
  "phone_number": "+1234567890"
}
```

#### Response
```json
{
  "api_key": "sk_test_abc123...",
  "full_name": "John Doe",
  ...
}
```
</details>

<details>
<summary><b>POST /api/internal/transactions</b> - Record stock transaction</summary>

#### Request
```json
{
  "stock_code": "BBCA",
  "transaction_type": "buy",
  "quantity": 100,
  "transaction_date": "2024-01-10T14:30:00Z",
  "token": "firebase_id_token"
}
```

#### Response
```json
{
  "id": "tx_123",
  "stock_code": "BBCA",
  "quantity": 100,
  "price_per_share": 9450,
  "total_value": 945000,
  ...
}
```
</details>

<details>
<summary><b>POST /api/internal/alerts</b> - Create price alert</summary>

#### Request
```json
{
  "stock_code": "BBCA",
  "trigger_price": 9500,
  "trigger_type": "above",
  "notification_hour": 9,
  "is_repeating": true,
  "token": "firebase_id_token"
}
```

#### Response
```json
{
  "id": "alert_123",
  "stock_code": "BBCA",
  "trigger_price": 9500,
  ...
}
```
</details>

### Authentication Routes (/api/auth)

<details>
<summary><b>POST /api/auth/token</b> - Get JWT token</summary>

#### Request
Requires API key authentication via header

#### Response
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiL...",
  "token_type": "bearer"
}
```
</details>

## 🏗 Architecture

```
app/
├── api/                    # API routes
│   ├── auth/              # Authentication endpoints
│   ├── internal/          # Internal endpoints
│   ├── public/            # Public endpoints
│   └── secure/            # Secure endpoints
├── config/                # Configuration
├── core/                  # Core functionality
├── db/                    # Database
└── models/                # Data models
```

### Key Components

- **FastAPI**: Web framework for building APIs
- **SQLAlchemy**: ORM for database operations
- **Firebase Admin**: Authentication and user management
- **yfinance**: Real-time stock data
- **NumPy/SciPy**: Mathematical computations
- **Pydantic**: Data validation

## 👨‍💻 Development Guide

### Security Best Practices

- All secure endpoints require authentication
- API keys are hashed before storage
- Regular security audits
- Rate limiting on public endpoints