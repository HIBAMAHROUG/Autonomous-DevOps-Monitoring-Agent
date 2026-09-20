"""
Schémas de données pour le module remediation
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
import json

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ActionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTED = "executed"
    FAILED = "failed"
    ESCALATED = "escalated"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"

class ActionType(str, Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    RESTART_SERVICE = "restart_service"
    CLEANUP_LOGS = "cleanup_logs"
    INCREASE_MEMORY = "increase_memory_limit"
    INCREASE_TIMEOUT = "increase_timeout"
    ADD_CDN = "add_cdn"
    CONFIG_CHANGE = "config_change"
    ALERT_ONLY = "alert_only"
    ROLLBACK = "rollback"

@dataclass
class RemediationAction:
    """Action corrective proposee"""
    action_id: str
    anomaly_id: str
    action_type: str
    description: str
    confidence_score: float
    severity: Severity
    estimated_impact: str
    command: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    rollback_plan: Optional[str] = None
    prerequisites: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    status: ActionStatus = ActionStatus.PENDING
    executed_at: Optional[datetime] = None
    execution_result: Optional[str] = None
    execution_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'action_id': self.action_id,
            'anomaly_id': self.anomaly_id,
            'action_type': self.action_type,
            'description': self.description,
            'confidence_score': self.confidence_score,
            'severity': self.severity.value if hasattr(self.severity, 'value') else str(self.severity),
            'estimated_impact': self.estimated_impact,
            'command': self.command,
            'parameters': json.dumps(self.parameters),
            'rollback_plan': self.rollback_plan,
            'prerequisites': json.dumps(self.prerequisites),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'status': self.status.value if hasattr(self.status, 'value') else str(self.status),
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'execution_result': self.execution_result,
            'execution_error': self.execution_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RemediationAction':
        return cls(
            action_id=data.get('action_id'),
            anomaly_id=data.get('anomaly_id'),
            action_type=data.get('action_type'),
            description=data.get('description'),
            confidence_score=data.get('confidence_score', 0.0),
            severity=Severity(data.get('severity', 'medium')) if data.get('severity') else Severity.MEDIUM,
            estimated_impact=data.get('estimated_impact', ''),
            command=data.get('command'),
            parameters=json.loads(data.get('parameters', '{}')) if data.get('parameters') else {},
            rollback_plan=data.get('rollback_plan'),
            prerequisites=json.loads(data.get('prerequisites', '[]')) if data.get('prerequisites') else [],
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(),
            status=ActionStatus(data.get('status', 'pending')) if data.get('status') else ActionStatus.PENDING,
            executed_at=datetime.fromisoformat(data['executed_at']) if data.get('executed_at') else None,
            execution_result=data.get('execution_result'),
            execution_error=data.get('execution_error')
        )

@dataclass
class KnowledgeEntry:
    """Entree dans la base de connaissances"""
    id: str
    problem_pattern: str
    anomaly_signature: Dict[str, Any]
    actions: List[Dict[str, Any]]
    success_rate: float
    times_used: int
    severity_level: str
    tags: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    last_used: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'problem_pattern': self.problem_pattern,
            'anomaly_signature': json.dumps(self.anomaly_signature),
            'actions': json.dumps(self.actions),
            'success_rate': self.success_rate,
            'times_used': self.times_used,
            'severity_level': self.severity_level,
            'tags': json.dumps(self.tags),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active,
            'last_used': self.last_used.isoformat() if self.last_used else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeEntry':
        return cls(
            id=data.get('id'),
            problem_pattern=data.get('problem_pattern'),
            anomaly_signature=json.loads(data.get('anomaly_signature', '{}')) if data.get('anomaly_signature') else {},
            actions=json.loads(data.get('actions', '[]')) if data.get('actions') else [],
            success_rate=data.get('success_rate', 0.0),
            times_used=data.get('times_used', 0),
            severity_level=data.get('severity_level', 'medium'),
            tags=json.loads(data.get('tags', '[]')) if data.get('tags') else [],
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(),
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.now(),
            is_active=data.get('is_active', True),
            last_used=datetime.fromisoformat(data['last_used']) if data.get('last_used') else None
        )

@dataclass
class DecisionHistory:
    """Historique des decisions prises"""
    id: str
    anomaly_id: str
    anomaly_description: str
    severity: Severity
    proposed_actions: List[RemediationAction]
    decision_reason: str
    final_status: ActionStatus
    selected_action: Optional[RemediationAction] = None
    confidence_of_selected: Optional[float] = None
    escalated: bool = False
    escalated_to: Optional[str] = None
    user_feedback: Optional[str] = None
    feedback_score: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'anomaly_id': self.anomaly_id,
            'anomaly_description': self.anomaly_description,
            'severity': self.severity.value if hasattr(self.severity, 'value') else str(self.severity),
            'proposed_actions': [a.to_dict() for a in self.proposed_actions],
            'decision_reason': self.decision_reason,
            'final_status': self.final_status.value if hasattr(self.final_status, 'value') else str(self.final_status),
            'selected_action': self.selected_action.to_dict() if self.selected_action else None,
            'confidence_of_selected': self.confidence_of_selected,
            'escalated': self.escalated,
            'escalated_to': self.escalated_to,
            'user_feedback': self.user_feedback,
            'feedback_score': self.feedback_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }
