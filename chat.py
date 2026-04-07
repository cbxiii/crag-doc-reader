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
        if message.get("content"):
            st.markdown(message["content"])

        # Render persisted sources for assistant messages (if any)
        if message.get("role") == "assistant" and show_sources and message.get("sources"):
            with st.expander("Sources used (click to expand)"):
                for s in message.get("sources", []):
                    title = s.get("file_title", "")
                    section = s.get("section_header", "")
                    text = s.get("text", "")
                    score = s.get("score", "")
                    st.write(text)
                    st.caption(f"**{title}** — {section} — relevance: {score}")
                    st.write("---")

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
                    answer = None
                    assistant_text = f"Error generating answer: {e}"

                st.markdown(assistant_text)

                # Build a serializable sources list (cap to top 5) and optionally show them
                serialized_sources = []
                if answer is not None and hasattr(answer, "sources") and answer.sources:
                    raw_sources = list(answer.sources)[:5]
                    for s in raw_sources:
                        if isinstance(s, dict):
                            file_title = s.get("file_title", "")
                            section_header = s.get("section_header", "")
                            text = s.get("text", "")
                            score = s.get("score", "")
                        else:
                            file_title = getattr(s, "file_title", "")
                            section_header = getattr(s, "section_header", "")
                            text = getattr(s, "text", "")
                            score = getattr(s, "score", "")

                        # Normalize to simple serializable types
                        try:
                            score_val = float(score) if score is not None and score != "" else None
                        except Exception:
                            score_val = None

                        serialized_sources.append({
                            "file_title": str(file_title) if file_title is not None else "",
                            "section_header": str(section_header) if section_header is not None else "",
                            "text": str(text) if text is not None else "",
                            "score": score_val,
                        })

                # show sources immediately for the current assistant response
                if show_sources and serialized_sources:
                    with st.expander("Sources used (click to expand)"):
                        for s in serialized_sources:
                            st.write(s.get("text", ""))
                            st.caption(f"**{s.get('file_title','')}** — {s.get('section_header','')} — relevance: {s.get('score')}")
                            st.write("---")

        # Persist assistant message and its serializable sources so they survive reruns
        st.session_state.messages.append({"role": "assistant", "content": assistant_text, "sources": serialized_sources})

        
