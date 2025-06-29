#!/usr/bin/env python3
"""
Script to migrate Nadia's biographical knowledge documents to MongoDB.
This script loads all biographical documents from knowledge_documents/
and stores them in MongoDB with embeddings for RAG system.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge.mongodb_manager import MongoDBManager, KnowledgeDocument
from knowledge.local_embeddings_service import get_local_embeddings_service
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BiographyMigrator:
    """Migrates Nadia's biographical documents to MongoDB."""
    
    def __init__(self, mongodb_url: str = "mongodb://localhost:27017"):
        """Initialize the migrator."""
        self.mongodb_url = mongodb_url
        self.mongodb_manager = None
        self.embeddings_service = None
        self.knowledge_docs_path = Path(__file__).parent.parent / "knowledge_documents"
        
        # Document mapping
        self.document_categories = {
            "nadia_biografia_familiar.md": "family",
            "nadia_vida_estudiantil.md": "education", 
            "nadia_personalidad_hobbies.md": "personality",
            "nadia_fanvue_backstory.md": "backstory",
            "nadia_austin_texas.md": "travel",
            "nadia_monterrey_montanismo.md": "hobbies",
            "nadia_conocimiento_medico.md": "medical_knowledge"
        }
    
    async def initialize(self):
        """Initialize MongoDB and embeddings service."""
        logger.info("Initializing services...")
        
        # Initialize MongoDB
        self.mongodb_manager = MongoDBManager(self.mongodb_url)
        if not await self.mongodb_manager.connect():
            raise ConnectionError("Failed to connect to MongoDB")
        
        # Initialize local embeddings service
        self.embeddings_service = get_local_embeddings_service()
        
        logger.info("Services initialized successfully")
    
    async def load_document(self, file_path: Path) -> Dict[str, Any]:
        """Load a single biographical document."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title from first line if it's a header
            lines = content.split('\n')
            title = lines[0].strip('#').strip() if lines[0].startswith('#') else file_path.stem
            
            return {
                "filename": file_path.name,
                "title": title,
                "content": content,
                "category": self.document_categories.get(file_path.name, "general"),
                "source": "nadia_biography"
            }
            
        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {e}")
            return None
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using local embeddings service."""
        try:
            embedding_result = await self.embeddings_service.get_embedding(text)
            if embedding_result and embedding_result.embedding:
                return embedding_result.embedding
            else:
                logger.warning(f"Failed to generate embedding for text: {text[:100]}...")
                return None
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    async def migrate_document(self, doc_data: Dict[str, Any]) -> bool:
        """Migrate a single document to MongoDB."""
        try:
            # Generate embedding for the content
            logger.info(f"Generating embedding for {doc_data['filename']}...")
            embedding = await self.generate_embedding(doc_data['content'])
            
            if not embedding:
                logger.warning(f"Skipping {doc_data['filename']} - no embedding generated")
                return False
            
            # Create knowledge document
            knowledge_doc = KnowledgeDocument(
                id=f"nadia_bio_{doc_data['filename'].replace('.md', '')}",
                title=doc_data['title'],
                content=doc_data['content'],
                source=doc_data['source'],
                category=doc_data['category'],
                embedding=embedding,
                metadata={
                    "filename": doc_data['filename'],
                    "content_length": len(doc_data['content']),
                    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                    "migration_date": datetime.now().isoformat()
                },
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Store in MongoDB
            success = await self.mongodb_manager.store_knowledge_document(knowledge_doc)
            if success:
                logger.info(f"✅ Migrated {doc_data['filename']} to MongoDB")
            else:
                logger.error(f"❌ Failed to migrate {doc_data['filename']}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error migrating document {doc_data['filename']}: {e}")
            return False
    
    async def migrate_all_documents(self) -> Dict[str, Any]:
        """Migrate all biographical documents to MongoDB."""
        logger.info("Starting migration of all biographical documents...")
        
        results = {
            "total_documents": 0,
            "successful_migrations": 0,
            "failed_migrations": 0,
            "documents_processed": []
        }
        
        # Find all markdown files in knowledge_documents directory
        md_files = list(self.knowledge_docs_path.glob("*.md"))
        results["total_documents"] = len(md_files)
        
        logger.info(f"Found {len(md_files)} biographical documents to migrate")
        
        for file_path in md_files:
            logger.info(f"Processing {file_path.name}...")
            
            # Load document
            doc_data = await self.load_document(file_path)
            if not doc_data:
                results["failed_migrations"] += 1
                results["documents_processed"].append({
                    "filename": file_path.name,
                    "status": "failed_to_load"
                })
                continue
            
            # Migrate document
            success = await self.migrate_document(doc_data)
            if success:
                results["successful_migrations"] += 1
                results["documents_processed"].append({
                    "filename": file_path.name,
                    "status": "success",
                    "category": doc_data["category"]
                })
            else:
                results["failed_migrations"] += 1
                results["documents_processed"].append({
                    "filename": file_path.name,
                    "status": "failed_to_migrate"
                })
        
        return results
    
    async def verify_migration(self) -> Dict[str, Any]:
        """Verify that documents were migrated correctly."""
        logger.info("Verifying migration...")
        
        stats = await self.mongodb_manager.get_collection_stats()
        
        # Search for biographical documents
        bio_docs = await self.mongodb_manager.search_knowledge_documents(
            category="family",
            limit=10
        )
        
        verification = {
            "mongodb_stats": stats,
            "sample_documents_found": len(bio_docs),
            "verification_status": "success" if stats.get("knowledge_documents", 0) > 0 else "failed"
        }
        
        logger.info(f"Verification results: {verification}")
        return verification
    
    async def close(self):
        """Close connections."""
        if self.mongodb_manager:
            await self.mongodb_manager.close()


async def main():
    """Main migration function."""
    logger.info("🚀 Starting Nadia Biography Migration to MongoDB")
    
    # Check if MongoDB URL is provided
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    logger.info(f"Using MongoDB URL: {mongodb_url}")
    
    migrator = BiographyMigrator(mongodb_url)
    
    try:
        # Initialize services
        await migrator.initialize()
        
        # Migrate all documents
        results = await migrator.migrate_all_documents()
        
        # Print results
        logger.info("📊 Migration Results:")
        logger.info(f"   Total documents: {results['total_documents']}")
        logger.info(f"   Successful: {results['successful_migrations']}")
        logger.info(f"   Failed: {results['failed_migrations']}")
        
        # Verify migration
        verification = await migrator.verify_migration()
        
        if results['successful_migrations'] > 0:
            logger.info("✅ Migration completed successfully!")
            logger.info("🔍 Documents are now available for RAG system")
        else:
            logger.warning("⚠️  No documents were migrated successfully")
        
        return results['successful_migrations'] > 0
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False
    
    finally:
        await migrator.close()


if __name__ == "__main__":
    # Set MongoDB URL if not in environment
    if not os.getenv("MONGODB_URL"):
        os.environ["MONGODB_URL"] = "mongodb://localhost:27017"
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)