# app.py

import os
from flask import Flask, render_template, request, jsonify
from datetime import datetime

# -------------------------------------------------------------------
# 1. 将您所有的核心逻辑函数粘贴到这里
#    这些函数与框架无关，可以直接复用
# -------------------------------------------------------------------
# =========================================================================
# 【核心变化】: 从编译后的模块导入函数，而不是在本地定义它们
# 当部署后，Python会找到 secure_core.so 并从中导入
import secure_core 
# =========================================================================
# 从环境变量加载后台默认配置
DEFAULT_SYSTEM_PROMPT = os.environ.get('DEFAULT_SYSTEM_PROMPT', "这是一个备用提示词，以防环境变量未设置。")


# -------------------------------------------------------------------
# 2. 创建Flask应用
# -------------------------------------------------------------------

app = Flask(__name__)

@app.route('/')
def index():
    """提供主网页界面"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """
    处理分析请求的API端点。这替代了所有的on_click事件处理。
    """
    # a. 验证输入
    if 'pdfFile' not in request.files:
        return jsonify({'error': '未找到上传的文件。'}), 400
    
    file = request.files['pdfFile']
    api_key = request.form.get('apiKey')
    custom_prompt = request.form.get('prompt')

    if file.filename == '':
        return jsonify({'error': '请选择一个文件。'}), 400
    if not api_key:
        return jsonify({'error': 'API Key是必需的。'}), 400

    # b. 决定使用哪个提示词
    final_system_prompt = custom_prompt if custom_prompt else DEFAULT_SYSTEM_PROMPT
    if not final_system_prompt:
        # 这是一个服务器配置错误
        return jsonify({'error': '服务器默认提示词丢失，请联系管理员。'}), 500

    try:
        # c. 执行核心逻辑
        pdf_content_bytes = file.read() # 直接在内存中读取文件内容
        markdown_list = process_pdf_to_markdown_list(pdf_content_bytes)

        if not markdown_list:
            return jsonify({'result': '处理完成：在PDF中未能找到可供分析的表格。'})

        final_result = analyze_tables_with_doubao(
            tables_data_list=markdown_list,
            ark_api_key=api_key,
            system_prompt=final_system_prompt
        )
        
        # d. 返回成功结果
        return jsonify({'result': final_result})

    except Exception as e:
        # e. 处理未知错误
        print(f"发生未知错误: {e}")
        # from openai import AuthenticationError
        # if isinstance(e, AuthenticationError):
        #     return jsonify({'error': '认证失败：您提供的API Key无效或已过期。'}), 401
        return jsonify({'error': '服务器处理时发生未知错误，请检查您的文件或联系管理员。'}), 500

if __name__ == '__main__':
    # 这只在本地开发时运行
    # Render会使用Gunicorn来启动应用
    app.run(host='0.0.0.0', port=5001, debug=True)
