import re

# 编译正则表达式用于切分 CamelCase / PascalCase 命名
# 模式说明：
#   [A-Z]+(?![a-z])   → 匹配连续的大写字母序列（如 "DB", "HTTP"），
#                        但后面不能紧跟小写字母（否则属于下一个模式匹配）
#   [A-Z][a-z0-9]*    → 匹配一个大写字母后跟零个或多个小写字母/数字（如 "Service", "Api"）
# 二者用 | 连接：先尝试匹配纯大写缩写，再匹配标准 PascalCase 单词
# 例如 "DBService" → ["DB", "Service"], "SimpleXMLParser" → ["Simple", "XML", "Parser"]
_camel_split = re.compile(r"([A-Z]+(?![a-z])|[A-Z][a-z0-9]*)")


def to_snake(name: str) -> str:
    # 使用正则表达式查找所有匹配的单词片段
    # findall 返回所有非重叠匹配的字符串列表
    parts = _camel_split.findall(name)

    if not parts:
        # 如果正则无法切分（例如输入已经是全小写 snake_case），直接返回小写结果
        return name.lower()

    # 将每个单词转为小写并用下划线连接
    # 例如 ["DB", "Service"] → "db_service"
    return "_".join(p.lower() for p in parts)
