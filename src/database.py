#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson.objectid import ObjectId
from dotenv import load_dotenv

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class MongoDBHandler:
    """Handler for MongoDB database operations"""

    def __init__(self):
        """Initialize MongoDB connection"""
        mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
        logger.debug(f"connecting to mongodb: {mongo_uri}")
        
        try:
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            # validate connection
            self.client.admin.command('ping')
            logger.info("mongodb connection successful")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"failed to connect to mongodb: {e}")
            raise
            
        self.db = self.client.library_db
        
        # Collections
        self.readers = self.db.readers
        self.loans = self.db.loans
        
        # Ensure indexes
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Setup database indexes"""
        try:
            # Create indexes for common queries
            self.readers.create_index("name")
            self.loans.create_index([("reader_id", 1), ("is_active", 1)])
            logger.debug("Database indexes created")
        except Exception as e:
            logger.warning(f"Failed to create indexes: {e}")
    
    def add_reader(self, reader_data: Dict[str, Any]) -> str:
        """Add a new reader to the database"""
        try:
            result = self.readers.insert_one(reader_data)
            logger.info(f"Reader added with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to add reader: {e}")
            raise
    
    def get_all_readers(self) -> List[Dict[str, Any]]:
        """Get all readers from the database"""
        try:
            readers = list(self.readers.find())
            logger.debug(f"Retrieved {len(readers)} readers")
            return readers
        except Exception as e:
            logger.error(f"Failed to retrieve readers: {e}")
            raise
    
    def get_reader_by_id(self, reader_id) -> Optional[Dict[str, Any]]:
        """Get reader by ID"""
        try:
            if isinstance(reader_id, str):
                reader_id = ObjectId(reader_id)
            reader = self.readers.find_one({"_id": reader_id})
            logger.debug(f"Reader retrieved by ID: {reader_id}")
            return reader
        except Exception as e:
            logger.error(f"Failed to retrieve reader by ID: {e}")
            raise
    
    def get_reader_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get reader by name"""
        try:
            reader = self.readers.find_one({"name": name})
            logger.debug(f"Reader retrieved by name: {name}")
            return reader
        except Exception as e:
            logger.error(f"Failed to retrieve reader by name: {e}")
            raise
    
    def update_reader_deposit(self, reader_id, deposit_amount: int) -> bool:
        """Update reader's deposit amount"""
        try:
            if isinstance(reader_id, str):
                reader_id = ObjectId(reader_id)
            result = self.readers.update_one(
                {"_id": reader_id},
                {"$set": {"deposit_amount": deposit_amount}}
            )
            logger.info(f"Updated deposit for reader ID: {reader_id}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update reader deposit: {e}")
            raise
    
    def add_loan(self, loan_data: Dict[str, Any]) -> str:
        """Add a new book loan to the database"""
        try:
            result = self.loans.insert_one(loan_data)
            logger.info(f"Loan added with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to add loan: {e}")
            raise
    
    def get_active_loans(self) -> List[Dict[str, Any]]:
        """Get all active loans from the database"""
        try:
            loans = list(self.loans.find({"is_active": True}))
            logger.debug(f"Retrieved {len(loans)} active loans")
            return loans
        except Exception as e:
            logger.error(f"Failed to retrieve active loans: {e}")
            raise
    
    def get_reader_active_loans(self, reader_id) -> List[Dict[str, Any]]:
        """Get all active loans for a specific reader"""
        try:
            if isinstance(reader_id, str):
                reader_id = ObjectId(reader_id)
            loans = list(self.loans.find({"reader_id": reader_id, "is_active": True}))
            logger.debug(f"Retrieved {len(loans)} active loans for reader ID: {reader_id}")
            return loans
        except Exception as e:
            logger.error(f"Failed to retrieve active loans for reader: {e}")
            raise
    
    def return_book(self, reader_id, book_title: str) -> bool:
        """Mark a book as returned"""
        try:
            if isinstance(reader_id, str):
                reader_id = ObjectId(reader_id)
            result = self.loans.update_one(
                {"reader_id": reader_id, "book_title": book_title, "is_active": True},
                {"$set": {"is_active": False, "return_date": datetime.now()}}
            )
            logger.info(f"Book returned: {book_title} for reader ID: {reader_id}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to return book: {e}")
            raise