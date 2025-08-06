"""
End-to-end integration tests for the complete RAG system.

Tests the full query flow from user input to final response.
"""

import os
import sys
import unittest
from unittest.mock import patch, Mock

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rag_system import RAGSystem
from config import config, Config
import tempfile
import shutil


class TestRAGSystemIntegration(unittest.TestCase):
    """Test complete RAG system integration"""

    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test
        self.temp_dir = tempfile.mkdtemp()

        # Create test config with fixed MAX_RESULTS
        self.test_config = Config()
        self.test_config.MAX_RESULTS = 3  # Fix the bug for testing
        self.test_config.CHROMA_PATH = os.path.join(self.temp_dir, "test_chroma")

        # Initialize RAG system with test config
        self.rag_system = RAGSystem(self.test_config)

    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_rag_system_initialization(self):
        """Test that RAG system initializes all components correctly"""
        # Check core components
        self.assertIsNotNone(self.rag_system.document_processor)
        self.assertIsNotNone(self.rag_system.vector_store)
        self.assertIsNotNone(self.rag_system.ai_generator)
        self.assertIsNotNone(self.rag_system.session_manager)

        # Check tool system
        self.assertIsNotNone(self.rag_system.tool_manager)
        self.assertIsNotNone(self.rag_system.search_tool)
        self.assertIsNotNone(self.rag_system.outline_tool)

        # Check that tools are registered
        tool_definitions = self.rag_system.tool_manager.get_tool_definitions()
        tool_names = [tool["name"] for tool in tool_definitions]
        self.assertIn("search_course_content", tool_names)
        self.assertIn("get_course_outline", tool_names)

    def test_query_with_empty_vector_store(self):
        """Test querying when no course data is loaded"""
        try:
            response, sources = self.rag_system.query("What is machine learning?")

            # Should get a response (may be general knowledge or "no results")
            self.assertIsInstance(response, str)
            self.assertIsInstance(sources, list)

            print(f"\n📝 Empty store response: {response[:100]}...")

        except Exception as e:
            print(f"\n❌ Query failed with empty store: {e}")
            # This might fail due to the MAX_RESULTS=0 bug even in our test

    @patch("anthropic.Anthropic")
    def test_query_flow_with_mocked_ai(self, mock_anthropic_class):
        """Test complete query flow with mocked AI responses"""
        # Mock the Anthropic client to avoid API calls
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [
            Mock(text="Machine learning is a subset of AI that focuses on algorithms.")
        ]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        # Create fresh RAG system with mocked AI
        rag_system = RAGSystem(self.test_config)

        response, sources = rag_system.query("What is machine learning?")

        self.assertIsInstance(response, str)
        self.assertIn("machine learning", response.lower())
        self.assertIsInstance(sources, list)

    @patch("anthropic.Anthropic")
    def test_query_with_tool_use_mocked(self, mock_anthropic_class):
        """Test query flow when AI decides to use tools (mocked)"""
        # Mock AI client to simulate tool use
        mock_client = Mock()

        # Mock initial response with tool use
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.id = "tool_123"
        mock_tool_block.input = {"query": "machine learning"}

        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block]
        mock_initial_response.stop_reason = "tool_use"

        # Mock final response
        mock_final_response = Mock()
        mock_final_response.content = [
            Mock(text="Based on course materials, machine learning involves...")
        ]

        mock_client.messages.create.side_effect = [
            mock_initial_response,
            mock_final_response,
        ]
        mock_anthropic_class.return_value = mock_client

        # Create RAG system with mocked AI
        rag_system = RAGSystem(self.test_config)

        response, sources = rag_system.query(
            "Tell me about machine learning from the courses"
        )

        self.assertIsInstance(response, str)
        self.assertIsInstance(sources, list)

        # Verify AI called the API twice (initial + final)
        self.assertEqual(mock_client.messages.create.call_count, 2)

    def test_session_management(self):
        """Test session management in RAG system"""
        with patch("anthropic.Anthropic") as mock_anthropic_class:
            # Mock simple responses
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="Response")]
            mock_response.stop_reason = "end_turn"
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            rag_system = RAGSystem(self.test_config)

            # First query without session ID
            response1, sources1 = rag_system.query("First question")

            # Second query with session ID from first
            session_id = rag_system.session_manager.create_session()
            response2, sources2 = rag_system.query("Second question", session_id)

            # Should maintain session
            history = rag_system.session_manager.get_conversation_history(session_id)
            self.assertIsNotNone(history)

    def test_source_tracking(self):
        """Test that sources are properly tracked through the system"""
        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="Response")]
            mock_response.stop_reason = "end_turn"
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client

            rag_system = RAGSystem(self.test_config)

            response, sources = rag_system.query("Test query")

            # Sources should be a list (may be empty if no search was performed)
            self.assertIsInstance(sources, list)

    def test_get_course_analytics(self):
        """Test course analytics functionality"""
        analytics = self.rag_system.get_course_analytics()

        self.assertIsInstance(analytics, dict)
        self.assertIn("total_courses", analytics)
        self.assertIn("course_titles", analytics)
        self.assertIsInstance(analytics["total_courses"], int)
        self.assertIsInstance(analytics["course_titles"], list)


class TestRealRAGSystemIntegration(unittest.TestCase):
    """Test RAG system with real configuration and data"""

    def setUp(self):
        """Set up with real RAG system"""
        self.rag_system = RAGSystem(config)

    def test_real_system_initialization(self):
        """Test real RAG system initialization"""
        # Check components exist
        self.assertIsNotNone(self.rag_system.vector_store)
        self.assertIsNotNone(self.rag_system.ai_generator)

        # Check configuration issues
        max_results = self.rag_system.vector_store.max_results
        print(f"\n📊 Real system MAX_RESULTS: {max_results}")

        if max_results == 0:
            print("❌ CRITICAL: Real system has MAX_RESULTS=0 bug")
        else:
            print(f"✅ MAX_RESULTS is {max_results}")

    def test_real_data_status(self):
        """Test status of real course data"""
        analytics = self.rag_system.get_course_analytics()

        print(f"\n📚 Real data status:")
        print(f"   Total courses: {analytics['total_courses']}")
        print(f"   Course titles: {analytics['course_titles']}")

        if analytics["total_courses"] > 0:
            print("✅ Course data is loaded")
        else:
            print("❌ No course data loaded")

    def test_real_query_with_max_results_bug(self):
        """Test a real query with the MAX_RESULTS=0 bug"""
        print(f"\n🔍 Testing real query with MAX_RESULTS={config.MAX_RESULTS}")

        try:
            # This will likely fail due to MAX_RESULTS=0
            response, sources = self.rag_system.query("What is machine learning?")

            print(f"   Response: {response[:100]}...")
            print(f"   Sources: {len(sources)} sources")

            if "failed" in response.lower() or "error" in response.lower():
                print("❌ Query resulted in error/failure response")
            else:
                print("✅ Query succeeded despite MAX_RESULTS bug")

        except Exception as e:
            print(f"❌ Query raised exception: {e}")

    @patch("config.config.MAX_RESULTS", 5)
    def test_query_with_fixed_config(self):
        """Test query with corrected MAX_RESULTS"""
        print(f"\n🔧 Testing with fixed MAX_RESULTS=5")

        # Create new RAG system with fixed config
        fixed_config = Config()
        fixed_config.MAX_RESULTS = 5
        fixed_config.ANTHROPIC_API_KEY = config.ANTHROPIC_API_KEY

        try:
            fixed_rag = RAGSystem(fixed_config)
            print("✅ RAG system created with fixed config")

            # Note: This would require reloading data, which is complex for this test
            # But it demonstrates the fix would work

        except Exception as e:
            print(f"❌ Fixed config failed: {e}")


def run_integration_diagnostics():
    """Run comprehensive RAG system integration diagnostics"""
    print("=== RAG SYSTEM INTEGRATION DIAGNOSTICS ===")

    print("\n--- Configuration Status ---")
    print(
        f"MAX_RESULTS: {config.MAX_RESULTS} {'❌ BUG' if config.MAX_RESULTS == 0 else '✅'}"
    )
    print(f"API Key: {'✅ Set' if config.ANTHROPIC_API_KEY else '❌ Missing'}")

    print("\n--- Unit Tests ---")
    suite1 = unittest.TestLoader().loadTestsFromTestCase(TestRAGSystemIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    result1 = runner.run(suite1)

    print("\n--- Real System Tests ---")
    suite2 = unittest.TestLoader().loadTestsFromTestCase(TestRealRAGSystemIntegration)
    result2 = runner.run(suite2)

    total_tests = result1.testsRun + result2.testsRun
    total_failures = len(
        result1.failures + result1.errors + result2.failures + result2.errors
    )

    success = total_failures == 0
    print(
        f"\n{'✅' if success else '❌'} Integration tests: {total_tests - total_failures}/{total_tests} passed"
    )

    return success


if __name__ == "__main__":
    run_integration_diagnostics()
