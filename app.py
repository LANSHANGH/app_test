# app.py (修正版)

import os
from flask import Flask, render_template, request, jsonify
import tempfile # <--- 导入tempfile库
import secure_core
import shutil
import subprocess



app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'pdfFile' not in request.files or not request.files['pdfFile'].filename:
        return jsonify({'error': '请选择一个文件。'}), 400
    if not request.form.get('apiKey'):
        return jsonify({'error': 'API Key是必需的。'}), 400

    file = request.files['pdfFile']
    api_key = request.form.get('apiKey')
    custom_prompt = request.form.get('prompt')

    # 使用 with 语句来安全地管理临时文件
    # NamedTemporaryFile会创建一个带名字的临时文件
    # delete=False 是为了在with块结束后文件不会马上被删除，方便调试。
    # 在生产环境中，可以设为True，或者在finally中手动删除。
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
        try:
            # 1. 将上传的文件内容保存到临时文件中
            file.save(temp_pdf.name)
            temp_pdf_path = temp_pdf.name
            
            # 2. 调用核心逻辑，【传递临时文件的路径】
            markdown_list = secure_core.process_pdf_to_markdown_list(temp_pdf_path)

            if not markdown_list:
                return jsonify({'result': '处理完成：在PDF中未能找到可供分析的表格。'})

            # 3. 调用AI分析逻辑
            final_result = secure_core.analyze_tables_with_doubao(
                tables_data_list=markdown_list,
                ark_api_key=api_key,
                system_prompt=custom_prompt
            )
            
            return jsonify({'result': final_result})

        except Exception as e:
            print(f"在 /analyze 路由中发生错误: {e}")
            return jsonify({'error': '服务器在处理您的请求时发生内部错误。'}), 500
        
        finally:
            # 4. 【重要】无论成功与否，都要确保清理临时文件
            if os.path.exists(temp_pdf.name):
                os.remove(temp_pdf.name)
                print(f"临时文件 '{temp_pdf.name}' 已清理。")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
