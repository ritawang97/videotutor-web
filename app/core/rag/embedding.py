# -*- coding: utf-8 -*-
"""
Embedding生成模块
支持多种embedding模型：OpenAI、Gemini、本地sentence-transformers等
"""
import logging
from typing import List, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

# 可选导入sentence_transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

# 可选导入google genai (新版) 或 google.generativeai (旧版)
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
    GEMINI_NEW_API = True
except ImportError:
    try:
        import google.generativeai as genai
        genai_types = None
        GEMINI_AVAILABLE = True
        GEMINI_NEW_API = False
    except ImportError:
        GEMINI_AVAILABLE = False
        GEMINI_NEW_API = False
        genai = None
        genai_types = None


class EmbeddingGenerator:
    """Embedding生成器"""
    
    def __init__(self, model_type: str = "openai", api_key: Optional[str] = None, 
                 api_base: Optional[str] = None, model_name: Optional[str] = None):
        """
        初始化Embedding生成器
        
        Args:
            model_type: 模型类型 ("openai", "gemini" 或 "local")
            api_key: API密钥（OpenAI/Gemini需要）
            api_base: API基础URL（OpenAI需要，Gemini不需要）
            model_name: 模型名称
        """
        self.model_type = model_type
        self.api_key = api_key
        self.api_base = api_base or "https://api.openai.com/v1"
        self.model_name = model_name or ("text-embedding-ada-002" if model_type == "openai" else "gemini-embedding-001")
        self.local_model = None
        self.openai_client = None
        self.gemini_client = None
        
        if model_type == "local":
            # 使用本地sentence-transformers模型
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                raise ImportError(
                    "sentence-transformers is not installed. "
                    "Please install it with: pip install sentence-transformers"
                )
            try:
                self.local_model = SentenceTransformer(model_name or "paraphrase-multilingual-MiniLM-L12-v2")
                logger.info(f"Loaded local embedding model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load local embedding model: {e}")
                raise
        elif model_type == "gemini":
            if not GEMINI_AVAILABLE:
                raise ImportError(
                    "google-genai is not installed. "
                    "Please install it with: pip install google-genai"
                )
            if not api_key:
                raise ValueError("Gemini API key is required")
            # 清理API key（去除首尾空格）
            api_key = api_key.strip() if api_key else ""
            if not api_key:
                raise ValueError("Gemini API key is required and cannot be empty")
            try:
                if GEMINI_NEW_API:
                    # 使用新版API (google-genai)
                    self.gemini_client = genai.Client(api_key=api_key)
                    logger.info(f"Initialized Gemini embedding client (new API) with model: {self.model_name}")
                    # 验证API key格式（Gemini API key通常以AIza开头）
                    if not api_key.startswith("AIza"):
                        logger.warning(f"Gemini API key format may be incorrect (expected to start with 'AIza'): {api_key[:10]}...")
                else:
                    # 使用旧版API (google.generativeai - 已弃用)
                    genai.configure(api_key=api_key)
                    self.gemini_client = genai
                    logger.info(f"Initialized Gemini embedding client (legacy API) with model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                raise
        elif model_type == "openai":
            if not api_key:
                raise ValueError("OpenAI API key is required")
            self.openai_client = OpenAI(api_key=api_key, base_url=api_base)
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        生成文本的embedding向量
        
        Args:
            texts: 文本列表
            
        Returns:
            embedding向量列表
        """
        if not texts:
            return []
        
        try:
            if self.model_type == "local":
                return self.local_model.encode(texts, show_progress_bar=False).tolist()
            elif self.model_type == "gemini":
                # Gemini API
                if not self.gemini_client:
                    raise ValueError("Gemini client not initialized. Please check API key configuration.")
                try:
                    embeddings = []
                    # 检查是否是新版Client API
                    if GEMINI_NEW_API and hasattr(self.gemini_client, 'models'):
                        # 新版API: genai.Client()
                        logger.debug(f"Using new Gemini Client API with model: {self.model_name}")
                        for text in texts:
                            try:
                                # 使用正确的API格式：config参数
                                if genai_types:
                                    result = self.gemini_client.models.embed_content(
                                        model=self.model_name,
                                        contents=text,
                                        config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
                                    )
                                else:
                                    # 如果没有types模块，尝试不使用task_type
                                    result = self.gemini_client.models.embed_content(
                                        model=self.model_name,
                                        contents=text
                                    )
                                
                                # 新版API返回的对象，embeddings是列表，每个元素有values属性
                                if hasattr(result, 'embeddings'):
                                    emb_list = result.embeddings
                                    if isinstance(emb_list, list) and len(emb_list) > 0:
                                        # 每个embedding对象有values属性
                                        if hasattr(emb_list[0], 'values'):
                                            embeddings.append(emb_list[0].values)
                                        else:
                                            embeddings.append(emb_list[0])
                                    else:
                                        # 如果不是列表，直接使用
                                        if hasattr(emb_list, 'values'):
                                            embeddings.append(emb_list.values)
                                        else:
                                            embeddings.append(emb_list)
                                elif isinstance(result, dict) and 'embeddings' in result:
                                    emb = result['embeddings']
                                    if isinstance(emb, list) and len(emb) > 0:
                                        if isinstance(emb[0], dict) and 'values' in emb[0]:
                                            embeddings.append(emb[0]['values'])
                                        else:
                                            embeddings.append(emb[0])
                                    else:
                                        embeddings.append(emb)
                                else:
                                    logger.warning(f"Unexpected Gemini embedding result format: {type(result)}")
                                    raise ValueError(f"Unexpected Gemini embedding result format: {type(result)}")
                            except Exception as e:
                                logger.error(f"Error generating embedding for text (length: {len(text)}): {e}")
                                raise
                    else:
                        # 旧版API: genai.configure() + genai.embed_content()
                        logger.debug(f"Using legacy Gemini API with model: {self.model_name}")
                        for text in texts:
                            try:
                                result = genai.embed_content(
                                    model=self.model_name,
                                    content=text,
                                    task_type="retrieval_document"
                                )
                                # 旧版API返回字典
                                if isinstance(result, dict) and 'embedding' in result:
                                    embeddings.append(result['embedding'])
                                elif hasattr(result, 'embedding'):
                                    embeddings.append(result.embedding)
                                else:
                                    logger.warning(f"Unexpected Gemini embedding result format: {type(result)}")
                                    raise ValueError(f"Unexpected Gemini embedding result format: {type(result)}")
                            except Exception as e:
                                logger.error(f"Error generating embedding for text (length: {len(text)}): {e}")
                                raise
                    return embeddings
                except Exception as api_error:
                    error_msg = str(api_error)
                    # 提供更友好的错误信息
                    if "api_key" in error_msg.lower() or "authentication" in error_msg.lower() or "invalid" in error_msg.lower():
                        raise ValueError(f"API认证失败: 请检查Gemini API Key是否正确配置。错误详情: {error_msg}")
                    elif "rate_limit" in error_msg.lower() or "quota" in error_msg.lower():
                        raise ValueError(f"API额度不足: {error_msg}")
                    elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                        raise ValueError(f"网络连接失败: {error_msg}")
                    else:
                        raise ValueError(f"Gemini API调用失败: {error_msg}")
            else:
                # OpenAI API
                if not self.openai_client:
                    raise ValueError("OpenAI client not initialized. Please check API key configuration.")
                try:
                    response = self.openai_client.embeddings.create(
                        model=self.model_name,
                        input=texts
                    )
                    return [item.embedding for item in response.data]
                except Exception as api_error:
                    error_msg = str(api_error)
                    # 提供更友好的错误信息
                    if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                        raise ValueError(f"API认证失败: 请检查OpenAI API Key是否正确配置。错误详情: {error_msg}")
                    elif "rate_limit" in error_msg.lower() or "quota" in error_msg.lower():
                        raise ValueError(f"API额度不足: {error_msg}")
                    elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                        raise ValueError(f"网络连接失败: {error_msg}")
                    else:
                        raise ValueError(f"OpenAI API调用失败: {error_msg}")
        except ValueError:
            # 重新抛出ValueError（包含友好错误信息）
            raise
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        生成单个文本的embedding向量
        
        Args:
            text: 文本
            
        Returns:
            embedding向量
        """
        return self.generate_embeddings([text])[0]

