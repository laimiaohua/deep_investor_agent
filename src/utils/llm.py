"""Helper functions for LLM"""

import json
import os
from typing import Any, List
from pydantic import BaseModel
from langchain_core.messages import SystemMessage
from langchain_core.prompt_values import ChatPromptValue

from src.llm.models import get_model, get_model_info
from src.utils.progress import progress
import json
from src.graph.state import AgentState


def _remove_length_restrictions(content: str) -> str:
    """
    Remove any character/word length restrictions from the prompt content.
    This allows our detailed analysis requirements to take effect.
    """
    import re
    # Remove patterns like "Keep reasoning under X characters", "under X words", etc.
    patterns = [
        r'Keep reasoning under \d+ characters\.?\s*',
        r'Keep reasoning under \d+ words\.?\s*',
        r'under \d+ characters\.?\s*',
        r'under \d+ words\.?\s*',
        r'Keep.*?short\.?\s*',
        r'Keep.*?brief\.?\s*',
        r'Be concise\.?\s*',
        r'Be brief\.?\s*',
    ]
    for pattern in patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    return content


def _inject_language_instruction(prompt: Any, language: str, detail: str):
    """
    Prepend a system instruction to force output language and detail depth.
    Also removes any character length restrictions from the original prompt.
    Supports ChatPromptValue, list of messages, or plain string prompts.
    """
    if language:
        progress.set_language(language)
    if not language and not detail:
        return prompt

    # Build a strong instruction that will be prepended
    instruction_parts = []
    if language:
        # Use stronger language instruction
        if "Chinese" in language or "中文" in language or language.lower() in ["zh", "zh-cn", "zh-tw", "zh_hans", "zh_hant"]:
            instruction_parts.append(
                f"【关键指令 - 语言要求】\n"
                f"你必须完全使用{language}（简体中文或繁体中文）进行回复。\n"
                f"你的回复中的所有文本，包括推理过程、分析内容、信号解释和结论，都必须使用{language}编写。\n"
                f"除了股票代码、数字和金融术语（如P/E、ROE等）外，不得使用任何英文单词。\n"
                f"即使提示词是英文的，你也必须用中文回复。\n"
                f"这是强制要求，必须严格遵守。\n"
                f"\n"
                f"CRITICAL INSTRUCTION - LANGUAGE REQUIREMENT:\n"
                f"You MUST respond ENTIRELY in {language} (Simplified or Traditional Chinese). "
                f"ALL text in your response including reasoning, analysis, signal explanation, and conclusions MUST be written in {language}. "
                f"Do NOT use ANY English words in your response except for ticker symbols, numbers, and financial terms like P/E, ROE, etc. "
                f"Even if the prompt is in English, you MUST respond in Chinese. "
                f"This is a mandatory requirement that must be strictly followed."
            )
        else:
            instruction_parts.append(f"Respond in {language}.")
    
    if detail:
        instruction_parts.append(f"\nDETAILED ANALYSIS REQUIREMENT:\n{detail}")
    
    instruction = "\n".join(instruction_parts)

    # ChatPromptValue -> list[BaseMessage]
    if isinstance(prompt, ChatPromptValue):
        messages = prompt.to_messages()
        for i, msg in enumerate(messages):
            if msg.type == "system":
                # Remove length restrictions from original content
                original_content = _remove_length_restrictions(msg.content)
                # Prepend our instruction
                messages[i] = SystemMessage(content=f"{instruction}\n\n{original_content}")
                return messages
        # No system message found, insert at beginning
        messages.insert(0, SystemMessage(content=instruction))
        return messages

    # list of messages
    if isinstance(prompt, list):
        for i, msg in enumerate(prompt):
            if hasattr(msg, 'type') and msg.type == "system":
                # Remove length restrictions from original content
                original_content = _remove_length_restrictions(msg.content)
                prompt[i] = SystemMessage(content=f"{instruction}\n\n{original_content}")
                return prompt
        # No system message found, prepend new one
        return [SystemMessage(content=instruction)] + prompt

    # plain string
    if isinstance(prompt, str):
        # Remove length restrictions from original content
        prompt = _remove_length_restrictions(prompt)
        return f"{instruction}\n\n{prompt}"

    return prompt


def call_llm(
    prompt: Any,
    pydantic_model: type[BaseModel],
    agent_name: str | None = None,
    state: AgentState | None = None,
    max_retries: int = 3,
    default_factory=None,
    enable_streaming: bool = True,
    ticker: str | None = None,
) -> BaseModel:
    """
    Makes an LLM call with retry logic, handling both JSON supported and non-JSON supported models.

    Args:
        prompt: The prompt to send to the LLM
        pydantic_model: The Pydantic model class to structure the output
        agent_name: Optional name of the agent for progress updates and model config extraction
        state: Optional state object to extract agent-specific model configuration
        max_retries: Maximum number of retries (default: 3)
        default_factory: Optional factory function to create default response on failure
        enable_streaming: Whether to enable streaming output (default: True)
        ticker: Optional ticker symbol for progress updates

    Returns:
        An instance of the specified Pydantic model
    """
    
    # Extract model configuration if state is provided and agent_name is available
    if state and agent_name:
        model_name, model_provider = get_agent_model_config(state, agent_name)
        print(f"[LLM] Config for {agent_name}: model={model_name}, provider={model_provider}")
    else:
        # Use system defaults when no state or agent_name is provided
        # Prefer DeepSeek if API key is configured; otherwise fall back to OpenAI
        import os
        if os.getenv("DEEPSEEK_API_KEY"):
            model_name = "deepseek-chat"
            model_provider = "DeepSeek"
            print("[LLM] No model specified; using DeepSeek by default (DEEPSEEK_API_KEY is set)")
        else:
            model_name = "gpt-4.1"
            model_provider = "OPENAI"
            print("[LLM] No model specified; using OpenAI by default")

    # Extract API keys from state if available
    api_keys = None
    if state:
        request = state.get("metadata", {}).get("request")
        if request and hasattr(request, 'api_keys'):
            api_keys = request.api_keys

    model_info = get_model_info(model_name, model_provider)
    llm = get_model(model_name, model_provider, api_keys)

    # Inject language and detail requirement
    language = None
    detail = None
    if state:
        metadata = state.get("metadata", {}) or {}
        language = metadata.get("language")
        # Build detailed reasoning requirement based on language
        default_detail = metadata.get("reasoning_detail")
        if not default_detail:
            if language and ("Chinese" in language or "中文" in language):
                default_detail = (
                    "请提供详细的分析推理过程，包括：\n"
                    "1. 关键财务指标和具体数据（如市盈率、净利润率、营收增长率等）\n"
                    "2. 投资优势和风险因素\n"
                    "3. 估值分析和内在价值判断\n"
                    "4. 行业地位和竞争优势分析\n"
                    "5. 明确的投资结论和理由\n"
                    "分析内容需要具体、有数据支撑，不少于200字。"
                )
            else:
                default_detail = (
                    "Provide detailed reasoning including:\n"
                    "1. Key financial metrics with specific numbers (P/E ratio, profit margins, revenue growth, etc.)\n"
                    "2. Investment strengths and risk factors\n"
                    "3. Valuation analysis and intrinsic value assessment\n"
                    "4. Industry position and competitive advantages\n"
                    "5. Clear investment conclusion with supporting rationale\n"
                    "Analysis should be thorough, data-driven, and at least 200 words."
                )
        detail = default_detail
    # Debug log to verify language is being passed
    if language:
        print(f"[LLM] Language set to: {language}")
    
    prompt = _inject_language_instruction(prompt, language, detail)

    # Call the LLM with retries
    for attempt in range(max_retries):
        try:
            # Check if streaming is enabled and model supports it
            if enable_streaming and agent_name and ticker:
                # Use streaming for better UX (do NOT use structured output for streaming)
                print(f"[LLM] Starting streaming call for {agent_name}, ticker: {ticker}")
                result = _call_llm_with_streaming(
                    llm, prompt, pydantic_model, agent_name, ticker, model_info
                )
                print(f"[LLM] Streaming call completed for {agent_name}")
                # 流式调用返回的 result 已经是 pydantic 模型实例，直接返回
                if isinstance(result, pydantic_model):
                    return result
                # 如果不是模型实例，说明解析失败，继续重试逻辑
                raise ValueError("Streaming call did not return a valid model instance")
            else:
                # Use structured output for non-streaming calls
                print(f"[LLM] Using non-streaming call (streaming: {enable_streaming}, agent: {agent_name}, ticker: {ticker})")
                llm_with_structure = llm
                if not (model_info and not model_info.has_json_mode()):
                    llm_with_structure = llm.with_structured_output(
                        pydantic_model,
                        method="json_mode",
                    )
                result = llm_with_structure.invoke(prompt)

            # For non-JSON support models, we need to extract and parse the JSON manually
            # 注意：这里 result 可能是模型实例（structured output）或消息对象（普通调用）
            if isinstance(result, pydantic_model):
                # 如果已经是模型实例，直接返回
                return result
            elif hasattr(result, 'content'):
                # 如果是消息对象，提取 content 并解析
                if model_info and not model_info.has_json_mode():
                    parsed_result = extract_json_from_response(result.content)
                    if parsed_result:
                        return pydantic_model(**parsed_result)
                    else:
                        # If JSON parsing failed, raise an exception to trigger retry
                        error_msg = f"Failed to extract JSON from response. Response content: {result.content[:500]}"
                        print(f"JSON extraction failed: {error_msg}")
                        if attempt == max_retries - 1:
                            raise ValueError(error_msg)
                        continue  # Retry
                else:
                    # JSON mode supported, try to parse directly
                    try:
                        return pydantic_model(**result.content) if isinstance(result.content, dict) else pydantic_model.model_validate_json(result.content)
                    except Exception as e:
                        error_msg = f"Failed to parse response as {pydantic_model.__name__}: {str(e)}"
                        print(f"Parsing failed: {error_msg}")
                        if attempt == max_retries - 1:
                            raise ValueError(error_msg)
                        continue  # Retry
            else:
                # 未知类型，尝试直接返回
                return result

        except Exception as e:
            if agent_name:
                progress.update_status(agent_name, None, f"Error - retry {attempt + 1}/{max_retries}")

            if attempt == max_retries - 1:
                print(f"Error in LLM call after {max_retries} attempts: {e}")
                # Use default_factory if provided, otherwise create a basic default
                if default_factory:
                    return default_factory()
                return create_default_response(pydantic_model)

    # This should never be reached due to the retry logic above
    return create_default_response(pydantic_model)


def create_default_response(model_class: type[BaseModel]) -> BaseModel:
    """Creates a safe default response based on the model's fields."""
    default_values = {}
    for field_name, field in model_class.model_fields.items():
        if field.annotation == str:
            default_values[field_name] = "Error in analysis, using default"
        elif field.annotation == float:
            default_values[field_name] = 0.0
        elif field.annotation == int:
            default_values[field_name] = 0
        elif hasattr(field.annotation, "__origin__") and field.annotation.__origin__ == dict:
            default_values[field_name] = {}
        else:
            # For other types (like Literal), try to use the first allowed value
            if hasattr(field.annotation, "__args__"):
                default_values[field_name] = field.annotation.__args__[0]
            else:
                default_values[field_name] = None

    return model_class(**default_values)


def _call_llm_with_streaming(
    llm: Any,
    prompt: Any,
    pydantic_model: type[BaseModel],
    agent_name: str,
    ticker: str,
    model_info: Any = None
) -> BaseModel:
    """
    调用 LLM 并启用流式输出，实时显示生成过程。
    
    Args:
        llm: LLM 实例
        prompt: 提示词
        pydantic_model: 输出模型
        agent_name: 智能体名称
        ticker: 股票代码
        model_info: 模型信息
    
    Returns:
        结构化的模型输出
    """
    try:
        print(f"[LLM] Starting streaming for {agent_name}, ticker: {ticker}")
        # 使用 stream 方法获取流式输出
        full_content = ""
        chunk_count = 0
        # 完全关闭详细的流式进度日志，只保留开始和完成日志
        # 前端已经通过 SSE 实时更新了，不需要后端日志
        
        for chunk in llm.stream(prompt):
            chunk_count += 1
            # 首先检查是否是 pydantic 模型实例（必须在检查 content 之前）
            if isinstance(chunk, pydantic_model):
                print(f"[LLM] Received structured output directly, chunks: {chunk_count}")
                return chunk
            
            # 从 chunk 中提取内容
            content = None
            if isinstance(chunk, str):
                content = chunk
            elif isinstance(chunk, dict):
                content = chunk.get('content')
            elif hasattr(chunk, 'content'):
                # 确保不是 pydantic 模型（已经检查过了）
                try:
                    content = chunk.content
                except AttributeError:
                    # 如果访问 content 失败，跳过这个 chunk
                    continue
            
            if not content:
                continue
            
                full_content += content
            # 通过 progress 发送流式更新（不输出日志）
                progress.update_streaming_content(agent_name, ticker, content)
        
        # 流式输出完成，解析完整内容
        if model_info and not model_info.has_json_mode():
            # 手动解析 JSON
            parsed_result = extract_json_from_response(full_content)
            if parsed_result:
                return pydantic_model(**parsed_result)
            else:
                # 如果无法解析，fallback 到 invoke
                print("[LLM] Stream parse failed, using invoke as fallback")
                return llm.invoke(prompt)
        else:
            # 尝试解析完整输出
            parsed_result = extract_json_from_response(full_content)
            if parsed_result:
                return pydantic_model(**parsed_result)
            else:
                # Fallback: 使用非流式调用
                print("[LLM] Stream output incomplete, using invoke as fallback")
                return llm.invoke(prompt)
                
    except Exception as e:
        # 流式调用失败，fallback 到常规调用
        print(f"[LLM] Streaming failed: {e}, falling back to regular invoke")
        return llm.invoke(prompt)


def extract_json_from_response(content: str) -> dict | None:
    """Extracts JSON from markdown-formatted response."""
    if not content:
        return None
    
    try:
        # Try to find JSON in markdown code blocks first
        json_start = content.find("```json")
        if json_start != -1:
            json_text = content[json_start + 7 :]  # Skip past ```json
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                return json.loads(json_text)
        
        # Try to find JSON in plain code blocks
        json_start = content.find("```")
        if json_start != -1:
            json_text = content[json_start + 3 :]  # Skip past ```
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                try:
                    return json.loads(json_text)
                except:
                    pass
        
        # Try to find JSON object directly in the content
        # Look for { ... } pattern
        brace_start = content.find("{")
        if brace_start != -1:
            # Find the matching closing brace
            brace_count = 0
            for i in range(brace_start, len(content)):
                if content[i] == "{":
                    brace_count += 1
                elif content[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_text = content[brace_start:i+1]
                        try:
                            return json.loads(json_text)
                        except:
                            pass
        
        # Last resort: try to parse the entire content as JSON
        try:
            return json.loads(content.strip())
        except:
            pass
            
    except Exception as e:
        print(f"Error extracting JSON from response: {e}")
        print(f"Response content (first 500 chars): {content[:500]}")
    
    return None


def get_agent_model_config(state, agent_name):
    """
    Get model configuration for a specific agent from the state.
    Falls back to global model configuration if agent-specific config is not available.
    Always returns valid model_name and model_provider values.
    """
    request = state.get("metadata", {}).get("request")
    
    if request and hasattr(request, 'get_agent_model_config'):
        # Get agent-specific model configuration
        model_name, model_provider = request.get_agent_model_config(agent_name)
        # Ensure we have valid values
        if model_name and model_provider:
            provider_str = model_provider.value if hasattr(model_provider, 'value') else str(model_provider)
            print(f"[LLM] Agent-specific config for {agent_name}: {model_name}, {provider_str}")
            return model_name, provider_str
    
    # Fall back to global configuration from metadata
    model_name = state.get("metadata", {}).get("model_name")
    model_provider = state.get("metadata", {}).get("model_provider")
    
    print(f"[LLM] Global config from metadata for {agent_name}: model_name={model_name}, model_provider={model_provider}")
    
    # Treat None, empty string, or "None" string as not configured
    if not model_name or model_name == "None":
        model_name = None
    if not model_provider or model_provider == "None" or model_provider == "OPENAI":
        model_provider = None
    
    # If no valid global config, use intelligent defaults based on available API keys
    if not model_name or not model_provider:
        import os
        # Check available API keys and use the first available one
        if os.getenv("DEEPSEEK_API_KEY") and (not model_provider or model_provider != "OPENAI"):
            model_name = model_name or "deepseek-chat"
            model_provider = "DeepSeek"
            print(f"[LLM] ✓ Using DeepSeek for {agent_name}: {model_name}")
        elif os.getenv("ANTHROPIC_API_KEY") and (not model_provider or model_provider != "OPENAI"):
            model_name = model_name or "claude-sonnet-4-5-20250929"
            model_provider = "Anthropic"
            print(f"[LLM] ✓ Using Anthropic for {agent_name}: {model_name}")
        elif os.getenv("GROQ_API_KEY") and (not model_provider or model_provider != "OPENAI"):
            model_name = model_name or "llama-3.3-70b-versatile"
            model_provider = "Groq"
            print(f"[LLM] ✓ Using Groq for {agent_name}: {model_name}")
        else:
            # Final fallback to OpenAI (may fail if no key)
            model_name = model_name or "gpt-4.1"
            model_provider = "OPENAI"
            print(f"[LLM] ⚠ Falling back to OpenAI for {agent_name}: {model_name} (may fail if no key)")
    
    # Convert enum to string if necessary
    if hasattr(model_provider, 'value'):
        model_provider = model_provider.value
    
    print(f"[LLM] Final config for {agent_name}: {model_name}, {model_provider}")
    return model_name, model_provider
