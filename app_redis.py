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




## redis에 메세지들이 저장되는지 확인. 
from langchain_community.chat_message_histories import RedisChatMessageHistory

history = RedisChatMessageHistory("ssac1001",url="redis://localhost:6379")
print(history.messages)"""


import streamlit as st
from utils_redis import init_conversation, print_conversation ,StreamHandler
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import ChatMessage
from langchain_core.runnables.history import RunnableWithMessageHistory  # history 와 현재 입력으로 들어오는(runnable) 메세지 같이 실행할 수 있도록 하는 기능
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_upstage import ChatUpstage

import uuid
from dotenv import load_dotenv
import os

# 페이지 표시 및 타이틀 입력
st.set_page_config(page_title="SSAC_TALK",page_icon="🍀")
st.title("🍀 SSAC_TALK")

# dotenv 로 key 불러오기
load_dotenv()


# Redis 서버의 URL을 지정합니다.
# docker로 redis 서버를 띄운 것.
# redis라는 NoSQL기반의 데이터베이스를 내 로컬이 아닌 DOCKER가 제공하는 redis 이미지를 받아서 
# 그 이미지를 기반으로 컨테이너를 만들고 그 안에서 redis 서버가 돌아간다. (이미지 = 실행환경의 설계도)

# GCP 인스턴스에 띄운 REDIS 서버 
# REDIS_URL = "redis://:REDIS_PASSWORD@34.56.88.107:6379"

# LOCAL의 REDIS 서버 
REDIS_URL = "redis://localhost:6379/0"

# LANGCHAIN_TRACING_V2 환경 변수를 "true"로 설정합니다.
os.environ["LANGCHAIN_TRACING_V2"] = "true"
# LANGCHAIN_PROJECT 설정
os.environ["LANGCHAIN_PROJECT"] = "RunnableWithMessageHistory"

# 채팅 대화기록을 저장하는 store를(= dictionary) session_state 저장
if "store" not in st.session_state:
    st.session_state["store"] = dict()

def get_reids_message_history(session_id: str) -> RedisChatMessageHistory:
    # 세션 ID를 기반으로 RedisChatMessageHistory 객체를 반환합니다.
    # 멀티턴을 구현하려면 필요한 부분
    return RedisChatMessageHistory(session_id, url=REDIS_URL) # REDIS에 message_store:session_id 로 저장이 된다.

########################################################################################################################
# session_id 직접 입력하도록 하기
#with st.sidebar:
#    session_id = st.text_input("session ID",value="ssac1024")
#
#    clear_space = st.button("대화기록 초기화")
#    if clear_space:
#        st.session_state["messages"] = []
#        st.rerun()
########################################################################################################################
# session id user 별로 배정 
# 세션 상태 초기화
if "id" not in st.session_state:
    st.session_state.id = str(uuid.uuid4())
    st.session_state.file_cache = {}

session_id = st.session_state.id
client = None

with st.sidebar:
    st.markdown(f"👤{session_id}")
    
    clear_space = st.button("대화기록 초기화")
    if clear_space:
        st.session_state["messages"] = []
        st.rerun()

# session state 에 메세지 초기화 및 대화 출력init_conversation()
init_conversation()
print_conversation()

# store = {}  # 세션 기록을 저장할 딕셔너리
# # => 이러한 형태는 인메모리, 즉 이 파일이 꺼지면 메모리가 사라진다. 

# session id 기반으로 이전 세션기록 불러오기
def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """지정된 세션 ID에 해당하는 채팅 기록을 반환합니다.

    세션 ID가 store에 존재하지 않으면 새로운 ChatMessageHistory 객체를 생성하여 store에 저장합니다.
    
    Args:
        session_ids (str):  세션 ID 문자열

    Returns:
        BaseChatMessageHistory: 지정된 세션 ID에 해당하는 채팅 기록 객체
    """
    if session_id not in st.session_state["store"]:
        # 새로운 ChatMessageHistory 객체 생성하여 store에 저장
        st.session_state["store"][session_id] = ChatMessageHistory()
    return st.session_state["store"][session_id]  # session id 에 해당하는 세션 기록 반환

# 유저 입력 받아와서 챗봇 메세지로 기록 
if user_input:= st.chat_input("텍스트를 입력하세요."):
    # print(type(prompt)) # str
    st.chat_message("user").write(f"{user_input}")
    st.session_state["messages"].append(ChatMessage(role="user",content=user_input))
    
    # assistant 답변 표시 및 저장하기
    with st.chat_message("assistant"):
        # 이전에 response를 chunk단위로 split해서 time.sleep주고 실시간으로 출력하듯이 만든걸 
        # streamHandler로 쉽게 사용.
        stream_handler = StreamHandler(st.empty())  # container = st.empty() 로 만든 공간 = 들어온 메세지를 찍어내는 공간

        # 1. LLM 모델 생성
        api_key = os.getenv('UPSTAGE_API_KEY')
        llm = ChatUpstage(streaming=True, callbacks=[stream_handler],model='solar-mini',
                          api_key=api_key)

        # 2. Prompt 생성
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "짧고 위트있게 답변해줘. 말끝에는 나무🍀 를 붙여줘",
                ),
                # 대화 기록을 변수로 사용, history 가 MessageHistory 의 key 가 됨
                # chain_with_memory에서 history message key로 사용.
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),  # 사용자 질문을 입력
            ]
        )
        runnable = prompt | llm  # 프롬프트와 모델을 연결하여 runnable 객체 생성

        # 3. 답변 생성하기
        chain_with_memory = RunnableWithMessageHistory(
            runnable,  # 실행할 Runnable 객체
            get_reids_message_history,  # redis 에 세션 기록 --> 이전의 대화가 기록
            input_messages_key="question",  # 입력 질문의 키
            history_messages_key="history",  # 기록 메시지의 키 --> 이번 대화가 기록
            )
        
        print("잘들어가고 있나",session_id)
        response = chain_with_memory.invoke(
            # 유저의 입력(질문)을 전달
            {"question": user_input},
            # 설정 정보로 세션 ID "ssac----"를 전달합니다.
            config={"configurable": {"session_id": session_id}},
        )
        st.session_state["messages"].append(ChatMessage(role="assistant",content=response.content))