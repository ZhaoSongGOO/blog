# -*- coding: utf-8 -*-
import re
import argparse
import os

# 当前日期: 9/22/2025

def format_spacing(text: str) -> str:
    """
    在中文和英文/数字之间添加空格。
    - 汉字与英文/数字之间
    - 英文/数字与汉字之间
    
    这个函数是幂等的，即多次运行不会产生多余的空格。

    Args:
        text (str): 需要处理的原始字符串。

    Returns:
        str: 格式化后的字符串。
    """
    # 1. 在汉字和英文/数字之间添加空格
    # \u4e00-\u9fa5 是常用汉字的 Unicode 编码范围
    # [a-zA-Z0-9] 匹配所有大小写字母和数字
    # 使用 () 创建捕获组，之后可以用 \1, \2 来引用
    # r'\1 \2' 表示在第一个捕获组和第二个捕获组之间插入一个空格
    text = re.sub(r'([\u4e00-\u9fa5])([a-zA-Z0-9])', r'\1 \2', text)
    
    # 2. 在英文/数字和汉字之间添加空格
    text = re.sub(r'([a-zA-Z0-9])([\u4e00-\u9fa5])', r'\1 \2', text)
    
    return text

def process_file(input_path: str, output_path: str):
    """
    读取输入文件，格式化内容，并写入输出文件。
    """
    print(f"正在读取文件: {input_path}")
    try:
        with open(input_path, 'r', encoding='utf-8') as f_in:
            content = f_in.read()
            
        print("文件读取成功，开始格式化文本...")
        formatted_content = format_spacing(content)
        print("格式化完成！")
        
        # 如果输出路径和输入路径相同，创建一个备份
        if os.path.abspath(input_path) == os.path.abspath(output_path):
            backup_path = input_path + '.bak'
            print(f"警告：输入和输出路径相同。将创建备份文件: {backup_path}")
            os.rename(input_path, backup_path)

        with open(output_path, 'w', encoding='utf-8') as f_out:
            f_out.write(formatted_content)
            
        print(f"处理完成！格式化后的文件已保存到: {output_path}")

    except FileNotFoundError:
        print(f"错误：找不到文件 {input_path}。请检查文件路径是否正确。")
    except Exception as e:
        print(f"处理过程中发生错误: {e}")

# 当这个脚本被直接运行时，执行以下代码
if __name__ == "__main__":
    # 创建一个命令行参数解析器
    parser = argparse.ArgumentParser(
        description="一个用于格式化中文文档的脚本，在汉字与英文/数字之间添加空格。",
        epilog="示例: python format_document.py my_doc.txt formatted_doc.txt"
    )
    
    # 添加输入文件参数
    parser.add_argument("input_file", help="需要格式化的原始文件路径。")
    
    # 添加输出文件参数（可选）
    parser.add_argument("output_file", nargs='?', default=None, help="格式化后文件的保存路径。(可选，如果未提供，将覆盖原始文件并创建备份)")
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 如果没有提供输出文件路径，则默认与输入文件路径相同
    output_file_path = args.output_file if args.output_file is not None else args.input_file
    
    process_file(args.input_file, output_file_path)

