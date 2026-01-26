"""
Data models for BCR transaction processing.

This module exports typed data structures that replace
dictionary-based approaches throughout the codebase.
"""

from .transaction import Transaction, TransactionType

__all__ = ['Transaction', 'TransactionType']
