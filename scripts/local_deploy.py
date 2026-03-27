#!/usr/bin/env python3
"""
本地化部署脚本

一键部署本地 RAG 系统，使用开源模型实现完全本地化运行：
- LLM: Qwen2.5-Coder (通过 Ollama)
- Embedding: BGE-M3 (通过 Ollama)
- Reranker: BGE-Reranker (本地 Cross-Encoder)

使用方法:
    python scripts/local_deploy.py

依赖:
    - Ollama (https://ollama.ai)
    - Python 3.11+
"""

import subprocess
import sys
import os
from pathlib import Path


# 颜色输出
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_step(message: str):
    print(f"\n{Colors.BLUE}>>> {message}{Colors.END}")


def print_success(message: str):
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_warning(message: str):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")


def print_error(message: str):
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def check_ollama_installed() -> bool:
    """检查 Ollama 是否已安装"""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_model_installed(model_name: str) -> bool:
    """检查模型是否已下载"""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return model_name in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def run_command(cmd: list, description: str) -> bool:
    """运行命令并显示进度"""
    print(f"正在 {description}...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 分钟超时
        )
        if result.returncode == 0:
            print_success(f"{description} 完成")
            return True
        else:
            print_error(f"{description} 失败：{result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print_error(f"{description} 超时")
        return False
    except Exception as e:
        print_error(f"{description} 异常：{e}")
        return False


def install_ollama():
    """安装 Ollama"""
    print_step("安装 Ollama")
    
    system = sys.platform
    if system == "win32":
        print_warning("Windows 系统请手动安装 Ollama:")
        print("1. 访问 https://ollama.ai/download")
        print("2. 下载并运行安装程序")
        print("3. 安装完成后重新运行此脚本")
        return False
    elif system == "darwin":
        return run_command(
            ["brew", "install", "ollama"],
            "通过 Homebrew 安装 Ollama"
        )
    else:
        # Linux
        return run_command(
            ["curl", "-fsSL", "https://ollama.ai/install.sh", "|", "sh"],
            "安装 Ollama",
        )


def pull_model(model_name: str):
    """下载模型"""
    return run_command(
        ["ollama", "pull", model_name],
        f"下载模型 {model_name}"
    )


def create_local_config():
    """创建本地化配置文件"""
    print_step("创建本地化配置")
    
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    config_content = """# 本地化部署配置
# 使用 Ollama + 开源模型实现完全本地化运行

llm:
  provider: ollama
  base_url: http://localhost:11434
  model: qwen2.5-coder:7b
  temperature: 0.7
  max_tokens: 2048

embedding:
  provider: ollama
  base_url: http://localhost:11434
  model: bge-m3:latest

reranker:
  enabled: true
  provider: cross_encoder
  model: BAAI/bge-reranker-base

vector_store:
  provider: chroma
  persist_directory: data/db/chroma

bm25:
  index_dir: data/db/bm25

# 本地部署不需要 API Key
# 确保 Ollama 服务已启动：ollama serve
"""
    
    config_path = config_dir / "local_settings.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(config_content)
    
    print_success(f"配置文件已创建：{config_path}")
    return True


def create_docker_compose():
    """创建 Docker Compose 配置"""
    print_step("创建 Docker Compose 配置")
    
    docker_compose_content = """version: '3.8'

services:
  # Ollama 服务 - 提供 LLM 和 Embedding 能力
  ollama:
    image: ollama/ollama:latest
    container_name: rag-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    # 如果没有 GPU，移除上面的 deploy 部分
    
  # RAG MCP Server
  rag-server:
    build:
      context: .
      dockerfile: Dockerfile.local
    container_name: rag-mcp-server
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - CONFIG_PATH=/app/config/local_settings.yaml
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    depends_on:
      - ollama
    command: python main.py

  # Dashboard
  rag-dashboard:
    build:
      context: .
      dockerfile: Dockerfile.local
    container_name: rag-dashboard
    ports:
      - "8501:8501"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - CONFIG_PATH=/app/config/local_settings.yaml
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    depends_on:
      - ollama
    command: streamlit run src/observability/dashboard/app.py --server.address 0.0.0.0

volumes:
  ollama_data:
"""
    
    docker_path = Path("docker-compose.local.yml")
    with open(docker_path, "w", encoding="utf-8") as f:
        f.write(docker_compose_content)
    
    print_success(f"Docker Compose 配置已创建：{docker_path}")
    
    # 创建 Dockerfile
    dockerfile_content = """FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY pyproject.toml .
COPY current_requirements.txt .
RUN pip install -e .

# 复制项目代码
COPY src/ src/
COPY config/ config/
COPY scripts/ scripts/
COPY main.py .

# 创建数据目录
RUN mkdir -p data

EXPOSE 8000 8501

CMD ["python", "main.py"]
"""
    
    dockerfile_path = Path("Dockerfile.local")
    with open(dockerfile_path, "w", encoding="utf-8") as f:
        f.write(dockerfile_content)
    
    print_success(f"Dockerfile 已创建：{dockerfile_path}")
    
    return True


def create_quick_start_script():
    """创建快速启动脚本"""
    print_step("创建快速启动脚本")
    
    start_script_content = '''#!/usr/bin/env python3
"""
本地 RAG 系统快速启动脚本

使用方法:
    python scripts/start_local.py
"""

import subprocess
import sys
import time
from pathlib import Path


def check_ollama_running() -> bool:
    """检查 Ollama 服务是否运行"""
    import requests
    try:
        response = requests.get("http://localhost:11434/api/version", timeout=5)
        return response.status_code == 200
    except:
        return False


def start_ollama():
    """启动 Ollama 服务"""
    print("启动 Ollama 服务...")
    if sys.platform == "win32":
        # Windows 需要手动启动
        print("请在系统托盘启动 Ollama，或运行：ollama serve")
        return False
    else:
        subprocess.Popen(["ollama", "serve"])
        time.sleep(3)
        return check_ollama_running()


def main():
    print("=" * 50)
    print("本地 RAG 系统启动")
    print("=" * 50)
    
    # 检查 Ollama
    if not check_ollama_running():
        print("Ollama 服务未运行，尝试启动...")
        if not start_ollama():
            print("无法启动 Ollama 服务，请先手动启动")
            sys.exit(1)
    
    print("✓ Ollama 服务运行正常")
    
    # 检查配置文件
    config_path = Path("config/local_settings.yaml")
    if not config_path.exists():
        print("配置文件不存在，请先运行：python scripts/local_deploy.py")
        sys.exit(1)
    
    print("✓ 配置文件已就绪")
    
    # 启动 MCP Server
    print("\\n启动 MCP Server...")
    print("访问地址：http://localhost:8000")
    print("按 Ctrl+C 停止服务\\n")
    
    try:
        subprocess.run([
            sys.executable, "main.py",
            "--config", str(config_path)
        ])
    except KeyboardInterrupt:
        print("\\n服务已停止")


if __name__ == "__main__":
    main()
'''
    
    script_path = Path("scripts/start_local.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(start_script_content)
    
    print_success(f"快速启动脚本已创建：{script_path}")
    return True


def main():
    """主函数"""
    print("=" * 60)
    print(f"{Colors.GREEN}本地 RAG 系统部署脚本{Colors.END}")
    print("=" * 60)
    print("\n此脚本将帮助你完成本地化部署配置")
    print("使用开源模型，无需 API Key，完全本地运行\n")
    
    # 步骤 1: 检查 Ollama
    print_step("检查 Ollama 安装状态")
    if not check_ollama_installed():
        print_warning("Ollama 未安装")
        choice = input("是否要安装 Ollama? (y/n): ")
        if choice.lower() == 'y':
            if not install_ollama():
                print_error("Ollama 安装失败，请手动安装后重新运行")
                return
        else:
            print_warning("跳过 Ollama 安装，请确保已手动安装")
    
    print_success("Ollama 已安装")
    
    # 步骤 2: 下载模型
    print_step("下载所需模型")
    
    models_needed = [
        ("qwen2.5-coder:7b", "LLM 模型"),
        ("bge-m3:latest", "Embedding 模型"),
    ]
    
    for model_name, model_desc in models_needed:
        if not check_model_installed(model_name):
            print(f"需要下载 {model_desc}: {model_name}")
            choice = input(f"是否现在下载？(y/n): ")
            if choice.lower() == 'y':
                if not pull_model(model_name):
                    print_warning(f"{model_name} 下载失败，可稍后手动下载：ollama pull {model_name}")
            else:
                print_warning(f"跳过 {model_name}，可稍后手动下载")
        else:
            print_success(f"{model_desc} 已安装：{model_name}")
    
    # 步骤 3: 创建配置
    create_local_config()
    
    # 步骤 4: 创建 Docker 配置（可选）
    print_step("创建 Docker 配置（可选）")
    choice = input("是否需要创建 Docker Compose 配置？(y/n): ")
    if choice.lower() == 'y':
        create_docker_compose()
    
    # 步骤 5: 创建启动脚本
    create_quick_start_script()
    
    # 完成
    print("\n" + "=" * 60)
    print_success("本地化部署配置完成！")
    print("=" * 60)
    print("\n下一步操作:")
    print("1. 确保 Ollama 服务已启动：ollama serve")
    print("2. 下载所需模型（如果还没下载）:")
    print("   ollama pull qwen2.5-coder:7b")
    print("   ollama pull bge-m3:latest")
    print("3. 启动服务:")
    print("   python scripts/start_local.py")
    print("\n或使用 Docker Compose 启动:")
    print("   docker-compose -f docker-compose.local.yml up -d")
    print("=" * 60)


if __name__ == "__main__":
    main()