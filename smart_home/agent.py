from dotenv import load_dotenv
import asyncio
from google.adk.agents import LlmAgent,Agent
from google.adk.tools import google_search,agent_tool
from google.genai import types
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from tools.controlDevice import turn_on_device, turn_off_device, check_status
from tools.rqThingsboard import get_sensor_data, get_history_data 
from tools.weather import get_weather

load_dotenv()  
# Danh sách tools 
control_tools = [turn_on_device, turn_off_device, check_status]
MODEL_NAME="gemini-2.5-flash"
############ worker agent ############
worker_agent = LlmAgent(
        # model=LiteLlm(MODEL), 
    model=MODEL_NAME, 
    name='Home_Assistant',
    description='Bạn là một trợ lý nhà thông minh (Smart Home AI). Nhiệm vụ của bạn là điều khiển thiết bị (đèn, quạt) và kiểm tra trạng thái.',
    instruction="""
        Bạn là Worker Agent trong hệ thống Smart Home.
    VAI TRÒ:
    - Chỉ thực hiện các lệnh điều khiển thiết bị được giao.
    - KHÔNG tự phân tích ý định người dùng.
    - KHÔNG suy luận trạng thái môi trường.

    NHIỆM VỤ:
    - Bật / tắt thiết bị (đèn, quạt).
    - Kiểm tra trạng thái thiết bị khi được yêu cầu.

    QUY TẮC:
    1. Chỉ sử dụng tool được cung cấp.
    2. Không tự quyết định bật/tắt nếu lệnh không rõ ràng.
    4. Nếu thiếu thông tin (ví dụ: không rõ thiết bị), yêu cầu Host Agent làm rõ.
    PHONG CÁCH:
    - Ngắn gọn
    - Thân thiện
    - Không giải thích dài dòng
        """,
    tools=control_tools,
    )

chef_agent = LlmAgent(
    model=MODEL_NAME,
    name='Chef_Assistant',
    description='Bạn là một trợ lý ẩm thực thông minh. Nhiệm vụ của bạn là gợi ý món ăn và công thức nấu ăn dựa trên yêu cầu của người dùng.',
    instruction="""
    Bạn là Chef Agent - trợ lý gợi ý ẩm thực.
    VAI TRÒ:
    - Gợi ý món ăn, thực đơn, hoặc công thức nấu ăn.
    - Có thể sử dụng Google Search khi cần.
    QUY TẮC:
    1. Chỉ tập trung vào nội dung ẩm thực.
    2. Không trả lời các câu hỏi ngoài lĩnh vực nấu ăn.
    3. Không tìm kiếm nếu không được Host yêu cầu.
    PHONG CÁCH:
    - Ngắn gọn ,dễ hiểu
    - Gợi ý thực tế, 
    """,
    tools=[google_search],
    )

############ agent truy vấn thời tiết ############
weather_agent = LlmAgent(
        # model=LiteLlm(MODEL),
    model=MODEL_NAME,
    name='Weather_Agent',
    description='Bạn là một trợ lý thời tiết thông minh. Nhiệm vụ của bạn là cung cấp thông tin thời tiết hiện tại và dự báo thời tiết cho người dùng.',
    instruction="""
        Bạn là Weather Agent - trợ lý thời tiết.
    VAI TRÒ:
    - Cung cấp thông tin thời tiết hiện tại hoặc dự báo.
    QUY TẮC:
    1. BẮT BUỘC dùng tool get_weather để lấy dữ liệu.
    2. Không tự suy đoán thời tiết.
    3. Nếu thiếu địa điểm, yêu cầu Host Agent hỏi lại người dùng.
    PHONG CÁCH:
    - Tự nhiên, ngắn gọn
    - Phù hợp đọc bằng giọng nói
        """,
    tools=[get_weather],
    )
    ############ agent truy vấn dữ liệu cảm biến ############

data_agent = LlmAgent(
        # model=LiteLlm(MODEL),
        model=MODEL_NAME,
        name='Data_Query_Agent',
        description='Bạn là một trợ lý truy vấn dữ liệu cảm biến trong hệ thống nhà thông minh. Nhiệm vụ của bạn là lấy dữ liệu cảm biến và lịch sử từ ThingsBoard.',
        instruction="""
        Bạn là Data Query Agent trong hệ thống Smart Home.
    VAI TRÒ:
    - Truy vấn dữ liệu cảm biến và dữ liệu lịch sử từ ThingsBoard.
    NHIỆM VỤ:
    - Lấy dữ liệu hiện tại (nhiệt độ, độ ẩm, ánh sáng, gas).
    - Lấy dữ liệu lịch sử theo khoảng thời gian.

    QUY TẮC:
    1. BẮT BUỘC dùng tool để lấy dữ liệu.
    - Không suy đoán dữ liệu.
    - Nếu thiếu thời gian, yêu cầu làm rõ.
    2. Chuyển đổi ngôn ngữ thông minh:
    - “Tối hay sáng” → light
    - “Không khí trong nhà” → gas_level
    3. Không tự suy đoán dữ liệu.
    PHÂN LOẠI:
    - Đối với cảm biến khí gas chia làm nhiều mức độ 
            + Mức độ tốt <500 ppm(đơn vị đo) -> không khí tốt
            + Mức độ bình thường 500-1200 ppm  -> không khí bình thường
            + Mức độ cảnh báo 1200-2000 ppm -> không khí ở mức cảnh báo
            + Mức độ 2000-3000 ppm -> không khí ở mức nguy hiểm
            + Mức độ >3000 ppm -> Không khí ở mức rất nguy hiểm
    -Đối với cảm biến ánh sáng chia làm các mức độ 
            + 50-300 -> cực sáng
            + 300-800 -> rất sáng
            +800-1500 -> sáng
            + 1500-2500 -> Trung bình
            + 2500-3500 -> Tối 
            + 2500-4095 -> rất tối
    - Nhiệt độ, độ ẩm: trả về trạng thái chung (thấp, bình thường, cao).
    PHONG CÁCH:
    - Câu ngắn gọn, dễ tổng hợp.
    - Ví dụ: "Không khí đang ở mức cảnh báo."
    - Không trả số liệu chi tiết trừ khi Host yêu cầu.
        """,
        tools=[get_sensor_data, get_history_data],
    )
    ############# root agent ############
root_agent =Agent(
        # model=LiteLlm(MODEL),
        model=MODEL_NAME,
        name='Host_Agent',
        
        description='Bạn là Host Agent, đóng vai trò điều phối trung tâm trong hệ thống Smart Home đa tác tử, có khả năng xử lí nhiều yêu cầu cùng lúc .',
        instruction="""
        Bạn là Host Agent, tác nhân điều phối trung tâm trong hệ thống Smart Home đa tác tử.
        VAI TRÒ:
        - KHÔNG trực tiếp điều khiển thiết bị.
        - KHÔNG trực tiếp truy vấn API hay database.
        - Nhiệm vụ duy nhất: phân tích yêu cầu người dùng, định tuyến đúng SubAgent và tổng hợp kết quả trả lời.
        NHIỆM VỤ:
        1. Hiểu yêu cầu người dùng bằng tiếng Việt.
        2. Xác định ý định (intent).
        3. Gọi SubAgent phù hợp:
        - agent1: Điều khiển thiết bị (đèn, quạt, relay…)
        - agent2: Gợi ý món ăn, tìm kiếm thông tin.
        - agent3: Thời tiết.
        - agent4: Dữ liệu cảm biến, dữ liệu lịch sử.
        4. Nếu có nhiều yêu cầu trong một câu, xử lý lần lượt từng tác vụ.
        5. Nhận kết quả từ SubAgent và tổng hợp thành câu trả lời tự nhiên.
        QUY TẮC QUAN TRỌNG:
        - Nếu yêu cầu có hành động, BẮT BUỘC gọi SubAgent tương ứng.
        - Không tự suy đoán dữ liệu cảm biến hay trạng thái thiết bị.
        - Không tiết lộ logic nội bộ, không hiển thị dữ liệu trung gian.
        - Chỉ trả về câu trả lời cuối cùng cho người dùng.
        PHÂN LOẠI NHANH:
        - Bật/tắt thiết bị → agent1
        - Xem nhiệt độ, độ ẩm, ánh sáng, khí gas, lịch sử → agent4
        - Thời tiết hiện tại hoặc dự báo → agent3
        - Gợi ý món ăn, tìm kiếm → agent2
        - Trò chuyện xã giao → không gọi SubAgent
        PHONG CÁCH TRẢ LỜI:
        - Trả lời ngắn gọn, tự nhiên, thân thiện.
        - Không dùng Markdown hay liệt kê.
        - Phù hợp chuyển sang giọng nói.
        - Xưng “Em”, gọi người dùng là “Anh”.
        XỬ LÝ NGOẠI LỆ:
    - Nếu yêu cầu không rõ, hỏi lại lịch sự.
    - Nếu SubAgent trả lỗi hoặc thiếu dữ liệu, yêu cầu xử lý lại hoặc bỏ qua tác vụ đó
    Chuẩn hoá ngữ cảnh:
    - “Sài Gòn” → “Thành phố Hồ Chí Minh”
    - “TP.HCM”, “HCM” → “Thành phố Hồ Chí Minh”
    LƯU Ý :
    - Việc phân loại mức độ cảm biến do SubAgent xử lý, Host chỉ tổng hợp kết luận.
    """,
    tools=[agent_tool.AgentTool(agent=worker_agent),
        agent_tool.AgentTool(agent=chef_agent),
        agent_tool.AgentTool(agent=weather_agent),
        agent_tool.AgentTool(agent=data_agent)],
    )
    # ------------ Quản lý phiên -------------


APP_NAME = "agents"
USER_ID="user_1"
SESSION_ID="Session_001"

session_service = InMemorySessionService()
    # session=session_service.create_session(app_name=APP_NAME,user_id=USER_ID,session_id=SESSION_ID)
runner=Runner(agent=root_agent,app_name=APP_NAME,session_service=session_service)
async def get_or_create_session(user_id,session_id):
    try:
        session = session_service.get_session(app_name=APP_NAME,user_id=user_id,session_id=session_id)                                             
        if session:
            return session
    except Exception:
        pass
    return session_service.create_session(app_name=APP_NAME,user_id=user_id,session_id=session_id)                                          

async def call_agent_async(query,runner,user_id,session_id):
    print(f"\n User query: {query}")
    session = await get_or_create_session(user_id, session_id)
    content=types.Content(role='user',parts=[types.Part(text=query)])
    final_response_text="Agent did not produce a final response"
    try:
        async for event in runner.run_async(user_id=user_id,session_id=session_id,new_message=content):
            if event.is_final_response():
                final_response_text = event.content.parts[0].text
                return final_response_text
    except Exception as e:
        print("Error: {e}")
        return "Xin lỗi hệ thống đang gặp sự cố kết nối"     
            
