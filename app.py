# app.py (修正版)

import os
from flask import Flask, render_template, request, jsonify

# -------------------------------------------------------------------
# 【核心变化】: 从编译后的模块导入函数
# 我们的所有核心逻辑都封装在这个模块里
import secure_core 
# -------------------------------------------------------------------

app = Flask(__name__)

@app.route('/')
def index():
    """提供主网页界面"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """处理分析请求的API端点"""
    
    # a. 验证输入
    if 'pdfFile' not in request.files or not request.files['pdfFile'].filename:
        return jsonify({'error': '请选择一个文件。'}), 400
    
    api_key = request.form.get('apiKey')
    if not api_key:
        return jsonify({'error': 'API Key是必需的。'}), 400

    custom_prompt = request.form.get('prompt')
    file = request.files['pdfFile']

    try:
        # b. 执行核心逻辑
        pdf_content_bytes = file.read()
        
        # 【修正 #1】: 通过 secure_core 模块来调用函数
        markdown_list = secure_core.process_pdf_to_markdown_list(pdf_content_bytes)

        if not markdown_list:
            return jsonify({'result': '处理完成：在PDF中未能找到可供分析的表格。'})

        # 【修正 #2】: 通过 secure_core 模块来调用函数
        # 我们把 custom_prompt 传递给核心模块，
        # 让模块内部自己去判断是用 custom_prompt 还是用它内部的 DEFAULT_SYSTEM_PROMPT
        final_result = secure_core.analyze_tables_with_doubao(
            tables_data_list=markdown_list,
            ark_api_key=api_key,
            system_prompt=custom_prompt  # 即使custom_prompt是空字符串或None，也直接传过去
        )
        
        # c. 返回成功结果
        return jsonify({'result': final_result})

    except Exception as e:
        # d. 处理未知错误
        # 打印到后端日志，方便调试
        print(f"在 /analyze 路由中发生错误: {e}") 
        # 返回给前端一个通用的、安全的信息
        return jsonify({'error': '服务器在处理您的请求时发生内部错误，请稍后重试或联系管理员。'}), 500

if __name__ == '__main__':
    # 本地开发设置
    app.run(host='0.0.0.0', port=5001, debug=True)
