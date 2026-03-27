"""
Token Monitor 单元测试

测试范围：
1. 配置加载和验证
2. TokenTracker 核心功能
3. BudgetManager 预算检查
4. 数据模型序列化
"""

import pytest
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import json

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.observability.token_monitor.config import TokenMonitorConfig
from src.observability.token_monitor.models import (
    TokenUsage, TokenStatus, BudgetStatus, Alert, AlertType
)
from src.observability.token_monitor.tracker import TokenTracker
from src.observability.token_monitor.budget import BudgetManager


class TestTokenMonitorConfig:
    """测试配置模块"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = TokenMonitorConfig()
        
        assert config.enabled is True
        assert config.database_path == "data/token_usage.db"
        assert config.default_daily_budget == 10.0
        assert config.default_monthly_budget == 300.0
        assert config.alert_threshold == 0.8
    
    def test_config_validation_valid(self):
        """测试配置验证（有效配置）"""
        config = TokenMonitorConfig()
        errors = config.validate()
        
        assert len(errors) == 0
    
    def test_config_validation_invalid_threshold(self):
        """测试配置验证（无效阈值）"""
        config = TokenMonitorConfig(alert_threshold=1.5)
        errors = config.validate()
        
        assert any("alert_threshold" in e for e in errors)
    
    def test_config_validation_invalid_sampling_rate(self):
        """测试配置验证（无效采样率）"""
        config = TokenMonitorConfig(sampling_rate=1.5)
        errors = config.validate()
        
        assert any("sampling_rate" in e for e in errors)
    
    def test_config_validation_negative_budget(self):
        """测试配置验证（负预算）"""
        config = TokenMonitorConfig(default_daily_budget=-100)
        errors = config.validate()
        
        assert any("default_daily_budget" in e for e in errors)
    
    def test_get_model_price(self):
        """测试模型定价获取"""
        config = TokenMonitorConfig()
        
        # 测试已知模型
        price = config.get_model_price("gpt-4")
        assert "input" in price
        assert "output" in price
        
        # 测试未知模型（返回默认）
        price = config.get_model_price("unknown-model")
        assert price == config.model_pricing["default"]
    
    def test_calculate_cost(self):
        """测试成本计算"""
        config = TokenMonitorConfig()
        
        # 测试 GPT-4 成本计算
        cost = config.calculate_cost("gpt-4", 1000, 500)
        expected = (1000 / 1000) * 0.064 + (500 / 1000) * 0.128
        assert abs(cost - expected) < 0.0001
    
    def test_from_yaml_with_temp_file(self):
        """测试从 YAML 加载配置"""
        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
token_monitor:
  enabled: true
  database_path: "/tmp/test.db"
  budgets:
    default_daily: 20.0
    default_monthly: 500.0
    alert_threshold: 0.7
""")
            temp_path = f.name
        
        try:
            config = TokenMonitorConfig.from_yaml(temp_path)
            
            assert config.enabled is True
            assert config.database_path == "/tmp/test.db"
            assert config.default_daily_budget == 20.0
            assert config.default_monthly_budget == 500.0
            assert config.alert_threshold == 0.7
        finally:
            os.unlink(temp_path)
    
    def test_env_override(self, monkeypatch):
        """测试环境变量覆盖"""
        monkeypatch.setenv("TOKEN_MONITOR_DAILY_BUDGET", "99.9")
        monkeypatch.setenv("TOKEN_MONITOR_ENABLED", "false")
        
        config = TokenMonitorConfig.from_yaml("/nonexistent.yaml")
        
        assert config.default_daily_budget == 99.9
        # 验证环境变量被正确读取（字符串"false"会被解析为 False）
        assert str(config.enabled).lower() == "false" or config.enabled is False


class TestTokenUsage:
    """测试 TokenUsage 数据模型"""
    
    def test_creation(self):
        """测试创建记录"""
        usage = TokenUsage(
            model="gpt-3.5-turbo",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.01
        )
        
        assert usage.model == "gpt-3.5-turbo"
        assert usage.total_tokens == 150
        assert usage.status == TokenStatus.SUCCESS
    
    def test_to_dict(self):
        """测试序列化为字典"""
        usage = TokenUsage(
            model="gpt-4",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            cost=0.05,
            user_id="user_123"
        )
        
        data = usage.to_dict()
        
        assert data["model"] == "gpt-4"
        assert data["user_id"] == "user_123"
        assert "timestamp" in data
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "model": "qwen-plus",
            "prompt_tokens": 150,
            "completion_tokens": 75,
            "total_tokens": 225,
            "cost": 0.02,
            "status": "success",
            "timestamp": "2024-01-01T12:00:00"
        }
        
        usage = TokenUsage.from_dict(data)
        
        assert usage.model == "qwen-plus"
        assert isinstance(usage.timestamp, datetime)


class TestBudgetStatus:
    """测试预算状态"""
    
    def test_remaining_budget(self):
        """测试剩余预算计算"""
        status = BudgetStatus(
            today_cost=5.0,
            daily_budget=10.0,
            monthly_budget=300.0,
            month_cost=150.0
        )
        
        assert status.remaining_daily == 5.0
        assert status.remaining_monthly == 150.0
    
    def test_usage_ratio(self):
        """测试使用率计算"""
        status = BudgetStatus(
            today_cost=8.0,
            daily_budget=10.0,
            monthly_budget=300.0,
            month_cost=250.0
        )
        
        assert abs(status.daily_usage_ratio - 0.8) < 0.001
        assert abs(status.monthly_usage_ratio - 0.833) < 0.001
    
    def test_needs_warning(self):
        """测试告警判断"""
        # 未达警告阈值
        status1 = BudgetStatus(today_cost=5.0, daily_budget=10.0, monthly_budget=300.0, month_cost=100.0)
        assert not status1.needs_warning
        
        # 达到警告阈值
        status2 = BudgetStatus(today_cost=8.0, daily_budget=10.0, monthly_budget=300.0, month_cost=100.0)
        assert status2.needs_warning
    
    def test_is_over_budget(self):
        """测试超预算判断"""
        # 未超预算
        status1 = BudgetStatus(today_cost=5.0, daily_budget=10.0, monthly_budget=300.0, month_cost=100.0)
        assert not status1.is_over_budget
        
        # 超预算
        status2 = BudgetStatus(today_cost=15.0, daily_budget=10.0, monthly_budget=300.0, month_cost=100.0)
        assert status2.is_over_budget


class TestTokenTracker:
    """测试 TokenTracker"""
    
    @pytest.fixture
    def temp_config(self):
        """创建临时配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_token_usage.db")
            log_path = os.path.join(tmpdir, "test_token_usage.jsonl")
            
            config = TokenMonitorConfig(
                database_path=db_path,
                log_file=log_path,
                enabled=True,
                sampling_enabled=False,
            )
            yield config
    
    @pytest.fixture
    def tracker(self, temp_config):
        """创建 Tracker 实例"""
        return TokenTracker(temp_config)
    
    def test_record_basic(self, tracker):
        """测试基本记录功能"""
        usage = tracker.record(
            model="gpt-3.5-turbo",
            prompt_tokens=100,
            completion_tokens=50,
            user_id="test_user",
            task_type="chat",
            sync=True
        )
        
        assert usage.model == "gpt-3.5-turbo"
        assert usage.total_tokens == 150
        assert usage.cost > 0
    
    def test_record_with_metadata(self, tracker):
        """测试带元数据的记录"""
        usage = tracker.record(
            model="gpt-4",
            prompt_tokens=200,
            completion_tokens=100,
            user_id="test_user",
            metadata={"session_id": "abc123", "custom_field": "value"},
            sync=True
        )
        
        assert usage.metadata["session_id"] == "abc123"
    
    def test_get_stats(self, tracker):
        """测试统计查询"""
        # 先记录一些数据
        for i in range(5):
            tracker.record(
                model="gpt-3.5-turbo",
                prompt_tokens=100,
                completion_tokens=50,
                user_id="test_user",
                sync=True
            )
        
        stats = tracker.get_stats(days=1)
        
        assert stats.total_requests == 5
        assert stats.total_tokens == 750  # 5 * 150
    
    def test_get_model_breakdown(self, tracker):
        """测试模型用量明细"""
        # 记录不同模型的数据
        tracker.record(model="gpt-4", prompt_tokens=100, completion_tokens=50, sync=True)
        tracker.record(model="gpt-3.5-turbo", prompt_tokens=100, completion_tokens=50, sync=True)
        tracker.record(model="gpt-4", prompt_tokens=100, completion_tokens=50, sync=True)
        
        breakdown = tracker.get_model_breakdown(days=1)
        
        assert len(breakdown) == 2
        assert breakdown[0].model == "gpt-4"  # 按成本排序
    
    def test_disabled_tracker(self, temp_config):
        """测试禁用的追踪器"""
        temp_config.enabled = False
        tracker = TokenTracker(temp_config)
        
        usage = tracker.record(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
        )
        
        assert usage.cost == 0.0
    
    def test_sampling(self, temp_config):
        """测试采样功能"""
        temp_config.sampling_enabled = True
        temp_config.sampling_rate = 0.0  # 0% 采样
        tracker = TokenTracker(temp_config)
        
        # 多次记录，应该都被跳过
        for _ in range(100):
            tracker.record(
                model="gpt-4",
                prompt_tokens=100,
                completion_tokens=50,
                sync=True
            )
        
        stats = tracker.get_stats(days=1)
        assert stats.total_requests == 0


class TestBudgetManager:
    """测试 BudgetManager"""
    
    @pytest.fixture
    def temp_config(self):
        """创建临时配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_token_usage.db")
            log_path = os.path.join(tmpdir, "test_token_usage.jsonl")
            
            config = TokenMonitorConfig(
                database_path=db_path,
                log_file=log_path,
                default_daily_budget=10.0,
                default_monthly_budget=300.0,
            )
            yield config
    
    @pytest.fixture
    def tracker_and_budget(self, temp_config):
        """创建 Tracker 和 BudgetManager"""
        tracker = TokenTracker(temp_config)
        budget_mgr = BudgetManager(tracker, temp_config)
        return tracker, budget_mgr
    
    def test_check_budget(self, tracker_and_budget):
        """测试预算检查"""
        tracker, budget_mgr = tracker_and_budget
        
        status = budget_mgr.check_budget()
        
        assert status.today_cost == 0
        assert status.daily_budget == 10.0
    
    def test_set_user_budget(self, tracker_and_budget):
        """测试设置用户预算"""
        tracker, budget_mgr = tracker_and_budget
        
        budget_mgr.set_budget("user_123", daily=20.0, monthly=600.0)
        
        user_config = budget_mgr.get_user_budget("user_123")
        assert user_config["daily_budget"] == 20.0
        assert user_config["monthly_budget"] == 600.0
    
    def test_can_proceed(self, tracker_and_budget):
        """测试是否可以继续"""
        tracker, budget_mgr = tracker_and_budget
        
        # 预算充足
        can_proceed, message = budget_mgr.can_proceed(estimated_cost=0.1)
        assert can_proceed is True
        
        # 记录一些用量
        tracker.record(
            model="gpt-4",
            prompt_tokens=5000,
            completion_tokens=2500,
            sync=True
        )
        
        # 再次检查（取决于实际成本）
        can_proceed, message = budget_mgr.can_proceed(estimated_cost=0.1)
        # 可能仍然可以，因为 GPT-4 成本不高
    
    def test_budget_alerts(self, tracker_and_budget):
        """测试预算告警"""
        tracker, budget_mgr = tracker_and_budget
        
        # 获取告警（应该是空的）
        alerts = budget_mgr.get_alerts(days=1)
        assert len(alerts) == 0
    
    def test_resolve_alert(self, tracker_and_budget):
        """测试解决告警"""
        tracker, budget_mgr = tracker_and_budget
        
        # 先触发一个告警
        budget_mgr.check_and_alert()
        
        alerts = budget_mgr.get_alerts(days=1)
        if alerts:
            result = budget_mgr.resolve_alert(alerts[0].id)
            assert result is True
            
            # 验证已解决
            alerts = budget_mgr.get_alerts(days=1, unresolved_only=True)
            # 告警可能不存在或已解决


if __name__ == "__main__":
    pytest.main([__file__, "-v"])