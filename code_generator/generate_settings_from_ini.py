#!/usr/bin/env python3
import re
import sys
from pathlib import Path
from datetime import datetime
import configparser

def parse_settings_ini(ini_path):
    """按行解析settings.ini文件，严格遵循指定的格式流程和注释格式规则"""
    try:
        with open(ini_path, "r") as f:
            # 读取所有行并记录行号（从1开始）
            lines = [(i + 1, line.rstrip("\n")) for i, line in enumerate(f.readlines())]
    except Exception as e:
        print(f"读取 INI 文件时发生错误: {e}", file=sys.stderr)
        sys.exit(1)

    settings = []  # 用Python列表存储解析结果，每个元素是一个配置项字典
    current_section = None
    i = 0
    line_count = len(lines)

    # 第一行必须是section
    if line_count == 0:
        print("错误: INI 文件为空", file=sys.stderr)
        sys.exit(1)

    line_num, line = lines[0]
    stripped_line = line.strip()
    if not (stripped_line.startswith("[") and stripped_line.endswith("]")):
        print(
            f'第 1 行格式错误: 必须为某个section, 格式为 "[section_name]"',
            file=sys.stderr,
        )
        sys.exit(1)

    # 开始逐行解析
    while i < line_count:
        line_num, line = lines[i]
        stripped_line = line.strip()

        # 1. 处理section行（必须是[xxx]格式）
        if stripped_line.startswith("[") and stripped_line.endswith("]"):
            section_name = stripped_line[1:-1].strip()
            if not section_name:
                print(
                    f"第 {line_num} 行格式错误: section 名字不能为空",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 验证section名称符合C语言标识符规则
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", section_name):
                print(
                    f"第 {line_num} 行格式错误: section 命名 '{section_name}' 非法. 无法生成对应结构体名称",
                    file=sys.stderr,
                )
                sys.exit(1)

            current_section = section_name
            i += 1

            # 检查是否有下一行
            if i >= line_count:
                print(
                    f"第 {line_num} 行格式错误: section '{section_name}' 为空, 无法继续解析",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 验证section的下一行必须是comment
            next_line_num, next_line = lines[i]
            next_stripped = next_line.strip()
            if not next_stripped.startswith(";"):
                print(
                    f"第 {line_num + 1} 行格式错误: section 中的首行必须为 comment",
                    file=sys.stderr,
                )
                sys.exit(1)

            continue

        # 2. 处理comment行（必须紧跟在section或另一个KV之后）
        if stripped_line.startswith(";"):
            if current_section is None:
                print(
                    f"第 {line_num} 行格式错误: comment 必须要在 section 内部",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 提取注释内容
            comment_content = stripped_line[1:].strip()
            if not comment_content:
                print(
                    f"第 {line_num} 行格式错误: comment 不可为空",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 提取key名称（注释中第一个标识符）
            if ":" in comment_content:
                key_part, meta_part = comment_content.split(":", 1)
                key_name = key_part.strip()
                meta_part = meta_part.strip()
            else:
                print(
                    f"第 {line_num} 行格式错误: comment 无法解析. (标准格式: '; key: type=..., default=..., min=..., max=...' 或 '; key: type=..., default=...')",
                    file=sys.stderr,
                )
                sys.exit(1)

            if not key_name:
                print(
                    f"第 {line_num} 行格式错误: comment 无法解析(找不到key). (标准格式: '; key: type=..., default=..., min=..., max=...' 或 '; key: type=..., default=...')",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 验证key名称符合C语言变量命名规则
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key_name):
                print(
                    f"第 {line_num} 行格式错误: key 命名 '{key_name}' 非法. 无法生成对应的结构体变量名称.",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 解析元数据部分，提取所有键值对
            meta_items = []
            # 分割元数据（处理逗号分隔的情况）
            for item in re.split(r",(?=\s*[a-zA-Z]+[:=])", meta_part):
                item = item.strip()
                if not item:
                    continue
                if "=" in item:
                    k, v = item.split("=", 1)
                else:
                    print(
                        f" {line_num} 行格式错误. (标准格式: '; key: type=..., default=..., min=..., max=...' 或 '; key: type=..., default=...')"
                    )
                    sys.exit(1)
                meta_items.append((k.strip().lower(), v.strip()))

            # 构建元数据字典
            meta = dict(meta_items)

            # 检查必须包含的元数据
            required_meta = ["type", "default"]
            for req in required_meta:
                if req not in meta:
                    print(
                        f"第 {line_num} 行格式错误: comment中必须指明'{req}' (标准格式: '{req}=value')",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            # 提取元数据
            data_type = meta["type"].lower()
            default_val_str = meta["default"]

            # 验证类型是否支持
            supported_types = [
                "int",
                "bool",
                "float",
                "string",
            ]
            if data_type not in supported_types and not data_type.startswith("string:"):
                print(
                    f"第 {line_num} 行格式错误: key:'{key_name} 具有不支持的类型 '{data_type}''. 暂时只支持: {', '.join(supported_types)}, string:len",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 检查bool和string的comment中是否存在不允许的元数据（min/max）
            disallowed_meta = []
            if data_type in ["bool", "string"] or data_type.startswith("string:"):
                disallowed_meta = ["min", "max"]

            # 检查是否有不允许的元数据
            for meta_key in disallowed_meta:
                if meta_key in meta:
                    # 即使值为空也不允许存在
                    print(
                        f"第 {line_num} 行格式错误: {data_type} 类型的comment中不允许出现 '{meta_key}'",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            # 提取允许的min和max（如存在）
            min_val_str = meta.get("min") if data_type not in disallowed_meta else None
            max_val_str = meta.get("max") if data_type not in disallowed_meta else None

            # 检查下一行是否为KV行
            if i + 1 >= line_count:
                print(
                    f"第 {line_num} 行格式错误: comment 的下一行必须是 key-value对",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 3. 处理KV行
            kv_line_num, kv_line = lines[i + 1]
            kv_stripped = kv_line.strip()

            # 验证KV行格式严格为xxx=xxx
            if "=" not in kv_stripped:
                print(
                    f"第 {kv_line_num} 行格式错误: comment 的下一行必须是 key-value对",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 确保只有一个'='
            if kv_stripped.count("=") > 1:
                print(
                    f"第 {kv_line_num} 行格式错误: key-value对 中只能有1个 '='",
                    file=sys.stderr,
                )
                sys.exit(1)

            kv_parts = kv_stripped.split("=", 1)
            kv_key = kv_parts[0].strip()
            kv_value = kv_parts[1].strip()

            # 验证KV的key与注释中的key一致
            if kv_key != key_name:
                print(
                    f"第 {kv_line_num} 行格式错误: key-value对中的key 与 comment中的key名称不匹配",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 验证value不为空
            if not kv_value:
                print(
                    f"第 {kv_line_num} 行格式错误: key-value对中的 value 不能为空",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 根据类型验证所有值
            try:
                # 整数类型验证
                if data_type == "int":
                    # 验证value是整数
                    try:
                        value = int(kv_value)
                    except ValueError:
                        print(
                            f"第 {kv_line_num} 行格式错误: key-value对中的 value 值非法.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证default是整数
                    try:
                        default_val = int(default_val_str)
                    except ValueError:
                        print(
                            f"第 {kv_line_num} 行格式错误: comment 中的default值非法.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    if min_val_str is None or min_val_str == "":
                        print(
                            f"第 {kv_line_num} 行格式错误: int类型的 comment 中必须指明min. (标准格式: '; key: type=int, default=..., min=..., max=...')",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    if max_val_str is None or max_val_str == "":
                        print(
                            f"第 {kv_line_num} 行格式错误: int类型的 comment 中必须指明max. (标准格式: '; key: type=int, default=..., min=..., max=...')",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证min是整数
                    try:
                        min_val = int(min_val_str)
                    except ValueError:
                        print(
                            f"第 {kv_line_num} 行格式错误: comment 中的min值非法.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证max是整数（如存在）
                    try:
                        max_val = int(max_val_str)
                    except ValueError:
                        print(
                            f"第 {kv_line_num} 行格式错误: comment 中的max值非法.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证value等于default
                    if value != default_val:
                        print(
                            f"第 {kv_line_num} 行格式错误: key-value对中的 value:{value} 必须等于 comment 中的 default:{default_val}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证范围
                    if default_val < min_val:
                        print(
                            f"第 {line_num} 行格式错误: comment 中的 default:{default_val} 必须 >= min:{min_val}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    if default_val > max_val:
                        print(
                            f"第 {line_num} 行格式错误: comment 中的 default:{default_val} 必须 <= max:{max_val}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                # 布尔类型验证
                elif data_type == "bool":
                    valid_bools = ["true", "false"]

                    value = kv_value
                    default_val = default_val_str

                    # 验证value是有效的布尔值
                    if kv_value not in valid_bools:
                        print(
                            f"第 {kv_line_num} 行格式错误: key-value对中的 value:{kv_value} 非法. 暂时只支持: {', '.join(valid_bools)}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证default是有效的布尔值
                    if default_val_str not in valid_bools:
                        print(
                            f"第 {line_num} 行格式错误: comment中的 default:{default_val_str} 非法. 暂时只支持: {', '.join(valid_bools)}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证value等于default
                    if kv_value != default_val_str:
                        print(
                            f"第 {kv_line_num} 行格式错误: key-value对中的 value:{kv_value} 必须等于 comment 中的 default:{default_val_str}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    min_val = None
                    max_val = None

                # 浮点类型验证
                elif data_type in ["float"]:
                    # 验证value是浮点数
                    try:
                        value = float(kv_value)
                    except ValueError:
                        print(
                            f"第 {kv_line_num} 行格式错误: key-value对中的 value 值非法.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证default是浮点数
                    try:
                        default_val = float(default_val_str)
                    except ValueError:
                        print(
                            f"第 {kv_line_num} 行格式错误: comment 中的default值非法.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    if min_val_str is None or min_val_str == "":
                        print(
                            f"第 {kv_line_num} 行格式错误: float类型的 comment 中必须指明min. (标准格式: '; key: type=float, default=..., min=..., max=...')",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    if max_val_str is None or max_val_str == "":
                        print(
                            f"第 {kv_line_num} 行格式错误: float类型的 comment 中必须指明max. (标准格式: '; key: type=float, default=..., min=..., max=...')",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证min是浮点数
                    try:
                        min_val = float(min_val_str)
                    except ValueError:
                        print(
                            f"第 {kv_line_num} 行格式错误: comment 中的min值非法.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证max是浮点数
                    try:
                        max_val = float(max_val_str)
                    except ValueError:
                        print(
                            f"第 {kv_line_num} 行格式错误: comment 中的max值非法.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证value等于default
                    if kv_value != default_val_str:
                        print(
                            f"第 {kv_line_num} 行格式错误: key-value对中的 value:{kv_value} 必须等于 comment 中的 default:{default_val_str}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证范围
                    if default_val < min_val:
                        print(
                            f"第 {line_num} 行格式错误: comment 中的 default:{default_val} 必须 >= min:{min_val}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    if default_val > max_val:
                        print(
                            f"第 {line_num} 行格式错误: comment 中的 default:{default_val} 必须 <= max:{max_val}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                # 字符串类型验证
                elif data_type in ["string"] or data_type.startswith("string:"):
                    # 提取字符串长度限制（如指定）
                    str_len = None
                    if ":" in data_type:
                        str_len_part = data_type.split(":", 1)[1].strip()
                        try:
                            str_len = int(str_len_part)
                        except ValueError:
                            print(
                                f"第 {line_num} 行格式错误: string 类型的comment中所指明的大小非法.",
                                file=sys.stderr,
                            )
                            sys.exit(1)
                    else:
                        print(
                            f"第 {line_num} 行格式错误: string 类型的comment中必须要指明大小. 例如: type=string:20",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证value长度
                    if len(kv_value) > str_len - 1:
                        print(
                            f"第 {kv_line_num} 行格式错误: key-value对中的 value 过长({len(kv_value)}). comment 中的限制: {str_len} - 1",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证default长度
                    if len(default_val_str) > str_len - 1:
                        print(
                            f"第 {line_num} 行格式错误: comment中的 default value 过长({len(default_val_str)}). comment 中的限制: {str_len} - 1",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 验证value等于default
                    if kv_value != default_val_str:
                        print(
                            f"第 {kv_line_num} 行格式错误: key-value对中的 value:{value} 必须等于 comment 中的 default:{default_val}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    min_val = None
                    max_val = None
                    value = kv_value
                    default_val = default_val_str

            except ValueError as e:
                print(
                    f"第 {line_num if 'default' in str(e).lower() else kv_line_num} 行格式错误: {data_type} 出现非法值 - {str(e)} (key '{kv_key}')",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 存储解析结果
            settings.append(
                {
                    "section": current_section,
                    "key": kv_key,
                    "value": value,
                    "default": default_val,
                    "type": data_type,
                    "min": min_val,
                    "max": max_val,
                    "comment": comment_content,
                    "comment_line": line_num,
                    "kv_line": kv_line_num,
                }
            )

            # 移动到下一行（KV行的下一行）
            i += 2

            # 4. 处理可能的空行（表示section结束）
            if i < line_count:
                next_line_num, next_line = lines[i]
                next_stripped = next_line.strip()

                if not next_stripped:  # 空行
                    # 空行后必须是新的section
                    i += 1  # 跳过空行

                    if i >= line_count:
                        print(
                            f"第 {next_line_num} 行格式错误: 空行后面必须是一个新的 section",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # 检查空行后的行是否为section
                    section_line_num, section_line = lines[i]
                    section_stripped = section_line.strip()

                    if not (
                        section_stripped.startswith("[")
                        and section_stripped.endswith("]")
                    ):
                        print(
                            f"第 {section_line_num} 行格式错误: 空行后面必须是一个新的 section",
                            file=sys.stderr,
                        )
                        sys.exit(1)

            continue

        # 如果不是section、comment或空行，就是无效行
        print(
            f"第 {line_num} 行格式错误: Invalid content. Expected section, comment, or empty line (only between sections)",
            file=sys.stderr,
        )
        sys.exit(1)

    # 验证至少有一个配置项
    if not settings:
        print("错误: 未从 INI 文件中解析出任何配置项", file=sys.stderr)
        sys.exit(1)

    have_verify = False
    for item in settings:
        if item["section"] == "Verify" and item["key"] == "crc_16_ibm":
            have_verify = True
    if have_verify == False:
        print("错误: INI 文件中缺少Verify.crc_16_ibm项, 无法进行校验", file=sys.stderr)
        sys.exit(1)
    return settings


def generate_settings_persist_header(settings):
    """生成settings.h文件，包含配置结构体定义，带min/max注释"""
    code = "#ifndef _SETTINGS_PERSIST_H\n"
    code += "#define _SETTINGS_PERSIST_H\n\n"
    code += "#include <stdbool.h>\n"
    code += "#include <stdint.h>\n"
    code += "#include <string.h>\n\n"
    code += "typedef struct\n"
    code += "{\n"

    # 按section分组
    sections = {}
    for item in settings:
        section = item["section"]
        if section not in sections:
            sections[section] = []
        sections[section].append(item)

    # 为每个section生成嵌套结构体
    for section, items in sections.items():
        code += f"    /* {section} settings */\n"
        code += "    struct\n"
        code += "    {\n"

        for item in items:
            # 定义C变量类型
            if item["type"] == "int":
                c_type = f"int {item['key']}"
            elif item["type"] == "bool":
                c_type = f"bool {item['key']}"
            elif item["type"] == "float":
                c_type = f"float {item['key']}"
            elif item["type"].startswith("string"):
                # 处理带长度的字符串
                match = re.search(r"string:(\d+)", item["type"])
                if match:
                    c_type = f"char {item['key']}[{match.group(1)}]"
                else:
                    c_type = f"char {item['key']}[64]"  # 默认长度
            else:
                c_type = f"char {item['key']}[64]"  # 默认为字符串

            # 构建注释内容
            if item["type"].startswith("string"):
                # 字符串类型：带引号的默认值
                comment = f'/* default: "{item["default"]}" */'
            else:
                # 数值类型：包含默认值、min和max
                comment_parts = [f"default: {item['default']}"]
                if "min" in item and item["min"] is not None:
                    comment_parts.append(f"min: {item['min']}")
                if "max" in item and item["max"] is not None:
                    comment_parts.append(f"max: {item['max']}")
                comment = f"/* {', '.join(comment_parts)} */"

            code += f"        {c_type};  {comment}\n"

        code += f"    }} {section};\n\n"

    code += "} Settings;\n\n"

    code += "int settings_persist_init(void);\n\n"
    code += "int settings_persist_get_data(Settings *settings);\n\n"
    code += "int settings_persist_set_data(const Settings *settings);\n\n"
    code += "int settings_persist_reset_all_data(void);\n\n"

    # 生成setter函数声明
    for section, items in sections.items():
        for item in items:
            # 跳过不需要生成setter的项：section为"Verify"且key为"crc_16_ibm"
            if section == "Verify" and item["key"] == "crc_16_ibm":
                continue
            # 确定参数类型
            if item["type"] == "int":
                param_type = "int"
            elif item["type"] == "bool":
                param_type = "bool"
            elif item["type"] == "float":
                param_type = "float"
            elif item["type"].startswith("string"):
                param_type = "const char*"
            else:
                param_type = "const char*"
            # 生成函数声明
            func_name = f"settings_persist_set_{section}_{item['key']}"
            code += f"int {func_name}({param_type} {item['key']});\n\n"

    code += "int settings_persist_deinit(void);\n\n"
    code += "#endif /* _SETTINGS_PERSIST_H */\n"
    return code


def generate_settings_set_functions(settings):
    """生成所有配置项的setter函数代码"""
    code = """
extern int settings_persist_thread_running;
extern pthread_mutex_t settings_persist_thread_status_mutex;
extern Settings settings_cache;
extern pthread_mutex_t cache_mutex;

"""

    # 按section分组
    sections = {}
    for item in settings:
        section = item["section"]
        if section not in sections:
            sections[section] = []
        sections[section].append(item)

    # 为每个配置项生成setter函数
    for section, items in sections.items():
        for item in items:
            # 跳过Verify部分的crc_16_ibm配置项
            if section == "Verify" and item["key"] == "crc_16_ibm":
                continue  # 不生成该配置项的setter函数
            # 确定参数类型
            if item["type"] == "int":
                param_type = "int"
            elif item["type"] == "bool":
                param_type = "bool"
            elif item["type"] == "float":
                param_type = "float"
            elif item["type"].startswith("string"):
                param_type = "const char*"
            else:
                param_type = "const char*"

            param_name = item["key"]
            func_name = f"settings_persist_set_{section}_{param_name}"

            # 函数开头
            func_code = f"int {func_name}({param_type} {param_name})\n"
            func_code += "{\n"
            func_code += f'    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("{func_name}");\n'

            # 生成参数验证代码
            validation_code = ""
            if item["type"] == "int":
                # 整数类型验证min和max
                if (
                    "min" in item
                    and item["min"] is not None
                    and "max" in item
                    and item["max"] is not None
                ):
                    validation_code += f"    if ({param_name} > {item['max']} || {param_name} < {item['min']})\n"
                    validation_code += "    {\n"
                    validation_code += f"        SETTINGS_PERSIST_LOG_WARN(\"参数值超出范围: {item['min']}~{item['max']}\");\n"
                    validation_code += "        return -1;\n"
                    validation_code += "    }\n"

            elif item["type"] == "float":
                # 浮点类型验证min和max
                if (
                    "min" in item
                    and item["min"] is not None
                    and "max" in item
                    and item["max"] is not None
                ):
                    validation_code += f"    if ({param_name} > {item['max']} || {param_name} < {item['min']})\n"
                    validation_code += "    {\n"
                    validation_code += f"        SETTINGS_PERSIST_LOG_WARN(\"参数值超出范围: {item['min']}~{item['max']}\");\n"
                    validation_code += "        return -1;\n"
                    validation_code += "    }\n"

            elif item["type"].startswith("string"):
                # 字符串类型验证长度
                match = re.search(r"string:(\d+)", item["type"])
                if match:
                    max_len = int(match.group(1)) - 1  # 留一个字节给终止符
                    validation_code += f"    if (strlen({param_name}) > {max_len})\n"
                    validation_code += "    {\n"
                    validation_code += f'        SETTINGS_PERSIST_LOG_WARN("字符串过长 最大长度为{max_len}");\n'
                    validation_code += "        return -1;\n"
                    validation_code += "    }\n"

            # 添加验证代码
            if validation_code:
                func_code += validation_code

            # 线程安全检查和数据更新
            func_code += (
                "\n    pthread_mutex_lock(&settings_persist_thread_status_mutex);\n"
            )
            func_code += "    if (settings_persist_thread_running == 0)\n"
            func_code += "    {\n"
            func_code += '        SETTINGS_PERSIST_LOG_WARN("数据更新失败: settings_persist模块未初始化");\n'
            func_code += (
                "        pthread_mutex_unlock(&settings_persist_thread_status_mutex);\n"
            )
            func_code += "        return -2;\n"
            func_code += "    }\n\n"

            # 数据更新逻辑
            func_code += "    pthread_mutex_lock(&cache_mutex);\n"

            # 根据类型生成不同的赋值语句
            if item["type"].startswith("string"):
                # 字符串需要用strcpy
                func_code += f"    strcpy(settings_cache.{section}.{param_name}, {param_name});\n"
            else:
                # 其他类型直接赋值
                func_code += (
                    f"    settings_cache.{section}.{param_name} = {param_name};\n"
                )

            # 函数结尾
            func_code += "    pthread_mutex_unlock(&cache_mutex);\n"
            func_code += '    SETTINGS_PERSIST_LOG_DEBUG("数据更新成功");\n'
            func_code += (
                "    pthread_mutex_unlock(&settings_persist_thread_status_mutex);\n"
            )
            func_code += "    return 0;\n"
            func_code += "}"

            # 添加到总代码中
            code += func_code + "\n"

    return code


def generate_ini_handler_function(settings):
    """生成更安全的ini_handler()函数，包含错误处理和范围检查"""
    code = """/**
 * @brief INI文件的解析函数 需搭配inih库使用
 *
 * @param[in, out] user 解析结果
 * @param[in] section 节
 * @param[in] name 相当于key-value对中的key
 * @param[in] value 相当于key-value对中的value
 * @return int
 */
int settings_ini_handler(void* user, const char* section, const char* name, const char* value) {
    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("settings_ini_handler");
    Settings* settings = (Settings*)user;
    if (!settings || !section || !name || !value)
    {
        SETTINGS_PERSIST_LOG_ERROR("输入参数中含有NULL");
        return 0;
    }\n\n"""
    # 按section分组处理
    for item in settings:
        section = item["section"]
        key = item["key"]
        data_type = item["type"]
        default_val = item["default"]

        member_access = f"settings->{section}.{key}"

        # 生成匹配section和key的条件
        code += f'    if (strcmp(section, "{section}") == 0 && strcmp(name, "{key}") == 0) {{\n'

        # 根据类型生成不同的解析代码 
        if data_type == "int":
            # 整数类型，使用strtol进行安全转换，支持范围检查
            code += f"        char* endptr;\n"
            code += f"        long val;\n"
            code += f"        errno = 0;\n"
            code += f"        val = strtol(value, &endptr, 10);\n"
            code += f"        /* 检查转换错误或未转换任何字符 */\n"
            code += f"        if (errno != 0 || endptr == value) {{\n"
            code += f"            /* 转换失败 使用默认值 */\n"
            code += f"            {member_access} = {default_val};\n"
            code += f'            SETTINGS_PERSIST_LOG_ERROR("settings.{section}.{key}(type:int)转换失败, 已自动恢复默认值: {default_val}");\n'
            code += f"        }} else {{\n"
            # 添加范围检查
            code += f"            /* 检查范围 */\n"
            code += f"            if (val < {item['min']} || val > {item['max']}) {{\n"
            code += f"                /* 超出范围 使用默认值 */\n"
            code += f"                {member_access} = {default_val};\n"
            code += f"                SETTINGS_PERSIST_LOG_ERROR(\"settings.{section}.{key}超出范围[{item['min']}, {item['max']}], 已自动恢复默认值: {default_val}\");\n"
            code += f"            }} else {{\n"
            code += f"                {member_access} = (int)val;\n"
            code += f'                SETTINGS_PERSIST_LOG_INFO("settings.{section}.{key}读取并解析成功: %d", (int)val);\n'
            code += f"            }}\n"

            code += f"        }}\n"

        elif data_type == "float":
            # 浮点类型，使用strtof进行安全转换，支持范围检查
            code += f"        char* endptr;\n"
            code += f"        float val;\n"
            code += f"        errno = 0;\n"
            code += f"        val = strtof(value, &endptr);\n"
            code += f"        /* 检查转换错误或未转换任何字符 */\n"
            code += f"        if (errno != 0 || endptr == value) {{\n"
            code += f"            /* 转换失败 使用默认值 */\n"
            code += f"            {member_access} = {default_val};\n"
            code += f'            SETTINGS_PERSIST_LOG_ERROR("settings.{section}.{key}(type:float)转换失败, 已自动恢复默认值: {default_val}");\n'
            code += f"        }} else {{\n"
            # 添加范围检查
            code += f"            /* 检查范围 */\n"
            code += f"            if (val < {item['min']} || val > {item['max']}) {{\n"
            code += f"                /* 超出范围 使用默认值 */\n"
            code += f"                {member_access} = {default_val};\n"
            code += f"                SETTINGS_PERSIST_LOG_ERROR(\"settings.{section}.{key}超出范围[{item['min']}, {item['max']}], 已自动恢复默认值: {default_val}\");\n"
            code += f"            }} else {{\n"
            code += f"                {member_access} = val;\n"
            code += f'                SETTINGS_PERSIST_LOG_INFO("settings.{section}.{key}读取并解析成功: %f", val);\n'
            code += f"            }}\n"

            code += f"        }}\n"

        elif data_type == "bool":
            # 布尔类型 - 严格解析
            code += f'        if (strcmp(value, "true") == 0) {{\n'
            code += f"            {member_access} = true;\n"
            code += f'            SETTINGS_PERSIST_LOG_INFO("settings.{section}.{key}读取并解析成功: true");\n'
            code += f'        }} else if (strcmp(value, "false") == 0) {{\n'
            code += f"            {member_access} = false;\n"
            code += f'            SETTINGS_PERSIST_LOG_INFO("settings.{section}.{key}读取并解析成功: false");\n'
            code += f"        }} else {{\n"
            code += f"            /* 无效的布尔值 使用默认值 */\n"
            code += f"            {member_access} = {default_val};\n"
            code += f'            SETTINGS_PERSIST_LOG_ERROR("settings.{section}.{key}(type:bool)转换失败, 已自动恢复默认值: {default_val}");\n'
            code += f"        }}\n"

        elif data_type.startswith("string:"):
            # 字符串类型settings_restore_defaults
            code += (
                f"        strncpy({member_access}, value, sizeof({member_access})-1);\n"
            )
            code += f"        {member_access}[sizeof({member_access})-1] = '\\0';\n"
            code += f'        SETTINGS_PERSIST_LOG_INFO("settings.{section}.{key}读取并解析成功: %s", {member_access});\n'

        else:
            code += f"        /* Unsupported type: {data_type} */\n"

        code += "        return 1;\n"
        code += "    }\n\n"

    code += "    /* 未知的 section 或 name - 已忽略 */\n"
    code += '    SETTINGS_PERSIST_LOG_WARN("读取到未知数据记录: %s(section)->%s(name)", section, name);\n'
    code += "    return 0;\n"
    code += "}\n"
    return code


def generate_restore_defaults_function(settings):
    """生成settings_restore_defaults()函数"""
    code = """/**
 * @brief 将Settings恢复至默认值
 *
 * @param[in, out] settings 目标
 */
void settings_restore_defaults(Settings *settings) {\n"""
    code += '    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("settings_restore_defaults");\n'
    code += "    if (!settings)\n"
    code += "    {\n"
    code += '        SETTINGS_PERSIST_LOG_ERROR("输入参数为NULL");\n'
    code += "        return;\n"
    code += "    }\n\n"

    # 按section分组
    sections = {}
    for item in settings:
        section = item["section"]
        if section not in sections:
            sections[section] = []
        sections[section].append(item)

    # 生成每个配置项的默认值设置
    for section, items in sections.items():
        code += f"    /* 恢复 {section} 至默认值 */\n"

        for item in items:
            member_access = f"settings->{section}.{item['key']}"

            # 根据类型处理默认值
            if item["type"].startswith("string:"):
                # string类型
                code += f"    strncpy({member_access}, \"{item['default']}\", sizeof({member_access})-1);\n"
                code += f"    {member_access}[sizeof({member_access})-1] = '\\0';\n"
            elif item["type"] == "bool":
                # bool类型
                default_val = "true" if item["default"] == "true" else "false"
                code += f"    {member_access} = {default_val};\n"
            else:
                # int类型
                code += f"    {member_access} = {item['default']};\n"

        code += "\n"

    code += "}\n"

    code += """
int settings_persist_reset_all_data(void)
{
    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("settings_persist_reset_all_data");
    pthread_mutex_lock(&settings_persist_thread_status_mutex);
    if (settings_persist_thread_running == 0)
    {
        SETTINGS_PERSIST_LOG_WARN("数据重置失败: settings_persist模块未初始化");
        pthread_mutex_unlock(&settings_persist_thread_status_mutex);
        return -2;
    }

    pthread_mutex_lock(&cache_mutex);
    settings_restore_defaults(&settings_cache);
    pthread_mutex_unlock(&cache_mutex);
    SETTINGS_PERSIST_LOG_DEBUG("数据重置成功");
    pthread_mutex_unlock(&settings_persist_thread_status_mutex);
    return 0;
}

"""
    return code


def generate_write_function(settings):
    """生成write_settings_to_file()函数"""
    code = """/**
 * @brief 将设置保存到对应文件中(以ini格式)
 *
 * @param[in] filename 保存到的文件路径
 * @param[in] settings 设置值
 * @return 保存结果
 * @retval 0 保存成功
 * @retval -1 保存失败: 输入参数中含有NULL
 * @retval -2 保存失败: 未知原因
 */
int write_settings_to_file(const char* filename, const Settings* settings) {
    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("write_settings_to_file");
    if (!filename || !settings)
    {
        errno = EINVAL;
        SETTINGS_PERSIST_LOG_ERROR("输入参数中含有NULL");
        return -1;
    }

    FILE* file = NULL;
    int retries = 2; /* 最多重试2次(1次正常写入 1次删除重建写入) */\n\n"""

    # 按section分组
    sections = {}
    for item in settings:
        section = item["section"]
        if section not in sections:
            sections[section] = []
        sections[section].append(item)

    # 生成每个section和配置项的写入代码
    first_section = True
    code += "    while (retries-- > 0) {\n"
    code += "        /* 尝试正常打开并写入 */\n"
    code += '        file = fopen(filename, "w");\n'
    code += "        if (file) {\n"
    for section, items in sections.items():
        first_section = False

        code += f"            /* Write {section} settings */\n"
        code += f'            fprintf(file, "[{section}]\\n");\n'

        for item in items:
            member_access = f"settings->{section}.{item['key']}"

            # 根据类型生成不同的写入代码
            if item["type"] in ["int", "float"]:
                fmt = "%f" if item["type"] == "float" else "%d"
                code += f"            fprintf(file, \"{item['key']}={fmt}\\n\", {member_access});\n"
            elif item["type"] == "bool":
                code += f"            fprintf(file, \"{item['key']}=%s\\n\", {member_access} ? \"true\" : \"false\");\n"
            elif item["type"].startswith("string:"):
                code += f"            fprintf(file, \"{item['key']}=%s\\n\", {member_access});\n"
            else:
                code += f"            /* Unsupported type: {item['type']} for {item['key']} */\n"
                code += f"            SETTINGS_PERSIST_LOG_ERROR(\"检测到{item['key']}具有暂不支持的数据类型({item['type']}), 请检查!!!\");\n"

    code += "            /* 确保数据刷盘 */\n"
    code += "            int fd = fileno(file);\n"
    code += "            if (fflush(file) != 0 || fsync(fd) != 0) {\n"
    code += "                fclose(file);\n"
    code += "                errno = EIO;\n"
    code += "                continue; /* 刷盘失败 开始重试 */\n"
    code += "            }\n"
    code += "            fclose(file);\n"
    code += '            SETTINGS_PERSIST_LOG_DEBUG("成功保存");\n'
    code += "            return 0; /* 写入成功 */\n"
    code += "        }\n"
    code += "\n"
    code += '        SETTINGS_PERSIST_LOG_ERROR("保存失败");\n'
    code += "        /* 打开失败 判断是否需要删除重建 */\n"
    code += "        int err = errno;\n"
    code += '        /* 仅处理"文件存在但无法打开"的情况 */\n'
    code += "        if (err != EIO && err != EACCES) {\n"
    code += "            /* 其他错误 */\n"
    code += '            SETTINGS_PERSIST_LOG_WARN("未知原因, 暂时无法挽救");\n'
    code += "            break;\n"
    code += "        }\n"
    code += "        struct stat st;\n"
    code += "        int file_exists = (stat(filename, &st) == 0);\n"
    code += "        int is_regular = file_exists ? S_ISREG(st.st_mode) : 0;\n"
    code += "\n"
    code += "        if (file_exists && is_regular) {\n"
    code += "            /* 尝试删除异常文件 */\n"
    code += (
        '            SETTINGS_PERSIST_LOG_INFO("文件存在但是无法打开, 准备删除重建");\n'
    )
    code += "            if (unlink(filename) != 0) {\n"
    code += "                /* 删除失败 直接退出 */\n"
    code += (
        '                SETTINGS_PERSIST_LOG_ERROR("文件unlink失败, 我也没招了");\n'
    )
    code += "                break;\n"
    code += "            }\n"
    code += "        }\n"
    code += "        else {\n"
    code += (
        '            SETTINGS_PERSIST_LOG_WARN("文件不存在或不是普通文件 无需删除");\n'
    )
    code += "            break;\n"
    code += "        }\n"
    code += "    }\n"
    code += "    /* 所有重试失败 返回错误 */\n"
    code += '    SETTINGS_PERSIST_LOG_ERROR("最终还是失败了");\n'
    code += "    return -2;\n"
    code += "}\n"

    return code


def main():
    settings = parse_settings_ini("./settings(for_code_generator).ini")

    # 调试：打印解析结果
    print("\nParsed settings:")
    for item in settings:
        print(f"Section: {item['section']}, Key: {item['key']}")
        print(f"  Type: {item['type']}, Default: {item['default']}")
        print(f"  Min: {item['min']}, Max: {item['max']}")
        print(f"  Comment: {item['comment']}\n")

    # 获取当前日期
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 生成代码
    print("Generating settings code...")
    header_code = generate_settings_persist_header(settings)
    set_functions = generate_settings_set_functions(settings)
    ini_handler = generate_ini_handler_function(settings)
    restore_defaults = generate_restore_defaults_function(settings)
    write_function = generate_write_function(settings)

    # 获取当前脚本所在的目录路径
    current_script_dir = Path(__file__).parent

    # 输出头文件
    header_path = current_script_dir / "../settings_persist.h"
    with open(header_path, "w") as f:
        f.write("/**\n")
        f.write(" * @file settings_persist.h\n")
        f.write(" * @author auto-generated\n")
        f.write(" * @brief Settings_persist模块的头文件\n")
        f.write(" * @version 0.1\n")
        f.write(f" * @date {current_date}\n")
        f.write(" *\n")
        f.write(" * @attention This file is auto-generated by generate_settings_from_ini.py. Do not edit manually!\n")
        f.write(" * @copyright Copyright (c) 2025\n")
        f.write(" *\n")
        f.write(" */\n")
        f.write(header_code)

    # 输出自动生成的实现文件
    impl_path = current_script_dir / "../settings_auto_generated.c"
    with open(impl_path, "w") as f:
        f.write("/**\n")
        f.write(" * @file settings_auto_generated.c\n")
        f.write(" * @author auto-generated\n")
        f.write(" * @brief Settings_persist模块中自动生成的代码\n")
        f.write(" * @version 0.1\n")
        f.write(f" * @date {current_date}\n")
        f.write(" *\n")
        f.write(" * @attention This file is auto-generated by generate_settings_from_ini.py. Do not edit manually!\n")
        f.write(" * @copyright Copyright (c) 2025\n")
        f.write(" *\n")
        f.write(" */\n")
        f.write("#include <errno.h>\n")
        f.write("#include <pthread.h>\n")
        f.write("#include <stdio.h>\n")
        f.write("#include <string.h>\n")
        f.write("#include <stdlib.h>\n")
        f.write("#include <unistd.h>\n")
        f.write("#include <sys/stat.h>\n")
        f.write('#include "settings_persist.h"\n')
        f.write('#define SETTINGS_PERSIST_MODULE_TAG "settings_persist"\n')
        f.write('#include "settings_persist_log.h"\n')
        f.write(set_functions)
        f.write(ini_handler)
        f.write("\n")
        f.write(restore_defaults)
        f.write("\n")
        f.write(write_function)

    print(f"Generated files: {header_path} and {impl_path}")


if __name__ == "__main__":
    main()
