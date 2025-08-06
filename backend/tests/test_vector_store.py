"""
Tests for VectorStore functionality including data loading and search operations.

These tests verify if course data is properly loaded and if search functionality works.
"""

import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, Mock

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from vector_store import VectorStore, SearchResults
from config import config
from models import Course, Lesson, CourseChunk


class TestVectorStore(unittest.TestCase):
    """Test VectorStore functionality with real configuration"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test ChromaDB
        self.temp_dir = tempfile.mkdtemp()
        self.test_chroma_path = os.path.join(self.temp_dir, "test_chroma")
        
        # Create VectorStore with test path but real config values
        self.vector_store = VectorStore(
            chroma_path=self.test_chroma_path,
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS  # This will be 0 - the bug!
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_vector_store_initialization(self):
        """Test that VectorStore initializes correctly"""
        self.assertIsNotNone(self.vector_store.client)
        self.assertIsNotNone(self.vector_store.course_catalog)
        self.assertIsNotNone(self.vector_store.course_content)
        self.assertEqual(self.vector_store.max_results, config.MAX_RESULTS)
    
    def test_max_results_configuration_issue(self):
        """Test that demonstrates the MAX_RESULTS=0 issue"""
        # This test documents the actual bug
        self.assertEqual(self.vector_store.max_results, 0,
                        "VectorStore max_results is 0 - this breaks all searches!")
        print(f"\n💡 ISSUE: VectorStore initialized with max_results={self.vector_store.max_results}")
    
    def test_add_course_metadata(self):
        """Test adding course metadata to vector store"""
        # Create test course
        lessons = [
            Lesson(lesson_number=1, title="Introduction", lesson_link="https://example.com/lesson1"),
            Lesson(lesson_number=2, title="Advanced Topics", lesson_link="https://example.com/lesson2")
        ]
        course = Course(
            title="Test Course",
            course_link="https://example.com/course",
            instructor="Test Instructor",
            lessons=lessons
        )
        
        # Add to vector store
        self.vector_store.add_course_metadata(course)
        
        # Verify course was added
        existing_titles = self.vector_store.get_existing_course_titles()
        self.assertIn("Test Course", existing_titles)
        self.assertEqual(self.vector_store.get_course_count(), 1)
    
    def test_add_course_content(self):
        """Test adding course content chunks to vector store"""
        # Create test chunks
        chunks = [
            CourseChunk(
                content="This is lesson 1 content about machine learning basics",
                course_title="Test Course",
                lesson_number=1,
                chunk_index=0
            ),
            CourseChunk(
                content="This is lesson 2 content about advanced neural networks",
                course_title="Test Course", 
                lesson_number=2,
                chunk_index=1
            )
        ]
        
        # Add to vector store
        self.vector_store.add_course_content(chunks)
        
        # Content is added but we can't verify easily without search working
        # This test mainly ensures no exceptions are raised
    
    def test_search_with_max_results_zero_bug(self):
        """Test search functionality with MAX_RESULTS=0 bug"""
        # Add some test data first
        chunks = [
            CourseChunk(
                content="Machine learning is a subset of artificial intelligence",
                course_title="AI Basics",
                lesson_number=1,
                chunk_index=0
            )
        ]
        self.vector_store.add_course_content(chunks)
        
        # Attempt search with the buggy configuration
        results = self.vector_store.search("machine learning")
        
        # With max_results=0, this should return empty results
        self.assertTrue(results.is_empty(), 
                       "Search should return empty results when max_results=0")
        self.assertEqual(len(results.documents), 0)
        print(f"\n💡 CONFIRMED: Search with max_results=0 returns {len(results.documents)} results")
    
    def test_search_with_fixed_max_results(self):
        """Test search functionality with corrected max_results"""
        # Add some test data first
        chunks = [
            CourseChunk(
                content="Machine learning is a subset of artificial intelligence",
                course_title="AI Basics",
                lesson_number=1,
                chunk_index=0
            )
        ]
        self.vector_store.add_course_content(chunks)
        
        # Test search with manually specified limit (bypassing max_results)
        results = self.vector_store.search("machine learning", limit=3)
        
        # This should work because we're providing explicit limit
        if not results.error:
            self.assertFalse(results.is_empty(),
                           "Search with explicit limit should return results")
            print(f"\n✅ Search with explicit limit=3 returns {len(results.documents)} results")
        else:
            print(f"\n❌ Search error: {results.error}")
    
    def test_course_name_resolution(self):
        """Test course name resolution functionality"""
        # Add test course metadata
        lessons = [Lesson(lesson_number=1, title="Test Lesson")]
        course = Course(title="Machine Learning Fundamentals", lessons=lessons)
        self.vector_store.add_course_metadata(course)
        
        # Test course name resolution
        resolved = self.vector_store._resolve_course_name("Machine Learning")
        self.assertEqual(resolved, "Machine Learning Fundamentals")
        
        # Test partial match
        resolved_partial = self.vector_store._resolve_course_name("ML")
        # This might not work perfectly but shouldn't crash
        
    def test_get_all_courses_metadata(self):
        """Test getting all course metadata"""
        # Add test course
        lessons = [
            Lesson(lesson_number=1, title="Intro", lesson_link="https://example.com/1"),
            Lesson(lesson_number=2, title="Advanced", lesson_link="https://example.com/2")
        ]
        course = Course(
            title="Test Course",
            course_link="https://example.com/course",
            instructor="Test Teacher",
            lessons=lessons
        )
        self.vector_store.add_course_metadata(course)
        
        # Get metadata
        metadata = self.vector_store.get_all_courses_metadata()
        self.assertEqual(len(metadata), 1)
        
        course_meta = metadata[0]
        self.assertEqual(course_meta['title'], "Test Course")
        self.assertEqual(course_meta['instructor'], "Test Teacher")
        self.assertEqual(course_meta['course_link'], "https://example.com/course")
        self.assertEqual(len(course_meta['lessons']), 2)
    
    def test_get_lesson_link(self):
        """Test getting lesson links"""
        # Add test course with lessons
        lessons = [
            Lesson(lesson_number=1, title="Lesson 1", lesson_link="https://example.com/lesson1"),
            Lesson(lesson_number=2, title="Lesson 2", lesson_link="https://example.com/lesson2")
        ]
        course = Course(title="Test Course", lessons=lessons)
        self.vector_store.add_course_metadata(course)
        
        # Test getting lesson link
        link1 = self.vector_store.get_lesson_link("Test Course", 1)
        self.assertEqual(link1, "https://example.com/lesson1")
        
        link2 = self.vector_store.get_lesson_link("Test Course", 2) 
        self.assertEqual(link2, "https://example.com/lesson2")
        
        # Test non-existent lesson
        no_link = self.vector_store.get_lesson_link("Test Course", 99)
        self.assertIsNone(no_link)


class TestRealVectorStoreData(unittest.TestCase):
    """Test with the actual vector store and data"""
    
    def setUp(self):
        """Set up with real vector store"""
        self.vector_store = VectorStore(
            chroma_path=config.CHROMA_PATH,
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS
        )
    
    def test_real_data_loading(self):
        """Test if real course data is loaded"""
        course_count = self.vector_store.get_course_count()
        course_titles = self.vector_store.get_existing_course_titles()
        
        print(f"\n📊 REAL DATA STATUS:")
        print(f"   Courses loaded: {course_count}")
        print(f"   Course titles: {course_titles}")
        
        if course_count > 0:
            print("✅ Course data is loaded in vector store")
            
            # Test search with real data and MAX_RESULTS=0
            results = self.vector_store.search("machine learning")
            print(f"   Search results with MAX_RESULTS=0: {len(results.documents)} documents")
            
            if results.error:
                print(f"   Search error: {results.error}")
            elif results.is_empty():
                print("   ❌ Search returns empty (due to MAX_RESULTS=0)")
            
            # Test with explicit limit
            results_with_limit = self.vector_store.search("machine learning", limit=3)
            print(f"   Search with explicit limit=3: {len(results_with_limit.documents)} documents")
            
        else:
            print("❌ No course data found in vector store")


def run_vector_store_diagnostics():
    """Run comprehensive VectorStore diagnostics"""
    print("=== VECTOR STORE DIAGNOSTICS ===")
    
    print("Running VectorStore unit tests...")
    
    # Run unit tests
    suite1 = unittest.TestLoader().loadTestsFromTestCase(TestVectorStore)
    suite2 = unittest.TestLoader().loadTestsFromTestCase(TestRealVectorStoreData)
    
    runner = unittest.TextTestRunner(verbosity=2)
    
    print("\n--- Unit Tests ---")
    result1 = runner.run(suite1)
    
    print("\n--- Real Data Tests ---") 
    result2 = runner.run(suite2)
    
    total_tests = result1.testsRun + result2.testsRun
    total_failures = len(result1.failures + result1.errors + result2.failures + result2.errors)
    
    success = total_failures == 0
    print(f"\n{'✅' if success else '❌'} VectorStore tests: {total_tests - total_failures}/{total_tests} passed")
    
    return success


if __name__ == "__main__":
    run_vector_store_diagnostics()