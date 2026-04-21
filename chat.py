import streamlit as st
import dotenv
from typing import List, Tuple
import time
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart

from semantic_retrieval import search, synthesize_answer, AnswerModel
from vector_store_utils import load_existing_data

dotenv.load_dotenv()

st.set_page_config(page_title="CRAGBot")
st.title("CRAGBot")

if "messages" not in st.session_state:
    st.session_state.messages: List[ModelMessage] = [] # type: ignore

if "vs_status" not in st.session_state:
    st.session_state.vs_status = "not_loaded"
if st.button("Reload vector store") or st.session_state.vs_status == "not_loaded":
    try:
        sentences, embeddings, index, processed_files = load_existing_data()
        st.session_state.sentences = sentences
        st.session_state.embeddings = embeddings
        st.session_state.index = index
        st.session_state.processed_files = processed_files
        st.session_state.vs_status = "loaded"
    except Exception as e:
        st.session_state.vs_status = "error"
        st.error(f"Error loading vector store: {e}")

with st.sidebar:
    st.header("Vector Store Status")
    if st.session_state.vs_status == "loaded":
        st.success("Vector store loaded successfully!")
        st.write(f"Processed files: {st.session_state.processed_files}")
    elif st.session_state.vs_status == "error":
        st.error("Error loading vector store. Please check the console for details.")
    else:
        st.warning("Vector store not loaded. Please click the button above to load it.")

# clear chat
if st.button("Clear chat history"):
    st.session_state.messages = []
    st.rerun()

show_sources = st.checkbox("Show sources", value=True)

# display chat messages from history on app rerun
for message in st.session_state.messages:
    role = "user" if isinstance(message, ModelRequest) else "assistant"

    with st.chat_message(role):
        for part in message.parts:
            if hasattr(part, "content"):
                st.markdown(part.content)
        
        if role == "assistant" and hasattr(message, "metadata"):
            sources = message.metadata.get("sources", [])
            if show_sources and sources:
                with st.expander("Sources used (click to expand)"):
                    for s in sources:
                        title = s.title
                        section = s.section_header
                        text = s.text
                        score = s.score
                        st.write(text)
                        st.caption(f"**{title}** — {section} — relevance: {score}")
                        st.write("---")

if prompt := st.chat_input("Ask a question about the CRAG Library."):
    # add user message to chat history
    user_msg = ModelRequest(parts=[UserPromptPart(content=prompt)])
    st.session_state.messages.append(user_msg)
    # display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # If vector store not loaded, show helpful message
    index = st.session_state.get("index")
    sentences = st.session_state.get("sentences", [])

    if index is None:
        assistant_text = "No vector store index loaded. Please load the vector store from the sidebar."
        with st.chat_message("assistant"):
            st.markdown(assistant_text)
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
    else:
        # run search
        try:
            results: List[Tuple] = search(index, sentences, prompt, top_k=10)
        except Exception as e:
            err = f"Search error: {e}"
            with st.chat_message("assistant"):
                st.markdown(err)
            st.session_state.messages.append({"role": "assistant", "content": err})
            results = []

        # synthesize answer (with validation)
        with st.chat_message("assistant"):
            try:
                answer = synthesize_answer(prompt, results, message_history=st.session_state.messages)
                assistant_text = answer.summary
            except Exception as e:
                assistant_text = f"Error generating response: {e}."
                
            def stream_wrapper():
                for word in assistant_text.split(" "):
                    yield word + " "
                    time.sleep(0.05)
            
            st.write_stream(stream_wrapper())

            assistant_msg = ModelResponse(parts=[TextPart(content=assistant_text)])
            if hasattr(answer, "sources"):
                assistant_msg.metadata = {"sources": answer.sources}
            st.session_state.messages.append(assistant_msg)
            # optionally show sources
            if show_sources and hasattr(answer, "sources") and answer.sources:
                with st.expander("Sources used (click to expand)"):
                    for s in answer.sources:
                        title = s.file_title
                        section = s.section_header
                        text = s.text
                        score = s.score
                        st.write(text)
                        st.caption(f"**{title}** — {section} — relevance: {score}")
                        st.write("---")