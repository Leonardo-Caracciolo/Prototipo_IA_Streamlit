from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from core.vectorizer import get_vector_store_for_workspace
import os

def responder(workspace, prompt):
    llm = ChatOpenAI(model=os.getenv("MODEL_NAME", "gpt-4o"))
    vectorstore = get_vector_store_for_workspace(workspace)
    retriever = vectorstore.as_retriever()
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True
    )
    output = chain.invoke({"query": prompt})
    return output["result"]