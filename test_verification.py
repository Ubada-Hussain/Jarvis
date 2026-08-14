import os
import unittest
from unittest.mock import patch
from core.verification import VerificationStatus, ToolResult
from core.system_tools import delete_file

class TestVerification(unittest.TestCase):
    
    @patch('os.remove')
    @patch('os.path.exists')
    @patch('os.path.isfile')
    def test_delete_file_verified_success(self, mock_isfile, mock_exists, mock_remove):
        # exists before, is file before, DOES NOT exist after
        mock_exists.side_effect = [True, False]
        mock_isfile.return_value = True
        
        result = delete_file("dummy.txt")
        
        self.assertEqual(result.status, VerificationStatus.VERIFIED_SUCCESS)
        mock_remove.assert_called_once_with("dummy.txt")

    @patch('os.remove')
    @patch('os.path.exists')
    @patch('os.path.isfile')
    def test_delete_file_verified_failure_when_still_exists(self, mock_isfile, mock_exists, mock_remove):
        # exists before, is file before, STILL EXISTS after
        mock_exists.side_effect = [True, True]
        mock_isfile.return_value = True
        
        result = delete_file("dummy.txt")
        
        self.assertEqual(result.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("still exists after", result.evidence)
        mock_remove.assert_called_once_with("dummy.txt")

    @patch('os.remove')
    @patch('os.path.exists')
    def test_delete_file_verified_failure_when_does_not_exist_initially(self, mock_exists, mock_remove):
        mock_exists.return_value = False
        
        result = delete_file("dummy.txt")
        
        self.assertEqual(result.status, VerificationStatus.VERIFIED_FAILURE)
        self.assertIn("does not exist", result.message)
        mock_remove.assert_not_called()

if __name__ == '__main__':
    unittest.main()
