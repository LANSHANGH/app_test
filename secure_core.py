# ---------------------------------
# 2. 导入模块
# ---------------------------------
import io
import fitz  # PyMuPDF
import os
from openai import OpenAI
import os
from typing import Optional
from datetime import datetime # 导入datetime模块用于生成时间戳
# ==============================================================================
#                 PDF表格智能提取引擎 - V8 (语义分组最终版)
#
# 描述:
# 在V7.1的基础上，增加了最终的“语义分组”阶段。此版本能够根据表名的
# 核心中文字符串，将所有逻辑上属于同一系列的表格归类到一起，
# 是目前最完整、最智能的解决方案。
# ==============================================================================
import camelot, fitz
import pandas as pd
from typing import List, Dict, Any
import re
# --- 全局自适应参数 ---
# ==============================================================================
# 【终极修复】: 在Python运行时强制设置PATH环境变量
# ==============================================================================
# Linux系统中，通过apt-get安装的程序通常都在这些路径下
standard_paths = [
    '/usr/local/sbin',
    '/usr/local/bin',
    '/usr/sbin',
    '/usr/bin',
    '/sbin',
    '/bin'
]
# 获取当前的PATH，如果不存在则为空
current_path = os.environ.get('PATH', '')
# 将标准路径添加到当前PATH的前面，确保它们被优先搜索
# 使用set来避免重复路径
new_path_parts = list(dict.fromkeys(standard_paths + current_path.split(os.pathsep)))
new_path = os.pathsep.join(new_path_parts)
os.environ['PATH'] = new_path

# 打印出最终的PATH，用于在Render日志中进行调试验证
print(f"DEBUG: Python runtime PATH set to: {os.environ['PATH']}")

print(f"正在使用的 Camelot 版本是: {camelot.__version__}")
print(f"即将使用 backend='pdfium' 调用 camelot.read_pdf")


TITLE_KEYWORDS = ['表', '附表', '图', '表格', '列表', '一览表', 'Table', 'Fig', 'Figure', 'Chart', 'List']

STRUCTURED_CONTEXT_KEYWORDS = [
    '工程名称', '项目名称', '项目名', '工程编号', '合同号', '标段', 'Project Name',
    '位置', '部位', '里程', '桩号', '孔号', '监测点', '测点', '设备名称', '设备编号', 'Location', 'Point ID',
    '日期', '时间', '开始日期', '结束日期', '报告日期', '监测时段', 'Date', 'Time',
    '监测仪器', '监测方法', '测值法', '监测内容', '基准点', '初始值', '高程', 'Instrument', 'Method',
    '监测单位', '施工单位', '监理单位', '记录人', '审核人', '负责人', 'Company', 'Operator',
    '天气', '气温', '状况', '情况', '备注', '说明', 'Weather', 'Temp', 'Remarks'
]

FINAL_FILTER_KEYWORDS = ['成果表', '结果', '成果']
# (新的全局变量)
FINAL_FILTER_REGEX_PATTERNS = [
    r'(成果|结果)[\u4e00-\u9fa5]*表'
]

def check_ghostscript_exists():
    """检查系统中是否存在Ghostscript命令"""
    return shutil.which("gs") or shutil.which("gswin6arantec")
    
# --- V8新增辅助函数 ---
def get_chinese_chars(text: str) -> str:
    """从字符串中提取所有中文字符，作为语义分组的键。"""
    if not isinstance(text, str):
        return ""
    # 正则表达式匹配所有中文字符 (Unicode范围: \u4e00-\u9fa5)
    chinese_only = re.findall(r'[\u4e00-\u9fa5]', text)
    return "".join(chinese_only)


# --- 之前版本的所有稳定函数 (此处为了简洁，仅保留函数签名) ---

def find_potential_titles_for_memory(page: fitz.Page) -> List[Dict[str, Any]]:
    # ... V7.1的完整代码 ...
    titles = []
    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        if block['type'] == 0:
            for line in block['lines']:
                if line['spans']:
                    span = line['spans'][0]
                    line_text = "".join(s['text'] for s in line['spans']).strip()
                    if span['size'] > 13 and any(keyword in line_text for keyword in TITLE_KEYWORDS):
                        titles.append({"text": line_text, "bbox": line['bbox']})
    return titles

def find_title_on_page_in_boundary(page: fitz.Page, table_top_y: float, search_top_y: float) -> Dict[str, Any]:
    # ... V7.1的完整代码 ...
    max_font_size, title_info = 0, None
    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        if block['type'] == 0:
            for line in block['lines']:
                if search_top_y < line['bbox'][1] and line['bbox'][3] < table_top_y:
                    line_text = "".join(s['text'] for s in line['spans']).strip()
                    if not line_text or not line['spans']: continue
                    current_size = line['spans'][0]['size']
                    if current_size > max_font_size and any(kw in line_text for kw in TITLE_KEYWORDS):
                        max_font_size, title_info = current_size, {"text": line_text, "bbox": line['bbox']}
    return title_info

def find_title_on_page(page: fitz.Page, table_top_y: float) -> Dict[str, Any]:
    max_font_size, title_info = 0, None
    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        if block['type'] == 0:
            for line in block['lines']:
                if line['bbox'][3] < table_top_y:
                    line_text = "".join(s['text'] for s in line['spans']).strip()
                    if not line_text or not line['spans']: continue
                    current_size = line['spans'][0]['size']
                    if current_size > max_font_size and any(kw in line_text for kw in TITLE_KEYWORDS):
                        max_font_size, title_info = current_size, {"text": line_text, "bbox": line['bbox']}
    return title_info


def classify_context_lines(page: fitz.Page, search_bbox: tuple) -> tuple[list, list]:
    # ... V7.1的完整代码 ...
    structured_lines, other_lines = [], []
    search_area_top, search_area_bottom = search_bbox[1], search_bbox[3]
    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        if block['type'] == 0:
            for line in block['lines']:
                if search_area_top < line['bbox'][1] and line['bbox'][3] < search_area_bottom:
                    line_text = "".join(s['text'] for s in line['spans']).strip()
                    if not line_text: continue
                    if any(keyword in line_text for keyword in STRUCTURED_CONTEXT_KEYWORDS):
                        structured_lines.append(line_text)
                    else:
                        other_lines.append(line_text)
    return structured_lines, other_lines

# ==============================================================================
#                      (最终版) 标题识别引擎
#        (采用“局部优先，有限回溯”策略，在表格上方5行内查找，最多跨一页)
# ==============================================================================

def _get_lines_from_page(page: fitz.Page) -> List[str]:
    """一个简单的辅助函数，获取页面上所有排序好的文本行。"""
    lines = []
    blocks = page.get_text("dict")["blocks"]
    # 按垂直位置排序
    blocks.sort(key=lambda b: b['bbox'][1])
    for block in blocks:
        if block['type'] == 0:
            for line in block['lines']:
                lines.append("".join(s['text'] for s in line['spans']).strip())
    return lines

def find_title_with_limited_lookback(
    current_page_num: int,
    current_page_fitz: fitz.Page,
    pdf_document: fitz.Document,
    table_bbox_fitz: tuple
) -> str:
    """
    (最终版核心) 在表格上方5行内查找标题，如果找不到，则向上回溯一页的最后5行。
    """

    # --- 步骤1: 优先在当前页的邻近5行内搜索 ---
    lines_above_on_current_page = []
    blocks = current_page_fitz.get_text("dict")["blocks"]
    for block in blocks:
        if block['type'] == 0:
            for line in block['lines']:
                if line['bbox'][3] < table_bbox_fitz[1]: # 行在表格上方
                    lines_above_on_current_page.append("".join(s['text'] for s in line['spans']).strip())

    nearby_lines_current = lines_above_on_current_page[-5:]

    # 在这5行中，从下往上，寻找第一个包含标题关键词的行
    for line_text in reversed(nearby_lines_current):
        if any(keyword in line_text for keyword in TITLE_KEYWORDS):
            print(f"    -> 标题识别: 在当前页邻近区域找到标题: '{line_text}'")
            return line_text

    # --- 步骤2: 如果当前页未找到，则尝试向上回溯一页 ---
    if current_page_num > 1:
        print(f"    -> 标题识别: 当前页未找到，尝试回溯到第 {current_page_num - 1} 页...")
        previous_page_fitz = pdf_document.load_page(current_page_num - 2)

        # 获取上一页的所有行，并只取最后的5行
        lines_on_previous_page = _get_lines_from_page(previous_page_fitz)
        nearby_lines_previous = lines_on_previous_page[-5:]

        # 在这5行中，从下往上，寻找第一个包含标题关键词的行
        for line_text in reversed(nearby_lines_previous):
            if any(keyword in line_text for keyword in TITLE_KEYWORDS):
                print(f"    -> 标题识别: 在上一页底部找到跨页标题: '{line_text}'")
                return line_text

    # 如果所有尝试都失败
    print(f"    -> 标题识别: 未在任何邻近区域找到标题。")
    return "N/A (未关联)"


def extract_and_merge_fragments(pdf_path: str) -> List[Dict[str, Any]]:
    # ... V7.1的完整代码 ...
    all_results = []
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    gs_path = check_ghostscript_exists()
    if gs_path:
        print(f"诊断信息：检测到 Ghostscript 存在于: {gs_path}")
    else:
        print("诊断信息：未检测到 Ghostscript。如果代码能成功运行，则证明 pdfium 生效。")
    print(f"✅ (阶段1) PDF文件打开成功，共 {total_pages} 页。开始提取所有表格片段...")
    active_title_context = None
    for page_num in range(1, total_pages + 1):
        print(f"\n{'='*20} 正在提取第 {page_num} / {total_pages} 页 {'='*20}")
        page_fitz = doc.load_page(page_num - 1)
        try:
            tables_on_page = camelot.read_pdf(pdf_path, pages=str(page_num), flavor='lattice',backend="pdfium")
            if tables_on_page.n == 0:
                tables_on_page = camelot.read_pdf(pdf_path, pages=str(page_num), flavor='stream',backend="pdfium")
        except Exception as e:
            print(f"  -- Camelot 在本页提取时出错: {e}, 跳过。")
            continue
        print(f"  -- 在本页找到 {tables_on_page.n} 个表格片段。")

        all_titles_on_page = sorted(find_potential_titles_for_memory(page_fitz), key=lambda x: x['bbox'][1])
        for table in tables_on_page:
            table_bbox_fitz = (table._bbox[0], page_fitz.rect.height - table._bbox[3], table._bbox[2], page_fitz.rect.height - table._bbox[1])
            title_on_this_page = find_title_on_page(page_fitz, table_bbox_fitz[1])
            final_title_context = None
            if title_on_this_page:
                final_title_context = title_on_this_page
                active_title_context = title_on_this_page
            elif active_title_context:
                final_title_context = active_title_context
            structured_info, other_info = [], []
            if final_title_context:
                metadata_zone = (0, final_title_context['bbox'][3], page_fitz.rect.width, table_bbox_fitz[1])
                structured_info, other_info = classify_context_lines(page_fitz, metadata_zone)
            # 1. 首先，获取临时的表名，用于判断
            temp_table_name = final_title_context['text'] if final_title_context else "N/A (未关联)"

            # 2. (核心修改) 根据表名是否符合关键词，来决定如何构建 result 字典
            if any(re.search(pattern, temp_table_name) for pattern in FINAL_FILTER_REGEX_PATTERNS):
                # --- 如果符合条件，创建完整的 result 字典 ---
                print(f"    -> 筛选通过: 表格 '{temp_table_name}' 的完整信息已被采纳。")
                result = {
                    "page": page_num,
                    "table_name": temp_table_name,
                    "structured_context": structured_info or None,
                    "other_context": other_info or None,
                    "table_dataframe": table.df
                }
            else:
                # --- 如果不符合条件，创建“降级”的 result 字典 ---
                print(f"    -> 筛选未通过: 表格 '{temp_table_name}' 的上下文信息已被降级处理。")
                result = {
                    "page": page_num,
                    "table_name": "N/A (未关联)",  # 强制设置为 "N/A"
                    "structured_context": None,          # 强制设置为 None
                    "other_context": None,               # 强制设置为 None
                    "table_dataframe": table.df          # 依然保留原始数据
                }

            # 3. 将最终构建的 result (无论是完整版还是降级版) 添加到列表中
            all_results.append(result)
        if all_titles_on_page:
            active_title_context = all_titles_on_page[-1]
    doc.close()
    print("\n✅ (阶段2) 开始对提取的表格片段进行智能合并...")
    if not all_results: return []
    grouped_by_name = {}
    for res in all_results:
        name = res['table_name']
        if name not in grouped_by_name: grouped_by_name[name] = []
        grouped_by_name[name].append(res)
    final_merged_results = []
    for name, tables_group in grouped_by_name.items():
        if len(tables_group) == 1 or name == "N/A (未关联)":
            final_merged_results.extend(tables_group)
            continue
        first_part = tables_group[0]
        dataframes_to_merge = [part['table_dataframe'] for part in tables_group]
        try:
            merged_df = pd.concat(dataframes_to_merge, ignore_index=True)
            merged_result = {"page": first_part['page'],"table_name": name,"structured_context": first_part['structured_context'],"other_context": first_part['other_context'],"table_dataframe": merged_df,"is_merged": True,"source_pages": sorted(list(set(p['page'] for p in tables_group)))}
            final_merged_results.append(merged_result)
        except Exception:
            final_merged_results.extend(tables_group)
    return final_merged_results

def enhance_results_with_internal_titles(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # ... V7.1的完整代码 ...
    print("\n✅ (阶段3) 开始对无主表格进行内省式标题修正...")
    enhanced_results = []
    for result in results:
        if result['table_name'] == "N/A (未关联)":
            df = result['table_dataframe']
            if df.empty or len(df.columns) == 0:
                enhanced_results.append(result)
                continue
            first_row = df.iloc[0]
            if first_row.count() == 1:
                internal_title = first_row.dropna().iloc[0]
                result['table_name'] = internal_title
                new_df = df.copy().iloc[1:].reset_index(drop=True)
                context_rows, rows_to_drop = [], []
                for index, row in new_df.iterrows():
                    row_text = ' '.join(row.dropna().astype(str))
                    if any(kw in row_text for kw in STRUCTURED_CONTEXT_KEYWORDS):
                        context_rows.append(row_text)
                        rows_to_drop.append(index)
                if context_rows:
                    if not result['structured_context']: result['structured_context'] = []
                    result['structured_context'].extend(context_rows)
                result['table_dataframe'] = new_df.drop(rows_to_drop).reset_index(drop=True)
        enhanced_results.append(result)
    return enhanced_results

# ==============================================================================
#                      (V10.2) 最终版内省式标题修正函数
# ==============================================================================

def is_text_centered(text_bbox: tuple, container_bbox: tuple, tolerance: float = 0.1) -> bool:
    """
    辅助函数：判断一个文本框是否在容器框内居中。
    """
    text_center_x = (text_bbox[0] + text_bbox[2]) / 2
    container_center_x = (container_bbox[0] + container_bbox[2]) / 2
    container_width = container_bbox[2] - container_bbox[0]

    # 如果中心点差异小于容器宽度的10%，则认为是居中
    return abs(text_center_x - container_center_x) < container_width * tolerance

# (新增) V10.2 全局参数
TITLE_ANCHOR_KEYWORDS = ['监测项', '监测项目', '项目名称']

def enhance_results_with_internal_titles(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    (V10.2 语义锚点版) 对无外部标题的表格进行多规则内省，优先使用语义锚点。
    """
    print("\n✅ (阶段3) 开始对无主表格进行内省式标题修正 (V3 语义锚点版)...")
    enhanced_results = []

    for result in results:
        # 只处理那些没有找到外部标题的表格
        if result.get('table_name') == "N/A (未关联)":
            df = result['table_dataframe'].copy()
            if df.empty or len(df.columns) < 2: # 至少需要两列才能有键值对
                enhanced_results.append(result)
                continue

            header_rows_limit = min(5, len(df))
            header_df = df.head(header_rows_limit)
            page_num = result['page']
            internal_title = None
            title_found = False
            rows_to_drop_indices = []

            # --- 规则一 (最高优先级): 语义锚点规则 ---
            for index, row in header_df.iterrows():
                for col_idx, cell_value in enumerate(row):
                    # 检查单元格是否是我们的锚点关键词
                    if str(cell_value).strip() in TITLE_ANCHOR_KEYWORDS:
                        # 确保右侧有单元格
                        if col_idx + 1 < len(row):
                            internal_title = str(df.iloc[index, col_idx + 1]).strip()
                            # 将完整的标题拼接起来
                            # 查找同一行中可能存在的其他部分
                            title_parts = [internal_title]
                            for next_cell in row[col_idx+2:]:
                                if pd.notna(next_cell) and str(next_cell).strip():
                                     title_parts.append(str(next_cell).strip())
                                else:
                                    break # 遇到空值则停止
                            internal_title = " ".join(title_parts)

                            print(f"  -- 规则1命中: 在第 {result['page']} 页通过锚点'{str(cell_value).strip()}'找到标题: '{internal_title}'")
                            title_found = True
                            break
                if title_found: break

            # --- 规则二 (备用): 单格纯中文标题规则 (您的修改) ---
            for index, row in header_df.iterrows():
                # 1. 获取当前行的所有非空文本
                row_texts = [str(v).strip() for v in row.values if pd.notna(v) and str(v).strip()]
                if not row_texts: continue

                dominant_text = None

                # 2. 应用“优势文本”判断逻辑
                if len(row_texts) == 1:
                    # 如果只有一个非空文本，它就是优势文本
                    dominant_text = row_texts[0]
                elif len(row_texts) > 1:
                    # 如果有多个，则判断是否存在一个“鹤立鸡群”的
                    row_texts.sort(key=len, reverse=True)
                    longest_text = row_texts[0]
                    other_texts_len = sum(len(s) for s in row_texts[1:])

                    # 核心规则：最长的文本长度，必须大于其他所有文本总长度的5倍
                    if len(longest_text) > other_texts_len * 5:
                        dominant_text = longest_text

                # 3. 如果找到了优势文本，再进行语义检查
                if dominant_text:
                    def is_mostly_chinese(text: str) -> bool:
                        if not text: return False
                        text_for_check = re.sub(r'[【】\s-]', '', text)
                        if not text_for_check: return False
                        chinese_chars = re.findall(r'[\u4e00-\u9fa5]', text_for_check)
                        return len(chinese_chars) / len(text_for_check) > 0.8

                    if is_mostly_chinese(dominant_text):
                        internal_title = dominant_text
                        title_row_idx = index
                        title_found = True
                        print(f"  -- 优势文本规则命中: 在第 {page_num} 页找到内嵌标题: '{internal_title}'")
                        break # 找到即停止

            # --- 数据清理与更新 ---
            if title_found:
                result['table_name'] = internal_title

                # 重新提取所有上下文并清理DataFrame
                context_rows = []
                data_header_row_idx = -1
                max_cells = 0

                for index, row in header_df.iterrows():
                    row_text = ' '.join(row.dropna().astype(str))
                    # 找到真正的列标题行（最多非空单元格的行）
                    if row.count() > max_cells:
                        max_cells = row.count()
                        data_header_row_idx = index
                    # 将非列标题的表头行作为上下文
                    context_rows.append(row_text)

                # 将找到的上下文信息添加到结果中
                if context_rows:
                    if not result.get('structured_context'): result['structured_context'] = []
                    result['structured_context'].extend(context_rows)

                # 从原始df中删除所有被识别为“大表头”的行
                if data_header_row_idx != -1:
                    new_columns = df.iloc[data_header_row_idx]
                    # 从数据头行的下一行开始，才是真正的表格数据
                    final_df = df.iloc[data_header_row_idx + 1:].reset_index(drop=True)
                    final_df.columns = [str(c) if pd.notna(c) else f'col_{i}' for i, c in enumerate(new_columns)]
                    result['table_dataframe'] = final_df
                else:
                    # 如果找不到数据头，可能是个简单的表，只移除标题行
                    result['table_dataframe'] = df.iloc[1:].reset_index(drop=True)

        enhanced_results.append(result)

    print("✅ 内省修正完成。")
    return enhanced_results

def filter_results_by_keywords(results: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    # ... V6的完整代码 ...
    filtered_list = []
    print(f"\n✅ (阶段4) 开始根据关键词 {keywords} 筛选最终结果...")
    for result in results:
        match_found = False
        if result.get('table_name') and any(kw in result['table_name'] for kw in keywords): match_found = True
        if not match_found and result.get('structured_context'):
            if any(any(kw in line for kw in keywords) for line in result['structured_context']): match_found = True
        if not match_found and result.get('other_context'):
            if any(any(kw in line for kw in keywords) for line in result['other_context']): match_found = True
        if match_found: filtered_list.append(result)
    print(f"✅ 筛选完成。共筛选出 {len(filtered_list)} 个符合条件的表格。")
    return filtered_list
def _check_text_with_regex(text: str, patterns: List[str]) -> bool:
    """一个辅助函数，检查单个文本是否匹配任何一个正则表达式模式。"""
    if not text:
        return False
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False

def filter_results_by_keywords(results: List[Dict[str, Any]], regex_patterns: List[str]) -> List[Dict[str, Any]]:
    """
    (V13版) 根据一个正则表达式模式列表，对所有逻辑完整的表格进行筛选。
    """
    filtered_list = []
    print(f"\n✅ (阶段4) 开始根据正则表达式 {regex_patterns} 筛选最终结果...")

    for result in results:
        match_found = False

        # 1. 检查表名
        if _check_text_with_regex(result.get('table_name'), regex_patterns):
            match_found = True

        # 2. 检查结构化上下文 (如果还没找到匹配)
        if not match_found and result.get('structured_context'):
            # any() 会在找到第一个匹配的行后就停止，非常高效
            if any(_check_text_with_regex(line, regex_patterns) for line in result['structured_context']):
                match_found = True

        # 3. 检查其他上下文 (如果还没找到匹配)
        if not match_found and result.get('other_context'):
             if any(_check_text_with_regex(line, regex_patterns) for line in result['other_context']):
                match_found = True

        # 如果在任何地方找到了匹配，就将这个结果加入最终列表
        if match_found:
            filtered_list.append(result)

    print(f"✅ 筛选完成。共筛选出 {len(filtered_list)} 个符合条件的表格。")
    return filtered_list

# --- 阶段五：语义分组 (V8新增) ---

# (V8.2新增的核心函数，替换掉之前的merge_tables_by_semantic_name)
def group_tables_by_semantic_name(filtered_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    (V8.2核心) 后处理模块：根据表名的核心中文字符串，将属于同一系列的表格
    归类到一个列表中，而独立表格保持原样。
    """
    print("\n✅ (阶段5) 开始对筛选后的表格进行最终的语义归类...")

    if not filtered_results:
        return []

    # 1. 首先，按语义签名（核心中文字符串）对表格进行分组
    groups_dict = {}
    for result in filtered_results:
        table_name = result.get('table_name')
        if table_name and table_name != "N/A (未关联)":
            group_key = get_chinese_chars(table_name)
            if not group_key:
                group_key = f"no_chinese_title_{table_name}"

            if group_key not in groups_dict:
                groups_dict[group_key] = []
            groups_dict[group_key].append(result)
        else:
            if "unnamed" not in groups_dict:
                groups_dict["unnamed"] = []
            groups_dict["unnamed"].append(result)

    # 2. 遍历分组，构建最终的、分层的列表
    final_list = []
    for group_key, tables_group in groups_dict.items():
        # 如果一个组只有一个表格，或者它是无名组，则直接将表格本身加入最终列表
        if len(tables_group) == 1 or "unnamed" in group_key or "no_chinese_title" in group_key:
            final_list.extend(tables_group)
        else:
            # 如果一个组有多个表格，则创建一个代表“系列”的新字典
            print(f"  -- 发现表格系列: '{group_key}'，包含 {len(tables_group)} 个相关表格，正在整合...")
            series_dict = {
                "is_series": True,
                "series_name": group_key,
                "tables_count": len(tables_group),
                "tables_list": tables_group  # 将所有相关表格的完整字典放入一个列表
            }
            final_list.append(series_dict)

    print(f"✅ 语义归类完成。最终结果包含 {len(final_list)} 个条目（独立表格或表格系列）。")
    return final_list

# --- (V9.2新增) 阶段六：模块化Markdown报告生成 ---
def _generate_markdown_for_single_table(data: Dict[str, Any], heading_level: int = 2) -> str:
    content = []
    heading = '#' * heading_level
    content.append(f"{heading} {data.get('table_name', '无标题表格')}\n\n")
    if data.get('is_merged'):
        content.append(f"- **合并信息:** 这是一个由 {len(data['source_pages'])} 个片段合并的表格，来源页: {data['source_pages']}\n")
    content.append(f"- **页码 (起始页):** {data.get('page')}\n")
    content.append(f"- **结构化上下文:** `{data.get('structured_context', '无')}`\n")
    content.append(f"- **其他上下文:** `{data.get('other_context', '无')}`\n\n")
    df = data.get('table_dataframe')
    if df is not None and not df.empty:
        content.append(f"### 表格数据\n\n")
        content.append(df.to_markdown(index=False))
        content.append("\n\n")
    return "".join(content)

def generate_markdown_report_list(final_results: List[Dict[str, Any]]) -> List[str]:
    print(f"\n✅ (阶段6) 开始生成模块化的Markdown报告列表...")
    if not final_results: return ["# PDF报告提取结果\n\n未找到任何符合条件的表格。"]
    markdown_report_list = []
    for i, item in enumerate(final_results):
        item_markdown_parts = []
        if item.get("is_series"):
            series_name = item['series_name']
            item_markdown_parts.append(f"# 表格系列: {series_name}\n\n")
            item_markdown_parts.append(f"**共包含 {item['tables_count']} 个相关表格。**\n\n")
            for j, data in enumerate(item['tables_list']):
                item_markdown_parts.append(f"---\n\n### 系列内表格 {j+1}\n\n")
                item_markdown_parts.append(_generate_markdown_for_single_table(data, heading_level=4))
        else:
            data = item
            item_markdown_parts.append(_generate_markdown_for_single_table(data, heading_level=2))
        markdown_report_list.append("".join(item_markdown_parts))
    print(f"✅ 模块化报告列表生成完毕。共生成 {len(markdown_report_list)} 个独立的报告块。")
    return markdown_report_list

def process_pdf_to_markdown_list(pdf_path: str) -> List[str]:
    """
    (V10) 一站式PDF表格报告生成器。

    执行从提取、合并、修正、筛选、归类到最终生成模块化Markdown报告的完整流程。

    Args:
        pdf_path: PDF文件的路径。

    Returns:
        一个Markdown字符串的列表，每个字符串对应一个独立的报告块（独立表格或表格系列）。
    """
    # 阶段1 & 2: 提取并合并所有表格片段
    merged_results = extract_and_merge_fragments(pdf_path)

    # 阶段3: 对无主表格进行内省式标题修正
    enhanced_results = enhance_results_with_internal_titles(merged_results)

    # 阶段4: 根据关键词筛选最终结果
    final_filtered_results = filter_results_by_keywords(enhanced_results, FINAL_FILTER_KEYWORDS)

    # 阶段5: 对筛选结果进行最终的语义归类
    final_semantic_groups = group_tables_by_semantic_name(final_filtered_results)

    # 阶段6: 生成模块化的Markdown列表
    final_markdown_list = generate_markdown_report_list(final_semantic_groups)

    print("\n\n" + "="*80)
    print("                    所有流程执行完毕！")
    print("="*80)

    return final_markdown_list


# ==============================================================================
#                      新增的打印辅助函数
# ==============================================================================
def print_stage_results(results: List[Dict[str, Any]], stage_name: str):
    """
    一个通用的函数，用于打印任何处理阶段的结果摘要。
    """
    print("\n\n" + "="*80)
    print(f"                      阶段性快照: {stage_name}")
    print("="*80)

    if not results:
        print("本阶段无任何数据输出。")
        return

    print(f"本阶段共输出 {len(results)} 个条目。")

    for i, item in enumerate(results):
        print(f"\n--- 条目 {i+1} ---")

        # 判断是独立表格还是表格系列
        if item.get("is_series"):
            print(f"  - 类型: 表格系列")
            print(f"  - 系列名称: '{item['series_name']}'")
            print(f"  - 包含表格数: {item['tables_count']}")
            print(f"  - 系列内第一个表格的起始页: {item['tables_list'][0]['page']}")
        elif item.get("is_merged"):
            print(f"  - 类型: 合并后的独立表格")
            print(f"  - 表名: {item['table_name']}")
            print(f"  - 来源页: {item['source_pages']}")
        else: # 普通的、未合并的独立表格
            print(f"  - 类型: 独立表格片段")
            print(f"  - 表名: {item['table_name']}")
            print(f"  - 来源页: {item['page']}")

        # 打印DataFrame的形状以了解其大小
        if "table_dataframe" in item:
            df = item["table_dataframe"]
            print(f"  - 表格数据形状 (行, 列): {df.shape}")
        elif "tables_list" in item:
             df = item["tables_list"][0]["table_dataframe"]
             print(f"  - (系列中第一个表格的数据形状 (行, 列): {df.shape})")

    print("="*80 + "\n")

# ==============================================================================
#                      (最终版) 带深度数据打印的阶段性快照函数
# ==============================================================================

def print_stage_results2(results: List[Dict[str, Any]], stage_name: str, show_data: bool = True):
    """
    一个通用的函数，用于打印任何处理阶段的结果，并能选择性地显示表格数据。
    """
    print("\n\n" + "="*80)
    print(f"                      阶段性快照: {stage_name}")
    print("="*80)

    if not results:
        print("本阶段无任何数据输出。")
        print("="*80 + "\n")
        return

    print(f"本阶段共输出 {len(results)} 个条目。")

    for i, item in enumerate(results):
        print(f"\n--- 条目 {i+1} ---")

        # --- 打印元数据摘要 ---
        if item.get("is_series"):
            print(f"  - 类型: 表格系列")
            print(f"  - 系列名称: '{item['series_name']}'")
            print(f"  - 包含表格数: {item['tables_count']}")
            print(f"  - (系列内第一个表格的上下文: {item['tables_list'][0].get('structured_context')})")
        else: # 这是一个独立表格 (无论是合并的还是片段)
            if item.get("is_merged"):
                print(f"  - 类型: 合并后的独立表格")
                print(f"  - 来源页: {item['source_pages']}")
            else:
                print(f"  - 类型: 独立表格片段")
                print(f"  - 来源页: {item['page']}")
            print(f"  - 表名: {item['table_name']}")
            print(f"  - 结构化上下文: {item.get('structured_context')}")

        # --- (核心修改) 打印表格数据预览 ---
        if show_data:
            if item.get("is_series"):
                # 如果是表格系列，遍历打印系列内的每个表格
                for j, data in enumerate(item['tables_list']):
                    df = data.get('table_dataframe')
                    print(f"\n  --- 系列内表格 {j+1} (来自第 {data['page']} 页) 的数据预览 ---")
                    if df is not None and not df.empty:
                        print(df.head(3).to_string()) # 只打印前3行以保持简洁
                    else:
                        print("    (无数据)")
            else:
                # 如果是独立表格，直接打印
                df = item.get("table_dataframe")
                print(f"\n  --- 表格数据预览 ---")
                if df is not None and not df.empty:
                    print("    (前3行):")
                    print(df.head(3).to_string())
                    if len(df) > 5: # 如果表格较长，也打印后2行
                        print("    (后2行):")
                        print(df.tail(2).to_string())
                else:
                    print("    (无数据)")

    print("="*80 + "\n")
# --- 主程序入口 ---
# --- 主程序入口 ---
def process_pdf_to_markdown_list(pdf_path: str) -> List[str]:
    """
    (V10.1) 一站式PDF表格报告生成器。

    执行从提取、合并、修正、筛选、归类到最终生成模块化Markdown报告的完整流程。

    Args:
        pdf_path: PDF文件的路径。

    Returns:
        一个Markdown字符串的列表，每个字符串对应一个独立的报告块（独立表格或表格系列）。
    """
    # 阶段1 & 2: 提取并合并
    merged_results = extract_and_merge_fragments(pdf_path)

    # 阶段3: 内省修正
    enhanced_results = enhance_results_with_internal_titles(merged_results)

    # 阶段4: 正则表达式筛选
    final_filtered_results = filter_results_by_keywords(enhanced_results, FINAL_FILTER_REGEX_PATTERNS)

    # 阶段5: 语义归类
    final_semantic_groups = group_tables_by_semantic_name(final_filtered_results)

    # 阶段6: 生成报告
    final_markdown_list = generate_markdown_report_list(final_semantic_groups)

    print("\n\n" + "="*80 + "\n                    所有流程执行完毕！\n" + "="*80)

    return final_markdown_list







# 将默认的系统提示词定义为模块级别的常量
# 使用前导下划线表示这是模块内部使用的变量
_DEFAULT_SYSTEM_PROMPT = """
你需要根据提供的数据校验规则，检查给定的表格数据，逐行检查每张表中的每一行数据，确保不遗漏任何一行，按照规则指出所有不符合规则的问题，并按指定格式输出结果。

**数据校验规则如下：**

1.  **表分组规则：**
    将相同名称的表格归类到同一项目下。

2.  **单表项目校验规则 - 规则2（本次变化计算）：**
    当某次监测存在'上次累计变化'值，且上次监测数据无问题时，'本次变化(mm)'应等于（本次累计变化 - 上次累计变化）。若上次监测数据存在问题，则不进行本规则校验。

3.  **单表项目校验规则 - 规则3（累计变化验证）：**
    当上次累计变化值存在且无问题时，本次'累计变化(mm)'应等于（上次累计变化值 + 本次变化值）。若上次累计变化值存在问题，则不进行本规则校验。

4.  **单表项目校验规则 - 规则4（变化速率计算）：**
    当存在'上次累计变化'值且无问题时，变化速率 = (本次累计变化 - 上次累计变化) ÷ 监测间隔天数。若上次累计变化值存在问题，则不进行本规则校验。

5.  **最大值校验规则 - 规则5-7：**
    核对每张表的'最大值'部分中的：每次监测的最大变化速率值是否匹配'变化速率(mm)'列实际最大值；每次监测的最大累计变化值是否匹配'累计变化(mm)'列实际最大值。

6.  **多表项目校验规则 - 规则8（跨表本次变化）：**
    （按监测时间升序逐表检查）当前表行的'本次变化' =（当前表累计变化 - 前表同位置累计变化）。（前表不存在、无数据或前表同位置数据存在问题时跳过）。

7.  **多表项目校验规则 - 规则9（跨表累计变化）：**
    （按监测时间升序逐表检查）当前表累计变化 =（前表同位置累计变化 + 当前表本次变化）。（前表不存在、数据缺失或前表同位置数据存在问题时跳过）。

8.  **多表项目校验规则 - 规则10（跨表变化速率）：**
    （按监测时间升序逐表检查）先对齐小数位数：将变化速率的小数位数调整为与当前表累计变化相同（四舍五入）；计算公式：（当前表累计变化 - 前表同位置累计变化）÷ 间隔天数。（前表不存在、数据缺失或前表同位置数据存在问题时跳过）。

**输出格式要求：**

1.  每张表的检查结果必须按照固定格式输出：`## 表名/项目名 - [规则X] 问题描述（具体数值/位置）...`
2.  多个表格的问题按表格在原始数据中的出现顺序依次列出。
3.  若表格完全符合所有规则，则输出：`## 表名/项目名 - 所有规则校验通过。`
4.  每个问题必须标明违反的具体规则编号。

**补充说明：**

*   当一张表内同一行有多次监测结果时，属于单表项目，不适用规则8、规则9、10进行检查。
*   同一表内不同行的数据相互独立，需分别按照上述规则进行校验，且必须逐行检查，不遗漏任何一行。
"""

def analyze_tables_with_doubao(tables_data_list: list, ark_api_key: str, system_prompt: Optional[str] = None):
    """
    使用方舟(Ark)平台，根据复杂的规则校验一个或多个表格数据，
    并返回一个包含所有过程和结果的字符串。

    Args:
        tables_data_list (list): 一个字符串列表，每个字符串包含一个或多个需要校验的Markdown表格。
        ark_api_key (str): 您的方舟平台API Key。
        system_prompt (Optional[str], optional): 用于指导模型进行校验的系统指令。
                                                如果为 None 或不提供，将使用内置的默认提示词。
                                                默认为 None。

    Returns:
        str: 一个包含所有校验过程和结果的单一字符串。
    """
    # 1. 创建一个空列表，用于收集所有输出片段
    results_accumulator = []

    # --- 确定要使用的系统提示词 ---
    # 如果调用者没有提供 system_prompt，则使用预设的默认值
    final_system_prompt = system_prompt if system_prompt is not None else _DEFAULT_SYSTEM_PROMPT

    # --- 校验API Key ---
    if not ark_api_key or ark_api_key == "YOUR_ARK_API_KEY":
        return "错误：API密钥为空或未设置。请提供有效的方舟平台API密钥。"

    # --- 初始化客户端 ---
    try:
        client = OpenAI(
            api_key=ark_api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3"
        )
    except Exception as e:
        return f"初始化客户端时发生错误: {e}"

    # --- 循环处理每一个待校验的数据块 ---
    for index, table_data in enumerate(tables_data_list):
        results_accumulator.append(f"==================== 正在校验数据块 {index + 1} ====================")

        user_prompt = f"需要检查的数据：\n{table_data}"
        messages = [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # --- 发送API请求 ---
        try:
            response = client.chat.completions.create(
                # 以下参数完全来自于您提供的新JSON配置
                model="ep-20250208142840-rffqw",
                messages=messages,
                temperature=0.1,        # 极低的温度确保输出的确定性和准确性
                max_tokens=12048,       # 较大的token限制以容纳详细的报告
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                response_format={"type": "text"},
                # stream=False, stop=None 等其他参数均为默认值或在配置中指定
            )
            results_accumulator.append("模型校验结果:")
            results_accumulator.append(response.choices[0].message.content)

        except Exception as e:
            results_accumulator.append(f"调用API时发生错误: {e}")

        results_accumulator.append(f"==================== 数据块 {index + 1} 校验完毕 ====================")

    final_result_string = "\n\n".join(results_accumulator)
    return final_result_string
