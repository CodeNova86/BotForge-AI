import logging
import sys
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from typing import TypedDict
from tools import read_file, run_python, write_file, run_terminal
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# ============================================================
# LOGGING SETUP
# ============================================================
# Create a file handler for detailed logs
file_handler = logging.FileHandler("agent_core.log", mode="a", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)

# Create a stderr handler for important messages (won't interfere with input())
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.INFO)
stderr_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
stderr_handler.setFormatter(stderr_formatter)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[file_handler, stderr_handler]
)

logger = logging.getLogger("AgentCore")

# Reduce noise from third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("langgraph").setLevel(logging.INFO)
logging.getLogger("tools").setLevel(logging.INFO)


# ============================================================
# LLM & TOOLS SETUP
# ============================================================
llm = ChatOpenAI(
    model="nvidia/nemotron-3-ultra-550b-a55b",
    base_url="https://integrate.api.nvidia.com/v1",
    api_key="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",
    temperature=0.1,
)

tools = [read_file, run_python, write_file, run_terminal]
llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)

logger.info("LLM and tools initialized successfully")


# ============================================================
# GRAPH NODES
# ============================================================
def call_model(state: MessagesState):
    """Invoke the LLM with the current message history."""
    logger.debug(f"Calling model with {len(state['messages'])} messages in history")
    
    # Log the last user message for context
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            logger.info(f"User message: {msg.content[:200]}...")
            break
    
    response = llm_with_tools.invoke(state["messages"])
    
    # Log tool calls if any
    if response.tool_calls:
        for tc in response.tool_calls:
            logger.info(f"Tool call: {tc['name']}({tc['args']})")
    else:
        logger.debug(f"Model response (no tool calls): {response.content[:200]}...")
    
    return {"messages": [response]}


def should_continue(state: MessagesState):
    """Decide whether to continue to tools or end."""
    last_message = state["messages"][-1]
    
    if last_message.tool_calls:
        logger.debug("Tool calls detected -> routing to tools node")
        return "tools"
    
    logger.debug("No tool calls -> ending turn")
    return END


# ============================================================
# BUILD GRAPH
# ============================================================
graph = StateGraph(MessagesState)
graph.add_node("model", call_model)
graph.add_node("tools", tool_node)
graph.add_edge(START, "model")
graph.add_conditional_edges("model", should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "model")
app = graph.compile()

logger.info("Graph compiled and ready")


# ============================================================
# CONVERSATION LOOP
# ============================================================
def run_conversation():
    """Run an interactive conversation loop with history."""
    print("\n" + "=" * 60, flush=True)
    print("  Agent Core - Interactive Conversation", flush=True)
    print("  Type 'exit', 'quit', or 'q' to end", flush=True)
    print("  Type 'clear' to reset conversation history", flush=True)
    print("=" * 60 + "\n", flush=True)
    
    # This will hold the entire conversation history
    conversation_history = []
    turn_count = 0
    
    while True:
        try:
            # Get user input - using sys.stdin directly to avoid buffering issues
            user_input = input(f"\n[Turn {turn_count + 1}] You: ").strip()
            
            # Handle special commands
            if user_input.lower() in ("exit", "quit", "q"):
                logger.info("User requested exit")
                print("\nGoodbye!", flush=True)
                break
            
            if user_input.lower() == "clear":
                conversation_history = []
                turn_count = 0
                logger.info("Conversation history cleared by user")
                print("\n[History cleared]", flush=True)
                continue
            
            if not user_input:
                continue
            
            # Add user message to history
            conversation_history.append(HumanMessage(content=user_input))
            logger.info(f"Turn {turn_count + 1} - User: {user_input[:100]}...")
            
            # Invoke the graph with FULL conversation history
            logger.debug(f"Invoking graph with {len(conversation_history)} messages")
            result = app.invoke({"messages": conversation_history})
            
            # Update conversation history with the complete result
            # The result contains all messages including tool calls and responses
            conversation_history = result["messages"]
            turn_count += 1
            
            # Print the final AI response (last message that isn't a tool call)
            final_response = None
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage) and not msg.tool_calls:
                    final_response = msg.content
                    break
                elif isinstance(msg, HumanMessage):
                    # We've gone back past the AI response
                    break
            
            if final_response:
                print(f"\nAssistant: {final_response}", flush=True)
                logger.info(f"Turn {turn_count} - Assistant: {final_response[:200]}...")
            else:
                print("\nAssistant: [No text response generated]", flush=True)
                logger.warning("No final AI message found in result")
                
        except KeyboardInterrupt:
            logger.info("Interrupted by user (Ctrl+C)")
            print("\n\nInterrupted. Goodbye!", flush=True)
            break
        except Exception as e:
            logger.exception(f"Error during conversation: {e}")
            print(f"\n[Error] {e}", flush=True)
            # Don't break - let the user continue


if __name__ == "__main__":
    logger.info("Starting Agent Core conversation loop")
    run_conversation()
    logger.info("Agent Core session ended")