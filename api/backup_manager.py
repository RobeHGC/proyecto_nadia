# api/backup_manager.py
"""Backup and restore functionality for NADIA database."""
import asyncio
import gzip
import json
import logging
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import asyncpg
from utils.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self):
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.config = Config.from_env()
        self.database_url = self.config.database_url

    async def create_backup(self, name: str, include_data: bool = True, compress: bool = True) -> Dict[str, Any]:
        """Create a database backup."""
        try:
            backup_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"{name}_{timestamp}_{backup_id[:8]}"
            
            if compress:
                filename += ".sql.gz"
                backup_path = self.backup_dir / filename
            else:
                filename += ".sql"
                backup_path = self.backup_dir / filename
            
            # Parse database URL
            db_config = self._parse_database_url()
            
            # Build pg_dump command
            dump_cmd = [
                "pg_dump",
                "-h", db_config["host"],
                "-p", str(db_config["port"]),
                "-U", db_config["user"],
                "-d", db_config["database"],
                "-v",
                "--clean",
                "--if-exists"
            ]
            
            if not include_data:
                dump_cmd.append("--schema-only")
            
            # Set environment for password
            env = os.environ.copy()
            env["PGPASSWORD"] = db_config["password"]
            
            # Execute backup
            logger.info(f"Creating backup: {filename}")
            
            if compress:
                # Pipe through gzip
                with open(backup_path, 'wb') as f:
                    dump_process = subprocess.Popen(
                        dump_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env
                    )
                    gzip_process = subprocess.Popen(
                        ["gzip", "-c"],
                        stdin=dump_process.stdout,
                        stdout=f,
                        stderr=subprocess.PIPE
                    )
                    dump_process.stdout.close()
                    gzip_process.communicate()
                    dump_process.wait()
                    
                    if dump_process.returncode != 0:
                        _, stderr = dump_process.communicate()
                        raise Exception(f"pg_dump failed: {stderr.decode()}")
            else:
                # Direct output
                with open(backup_path, 'w') as f:
                    result = subprocess.run(
                        dump_cmd,
                        stdout=f,
                        stderr=subprocess.PIPE,
                        env=env,
                        text=True
                    )
                    
                    if result.returncode != 0:
                        raise Exception(f"pg_dump failed: {result.stderr}")
            
            # Get file size
            size_bytes = backup_path.stat().st_size
            
            # Create metadata file
            metadata = {
                "backup_id": backup_id,
                "name": name,
                "filename": filename,
                "created_at": datetime.utcnow().isoformat(),
                "size_bytes": size_bytes,
                "include_data": include_data,
                "compressed": compress,
                "database": db_config["database"],
                "version": "1.0"
            }
            
            metadata_path = self.backup_dir / f"{filename}.meta"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Backup created successfully: {filename} ({size_bytes} bytes)")
            
            return {
                "backup_id": backup_id,
                "name": name,
                "filename": filename,
                "path": str(backup_path),
                "size_bytes": size_bytes,
                "created_at": metadata["created_at"]
            }
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            # Cleanup on failure
            if 'backup_path' in locals() and backup_path.exists():
                backup_path.unlink()
            if 'metadata_path' in locals() and metadata_path.exists():
                metadata_path.unlink()
            raise

    async def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        try:
            backups = []
            
            for meta_file in self.backup_dir.glob("*.meta"):
                try:
                    with open(meta_file, 'r') as f:
                        metadata = json.load(f)
                    
                    # Check if backup file exists
                    backup_file = self.backup_dir / metadata["filename"]
                    if backup_file.exists():
                        metadata["file_exists"] = True
                        metadata["current_size"] = backup_file.stat().st_size
                    else:
                        metadata["file_exists"] = False
                        metadata["current_size"] = 0
                    
                    backups.append(metadata)
                    
                except Exception as e:
                    logger.warning(f"Error reading metadata {meta_file}: {e}")
                    continue
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x["created_at"], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []

    async def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """Restore from a specific backup."""
        try:
            # Find backup metadata
            backup_metadata = None
            for meta_file in self.backup_dir.glob("*.meta"):
                with open(meta_file, 'r') as f:
                    metadata = json.load(f)
                    if metadata["backup_id"] == backup_id:
                        backup_metadata = metadata
                        break
            
            if not backup_metadata:
                raise Exception(f"Backup {backup_id} not found")
            
            backup_file = self.backup_dir / backup_metadata["filename"]
            if not backup_file.exists():
                raise Exception(f"Backup file {backup_metadata['filename']} not found")
            
            # Parse database URL
            db_config = self._parse_database_url()
            
            # Extract backup content and filter out problematic commands
            temp_backup_path = self.backup_dir / f"temp_restore_{backup_id[:8]}.sql"
            
            if backup_metadata.get("compressed", False):
                # Decompress and filter
                with gzip.open(backup_file, 'rt') as input_file, open(temp_backup_path, 'w') as output_file:
                    for line in input_file:
                        # Skip commands that cause issues with active connections
                        if (line.startswith('DROP DATABASE') or 
                            line.startswith('CREATE DATABASE') or
                            line.strip().startswith('\\connect')):
                            continue
                        
                        # Convert CREATE FUNCTION to CREATE OR REPLACE FUNCTION to avoid conflicts
                        if line.startswith('CREATE FUNCTION'):
                            line = line.replace('CREATE FUNCTION', 'CREATE OR REPLACE FUNCTION')
                        
                        # Convert CREATE TABLE to DROP + CREATE for proper restore
                        if line.startswith('CREATE TABLE'):
                            table_name = line.split()[2]  # Get table name
                            output_file.write(f'DROP TABLE IF EXISTS {table_name} CASCADE;\n')
                            # Keep original CREATE TABLE command
                        
                        output_file.write(line)
            else:
                # Filter uncompressed file
                with open(backup_file, 'r') as input_file, open(temp_backup_path, 'w') as output_file:
                    for line in input_file:
                        # Skip commands that cause issues with active connections
                        if (line.startswith('DROP DATABASE') or 
                            line.startswith('CREATE DATABASE') or
                            line.strip().startswith('\\connect')):
                            continue
                        
                        # Convert CREATE FUNCTION to CREATE OR REPLACE FUNCTION to avoid conflicts
                        if line.startswith('CREATE FUNCTION'):
                            line = line.replace('CREATE FUNCTION', 'CREATE OR REPLACE FUNCTION')
                        
                        # Convert CREATE TABLE to DROP + CREATE for proper restore
                        if line.startswith('CREATE TABLE'):
                            table_name = line.split()[2]  # Get table name
                            output_file.write(f'DROP TABLE IF EXISTS {table_name} CASCADE;\n')
                            # Keep original CREATE TABLE command
                        
                        output_file.write(line)
            
            # Build psql command - connect directly to target database
            restore_cmd = [
                "psql",
                "-h", db_config["host"],
                "-p", str(db_config["port"]),
                "-U", db_config["user"],
                "-d", db_config["database"],
                "-v", "ON_ERROR_STOP=1"
            ]
            
            # Set environment for password
            env = os.environ.copy()
            env["PGPASSWORD"] = db_config["password"]
            
            logger.info(f"Restoring backup: {backup_metadata['filename']} (filtered)")
            
            # Execute restore with filtered backup
            with open(temp_backup_path, 'r') as f:
                result = subprocess.run(
                    restore_cmd,
                    stdin=f,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True
                )
                
                if result.returncode != 0:
                    # Clean up temp file
                    temp_backup_path.unlink(missing_ok=True)
                    raise Exception(f"Restore failed: {result.stderr}")
            
            # Clean up temp file
            temp_backup_path.unlink(missing_ok=True)
            
            logger.info(f"Backup restored successfully: {backup_metadata['filename']}")
            
            return {
                "backup_id": backup_id,
                "filename": backup_metadata["filename"],
                "restored_at": datetime.utcnow().isoformat(),
                "original_created_at": backup_metadata["created_at"]
            }
            
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            # Clean up temp file on error
            temp_backup_path = self.backup_dir / f"temp_restore_{backup_id[:8]}.sql"
            temp_backup_path.unlink(missing_ok=True)
            raise

    async def delete_backup(self, backup_id: str) -> Dict[str, Any]:
        """Delete a specific backup."""
        try:
            # Find and delete backup files
            backup_metadata = None
            meta_file_path = None
            
            for meta_file in self.backup_dir.glob("*.meta"):
                with open(meta_file, 'r') as f:
                    metadata = json.load(f)
                    if metadata["backup_id"] == backup_id:
                        backup_metadata = metadata
                        meta_file_path = meta_file
                        break
            
            if not backup_metadata:
                raise Exception(f"Backup {backup_id} not found")
            
            # Delete backup file
            backup_file = self.backup_dir / backup_metadata["filename"]
            if backup_file.exists():
                backup_file.unlink()
            
            # Delete metadata file
            if meta_file_path and meta_file_path.exists():
                meta_file_path.unlink()
            
            logger.info(f"Backup deleted: {backup_metadata['filename']}")
            
            return {
                "backup_id": backup_id,
                "filename": backup_metadata["filename"],
                "deleted_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error deleting backup: {e}")
            raise

    async def get_backup_info(self, backup_id: str) -> Dict[str, Any]:
        """Get detailed information about a backup."""
        try:
            # Find backup metadata
            for meta_file in self.backup_dir.glob("*.meta"):
                with open(meta_file, 'r') as f:
                    metadata = json.load(f)
                    if metadata["backup_id"] == backup_id:
                        # Check current file status
                        backup_file = self.backup_dir / metadata["filename"]
                        metadata["file_exists"] = backup_file.exists()
                        if backup_file.exists():
                            metadata["current_size"] = backup_file.stat().st_size
                            metadata["modified_at"] = datetime.fromtimestamp(
                                backup_file.stat().st_mtime
                            ).isoformat()
                        return metadata
            
            raise Exception(f"Backup {backup_id} not found")
            
        except Exception as e:
            logger.error(f"Error getting backup info: {e}")
            raise

    def _parse_database_url(self) -> Dict[str, Any]:
        """Parse PostgreSQL database URL."""
        from urllib.parse import urlparse
        
        parsed = urlparse(self.database_url)
        
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "user": parsed.username or "postgres",
            "password": parsed.password or "",
            "database": parsed.path.lstrip('/') if parsed.path else "postgres"
        }

    async def cleanup_old_backups(self, keep_count: int = 10) -> Dict[str, Any]:
        """Clean up old backups, keeping only the specified number."""
        try:
            backups = await self.list_backups()
            
            if len(backups) <= keep_count:
                return {
                    "deleted_count": 0,
                    "kept_count": len(backups),
                    "message": f"No cleanup needed, only {len(backups)} backups exist"
                }
            
            # Sort by creation date and keep newest ones
            backups.sort(key=lambda x: x["created_at"], reverse=True)
            backups_to_delete = backups[keep_count:]
            
            deleted_count = 0
            for backup in backups_to_delete:
                try:
                    await self.delete_backup(backup["backup_id"])
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete backup {backup['backup_id']}: {e}")
            
            return {
                "deleted_count": deleted_count,
                "kept_count": keep_count,
                "total_processed": len(backups)
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
            raise

    async def verify_backup_integrity(self, backup_id: str) -> Dict[str, Any]:
        """Verify backup file integrity."""
        try:
            backup_info = await self.get_backup_info(backup_id)
            
            if not backup_info["file_exists"]:
                return {
                    "valid": False,
                    "error": "Backup file does not exist"
                }
            
            backup_file = self.backup_dir / backup_info["filename"]
            
            # Check file size
            current_size = backup_file.stat().st_size
            expected_size = backup_info["size_bytes"]
            
            if current_size != expected_size:
                return {
                    "valid": False,
                    "error": f"File size mismatch: expected {expected_size}, got {current_size}"
                }
            
            # If compressed, test decompression
            if backup_info.get("compressed", False):
                try:
                    with gzip.open(backup_file, 'rt') as f:
                        # Read first few lines to test
                        for i, line in enumerate(f):
                            if i > 10:  # Just test first 10 lines
                                break
                except Exception as e:
                    return {
                        "valid": False,
                        "error": f"Decompression failed: {str(e)}"
                    }
            
            return {
                "valid": True,
                "size_bytes": current_size,
                "verified_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error verifying backup: {e}")
            return {
                "valid": False,
                "error": str(e)
            }