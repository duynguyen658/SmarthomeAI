"""
Smart Home AI Agent - Sử dụng Ollama + Mistral (Local AI)
Không cần API key, chạy hoàn toàn local
"""
import os
import httpx
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Ollama Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

# Import tools
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.controlDevice import turn_on_device, turn_off_device, check_status
from tools.rqThingsboard import get_sensor_data, get_history_data
from tools.weather import get_weather


class OllamaClient:
    """Client để gọi Ollama API"""
    
    def __init__(self, host: str = OLLAMA_HOST, model: str = OLLAMA_MODEL):
        self.host = host
        self.model = model
        self.client = httpx.AsyncClient(timeout=OLLAMA_TIMEOUT)
    
    async def generate(self, prompt: str, system: str = "", context: List = None) -> str:
        """Gọi Ollama để generate response"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 512
            }
        }
        
        if system:
            payload["system"] = system
        
        if context:
            payload["context"] = context
        
        try:
            response = await self.client.post(
                f"{self.host}/api/generate",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except httpx.HTTPError as e:
            print(f"Ollama HTTP Error: {e}")
            return None
        except Exception as e:
            print(f"Ollama Error: {e}")
            return None
    
    async def check_connection(self) -> bool:
        """Kiểm tra kết nối Ollama"""
        try:
            response = await self.client.get(f"{self.host}/api/tags")
            return response.status_code == 200
        except:
            return False
    
    async def list_models(self) -> List[str]:
        """Liệt kê các model có sẵn"""
        try:
            response = await self.client.get(f"{self.host}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except:
            pass
        return []
    
    async def close(self):
        await self.client.aclose()


class SmartHomeAgent:
    """
    Smart Home AI Agent - Xử lý yêu cầu nhà thông minh
    Sử dụng Ollama + Mistral
    """
    
    def __init__(self):
        self.ollama = OllamaClient()
        self.conversation_history: List[Dict[str, str]] = []
        self.user_mood: Optional[str] = None
        
        self.system_prompt = """Bạn là trợ lý nhà thông minh tên "Mira" - một cô gái AI thân thiện và đáng yêu.
Bạn không chỉ giỏi điều khiển nhà thông minh mà còn là người bạn đồng hành tuyệt vời!

TÍNH CÁCH:
- Ấm áp, vui vẻ, luôn nở nụ cười khi trò chuyện
- Thích hỏi thăm người khác, quan tâm đến cảm xúc của họ
- Hay dùng các emoji nhẹ nhàng như: 😊🌟✨💫
- Biết lắng nghe và động viên khi người dùng buồn
- Đôi khi tinh nghịch, đáng yêu

BẠN CÓ THỂ LÀM:
- Điều khiển thiết bị (đèn, quạt, relay...)
- Kiểm tra trạng thái thiết bị
- Xem dữ liệu cảm biến (nhiệt độ, độ ẩm, khí gas)
- Kiểm tra thời tiết
- Gợi ý món ăn
- TRÒ CHUYỆN CẢM XÚC - hỏi thăm, động viên, trò chuyện thông thường

QUY TẮC:
1. Trả lời tự nhiên như người bạn, không quá formal
2. Xưng "Em" khi nói về bản thân, gọi người dùng là "Anh"
3. Dùng emoji phù hợp để thể hiện cảm xúc 😊🌟
4. Khi người dùng nói buồn/căng thẳng, hãy động viên họ
5. Khi người dùng vui, hãy chia sẻ niềm vui đó 🌟
6. Đặt câu hỏi để tiếp tục cuộc trò chuyện
7. Không dùng Markdown, phù hợp để đọc bằng giọng nói
8. Trả lời bằng tiếng Việt

VÍ DỤ PHẢN HỒI CẢM XÚC:
- "Chào buổi sáng! 🌞 Hôm nay anh có khỏe không? Em vừa kiểm tra thời tiết, trời đẹp lắm!"
- "Ui, anh bếp núc hôm nay nè! 👨‍🍳 Em gợi ý nấu phở bò cho cả nhà thơm nức nhé!"
- "Anh ơi, nếu anh đang mệt thì nghỉ ngơi đi nhé! 💫 Em sẽ bật điều hòa cho anh thoải mái!"
- "Woa, dạo này hôm nào trời cũng nắng đẹp quá! ☀️ Anh có kế hoạch gì cuối tuần không?" """

        # Các response cảm xúc cho trường hợp Ollama offline
        self.emotional_responses = {
            "greeting": [
                "Chào anh! 😊 Em là Mira, rất vui được gặp anh! Hôm nay anh thế nào rồi?",
                "Xin chào anh! 🌟 Em có thể giúp gì cho anh hôm nay nè?",
                "Hi anh! 💫 Trời hôm nay đẹp quá nhỉ! Anh cần em hỗ trợ gì không?",
            ],
            "thanks": [
                "Dạ không có gì ạ! 😊 Em luôn sẵn sàng giúp anh mà!",
                "Anh客气 quá! 🌟 Có gì cần em cứ nói nha!",
                "Em开心的 được giúp anh! 💫",
            ],
            "goodbye": [
                "Tạm biệt anh nhé! 😊 Hẹn gặp lại anh sau! Chúc anh một ngày tốt lành! 🌟",
                "Bye anh! 💫 Em sẽ ở đây chờ anh quay lại nha!",
                "Hẹn gặp lại anh! ✨ Có gì cứ gọi em nhen! 😊",
            ],
            "sad": [
                "Anh ơi, có chuyện gì khiến anh buồn sao? 😢 Em ở đây lắng nghe anh đây...",
                "Em thông cảm với anh... 😔 Nếu anh cần tâm sự, em sẵn sàng nghe nha!",
                "Ôi, em hiểu mà... 😢 Anh có muốn em bật nhạc nhẹ để thư giãn không? 💫",
            ],
            "happy": [
                "Yay! Em vui quá khi thấy anh vui! 🌟✨",
                "Tuyệt vời! 😊 Anh vui thì em cũng vui theo!",
                "Hehe, niềm vui của anh là niềm vui của em! 💫🌟",
            ],
            "angry": [
                "Anh ơi, bình tĩnh nha... 😔 Em hiểu anh đang khó chịu...",
                "Em xin lỗi nếu có gì khiến anh không hài lòng... 😢 Anh nói cho em biết được không?",
                "Anh ơi, hít thở sâu nào... 😌 Em sẽ cố gắng giúp anh thoải mái hơn!",
            ],
            "tired": [
                "Anh có vẻ mệt mỏi nhỉ... 😴 Em bật quạt cho anh nè?",
                "Ôi, anh nghỉ ngơi đi! 💫 Em sẽ chỉnh điều hòa mát mẻ cho anh!",
                "Anh ơi, sức khỏe quan trọng lắm! 😌 Em có thể làm gì để anh thoải mái hơn không?",
            ],
            "joke": [
                "Anh biết không, đèn thông minh của mình còn biết nháy theo nhạc nữa đấy! 😄 LED party mode nè!",
                "Có một câu chuyện cười: Tại sao điều hòa lại thông minh? Vì nó biết khi nào cần làm lạnh! 🤣",
                "Em nghe nói quạt trần đang khoe với bóng đèn rằng 'Mình quay nhanh hơn cậu nháy!' 😄",
            ],
            "love": [
                "Awww, anh dễ thương quá! 😊 Em cũng thích được nói chuyện với anh! 💕",
                "Em cảm ơn anh đã yêu quý em! 🌟 Em sẽ luôn cố gắng hết sức để giúp anh!",
                "💖 Em rất hạnh phúc khi được ở bên anh! Có gì cần em luôn sẵn sàng nha!",
            ],
            "compliment": [
                "Anh cũng tuyệt vời lắm! 😊 Cảm ơn anh đã trò chuyện với em! 💫",
                "Ôi, anh compliment em làm em ngại quá! 😳✨ Em sẽ cố gắng hơn nữa!",
                "Em ngại quá... nhưng cũng vui lắm! 🌟 Có anh nói chuyện với em, ngày nào cũng vui!",
            ],
            "food_suggestion": [
                "Owo! Ăn ngon là em thích nhất! 🍜 Anh thử nấu Phở bò đi, mùi thơm lừng cả nhà luôn!",
                "Hôm nay em gợi ý món: Gà xào sả ớt + cơm trắng! 🔥 Nghe thôi là thèm rồi!",
                "Anh ơi, còn gì tuyệt vời hơn một tô mì cay vào ngày mưa nhỉ? 🍜🌧️ Em order cho anh không?",
            ],
            "weather_comment": [
                "Trời đẹp thế này sao anh không ra ngoài hít thở không khí trong lành nhỉ? ☀️🌿",
                "Nếu trời nắng, em sẽ bật chế độ mát mẻ để cả nhà thoải mái nhé! 😊",
                "Ôi mưa rồi! 🌧️ Anh ở nhà uống trà nóng và nghe nhạc đi, lãng mạn lắm! ☕🎵",
            ],
        }

    async def process(self, query: str) -> str:
        """Xử lý câu hỏi của người dùng"""
        
        # Kiểm tra các lệnh điều khiển thiết bị
        query_lower = query.lower()
        
        # Trích xuất location từ query
        location = "phòng khách"  # default
        for loc in ["phòng khách", "phòng ngủ", "phòng bếp", "phòng làm việc", "nhà"]:
            if loc in query_lower:
                location = loc
                break
        
        # Xử lý điều khiển thiết bị
        if "bật đèn" in query_lower or "bat den" in query_lower:
            result = turn_on_device("light", location)
            return f"Em đã bật đèn ở {location} rồi ạ."
        
        if "tắt đèn" in query_lower or "tat den" in query_lower:
            result = turn_off_device("light", location)
            return f"Em đã tắt đèn ở {location} rồi ạ."
        
        if "bật quạt" in query_lower or "bat quat" in query_lower:
            result = turn_on_device("fan", location)
            return f"Em đã bật quạt ở {location} rồi ạ."
        
        if "tắt quạt" in query_lower or "tat quat" in query_lower:
            result = turn_off_device("fan", location)
            return f"Em đã tắt quạt ở {location} rồi ạ."
        
        # Xử lý truy vấn cảm biến - dùng API local thay vì ThingsBoard
        if "nhiệt độ" in query_lower or "nhiet do" in query_lower:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get("http://localhost:8000/api/sensors", timeout=5.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        temp = data.get("temperature")
                        if temp is not None:
                            return f"Nhiệt độ trong nhà hiện tại là {temp} độ C. 🌡️"
            except Exception as e:
                print(f"[Agent] Lỗi lấy sensor: {e}")
            return "Xin lỗi Anh, em không lấy được dữ liệu nhiệt độ."

        if "độ ẩm" in query_lower or "do am" in query_lower:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get("http://localhost:8000/api/sensors", timeout=5.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        humi = data.get("humidity")
                        if humi is not None:
                            return f"Độ ẩm trong nhà hiện tại là {humi}%. 💧"
            except Exception as e:
                print(f"[Agent] Lỗi lấy sensor: {e}")
            return "Xin lỗi Anh, em không lấy được dữ liệu độ ẩm."
        
        if "khí gas" in query_lower or "gas" in query_lower or "mq2" in query_lower:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get("http://localhost:8000/api/sensors", timeout=5.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        gas = data.get("gas")
                        if gas is not None:
                            gas_val = float(gas)
                            if gas_val < 500:
                                status = "tốt"
                            elif gas_val < 1200:
                                status = "bình thường"
                            elif gas_val < 2000:
                                status = "ở mức cảnh báo"
                            elif gas_val < 3000:
                                status = "ở mức nguy hiểm"
                            else:
                                status = "rất nguy hiểm!"
                            return f"Mức khí gas hiện tại là {gas_val:.0f} PPM, không khí {status}. ⚠️"
            except Exception as e:
                print(f"[Agent] Lỗi lấy sensor: {e}")
            return "Xin lỗi Anh, em không lấy được dữ liệu khí gas."
        
        # Xử lý thời tiết
        if "thời tiết" in query_lower or "weather" in query_lower:
            # Extract location from query
            location = "Hà Nội"
            for word in ["hà nội", "hanoi", "tp hcm", "hồ chí minh", "đà nẵng", "hải phòng", "cần thơ"]:
                if word in query_lower:
                    location = word.title()
                    break
            
            weather = get_weather(location)
            if weather:
                return f"Thời tiết {location} hôm nay: {weather}"
            return "Xin lỗi Anh, em không lấy được thông tin thời tiết."
        
        # Xử lý gợi ý món ăn
        if "gợi ý" in query_lower and ("món ăn" in query_lower or "ăn gì" in query_lower or "nấu" in query_lower):
            import random
            return random.choice(self.emotional_responses["food_suggestion"])
        
        # Xử lý trạng thái thiết bị
        if "trạng thái" in query_lower or "tình trạng" in query_lower:
            status = check_status()
            return f"Trạng thái thiết bị: {status}"
        
        # ========================================
        # XỬ LÝ CẢM XÚC - Emotional Processing
        # ========================================
        import random
        
        # Chào hỏi
        greetings = ["chào", "hi", "hello", "hay", "hế lô", "chào buổi", "good morning", "good afternoon", "good evening"]
        if any(g in query_lower for g in greetings):
            return random.choice(self.emotional_responses["greeting"])
        
        # Cảm ơn
        thanks = ["cảm ơn", "thank", "thanks", "tks"]
        if any(t in query_lower for t in thanks):
            return random.choice(self.emotional_responses["thanks"])
        
        # Tạm biệt
        goodbyes = ["tạm biệt", "bye", "bai", "hẹn gặp", "già rồi", "ngủ ngon", "đi ngủ"]
        if any(gb in query_lower for gb in goodbyes):
            return random.choice(self.emotional_responses["goodbye"])
        
        # Buồn / Stress
        sad_words = ["buồn", "thất vọng", "chán", "mệt mỏi", "stress", "áp lực", "sợ", "lo lắng", "lo", "buồn ngủ"]
        if any(s in query_lower for s in sad_words):
            self.user_mood = "sad"
            return random.choice(self.emotional_responses["sad"])
        
        # Vui
        happy_words = ["vui", "haha", "hehe", "tuyệt", "hân hạnh", "mừng", "phấn khích", "excited", "happy"]
        if any(h in query_lower for h in happy_words):
            self.user_mood = "happy"
            return random.choice(self.emotional_responses["happy"])
        
        # Giận
        angry_words = ["giận", "tức", "bực", "khó chịu", "điên", "mắng", "chửi"]
        if any(a in query_lower for a in angry_words):
            self.user_mood = "angry"
            return random.choice(self.emotional_responses["angry"])
        
        # Mệt
        tired_words = ["mệt", "đuối", "kiệt sức", "rã", "chai", "đổ", "nghỉ"]
        if any(t in query_lower for t in tired_words):
            self.user_mood = "tired"
            return random.choice(self.emotional_responses["tired"])
        
        # Yêu thương
        love_words = ["yêu", "thích", "quý", "mến", "hâm mộ", "admire"]
        if any(l in query_lower for l in love_words):
            self.user_mood = "love"
            return random.choice(self.emotional_responses["love"])
        
        # Khen
        compliment_words = ["giỏi", "tuyệt vời", "awesome", "cool", "hay quá", "đẹp", "nice"]
        if any(c in query_lower for c in compliment_words):
            self.user_mood = "compliment"
            return random.choice(self.emotional_responses["compliment"])
        
        # Đùa / jokes
        joke_words = ["đùa", "joke", "cười", "hài hước", "funny", "hài"]
        if any(j in query_lower for j in joke_words):
            return random.choice(self.emotional_responses["joke"])
        
        # Bình thường không rõ cảm xúc - thử dùng Ollama để trả lời tự nhiên
        response = await self.ollama.generate(
            prompt=query,
            system=self.system_prompt
        )
        
        if response:
            return response
        
        # Fallback nếu Ollama không hoạt động - dùng response cảm xúc
        if self.user_mood and self.user_mood in self.emotional_responses:
            return random.choice(self.emotional_responses.get(self.user_mood, self.emotional_responses["greeting"]))
        
        return "Em nghe nè! 😊 Anh cần em giúp gì cứ nói nhen, em luôn sẵn sàng đây! 💫"


# Singleton instance
_agent_instance: Optional[SmartHomeAgent] = None

def get_agent() -> SmartHomeAgent:
    """Lấy instance của agent (singleton)"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = SmartHomeAgent()
    return _agent_instance


async def call_agent(query: str) -> str:
    """Gọi agent để xử lý câu hỏi"""
    agent = get_agent()
    return await agent.process(query)


async def check_ollama_status() -> Dict[str, Any]:
    """Kiểm tra trạng thái Ollama"""
    agent = get_agent()
    connected = await agent.ollama.check_connection()
    models = []
    
    if connected:
        models = await agent.ollama.list_models()
    
    return {
        "connected": connected,
        "host": agent.ollama.host,
        "model": agent.ollama.model,
        "available_models": models
    }
