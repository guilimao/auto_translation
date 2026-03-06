#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标注NFPA702017_page_001.png中的两个图标"""

from PIL import Image, ImageDraw

# 读取图片
input_image = "NFPA702017_page_001.png"
output_image = "NFPA702017_page_001_annotated.png"

img = Image.open(input_image)
width, height = img.size
print(f"图片尺寸: {width} x {height}")

# 基于图片内容估算两个图标的位置（使用像素坐标）
# 图标1: NFPA标志（左上角）- 调整后的精确位置
icon1_bbox = [
    (int(0.055 * width), int(0.045 * height)),   # 左上
    (int(0.145 * width), int(0.115 * height))    # 右下（缩短高度）
]

# 图标2: See ALERT标志（中间偏上）- 最终精确位置
icon2_bbox = [
    (int(0.420 * width), int(0.540 * height)),   # 左上（再向下移动）
    (int(0.580 * width), int(0.600 * height))    # 右下
]

print(f"图标1 (NFPA标志) bbox: {icon1_bbox}")
print(f"图标2 (See ALERT标志) bbox: {icon2_bbox}")

# 创建绘图对象
draw = ImageDraw.Draw(img)

# 绘制图标1的bbox（红色）
draw.rectangle(icon1_bbox, outline="red", width=5)

# 绘制图标2的bbox（蓝色）
draw.rectangle(icon2_bbox, outline="blue", width=5)

# 添加标签说明
try:
    # 尝试使用默认字体
    label_y1 = icon1_bbox[0][1] - 20
    draw.text((icon1_bbox[0][0], label_y1), "Icon 1: NFPA", fill="red")
    
    label_y2 = icon2_bbox[0][1] - 20
    draw.text((icon2_bbox[0][0], label_y2), "Icon 2: See ALERT", fill="blue")
except:
    pass  # 如果字体问题则跳过

# 保存结果
img.save(output_image)
print(f"标注后的图片已保存为: {output_image}")
