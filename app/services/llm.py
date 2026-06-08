
import json
import logging

import httpx
from openai import OpenAI

import app.core.logging
from app.core.config import COMPANY_NAME, OPENAI_API_KEY, OPENAI_MODEL
from app.prompts.loader import render_prompt
from app.services.tools import call_tool
from app.schemas.tools import TOOLS



# настройка клиента OpenAI
# client = OpenAI(api_key=OPENAI_API_KEY)

client = OpenAI(
    api_key=OPENAI_API_KEY,
    http_client=httpx.Client(trust_env=False),
)

def log_event(event: str, data: dict) -> None:
    # Создаем словарь с названием события и данными события.
    log_data = {
        "event": event,
        "data": data,
    }

    # Превращаем словарь Python в JSON-строку.
    log_message = json.dumps(log_data, ensure_ascii=False)

    # Записываем JSON-строку в файл логов assistant.log.
    logging.info(log_message)
    
# главная функция для общения с LLM
def ask_assistant(user_input: str) -> str:
    system_prompt = render_prompt(
        "system_v1.j2", 
        company_name=COMPANY_NAME,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]
    
    log_event("user_input", {"input": user_input})
    
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        tools=TOOLS,
    )
    
    assistant_message = response.choices[0].message
    
    while assistant_message.tool_calls: # если ассистент решил вызвать инструмент, то выполняем его и отправляем результат обратно ассистенту
        messages.append(assistant_message)
        
        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            tool_arguments = json.loads(tool_call.function.arguments)
            
            log_event(
                "tool_call", 
                {
                    "name": tool_name, 
                    "arguments": tool_arguments,
                }
            )
            
            tool_result = call_tool(tool_name, tool_arguments)
            
            log_event(
                "tool_result", 
                {
                    "name": tool_name, 
                    "result": tool_result,
                }
            )
            
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=TOOLS,
        )
        
        assistant_message = response.choices[0].message
        
    final_answer = assistant_message.content or ""
    
    log_event(
        "final_answer",
        {
            "text": final_answer,
            "total_tokens": response.usage.total_tokens if response.usage else None
        }
    )   
    
    return final_answer
    


