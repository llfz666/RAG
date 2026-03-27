"""
Budget Manager - 预算管理器模块

负责：
1. 管理用户预算配置
2. 检查预算状态
3. 触发告警通知
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
from contextlib import contextmanager

from .config import TokenMonitorConfig
from .models import BudgetStatus, Alert, AlertType
from .tracker import TokenTracker


class BudgetManager:
    """
    预算管理器
    
    功能：
    - 设置和获取用户预算
    - 检查预算状态
    - 触发告警通知
    - 支持多种通知渠道（日志、邮件、企业微信）
    
    使用示例：
        budget_mgr = BudgetManager(tracker, config)
        
        # 设置预算
        budget_mgr.set_budget("user_123", daily=20.0, monthly=500.0)
        
        # 检查预算
        status = budget_mgr.check_budget("user_123")
        if status.is_over_budget:
            print("预算已用尽！")
        
        # 检查是否允许继续
        can_proceed, message = budget_mgr.can_proceed("user_123", estimated_cost=0.1)
    """
    
    def __init__(self, tracker: TokenTracker, config: TokenMonitorConfig):
        """
        初始化 BudgetManager
        
        Args:
            tracker: TokenTracker 实例
            config: 配置对象
        """
        self.tracker = tracker
        self.config = config
        
        # 告警回调函数
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        
        # 注册内置告警处理器
        self.register_alert_callback(self._log_alert)
    
    def register_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """
        注册告警回调函数
        
        Args:
            callback: 接收 Alert 对象的回调函数
        """
        self._alert_callbacks.append(callback)
    
    def _trigger_alert(self, alert: Alert) -> None:
        """触发告警通知"""
        # 保存到数据库
        self._save_alert(alert)
        
        # 调用所有回调
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"BudgetManager: 告警回调失败：{e}")
    
    def _save_alert(self, alert: Alert) -> None:
        """保存告警到数据库"""
        try:
            conn = sqlite3.connect(self.config.database_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alerts 
                (alert_type, message, timestamp, user_id, is_resolved, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_type.value,
                alert.message,
                alert.timestamp.isoformat(),
                alert.user_id,
                1 if alert.is_resolved else 0,
                json.dumps(alert.metadata, ensure_ascii=False) if alert.metadata else None,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"BudgetManager: 保存告警失败：{e}")
    
    def _log_alert(self, alert: Alert) -> None:
        """内置告警日志处理器"""
        level = "WARNING" if alert.alert_type == AlertType.BUDGET_WARNING else "ERROR"
        print(f"[{level}] Token Budget Alert: {alert.message}")
    
    def set_budget(
        self,
        user_id: str,
        daily: Optional[float] = None,
        monthly: Optional[float] = None,
        alert_threshold: Optional[float] = None,
    ) -> None:
        """
        设置用户预算
        
        Args:
            user_id: 用户 ID
            daily: 每日预算
            monthly: 每月预算
            alert_threshold: 告警阈值（0-1）
        """
        try:
            conn = sqlite3.connect(self.config.database_path, timeout=30.0)
            cursor = conn.cursor()
            
            # 检查用户是否已存在
            cursor.execute("SELECT user_id FROM user_budgets WHERE user_id = ?", (user_id,))
            exists = cursor.fetchone() is not None
            
            now = datetime.now().isoformat()
            
            if exists:
                # 更新
                updates = []
                params = []
                
                if daily is not None:
                    updates.append("daily_budget = ?")
                    params.append(daily)
                if monthly is not None:
                    updates.append("monthly_budget = ?")
                    params.append(monthly)
                if alert_threshold is not None:
                    updates.append("alert_threshold = ?")
                    params.append(alert_threshold)
                
                if updates:
                    updates.append("updated_at = ?")
                    params.append(now)
                    params.append(user_id)
                    
                    cursor.execute(f"""
                        UPDATE user_budgets SET {', '.join(updates)}
                        WHERE user_id = ?
                    """, params)
            else:
                # 插入
                cursor.execute("""
                    INSERT INTO user_budgets 
                    (user_id, daily_budget, monthly_budget, alert_threshold, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    daily or self.config.default_daily_budget,
                    monthly or self.config.default_monthly_budget,
                    alert_threshold or self.config.alert_threshold,
                    now,
                    now,
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"BudgetManager: 设置预算失败：{e}")
    
    def get_user_budget(self, user_id: str) -> Dict[str, Any]:
        """获取用户预算配置"""
        try:
            conn = sqlite3.connect(self.config.database_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_budgets WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'user_id': row['user_id'],
                    'daily_budget': row['daily_budget'],
                    'monthly_budget': row['monthly_budget'],
                    'alert_threshold': row['alert_threshold'],
                }
            else:
                return {
                    'user_id': user_id,
                    'daily_budget': self.config.default_daily_budget,
                    'monthly_budget': self.config.default_monthly_budget,
                    'alert_threshold': self.config.alert_threshold,
                }
        
        except Exception as e:
            print(f"BudgetManager: 获取用户预算失败：{e}")
            return {
                'user_id': user_id,
                'daily_budget': self.config.default_daily_budget,
                'monthly_budget': self.config.default_monthly_budget,
                'alert_threshold': self.config.alert_threshold,
            }
    
    def check_budget(self, user_id: Optional[str] = None) -> BudgetStatus:
        """
        检查预算状态
        
        Args:
            user_id: 用户 ID（可选，不传则检查全局预算）
        
        Returns:
            BudgetStatus 预算状态对象
        """
        # 获取今日和本月用量
        today_cost = self.tracker.get_today_usage(user_id)
        month_cost = self.tracker.get_month_usage(user_id)
        
        # 获取用户预算配置
        budget_config = self.get_user_budget(user_id) if user_id else {
            'daily_budget': self.config.default_daily_budget,
            'monthly_budget': self.config.default_monthly_budget,
            'alert_threshold': self.config.alert_threshold,
        }
        
        return BudgetStatus(
            today_cost=today_cost,
            daily_budget=budget_config['daily_budget'],
            monthly_budget=budget_config['monthly_budget'],
            month_cost=month_cost,
        )
    
    def can_proceed(
        self, 
        user_id: Optional[str] = None, 
        estimated_cost: float = 0.0
    ) -> Tuple[bool, str]:
        """
        检查是否可以继续执行 LLM 调用
        
        Args:
            user_id: 用户 ID
            estimated_cost: 预计成本
        
        Returns:
            (是否允许，消息)
        """
        status = self.check_budget(user_id)
        
        # 检查是否会超出预算
        if status.today_cost + estimated_cost > status.daily_budget:
            return False, f"今日预算不足（已用 ¥{status.today_cost:.2f}/¥{status.daily_budget:.2f}）"
        
        if status.month_cost + estimated_cost > status.monthly_budget:
            return False, f"本月预算不足（已用 ¥{status.month_cost:.2f}/¥{status.monthly_budget:.2f}）"
        
        # 检查是否需要告警
        if status.needs_warning:
            # 触发告警但不阻止
            self._trigger_budget_warning(status, user_id)
            return True, f"预算警告：今日已用{status.daily_usage_ratio*100:.1f}%"
        
        return True, "OK"
    
    def _trigger_budget_warning(self, status: BudgetStatus, user_id: Optional[str]) -> None:
        """触发预算警告"""
        # 避免重复告警（简单实现：每次都会触发，实际可以加缓存去重）
        alert = Alert(
            alert_type=AlertType.BUDGET_WARNING,
            message=f"预算使用已达{status.daily_usage_ratio*100:.1f}% "
                   f"(¥{status.today_cost:.2f}/¥{status.daily_budget:.2f})",
            user_id=user_id,
            metadata=status.to_dict(),
        )
        self._trigger_alert(alert)
    
    def check_and_alert(self, user_id: Optional[str] = None) -> BudgetStatus:
        """
        检查预算并触发必要的告警
        
        Args:
            user_id: 用户 ID
        
        Returns:
            BudgetStatus 预算状态
        """
        status = self.check_budget(user_id)
        
        # 检查是否超出预算
        if status.is_over_budget:
            alert = Alert(
                alert_type=AlertType.BUDGET_EXCEEDED,
                message=f"预算已用尽！"
                       f"今日：¥{status.today_cost:.2f}/¥{status.daily_budget:.2f}, "
                       f"本月：¥{status.month_cost:.2f}/¥{status.monthly_budget:.2f}",
                user_id=user_id,
                metadata=status.to_dict(),
            )
            self._trigger_alert(alert)
        
        # 检查是否需要警告
        elif status.needs_warning:
            self._trigger_budget_warning(status, user_id)
        
        return status
    
    def get_alerts(
        self,
        user_id: Optional[str] = None,
        days: int = 7,
        unresolved_only: bool = False,
    ) -> List[Alert]:
        """
        获取告警记录
        
        Args:
            user_id: 用户 ID（可选）
            days: 天数
            unresolved_only: 是否只获取未解决的告警
        
        Returns:
            Alert 列表
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        try:
            conn = sqlite3.connect(self.config.database_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM alerts WHERE timestamp >= ?"
            params = [cutoff]
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            if unresolved_only:
                query += " AND is_resolved = 0"
            
            query += " ORDER BY timestamp DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return [
                Alert(
                    alert_type=AlertType(row['alert_type']),
                    message=row['message'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    user_id=row['user_id'],
                    is_resolved=bool(row['is_resolved']),
                    resolved_at=datetime.fromisoformat(row['resolved_at']) if row['resolved_at'] else None,
                    metadata=json.loads(row['metadata']) if row['metadata'] else None,
                )
                for row in rows
            ]
        
        except Exception as e:
            print(f"BudgetManager: 获取告警记录失败：{e}")
            return []
    
    def resolve_alert(self, alert_id: int) -> bool:
        """
        标记告警为已解决
        
        Args:
            alert_id: 告警 ID
        
        Returns:
            是否成功
        """
        try:
            conn = sqlite3.connect(self.config.database_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE alerts 
                SET is_resolved = 1, resolved_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), alert_id))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"BudgetManager: 更新告警状态失败：{e}")
            return False
    
    def send_wechat_alert(self, alert: Alert) -> None:
        """
        发送企业微信告警
        
        Args:
            alert: 告警对象
        """
        if not self.config.alert_wechat_webhook:
            return
        
        try:
            import requests
            
            # 构建消息
            if alert.alert_type == AlertType.BUDGET_WARNING:
                color = "warning"
                title = "⚠️ 预算警告"
            elif alert.alert_type == AlertType.BUDGET_EXCEEDED:
                color = "danger"
                title = "🚨 预算已用尽"
            else:
                color = "comment"
                title = "📊 Token 监控"
            
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"""## {title}
> 用户：{alert.user_id or '全局'}
> 消息：{alert.message}
> 时间：{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""
                }
            }
            
            requests.post(
                self.config.alert_wechat_webhook,
                json=message,
                timeout=10
            )
            
        except Exception as e:
            print(f"BudgetManager: 发送企业微信告警失败：{e}")
    
    def send_email_alert(self, alert: Alert) -> None:
        """
        发送邮件告警
        
        Args:
            alert: 告警对象
        """
        if not self.config.alert_email:
            return
        
        # 这里可以实现邮件发送逻辑
        # 需要使用 smtplib 或第三方邮件服务
        print(f"BudgetManager: 邮件告警（未实现）：{alert.message}")