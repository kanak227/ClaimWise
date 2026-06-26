import json
from sqlalchemy import Column, String, Boolean, Integer, Float, Text, LargeBinary
from .db import Base

class DBRule(Base):
    __tablename__ = "routing_rules"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=50)
    condition_type = Column(String, nullable=True)
    condition_value = Column(String, nullable=True)
    claim_type = Column(String, nullable=True)
    routing_team = Column(String, nullable=True)
    adjuster = Column(String, nullable=True)
    operator = Column(String, nullable=True)
    threshold = Column(Float, nullable=True)
    fraud_category = Column(String, nullable=True)
    severity_category = Column(String, nullable=True)
    complexity_category = Column(String, nullable=True)
    attribute = Column(String, nullable=True)
    amount = Column(Float, nullable=True)
    forward_to = Column(String, nullable=True)
    created_at = Column(String, nullable=True)
    updated_at = Column(String, nullable=True)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class DBClaim(Base):
    __tablename__ = "claims"
    
    id = Column(String, primary_key=True)
    claim_number = Column(String, nullable=False)
    claimant = Column(String, nullable=False)
    policy_no = Column(String, nullable=False)
    loss_type = Column(String, nullable=False)
    claim_type = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    severity_level = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    queue = Column(String, nullable=False)
    routing_team = Column(String, nullable=False)
    final_team = Column(String, nullable=False)
    status = Column(String, default="Processing")
    email = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    rationale = Column(Text, nullable=True)
    
    # Store nested JSON data as string text
    _evidence = Column("evidence", Text, nullable=True)
    _ai_analysis = Column("ai_analysis", Text, nullable=True)
    _sources = Column("sources", Text, nullable=True)
    _attachments = Column("attachments", Text, nullable=True)
    _ml_scores = Column("ml_scores", Text, nullable=True)
    _routing = Column("routing", Text, nullable=True)
    _history = Column("history", Text, nullable=True)
    
    assignee = Column(String, nullable=True)
    adjuster = Column(String, nullable=True)
    fraud_score = Column(Float, nullable=True)
    complexity_score = Column(Float, nullable=True)

    @property
    def evidence(self):
        return json.loads(self._evidence) if self._evidence else []
    @evidence.setter
    def evidence(self, val):
        self._evidence = json.dumps(val)

    @property
    def ai_analysis(self):
        return json.loads(self._ai_analysis) if self._ai_analysis else {}
    @ai_analysis.setter
    def ai_analysis(self, val):
        self._ai_analysis = json.dumps(val)

    @property
    def sources(self):
        return json.loads(self._sources) if self._sources else []
    @sources.setter
    def sources(self, val):
        self._sources = json.dumps(val)

    @property
    def attachments(self):
        return json.loads(self._attachments) if self._attachments else []
    @attachments.setter
    def attachments(self, val):
        self._attachments = json.dumps(val)

    @property
    def ml_scores(self):
        return json.loads(self._ml_scores) if self._ml_scores else {}
    @ml_scores.setter
    def ml_scores(self, val):
        self._ml_scores = json.dumps(val)

    @property
    def routing(self):
        return json.loads(self._routing) if self._routing else {}
    @routing.setter
    def routing(self, val):
        self._routing = json.dumps(val)

    @property
    def history(self):
        return json.loads(self._history) if self._history else []
    @history.setter
    def history(self, val):
        self._history = json.dumps(val)

    def to_dict(self):
        return {
            "id": self.id,
            "claim_number": self.claim_number,
            "claimant": self.claimant,
            "policy_no": self.policy_no,
            "loss_type": self.loss_type,
            "claim_type": self.claim_type,
            "created_at": self.created_at,
            "severity": self.severity,
            "severity_level": self.severity_level,
            "confidence": self.confidence,
            "queue": self.queue,
            "routing_team": self.routing_team,
            "final_team": self.final_team,
            "status": self.status,
            "email": self.email,
            "description": self.description,
            "rationale": self.rationale,
            "assignee": self.assignee,
            "adjuster": self.adjuster,
            "fraud_score": self.fraud_score,
            "complexity_score": self.complexity_score,
            "evidence": self.evidence,
            "ai_analysis": self.ai_analysis,
            "sources": self.sources,
            "attachments": self.attachments,
            "ml_scores": self.ml_scores,
            "routing": self.routing,
            "history": self.history,
        }


class DBFile(Base):
    __tablename__ = "files"
    
    filename = Column(String, primary_key=True)
    content = Column(LargeBinary, nullable=False)
    mime_type = Column(String, nullable=False)
