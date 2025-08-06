"""
Tests for AIGenerator tool calling and API integration.

Tests whether AIGenerator correctly calls tools and handles API responses.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import anthropic

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai_generator import AIGenerator
from search_tools import ToolManager, CourseSearchTool
from config import config


class TestAIGenerator(unittest.TestCase):
    """Test AIGenerator functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create AI generator with test API key
        self.ai_generator = AIGenerator("test-api-key", config.ANTHROPIC_MODEL)
        
        # Create mock tool manager
        self.mock_tool_manager = Mock(spec=ToolManager)
        
    def test_system_prompt_contains_tool_instructions(self):
        """Test that system prompt includes tool usage instructions"""
        prompt = self.ai_generator.SYSTEM_PROMPT
        
        # Check for tool-related instructions
        self.assertIn("get_course_outline", prompt)
        self.assertIn("search_course_content", prompt)
        self.assertIn("Tool Usage Guidelines", prompt)
        self.assertIn("Course outline/structure queries", prompt)
        self.assertIn("Specific content queries", prompt)
    
    def test_base_params_configuration(self):
        """Test that base API parameters are correctly configured"""
        params = self.ai_generator.base_params
        
        self.assertEqual(params["model"], config.ANTHROPIC_MODEL)
        self.assertEqual(params["temperature"], 0)
        self.assertEqual(params["max_tokens"], 800)
    
    @patch('anthropic.Anthropic')
    def test_generate_response_without_tools(self, mock_anthropic_class):
        """Test generating response without tools (direct API call)"""
        # Mock the Anthropic client and response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Test response")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client
        
        # Create fresh AI generator to use mocked client
        ai_gen = AIGenerator("test-key", "claude-3-sonnet-20240229")
        
        result = ai_gen.generate_response("What is machine learning?")
        
        self.assertEqual(result, "Test response")
        mock_client.messages.create.assert_called_once()
        
        # Verify API call parameters
        call_args = mock_client.messages.create.call_args
        self.assertIn("messages", call_args.kwargs)
        self.assertIn("system", call_args.kwargs)
        self.assertNotIn("tools", call_args.kwargs)  # No tools provided
    
    @patch('anthropic.Anthropic')
    def test_generate_response_with_tools_no_tool_use(self, mock_anthropic_class):
        """Test generating response with tools available but not used"""
        # Mock the Anthropic client and response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Machine learning is...")]
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client
        
        # Create fresh AI generator
        ai_gen = AIGenerator("test-key", "claude-3-sonnet-20240229")
        
        # Mock tool definitions
        mock_tools = [{"name": "search_course_content", "description": "Search courses"}]
        
        result = ai_gen.generate_response(
            "What is machine learning?", 
            tools=mock_tools,
            tool_manager=self.mock_tool_manager
        )
        
        self.assertEqual(result, "Machine learning is...")
        
        # Verify tools were passed to API
        call_args = mock_client.messages.create.call_args
        self.assertIn("tools", call_args.kwargs)
        self.assertEqual(call_args.kwargs["tools"], mock_tools)
    
    @patch('anthropic.Anthropic')
    def test_generate_response_with_tool_use(self, mock_anthropic_class):
        """Test generating response when AI decides to use tools"""
        # Mock the Anthropic client
        mock_client = Mock()
        
        # Mock initial response with tool use
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.id = "tool_call_123"
        mock_tool_block.input = {"query": "machine learning"}
        
        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block]
        mock_initial_response.stop_reason = "tool_use"
        
        # Mock final response after tool execution
        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="Based on the course content, machine learning is...")]
        
        # Set up client responses
        mock_client.messages.create.side_effect = [mock_initial_response, mock_final_response]
        mock_anthropic_class.return_value = mock_client
        
        # Mock tool manager execution
        self.mock_tool_manager.execute_tool.return_value = "Course content about ML..."
        
        # Create fresh AI generator
        ai_gen = AIGenerator("test-key", "claude-3-sonnet-20240229")
        
        mock_tools = [{"name": "search_course_content", "description": "Search courses"}]
        
        result = ai_gen.generate_response(
            "Tell me about machine learning from the courses",
            tools=mock_tools,
            tool_manager=self.mock_tool_manager
        )
        
        self.assertEqual(result, "Based on the course content, machine learning is...")
        
        # Verify tool was executed
        self.mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="machine learning"
        )
        
        # Verify two API calls were made (initial + final)
        self.assertEqual(mock_client.messages.create.call_count, 2)
    
    @patch('anthropic.Anthropic')
    def test_tool_execution_error_handling(self, mock_anthropic_class):
        """Test handling of tool execution errors"""
        # Mock the Anthropic client
        mock_client = Mock()
        
        # Mock initial response with tool use
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.id = "tool_call_123"
        mock_tool_block.input = {"query": "test"}
        
        mock_initial_response = Mock()
        mock_initial_response.content = [mock_tool_block]
        mock_initial_response.stop_reason = "tool_use"
        
        # Mock final response
        mock_final_response = Mock()
        mock_final_response.content = [Mock(text="I apologize, but I encountered an error...")]
        
        mock_client.messages.create.side_effect = [mock_initial_response, mock_final_response]
        mock_anthropic_class.return_value = mock_client
        
        # Mock tool manager to return error
        self.mock_tool_manager.execute_tool.return_value = "Search error: ChromaDB connection failed"
        
        # Create fresh AI generator
        ai_gen = AIGenerator("test-key", "claude-3-sonnet-20240229")
        
        mock_tools = [{"name": "search_course_content", "description": "Search courses"}]
        
        result = ai_gen.generate_response(
            "Search for AI content",
            tools=mock_tools,
            tool_manager=self.mock_tool_manager
        )
        
        # Should handle the error gracefully
        self.assertIn("I apologize", result)
        self.mock_tool_manager.execute_tool.assert_called_once()
    
    def test_conversation_history_integration(self):
        """Test that conversation history is properly integrated"""
        history = "User: What is AI?\nAssistant: Artificial Intelligence is..."
        
        # Test that system content includes history when provided
        with patch('anthropic.Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(text="Test response")]
            mock_response.stop_reason = "end_turn"
            mock_client.messages.create.return_value = mock_response
            mock_anthropic_class.return_value = mock_client
            
            ai_gen = AIGenerator("test-key", "claude-3-sonnet-20240229")
            
            result = ai_gen.generate_response("Continue the conversation", conversation_history=history)
            
            # Check that system content includes history
            call_args = mock_client.messages.create.call_args
            system_content = call_args.kwargs["system"]
            self.assertIn(history, system_content)
    
    @patch('anthropic.Anthropic')
    def test_api_key_validation(self, mock_anthropic_class):
        """Test behavior with invalid API key"""
        # Mock API error response
        mock_client = Mock()
        mock_client.messages.create.side_effect = anthropic.AuthenticationError("Invalid API key")
        mock_anthropic_class.return_value = mock_client
        
        ai_gen = AIGenerator("invalid-key", "claude-3-sonnet-20240229")
        
        # Should raise the authentication error
        with self.assertRaises(anthropic.AuthenticationError):
            ai_gen.generate_response("Test query")
    
    def test_real_config_api_key(self):
        """Test that real configuration has API key set"""
        # Check if API key is configured
        api_key = config.ANTHROPIC_API_KEY
        
        if api_key and api_key.strip():
            print(f"\n✅ API key is configured (length: {len(api_key)} chars)")
            
            # Test that AIGenerator can be initialized with real config
            try:
                real_ai_gen = AIGenerator(api_key, config.ANTHROPIC_MODEL)
                self.assertIsNotNone(real_ai_gen.client)
                print("✅ AIGenerator initialized successfully with real config")
            except Exception as e:
                print(f"❌ AIGenerator initialization failed: {e}")
                self.fail(f"AIGenerator failed to initialize: {e}")
        else:
            print("❌ API key not configured")
            self.fail("ANTHROPIC_API_KEY is not set")


class TestSequentialToolCalling(unittest.TestCase):
    """Test sequential tool calling functionality"""
    
    def setUp(self):
        """Set up test fixtures for sequential tool calling"""
        self.ai_generator = AIGenerator("test-api-key", config.ANTHROPIC_MODEL)
        self.mock_tool_manager = Mock(spec=ToolManager)
        
    @patch('anthropic.Anthropic')
    def test_sequential_tool_calling_two_rounds(self, mock_anthropic_class):
        """Test full 2-round sequential tool calling scenario"""
        mock_client = Mock()
        
        # Mock Round 1: AI decides to get course outline
        mock_tool_block_1 = Mock()
        mock_tool_block_1.type = "tool_use"
        mock_tool_block_1.name = "get_course_outline"
        mock_tool_block_1.id = "tool_call_1"
        mock_tool_block_1.input = {"course_name": "MCP"}
        
        mock_response_1 = Mock()
        mock_response_1.content = [mock_tool_block_1]
        mock_response_1.stop_reason = "tool_use"
        
        # Mock Round 2: AI decides to search for content
        mock_tool_block_2 = Mock()
        mock_tool_block_2.type = "tool_use"
        mock_tool_block_2.name = "search_course_content"
        mock_tool_block_2.id = "tool_call_2"
        mock_tool_block_2.input = {"query": "RAG systems"}
        
        mock_response_2 = Mock()
        mock_response_2.content = [mock_tool_block_2]
        mock_response_2.stop_reason = "tool_use"
        
        # Mock Final Response
        mock_text_block = Mock()
        mock_text_block.text = "Based on the course outline and content search, here's information about RAG systems..."
        mock_final_response = Mock()
        mock_final_response.content = [mock_text_block]
        
        # Set up client responses (Round 1, Round 2, Final)
        mock_client.messages.create.side_effect = [
            mock_response_1, mock_response_2, mock_final_response
        ]
        mock_anthropic_class.return_value = mock_client
        
        # Mock tool executions
        self.mock_tool_manager.execute_tool.side_effect = [
            "Course outline with lesson 4: RAG Systems",
            "Content about RAG systems from courses"
        ]
        
        # Create fresh AI generator
        ai_gen = AIGenerator("test-key", "claude-3-sonnet-20240229")
        
        mock_tools = [
            {"name": "get_course_outline", "description": "Get course outline"},
            {"name": "search_course_content", "description": "Search course content"}
        ]
        
        result = ai_gen.generate_response_with_sequential_tools(
            query="Find information about the same topic as lesson 4 of the MCP course",
            tools=mock_tools,
            tool_manager=self.mock_tool_manager,
            max_rounds=2
        )
        
        # Verify results
        self.assertIn("RAG systems", result)
        
        # Verify tool calls were made in sequence
        self.assertEqual(self.mock_tool_manager.execute_tool.call_count, 2)
        
        # Verify API calls (2 rounds + 1 final = 3 total)
        self.assertEqual(mock_client.messages.create.call_count, 3)
        
        # Verify tool execution sequence
        tool_calls = self.mock_tool_manager.execute_tool.call_args_list
        self.assertEqual(tool_calls[0][0][0], "get_course_outline")  # First call
        self.assertEqual(tool_calls[1][0][0], "search_course_content")  # Second call
    
    @patch('anthropic.Anthropic')
    def test_single_round_termination(self, mock_anthropic_class):
        """Test early termination when no tools needed in Round 2"""
        mock_client = Mock()
        
        # Mock Round 1: AI uses one tool and provides complete answer
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.id = "tool_call_1"
        mock_tool_block.input = {"query": "machine learning"}
        
        mock_round_1_response = Mock()
        mock_round_1_response.content = [mock_tool_block]
        mock_round_1_response.stop_reason = "tool_use"
        
        # Mock Round 2: AI provides final answer without tools
        mock_text_block = Mock()
        mock_text_block.text = "Machine learning is a subset of AI..."
        mock_final_response = Mock()
        mock_final_response.content = [mock_text_block]
        mock_final_response.stop_reason = "end_turn"
        
        mock_client.messages.create.side_effect = [
            mock_round_1_response, mock_final_response
        ]
        mock_anthropic_class.return_value = mock_client
        
        # Mock tool execution
        self.mock_tool_manager.execute_tool.return_value = "Course content about machine learning"
        
        # Create fresh AI generator
        ai_gen = AIGenerator("test-key", "claude-3-sonnet-20240229")
        
        mock_tools = [{"name": "search_course_content", "description": "Search courses"}]
        
        result = ai_gen.generate_response_with_sequential_tools(
            query="What is machine learning?",
            tools=mock_tools,
            tool_manager=self.mock_tool_manager,
            max_rounds=2
        )
        
        # Verify results
        self.assertIn("Machine learning", result)
        
        # Verify only one tool call made
        self.assertEqual(self.mock_tool_manager.execute_tool.call_count, 1)
        
        # Verify only 2 API calls (Round 1 + Round 2, no final call needed)
        self.assertEqual(mock_client.messages.create.call_count, 2)
    
    @patch('anthropic.Anthropic')
    def test_tool_execution_failure_handling(self, mock_anthropic_class):
        """Test graceful degradation on tool execution failures"""
        mock_client = Mock()
        
        # Mock Round 1: AI tries to use tool
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.id = "tool_call_1"
        mock_tool_block.input = {"query": "test"}
        
        mock_text_block = Mock()
        mock_text_block.text = "I couldn't complete the search due to a tool error."
        mock_response = Mock()
        mock_response.content = [mock_text_block, mock_tool_block]  # Include both text and tool
        mock_response.stop_reason = "tool_use"
        
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client
        
        # Mock tool execution failure
        self.mock_tool_manager.execute_tool.side_effect = Exception("Tool execution failed")
        
        # Create fresh AI generator
        ai_gen = AIGenerator("test-key", "claude-3-sonnet-20240229")
        
        mock_tools = [{"name": "search_course_content", "description": "Search courses"}]
        
        # Should not raise exception, should return partial response
        result = ai_gen.generate_response_with_sequential_tools(
            query="Search for AI content",
            tools=mock_tools,
            tool_manager=self.mock_tool_manager,
            max_rounds=2
        )
        
        # Should get some response (even if partial)
        self.assertIsInstance(result, str)
        
        # Tool execution was attempted
        self.mock_tool_manager.execute_tool.assert_called_once()
    
    @patch('anthropic.Anthropic')
    def test_max_rounds_enforcement(self, mock_anthropic_class):
        """Test that hard limit of 2 rounds is enforced"""
        mock_client = Mock()
        
        # Mock all responses to request tool usage (would create infinite loop without limit)
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "search_course_content"
        mock_tool_block.id = "tool_call_1"
        mock_tool_block.input = {"query": "test"}
        
        mock_response = Mock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"
        
        mock_text_block = Mock()
        mock_text_block.text = "Final answer after 2 rounds"
        mock_final_response = Mock()
        mock_final_response.content = [mock_text_block]
        
        # Round 1, Round 2, Final call
        mock_client.messages.create.side_effect = [
            mock_response, mock_response, mock_final_response
        ]
        mock_anthropic_class.return_value = mock_client
        
        # Mock tool execution
        self.mock_tool_manager.execute_tool.return_value = "Tool result"
        
        # Create fresh AI generator
        ai_gen = AIGenerator("test-key", "claude-3-sonnet-20240229")
        
        mock_tools = [{"name": "search_course_content", "description": "Search courses"}]
        
        result = ai_gen.generate_response_with_sequential_tools(
            query="Test query",
            tools=mock_tools,
            tool_manager=self.mock_tool_manager,
            max_rounds=2
        )
        
        # Should get final response
        self.assertEqual(result, "Final answer after 2 rounds")
        
        # Should make exactly 2 tool calls (max rounds)
        self.assertEqual(self.mock_tool_manager.execute_tool.call_count, 2)
        
        # Should make exactly 3 API calls (Round 1, Round 2, Final)
        self.assertEqual(mock_client.messages.create.call_count, 3)
    
    @patch('anthropic.Anthropic')
    def test_context_preservation_across_rounds(self, mock_anthropic_class):
        """Test that conversation context is maintained between rounds"""
        mock_client = Mock()
        
        # Mock responses
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "get_course_outline"
        mock_tool_block.id = "tool_1"
        mock_tool_block.input = {"course_name": "AI"}
        
        mock_round_1 = Mock()
        mock_round_1.content = [mock_tool_block]
        mock_round_1.stop_reason = "tool_use"
        
        mock_text_block = Mock()
        mock_text_block.text = "Final answer with context"
        mock_final = Mock()
        mock_final.content = [mock_text_block]
        mock_final.stop_reason = "end_turn"
        
        mock_client.messages.create.side_effect = [mock_round_1, mock_final]
        mock_anthropic_class.return_value = mock_client
        
        # Mock tool execution
        self.mock_tool_manager.execute_tool.return_value = "Course outline result"
        
        # Create fresh AI generator
        ai_gen = AIGenerator("test-key", "claude-3-sonnet-20240229")
        
        mock_tools = [{"name": "get_course_outline", "description": "Get outline"}]
        
        # Test with conversation history
        result = ai_gen.generate_response_with_sequential_tools(
            query="Get AI course info",
            conversation_history="Previous: User asked about ML concepts",
            tools=mock_tools,
            tool_manager=self.mock_tool_manager,
            max_rounds=2
        )
        
        # Verify API calls were made
        self.assertEqual(mock_client.messages.create.call_count, 2)
        
        # Verify system prompts included conversation history
        call_args_list = mock_client.messages.create.call_args_list
        for call_args in call_args_list:
            system_content = call_args.kwargs["system"]
            self.assertIn("Previous conversation", system_content)
            self.assertIn("User asked about ML concepts", system_content)
        
        # Verify messages build up across rounds
        round_2_messages = call_args_list[1].kwargs["messages"]
        self.assertGreater(len(round_2_messages), 1)  # Should have multiple messages
    
    def test_round_aware_system_prompt(self):
        """Test round-aware system prompt generation"""
        ai_gen = AIGenerator("test-key", "test-model")
        
        base_prompt = "Base system prompt"
        
        # Test Round 1
        round_1_prompt = ai_gen._build_round_aware_system_prompt(base_prompt, 1, 2)
        self.assertIn("Current Round: 1 of 2", round_1_prompt)
        self.assertIn("first opportunity", round_1_prompt)
        self.assertIn("Round 2", round_1_prompt)
        
        # Test Round 2 (final)
        round_2_prompt = ai_gen._build_round_aware_system_prompt(base_prompt, 2, 2)
        self.assertIn("Current Round: 2 of 2", round_2_prompt)
        self.assertIn("final round", round_2_prompt)
        self.assertIn("complete final answer", round_2_prompt)
    
    def test_should_continue_rounds_logic(self):
        """Test round continuation decision logic"""
        ai_gen = AIGenerator("test-key", "test-model")
        
        # Mock response with tool use
        mock_response_with_tools = Mock()
        mock_response_with_tools.stop_reason = "tool_use"
        
        # Mock response without tool use
        mock_response_no_tools = Mock()
        mock_response_no_tools.stop_reason = "end_turn"
        
        # Should continue when tool_use and not at max rounds
        self.assertTrue(ai_gen._should_continue_rounds(mock_response_with_tools, 1, 2))
        
        # Should not continue when no tool_use
        self.assertFalse(ai_gen._should_continue_rounds(mock_response_no_tools, 1, 2))
        
        # Should not continue when at max rounds
        self.assertFalse(ai_gen._should_continue_rounds(mock_response_with_tools, 2, 2))


def run_ai_generator_diagnostics():
    """Run comprehensive AIGenerator diagnostics"""
    print("=== AI GENERATOR DIAGNOSTICS ===")
    
    # Check API key configuration
    api_key = config.ANTHROPIC_API_KEY
    if api_key and api_key.strip():
        print(f"✅ API Key: Configured ({len(api_key)} chars)")
    else:
        print("❌ API Key: Missing")
    
    print(f"✅ Model: {config.ANTHROPIC_MODEL}")
    
    print("\nRunning AIGenerator unit tests...")
    suite1 = unittest.TestLoader().loadTestsFromTestCase(TestAIGenerator)
    suite2 = unittest.TestLoader().loadTestsFromTestCase(TestSequentialToolCalling)
    
    # Combine test suites
    combined_suite = unittest.TestSuite([suite1, suite2])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(combined_suite)
    
    success = len(result.failures + result.errors) == 0
    print(f"\n{'✅' if success else '❌'} AIGenerator tests: {result.testsRun - len(result.failures + result.errors)}/{result.testsRun} passed")
    
    if result.failures or result.errors:
        print("\n❌ Test failures/errors found:")
        for test, error in result.failures + result.errors:
            print(f"   - {test}: {error.split(chr(10))[0]}")
    
    return success


if __name__ == "__main__":
    run_ai_generator_diagnostics()