# -*- coding: utf-8 -*-
"""
PDF解析器
按页提取PDF文本内容
"""

import re
from pathlib import Path
from typing import List, Dict, Optional

from app.core.utils.logger import setup_logger

logger = setup_logger("PDFParser")

# 尝试导入PDF解析库
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    pdfplumber = None


class PDFParser:
    """PDF解析器 - 按页提取文本"""
    
    def __init__(self, prefer_library: str = "pymupdf"):
        """
        初始化PDF解析器
        
        Args:
            prefer_library: 优先使用的库 ("pymupdf" 或 "pdfplumber")
        """
        self.prefer_library = prefer_library
        self.available_libraries = []
        
        if PYMUPDF_AVAILABLE:
            self.available_libraries.append("pymupdf")
        if PDFPLUMBER_AVAILABLE:
            self.available_libraries.append("pdfplumber")
        
        if not self.available_libraries:
            raise ImportError(
                "No PDF parsing library available. "
                "Please install one of: pip install pymupdf OR pip install pdfplumber"
            )
        
        logger.info(f"PDF parser initialized with libraries: {self.available_libraries}")
    
    def parse_pdf(self, pdf_path: Path) -> List[Dict[str, any]]:
        """
        解析PDF文件，按页提取文本
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            页面列表，每个页面包含：
            - page_number: 页码（从1开始）
            - text: 页面文本内容
            - is_empty: 是否为空页
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # 选择解析库
        library = self._select_library()
        
        try:
            if library == "pymupdf":
                return self._parse_with_pymupdf(pdf_path)
            elif library == "pdfplumber":
                return self._parse_with_pdfplumber(pdf_path)
            else:
                raise ValueError(f"Unknown library: {library}")
        except Exception as e:
            logger.error(f"Failed to parse PDF with {library}: {e}")
            # 尝试备用库
            if library != self.available_libraries[0] and len(self.available_libraries) > 1:
                fallback_library = self.available_libraries[0]
                logger.info(f"Trying fallback library: {fallback_library}")
                if fallback_library == "pymupdf":
                    return self._parse_with_pymupdf(pdf_path)
                elif fallback_library == "pdfplumber":
                    return self._parse_with_pdfplumber(pdf_path)
            raise
    
    def _select_library(self) -> str:
        """选择要使用的PDF解析库"""
        if self.prefer_library in self.available_libraries:
            return self.prefer_library
        return self.available_libraries[0]
    
    def _parse_with_pymupdf(self, pdf_path: Path) -> List[Dict[str, any]]:
        """使用PyMuPDF解析PDF"""
        pages = []
        doc = fitz.open(str(pdf_path))
        
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                
                # 文本清洗
                text = self._clean_text(text)
                is_empty = len(text.strip()) == 0
                
                pages.append({
                    "page_number": page_num + 1,  # 从1开始
                    "text": text,
                    "is_empty": is_empty
                })
                
                logger.debug(f"Parsed page {page_num + 1}: {len(text)} characters, empty={is_empty}")
        
        finally:
            doc.close()
        
        logger.info(f"Parsed {len(pages)} pages from {pdf_path.name}")
        return pages
    
    def _parse_with_pdfplumber(self, pdf_path: Path) -> List[Dict[str, any]]:
        """使用pdfplumber解析PDF"""
        pages = []
        
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                
                if text is None:
                    text = ""
                
                # 文本清洗
                text = self._clean_text(text)
                is_empty = len(text.strip()) == 0
                
                pages.append({
                    "page_number": page_num,
                    "text": text,
                    "is_empty": is_empty
                })
                
                logger.debug(f"Parsed page {page_num}: {len(text)} characters, empty={is_empty}")
        
        logger.info(f"Parsed {len(pages)} pages from {pdf_path.name}")
        return pages
    
    def _clean_text(self, text: str) -> str:
        """
        清洗文本：去除多余空行和空白字符
        
        Args:
            text: 原始文本
            
        Returns:
            清洗后的文本
        """
        if not text:
            return ""
        
        # 去除多余的空白字符
        text = re.sub(r'[ \t]+', ' ', text)  # 多个空格/制表符替换为单个空格
        
        # 去除多余的空行（保留最多一个空行）
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 去除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        # 去除首尾空白
        text = text.strip()
        
        return text
