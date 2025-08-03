# app.py (修正版)

import os
from flask import Flask, render_template, request, jsonify
import tempfile # <--- 导入tempfile库
import secure_core
import shutil
import subprocess

def check_ghostscript():
    """
    检查 Ghostscript 是否已安装，并打印其版本信息。
    """
    print("正在检查 Ghostscript 是否已安装...")

    # Ghostscript 的可执行文件名在不同操作系统上可能不同
    # Windows: gswin64c.exe 或 gswin32c.exe
    # Linux/macOS: gs
    # shutil.which 会在系统的 PATH 中查找这些命令
    gs_executable = shutil.which('gs') or shutil.which('gswin64c') or shutil.which('gswin32c')

    if gs_executable is None:
        # 如果 shutil.which 返回 None，说明在 PATH 中找不到任何一个可执行文件
        print("\n[错误] Ghostscript 未安装，或其安装路径未添加到系统的 PATH 环境变量中。")
        print("请参考这里的说明进行安装: https://camelot-py.readthedocs.io/en/latest/user/install-deps.html")
        return False
    
    try:
        # 如果找到了可执行文件，尝试运行它并获取版本号 (-v 参数)
        # 使用 subprocess.run 来执行命令
        result = subprocess.run(
            [gs_executable, '-v'],
            capture_output=True, # 捕获命令的标准输出和标准错误
            text=True,           # 将输出解码为文本
            check=True           # 如果命令返回非零退出码（表示错误），则抛出 CalledProcessError
        )
        
        # 如果命令成功执行，打印成功信息和版本详情
        print("\n[成功] Ghostscript 已安装完成！")
        print(f"可执行文件路径: {gs_executable}")
        print("版本信息:")
        # Ghostscript 的版本信息通常在标准输出的第一行
        print(result.stdout.splitlines()[0])
        return True

    except FileNotFoundError:
        # 这是一个备用检查，虽然 shutil.which 已经处理了大部分情况
        print("\n[错误] 无法找到 Ghostscript 可执行文件。")
        return False
    except subprocess.CalledProcessError as e:
        # 如果 gs -v 命令执行失败
        print(f"\n[错误] 调用 Ghostscript 时发生错误: {e}")
        print(f"标准输出:\n{e.stdout}")
        print(f"标准错误:\n{e.stderr}")
        return False
    except Exception as e:
        # 捕获其他未知异常
        print(f"\n[错误] 发生未知错误: {e}")
        return False
check_ghostscript()

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
