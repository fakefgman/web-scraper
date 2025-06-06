import re
from bs4 import BeautifulSoup
import os
from datetime import datetime
import traceback

OPTION_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

def clean_text(text):
    """清理文本，移除多余的空白字符"""
    # 替换多个空白字符为单个空格
    text = re.sub(r'\s+', ' ', text)
    # 移除首尾空白
    text = text.strip()
    return text

def extract_qa_from_html(html_file):
    """从HTML文件中提取题目和答案"""
    try:
        print(f"正在处理文件: {html_file}")
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        # 判断是否为HTML结构
        is_html = '<li>' in content or '<ul' in content or '<ol' in content
        qa_list = []
        if is_html:
            # 处理HTML结构
            soup = BeautifulSoup(content, 'html.parser')
            def parse_question_li(li):
                text = li.get_text(separator=' ', strip=True)
                q_match = re.match(r'^(\d{7})\s+(.+?)【(.+?)】', text)
                if not q_match:
                    return None
                qa = {
                    'question_id': q_match.group(1),
                    'question': clean_text(q_match.group(2)),
                    'question_type': clean_text(q_match.group(3)),
                    'options': [],
                    'answer_letters': [],
                    'explanations': []
                }
                # 选项li在当前li的ul/li下
                ul = li.find('ul', recursive=False)
                if not ul:
                    return qa
                option_lis = ul.find_all('li', recursive=False)
                for idx, oli in enumerate(option_lis):
                    otext = oli.get_text(separator=' ', strip=True)
                    o_match = re.match(r'^(\d{7})\s+(.+)', otext)
                    if not o_match:
                        continue
                    option_id = o_match.group(1)
                    option_text = clean_text(o_match.group(2))
                    # 解析li在当前选项li的ul/li下
                    explanation = ''
                    is_correct = False
                    subul = oli.find('ul', recursive=False)
                    if subul:
                        for subli in subul.find_all('li', recursive=False):
                            subtext = subli.get_text(separator=' ', strip=True)
                            flag_match = re.match(r'([✔❌])\s*选中。(.+)', subtext)
                            if flag_match:
                                is_correct = flag_match.group(1) == '✔'
                                explanation = clean_text(flag_match.group(2))
                    letter = OPTION_LETTERS[idx]
                    qa['options'].append({
                        'letter': letter,
                        'option_id': option_id,
                        'option': option_text,
                        'is_correct': is_correct,
                        'explanation': explanation
                    })
                    if is_correct:
                        qa['answer_letters'].append(letter)
                    if explanation:
                        qa['explanations'].append(f"选项{letter}: {explanation}")
                return qa
            # 递归查找所有题目li
            def find_all_question_lis(soup):
                result = []
                for li in soup.find_all('li'):
                    # 只处理题目li
                    text = li.get_text(separator=' ', strip=True)
                    if re.match(r'^(\d{7})\s+.+【.+】', text):
                        qa = parse_question_li(li)
                        if qa:
                            result.append(qa)
                return result
            qa_list = find_all_question_lis(soup)
        else:
            # 处理Markdown结构
            lines = content.splitlines()
            current_qa = None
            for line in lines:
                line_raw = line
                line = line.rstrip()
                # 题目行
                q_match = re.match(r'^[-*] (\d{7}) [*\s]*([^【\n]+)【([^】]+)】', line)
                if q_match:
                    if current_qa:
                        qa_list.append(current_qa)
                    current_qa = {
                        'question_id': q_match.group(1),
                        'question': clean_text(q_match.group(2)),
                        'question_type': clean_text(q_match.group(3)),
                        'options': [],
                        'answer_letters': [],
                        'explanations': []
                    }
                    continue
                # 选项行
                o_match = re.match(r'^[ \t-]+(\d{7})[ \t]+(.+)', line)
                if o_match and current_qa:
                    idx = len(current_qa['options'])
                    letter = OPTION_LETTERS[idx]
                    option_id = o_match.group(1)
                    option_text = clean_text(o_match.group(2))
                    # 解析行在下一个缩进更深的行
                    explanation = ''
                    is_correct = False
                    # 查找下一个行（解析）
                    next_idx = lines.index(line_raw) + 1
                    if next_idx < len(lines):
                        next_line = lines[next_idx].strip()
                        flag_match = re.match(r'[-*] ([✔❌]) 选中。(.+)', next_line)
                        if flag_match:
                            is_correct = flag_match.group(1) == '✔'
                            explanation = clean_text(flag_match.group(2))
                    current_qa['options'].append({
                        'letter': letter,
                        'option_id': option_id,
                        'option': option_text,
                        'is_correct': is_correct,
                        'explanation': explanation
                    })
                    if is_correct:
                        current_qa['answer_letters'].append(letter)
                    if explanation:
                        current_qa['explanations'].append(f"选项{letter}: {explanation}")
                    continue
            if current_qa:
                qa_list.append(current_qa)
        print(f"从 {html_file} 中提取了 {len(qa_list)} 道题目")
        return qa_list
    except Exception as e:
        print(f"处理文件 {html_file} 时出错:")
        print(traceback.format_exc())
        return []

def format_qa(qa_list):
    """格式化题目和答案为易读格式，选项带ID"""
    formatted_qa = []
    for q in qa_list:
        formatted = []
        formatted.append(f"【题目ID】{q['question_id']}")
        formatted.append(f"【题型】{q['question_type']}")
        formatted.append(f"【题目】\n{q['question']}")
        formatted.append(f"【选项】")
        for opt in q['options']:
            formatted.append(f"{opt['letter']}. [ID: {opt['option_id']}] {opt['option']}")
        formatted.append(f"\n【答案】{'/'.join(q['answer_letters']) if q['answer_letters'] else '无'}")
        if q['explanations']:
            formatted.append(f"【解析】\n" + '\n'.join(q['explanations']))
        formatted.append("=" * 50)
        formatted_qa.append('\n'.join(formatted))
    return formatted_qa

def process_html_files():
    """处理所有HTML文件并生成规范化的题库"""
    html_files = ['web.html', 'web1.html', 'web2.html']
    all_qa = []
    
    for html_file in html_files:
        if os.path.exists(html_file):
            qa_list = extract_qa_from_html(html_file)
            all_qa.extend(qa_list)
        else:
            print(f"文件不存在: {html_file}")
    
    if not all_qa:
        print("警告: 没有提取到任何题目")
        return
    
    # 按题目ID排序
    all_qa.sort(key=lambda x: int(x['question_id']))
    
    # 格式化并写入文件
    formatted_qa = format_qa(all_qa)
    
    # 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"qa_database_{timestamp}.txt"
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n\n".join(formatted_qa))
        print(f"题库已保存到: {output_file}")
    except Exception as e:
        print(f"保存文件时出错:")
        print(traceback.format_exc())

if __name__ == "__main__":
    try:
        process_html_files()
    except Exception as e:
        print("程序执行出错:")
        print(traceback.format_exc())
