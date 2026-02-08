import requests
import json
from typing import Optional, Dict, Any

class LLMInterface:
    def __init__(self, primary_model: str = "gpt-oss:20b", fallback_model: str = "llama3:8b"):
        self.api_url = "http://localhost:11434/api/generate"
        self.primary_model = primary_model
        self.fallback_model = fallback_model

    def generate_question(self, signal_code: str, signal_message: str, snippet: str) -> str:
        """
        Generates a natural language question based on the signal.
        """
        system_prompt = (
            "당신은 사용자의 사고를 돕는 직관적인 파트너 '소피아'입니다.\n"
            "입력된 구조적 신호(Signal)를 바탕으로, 사용자가 자신의 생각을 명확히 할 수 있도록 '핵심을 찌르는 질문'을 던지세요.\n"
            "허락을 구하거나 주저하는 말투(예: '여쭤봐도 될까요?')는 금지입니다.\n"
            "'이 부분은 왜 그런가요?', '이 단어의 정의는 무엇인가요?'와 같이 단도직입적으로 물어보세요.\n"
            "답변은 오직 질문 하나만 출력하세요."
        )
        
        user_prompt = f"""
        [Signal Info]
        Code: {signal_code}
        Hint: {signal_message}
        Context: "{snippet}"
        
        [Task]
        위 신호를 바탕으로 사용자에게 건넬 질문을 작성하세요.
        """

        response = self._call_ollama(self.primary_model, system_prompt, user_prompt)
        if not response:
            print(f"Primary model {self.primary_model} failed. Trying fallback {self.fallback_model}...")
            response = self._call_ollama(self.fallback_model, system_prompt, user_prompt)
            
        return response or signal_message # Fallback to raw signal message if both fail

    def _call_ollama(self, model: str, system: str, prompt: str) -> Optional[str]:
        payload = {
            "model": model,
            "prompt": f"{system}\n\n{prompt}", # Ollama generate endpoint uses single prompt usually, or template. 
            # Ideally we should use /api/chat if possible for better system prompt handling, 
            # but user specified /api/generate with referencing request example. 
            # I'll stick to simple concatenation or just prompt.
            # Let's try to structure it clearly.
            "stream": False,
            "options": {
                "temperature": 0.7
            }
        }
        
        try:
            res = requests.post(self.api_url, json=payload, timeout=30)
            res.raise_for_status()
            return res.json().get('response', '').strip()
        except Exception as e:
            print(f"LLM Call Failed ({model}): {e}")
            return None
