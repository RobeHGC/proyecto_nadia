# NADIA RAG System Installation Guide

## Overview

This guide explains how to install and configure the RAG (Retrieval-Augmented Generation) system for NADIA, which enhances the bot's responses with knowledge base integration and user learning capabilities.

## Prerequisites

- NADIA base system already installed and working
- Python 3.8+ with pip
- MongoDB 4.4+ (local or cloud)
- OpenAI API key for embeddings

## Installation Steps

### 1. Install RAG Dependencies

```bash
# Install MongoDB and vector processing dependencies
pip install -r requirements-rag.txt

# Or install individually:
pip install motor>=3.0.0 pymongo>=4.0.0 numpy>=1.21.0 openai>=1.0.0
```

### 2. MongoDB Setup

#### Option A: Local MongoDB
```bash
# Install MongoDB (Ubuntu/Debian)
sudo apt update
sudo apt install -y mongodb

# Start MongoDB service
sudo systemctl start mongodb
sudo systemctl enable mongodb

# Create NADIA database
mongo
> use nadia_knowledge
> db.createUser({user: "nadia_user", pwd: "secure_password", roles: ["readWrite"]})
> exit
```

#### Option B: MongoDB Atlas (Cloud)
1. Create account at https://cloud.mongodb.com
2. Create a new cluster
3. Get connection string
4. Set environment variable: `MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/nadia_knowledge`

### 3. Environment Configuration

Add these variables to your `.env` file:

```bash
# RAG System Configuration
MONGODB_URL=mongodb://localhost:27017/nadia_knowledge
MONGODB_DATABASE=nadia_knowledge

# OpenAI for embeddings (can reuse existing key)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Optional: Advanced settings
RAG_CONFIDENCE_THRESHOLD=0.3
RAG_MAX_DOCUMENTS=3
RAG_CONTEXT_LENGTH=2000
```

### 4. Initialize RAG Collections

Run the initialization script:

```bash
# Create MongoDB collections and indexes
python -c "
import asyncio
from knowledge.mongodb_manager import get_mongodb_manager

async def init():
    manager = await get_mongodb_manager()
    print('RAG collections initialized successfully!')

asyncio.run(init())
"
```

### 5. Verify Installation

```bash
# Test RAG system health
curl -H 'Authorization: Bearer your-api-key' http://localhost:8000/api/knowledge/health

# Expected response:
# {
#   "rag_available": true,
#   "mongodb_connected": true,
#   "embeddings_service": true,
#   "vector_search": true,
#   "status": "healthy"
# }
```

## Usage

### 1. Access Knowledge Management

Open the dashboard and click "🧠 Knowledge RAG" to access:
- **Upload Knowledge**: Add documents to the knowledge base
- **Search Knowledge**: Test semantic search functionality
- **User Learning**: Manage user preferences and interests
- **Statistics**: View system stats and usage

### 2. Upload Sample Knowledge

```bash
# Upload personality knowledge via API
curl -X POST http://localhost:8000/api/knowledge/documents \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "NADIA Personality Traits",
    "content": "NADIA is a friendly 24-year-old medical student from Monterrey. She loves hiking, cooking, and helping people. She uses casual American English with Texas influences.",
    "source": "Personality Manual",
    "category": "personality"
  }'
```

### 3. Test Enhanced Responses

1. Send a message through Telegram
2. Check the logs for RAG enhancement messages:
   ```
   INFO - RAG enhanced prompt with confidence 0.85
   DEBUG - Stored RAG interaction for user 12345
   ```
3. Review enhanced responses in the dashboard

## Architecture Integration

### Enhanced Message Flow

```
Telegram Message
       ↓
   UserBot receives
       ↓
   RAG Context Retrieval
   ├── Search knowledge base
   ├── Get user preferences  
   └── Find similar conversations
       ↓
   LLM1 (Enhanced Prompt)
       ↓
   LLM2 (Refinement)
       ↓
   Human Review
       ↓
   Store for Learning
```

### Data Flow

1. **Knowledge Storage**: Documents → Embeddings → MongoDB
2. **Context Retrieval**: User message → Semantic search → Relevant knowledge
3. **Prompt Enhancement**: Original prompt + Context → Enhanced prompt
4. **Learning Loop**: User interaction → Embedding → Future context

## Configuration Options

### RAG Manager Settings

```python
# In knowledge/rag_manager.py, modify config:
self.config = {
    "max_context_length": 2000,      # Max chars for context injection
    "min_similarity_threshold": 0.7,  # Min similarity for relevance
    "max_documents": 3,               # Max docs per context
    "include_conversation_history": True,
    "include_user_preferences": True,
    "context_weight": 0.3
}
```

### Embeddings Service

```python
# Uses OpenAI text-embedding-3-small by default
# Cost: ~$0.00002 per 1000 tokens
# Dimension: 1536
```

## Monitoring and Maintenance

### 1. Check System Stats

```bash
# View RAG statistics
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8000/api/knowledge/stats
```

### 2. Monitor Usage

```bash
# Check MongoDB collection sizes
mongo nadia_knowledge --eval "
db.knowledge_documents.countDocuments();
db.user_preferences.countDocuments();
db.conversation_embeddings.countDocuments();
"
```

### 3. Clean Old Data

```bash
# Clean conversation embeddings older than 30 days
python -c "
import asyncio
from memory.enhanced_user_memory import create_enhanced_memory_manager

async def cleanup():
    manager = await create_enhanced_memory_manager()
    result = await manager.cleanup_old_persistent_data(days_to_keep=30)
    print(f'Cleaned up {result[\"deleted_embeddings\"]} old embeddings')

asyncio.run(cleanup())
"
```

## Troubleshooting

### RAG System Not Available

```
ERROR - RAG system not available - continuing without knowledge enhancement
```

**Solution**: Install missing dependencies
```bash
pip install motor pymongo numpy openai
```

### MongoDB Connection Failed

```
ERROR - Failed to connect to MongoDB: connection refused
```

**Solutions**:
1. Check MongoDB is running: `sudo systemctl status mongodb`
2. Verify connection string in environment variables
3. Check firewall/network settings

### Embeddings Service Errors

```
ERROR - OpenAI API error for embedding: invalid API key
```

**Solution**: Verify OpenAI API key in environment variables

### Low Confidence Scores

```
DEBUG - RAG context not confident enough, using original message
```

**Solutions**:
1. Add more relevant knowledge documents
2. Lower confidence threshold in configuration
3. Improve document content quality

## Performance Tuning

### 1. Embedding Cache

- Default cache size: 1000 embeddings
- Adjust in `embeddings_service.py`: `self._cache_max_size = 2000`

### 2. MongoDB Indexing

```javascript
// Create additional indexes for better performance
db.knowledge_documents.createIndex({"title": "text", "content": "text"})
db.conversation_embeddings.createIndex({"user_id": 1, "created_at": -1})
```

### 3. Memory Usage

- Monitor embedding cache size via `/api/knowledge/stats`
- Consider using external vector database for large deployments

## Security Considerations

1. **API Access**: RAG endpoints use same authentication as main API
2. **Data Privacy**: User conversations are embedded for learning but can be configured to exclude sensitive data
3. **MongoDB Security**: Use authentication and encryption in production
4. **Knowledge Base**: Review uploaded documents for sensitive information

## Next Steps

1. **Customize Knowledge**: Upload domain-specific documents
2. **Monitor Usage**: Track which knowledge gets retrieved most
3. **Optimize Prompts**: Adjust RAG enhancement based on response quality
4. **Scale Storage**: Consider vector databases for large knowledge bases

## Support

For issues with the RAG system:
1. Check logs for specific error messages
2. Verify all dependencies are installed
3. Test MongoDB connectivity separately
4. Check OpenAI API quota and usage

The RAG system is designed to be optional and non-disruptive - if it fails, NADIA will continue working with the original functionality.