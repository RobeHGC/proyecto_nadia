# Recovery & Protocol Systems Documentation

**Epic 52 - Session 4: Recovery & Protocol Systems Architecture**  
**Status**: ✅ Complete  
**Priority**: Important - System resilience  
**Documentation Date**: June 28, 2025

## Overview

The Recovery & Protocol Systems handle system resilience and message integrity in NADIA HITL. This subsystem ensures zero message loss ("Sin Dejar a Nadie Atrás") during system downtime and manages user quarantine protocols for behavioral moderation.

## Core Components

### 1. Recovery Agent (`agents/recovery_agent.py`)
**Purpose**: Zero message loss system for downtime recovery
**Dependencies**: DatabaseManager, TelegramHistoryManager, SupervisorAgent

#### Key Features
- **Comprehensive Startup Recovery**: Scans all Telegram dialogs for missed messages
- **Priority-Based Processing**: Three-tier system (TIER_1: <2h, TIER_2: 2-12h, TIER_3: 12h+)
- **Rate Limited Processing**: Telegram API compliance with semaphores
- **Temporal Context Enhancement**: Adds recovery timestamps to messages

#### Recovery Strategy
```python
# Startup Recovery Flow
1. Scan Telegram dialogs → get user IDs
2. SQL lookup → last processed message per user  
3. Gap detection → Telegram messages > SQL messages
4. Priority batching → TIER_1 processed first
5. Enhanced processing → rate limits + error handling
```

#### Rate Limiting Architecture
- **Processing Semaphore**: `max_concurrent_users` (default controlled)
- **Telegram Rate Limiter**: API compliance semaphore  
- **Enhanced Controls**: Circuit breaker pattern for error rates
- **Dynamic Delays**: Progress-based batch processing

#### Recovery Operations Tracking
- Database operation logging with `start_recovery_operation()`
- Comprehensive statistics: users scanned/checked, messages recovered/skipped
- Error tracking and operation status management

### 2. Protocol Manager (`utils/protocol_manager.py`) 
**Purpose**: PROTOCOLO DE SILENCIO quarantine system management
**Dependencies**: DatabaseManager, Redis caching

#### Key Features
- **Redis-Cached Protocol Status**: 5-minute TTL for performance
- **Real-time Quarantine Queue**: Redis sorted sets for immediate display
- **Database Persistence**: Permanent quarantine message storage
- **Event Publishing**: Real-time protocol status updates

#### Quarantine System Architecture
```python
# Quarantine Flow
1. Protocol activation → Redis cache + DB persistence
2. Message interception → queue for quarantine 
3. Redis storage → hash (data) + sorted set (queue)
4. Human review → process quarantine messages
5. Protocol deactivation → cache invalidation
```

#### Cache Management
- **Cache Keys**: `protocol_cache:{user_id}`
- **TTL Strategy**: 5-minute expiration with database fallback
- **Warm Cache**: Initialize with active protocols on startup
- **Cache Invalidation**: Manual invalidation on status changes

#### Quarantine Queue Structure
- **Items Hash**: `nadia_quarantine_items` (message data)
- **Queue Sorted Set**: `nadia_quarantine_queue` (timestamp ordering)
- **Real-time Updates**: Redis Pub/Sub for protocol events

### 3. Intermediary Agent (`agents/intermediary_agent.py`)
**Purpose**: LLM1→LLM2 bridge for coherence analysis
**Dependencies**: DatabaseManager, BaseLLMClient (LLM2)

#### Key Features
- **Commitment Integration**: Fetches active user commitments from database
- **Structured Analysis Payload**: Formats data for LLM2 coherence check
- **Static Prompt Optimization**: 75% cache hit rate for LLM2 calls
- **Conflict Detection**: Schedule conflicts and identity inconsistencies

#### Processing Pipeline
```python
# Intermediary Flow
1. LLM1 response → received from supervisor
2. Active commitments → fetch from database
3. Payload preparation → structured data for LLM2
4. LLM2 analysis → coherence check with static prompt
5. Analysis storage → save results to coherence_analysis table
6. JSON response → return for post-processing
```

#### Coherence Analysis Types
- **CONFLICTO_DE_DISPONIBILIDAD**: Scheduling conflicts with existing commitments
- **CONFLICTO_DE_IDENTIDAD**: Repetitive postponing patterns
- **Status OK**: No conflicts detected

#### LLM2 Integration
- **Temperature**: 0.1 (low for consistency)
- **Seed**: 42 (deterministic responses)
- **Prompt Caching**: Static system prompt for cache optimization
- **JSON Output**: Structured conflict analysis format

## Data Flow Architecture

### Recovery System Flow
```
System Downtime → Missed Messages → Telegram Scan → Gap Detection → 
Priority Classification → Rate-Limited Processing → Database Storage → 
Recovery Statistics
```

### Protocol System Flow  
```
User Behavior → Protocol Activation → Cache Update → Message Interception → 
Quarantine Queue → Human Review → Message Processing → Protocol Management
```

### Intermediary System Flow
```
LLM1 Response → Commitment Fetch → Payload Structure → LLM2 Analysis → 
Conflict Detection → Analysis Storage → Response Enhancement
```

## Integration Points

### With Core Message Flow
- **Recovery Agent**: Processes missed messages through SupervisorAgent
- **Protocol Manager**: Intercepts messages for quarantine before processing
- **Intermediary Agent**: Enhances LLM1 responses with coherence analysis

### With Data Storage Layer
- **Recovery Operations**: Tracked in dedicated recovery tables
- **Quarantine Messages**: Persistent storage with Redis caching
- **Coherence Analysis**: Stored in analysis tables for auditing

### With Safety & Review System
- **Protocol Integration**: Quarantine system supports human review workflow
- **Recovery Context**: Temporal context added to recovered messages
- **Analysis Results**: Coherence conflicts flagged for review

## Configuration & Controls

### Recovery Agent Configuration
```python
RecoveryConfig:
- max_concurrent_users: Processing semaphore limit
- telegram_rate_limit: API compliance rate
- max_message_age_hours: Recovery time window
- max_messages_per_user: Per-user recovery limit
```

### Protocol Manager Configuration
```python
ProtocolManager:
- CACHE_TTL: 300 seconds (5 minutes)
- QUARANTINE_QUEUE: Redis sorted set key
- QUARANTINE_ITEMS: Redis hash key
```

### Intermediary Agent Configuration
```python
IntermediaryAgent:
- temperature: 0.1 (LLM2 consistency)
- seed: 42 (deterministic responses)
- commitment_window: 2 hours (active commitments)
```

## Error Handling & Resilience

### Recovery Agent Resilience
- **Batch Error Limits**: Maximum 3 consecutive errors per batch
- **Exponential Backoff**: Error recovery with increasing delays
- **Operation Tracking**: Failed operations logged with error details
- **Circuit Breaker**: Rate limiting with error rate monitoring

### Protocol Manager Resilience
- **Redis Fallback**: Database queries on cache failures
- **Cache Warming**: Startup initialization of active protocols
- **Event Publishing**: Non-blocking protocol updates
- **Error Isolation**: Cache errors don't block protocol operations

### Intermediary Agent Resilience
- **Fallback Response**: Default OK status on analysis failures
- **Database Isolation**: Commitment fetch errors don't block processing
- **JSON Validation**: Parse error handling with fallback structures
- **Analysis Logging**: Non-critical analysis storage errors

## Performance Characteristics

### Recovery Agent Performance
- **Batch Processing**: 10 users processed concurrently
- **Rate Limiting**: Telegram API compliance (configurable)
- **Progress Tracking**: Real-time statistics and operation monitoring
- **Memory Efficient**: Streaming processing of large user sets

### Protocol Manager Performance  
- **Cache Hit Rate**: ~95% for active protocol checks
- **Queue Performance**: Redis sorted sets for O(log N) operations
- **Real-time Updates**: Sub-second protocol status changes
- **Scalable Architecture**: Redis-based caching supports high load

### Intermediary Agent Performance
- **Cache Optimization**: 75% LLM2 prompt cache hit rate
- **Database Efficiency**: Optimized commitment queries with time windows
- **Processing Speed**: Low-latency coherence analysis
- **Memory Usage**: Minimal payload structures

## Monitoring & Observability

### Recovery System Monitoring
- Recovery operation statistics (users/messages processed)
- Error rates and consecutive failure tracking
- Processing times and throughput metrics
- Telegram API rate limit compliance

### Protocol System Monitoring  
- Active protocol count and cache hit rates
- Quarantine queue size and processing times
- Protocol activation/deactivation events
- Redis connection health and performance

### Intermediary System Monitoring
- Coherence analysis success rates and conflict detection
- LLM2 response times and cache hit rates
- Commitment fetch performance and database load
- JSON parsing success rates

## Technical Debt & Improvements

### Identified Technical Debt
1. **Recovery Agent**: Manual rate limiting could use more sophisticated circuit breaker
2. **Protocol Manager**: Cache warming strategy could be more efficient
3. **Intermediary Agent**: Commitment query could benefit from better indexing

### Future Enhancements
1. **Predictive Recovery**: Proactive gap detection based on user patterns
2. **Dynamic Protocol Thresholds**: Adaptive quarantine criteria
3. **Advanced Coherence**: Multi-turn conversation coherence analysis
4. **Performance Optimization**: Enhanced caching strategies

## Security Considerations

### Recovery System Security
- **Message Integrity**: Cryptographic verification of recovered messages
- **Access Control**: Recovery operations require appropriate permissions
- **Data Privacy**: Temporal context respects user privacy requirements

### Protocol System Security
- **Authorization**: Protocol activation requires human authorization
- **Audit Trail**: Complete quarantine operation logging
- **Data Retention**: Configurable quarantine message retention

### Intermediary System Security  
- **Commitment Privacy**: User schedule data access controls
- **Analysis Integrity**: Coherence analysis immutable once stored
- **LLM Security**: Static prompts prevent injection attacks

---

**Session 4 Status**: ✅ **Complete**  
**Next Session**: Session 5 - Infrastructure & Support Systems  
**Documentation Completeness**: 100% - All recovery and protocol systems documented

**Key Findings**: 
- Robust zero-message-loss recovery system with priority-based processing
- Comprehensive quarantine system with Redis caching for performance  
- Sophisticated LLM1→LLM2 bridge with coherence analysis capabilities
- Strong resilience patterns and error handling throughout
- Well-integrated monitoring and observability features