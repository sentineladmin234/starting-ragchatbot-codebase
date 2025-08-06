"""
Tests for configuration validation and environment setup.

These tests identify configuration issues that could cause system failures.
"""

import os
import unittest
from unittest.mock import patch
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import Config, config


class TestConfig(unittest.TestCase):
    """Test configuration validation and settings"""
    
    def test_max_results_not_zero(self):
        """CRITICAL: Test that MAX_RESULTS is not zero - this causes search failures"""
        self.assertGreater(config.MAX_RESULTS, 0, 
                          "MAX_RESULTS is 0! This causes all searches to return empty results.")
    
    def test_anthropic_api_key_set(self):
        """Test that ANTHROPIC_API_KEY is configured"""
        # Check if key is set in environment or config
        api_key = config.ANTHROPIC_API_KEY
        self.assertTrue(api_key and api_key.strip(), 
                       "ANTHROPIC_API_KEY is not set in environment variables")
        self.assertFalse(api_key.startswith("sk-ant-"), 
                        "API key appears to be a placeholder, not a real key")
    
    def test_chunk_size_valid(self):
        """Test that chunk size is reasonable for document processing"""
        self.assertGreater(config.CHUNK_SIZE, 100, 
                          "CHUNK_SIZE too small - may not capture meaningful content")
        self.assertLess(config.CHUNK_SIZE, 5000, 
                       "CHUNK_SIZE too large - may exceed token limits")
    
    def test_chunk_overlap_valid(self):
        """Test that chunk overlap is reasonable"""
        self.assertGreaterEqual(config.CHUNK_OVERLAP, 0, 
                               "CHUNK_OVERLAP cannot be negative")
        self.assertLess(config.CHUNK_OVERLAP, config.CHUNK_SIZE, 
                       "CHUNK_OVERLAP should be less than CHUNK_SIZE")
    
    def test_max_history_valid(self):
        """Test that conversation history limit is reasonable"""
        self.assertGreaterEqual(config.MAX_HISTORY, 1, 
                               "MAX_HISTORY should be at least 1 for context")
        self.assertLessEqual(config.MAX_HISTORY, 10, 
                            "MAX_HISTORY too large - may consume too much context")
    
    def test_anthropic_model_valid(self):
        """Test that the model name is a valid Anthropic model"""
        valid_models = [
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022", 
            "claude-3-5-sonnet-20240620",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229"
        ]
        self.assertIn(config.ANTHROPIC_MODEL, valid_models, 
                     f"Model '{config.ANTHROPIC_MODEL}' may not be valid")
    
    def test_embedding_model_valid(self):
        """Test that embedding model name is valid"""
        # Common sentence transformer models
        valid_embedding_models = [
            "all-MiniLM-L6-v2",
            "all-mpnet-base-v2",
            "all-distilroberta-v1"
        ]
        self.assertIn(config.EMBEDDING_MODEL, valid_embedding_models, 
                     f"Embedding model '{config.EMBEDDING_MODEL}' may not be valid")
    
    def test_chroma_path_valid(self):
        """Test that ChromaDB path is valid"""
        self.assertTrue(config.CHROMA_PATH, "CHROMA_PATH cannot be empty")
        # Path should be relative or absolute but not empty
        self.assertNotEqual(config.CHROMA_PATH.strip(), "", 
                           "CHROMA_PATH is empty or whitespace")
    
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""})
    def test_missing_api_key_handling(self):
        """Test behavior when API key is missing"""
        # Reload config with empty API key
        test_config = Config()
        self.assertEqual(test_config.ANTHROPIC_API_KEY, "", 
                        "Config should handle missing API key gracefully")
    
    def test_config_singleton_behavior(self):
        """Test that config instance is consistent"""
        # The imported config should be the same as a new Config()
        new_config = Config()
        self.assertEqual(config.ANTHROPIC_MODEL, new_config.ANTHROPIC_MODEL)
        self.assertEqual(config.MAX_RESULTS, new_config.MAX_RESULTS)
    
    def print_config_status(self):
        """Print current configuration for debugging"""
        print(f"\n=== CONFIGURATION STATUS ===")
        print(f"MAX_RESULTS: {config.MAX_RESULTS} {'❌ CRITICAL ISSUE' if config.MAX_RESULTS == 0 else '✅'}")
        print(f"ANTHROPIC_API_KEY: {'Set ✅' if config.ANTHROPIC_API_KEY else 'Missing ❌'}")
        print(f"ANTHROPIC_MODEL: {config.ANTHROPIC_MODEL}")
        print(f"EMBEDDING_MODEL: {config.EMBEDDING_MODEL}")
        print(f"CHUNK_SIZE: {config.CHUNK_SIZE}")
        print(f"CHUNK_OVERLAP: {config.CHUNK_OVERLAP}")
        print(f"MAX_HISTORY: {config.MAX_HISTORY}")
        print(f"CHROMA_PATH: {config.CHROMA_PATH}")
        print(f"=== END CONFIGURATION STATUS ===\n")


def run_config_diagnostics():
    """Run configuration diagnostics and print results"""
    test = TestConfig()
    test.print_config_status()
    
    print("Running configuration validation tests...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestConfig)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.failures or result.errors:
        print(f"\n❌ Found {len(result.failures + result.errors)} configuration issues!")
        for test, error in result.failures + result.errors:
            print(f"ISSUE: {test}")
            print(f"DETAILS: {error}")
    else:
        print("\n✅ All configuration tests passed!")
    
    return len(result.failures + result.errors) == 0


if __name__ == "__main__":
    # Run diagnostics when called directly
    run_config_diagnostics()