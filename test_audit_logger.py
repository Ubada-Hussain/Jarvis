import unittest
import sqlite3
import os
from unittest.mock import MagicMock
from core.audit_logger import SQLiteAuditLogger, AuditEvent
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.verification import ToolResult, VerificationStatus

class TestAuditLogger(unittest.TestCase):

    def setUp(self):
        self.db_path = "test_audit.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
        self.logger = SQLiteAuditLogger(db_path=self.db_path)
        self.approval_manager = MagicMock()
        self.gate = ExecutionGate(self.approval_manager, agent_name="TestAgent", audit_logger=self.logger)

        self.mock_tool = MagicMock(return_value=ToolResult(VerificationStatus.VERIFIED_SUCCESS, "Done"))
        self.gate.register(ToolMetadata("my_tool", RiskLevel.DESTRUCTIVE, "write", requires_confirmation=True, target_arg="file_path"), self.mock_tool)
        self.gate.register(ToolMetadata("safe_tool", RiskLevel.READ_ONLY, "read", requires_confirmation=False), self.mock_tool)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_successful_action_creates_audit_event(self):
        self.gate.execute("safe_tool", query="weather")
        events = self.logger.query_events(tool="safe_tool")
        
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event['agent'], "TestAgent")
        self.assertEqual(event['tool'], "safe_tool")
        self.assertEqual(event['execution_status'], "EXECUTED")
        self.assertEqual(event['verification_status'], "VERIFIED_SUCCESS")
        self.assertEqual(event['permission_status'], "GRANTED")
        self.assertEqual(event['target'], "weather")

    def test_permission_denied_creates_audit_event(self):
        self.approval_manager.require_approval.return_value = False
        
        self.gate.execute("my_tool", file_path="C:/windows/system32")
        events = self.logger.query_events(tool="my_tool")
        
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event['agent'], "TestAgent")
        self.assertEqual(event['tool'], "my_tool")
        self.assertEqual(event['execution_status'], "NOT_EXECUTED")
        self.assertEqual(event['permission_status'], "DENIED")
        self.assertEqual(event['confirmation_status'], "DENIED")
        self.assertEqual(event['target'], "C:/windows/system32")
        self.assertEqual(event['risk_level'], "DESTRUCTIVE")

    def test_sensitive_data_redaction(self):
        self.gate.execute("safe_tool", api_key="sk-1234567890abcdef")
        events = self.logger.query_events(tool="safe_tool")
        
        self.assertEqual(len(events), 1)
        event = events[0]
        # The target extractor should have sanitized it
        self.assertEqual(event['target'], "[REDACTED]")

    def test_audit_failure_does_not_crash_main_execution(self):
        # Break the logger intentionally by pointing it to a read-only or invalid path
        broken_logger = SQLiteAuditLogger(db_path="/invalid_dir/test_audit.db")
        broken_gate = ExecutionGate(self.approval_manager, audit_logger=broken_logger)
        broken_gate.register(ToolMetadata("safe_tool", RiskLevel.READ_ONLY, "read", requires_confirmation=False), self.mock_tool)
        
        # This should execute successfully despite the audit failing to write to disk
        result = broken_gate.execute("safe_tool")
        
        self.assertEqual(result.status, VerificationStatus.VERIFIED_SUCCESS)
        self.mock_tool.assert_called_once()
        
    def test_unknown_tool_creates_audit_event(self):
        self.gate.execute("ghost_tool")
        events = self.logger.query_events(tool="ghost_tool")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['execution_status'], "NOT_EXECUTED")
        self.assertEqual(events[0]['verification_status'], "NONE")

if __name__ == '__main__':
    unittest.main()
