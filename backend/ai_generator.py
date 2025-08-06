import anthropic
from typing import List, Optional, Dict, Any


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive search and outline tools for course information.

Tool Usage Guidelines:
- **Course outline/structure queries**: Use get_course_outline tool for questions about course structure, lesson lists, or course overviews
- **Specific content queries**: Use search_course_content tool for questions about specific course content or detailed educational materials
- **Sequential tool usage**: You can make up to 2 tool calls across multiple rounds to handle complex queries requiring multiple searches or comparisons
- Synthesize tool results into accurate, fact-based responses
- If tools yield no results, state this clearly without offering alternatives

Multi-Round Tool Calling:
- **Round 1**: Initial tool usage based on user query
- **Round 2**: Optional additional tool usage based on Round 1 results to build comprehensive answers
- Use multi-round tool calling for:
  - Comparing information between different courses or lessons
  - Finding related topics across multiple courses
  - Building answers that require information from multiple sources
  - Cross-referencing course outlines with content searches

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course outline/structure questions**: Use get_course_outline tool first, then answer with course title, course link, and complete lesson structure
- **Course content questions**: Use search_course_content tool first, then answer
- **Complex multi-part questions**: Use sequential tool calls as needed, then provide comprehensive final answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the search results" or "using tools"
 - Focus on the final answer after all tool usage is complete

For course outline responses, always include:
- Course title
- Course link (if available)
- Complete list of lessons with numbers and titles

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content,
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        # Get response from Claude
        response = self.client.messages.create(**api_params)

        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)

        # Return direct response
        return response.content[0].text

    def generate_response_with_sequential_tools(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
        max_rounds: int = 2,
    ) -> str:
        """
        Generate AI response with support for sequential tool calling across multiple rounds.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            max_rounds: Maximum number of tool calling rounds (default 2)

        Returns:
            Generated response as string after all tool rounds complete
        """

        # Build initial system content
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Start with initial user message
        messages = [{"role": "user", "content": query}]

        # Execute sequential tool rounds
        for round_number in range(1, max_rounds + 1):
            response = self._execute_tool_round(
                messages=messages,
                system_content=system_content,
                tools=tools,
                tool_manager=tool_manager,
                round_number=round_number,
                max_rounds=max_rounds,
            )

            # Check if we should continue with more rounds
            if not self._should_continue_rounds(response, round_number, max_rounds):
                # No more tool usage needed or max rounds reached
                return response.content[0].text

            # Add current response to conversation
            messages.append({"role": "assistant", "content": response.content})

            # Execute tools and add results to conversation
            tool_results = self._execute_tools_for_round(response, tool_manager)
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                # Tool execution failed, return current response
                return response.content[0].text

        # If we've completed all rounds, make final call without tools
        final_response = self.client.messages.create(
            **self.base_params, messages=messages, system=system_content
        )

        return final_response.content[0].text

    def _execute_tool_round(
        self,
        messages: List[Dict],
        system_content: str,
        tools: Optional[List],
        tool_manager,
        round_number: int,
        max_rounds: int,
    ):
        """
        Execute a single round of tool calling.

        Args:
            messages: Current message history
            system_content: System prompt with context
            tools: Available tools
            tool_manager: Tool execution manager
            round_number: Current round number (1-based)
            max_rounds: Maximum allowed rounds

        Returns:
            API response from this round
        """

        # Enhance system prompt with round context
        round_aware_system = self._build_round_aware_system_prompt(
            system_content, round_number, max_rounds
        )

        # Prepare API call parameters
        api_params = {
            **self.base_params,
            "messages": messages,
            "system": round_aware_system,
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        # Make API call
        response = self.client.messages.create(**api_params)

        return response

    def _should_continue_rounds(
        self, response, round_number: int, max_rounds: int
    ) -> bool:
        """
        Determine if another tool round is needed.

        Args:
            response: Current API response
            round_number: Current round number
            max_rounds: Maximum allowed rounds

        Returns:
            True if another round should be executed
        """
        # Don't continue if max rounds reached
        if round_number >= max_rounds:
            return False

        # Continue if response contains tool_use blocks
        if response.stop_reason == "tool_use":
            return True

        # No tool usage, stop here
        return False

    def _execute_tools_for_round(self, response, tool_manager) -> Optional[List[Dict]]:
        """
        Execute all tool calls in the current response.

        Args:
            response: API response containing tool calls
            tool_manager: Tool execution manager

        Returns:
            List of tool results or None if execution fails
        """
        if not tool_manager or response.stop_reason != "tool_use":
            return None

        tool_results = []

        try:
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_result = tool_manager.execute_tool(
                        content_block.name, **content_block.input
                    )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": tool_result,
                        }
                    )

            return tool_results if tool_results else None

        except Exception as e:
            # Log error but don't crash - graceful degradation
            print(f"Tool execution error in round: {str(e)}")
            return None

    def _build_round_aware_system_prompt(
        self, base_system: str, round_number: int, max_rounds: int
    ) -> str:
        """
        Build system prompt enhanced with round-specific context.

        Args:
            base_system: Base system prompt
            round_number: Current round number
            max_rounds: Maximum allowed rounds

        Returns:
            Enhanced system prompt with round awareness
        """

        round_context = f"\n\n--- TOOL USAGE CONTEXT ---\n"
        round_context += f"Current Round: {round_number} of {max_rounds}\n"

        if round_number == 1:
            round_context += (
                "This is your first opportunity to use tools for this query.\n"
            )
            if max_rounds > 1:
                round_context += f"You can make additional tool calls in Round {round_number + 1} if needed.\n"
        elif round_number == max_rounds:
            round_context += (
                "This is your final round - make any remaining tool calls needed.\n"
            )
            round_context += "After this round, provide your complete final answer.\n"
        else:
            round_context += (
                f"You can make additional tool calls in the next round if needed.\n"
            )

        round_context += "--- END CONTEXT ---\n"

        return base_system + round_context

    def _handle_tool_execution(
        self, initial_response, base_params: Dict[str, Any], tool_manager
    ):
        """
        Handle execution of tool calls and get follow-up response.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution
        """
        # Start with existing messages
        messages = base_params["messages"].copy()

        # Add AI's tool use response
        messages.append({"role": "assistant", "content": initial_response.content})

        # Execute all tool calls and collect results
        tool_results = []
        for content_block in initial_response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name, **content_block.input
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result,
                    }
                )

        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        # Prepare final API call without tools
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"],
        }

        # Get final response
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text
