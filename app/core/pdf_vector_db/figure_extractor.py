# -*- coding: utf-8 -*-
"""
PDF图片提取模块
从PDF页面中提取图片并保存为PNG文件
"""

import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import io

from app.core.utils.logger import setup_logger

logger = setup_logger("FigureExtractor")

# 尝试导入PIL用于图片分析
try:
    from PIL import Image, ImageStat
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    ImageStat = None

# 尝试导入PyMuPDF
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None


@dataclass
class AssetCreate:
    """资产创建数据类"""
    asset_id: str
    doc_id: str
    page_no: int
    bbox: List[float]  # [x0, y0, x1, y1]
    image_path: str
    type: str = "figure"
    teacher_note: Optional[str] = None


def is_meaningful_image(image_bytes: bytes, min_width: int = 50, min_height: int = 50, 
                        max_color_ratio: float = 0.95, min_unique_colors: int = 10) -> bool:
    """
    检查图片是否有意义（不是纯色、太小或异常形状）
    
    Args:
        image_bytes: 图片字节数据
        min_width: 最小宽度（像素）
        min_height: 最小高度（像素）
        max_color_ratio: 最大单一颜色占比（超过此比例认为是纯色）
        min_unique_colors: 最小唯一颜色数量
    
    Returns:
        True表示图片有意义，False表示应该过滤掉
    """
    if not PIL_AVAILABLE:
        # 如果没有PIL，无法分析，默认保留
        logger.warning("PIL not available, cannot filter images. Install Pillow for image filtering.")
        return True
    
    try:
        # 从字节数据加载图片
        img = Image.open(io.BytesIO(image_bytes))
        
        # 检查尺寸
        width, height = img.size
        if width < min_width or height < min_height:
            logger.debug(f"Image too small: {width}x{height}, filtering out")
            return False
        
        # 检查宽高比（太极端的长条形或扁条形可能是装饰性元素）
        aspect_ratio = max(width, height) / min(width, height)
        if aspect_ratio > 20:  # 长宽比超过20:1认为是异常形状
            logger.debug(f"Image aspect ratio too extreme: {aspect_ratio:.2f}, filtering out")
            return False
        
        # 转换为RGB模式（如果是RGBA或其他模式）
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 获取图片统计信息
        stat = ImageStat.Stat(img)
        
        # 计算唯一颜色数量（使用量化来加速）
        # 将图片缩小并量化以减少计算量
        small_img = img.resize((100, 100), Image.Resampling.LANCZOS)
        colors = small_img.getcolors(maxcolors=256*256*256)  # 获取所有颜色
        
        if colors is None:
            # 如果颜色太多，使用另一种方法
            # 检查颜色方差（纯色图片方差很小）
            color_variance = sum([stat.stddev[i] for i in range(3)])
            if color_variance < 5:  # 方差太小，可能是纯色或接近纯色
                logger.debug(f"Image color variance too low: {color_variance:.2f}, filtering out")
                return False
        else:
            unique_colors = len(colors)
            if unique_colors < min_unique_colors:
                logger.debug(f"Image has too few unique colors: {unique_colors}, filtering out")
                return False
            
            # 检查是否有单一颜色占比过高
            total_pixels = sum([count for count, _ in colors])
            max_color_count = max([count for count, _ in colors])
            max_color_ratio_actual = max_color_count / total_pixels if total_pixels > 0 else 0
            
            if max_color_ratio_actual > max_color_ratio:
                logger.debug(
                    f"Image has dominant color ratio: {max_color_ratio_actual:.2%}, filtering out"
                )
                return False
        
        # 检查是否是纯白色或纯黑色
        # 计算平均亮度
        if img.mode == 'RGB':
            # 转换为灰度并计算平均值
            gray = img.convert('L')
            avg_brightness = ImageStat.Stat(gray).mean[0]
            
            # 如果平均亮度接近0（纯黑）或255（纯白），可能是无意义的图片
            if avg_brightness < 5 or avg_brightness > 250:
                # 但需要检查是否有足够的颜色变化
                brightness_std = ImageStat.Stat(gray).stddev[0]
                if brightness_std < 10:  # 亮度标准差太小，可能是纯色
                    logger.debug(
                        f"Image appears to be solid color (brightness: {avg_brightness:.1f}, "
                        f"std: {brightness_std:.1f}), filtering out"
                    )
                    return False
        
        return True
        
    except Exception as e:
        logger.warning(f"Failed to analyze image for filtering: {e}, keeping image")
        # 如果分析失败，默认保留图片
        return True


def extract_figures_from_pdf(pdf_path: Path, doc_id: str, assets_base_dir: Path) -> List[AssetCreate]:
    """
    从PDF中提取所有图片
    
    Args:
        pdf_path: PDF文件路径
        doc_id: 文档ID（通常是文件名，不含扩展名）
        assets_base_dir: 资产存储基础目录（例如：assets/）
        
    Returns:
        资产创建对象列表
    """
    if not PYMUPDF_AVAILABLE:
        raise ImportError(
            "PyMuPDF is not installed. Please install it with: pip install pymupdf"
        )
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    assets = []
    
    try:
        doc = fitz.open(str(pdf_path))
        
        # 为每个文档创建资产目录
        doc_assets_dir = assets_base_dir / doc_id
        doc_assets_dir.mkdir(parents=True, exist_ok=True)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_no = page_num + 1  # 1-based
            
            # 获取页面中的所有图片
            image_list = page.get_images(full=True)
            
            if not image_list:
                logger.debug(f"No images found on page {page_no}")
                continue
            
            # 为每个页面创建目录
            page_dir = doc_assets_dir / f"page_{page_no}"
            page_dir.mkdir(parents=True, exist_ok=True)
            
            # 提取每个图片
            for img_idx, img in enumerate(image_list):
                try:
                    # 获取图片引用
                    xref = img[0]
                    
                    # 获取图片数据
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # 转换为PNG格式（如果需要）
                    if image_ext.lower() not in ["png", "jpg", "jpeg"]:
                        # 如果格式不是PNG，保存时使用PNG扩展名
                        image_ext = "png"
                    
                    # 检查图片是否有意义（过滤无意义的图片）
                    if not is_meaningful_image(image_bytes):
                        logger.debug(
                            f"Skipping meaningless image {img_idx} from page {page_no} "
                            f"(likely solid color, too small, or unusual shape)"
                        )
                        continue
                    
                    # 保存图片
                    image_filename = f"img_{img_idx}.{image_ext}"
                    image_path = page_dir / image_filename
                    
                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)
                    
                    # 获取图片在页面上的位置（边界框）
                    # 查找图片在页面中的位置
                    image_rects = page.get_image_rects(xref)
                    
                    if image_rects:
                        # 使用第一个矩形作为边界框
                        rect = image_rects[0]
                        bbox = [rect.x0, rect.y0, rect.x1, rect.y1]
                    else:
                        # 如果没有找到位置信息，使用页面尺寸作为默认值
                        page_rect = page.rect
                        bbox = [0.0, 0.0, page_rect.width, page_rect.height]
                        logger.warning(
                            f"Could not determine bbox for image {img_idx} on page {page_no}, "
                            f"using page dimensions"
                        )
                    
                    # 生成唯一资产ID
                    asset_id = f"{doc_id}_page{page_no}_img{img_idx}"
                    
                    # 创建资产对象
                    asset = AssetCreate(
                        asset_id=asset_id,
                        doc_id=doc_id,
                        page_no=page_no,
                        bbox=bbox,
                        type="figure",
                        image_path=str(image_path)
                    )
                    
                    assets.append(asset)
                    logger.debug(
                        f"Extracted image {img_idx} from page {page_no}: {image_path} "
                        f"(bbox: {bbox})"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Failed to extract image {img_idx} from page {page_no}: {e}",
                        exc_info=True
                    )
                    continue
        
        doc.close()
        logger.info(
            f"Extracted {len(assets)} images from {len(doc)} pages in {pdf_path.name}"
        )
        
    except Exception as e:
        logger.error(f"Failed to extract figures from PDF {pdf_path}: {e}", exc_info=True)
        raise
    
    return assets
