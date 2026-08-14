import unittest
from unittest.mock import MagicMock
from core.execution_gate import ExecutionGate, ToolMetadata, RiskLevel
from core.verification import ToolResult, VerificationStatus

class TestExecutionGate(unittest.TestCase):
    
    def setUp(self):
        self.approval_manager = MagicMock()
        self.gate = ExecutionGate(self.approval_manager)
        
        self.level_0_tool = MagicMock(return_value=ToolResult(VerificationStatus.VERIFIED_SUCCESS, "L0"))
        self.level_1_tool = MagicMock(return_value=ToolResult(VerificationStatus.VERIFIED_SUCCESS, "L1"))
        self.level_2_tool = MagicMock(return_value=ToolResult(VerificationStatus.VERIFIED_SUCCESS, "L2"))
        self.level_3_tool = MagicMock(return_value=ToolResult(VerificationStatus.VERIFIED_SUCCESS, "L3"))
        
        self.gate.register(ToolMetadata("t0", RiskLevel.READ_ONLY, "perm_read"), self.level_0_tool)
        self.gate.register(ToolMetadata("t1", RiskLevel.REVERSIBLE, "perm_write"), self.level_1_tool)
        self.gate.register(ToolMetadata("t2", RiskLevel.EXTERNAL_SIDE_EFFECT, "perm_ext"), self.level_2_tool)
        self.gate.register(ToolMetadata("t3", RiskLevel.DESTRUCTIVE, "perm_dest", requires_confirmation=True), self.level_3_tool)

    def test_level_0_executes_without_confirmation(self):
        result = self.gate.execute("t0")
        self.assertEqual(result.status, VerificationStatus.VERIFIED_SUCCESS)
        self.approval_manager.require_approval.assert_not_called()
        self.level_0_tool.assert_called_once()

    def test_level_1_executes_without_confirmation_by_default(self):
        result = self.gate.execute("t1")
        self.assertEqual(result.status, VerificationStatus.VERIFIED_SUCCESS)
        self.approval_manager.require_approval.assert_not_called()
        self.level_1_tool.assert_called_once()

    def test_level_2_requires_confirmation(self):
        self.approval_manager.require_approval.return_value = True
        result = self.gate.execute("t2")
        self.assertEqual(result.status, VerificationStatus.VERIFIED_SUCCESS)
        self.approval_manager.require_approval.assert_called_once()
        self.level_2_tool.assert_called_once()

    def test_level_3_requires_confirmation(self):
        self.approval_manager.require_approval.return_value = True
        result = self.gate.execute("t3")
        self.assertEqual(result.status, VerificationStatus.VERIFIED_SUCCESS)
        self.approval_manager.require_approval.assert_called_once()
        self.level_3_tool.assert_called_once()

    def test_user_denies_tool_never_executes(self):
        self.approval_manager.require_approval.return_value = False
        result = self.gate.execute("t3")
        
        self.assertEqual(result.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("DENIED", result.message)
        self.level_3_tool.assert_not_called()

    def test_missing_approval_manager_blocks_restricted_tool(self):
        gate_no_approval = ExecutionGate(None)
        gate_no_approval.register(ToolMetadata("t3", RiskLevel.DESTRUCTIVE, "perm_dest"), self.level_3_tool)
        
        result = gate_no_approval.execute("t3")
        self.assertEqual(result.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("Approval required but no ApprovalManager is configured", result.message)
        self.level_3_tool.assert_not_called()

    def test_unknown_tool_fails_safely(self):
        result = self.gate.execute("unknown_tool")
        self.assertEqual(result.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("not registered", result.message)

    def test_tool_must_return_toolresult(self):
        def bad_tool():
            return "Just a string"
            
        self.gate.register(ToolMetadata("bad", RiskLevel.READ_ONLY, "perm"), bad_tool)
        result = self.gate.execute("bad")
        
        # Must wrap in UNVERIFIED if the tool breaks the contract
        self.assertEqual(result.status, VerificationStatus.UNVERIFIED)
        self.assertIn("Warning: Tool did not return a ToolResult", result.evidence)

if __name__ == '__main__':
    unittest.main()
