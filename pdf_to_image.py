import fitz  # PyMuPDF
import os

# PDF文件路径
pdf_path = "NFPA702017-NationalElectricalCode.pdf"

# 打开PDF文件
doc = fitz.open(pdf_path)

print(f"PDF共有 {len(doc)} 页")

# 遍历每一页并转换为图片
for page_num in range(len(doc)):
    page = doc[page_num]
    
    # 设置缩放比例（2表示2倍分辨率，可根据需要调整）
    mat = fitz.Matrix(2, 2)
    
    # 渲染页面为图片
    pix = page.get_pixmap(matrix=mat)
    
    # 保存图片
    output_filename = f"NFPA702017_page_{page_num + 1:03d}.png"
    pix.save(output_filename)
    
    print(f"已保存: {output_filename}")

# 关闭文档
doc.close()
print("\n转换完成！")
