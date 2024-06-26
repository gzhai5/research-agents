import os
from fastapi import UploadFile
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_community.vectorstores import Chroma
from langchain_community.llms import Ollama
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from app.s3.s3_service import s3_service


class CommonService:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1024, chunk_overlap=80, length_function=len, is_separator_regex=False)
        self.embedding = FastEmbedEmbeddings()
        self.cached_llm = Ollama(model="llama3")
        self.vector_store_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../vector_store"
    
    async def upload_pdf(self, file: UploadFile, user_id: str):
        # save the file to a temp pdf folder
        saved_file_path = f"{os.path.dirname(os.path.abspath(__file__))}/../../temp/{file.filename}"
        with open(saved_file_path, "wb") as buffer:
            buffer.write(file.file.read())
        logger.info(f"PDF file saved to: {saved_file_path}")

        # load and split the pdf
        loader = PDFPlumberLoader(saved_file_path)
        docs = loader.load_and_split()
        logger.info(f"PDF file docs have length: {len(docs)}")

        # get into chunks
        chunks = self.text_splitter.split_documents(docs)
        logger.info(f"PDF file chunks have length: {len(chunks)}")

        # store in vector db
        vector_store = Chroma.from_documents(documents=chunks, embedding=self.embedding, persist_directory=self.vector_store_path)
        vector_store.persist()

        # upload to s3
        pdf_s3_key = await s3_service.upload_pdf(file, user_id)
        vector_store_s3_key = await s3_service.upload_folder(self.vector_store_path, user_id, topic="vector_store")

        # clean up
        os.remove(saved_file_path)

        return {
            "filename": file.filename,
            "doc_length": len(docs),
            "chunk_length": len(chunks),
            "pdf_s3_key": pdf_s3_key,
            "vector_store_s3_key": vector_store_s3_key
        }

common_service = CommonService()