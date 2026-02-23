import streamlit as st
import dotenv
from typing import List, Tuple

from semantic_retrieval import search, synthesize_with_validation
from vector_store_utils import load_existing_data

dotenv.load_dotenv()

st.set_page_config(page_title="CRAGBot")
st.title("CRAGBot")

if "messages" not in st.session_state:
    st.session_state.messages = []

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

# clear chat
if st.button("Clear chat history"):
    st.session_state.messages = []
    st.rerun()

show_sources = st.checkbox("Show sources", value=True)

# display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["content"]:
            st.markdown(message["content"])

if prompt := st.chat_input("Ask a question about the research papers within the CRAG Library."):
    # add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
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
            with st.spinner("Generating answer..."):
                try:
                    # Pass recent chat history so the LLM can reference prior messages
                    history = st.session_state.messages[-6:]
                    answer = synthesize_with_validation(prompt, results, history=history)
                    assistant_text = answer.summary
                except Exception as e:
                    assistant_text = f"Error generating answer: {e}"
                st.markdown(assistant_text)

        st.session_state.messages.append({"role": "assistant", "content": assistant_text})

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
        
