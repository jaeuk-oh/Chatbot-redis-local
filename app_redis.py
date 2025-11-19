"""
This file is part of the langchain-kr project.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

This file references code from the following source:
Link: https://github.com/teddylee777/langchain-kr

Original Author: teddylee777
Modifications:
- [2024-07-23]: Added and modified some comments for clarification and added a docstring by jonhyuk0922
- [2025-11-08]: Added UUID generation for session ID and detailed comments

"""

import streamlit as st
from utils_redis import init_conversation, print_conversation, StreamHandler
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import ChatMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_upstage import ChatUpstage

from dotenv import load_dotenv
import os
import uuid  # UUID 생성을 위한 모듈 추가

# ============================================
# 페이지 설정
# ============================================
st.set_page_config(page_title="SSAC_TALK", page_icon="🍀")
st.title("🍀 SSAC_TALK")

# ============================================
# 환경 변수 로드
# ============================================
# .env 파일에서 API 키 등의 환경 변수를 불러옵니다.
load_dotenv()

# ============================================
# Redis 및 LangChain 설정
# ============================================
# Redis 서버의 URL을 지정합니다. (로컬호스트의 6379 포트, 0번 데이터베이스)
REDIS_URL = "redis://localhost:6379/0"

# LangSmith 트레이싱을 활성화하여 디버깅 및 모니터링을 수행합니다.
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "RunnableWithMessageHistory"

# ============================================
# 세션 상태 초기화
# ============================================
# 채팅 대화기록을 저장하는 store를 session_state에 저장
# 이는 여러 세션의 대화 기록을 메모리에 보관하기 위한 딕셔너리
if "store" not in st.session_state:
    st.session_state["store"] = dict()

# 세션 ID 상태 관리 
if "session_initialized" not in st.session_state:
    st.session_state["session_initialized"] = False

# 세션 ID를 session_state에 저장 (초기값 설정)
if "session_id" not in st.session_state:
    st.session_state["session_id"] = False

# ============================================
# Redis 메시지 히스토리 함수
# ============================================

# prefix와 session id를 변수로 받아서 redis key값이 된다. -> key를 가지고 저장을 한다.
#class RedisChatMessageHistory:
#    def __init__(self, session_id, url):
#        self.session_id = session_id
#        self.url = url
#        self.key_prefix = "message_store"  # prefix 기본값
#        self.redis_key = f"{self.key_prefix}:{self.session_id}"
        
def get_redis_message_history(session_id: str) -> RedisChatMessageHistory:
    """Redis를 사용하여 세션 ID 기반의 채팅 기록을 반환합니다.

    Args:
        session_id (str): 세션 식별자

    Returns:
        RedisChatMessageHistory: Redis에 저장된 채팅 기록 객체
    """
    # 세션 ID를 기반으로 RedisChatMessageHistory 객체를 반환합니다.
    # redis 내부적으로 message_store:"id값" 이라는 key name으로 대화를 저장함.
    return RedisChatMessageHistory(session_id, url=REDIS_URL)

# ============================================
# 세션 유효성 검사 
# ============================================
# if not a or b --> 해버리면 not이 or 보다 우선되기 때문에 (not a) or b 가 되어버린다. 그래서 a가 false거나 b가 false일 때가 아니라 
# a가 false거나 b가 참일 때가 되어버린다.
def session_valid() -> bool:
    if not st.session_state["session_initialized"] or not st.session_state["session_id"]:
        return False
    return True

# ============================================
# 사이드바 UI
# ============================================
with st.sidebar:
    st.subheader("세션 관리")

    # UUID 생성 버튼 추가
    if st.button("🆕 새 세션 ID 생성 (UUID)", help="무작위 UUID를 생성하여 새로운 세션을 시작합니다"):
        # UUID4를 사용하여 고유한 세션 ID 생성
        new_session_id = str(uuid.uuid4())
        st.session_state["session_id"] = new_session_id
        st.session_state["session_initialized"] = True
        st.success(f"새 세션이 생성되었습니다!\\nID: {new_session_id}")
    
    st.write(f"반갑습니다. {st.session_state.session_id}님")
    st.divider()

    # 대화기록 초기화 버튼
    clear_space = st.button("🗑️ 대화기록 초기화", help="현재 화면의 대화 내용을 삭제합니다")
    if clear_space:
        # session_state의 messages를 초기화하여 화면에 표시된 대화를 삭제
        st.session_state["messages"] = []
        st.rerun()

# ============================================
# 대화 초기화 및 출력
# ============================================
# session_state에 메시지 리스트를 초기화하고 이전 대화를 화면에 출력합니다.
init_conversation()
print_conversation()

# ============================================
# 세션 기록 관리 함수 (인메모리)
# 이거는 sessino_state에 저장하는 건데 redis 쓰니까 지금은 필요없는 것
# ============================================
def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """지정된 세션 ID에 해당하는 채팅 기록을 반환합니다.

    이 함수는 인메모리 방식으로 세션 기록을 관리합니다.
    세션 ID가 store에 존재하지 않으면 새로운 ChatMessageHistory 객체를 생성하여 저장합니다.

    Args:
        session_id (str): 세션 ID 문자열

    Returns:
        BaseChatMessageHistory: 지정된 세션 ID에 해당하는 채팅 기록 객체
    """
    if session_id not in st.session_state["store"]:
        # 새로운 ChatMessageHistory 객체 생성하여 store에 저장
        st.session_state["store"][session_id] = ChatMessageHistory()
    # session_id에 해당하는 세션 기록 반환
    return st.session_state["store"][session_id]

# ============================================
# 사용자 입력 처리 및 응답 생성
# ============================================
# 사용자로부터 텍스트 입력을 받습니다.
if user_input := st.chat_input("텍스트를 입력하세요."):
    if not session_valid():
        # 디버깅을 위한 세션 ID 출력
        print(f"init 세션: {st.session_state.session_initialized}")
        print(f"현재 세션 valid: {session_valid()}")
        print(f"현재 세션 ID: {st.session_state.session_id}")    
     
        st.warning("⚠️ 채팅을 사용하기 위해서는 먼저 '새 세션 ID 생성' 버튼을 눌러주세요!")
    else:
        # --------------------------------------------
        # 사용자 메시지 표시 및 저장
        # --------------------------------------------
        # 사용자 메시지를 화면에 표시
        st.chat_message("user").write(f"{user_input}")
        # 사용자 메시지를 session_state에 저장
        st.session_state["messages"].append(ChatMessage(role="user", content=user_input))

        # --------------------------------------------
        # 어시스턴트 응답 생성 및 표시
        # --------------------------------------------
        with st.chat_message("assistant"):
            # 스트리밍 핸들러 생성: 실시간으로 응답을 화면에 출력하기 위한 핸들러
            stream_handler = StreamHandler(st.empty())

            # 1. LLM 모델 생성
            # ChatOpenAI 모델을 생성하며, 스트리밍 모드를 활성화하고 콜백 핸들러를 설정합니다.
            llm = ChatUpstage(
                streaming=True, 
                callbacks=[stream_handler], 
                model='solar-mini'
            )

            # 2. 프롬프트 템플릿 생성
            # 시스템 메시지, 대화 기록, 사용자 질문을 포함하는 프롬프트를 구성합니다.
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "짧고 위트있게 답변해줘. 말끝에는 나무🍀 를 붙여줘",
                    ),
                    # 대화 기록을 변수로 사용, "history"가 MessageHistory의 키가 됩니다.
                    MessagesPlaceholder(variable_name="history"),
                    # 사용자 질문을 입력받는 플레이스홀더
                    ("human", "{question}"),
                ]
            )

            # 프롬프트와 LLM 모델을 파이프라인으로 연결하여 runnable 객체 생성
            runnable = prompt | llm

            # 3. 메시지 히스토리를 포함한 체인 생성
            # RunnableWithMessageHistory를 사용하여 대화 기록을 자동으로 관리합니다.
            chain_with_memory = RunnableWithMessageHistory(
                runnable,  # 실행할 Runnable 객체 (프롬프트 + LLM)
                get_redis_message_history,  # Redis에 세션 기록을 저장/조회하는 함수
                input_messages_key="question",  # 사용자 입력(질문)의 키 이름
                history_messages_key="history",  # 대화 기록의 키 이름
            )
            
            # 디버깅을 위한 세션 ID 출력
            print(f"init 세션: {st.session_state.session_initialized}")
            print(f"현재 세션 valid: {session_valid()}")
            print(f"현재 세션 ID: {st.session_state.session_id}")

            # 4. 체인 실행 및 응답 생성
            # 사용자 질문과 세션 ID를 전달하여 LLM 응답을 생성합니다.
            response = chain_with_memory.invoke(
                # 사용자의 입력(질문)을 전달
                {"question": user_input},
                # 설정 정보로 세션 ID를 전달하여 해당 세션의 대화 기록을 사용
                config={"configurable": {"session_id": st.session_state.session_id}},
            )

            # 5. 어시스턴트 응답을 session_state에 저장
            # 생성된 응답을 메시지 리스트에 추가하여 화면에 표시되도록 합니다.
            st.session_state["messages"].append(
                ChatMessage(role="assistant", content=response.content)
            )
