# 文档质量检测模块使用指南

## 概述

文档质量检测模块是 RAG 系统 Pipeline 入口的前处理组件，用于在文档入库前进行质量预检，防止低质量文档污染知识库。

## 设计原理

### 问题背景
- 低质量 PDF（如扫描件、模糊复印件）的文本层存在严重问题
- 强行入库会导致切分出的 chunk 质量低下
- 检索质量无法保证，影响整个 RAG 系统效果

### 解决方案
在 Pipeline 入口添加质量检测关卡：
1. 提取前几页文本
2. 计算有效字符占比和可识别文本密度
3. 低于阈值直接拒绝入库
4. 在 Dashboard 上给用户明确的提示

## 核心指标

### 1. 有效字符占比 (Effective Character Ratio)
```
有效字符占比 = 非空白字符数 / 总字符数
```
- **阈值**: ≥80% (默认)
- **说明**: 衡量文本中实际内容字符的比例

### 2. 可识别文本密度 (Text Density)
```
文本密度 = 非空行数 / 总行数
```
- **阈值**: ≥70% (默认)
- **说明**: 衡量文档行结构的紧凑程度

### 3. 乱码比例 (Garbage Ratio)
```
乱码比例 = 乱码字符数 / 总字符数
```
- **阈值**: ≤5% (默认)
- **说明**: 检测控制字符、替换字符等无效字符

### 4. 最小文本长度 (Min Text Length)
- **阈值**: ≥500 字符 (默认)
- **说明**: 确保提取的文本有足够的信息量

## 模块架构

```
src/ingestion/quality/
├── __init__.py          # 模块导出
├── checker.py           # 主检测器
├── metrics.py           # 指标计算
├── exceptions.py        # 异常定义
└── config.py            # 配置管理
```

## 使用示例

### 基础用法
```python
from src.ingestion.quality import DocumentQualityChecker, QualityCheckFailed

# 创建检测器
checker = DocumentQualityChecker(threshold=0.80, max_pages=5)

# 执行检测
try:
    result = checker.check_or_raise("document.pdf")
    print("✅ 质量检查通过")
except QualityCheckFailed as e:
    print(f"❌ 质量检查失败：{e.message}")
```

### 获取详细报告
```python
result = checker.check("document.pdf")

if not result.passed:
    print(result.details)
    # 输出：
    # ❌ 文档质量不达标
    # === 检测结果 ===
    # 分析页数：5
    # 文本总长度：350 字符
    # === 质量指标 ===
    # 有效字符占比：65.23%
    # 可识别文本密度：45.10%
    # 乱码比例：8.50%
    # === 建议 ===
    # • 检查原始文档是否清晰可读
    # • 如为扫描件，尝试 OCR 增强版本
    # • 联系文档提供方获取可编辑版本
```

### 严格模式
```python
# 使用更严格的阈值
strict_checker = DocumentQualityChecker(
    threshold=0.85,
    max_pages=5,
    strict_mode=True  # 启用严格模式
)
```

## 集成到 Pipeline

质量检测已自动集成到 IngestionPipeline 中：

```python
from src.ingestion.pipeline import IngestionPipeline

pipeline = IngestionPipeline(settings, collection="default")
result = pipeline.run("document.pdf")

if not result.success:
    if "文档质量不达标" in result.error:
        # 处理质量检查失败
        print("文档质量不符合入库标准")
```

## Dashboard 展示

当用户上传低质量文档时，Dashboard 会显示：

```
❌ 文档质量检查未通过

📊 质量检测报告

检测值                    阈值要求
有效字符占比：65.2%   |   ≥80%
文本密度：45.1%       |   ≥70%
乱码比例：8.50%       |   ≤5%

💡 建议
• 检查原始文档是否清晰可读
• 如为扫描件，尝试使用 OCR 增强版本
• 联系文档提供方获取可编辑版本（如 Word 格式）
• 确保 PDF 包含可选择的文本层，而非纯图片
```

## 配置选项

### QualityThresholds 配置
```python
from src.ingestion.quality import QualityThresholds

thresholds = QualityThresholds(
    min_effective_char_ratio=0.80,  # 最小有效字符占比
    min_text_density=0.70,          # 最小文本密度
    max_garbage_ratio=0.05,         # 最大乱码比例
    min_text_length=500,            # 最小文本长度
    max_replacement_chars=10,       # 最大替换字符数
)
```

### 自定义阈值
```python
checker = DocumentQualityChecker(
    threshold=0.75,      # 自定义有效字符占比阈值
    max_pages=3,         # 只检测前 3 页
    dpi=200,             # OCR 渲染 DPI
    strict_mode=False    # 不使用严格模式
)
```

## 异常处理

### InvalidDocumentError
当文件无法处理时抛出：
- 文件不存在
- 文件为空
- 文件格式错误
- 缺少依赖（PyMuPDF）

```python
from src.ingestion.quality import InvalidDocumentError

try:
    checker.check("missing.pdf")
except InvalidDocumentError as e:
    print(f"文件无效：{e.reason}")  # file_not_found, empty_file, etc.
```

### QualityCheckFailed
当质量检查失败时抛出：

```python
from src.ingestion.quality import QualityCheckFailed

try:
    checker.check_or_raise("low_quality.pdf")
except QualityCheckFailed as e:
    print(f"有效字符占比：{e.effective_char_ratio}")
    print(f"文本密度：{e.text_density}")
    print(f"乱码比例：{e.garbage_ratio}")
```

## 测试

运行单元测试：
```bash
python -m pytest tests/unit/test_quality_checker.py -v
```

## 面试要点

### 1. 设计理念
- **预防优于治理**: 在入口拦截低质量文档，避免后续处理浪费资源
- **明确反馈**: 给用户清晰的失败原因和改进建议
- **可配置**: 不同场景可调整阈值

### 2. 技术实现
- **多维度指标**: 综合评估文档质量
- **Unicode 分析**: 精确识别不同语言字符
- **分级告警**: 失败项和警告项区分

### 3. 业务价值
- 提升知识库整体质量
- 减少无效检索结果
- 改善用户体验

## 扩展建议

### 未来增强
1. **OCR 质量评估**: 对 OCR 结果进行置信度分析
2. **表格检测**: 识别表格结构完整性
3. **图片质量**: 评估嵌入图片的清晰度
4. **语言检测**: 自动识别文档语言
5. **敏感信息**: 检测并标记敏感内容

### 性能优化
1. **异步处理**: 大文件异步检测
2. **缓存机制**: 已检测文档结果缓存
3. **批量检测**: 支持批量文档质量评估

## 常见问题

**Q: 为什么只检测前几页？**
A: 文档通常具有均匀的质量分布，前几页能代表整体质量。检测全部页面会增加处理时间。

**Q: 阈值如何设定？**
A: 默认阈值基于大量测试数据设定。可根据实际业务场景调整，建议先运行一批样本文档分析分布。

**Q: 扫描件一定无法通过吗？**
A: 不一定。清晰的扫描件配合优质 OCR 可以通过检测。建议对扫描件使用 OCR 增强模式。

**Q: 如何查看详细的检测日志？**
A: 设置日志级别为 DEBUG：
```python
import logging
logging.getLogger('src.ingestion.quality').setLevel(logging.DEBUG)