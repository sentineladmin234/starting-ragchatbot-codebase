"""
Unit tests for CourseSearchTool functionality.

Tests the execute method of CourseSearchTool to identify why content queries fail.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from search_tools import CourseSearchTool, ToolManager
from vector_store import VectorStore, SearchResults
from models import SourceWithLink
from config import config


class TestCourseSearchTool(unittest.TestCase):
    """Test CourseSearchTool functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock vector store
        self.mock_vector_store = Mock(spec=VectorStore)
        self.search_tool = CourseSearchTool(self.mock_vector_store)
        
    def test_tool_definition(self):
        """Test that tool definition is correctly structured"""
        tool_def = self.search_tool.get_tool_definition()
        
        # Check required fields
        self.assertIn("name", tool_def)
        self.assertIn("description", tool_def)
        self.assertIn("input_schema", tool_def)
        
        # Check tool name
        self.assertEqual(tool_def["name"], "search_course_content")
        
        # Check required parameters
        required = tool_def["input_schema"]["required"]
        self.assertIn("query", required)
        self.assertEqual(len(required), 1)  # Only query is required
        
        # Check optional parameters
        properties = tool_def["input_schema"]["properties"]
        self.assertIn("course_name", properties)
        self.assertIn("lesson_number", properties)
    
    def test_execute_with_empty_results_due_to_max_results_zero(self):
        """Test execute when vector store returns empty results due to MAX_RESULTS=0"""
        # Mock search results to be empty (simulating MAX_RESULTS=0 issue)
        empty_results = SearchResults(documents=[], metadata=[], distances=[])
        self.mock_vector_store.search.return_value = empty_results
        
        result = self.search_tool.execute("test query")
        
        # Should return "No relevant content found" message
        self.assertIn("No relevant content found", result)
        self.mock_vector_store.search.assert_called_once_with(
            query="test query",
            course_name=None,
            lesson_number=None
        )
    
    def test_execute_with_search_error(self):
        """Test execute when vector store returns error"""
        error_results = SearchResults.empty("Search error: ChromaDB connection failed")
        self.mock_vector_store.search.return_value = error_results
        
        result = self.search_tool.execute("test query")
        
        # Should return the error message
        self.assertEqual(result, "Search error: ChromaDB connection failed")
    
    def test_execute_with_successful_results(self):
        """Test execute with successful search results"""
        # Mock successful search results
        mock_results = SearchResults(
            documents=["This is test content about machine learning"],
            metadata=[{
                "course_title": "AI Foundations",
                "lesson_number": 1
            }],
            distances=[0.8]
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson1"
        
        result = self.search_tool.execute("machine learning")
        
        # Should format and return the results
        self.assertIn("AI Foundations", result)
        self.assertIn("Lesson 1", result)
        self.assertIn("This is test content", result)
    
    def test_execute_with_course_filter(self):
        """Test execute with course name filter"""
        empty_results = SearchResults(documents=[], metadata=[], distances=[])
        self.mock_vector_store.search.return_value = empty_results
        
        result = self.search_tool.execute("test query", course_name="AI Course")
        
        # Should include course name in filter message
        self.assertIn("in course 'AI Course'", result)
        self.mock_vector_store.search.assert_called_once_with(
            query="test query",
            course_name="AI Course",
            lesson_number=None
        )
    
    def test_execute_with_lesson_filter(self):
        """Test execute with lesson number filter"""
        empty_results = SearchResults(documents=[], metadata=[], distances=[])
        self.mock_vector_store.search.return_value = empty_results
        
        result = self.search_tool.execute("test query", lesson_number=2)
        
        # Should include lesson number in filter message
        self.assertIn("in lesson 2", result)
        self.mock_vector_store.search.assert_called_once_with(
            query="test query",
            course_name=None,
            lesson_number=2
        )
    
    def test_source_tracking(self):
        """Test that sources are properly tracked"""
        # Mock successful search results
        mock_results = SearchResults(
            documents=["Content 1", "Content 2"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2}
            ],
            distances=[0.8, 0.9]
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.side_effect = [
            "https://example.com/course-a/lesson-1",
            "https://example.com/course-b/lesson-2"
        ]
        
        result = self.search_tool.execute("test query")
        
        # Check that sources were tracked
        self.assertEqual(len(self.search_tool.last_sources), 2)
        
        # Check first source
        source1 = self.search_tool.last_sources[0]
        self.assertIsInstance(source1, SourceWithLink)
        self.assertEqual(source1.text, "Course A - Lesson 1")
        self.assertEqual(source1.url, "https://example.com/course-a/lesson-1")
        
        # Check second source
        source2 = self.search_tool.last_sources[1]
        self.assertEqual(source2.text, "Course B - Lesson 2")
        self.assertEqual(source2.url, "https://example.com/course-b/lesson-2")
    
    def test_tool_manager_registration(self):
        """Test that CourseSearchTool can be registered with ToolManager"""
        tool_manager = ToolManager()
        tool_manager.register_tool(self.search_tool)
        
        # Check that tool is registered
        self.assertIn("search_course_content", tool_manager.tools)
        
        # Check tool definitions
        definitions = tool_manager.get_tool_definitions()
        self.assertEqual(len(definitions), 1)
        self.assertEqual(definitions[0]["name"], "search_course_content")
    
    def test_tool_manager_execution(self):
        """Test executing tool through ToolManager"""
        tool_manager = ToolManager()
        tool_manager.register_tool(self.search_tool)
        
        # Mock empty results
        empty_results = SearchResults(documents=[], metadata=[], distances=[])
        self.mock_vector_store.search.return_value = empty_results
        
        # Execute through tool manager
        result = tool_manager.execute_tool("search_course_content", query="test query")
        
        self.assertIn("No relevant content found", result)
    
    def test_real_config_max_results_issue(self):
        """Test that shows the real MAX_RESULTS=0 configuration issue"""
        from config import config
        
        # This test documents the actual issue
        self.assertEqual(config.MAX_RESULTS, 0, 
                        "This test confirms MAX_RESULTS is 0 - causing search failures")
        
        print(f"\n💡 DIAGNOSIS: MAX_RESULTS is set to {config.MAX_RESULTS}")
        print("This means vector store searches request 0 results, always returning empty!")
        print("This is the root cause of 'query failed' responses.")


def run_search_tool_diagnostics():
    """Run comprehensive CourseSearchTool diagnostics"""
    print("=== COURSESEARCHTOOL DIAGNOSTICS ===")
    
    # Test configuration issue
    from config import config
    if config.MAX_RESULTS == 0:
        print("❌ CRITICAL: MAX_RESULTS is 0 - this breaks all searches!")
    else:
        print(f"✅ MAX_RESULTS is {config.MAX_RESULTS}")
    
    print("\nRunning CourseSearchTool unit tests...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCourseSearchTool)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    success = len(result.failures + result.errors) == 0
    print(f"\n{'✅' if success else '❌'} CourseSearchTool tests: {result.testsRun - len(result.failures + result.errors)}/{result.testsRun} passed")
    
    return success


if __name__ == "__main__":
    run_search_tool_diagnostics()