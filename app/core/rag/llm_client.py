# -*- coding: utf-8 -*-
"""
LLM客户端包装器
用于RAG引擎调用LLM生成回答
"""
import logging
import openai
from typing import Optional
from app.common.config import cfg
from app.core.entities import LLMServiceEnum

logger = logging.getLogger(__name__)


class RAGLLMClient:
    """RAG使用的LLM客户端"""
    
    def __init__(self):
        """初始化LLM客户端"""
        self.client = None
        self.model = None
        self._init_client()
    
    def _init_client(self):
        """初始化客户端"""
        try:
            current_service = cfg.get(cfg.llm_service)
            
            if current_service == LLMServiceEnum.OPENAI:
                base_url = cfg.get(cfg.openai_api_base)
                api_key = cfg.get(cfg.openai_api_key)
                model = cfg.get(cfg.openai_model)
            elif current_service == LLMServiceEnum.SILICON_CLOUD:
                base_url = cfg.get(cfg.silicon_cloud_api_base)
                api_key = cfg.get(cfg.silicon_cloud_api_key)
                model = cfg.get(cfg.silicon_cloud_model)
            elif current_service == LLMServiceEnum.DEEPSEEK:
                base_url = cfg.get(cfg.deepseek_api_base)
                api_key = cfg.get(cfg.deepseek_api_key)
                model = cfg.get(cfg.deepseek_model)
            elif current_service == LLMServiceEnum.GEMINI:
                base_url = cfg.get(cfg.gemini_api_base)
                api_key = cfg.get(cfg.gemini_api_key)
                model = cfg.get(cfg.gemini_model)
            elif current_service == LLMServiceEnum.CHATGLM:
                base_url = cfg.get(cfg.chatglm_api_base)
                api_key = cfg.get(cfg.chatglm_api_key)
                model = cfg.get(cfg.chatglm_model)
            else:
                # 默认使用OpenAI配置
                base_url = cfg.get(cfg.openai_api_base)
                api_key = cfg.get(cfg.openai_api_key)
                model = cfg.get(cfg.openai_model)
            
            if not api_key or api_key.strip() == "":
                logger.warning("LLM API key not configured")
                return
            
            self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
            self.model = model
            logger.info(f"LLM client initialized: {current_service.value}, model: {model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
    
    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        """
        生成文本
        
        Args:
            prompt: 提示词
            temperature: 温度参数
            
        Returns:
            生成的文本
        """
        if not self.client or not self.model:
            raise ValueError("LLM client not initialized")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                timeout=60
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Failed to generate text: {e}")
            raise


