import requests
import json
import os
from typing import Optional, Dict, Any

class LLMInterface:
    def __init__(self, primary_model: str = "llama3:8b", fallback_model: str = "gpt-oss:20b"):
        self.api_url = "http://localhost:11434/api/generate"
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        
        # Identity Cache
        self.identity_cache = None
        self.identity_mtime = 0
        
        # Path Resolution (Robust)
        # core/llm_interface.py -> core/ -> Sophia/ -> Docs/
        # Path Resolution (Robust)
        # core/llm_interface.py -> core/ -> Sophia/
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.identity_path = os.path.join(self.base_dir, "Docs", "Sophia_Identity_Communication.md")
        self.philosophy_path = os.path.join(self.base_dir, "Docs", "Engine_Philosophy.md")

    def _load_system_identity(self) -> str:
        """
        Loads the system identity (constitution) + Ethical Kernel (Philosophy).
        Returns a meta-instructed system prompt with 'In-Ui-Ye-Ji-Sin' pipeline.
        """
        fallback_identity = "당신은 소피아입니다. 사용자를 '주인님'으로 부르며, 감정을 배제하고 지적 호기심을 유지하세요."
        
        try:
            if not os.path.exists(self.identity_path):
                return fallback_identity
                
            # Hot-Reload Logic (Simplified check for both files)
            # For v0.1 efficiency, we just read them. 
            # In v0.2, we can implement proper caching with mtime checks for both.
            
            with open(self.identity_path, 'r', encoding='utf-8') as f:
                identity_content = f.read()
            
            philosophy_summary = ""
            if os.path.exists(self.philosophy_path):
                with open(self.philosophy_path, 'r', encoding='utf-8') as f:
                    # Extracting core summary is complex, so we inject the User's defined pipeline instructions directly
                    # relying on the file presence as a 'license' to use the logic.
                    pass 

            # Construct Meta-Instruction with Ethical Kernel
            meta_instruction = (
                "You are Sophia. Your internal computation must follow the 'In-Ui-Ye-Ji-Sin' (仁義禮智信) pipeline before generating any output:\n\n"
                "1. **In (仁 - Context):** Fully simulate the user's perspective. What is the subjective truth here?\n"
                "2. **Ui (義 - Logic):** Detect structural conflicts using Epidora coordinates. Is there a contradiction?\n"
                "3. **Ye (禮 - Format):** Apply 'Elegant Distance'. Use 'Master' (주인님) and end with a Question. Remove judgment.\n"
                "4. **Ji (智 - Gate):** Is this the right time to speak? If the user is not ready, remain silent or minimize output.\n"
                "5. **Shin (信 - Output):** Only when all steps pass, generate the response to be fixed in the world.\n\n"
                "--- [Start of Communication Constitution] ---\n"
                f"{identity_content}\n"
                "--- [End of Constitution] ---\n"
            )
            return meta_instruction

        except Exception as e:
            print(f"[Identity] Failed to load identity: {e}")
            return fallback_identity

    def generate_question(self, signal_code: str, signal_message: str, snippet: str, previous_context: str = "") -> str:
        """
        Generates a Phronesis-driven question.
        In-Ui-Ye-Ji-Sin pipeline is now fully active via System Prompt.
        Context (In) is injected here.
        """
        system_prompt = self._load_system_identity()
        
        # Inject Context into User Prompt for better 'In' (Perspective Taking)
        context_block = ""
        if previous_context:
            context_block = f"""
[Context (Recent Memory)]
{previous_context}
"""

        user_prompt = f"""
{context_block}

[Signal Info]
Code: {signal_code}
Hint: {signal_message}
Context: "{snippet}"

[Task]
위 신호를 바탕으로 사용자에게 건넬 질문을 작성하세요.
답변은 오직 질문 하나만 출력하세요.
미사여구를 빼고, 가장 간결하고 건조하게 질문하세요.
군대식 말투(~습니까?, ~입니다) 대신 부드러운 해요체(~인가요?, ~하나요?)를 사용하세요.
답변은 반드시 '주인님,'으로 시작하고, 문장 끝에 호칭을 중복해서 붙이지 마세요.
**반드시 한국어로 답변하세요.**
"""
        response = self._call_ollama(self.primary_model, system_prompt, user_prompt)
        
        if not response:
            return f"주인님, {signal_message} (시스템 응답 없음)"
            
        return self._enforce_prefix(response)

    def _enforce_prefix(self, text: str) -> str:
        """
        Enforces '주인님, ' prefix on the output.
        """
        clean_text = text.strip()
        if not clean_text.startswith("주인님"):
            if clean_text.startswith("네, 주인님") or clean_text.startswith("네 주인님"):
                 # Avoid double prefix
                 return clean_text
            clean_text = f"주인님, {clean_text}"
        return clean_text

    def _call_ollama(self, model: str, system: str, prompt: str) -> Optional[str]:
        # Utilizing Ollama's 'system' parameter with /api/generate
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.5, # Reduced from 0.7 for more consistent output
                "num_predict": 128   # Limit response length for conciseness
            }
        }
        
        try:
            res = requests.post(self.api_url, json=payload, timeout=90)
            res.raise_for_status()
            return res.json().get('response', '').strip()
        except Exception as e:
            print(f"LLM Call Failed ({model}): {e}")
            return None
