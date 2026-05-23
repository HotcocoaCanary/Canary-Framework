# 从 cf.core 包中导入所有公开 API（config, service, module, on_init, on_start, on_end, Canary, Context）
# 这样用户只需 `from cf import Canary, service, ...` 即可使用框架的全部核心功能
from cf.core import *
