# NADIA - Human-in-the-Loop Conversational AI

Nadia is a conversational AI system designed for English-speaking users that implements Human-in-the-Loop (HITL) review. The bot presents as a friendly, flirty 24-year-old American woman chatting on Telegram. All AI responses go through human review before being sent to users, with the goal of collecting high-quality training data.

## 🎯 Key Features

- **Dual-LLM Pipeline**: Creative generation + refinement for natural conversations
- **Human Review System**: All messages reviewed before sending via web dashboard
- **CTA Support**: Manual insertion of call-to-action messages during review
- **Constitution Filter**: AI safety layer that analyzes content without blocking
- **Data Collection**: Comprehensive tracking for training data generation
- **English US Persona**: Casual American texting style with natural emojis

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Redis
- Telegram Bot Token and API credentials
- OpenAI API key

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd chatbot_nadia

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Setup

Create a `.env` file with the following variables:

```bash
# Telegram Credentials
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
PHONE_NUMBER=your_phone_number

# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Database & Redis
DATABASE_URL=postgresql://username:password@localhost/nadia_hitl
REDIS_URL=redis://localhost:6379/0

# Security
DASHBOARD_API_KEY=your_secure_api_key_here

# Optional
API_PORT=8000
```

### 3. Database Setup

```bash
# Create database
createdb nadia_hitl

# Apply schema
psql -d nadia_hitl -f DATABASE_SCHEMA.sql

# Apply CTA migration
psql -d nadia_hitl -f database/migrations/add_cta_support.sql
```

### 4. Running the System

The system requires three components running simultaneously:

```bash
# Terminal 1: API Server (port 8000)
PYTHONPATH=/home/rober/projects/chatbot_nadia python -m api.server

# Terminal 2: Dashboard (port 3000)
python dashboard/backend/static_server.py

# Terminal 3: Telegram Bot
python userbot.py
```

### 5. Access the Dashboard

Open your browser to `http://localhost:3000` to access the human review dashboard.

## 📋 Usage Workflow

1. **Send messages** to your Telegram bot
2. **Messages are processed** through the dual-LLM pipeline
3. **Review messages** appear in the dashboard at `http://localhost:3000`
4. **Edit and approve** messages, optionally inserting CTAs
5. **Approved messages** are sent to users automatically
6. **Training data** is saved to PostgreSQL for analysis

## 🛠️ Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific HITL tests
pytest tests/test_hitl_constitution.py
pytest tests/test_hitl_supervisor.py
pytest tests/test_hitl_api.py
pytest tests/test_hitl_database.py

# Run with async support
pytest --asyncio-mode=auto
```

### Code Quality

```bash
# Lint code
ruff check .

# Format code
ruff format .
```

### Project Structure

```
├── agents/              # AI agents and orchestration
├── api/                 # FastAPI server for dashboard
├── cognition/           # Constitution safety filter
├── dashboard/           # Web interface for human review
├── database/            # PostgreSQL models and migrations
├── docs/                # Documentation and taxonomies
├── llms/                # OpenAI client wrapper
├── memory/              # User context management
├── tests/               # Test suite
├── utils/               # Configuration and utilities
└── userbot.py          # Main Telegram bot entry point
```

## 🎯 CTA (Call-to-Action) Features

The dashboard supports inserting CTAs during human review:

- **Soft CTAs**: "btw i have some pics i can't send here 🙈"
- **Medium CTAs**: "i have exclusive content elsewhere 👀"  
- **Direct CTAs**: "check out my Fanvue for more content 💕"

CTAs are tracked in the database for training analysis.

## 🔍 Monitoring

### Health Check
```bash
curl http://localhost:8000/health
```

### Database Queries
```sql
-- Check pending reviews
SELECT COUNT(*) FROM interactions WHERE review_status = 'pending';

-- Check CTA insertions
SELECT cta_data->>'type', COUNT(*) 
FROM interactions 
WHERE cta_data IS NOT NULL 
GROUP BY 1;
```

## 📊 Analytics

The system includes built-in analytics for CTA performance and review metrics:

```python
from analytics.cta_analytics import CTAAnalytics

# Get CTA metrics
metrics = await CTAAnalytics.get_cta_metrics(db_conn)

# Export training data
training_data = await CTAAnalytics.export_cta_training_data(db_conn)
```

## 🛡️ Security & Privacy

### API Security
- **Authentication**: Bearer token authentication for all dashboard endpoints
- **Rate Limiting**: Comprehensive rate limits (5-60 requests/minute based on endpoint)
- **Input Validation**: Pydantic models with field constraints and HTML escaping
- **CORS**: Restricted to specific allowed origins (no wildcards)

### Data Protection
- **Constitution Filter**: Analyzes all responses for safety without blocking
- **GDPR Compliance**: User data deletion endpoints
- **Privacy Logging**: Truncated logs for sensitive content
- **Review Tracking**: Complete audit trail of human edits
- **Input Sanitization**: HTML escaping for user-provided content

### Environment Variables
Set a strong API key in production:
```bash
DASHBOARD_API_KEY=your_very_secure_random_key_here
ALLOWED_ORIGINS=https://yourdomain.com,https://dashboard.yourdomain.com
```

## 📚 Documentation

- `CLAUDE.md` - Development guidance for Claude Code
- `docs/ENGLISH_US_MIGRATION_SUMMARY.md` - Migration details
- `docs/CTA_FEATURE_GUIDE.md` - CTA functionality guide
- `ARCHITECTURE.md` - Technical architecture overview

## 🐛 Troubleshooting

### Common Issues

1. **Database connection errors**: Ensure PostgreSQL is running and credentials are correct
2. **Redis connection errors**: Ensure Redis is running on the specified port
3. **Telegram authentication**: Verify API credentials and phone number
4. **OpenAI API errors**: Check API key and rate limits

### Logs

Check logs for debugging:
- API server logs in terminal
- Telegram bot logs in terminal
- Dashboard logs in browser console

## 🤝 Contributing

1. Follow the existing code style (enforced by ruff)
2. Add tests for new functionality
3. Update documentation as needed
4. Ensure all tests pass before submitting