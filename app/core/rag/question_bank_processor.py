# -*- coding: utf-8 -*-
"""
题库处理模块
解析题库文件（支持JSON、CSV、TXT格式），进行文本分块，准备embedding
"""
import logging
import json
import csv
import re
from typing import List, Dict, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class QuestionBankProcessor:
    """题库处理器"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        初始化题库处理器
        
        Args:
            chunk_size: 文本分块大小（字符数）
            chunk_overlap: 分块重叠大小（字符数）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def load_question_bank(self, file_path: str) -> List[Dict]:
        """
        加载题库文件
        
        支持格式：
        1. JSON: [{"question": "...", "answer": "...", "category": "..."}, ...]
        2. CSV: question,answer,category
        3. TXT: Q: ...\nA: ...\n\n格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            题目列表，每个题目包含question、answer等字段
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Question bank file not found: {file_path}")
        
        suffix = file_path.suffix.lower()
        
        try:
            if suffix == ".json":
                return self._load_json(file_path)
            elif suffix == ".csv":
                return self._load_csv(file_path)
            elif suffix == ".txt":
                return self._load_txt(file_path)
            else:
                raise ValueError(f"Unsupported file format: {suffix}")
        except Exception as e:
            logger.error(f"Failed to load question bank: {e}")
            raise
    
    def _load_json(self, file_path: Path) -> List[Dict]:
        """加载JSON格式题库"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            raise ValueError("JSON file should contain a list of questions")
        
        questions = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            
            question = item.get("question", item.get("q", ""))
            answer = item.get("answer", item.get("a", ""))
            
            if question and answer:
                questions.append({
                    "question": question,
                    "answer": answer,
                    "category": item.get("category", item.get("type", "")),
                    "difficulty": item.get("difficulty", ""),
                    "index": i
                })
        
        return questions
    
    def _load_csv(self, file_path: Path) -> List[Dict]:
        """加载CSV格式题库"""
        questions = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                question = row.get("question", row.get("q", ""))
                answer = row.get("answer", row.get("a", ""))
                
                if question and answer:
                    questions.append({
                        "question": question,
                        "answer": answer,
                        "category": row.get("category", row.get("type", "")),
                        "difficulty": row.get("difficulty", ""),
                        "index": i
                    })
        
        return questions
    
    def _load_txt(self, file_path: Path) -> List[Dict]:
        """加载TXT格式题库"""
        questions = []
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 尝试匹配 Q: ... A: ... 格式
        pattern = r'Q[:\s]+(.*?)\nA[:\s]+(.*?)(?=\n\n|\nQ[:\s]|$)'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        
        for i, (question, answer) in enumerate(matches):
            question = question.strip()
            answer = answer.strip()
            if question and answer:
                questions.append({
                    "question": question,
                    "answer": answer,
                    "category": "",
                    "difficulty": "",
                    "index": i
                })
        
        # 如果没有匹配到，尝试按空行分割
        if not questions:
            blocks = content.split("\n\n")
            for i, block in enumerate(blocks):
                lines = block.strip().split("\n")
                if len(lines) >= 2:
                    question = lines[0].replace("Q:", "").replace("Q：", "").strip()
                    answer = "\n".join(lines[1:]).replace("A:", "").replace("A：", "").strip()
                    if question and answer:
                        questions.append({
                            "question": question,
                            "answer": answer,
                            "category": "",
                            "difficulty": "",
                            "index": i
                        })
        
        return questions
    
    def chunk_text(self, text: str) -> List[str]:
        """
        将文本分块
        
        Args:
            text: 文本内容
            
        Returns:
            文本块列表
        """
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # 尝试在句号、问号、感叹号处分割
            if end < len(text):
                # 向后查找句号、问号、感叹号
                for i in range(end, max(start, end - 100), -1):
                    if text[i] in '。！？\n':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap
        
        return chunks
    
    def prepare_documents(self, questions: List[Dict]) -> List[Tuple[str, Dict]]:
        """
        准备文档用于embedding和存储
        
        Args:
            questions: 题目列表
            
        Returns:
            (文档文本, 元数据) 元组列表
        """
        documents = []
        
        for q in questions:
            # 将问题和答案组合成文档
            question_text = q["question"]
            answer_text = q["answer"]
            
            # 如果答案太长，进行分块
            if len(answer_text) > self.chunk_size:
                chunks = self.chunk_text(answer_text)
                for i, chunk in enumerate(chunks):
                    doc_text = f"问题：{question_text}\n答案片段{i+1}：{chunk}"
                    metadata = {
                        "question": question_text,
                        "answer": answer_text,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "category": q.get("category", ""),
                        "difficulty": q.get("difficulty", ""),
                        "question_index": q.get("index", 0)
                    }
                    documents.append((doc_text, metadata))
            else:
                doc_text = f"问题：{question_text}\n答案：{answer_text}"
                metadata = {
                    "question": question_text,
                    "answer": answer_text,
                    "chunk_index": 0,
                    "total_chunks": 1,
                    "category": q.get("category", ""),
                    "difficulty": q.get("difficulty", ""),
                    "question_index": q.get("index", 0)
                }
                documents.append((doc_text, metadata))
        
        return documents


